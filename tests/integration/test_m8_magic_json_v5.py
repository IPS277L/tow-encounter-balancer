"""Current Magic JSON contract: deterministic admission and source guards."""
import json
import unittest

from tests.integration.test_m8_magic_cli import ROOT, invoke
from towr.adapters.magic_json_schema import validate_magic_simulation_document
from towr.adapters.magic_simulation_json import (
    encode_magic_simulation_result, parse_magic_simulation_request,
)
from towr.application.magic_simulation_service import execute_magic_simulation


class M8MagicJsonV5IntegrationTests(unittest.TestCase):

    def test_simulation_and_balance_help_reflect_supported_magic_versions(self):
        completed = invoke('-h')
        self.assertEqual(completed.returncode, 0, completed.stderr)
        normalized = b' '.join(completed.stdout.split())
        self.assertEqual(normalized.count(b'v6 request'), 2)


if __name__ == '__main__':
    unittest.main()
