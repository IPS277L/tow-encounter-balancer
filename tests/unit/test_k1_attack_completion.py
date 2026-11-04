"""Complete prepared attack Tests once, retaining their literal traces."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_attack_resolution import attack_request
from towr.domain.attack_models import (
    AttackOutcome, ConditionImpactSpec, DamageModifier, DamageProfile,
    HazardImpactSpec, ImpactOutcome, MissConsequence, ResilienceModifier,
)
from towr.domain.condition_models import Condition
from towr.domain.test_models import QualityModifier, Skill, TestQuality
from towr.rules.attack_resolution import _resolve_attack_after_tests, resolve_attack
from towr.rules.test_resolution import RerollAllFailures, resolve_test


class AttackCompletionTests(unittest.TestCase):
    def test_completed_results_preserve_literal_hit_tie_miss_and_unopposed_outcomes(self):
        cases = (
            (attack_request(),[1,10,10,2,10],AttackOutcome.HIT,0,ImpactOutcome.STAGGERED),
            (attack_request(),[1,2,3,1,10],AttackOutcome.HIT,2,ImpactOutcome.WOUND),
            (attack_request(),[10,10,10,10,10],AttackOutcome.MISS,0,None),
            (attack_request(),[1,10,10,1,2],AttackOutcome.MISS,0,None),
            (attack_request(defender=False),[1,2,10],AttackOutcome.HIT,2,ImpactOutcome.WOUND),
            (attack_request(defender=False),[10,10,10],AttackOutcome.MISS,0,None),
        )
        for request,values,outcome,margin,impact in cases:
            with self.subTest(values=values,defender=request.defender_test is not None):
                resolved = resolve_attack(request,SequenceRandom(values))
                with patch('towr.rules.attack_resolution.resolve_test',side_effect=AssertionError('Test replay')):
                    completed = _resolve_attack_after_tests(request,resolved.attacker_test,resolved.defender_test)
                self.assertEqual(completed,resolved)
                self.assertIs(completed.attacker_test,resolved.attacker_test)
                self.assertIs(completed.defender_test,resolved.defender_test)
                self.assertEqual((completed.outcome,completed.success_margin,completed.impact),(outcome,margin,impact))

    def test_existing_rng_order_finishes_attacker_rerolls_before_defender_pool(self):
        request = attack_request()
        request = replace(request,
            attacker_test=replace(request.attacker_test,quality_modifiers=(
                QualityModifier('authored:glorious',TestQuality.GLORIOUS),)),
            defender_test=replace(request.defender_test,quality_modifiers=(
                QualityModifier('authored:grim',TestQuality.GRIM),)))
        result = resolve_attack(request,SequenceRandom([1,10,10,2,3,4,10,9]),
            decisions=RerollAllFailures())
        self.assertEqual(result.attacker_test.trace.initial_values,(1,10,10))
        self.assertEqual(result.attacker_test.trace.final_values,(1,2,3))
        self.assertEqual(result.defender_test.trace.initial_values,(4,10))
        self.assertEqual(result.defender_test.trace.final_values,(9,10))
        self.assertEqual(result.success_margin,3)

    def test_completion_keeps_damage_modifiers_ignored_armour_and_multiplier(self):
        request = attack_request(damage=DamageProfile(3,2),ignores_armour=True,
            damage_modifiers=(DamageModifier('authored:damage',1),),
            resilience_modifiers=(ResilienceModifier('authored:resilience',-1),))
        original = resolve_attack(request,SequenceRandom([1,2,3,1,10]))
        result = _resolve_attack_after_tests(request,original.attacker_test,original.defender_test)
        self.assertEqual((result.damage,result.effective_resilience),(8,3))
        self.assertEqual(result.applied_rule_ids,('authored:damage','authored:resilience'))

    def test_non_damage_impacts_keep_their_own_rule_and_positive_tie(self):
        for spec in (ConditionImpactSpec(Condition.BURDENED,'authored:condition'),
            HazardImpactSpec(3,Skill.ENDURANCE,'authored:hazard')):
            with self.subTest(spec=spec):
                request = attack_request(impact_spec=spec)
                original = resolve_attack(request,SequenceRandom([1,10,10,2,10]))
                result = _resolve_attack_after_tests(request,original.attacker_test,original.defender_test)
                self.assertIs(result.impact_spec,spec)
                self.assertEqual(result.applied_rule_ids,(spec.rule_id,'RULE-COMBAT-006:attack-tie'))
                self.assertIsNone(result.damage)
                self.assertIsNone(result.impact)

    def test_miss_keeps_close_stagger_and_immunity_policy(self):
        for changes,consequence,rules in (
            ({},MissConsequence.STAGGER_ATTACKER,()),
            ({'attacker_staggered':True},MissConsequence.NONE,()),
            ({'close':False},MissConsequence.NONE,()),
            ({'miss_immunity_rule_id':'authored:immunity'},MissConsequence.NONE,('authored:immunity',))):
            request = attack_request(defender=False,**changes)
            original = resolve_attack(request,SequenceRandom([10,10,10]))
            result = _resolve_attack_after_tests(request,original.attacker_test,None)
            self.assertEqual((result.miss_consequence,result.applied_rule_ids),(consequence,rules))

    def test_missing_foreign_or_extra_test_results_are_rejected(self):
        request = attack_request()
        attacker = resolve_test(request.attacker_test,SequenceRandom([1,10,10]))
        defender = resolve_test(request.defender_test,SequenceRandom([1,10]))
        foreign = replace(attacker,trace=replace(attacker.trace,request_id='foreign'))
        for a,d in ((foreign,defender),(attacker,attacker)):
            with self.assertRaises(ValueError):
                _resolve_attack_after_tests(request,a,d)
        with self.assertRaises(TypeError):
            _resolve_attack_after_tests(request,attacker,None)
        with self.assertRaises(TypeError):
            _resolve_attack_after_tests(request,object(),defender)
        with self.assertRaises(ValueError):
            _resolve_attack_after_tests(replace(request,defender_test=None),attacker,defender)
        for successes in (True,-1):
            bad = replace(attacker,trace=replace(attacker.trace,successes=successes))
            with self.assertRaises((TypeError,ValueError)):
                _resolve_attack_after_tests(request,bad,defender)


if __name__ == '__main__':
    unittest.main()
