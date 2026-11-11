"""One spawn representative preserves Pistol source and actual reload cycles."""
from dataclasses import replace
import json
from random import Random
import unittest

from tests.unit.test_m9_pc_melee_json import document
from tests.unit.test_m54_pistol_execution import scene, shots, steps
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.domain.pc_ranged_models import PcRangedReloadProof
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def process_request():
    source = scene(rounds=9, durable=True, ballistic_skill=4, shooting=6,
        initiative=4, dexterity=6)
    enemy = source.enemies[0]
    attack = enemy.definition.attacks[0]
    source = replace(source, enemies=(replace(enemy,
        definition=replace(enemy.definition, attacks=(replace(attack,
            test_profile=replace(attack.test_profile, threshold=1)),))),))
    raw = document()
    raw['scenario'] = scenario_document(source)
    raw['simulation'].update(master_seed='42', trials=4)
    return parse_pc_melee_simulation_request(json.dumps(raw)).request


class PcPistolProcessTests(unittest.TestCase):
    def test_actual_reload_cycles_and_complete_source_match_spawn(self):
        request = process_request()
        journals = tuple(run_pc_melee_scenario(request.scenario,
            Random(request.seed_for(index))) for index in range(request.trials))
        self.assertTrue(all(steps(journal, PcRangedReloadProof) for journal in journals))
        self.assertTrue(any(len(shots(journal)) >= 2 for journal in journals))
        self.assertTrue(any(len(journal.state.participant('pc1').ranged.reload_cycle_ids) >= 2
            for journal in journals))
        sequential = run_pc_melee_simulation(request)
        parallel = run_pc_melee_simulation_parallel(request, workers=2, batch_size=1)
        self.assertEqual(parallel, sequential)
        self.assertEqual(summarize_pc_melee_simulation(parallel),
            summarize_pc_melee_simulation(sequential))
        for record, journal in zip(parallel.records, journals, strict=True):
            self.assertEqual(record.source_scenario, request.scenario)
            self.assertEqual(record.source_scenario.participant('pc1').pc.ranged,
                request.scenario.participant('pc1').pc.ranged)
            self.assertEqual(record.executed_actions, journal.executed_actions)
            self.assertFalse(hasattr(record, 'steps'))
            self.assertFalse(hasattr(record, 'reload_count'))


if __name__ == '__main__':
    unittest.main()
