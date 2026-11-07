"""One actual process representative for authored Shield and runtime protection."""
from dataclasses import replace
import json
from random import Random
import unittest

from tests.unit.test_m9_pc_melee_json import document
from tests.unit.test_m53_shield_execution import book_scene, incoming
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def process_request():
    source = book_scene(rounds=3, net_goblins=1, footpads=1)
    source = replace(source, party=(replace(source.party[0],
        pc=replace(source.party[0].pc, melee=1, strength=1)),))
    raw = document()
    raw['scenario'] = scenario_document(source)
    raw['simulation'].update(master_seed='42', trials=4)
    return parse_pc_melee_simulation_request(json.dumps(raw)).request


class PcShieldProcessTests(unittest.TestCase):
    def test_actual_net_shield_protection_and_complete_source_match_spawn(self):
        request = process_request()
        journals = tuple(run_pc_melee_scenario(request.scenario,
            Random(request.seed_for(index))) for index in range(request.trials))
        self.assertTrue(any(step.proof.request.actor_id == 'net_goblin1'
            and step.proof.protection.source_request.selected_skill is Skill.DEFENCE
            for journal in journals for step in incoming(journal)))
        self.assertTrue(all(journal.state.participant('pc1').shield is not None for journal in journals))
        sequential = run_pc_melee_simulation(request)
        parallel = run_pc_melee_simulation_parallel(request, workers=2, batch_size=1)
        self.assertEqual(parallel, sequential)
        self.assertEqual(summarize_pc_melee_simulation(parallel),
            summarize_pc_melee_simulation(sequential))
        for record, journal in zip(parallel.records, journals, strict=True):
            self.assertEqual(record.source_scenario, request.scenario)
            self.assertEqual(record.source_scenario.participant('pc1').shield,
                request.scenario.participant('pc1').shield)
            self.assertEqual(record.executed_actions, journal.executed_actions)
            self.assertFalse(hasattr(record, 'steps'))
            self.assertFalse(hasattr(record, 'shield_pickup_count'))


if __name__ == '__main__':
    unittest.main()
