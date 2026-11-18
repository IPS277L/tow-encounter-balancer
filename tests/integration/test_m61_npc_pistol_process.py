"""One actual NPC Reload representative agrees across sequential and spawn."""
import json
from random import Random
import unittest

from tests.integration.test_m61_npc_pistol_json import request_document
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.domain.pc_melee_result_models import PcAttackProof
from towr.domain.pc_npc_ranged_models import PcNpcRangedReloadProof, pc_npc_ranged_weapon
from towr.domain.weapon_inventory_models import weapon_unit_id
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def process_request():
    return parse_pc_melee_simulation_request(json.dumps(request_document())).request


class NpcPistolProcessTests(unittest.TestCase):
    def test_actual_reload_cycles_full_sources_records_and_summary_match_spawn(self):
        request = process_request()
        journals = tuple(run_pc_melee_scenario(request.scenario,
            Random(request.seed_for(index))) for index in range(request.trials))
        reloads = tuple(step for journal in journals for step in journal.steps
            if type(step.proof) is PcNpcRangedReloadProof)
        self.assertTrue(reloads)
        self.assertTrue(any(step.proof.result.state.loaded for step in reloads))
        self.assertTrue(any(not step.proof.result.state.loaded for step in reloads))
        self.assertTrue(all(step.proof.result.previous_state.weapon_instance_id
            == weapon_unit_id(step.proof.request.actor_id,'weapon',0) for step in reloads))
        for journal in journals:
            shots = tuple(step for step in journal.steps if type(step.proof) is PcAttackProof
                and step.proof.npc_ranged_shot is not None)
            self.assertEqual({step.proof.request.actor_id for step in shots}, {'minion1', 'minion2'})
            for shot in shots:
                actor = shot.proof.request.actor_id
                self.assertTrue(pc_npc_ranged_weapon(shot.source, actor).loaded)
                self.assertFalse(pc_npc_ranged_weapon(shot.state, actor).loaded)
        sequential = run_pc_melee_simulation(request)
        parallel = run_pc_melee_simulation_parallel(request, workers=2, batch_size=1)
        self.assertEqual(parallel, sequential)
        self.assertEqual(summarize_pc_melee_simulation(parallel),
            summarize_pc_melee_simulation(sequential))
        for record, journal in zip(parallel.records, journals, strict=True):
            self.assertEqual(record.source_scenario, request.scenario)
            self.assertEqual(record.source_scenario.npc_ranged_policies,
                request.scenario.npc_ranged_policies)
            self.assertEqual(record.executed_actions, journal.executed_actions)
            self.assertFalse(hasattr(record, 'steps'))
            self.assertFalse(hasattr(record, 'reload_count'))


if __name__ == '__main__':
    unittest.main()
