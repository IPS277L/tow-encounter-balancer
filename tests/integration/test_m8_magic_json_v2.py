"""Actual v2 magic simulation backends and CLI; other routes remain v1."""
from copy import deepcopy
import json
from multiprocessing import active_children
import random
import subprocess
import sys
import unittest

from tests.integration.test_m8_magic_cli import ROOT, environment, invoke
from tests.unit.test_m8_magic_json import document as legacy_document
from tests.unit.test_m8_magic_json_v2 import document
from towr.adapters.magic_json_schema import validate_magic_simulation_document as validate
from towr.adapters.magic_simulation_json import (
    encode_magic_simulation_result as encode,
    parse_magic_simulation_request as parse,
)
from towr.application.magic_simulation_service import execute_magic_simulation
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation


class M8MagicJsonV2IntegrationTests(unittest.TestCase):
    def test_both_policies_preserve_full_sources_records_and_backend_aggregates(self):
        state, children = random.getstate(), {c.pid for c in active_children()}
        for opted in (False, True):
            with self.subTest(opted=opted):
                data = document(opted=opted)
                command = parse(json.dumps(data))
                before = deepcopy(command)
                sequential = run_npc_magic_simulation(command.request)
                process = run_npc_magic_simulation_parallel(command.request, workers=2, batch_size=3)
                self.assertEqual(process, sequential)
                self.assertEqual(process.source_request, command.request)
                for record in process.trials:
                    self.assertEqual(record.source_scenario, command.request.scenario)
                expected = summarize_npc_magic_simulation(sequential)
                output = json.loads(encode(command, expected))
                validate(output, 'result', schema_version='2')
                self.assertEqual(output['request'], data)
                self.assertEqual(parse(json.dumps(output['request'])), command)
                self.assertEqual(sum(output['summary']['outcome_counts'].values()), command.request.trials)
                self.assertEqual(command, before)
                if not opted:
                    legacy = parse(json.dumps(legacy_document()))
                    self.assertEqual(run_npc_magic_simulation(legacy.request), sequential)
        self.assertEqual(random.getstate(), state)
        self.assertEqual({c.pid for c in active_children()}, children)

    def test_existing_cli_v2_unicode_null_and_opted_sequential_and_process(self):
        for opted in (False, True):
            data = document(opted=opted)
            data['request_id'] = 'магия-雪'
            data['scenario']['wizard']['day_id'] = 'день-雪'
            command = parse(json.dumps(data))
            expected = json.loads(encode(command, execute_magic_simulation(command)))
            for mode in ('sequential', 'process'):
                with self.subTest(opted=opted, mode=mode):
                    data['execution'] = ({'mode': 'process', 'workers': 2, 'batch_size': 1}
                                         if mode == 'process' else {'mode': 'sequential'})
                    completed = invoke('simulate-magic', '-',
                        data=json.dumps(data, ensure_ascii=False).encode('utf-8'))
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    self.assertEqual(completed.stderr, b'')
                    self.assertTrue(completed.stdout.endswith(b'\n'))
                    self.assertIn('магия-雪'.encode('utf-8'), completed.stdout)
                    output = json.loads(completed.stdout)
                    validate(output, 'result', schema_version='2')
                    self.assertEqual(output['schema_version'], '2')
                    self.assertEqual(output['request'], data)
                    self.assertEqual(output['summary'], expected['summary'])
                    self.assertNotIn('trials', output)
                    self.assertNotIn('records', output)

    def test_public_v2_request_file_matches_native_and_echoes_exact_source(self):
        path = ROOT / 'docs/examples/m8/json/magic-simulation-v2.request.json'
        command = parse(path.read_bytes())
        expected = json.loads(encode(command, execute_magic_simulation(command)))
        completed = invoke('simulate-magic', str(path))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, b'')
        output = json.loads(completed.stdout)
        validate(output, 'result', schema_version='2')
        self.assertEqual(output, expected)
        self.assertEqual(output['request'], json.loads(path.read_bytes()))
        self.assertEqual(parse(json.dumps(output['request'])), command)

    def test_cli_input_errors_follow_complete_decode_version_table(self):
        invalid = document()
        invalid['scenario']['miscast_continuation']['facts']['no_cross_zone_close'] = False
        missing = document()
        del missing['scenario']['miscast_continuation']
        prefix = b'{"schema_version":"2","request_id":"seen",'
        cases = [
            (prefix + b'"x":1.0}', '1', 'invalid_input', None),
            (prefix + b'"x":1e0}', '1', 'invalid_input', None),
            (prefix + b'"x":NaN}', '1', 'invalid_json', None),
            (prefix + b'"x":"\\ud800"}', '1', 'invalid_json', None),
            (prefix + b'"x":0,"x":1}', '1', 'invalid_json', None),
            (json.dumps(invalid).encode(), '2', 'invalid_input', invalid['request_id']),
            (json.dumps(missing).encode(), '2', 'invalid_input', missing['request_id']),
            (json.dumps(dict(document(), schema_version='3')).encode(), '1', 'unsupported_version', document()['request_id']),
        ]
        for raw, version, code, request_id in cases:
            with self.subTest(version=version, code=code, raw=raw[:45]):
                completed = invoke('simulate-magic', '-', data=raw)
                self.assertEqual(completed.returncode, 2, completed.stderr)
                output = json.loads(completed.stdout)
                validate(output, 'error', schema_version=version)
                self.assertEqual(output['schema_version'], version)
                self.assertEqual(output['request_id'], request_id)
                self.assertEqual(output['error']['code'], code)
                self.assertNotIn('summary', output)
                self.assertNotIn(b'Traceback', completed.stderr)

    def test_cli_v2_runtime_failure_is_v2_without_partial_or_private_output(self):
        script = (
            "from unittest.mock import patch\n"
            "from towr.cli import main\n"
            "cause = OSError('private pool unavailable')\n"
            "cause.add_note('private worker note')\n"
            "with patch('towr.simulation.npc_magic_parallel.ProcessPoolExecutor', side_effect=cause):\n"
            "    raise SystemExit(main(['simulate-magic', '-']))\n"
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
        self.assertEqual(output['error']['code'], 'simulation_failed')
        self.assertIsNone(output['error']['path'])
        self.assertNotIn('summary', output)
        self.assertNotIn(b'private', completed.stdout + completed.stderr)
        self.assertNotIn(b'Traceback', completed.stderr)

    def test_balance_magic_and_six_other_routes_do_not_accept_v2(self):
        cases = (
            ('balance-magic', 'magic_balance_error', 'm8/json/magic-balance-v1.request.json'),
            ('simulate', 'simulation_error', 'm4/ranged-v1.request.json'),
            ('balance', 'balance_error', 'm5/json/balance-v1.request.json'),
            ('simulate-melee', 'melee_simulation_error', 'm6/json/melee-simulation-v1.request.json'),
            ('balance-melee', 'melee_balance_error', 'm6/json/melee-balance-v1.request.json'),
            ('simulate-mixed', 'mixed_simulation_error', 'm7/json/mixed-simulation-v1.request.json'),
            ('balance-mixed', 'mixed_balance_error', 'm7/json/mixed-balance-v1.request.json'),
        )
        for route, kind, relative in cases:
            with self.subTest(route=route):
                data = json.loads((ROOT / 'docs/examples' / relative).read_text(encoding='utf-8'))
                data['schema_version'] = '2'
                completed = invoke(route, '-', data=json.dumps(data).encode())
                self.assertEqual(completed.returncode, 2, completed.stderr)
                output = json.loads(completed.stdout)
                self.assertEqual(output['schema_version'], '1')
                self.assertEqual(output['kind'], kind)
                self.assertEqual(output['request_id'], data['request_id'])
                self.assertEqual(output['error']['code'], 'unsupported_version')
                self.assertEqual(output['error']['path'], '/schema_version')
                self.assertNotIn('summary', output)
