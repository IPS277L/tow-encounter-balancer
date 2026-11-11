"""One actual Aim/Second Action encounter crosses compact spawn records."""
import pickle
import unittest

from tests.support.pc_hochland_scenarios import make_pc_hochland_scenario
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


class PcHochlandProcessTests(unittest.TestCase):
    def test_actual_aim_spend_records_and_aggregate_match_spawn(self):
        source = make_pc_hochland_scenario(pc_count=2,enemy_count=3,max_rounds=2,
            npc_toughness=6,npc_armour_bonus=2)
        request = PcMeleeSimulationRequest(source,42,2)
        sequential = run_pc_melee_simulation(request)
        parallel = run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(parallel,sequential)
        summary = summarize_pc_melee_simulation(parallel)
        self.assertEqual(summary,summarize_pc_melee_simulation(sequential))
        self.assertEqual(summary.aim.total_action_count,4)
        self.assertEqual(summary.aim.total_second_action_spend_count,4)
        self.assertEqual(summary.total_glorious_spend_count,0)
        for record in parallel.records:
            self.assertEqual(record.source_scenario,source)
            self.assertEqual(record.aim.total_action_count,2)
            self.assertEqual(record.aim.total_second_action_spend_count,2)
            self.assertEqual(pickle.loads(pickle.dumps(record)),record)


if __name__ == '__main__':
    unittest.main()
