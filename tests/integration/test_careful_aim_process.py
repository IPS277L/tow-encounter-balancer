"""Representative generic-stat/Application transport across real spawn."""
from dataclasses import replace
from unittest import TestCase

from tests.helpers import SequenceRandom
from tests.integration.test_careful_aim_native import scene
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def literal_factory(seed):
    # Known Test values for transport equivalence, not a probability estimate.
    return SequenceRandom([1,10]+[1]*4+[10]*3+[1,1,10]+[10]*500)


class CarefulAimProcessTests(TestCase):
    def test_pure_throwing_npc_counts_and_receipts_match_sequential_execution(self):
        source=replace(scene(npc_careful=True),max_rounds=2)
        request=PcMeleeSimulationRequest(source,42,2)
        sequential=run_pc_melee_simulation(request,rng_factory=literal_factory)
        parallel=run_pc_melee_simulation_parallel(request,workers=2,batch_size=1,rng_factory=literal_factory)
        self.assertEqual(parallel,sequential)
        summary=summarize_pc_melee_simulation(parallel)
        self.assertEqual(summary,summarize_pc_melee_simulation(sequential))
        self.assertIsNone(summary.aim)
        self.assertEqual(summary.npc_aim_counts[0].count,2)
        self.assertIsNone(source.enemies[0].definition.generated_components.ranged)
