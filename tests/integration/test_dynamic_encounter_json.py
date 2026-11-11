from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from towr.adapters.dynamic_encounter_json import (
    DynamicEncounterInputError, DynamicEncounterExecutionError,
    parse_dynamic_encounter_request, execute_dynamic_encounter,
    encode_dynamic_encounter_result, encode_dynamic_encounter_error,
    validate_dynamic_encounter_document,
)
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.application.dynamic_encounter import validate_dynamic_encounter_result
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


EXAMPLE = Path('docs/examples/dynamic/search.request.json')


class DynamicEncounterJsonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(EXAMPLE.read_bytes())
        cls.command = parse_dynamic_encounter_request(EXAMPLE.read_bytes())
        cls.result = execute_dynamic_encounter(cls.command)

    def test_party_without_enemy_reserve_and_exact_source_echo(self):
        self.assertNotIn('enemies', self.document)
        self.assertNotIn('target_priority', self.document['party'][0])
        result = json.loads(encode_dynamic_encounter_result(self.command, self.result))
        self.assertEqual(result['source_request'], self.document)
        self.assertEqual(result['total_trials'], 12)
        self.assertEqual(len(result['explored']), 3)
        self.assertEqual(len(result['validations']), 2)

    def test_all_replays_parse_and_one_finalist_reproduces_outcomes(self):
        result = json.loads(encode_dynamic_encounter_result(self.command, self.result))
        for candidate in result['explored'] + result['validations']:
            command = parse_pc_melee_simulation_request(json.dumps(candidate['replay']))
            self.assertEqual(command.request.trials, candidate['trials'])
        candidate = result['validations'][0]
        command = parse_pc_melee_simulation_request(json.dumps(candidate['replay']))
        summary = summarize_pc_melee_simulation(run_pc_melee_simulation(command.request))
        self.assertEqual(summary.outcome_counts.objective_achieved / summary.trials, candidate['win_rate'])

    def test_semantic_invalid_inputs_rejected_before_search(self):
        cases = [('/search/max_total_trials', 1), ('/search/master_seed', str(2**64)),
            ('/npc_count/minimum', 3), ('/targets/win_rate', dict(numerator=2, denominator=1)),
            ('/targets/win_rate', dict(numerator=6, denominator=10)),
            ('/targets/win_rate', dict(numerator=10**30+1, denominator=10**30)),
            ('/targets/started_rounds', dict(numerator=4, denominator=1))]
        for path, value in cases:
            document = deepcopy(self.document)
            section, field = path.strip('/').split('/')
            document[section][field] = value
            with self.subTest(path=path), patch('towr.adapters.dynamic_encounter_json.search_dynamic_encounter') as search:
                with self.assertRaises(DynamicEncounterInputError) as caught:
                    parse_dynamic_encounter_request(json.dumps(document))
                search.assert_not_called()
                self.assertEqual(caught.exception.code.value, 'invalid_input')
                self.assertEqual(caught.exception.request_id, self.command.request_id)

    def test_closed_shapes_and_supported_components(self):
        cases = [dict(enemies=[]), dict(party=[dict(self.document['party'][0], target_priority=['npc'])]),
            dict(search_space=dict(self.document['search_space'], weapon=['axe'])),
            dict(search_space=dict(self.document['search_space'], abilities=[['blood_rage']])),
            dict(search_space=dict(self.document['search_space'], melee=[True])),
            dict(execution=dict(mode='process'))]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(DynamicEncounterInputError):
                parse_dynamic_encounter_request(json.dumps(dict(self.document, **change)))

    def test_strict_json_and_current_version(self):
        for raw, code in [('{}', 'invalid_input'), ('{"a":1,"a":2}', 'invalid_json'),
                ('{"x":NaN}', 'invalid_json'), ('{"x":0.5}', 'invalid_input'),
                (b'\xff', 'invalid_json'),
                (json.dumps(dict(self.document, schema_version='2')), 'unsupported_version')]:
            with self.subTest(raw=raw), self.assertRaises(DynamicEncounterInputError) as caught:
                parse_dynamic_encounter_request(raw)
            self.assertEqual(caught.exception.code.value, code)
            validate_dynamic_encounter_document(json.loads(encode_dynamic_encounter_error(caught.exception)), 'error')

    def test_forged_accounting_source_and_ranking_rejected(self):
        for result in (replace(self.result, total_trials=0),
                replace(self.result, explored=self.result.explored[::-1]),
                replace(self.result, validations=()),
                replace(self.result, proposal_limit_reached=True)):
            with self.subTest(result=result.total_trials), self.assertRaises(ValueError):
                encode_dynamic_encounter_result(self.command, result)
        validate_dynamic_encounter_result(self.result)

    def test_execution_failure_has_no_partial_report(self):
        with patch('towr.adapters.dynamic_encounter_json.search_dynamic_encounter', side_effect=RuntimeError('worker failed')):
            with self.assertRaises(DynamicEncounterExecutionError) as caught:
                execute_dynamic_encounter(self.command)
        document = json.loads(encode_dynamic_encounter_error(caught.exception))
        self.assertEqual(document['error']['code'], 'execution_failed')
        self.assertEqual(document['request_id'], self.command.request_id)
        self.assertNotIn('explored', document)

    def test_module_cli_file_and_stdin_produce_same_complete_result(self):
        env = dict(os.environ, PYTHONPATH='src')
        expected = encode_dynamic_encounter_result(self.command, self.result).encode('utf-8')
        for name in (str(EXAMPLE), '-'):
            process = subprocess.run([sys.executable, '-m', 'towr', 'generate-encounter', name],
                input=EXAMPLE.read_bytes() if name == '-' else None, capture_output=True, env=env, timeout=40)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(process.stdout, expected)
            self.assertEqual(process.stderr, b'')

    def test_cli_invalid_input_is_structured_and_nonzero(self):
        process = subprocess.run([sys.executable, '-m', 'towr', 'generate-encounter', '-'],
            input=b'{}', capture_output=True, env=dict(os.environ, PYTHONPATH='src'), timeout=20)
        self.assertEqual(process.returncode, 2)
        document = json.loads(process.stdout)
        validate_dynamic_encounter_document(document, 'error')
        self.assertEqual(document['error']['code'], 'invalid_input')
        self.assertIn(b'invalid_input', process.stderr)


if __name__ == '__main__':
    unittest.main()
