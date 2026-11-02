"""Real balance v2 generation/stages/backends and existing CLI route."""
from copy import deepcopy
import json
from multiprocessing import active_children
import random
import subprocess
import sys
import unittest

from tests.integration.test_m8_magic_cli import ROOT, environment, invoke
from tests.unit.test_m8_magic_balance_json import document as legacy_document, generation_failure_document
from tests.unit.test_m8_magic_balance_json_v2 import document
from towr.adapters.magic_balance_json import encode_magic_balance_result as encode, parse_magic_balance_request as parse
from towr.adapters.magic_json_schema import validate_magic_balance_document as validate
from towr.application.magic_balance_service import execute_magic_balance


class M8MagicBalanceJsonV2IntegrationTests(unittest.TestCase):
    def test_real_sequential_and_process_keep_full_family_and_report_sources(self):
        state, children = random.getstate(), {c.pid for c in active_children()}
        for opted in (False, True):
            data = document(opted=opted)
            original, results, outputs = deepcopy(data), [], []
            for execution in ({'mode': 'sequential'}, {'mode': 'process', 'workers': 2, 'batch_size': 3}):
                with self.subTest(opted=opted, execution=execution):
                    command = parse(json.dumps(dict(data, execution=execution)))
                    before = deepcopy(command)
                    result = execute_magic_balance(command)
                    generated = result.generation_result
                    self.assertEqual(generated.source_request, command.generation_request)
                    self.assertEqual(result.evaluation_result.source_request, generated.evaluation_request)
                    expected_policy = command.generation_request.miscast_continuation
                    catalog = {c.candidate_id: c for c in generated.evaluation_request.candidates}
                    for candidate in catalog.values():
                        self.assertEqual(candidate.scenario.miscast_continuation, expected_policy)
                    for report in result.evaluation_result.stage_reports:
                        for row in report.candidates:
                            self.assertEqual(row.assessment.summary.source_request.scenario, catalog[row.candidate_id].scenario)
                    output = json.loads(encode(command, result))
                    validate(output, 'result', schema_version='2')
                    self.assertEqual(output['request'], dict(data, execution=execution))
                    self.assertEqual(parse(json.dumps(output['request'])), command)
                    self.assertEqual(output['total_trials'], result.evaluation_result.total_trials)
                    self.assertLessEqual(output['total_trials'], output['planned_trials'])
                    self.assertEqual(command, before)
                    output['request'].pop('execution')
                    results.append(result)
                    outputs.append(output)
            self.assertEqual(results[0], results[1])
            self.assertEqual(outputs[0], outputs[1])
            if not opted:
                self.assertEqual(execute_magic_balance(parse(json.dumps(legacy_document()))), results[0])
            self.assertEqual(data, original)
        self.assertEqual(random.getstate(), state)
        self.assertEqual({c.pid for c in active_children()}, children)

    def test_cli_null_and_opted_unicode_sequential_and_process_match_native(self):
        for opted in (False, True):
            data = document(opted=opted)
            data['request_id'] = 'подбор-雪'
            data['reserve']['scenario']['wizard']['day_id'] = 'день-雪'
            command = parse(json.dumps(data))
            expected = json.loads(encode(command, execute_magic_balance(command)))
            for execution in ({'mode': 'sequential'}, {'mode': 'process', 'workers': 2, 'batch_size': 1}):
                with self.subTest(opted=opted, execution=execution):
                    data['execution'] = execution
                    completed = invoke('balance-magic', '-', data=json.dumps(data, ensure_ascii=False).encode('utf-8'))
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    self.assertEqual(completed.stderr, b'')
                    self.assertTrue(completed.stdout.endswith(b'\n'))
                    self.assertIn('подбор-雪'.encode('utf-8'), completed.stdout)
                    output = json.loads(completed.stdout)
                    validate(output, 'result', schema_version='2')
                    self.assertEqual(output['schema_version'], '2')
                    self.assertEqual(output['request'], data)
                    expected['request']['execution'] = execution
                    self.assertEqual(output, expected)
                    self.assertNotIn('records', output)

    def test_public_v2_request_file_is_real_native_roundtrip(self):
        path = ROOT / 'docs/examples/m8/json/magic-balance-v2.request.json'
        command = parse(path.read_bytes())
        expected = json.loads(encode(command, execute_magic_balance(command)))
        completed = invoke('balance-magic', str(path))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, b'')
        output = json.loads(completed.stdout)
        validate(output, 'result', schema_version='2')
        self.assertEqual(output, expected)
        self.assertEqual(output['request'], json.loads(path.read_bytes()))
        self.assertEqual(parse(json.dumps(output['request'])), command)

    def test_cli_errors_use_fallback_only_before_complete_strict_decode(self):
        invalid = document()
        invalid['generation']['miscast_continuation']['facts']['no_cross_zone_close'] = False
        mismatch = document()
        mismatch['generation']['miscast_continuation'] = None
        missing = document()
        del missing['reserve']['scenario']['miscast_continuation']
        prefix = b'{"schema_version":"2","request_id":"seen",'
        cases = [(prefix + b'"x":1.0}', '1', 'invalid_input', None),
                 (prefix + b'"x":1e0}', '1', 'invalid_input', None),
                 (prefix + b'"x":NaN}', '1', 'invalid_json', None),
                 (prefix + b'"x":"\\ud800"}', '1', 'invalid_json', None),
                 (prefix + b'"x":0,"x":1}', '1', 'invalid_json', None),
                 (json.dumps(invalid).encode(), '2', 'invalid_input', invalid['request_id']),
                 (json.dumps(mismatch).encode(), '2', 'invalid_input', mismatch['request_id']),
                 (json.dumps(missing).encode(), '2', 'invalid_input', missing['request_id']),
                 (json.dumps(dict(document(), schema_version='6')).encode(), '1', 'unsupported_version', document()['request_id'])]
        for raw, version, code, request_id in cases:
            with self.subTest(version=version, code=code, raw=raw[:45]):
                completed = invoke('balance-magic', '-', data=raw)
                self.assertEqual(completed.returncode, 2, completed.stderr)
                output = json.loads(completed.stdout)
                validate(output, 'error', schema_version=version)
                self.assertEqual((output['schema_version'], output['request_id']), (version, request_id))
                self.assertEqual(output['error']['code'], code)
                for key in ('candidate_id', 'counts', 'stage_index'):
                    self.assertIsNone(output['error'][key])
                self.assertNotIn('stage_reports', output)
                self.assertNotIn(b'Traceback', completed.stderr)

    def test_real_generation_failure_after_valid_preflight_emits_v2_known_counts(self):
        data = document(source=generation_failure_document())
        command = parse(json.dumps(data))
        self.assertEqual(command.generation_request.candidate_count, 4)
        completed = invoke('balance-magic', '-', data=json.dumps(data).encode())
        self.assertEqual(completed.returncode, 3, completed.stderr)
        output = json.loads(completed.stdout)
        validate(output, 'error', schema_version='2')
        self.assertEqual(output['schema_version'], '2')
        self.assertEqual(output['request_id'], data['request_id'])
        self.assertEqual(output['error']['code'], 'generation_failed')
        self.assertEqual(output['error']['path'], '/generation')
        self.assertEqual(output['error']['counts'], [1, 0])
        self.assertIsNotNone(output['error']['candidate_id'])
        self.assertIsNone(output['error']['stage_index'])
        self.assertNotIn('stage_reports', output)
        self.assertNotIn(b'Traceback', completed.stderr)

    def test_cli_process_failure_is_v2_evaluation_error_with_no_private_or_partial_output(self):
        script = (
            "from unittest.mock import patch\n"
            "from towr.cli import main\n"
            "cause = OSError('private pool unavailable')\n"
            "cause.add_note('private worker note')\n"
            "with patch('towr.simulation.npc_magic_parallel.ProcessPoolExecutor', side_effect=cause):\n"
            "    raise SystemExit(main(['balance-magic', '-']))\n"
        )
        data = document()
        data['execution'] = {'mode': 'process', 'workers': 2, 'batch_size': 1}
        completed = subprocess.run([sys.executable, '-c', script], input=json.dumps(data).encode(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT, env=environment(), timeout=45)
        self.assertEqual(completed.returncode, 3, completed.stderr)
        output = json.loads(completed.stdout)
        validate(output, 'error', schema_version='2')
        self.assertEqual(output['schema_version'], '2')
        self.assertEqual(output['request_id'], data['request_id'])
        self.assertEqual(output['error']['code'], 'evaluation_failed')
        self.assertEqual(output['error']['path'], '/evaluation')
        self.assertEqual(output['error']['stage_index'], 0)
        self.assertIsNotNone(output['error']['candidate_id'])
        self.assertIsNone(output['error']['counts'])
        self.assertNotIn('stage_reports', output)
        self.assertNotIn(b'private', completed.stdout + completed.stderr)
        self.assertNotIn(b'Traceback', completed.stderr)
