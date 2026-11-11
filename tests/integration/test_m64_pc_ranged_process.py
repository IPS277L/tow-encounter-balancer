"""One actual Repeater ordinary/bonus/Reload representative crosses spawn."""
from dataclasses import replace
from pathlib import Path
from random import Random
import unittest

from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.domain.pc_melee_result_models import PcAttackProof
from towr.domain.pc_ranged_models import PcRangedReloadProof
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


class PcRangedProcessTests(unittest.TestCase):
    def test_actual_bonus_ordinary_and_reload_sources_records_match_spawn(self):
        example = Path(__file__).resolve().parents[2]/'docs/examples/m64/pc-melee-simulation.request.json'
        request = replace(parse_pc_melee_simulation_request(example.read_bytes()).request, trials=2)
        journals = tuple(run_pc_melee_scenario(request.scenario, Random(request.seed_for(index)))
            for index in range(request.trials))
        reloads = tuple(step for journal in journals for step in journal.steps
            if type(step.proof) is PcRangedReloadProof)
        self.assertTrue(reloads)
        self.assertTrue(any(step.proof.result.state.loaded for step in reloads))
        shots = tuple(step for journal in journals for step in journal.steps
            if type(step.proof) is PcAttackProof and step.proof.ranged_shot is not None)
        self.assertEqual({step.proof.request.actor_id for step in shots}, {'pc1','pc2','pc3','pc4'})
        bonus = tuple(step for step in shots
            if step.proof.ranged_shot.preparation.source_request.uses_optional_reload_bonus)
        ordinary = tuple(step for step in shots if step not in bonus)
        self.assertTrue(bonus)
        self.assertTrue(ordinary)
        self.assertTrue(all(not step.state.participant(step.proof.request.actor_id).ranged.loaded for step in bonus))
        self.assertTrue(all(step.state.participant(step.proof.request.actor_id).ranged
            == step.source.participant(step.proof.request.actor_id).ranged for step in ordinary))
        sequential = run_pc_melee_simulation(request)
        parallel = run_pc_melee_simulation_parallel(request, workers=2, batch_size=1)
        self.assertEqual(parallel, sequential)
        self.assertEqual(summarize_pc_melee_simulation(parallel), summarize_pc_melee_simulation(sequential))
        for record, journal in zip(parallel.records, journals, strict=True):
            self.assertEqual(record.source_scenario, request.scenario)
            self.assertEqual(record.executed_actions, journal.executed_actions)
            for actor in request.scenario.pc_activation_order:
                self.assertEqual(record.source_scenario.participant(actor).pc.ranged,
                    request.scenario.participant(actor).pc.ranged)


if __name__ == '__main__':
    unittest.main()
