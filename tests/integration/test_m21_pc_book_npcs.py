"""Book combat sources survive real trials, Windows spawn and mixed count search."""
from copy import deepcopy
from enum import Enum
from fractions import Fraction
from random import Random
import unittest
from unittest.mock import patch

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from towr.application.pc_melee_balance import evaluate_pc_melee_balance
from towr.application.pc_melee_balance_models import PcMeleeBalanceRequest,PcMeleeCompositionGroup
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


class PcBookNpcIntegrationTests(unittest.TestCase):
    def test_actual_book_trials_match_process_with_complete_source_and_skill(self):
        request=PcMeleeSimulationRequest(book_pc_scenario(),42,3)
        sequential=run_pc_melee_simulation(request)
        process=run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(process,sequential)
        self.assertEqual(summarize_pc_melee_simulation(process),summarize_pc_melee_simulation(sequential))
        for record in sequential.records:
            self.assertEqual(record.source_scenario,request.scenario)
            for enemy in record.source_scenario.enemies:
                validate_pc_book_npc_definition(enemy.definition)
                self.assertIs(enemy.definition.protection[0].skill,Skill.ATHLETICS)

    def test_mixed_count_search_preserves_canonical_book_definitions_without_battle_journals(self):
        source=book_pc_scenario()
        request=PcMeleeBalanceRequest(source,(
            PcMeleeCompositionGroup('footpads',('footpad1','footpad2'),1,2),
            PcMeleeCompositionGroup('townsfolk',('townsfolk1',),0,1)),source.facts,42,2,4,8,
            ObjectiveRateWindow(Fraction(0),Fraction(1,2),Fraction(1)),2)
        result=evaluate_pc_melee_balance(request,
            lambda trial:summarize_pc_melee_simulation(run_pc_melee_simulation(trial)))
        self.assertEqual(result.total_trials,8)
        definitions={enemy.state.actor_id:enemy.definition for enemy in source.enemies}
        for candidate in result.candidates:
            for enemy in candidate.source_request.scenario.enemies:
                self.assertEqual(enemy.definition,definitions[enemy.state.actor_id])
                validate_pc_book_npc_definition(enemy.definition)
            self.assertFalse(hasattr(candidate.summary,'records'))

    def test_equal_cached_skill_alias_cannot_become_a_book_trial_observation(self):
        request=PcMeleeSimulationRequest(book_pc_scenario(),42,1)
        native=run_pc_melee_scenario(request.scenario,Random(request.seed_for(0)))
        forged=deepcopy(native)
        option=forged.source.enemies[0].definition.protection[0]
        object.__setattr__(option,'skill',Enum('OtherSkill',{'ATHLETICS':'athletics'},type=str).ATHLETICS)
        self.assertEqual(forged,native)
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',return_value=forged):
            with self.assertRaises((TypeError,ValueError)):
                run_pc_melee_trial(request,0)


if __name__=='__main__':
    unittest.main()
