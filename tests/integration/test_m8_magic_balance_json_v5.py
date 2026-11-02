"""ADR-0058 balance5 reaches real generation, staged simulation and CLI."""
import json
import unittest

from tests.integration.test_m8_magic_cli import ROOT, invoke
from towr.adapters.magic_json_schema import validate_magic_balance_document
from towr.adapters.magic_balance_json import (
    encode_magic_balance_result, parse_magic_balance_request,
)
from towr.application.magic_balance_service import execute_magic_balance


REQUEST = ROOT / 'docs/examples/m8/json/magic-balance-v5.request.json'


class M8MagicBalanceJsonV5IntegrationTests(unittest.TestCase):
    def test_public_request_generates_and_runs_through_real_balance_cli(self):
        raw = json.loads(REQUEST.read_bytes())
        command = parse_magic_balance_request(json.dumps(raw))
        result = execute_magic_balance(command)
        generated = result.generation_result.evaluation_request.candidates
        self.assertTrue(generated)
        self.assertTrue(all(candidate.scenario.crushed_rib_continuation is
                            command.generation_request.crushed_rib_continuation for candidate in generated))
        expected = encode_magic_balance_result(command, result)
        completed = invoke('balance-magic', str(REQUEST))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, b'')
        self.assertEqual(completed.stdout.decode('utf-8'), expected)
        output = json.loads(completed.stdout)
        validate_magic_balance_document(output, 'result', schema_version='5')
        self.assertEqual(output['request'], raw)

    def test_balance_help_and_decoded_mismatch_use_version_five(self):
        help_result = invoke('-h')
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertEqual(help_result.stdout.count(b'v5'), 2)
        raw = json.loads(REQUEST.read_bytes())
        raw['generation']['crushed_rib_continuation'] = None
        completed = invoke('balance-magic', '-', data=json.dumps(raw).encode('utf-8'))
        self.assertEqual(completed.returncode, 2)
        output = json.loads(completed.stdout)
        validate_magic_balance_document(output, 'error', schema_version='5')
        self.assertEqual((output['schema_version'], output['request_id'], output['error']['code'],
                          output['error']['path']),
                         ('5', raw['request_id'], 'invalid_input', '/generation/crushed_rib_continuation'))


if __name__ == '__main__':
    unittest.main()
