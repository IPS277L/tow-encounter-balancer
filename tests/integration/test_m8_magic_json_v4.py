"""Current Magic JSON contract: deterministic admission and source guards."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import unittest

from tests.integration.test_m8_magic_cli import ROOT, environment, invoke
from tests.unit.test_m8_magic_json_v4 import document
from tests.unit.test_m8_miscast_continuation_policy import continuation_policy
from tests.unit.test_m8_stationary_wound_generation import collapse_request
from towr.adapters import magic_simulation_json as sim, magic_balance_json as bal
from towr.adapters.magic_json_schema import validate_magic_simulation_document, validate_magic_balance_document
from towr.application.magic_balance_models import MagicBalanceCommand
from towr.application.magic_balance_service import execute_magic_balance
from towr.application.magic_simulation_service import execute_magic_simulation
from towr.application.ranged_simulation_models import SimulationExecutionOptions, SimulationExecutionMode
from towr.domain.npc_magic_scenario_models import NpcMagicStationaryWoundPolicy, NpcMagicRepeatedLegSpasmPolicy


class M8MagicJsonV4IntegrationTests(unittest.TestCase):

    def test_cli_runtime_failure_uses_own_four_and_hides_foreign_cause(self):
        script = '''
from unittest.mock import patch
from towr.cli import main
from towr.application.magic_simulation_errors import MagicSimulationExecutionError
cause = MagicSimulationExecutionError('foreign-private-id', schema_version='6')
cause.add_note('private-worker-note')
with patch('towr.simulation.npc_magic_parallel.ProcessPoolExecutor', side_effect=cause):
    raise SystemExit(main(['simulate-magic', '-']))
'''
        data = document()
        data['execution'] = {'mode': 'process', 'workers': 1, 'batch_size': 1}
        completed = subprocess.run([sys.executable, '-c', script], input=json.dumps(data).encode(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT, env=environment(), timeout=45)
        self.assertEqual(completed.returncode, 3, completed.stderr)
        output = json.loads(completed.stdout)
        validate_magic_simulation_document(output, 'error', schema_version='6')
        self.assertEqual((output['schema_version'], output['request_id'], output['error']['code']),
                         ('6', data['request_id'], 'simulation_failed'))
        self.assertNotIn(b'private', completed.stdout + completed.stderr)

    def test_actual_late_generation_failure_has_no_partial_catalog_and_keeps_counts(self):
        source = collapse_request(conflict_actor='far-blocker')
        miscast = continuation_policy()
        stationary = NpcMagicStationaryWoundPolicy.LEG_SPASM_STAND_AND_CONTINUE
        repeated = NpcMagicRepeatedLegSpasmPolicy.STAND_ONCE_WITH_JOURNAL_WITNESSES
        source = replace(source, template_scenario=replace(source.template_scenario,
            miscast_continuation=miscast, stationary_wound_continuation=stationary,
            repeated_leg_spasm_continuation=repeated), miscast_continuation=miscast,
            stationary_wound_continuation=stationary, repeated_leg_spasm_continuation=repeated)
        order = tuple(dict.fromkeys(p.definition.id for p in source.template_scenario.initial.roster.participants))
        command = MagicBalanceCommand('late-v4', source,
            SimulationExecutionOptions(SimulationExecutionMode.SEQUENTIAL), order, '6')
        completed = invoke('balance-magic', '-', data=json.dumps(bal._request_document(command)).encode())
        self.assertEqual(completed.returncode, 3, completed.stderr)
        output = json.loads(completed.stdout)
        validate_magic_balance_document(output, 'error', schema_version='6')
        self.assertEqual((output['schema_version'], output['request_id'], output['error']['code']),
                         ('6', 'late-v4', 'generation_failed'))
        self.assertEqual(output['error']['counts'], [1, 1])
        self.assertIsNone(output['error']['stage_index'])
        self.assertNotIn('candidates', output)
        self.assertNotIn('stage_reports', output)

    def test_late_evaluation_failure_after_real_stage_keeps_four_and_privacy(self):
        script = '''
from unittest.mock import patch
from towr.application import magic_evaluation_service as evaluation
from towr.cli import main
import sys
original = evaluation.run_npc_magic_simulation
fail_at = int(sys.argv[1])
calls = 0
def run(source):
    global calls
    calls += 1
    if calls == fail_at:
        error = OSError('private late evaluation failure')
        error.add_note('private note')
        raise error
    return original(source)
with patch.object(evaluation, 'run_npc_magic_simulation', side_effect=run):
    status = main(['balance-magic', '-'])
assert calls == fail_at
raise SystemExit(status)
'''
        data = document(balance=True)
        first_stage_count = bal.parse_magic_balance_request(json.dumps(data)).generation_request.candidate_count
        completed = subprocess.run([sys.executable, '-c', script, str(first_stage_count + 1)], input=json.dumps(data).encode(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT, env=environment(), timeout=45)
        self.assertEqual(completed.returncode, 3, completed.stderr)
        output = json.loads(completed.stdout)
        validate_magic_balance_document(output, 'error', schema_version='6')
        self.assertEqual((output['schema_version'], output['request_id'], output['error']['code']),
                         ('6', data['request_id'], 'evaluation_failed'))
        self.assertEqual(output['error']['stage_index'], 1)
        self.assertIsNotNone(output['error']['candidate_id'])
        self.assertNotIn('stage_reports', output)
        self.assertNotIn(b'private', completed.stdout + completed.stderr)


if __name__ == '__main__':
    unittest.main()
