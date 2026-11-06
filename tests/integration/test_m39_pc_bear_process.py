"""One process representative covers the new source and compact counters."""
import json
import unittest

from tests.integration.test_m39_pc_bear_json import bear_document
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


class PcBearProcessTests(unittest.TestCase):
    def test_actual_extra_attack_records_and_summary_match_sequential(self):
        request = parse_pc_melee_simulation_request(json.dumps(bear_document())).request
        sequential = run_pc_melee_simulation(request)
        parallel = run_pc_melee_simulation_parallel(request, workers=2, batch_size=1)
        self.assertEqual(parallel, sequential)
        summary = summarize_pc_melee_simulation(parallel)
        self.assertEqual(summary, summarize_pc_melee_simulation(sequential))
        self.assertGreater(summary.total_npc_extra_attack_count, 0)
        for record in parallel.records:
            self.assertEqual(tuple(item.actor_id for item in record.npc_extra_attack_counts),
                ('bear1','footpad1'))
            self.assertFalse(hasattr(record,'steps'))


if __name__ == '__main__':
    unittest.main()
