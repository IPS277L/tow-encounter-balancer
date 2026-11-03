"""Current Magic JSON contract: deterministic admission and source guards."""
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
                validate(output, 'result', schema_version='6')
                self.assertEqual(output['request'], data)
                self.assertEqual(parse(json.dumps(output['request'])), command)
                self.assertEqual(sum(output['summary']['outcome_counts'].values()), command.request.trials)
                self.assertEqual(command, before)
                if not opted:
                    legacy = parse(json.dumps(legacy_document()))
                    self.assertEqual(run_npc_magic_simulation(legacy.request), sequential)
        self.assertEqual(random.getstate(), state)
        self.assertEqual({c.pid for c in active_children()}, children)



    def test_cli_input_errors_follow_complete_decode_version_table(self):
        invalid = document()
        invalid['scenario']['miscast_continuation']['facts']['no_cross_zone_close'] = False
        missing = document()
        del missing['scenario']['miscast_continuation']
        prefix = b'{"schema_version":"6","request_id":"seen",'
        cases = [
            (prefix + b'"x":1.0}', '6', 'invalid_input', None),
            (prefix + b'"x":1e0}', '6', 'invalid_input', None),
            (prefix + b'"x":NaN}', '6', 'invalid_json', None),
            (prefix + b'"x":"\\ud800"}', '6', 'invalid_json', None),
            (prefix + b'"x":0,"x":1}', '6', 'invalid_json', None),
            (json.dumps(invalid).encode(), '6', 'invalid_input', invalid['request_id']),
            (json.dumps(missing).encode(), '6', 'invalid_input', missing['request_id']),
            (json.dumps(dict(document(), schema_version='7')).encode(), '6', 'unsupported_version', document()['request_id']),
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
        validate(output, 'error', schema_version='6')
        self.assertEqual(output['schema_version'], '6')
        self.assertEqual(output['request_id'], data['request_id'])
        self.assertEqual(output['error']['code'], 'simulation_failed')
        self.assertIsNone(output['error']['path'])
        self.assertNotIn('summary', output)
        self.assertNotIn(b'private', completed.stdout + completed.stderr)
        self.assertNotIn(b'Traceback', completed.stderr)
