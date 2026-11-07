"""One spawn representative for the two-profile Crown source and compact costs."""
import json
import unittest

from tests.unit.test_m9_pc_melee_json import document
from tests.unit.test_m51_great_stag_execution import ACTOR, scene
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.domain.test_models import Skill
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def process_request():
    raw = document()
    raw['scenario'] = scenario_document(scene(rounds=4))
    raw['simulation'].update(master_seed='42', trials=4)
    return parse_pc_melee_simulation_request(json.dumps(raw)).request


class PcGreatStagProcessTests(unittest.TestCase):
    def test_actual_trample_records_source_and_summary_match_spawn(self):
        request = process_request()
        sequential = run_pc_melee_simulation(request)
        parallel = run_pc_melee_simulation_parallel(request, workers=2, batch_size=1)
        self.assertEqual(parallel, sequential)
        summary = summarize_pc_melee_simulation(sequential)
        self.assertEqual(summarize_pc_melee_simulation(parallel), summary)
        self.assertGreater(summary.total_npc_extra_attack_count, 0)
        for record in parallel.records:
            self.assertEqual(record.source_scenario, request.scenario)
            self.assertEqual(record.source_scenario.npc_extra_attack_actor_ids, (ACTOR,))
            self.assertEqual(tuple(p.skill for p in record.source_scenario.enemy(ACTOR).definition.attacks),
                (Skill.MELEE, Skill.BRAWN))
            self.assertEqual(tuple(row.actor_id for row in record.npc_extra_attack_counts), (ACTOR,))
            self.assertFalse(hasattr(record, 'steps'))


if __name__ == '__main__':
    unittest.main()
