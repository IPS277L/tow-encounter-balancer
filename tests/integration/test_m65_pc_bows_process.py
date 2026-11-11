"""One actual Short volley/approach/backup encounter crosses sequential/spawn."""
from dataclasses import replace
from pathlib import Path
from random import Random
import unittest

from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.domain.pc_melee_result_models import PcAttackProof, PcBackupWeaponDrawProof
from towr.domain.pc_short_opening_models import PcNpcApproachProof
from towr.domain.reload_models import FreeReloadWeaponState
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


class PcBowsProcessTests(unittest.TestCase):
    def test_actual_opening_approach_backup_records_and_summary_match_spawn(self):
        example = Path(__file__).resolve().parents[2]/'docs/examples/m65/pc-melee-simulation.request.json'
        request = replace(parse_pc_melee_simulation_request(example.read_bytes()).request,trials=2)
        journals = tuple(run_pc_melee_scenario(request.scenario,Random(request.seed_for(index)))
            for index in range(request.trials))
        approaches = tuple(step for journal in journals for step in journal.steps
            if type(step.proof) is PcNpcApproachProof)
        draws = tuple(step for journal in journals for step in journal.steps
            if type(step.proof) is PcBackupWeaponDrawProof)
        self.assertTrue(approaches)
        self.assertTrue(draws)
        for journal in journals:
            self.assertEqual(len(journal.state.approached_npc_ids),len(set(journal.state.approached_npc_ids)))
            shots = tuple(step for step in journal.steps if type(step.proof) is PcAttackProof
                and step.proof.ranged_shot is not None)
            self.assertEqual({step.proof.request.actor_id for step in shots},{'pc1','pc2','pc3'})
            for shot in shots:
                actor = shot.proof.request.actor_id
                self.assertIs(type(shot.state.participant(actor).ranged),FreeReloadWeaponState)
                self.assertEqual(shot.source.participant(actor).ranged,shot.state.participant(actor).ranged)
            for index,step in enumerate(journal.steps):
                if type(step.proof) is not PcBackupWeaponDrawProof:
                    continue
                actor = step.proof.actor_id
                self.assertEqual(step.source.participant(actor).ranged,journal.state.participant(actor).ranged)
                followups = tuple(later for later in journal.steps[index+1:]
                    if type(later.proof) is PcAttackProof and later.proof.request.actor_id==actor)
                self.assertTrue(all(later.proof.ranged_shot is None for later in followups))
        self.assertTrue(any(type(step.proof) is PcAttackProof
            and step.proof.request.actor_id in request.scenario.pc_activation_order
            and step.proof.ranged_shot is None for journal in journals for step in journal.steps))
        sequential = run_pc_melee_simulation(request)
        parallel = run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(parallel,sequential)
        self.assertEqual(summarize_pc_melee_simulation(parallel),summarize_pc_melee_simulation(sequential))
        for record,journal in zip(parallel.records,journals,strict=True):
            self.assertEqual(record.source_scenario,request.scenario)
            self.assertEqual(record.executed_actions,journal.executed_actions)
            self.assertEqual(record.source_scenario.short_range_opening,request.scenario.short_range_opening)


if __name__=='__main__':
    unittest.main()
