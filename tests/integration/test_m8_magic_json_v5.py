"""ADR-0058 simulation5 reaches the real service and public CLI unchanged."""
import json
import unittest

from tests.integration.test_m8_magic_cli import ROOT, invoke
from towr.adapters.magic_json_schema import validate_magic_simulation_document
from towr.adapters.magic_simulation_json import (
    encode_magic_simulation_result, parse_magic_simulation_request,
)
from towr.application.magic_simulation_service import execute_magic_simulation


class M8MagicJsonV5IntegrationTests(unittest.TestCase):
    def test_actual_cli_runs_and_echoes_matching_crushed_rib_permission(self):
        request = json.loads((ROOT / 'docs/examples/m8/json/magic-simulation-v5.request.json').read_bytes())
        command = parse_magic_simulation_request(json.dumps(request))
        expected = encode_magic_simulation_result(command, execute_magic_simulation(command))
        completed = invoke('simulate-magic', '-', data=json.dumps(request).encode('utf-8'))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, b'')
        self.assertEqual(completed.stdout.decode('utf-8'), expected)
        output = json.loads(completed.stdout)
        validate_magic_simulation_document(output, 'result', schema_version='5')
        self.assertEqual(output['request'], request)
        self.assertEqual(output['request']['scenario']['crushed_rib_continuation'],
                         'next_test_with_journal_witnesses')

    def test_simulation_and_balance_help_reflect_supported_magic_versions(self):
        completed = invoke('-h')
        self.assertEqual(completed.returncode, 0, completed.stderr)
        normalized = b' '.join(completed.stdout.split())
        self.assertEqual(normalized.count(b'v1/v2/v3/v4/v5/v6 request'), 2)


if __name__ == '__main__':
    unittest.main()
