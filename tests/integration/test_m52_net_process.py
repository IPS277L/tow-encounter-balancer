"""One spawn representative for finite Net source and unchanged compact records."""
from dataclasses import replace
import json
from random import Random
import unittest

from tests.unit.test_m9_pc_melee_json import document
from tests.unit.test_m52_net_execution import ACTOR, incoming, scene
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.domain.attack_models import ConditionImpactSpec
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def process_request():
    source = scene(rounds=3)
    source = replace(source, party=tuple(replace(member,
        pc=replace(member.pc, melee=1, strength=1)) for member in source.party))
    raw = document()
    raw['scenario'] = scenario_document(source)
    raw['simulation'].update(master_seed='42', trials=4)
    return parse_pc_melee_simulation_request(json.dumps(raw)).request


class PcNetProcessTests(unittest.TestCase):
    def test_actual_net_records_full_source_and_summary_match_spawn(self):
        request = process_request()
        # Establish actual Net execution in the same seeded representative;
        # compact trials intentionally retain neither journal nor a Net counter.
        journals = tuple(run_pc_melee_scenario(request.scenario,
            Random(request.seed_for(index))) for index in range(request.trials))
        self.assertTrue(any(type(step.proof.execution.resolution.attack.impact_spec)
            is ConditionImpactSpec for result in journals for step in incoming(result)))
        sequential = run_pc_melee_simulation(request)
        parallel = run_pc_melee_simulation_parallel(request, workers=2, batch_size=1)
        self.assertEqual(parallel, sequential)
        self.assertEqual(summarize_pc_melee_simulation(parallel),
            summarize_pc_melee_simulation(sequential))
        for record, journal in zip(parallel.records, journals, strict=True):
            self.assertEqual(record.source_scenario, request.scenario)
            self.assertEqual(record.executed_actions, journal.executed_actions)
            self.assertEqual(record.source_scenario.npc_net_policies,
                request.scenario.npc_net_policies)
            enemy = record.source_scenario.enemy(ACTOR)
            self.assertEqual(tuple(attack.skill for attack in enemy.definition.attacks),
                (Skill.MELEE, Skill.THROWING))
            self.assertIsNone(enemy.definition.attacks[1].damage)
            self.assertIs(type(enemy.definition.attacks[1].condition_impact), ConditionImpactSpec)
            self.assertTrue(enemy.definition.resilience.is_armoured)
            self.assertFalse(hasattr(record, 'steps'))
            self.assertFalse(hasattr(record, 'net_throw_count'))


if __name__ == '__main__':
    unittest.main()
