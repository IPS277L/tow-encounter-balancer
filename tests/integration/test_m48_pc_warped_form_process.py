"""One representative process check for the new end-phase source and metrics."""
import json
import unittest

from tests.integration.test_m48_pc_warped_form_json import warped_document
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


class PcWarpedFormProcessTests(unittest.TestCase):
    def test_selected_close_policy_and_activation_metrics_match_sequential(self):
        raw=warped_document()
        raw['scenario']['max_rounds']=4
        raw['simulation'].update(master_seed='42',trials=4)
        request=parse_pc_melee_simulation_request(json.dumps(raw)).request
        sequential=run_pc_melee_simulation(request)
        parallel=run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(parallel,sequential)
        summary=summarize_pc_melee_simulation(sequential)
        self.assertEqual(summarize_pc_melee_simulation(parallel),summary)
        self.assertGreater(summary.total_npc_warped_form_count,0)
        for record in parallel.records:
            self.assertEqual(record.source_scenario.npc_warped_form_policies,request.scenario.npc_warped_form_policies)
            self.assertFalse(hasattr(record,'steps'))
            self.assertEqual(tuple(row.actor_id for row in record.npc_warped_form_counts),request.scenario.enemy_activation_order)


if __name__=='__main__':
    unittest.main()
