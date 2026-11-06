"""A new typed source policy crosses the process boundary without journal costs."""
import json
import unittest

from tests.integration.test_m46_pc_bestigor_json import bestigor_document
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


class PcBestigorProcessTests(unittest.TestCase):
    def test_selected_blood_rage_policy_records_and_summary_match_sequential(self):
        request=parse_pc_melee_simulation_request(json.dumps(bestigor_document())).request
        sequential=run_pc_melee_simulation(request)
        parallel=run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(parallel,sequential)
        self.assertEqual(summarize_pc_melee_simulation(parallel),summarize_pc_melee_simulation(sequential))
        self.assertTrue(request.scenario.npc_blood_rage_actor_ids)
        for record in parallel.records:
            self.assertEqual(record.source_scenario.npc_blood_rage_actor_ids,request.scenario.npc_blood_rage_actor_ids)
            self.assertFalse(hasattr(record,'steps'))


if __name__=='__main__':
    unittest.main()
