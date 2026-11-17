"""Current dynamic execution admission, source guards and real process boundary."""
from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from jsonschema import ValidationError

from towr.adapters.dynamic_encounter_json import (
    DynamicEncounterInputError, DynamicEncounterExecutionError,
    encode_dynamic_encounter_error, encode_dynamic_encounter_result,
    execute_dynamic_encounter, parse_dynamic_encounter_request,
    validate_dynamic_encounter_document,
)
from towr.application.dynamic_encounter import DynamicEncounterCancelled, DynamicEncounterResult
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions


EXAMPLE = Path('docs/examples/dynamic/search.request.json')


class DynamicProcessAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.document = json.loads(EXAMPLE.read_bytes())

    def test_closed_modes_have_typed_execution_separate_from_search_facts(self):
        sequential = parse_dynamic_encounter_request(json.dumps(self.document))
        self.assertEqual(sequential.execution,
            SimulationExecutionOptions(SimulationExecutionMode.SEQUENTIAL))
        for workers in (1, 4, 61):
            raw = dict(self.document, execution=dict(mode='process', workers=workers))
            with self.subTest(workers=workers):
                validate_dynamic_encounter_document(raw)
                process = parse_dynamic_encounter_request(json.dumps(raw))
                self.assertEqual(process.execution,
                    SimulationExecutionOptions(SimulationExecutionMode.PROCESS, workers, 1))
                self.assertEqual(process.request, sequential.request)
                self.assertEqual(json.loads(process.source_json), raw)

    def test_malformed_execution_rejected_before_dispatch(self):
        cases = [None, [], {}, dict(mode='thread'), dict(mode='process'),
            dict(mode='sequential', workers=1), dict(mode='sequential', batch_size=1),
            dict(mode='process', workers=4, batch_size=1),
            dict(mode='process', workers=4, extra=True)]
        cases += [dict(mode='process', workers=value)
            for value in (None, True, False, 0, -1, 62, '4', [4])]
        for execution in cases:
            raw = dict(self.document, execution=execution)
            with self.subTest(execution=execution):
                with self.assertRaises(ValidationError):
                    validate_dynamic_encounter_document(raw)
                with patch('towr.adapters.dynamic_encounter_json.search_dynamic_encounter') as search:
                    with self.assertRaises(DynamicEncounterInputError) as caught:
                        parse_dynamic_encounter_request(json.dumps(raw))
                    self.assertEqual(caught.exception.code.value, 'invalid_input')
                    self.assertEqual(caught.exception.request_id, raw['request_id'])
                    self.assertEqual(caught.exception.path, '/execution')
                    search.assert_not_called()

    def test_float_worker_tokens_and_missing_execution_rejected(self):
        for value in (1.0, 4.5):
            raw = dict(self.document, execution=dict(mode='process', workers=value))
            with self.subTest(value=value), self.assertRaises(DynamicEncounterInputError):
                parse_dynamic_encounter_request(json.dumps(raw))
        raw = deepcopy(self.document)
        del raw['execution']
        with self.assertRaises(DynamicEncounterInputError):
            parse_dynamic_encounter_request(json.dumps(raw))

    def test_dispatch_passes_exact_execution_and_callbacks(self):
        for execution in (dict(mode='sequential'), dict(mode='process', workers=4)):
            command = parse_dynamic_encounter_request(json.dumps(dict(self.document, execution=execution)))
            cancel = lambda: False
            progress = lambda value: None
            result = object()
            with self.subTest(execution=execution), patch(
                    'towr.adapters.dynamic_encounter_json.search_dynamic_encounter', return_value=result) as search:
                self.assertIs(execute_dynamic_encounter(command,
                    cancel_requested=cancel, on_progress=progress), result)
                search.assert_called_once_with(command.request, execution=command.execution,
                    cancel_requested=cancel, on_progress=progress)

    def test_forged_execution_is_rejected_before_result_validation(self):
        command = parse_dynamic_encounter_request(json.dumps(dict(self.document,
            execution=dict(mode='process', workers=4))))
        result = DynamicEncounterResult(command.request, (), (), 0, 0, False)
        options = (SimulationExecutionOptions(SimulationExecutionMode.SEQUENTIAL),
            SimulationExecutionOptions(SimulationExecutionMode.PROCESS, 2, 1),
            SimulationExecutionOptions(SimulationExecutionMode.PROCESS, 4, 2))
        for execution in options:
            with self.subTest(execution=execution), patch(
                    'towr.adapters.dynamic_encounter_json.validate_dynamic_encounter_result') as validate:
                with self.assertRaisesRegex(ValueError, 'wire source differs'):
                    encode_dynamic_encounter_result(replace(command, execution=execution), result)
                validate.assert_not_called()
        for field in ('mode', 'workers'):
            raw = json.loads(command.source_json)
            raw['execution'] = (dict(mode='sequential') if field == 'mode'
                else dict(mode='process', workers=2))
            with self.subTest(source_field=field), self.assertRaisesRegex(ValueError, 'wire source differs'):
                encode_dynamic_encounter_result(replace(command, source_json=json.dumps(raw)), result)

    def test_equal_but_invalid_execution_is_rejected_before_result_validation(self):
        command=parse_dynamic_encounter_request(json.dumps(dict(self.document,
            execution=dict(mode='process',workers=4))))
        result=DynamicEncounterResult(command.request,(),(),0,0,False)
        for field,value in (('mode','process'),('workers',4.0),('batch_size',True)):
            forged=deepcopy(command.execution)
            object.__setattr__(forged,field,value)
            self.assertEqual(forged,command.execution)
            with self.subTest(field=field),patch(
                    'towr.adapters.dynamic_encounter_json.validate_dynamic_encounter_result') as validate:
                with self.assertRaises((TypeError,ValueError)):
                    encode_dynamic_encounter_result(replace(command,execution=forged),result)
                validate.assert_not_called()

    def test_process_failure_and_cancellation_do_not_become_partial_reports(self):
        command = parse_dynamic_encounter_request(json.dumps(dict(self.document,
            execution=dict(mode='process', workers=2))))
        with patch('towr.adapters.dynamic_encounter_json.search_dynamic_encounter',
                side_effect=RuntimeError('worker failed')):
            with self.assertRaises(DynamicEncounterExecutionError) as caught:
                execute_dynamic_encounter(command)
        error = json.loads(encode_dynamic_encounter_error(caught.exception))
        self.assertEqual(error['error']['code'], 'execution_failed')
        self.assertEqual(error['request_id'], command.request_id)
        self.assertNotIn('explored', error)
        cancellation = DynamicEncounterCancelled('cancelled')
        with patch('towr.adapters.dynamic_encounter_json.search_dynamic_encounter', side_effect=cancellation):
            with self.assertRaises(DynamicEncounterCancelled) as caught:
                execute_dynamic_encounter(command)
        self.assertIs(caught.exception, cancellation)


class DynamicProcessJsonSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = json.loads(EXAMPLE.read_bytes())
        raw['npc_count'] = dict(minimum=1, maximum=1)
        raw['max_rounds'] = 1
        raw['targets']['started_rounds'] = dict(numerator=1, denominator=1)
        raw['search'].update(max_candidates=2, exploration_trials=2,
            finalist_trials=2, top_k=1, max_total_trials=6)
        cls.sequential = parse_dynamic_encounter_request(json.dumps(raw))
        raw['execution'] = dict(mode='process', workers=2)
        cls.document = raw
        cls.command = parse_dynamic_encounter_request(json.dumps(raw))
        cls.result = execute_dynamic_encounter(cls.command)

    def test_spawn_matches_sequential_result_and_preserves_source_echo(self):
        self.assertEqual(self.result, execute_dynamic_encounter(self.sequential))
        report = json.loads(encode_dynamic_encounter_result(self.command, self.result))
        validate_dynamic_encounter_document(report, 'result')
        self.assertEqual(report['source_request'], self.document)
        self.assertEqual(report['total_trials'], 6)
        # Downloaded single-battle replays select their own execution mode.
        for candidate in report['explored'] + report['validations']:
            self.assertEqual(candidate['replay']['execution'], dict(mode='sequential'))

    def test_module_cli_process_stdin_matches_current_json_report(self):
        process = subprocess.run([sys.executable, '-m', 'towr', 'generate-encounter', '-'],
            input=json.dumps(self.document).encode('utf-8'), capture_output=True,
            env=dict(os.environ, PYTHONPATH='src'), timeout=60)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stderr, b'')
        self.assertEqual(json.loads(process.stdout),
            json.loads(encode_dynamic_encounter_result(self.command, self.result)))


if __name__ == '__main__':
    unittest.main()
