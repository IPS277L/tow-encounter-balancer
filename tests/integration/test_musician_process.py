"""One representative real spawn boundary for current music sources/results."""
from dataclasses import replace
from unittest import TestCase

from tests.integration.test_musician_native import music_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def literal_factory(seed):
    # A literal rule/transport fixture; not an estimate of a win probability.
    return ScriptedD10([1,10,10,10,10]+[10]*10+[1,10,1,10,10]+[10]*10)


class MusicianProcessTests(TestCase):
    def test_actual_spawn_keeps_sources_receipts_and_observations(self):
        source=replace(music_scenario(),enemy_target_priority=('pc2','pc1','pc3'))
        request=PcMeleeSimulationRequest(source,42,2)
        sequential=run_pc_melee_simulation(request,rng_factory=literal_factory)
        parallel=run_pc_melee_simulation_parallel(request,workers=2,batch_size=1,rng_factory=literal_factory)
        self.assertEqual(parallel,sequential)
        summary=summarize_pc_melee_simulation(parallel)
        self.assertEqual(summary,summarize_pc_melee_simulation(sequential))
        self.assertEqual(summary.music_counts[0].actions,2)
        self.assertEqual(summary.music_counts[0].protected_ties,2)
