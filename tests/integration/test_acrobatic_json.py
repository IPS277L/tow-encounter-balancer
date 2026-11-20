"""One actual seeded Acrobatic path through current JSON and real spawn.

The small two-trial batch checks source transport and parity, not statistical
accuracy. A separate ordinary Random journal proves the real movement source.
"""
import json
import pickle
from random import Random
import unittest

from tests.integration.test_acrobatic_native_movement import source
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json import (
    encode_pc_melee_simulation_result, parse_pc_melee_simulation_request,
)
from towr.domain.pc_give_ground_models import PcGiveGroundProof
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


class AcrobaticJsonTests(unittest.TestCase):
    def test_actual_blocked_give_ground_and_paid_source_survive_json_and_spawn(self):
        battle = source(pc_target=True)
        native = run_pc_melee_scenario(battle, Random(0))
        self.assertIsNone(native.unsupported)
        movement, = tuple(step for step in native.steps if type(step.proof) is PcGiveGroundProof)
        self.assertEqual(movement.proof.request.mover_id, 'pc')
        self.assertEqual(movement.proof.request.path_entity_ids, ('minion1',))
        self.assertEqual(movement.proof.request.acrobatic.actor_id, 'pc')
        self.assertEqual(movement.proof.request.acrobatic.talent, battle.party[0].talents[0])
        self.assertEqual(pickle.loads(pickle.dumps(movement.proof)), movement.proof)
        self.assertEqual(movement.source.round_state, movement.state.round_state)
        self.assertEqual(native.executed_actions, 2)

        raw = dict(schema_version='1', kind='pc_melee_simulation', request_id='acrobatic:spawn',
            ruleset='towr-pg1.4-gmg1.1', scenario=scenario_document(battle),
            simulation=dict(master_seed='0', trials=2), execution=dict(mode='sequential'))
        sequential_command = parse_pc_melee_simulation_request(json.dumps(raw))
        raw['execution'] = dict(mode='process', workers=2, batch_size=1)
        process_command = parse_pc_melee_simulation_request(json.dumps(raw))
        self.assertEqual(sequential_command.request, process_command.request)
        self.assertEqual(process_command.request.scenario, battle)
        self.assertTrue(process_command.request.scenario.battlefield.enemy_zone_blocking)

        sequential = run_pc_melee_simulation(sequential_command.request)
        execution = process_command.execution
        parallel = run_pc_melee_simulation_parallel(process_command.request,
            workers=execution.workers, batch_size=execution.batch_size)
        self.assertEqual(parallel, sequential)
        self.assertTrue(all(record.executed_actions <= 2 for record in parallel.records))
        self.assertTrue(all(record.immediate_attack_counts is None for record in parallel.records))
        summary = summarize_pc_melee_simulation(parallel)
        self.assertEqual(summary, summarize_pc_melee_simulation(sequential))
        self.assertEqual(summary.total_action_count, sum(record.executed_actions for record in parallel.records))
        self.assertLessEqual(summary.total_action_count, 4)
        document = json.loads(encode_pc_melee_simulation_result(process_command, summary))
        self.assertEqual(document['request']['scenario'], raw['scenario'])
        self.assertEqual(document['request']['execution'], raw['execution'])
        self.assertTrue(document['request']['scenario']['battlefield']['enemy_zone_blocking'])
        talent, = document['request']['scenario']['party'][0]['talents']
        self.assertEqual(talent['id'], 'acrobatic')
        self.assertEqual(talent['acquisitions'][0]['phase'], 'advancement')
        self.assertEqual(talent['acquisitions'][0]['funding'], 'xp')
        self.assertEqual(document['summary']['total_action_count'], summary.total_action_count)


if __name__ == '__main__':
    unittest.main()
