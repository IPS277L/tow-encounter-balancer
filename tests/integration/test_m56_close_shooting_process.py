"""One actual spawn representative preserves source-bound NPC opposition."""
from dataclasses import replace
import json
from random import Random
import unittest

from tests.unit.test_m9_pc_melee_json import document
from tests.unit.test_m54_pistol_execution import incoming, shots, steps
from tests.unit.test_m56_close_shooting_execution import close_shooting_scene
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.domain.pc_ranged_models import PcRangedReloadProof
from towr.domain.protection_models import CLOSE_RANGED_MELEE_RULE_ID
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def process_request():
    scenario = close_shooting_scene(rounds=8)
    # Explicit authored PC Defence: six successes always beat the book Knight's
    # four Attack dice, keeping the transport test focused on real shot/reload cycles.
    scenario = replace(scenario,party=tuple(replace(member,
        pc=replace(member.pc,weapon_skill=6,defence=10)) for member in scenario.party))
    raw = document()
    raw['scenario'] = scenario_document(scenario)
    raw['simulation'].update(master_seed='42',trials=4)
    return parse_pc_melee_simulation_request(json.dumps(raw)).request


class CloseShootingProcessTests(unittest.TestCase):
    def test_actual_selected_protection_and_reload_cycles_match_indexed_spawn(self):
        request = process_request()
        journals = tuple(run_pc_melee_scenario(request.scenario,
            Random(request.seed_for(index))) for index in range(request.trials))
        self.assertTrue(all(steps(journal,PcRangedReloadProof) for journal in journals))
        self.assertTrue(any(len(shots(journal))>=2 for journal in journals))
        for journal in journals:
            for shot in shots(journal):
                self.assertIs(shot.proof.protection.source_request.selected_skill,Skill.MELEE)
                self.assertIn(CLOSE_RANGED_MELEE_RULE_ID,shot.proof.protection.applied_rule_ids)
            self.assertTrue(all(step.proof.protection.source_request.selected_skill is Skill.DEFENCE
                for step in incoming(journal)))
        sequential = run_pc_melee_simulation(request)
        parallel = run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(parallel,sequential)
        self.assertEqual(summarize_pc_melee_simulation(parallel),summarize_pc_melee_simulation(sequential))
        for record,journal in zip(parallel.records,journals,strict=True):
            self.assertEqual(record.source_scenario,request.scenario)
            self.assertEqual(record.source_scenario.npc_close_shooting_protection_policies,
                request.scenario.npc_close_shooting_protection_policies)
            self.assertEqual(record.executed_actions,journal.executed_actions)
            self.assertFalse(hasattr(record,'steps'))


if __name__ == '__main__':
    unittest.main()
