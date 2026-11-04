"""Party losses are observations over all trials, including stopped trials."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
from tests.unit.test_m9_pc_melee_balance import request as balance_request
from towr.application.pc_melee_balance_models import project_pc_melee_candidate
from towr.balance.pc_melee_assessment import PcMeleeCandidateAssessment
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.pc_melee_result_models import PcMeleeOutcome as Outcome
from towr.simulation.pc_melee_models import (
    PcMeleeSimulationRequest, PcMeleeSimulationResult, PcMeleeTrialRecord, PcNearMissBurnCount, PcGloriousSpendCount,
)
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
from towr.simulation.pc_melee_summary_models import PcMeleeDefeatCount


def observed_batch():
    source = PcMeleeSimulationRequest(make_pc_melee_party_scenario(max_rounds=1),42,4)
    observations = (
        (Outcome.OBJECTIVE_ACHIEVED,('pc1',)),
        (Outcome.PARTY_DEFEATED,('pc1','pc2')),
        (Outcome.ROUND_LIMIT,('pc2',)),
        (Outcome.UNSUPPORTED_PATH,('pc1',)),
    )
    return PcMeleeSimulationResult(source,tuple(PcMeleeTrialRecord(source.scenario,index,
        source.seed_for(index),outcome,4,1,int(outcome is Outcome.ROUND_LIMIT),deaths,
        tuple(PcNearMissBurnCount(member.actor_id,0) for member in source.scenario.party),
        tuple(PcGloriousSpendCount(member.actor_id,0) for member in source.scenario.party))
        for index,(outcome,deaths) in enumerate(observations)))


class PcPartyStatisticsTests(unittest.TestCase):
    def test_confirmed_deaths_in_wins_limits_and_stops_keep_full_denominator(self):
        result = observed_batch()
        summary = summarize_pc_melee_simulation(result)
        self.assertEqual(summary.any_pc_defeated_count,4)
        self.assertEqual(summary.pc_defeat_counts,
            (PcMeleeDefeatCount('pc1',3),PcMeleeDefeatCount('pc2',2)))
        window = ObjectiveRateWindow(Fraction(0),Fraction(1,2),Fraction(1))
        assessment = PcMeleeCandidateAssessment(result.source_request,summary,window)
        self.assertEqual(assessment.party_defeated_rate,Fraction(1,4))
        self.assertEqual(assessment.objective_achieved_rate,Fraction(1,4))
        self.assertEqual(assessment.unsupported_path_rate,Fraction(1,4))
        self.assertIsNone(assessment.window_match)
        self.assertFalse(hasattr(summary,'records'))

    def test_loss_ids_cannot_repeat_change_source_order_or_claim_a_false_total_defeat(self):
        original = observed_batch().records[0]
        for ids in (('unknown',),('pc1','pc1'),('pc2','pc1'),('pc1','pc2')):
            with self.subTest(ids=ids),self.assertRaises(ValueError):
                replace(original,defeated_pc_ids=ids)
        with self.assertRaises(TypeError):
            replace(original,defeated_pc_ids=['pc1'])
        with self.assertRaises(ValueError):
            replace(original,outcome=Outcome.PARTY_DEFEATED)
        with self.assertRaises(ValueError):
            replace(original,executed_actions=0)

    def test_summary_rejects_filtered_reordered_foreign_and_impossible_loss_counts(self):
        summary = summarize_pc_melee_simulation(observed_batch())
        invalid = (
            {'any_pc_defeated_count':0},
            {'any_pc_defeated_count':5},
            {'any_pc_defeated_count':3},
            {'pc_defeat_counts':tuple(reversed(summary.pc_defeat_counts))},
            {'pc_defeat_counts':summary.pc_defeat_counts[:-1]},
            {'pc_defeat_counts':(PcMeleeDefeatCount('foreign',3),PcMeleeDefeatCount('pc2',2))},
            {'pc_defeat_counts':(PcMeleeDefeatCount('pc1',0),PcMeleeDefeatCount('pc2',2))},
            {'pc_defeat_counts':(PcMeleeDefeatCount('pc1',4),PcMeleeDefeatCount('pc2',4))},
        )
        for change in invalid:
            with self.subTest(change=change),self.assertRaises(ValueError):
                replace(summary,**change)
        forged = deepcopy(summary)
        object.__setattr__(forged.pc_defeat_counts[0],'count',True)
        with self.assertRaises(TypeError):
            replace(forged)

    def test_count_search_preserves_each_pc_profile_fate_and_independent_priorities(self):
        original = make_pc_melee_party_scenario(enemy_count=3)
        member = original.party[1]
        priority = tuple(reversed(member.target_priority))
        original = replace(original,
            party=(original.party[0],replace(member,target_priority=priority,
                defeat_decisions=tuple(member.defeat_decision(target) for target in priority))),
            pc_activation_order=('pc2','pc1'),enemy_target_priority=('pc2','pc1'))
        source = balance_request(template=original,trials=1)
        before = deepcopy(source)
        projected = project_pc_melee_candidate(source,(2,)).scenario
        self.assertEqual(source,before)
        self.assertEqual(projected.pc_activation_order,('pc2','pc1'))
        self.assertEqual(projected.enemy_target_priority,('pc2','pc1'))
        self.assertEqual(projected.party[0].target_priority,('minion1','minion2'))
        self.assertEqual(projected.party[1].target_priority,('minion2','minion1'))
        for actual,expected in zip(projected.party,original.party):
            self.assertIs(actual.pc,expected.pc)
            self.assertIs(actual.fate,expected.fate)
            self.assertEqual(tuple(decision.target_id for decision in actual.defeat_decisions),actual.target_priority)
            self.assertTrue(all(decision.attacker_id == actual.actor_id for decision in actual.defeat_decisions))


if __name__ == '__main__':
    unittest.main()
