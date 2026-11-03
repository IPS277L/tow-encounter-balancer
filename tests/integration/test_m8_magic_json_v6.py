"""Current Magic JSON contract: deterministic admission and source guards."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from tests.integration.test_m8_magic_cli import ROOT, environment
from tests.unit.test_m8_magic_json_v6 import document
from towr.adapters import magic_simulation_json as sim
from towr.adapters.magic_json_schema import validate_magic_simulation_document
from towr.application.magic_simulation_errors import MagicSimulationExecutionError
from towr.application.magic_simulation_service import execute_magic_simulation


def invoke_v6(command, raw, *, console=False):
    executable = Path(sys.executable).with_name('towr.exe' if sys.platform == 'win32' else 'towr')
    args = [str(executable)] if console else [sys.executable, '-m', 'towr']
    return subprocess.run([*args, command, '-'], input=json.dumps(raw).encode('utf-8'),
        capture_output=True, cwd=ROOT, env=environment(), timeout=60)


def small_document():
    raw = document()
    raw['simulation']['trials'] = 2
    raw['simulation']['round_budget'] = 2
    return raw


class M8MagicJsonV6IntegrationTests(unittest.TestCase):
    def test_module_console_and_both_backends_echo_full_v6_source_with_equal_aggregates(self):
        raw = small_document()
        command = sim.parse_magic_simulation_request(json.dumps(raw))
        original = deepcopy(command)
        expected = execute_magic_simulation(command)
        for console in (False, True):
            for mode in ('sequential', 'process'):
                request = deepcopy(raw)
                request['execution'] = {'mode': mode}
                if mode == 'process':
                    request['execution'].update(workers=2, batch_size=1)
                selected = sim.parse_magic_simulation_request(json.dumps(request))
                encoded = sim.encode_magic_simulation_result(selected, expected)
                completed = invoke_v6('simulate-magic', request, console=console)
                with self.subTest(console=console, mode=mode):
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    self.assertEqual(completed.stderr, b'')
                    self.assertEqual(completed.stdout.decode('utf-8'), encoded)
                    output = json.loads(completed.stdout)
                    validate_magic_simulation_document(output, 'result', schema_version='6')
                    self.assertEqual(output['request'], request)
                    self.assertEqual(output['request']['scenario']['battered_leg_continuation'],
                                     {'endurance_profile': {'dice': 2, 'threshold': 5}, 'prone_policy': None})
        self.assertEqual(command, original)

    def test_both_perspectives_preserve_the_authored_profile_and_objective(self):
        raw = small_document()
        for opposite in (False, True):
            request = deepcopy(raw)
            if opposite:
                request['scenario']['perspective_side'] = 'opposition'
                request['scenario']['objective_target_ids'] = ['wizard', 'ally']
            command = sim.parse_magic_simulation_request(json.dumps(request))
            result = execute_magic_simulation(command)
            output = json.loads(sim.encode_magic_simulation_result(command, result))
            self.assertEqual(output['request'], request)
            self.assertEqual(result.source_request.scenario.battered_leg_continuation,
                             command.request.scenario.battered_leg_continuation)

    def test_corrupt_equal_profile_is_refused_before_rng_or_process_pool(self):
        raw = small_document()
        raw['scenario']['battered_leg_continuation']['endurance_profile']['dice'] = 1
        command = sim.parse_magic_simulation_request(json.dumps(raw))
        forged = deepcopy(command)
        object.__setattr__(forged.request.scenario.battered_leg_continuation.endurance_profile, 'dice', True)
        self.assertEqual(forged, command)
        with patch('towr.application.magic_simulation_service.run_npc_magic_simulation') as sequential,\
                patch('towr.application.magic_simulation_service.run_npc_magic_simulation_parallel') as parallel:
            with self.assertRaises(MagicSimulationExecutionError) as caught:
                execute_magic_simulation(forged)
            self.assertEqual((caught.exception.schema_version, caught.exception.request_id),
                             ('6', command.request_id))
            self.assertIsInstance(caught.exception.__cause__, TypeError)
            sequential.assert_not_called()
            parallel.assert_not_called()

    def test_cli_known_v6_bad_profile_and_lexical_fallback_are_distinct(self):
        raw = small_document()
        raw['scenario']['battered_leg_continuation']['endurance_profile']['threshold'] = 11
        completed = invoke_v6('simulate-magic', raw)
        self.assertEqual(completed.returncode, 2)
        output = json.loads(completed.stdout)
        validate_magic_simulation_document(output, 'error', schema_version='6')
        self.assertEqual((output['schema_version'], output['request_id']), ('6', raw['request_id']))
        lexical = subprocess.run([sys.executable, '-m', 'towr', 'simulate-magic', '-'],
            input=b'{"schema_version":"6","request_id":"untrusted","n":2.0}',
            capture_output=True, cwd=ROOT, env=environment(), timeout=30)
        self.assertEqual(lexical.returncode, 2)
        output = json.loads(lexical.stdout)
        self.assertEqual((output['schema_version'], output['request_id']), ('6', None))

    def test_actual_cli_runtime_failure_uses_v6_and_hides_private_cause(self):
        script = """
from unittest.mock import patch
from towr.cli import main
with patch('towr.application.magic_simulation_service.run_npc_magic_simulation',
           side_effect=RuntimeError('private worker cause')):
    raise SystemExit(main(['simulate-magic', '-']))
"""
        raw = small_document()
        completed = subprocess.run([sys.executable, '-c', script], input=json.dumps(raw).encode(),
            capture_output=True, cwd=ROOT, env=environment(), timeout=30)
        self.assertEqual(completed.returncode, 3, completed.stderr)
        output = json.loads(completed.stdout)
        validate_magic_simulation_document(output, 'error', schema_version='6')
        self.assertEqual((output['schema_version'], output['request_id'], output['error']['code']),
                         ('6', raw['request_id'], 'simulation_failed'))
        self.assertNotIn(b'private', completed.stdout + completed.stderr)
        self.assertNotIn(b'Traceback', completed.stderr)


if __name__ == '__main__':
    unittest.main()
