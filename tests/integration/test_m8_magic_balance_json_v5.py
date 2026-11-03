"""Current Magic JSON contract: deterministic admission and source guards."""
import json
import unittest

from tests.integration.test_m8_magic_cli import ROOT, invoke
from towr.adapters.magic_json_schema import validate_magic_balance_document
from towr.adapters.magic_balance_json import (
    encode_magic_balance_result, parse_magic_balance_request,
)
from towr.application.magic_balance_service import execute_magic_balance


from tests.unit.test_m8_magic_balance_json_v5 import document


class M8MagicBalanceJsonV5IntegrationTests(unittest.TestCase):

    def test_balance_help_and_decoded_mismatch_use_version_five(self):
        raw = document(crushed=True)
        raw['generation']['crushed_rib_continuation'] = None
        completed = invoke('balance-magic', '-', data=json.dumps(raw).encode('utf-8'))
        self.assertEqual(completed.returncode, 2)
        output = json.loads(completed.stdout)
        validate_magic_balance_document(output, 'error', schema_version='6')
        self.assertEqual((output['schema_version'], output['request_id'], output['error']['code'],
                          output['error']['path']),
                         ('6', raw['request_id'], 'invalid_input', '/generation/crushed_rib_continuation'))


if __name__ == '__main__':
    unittest.main()
