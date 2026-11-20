"""PG1.4 III73/V109/119: actual opposed Attack ties and source admission."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from towr.domain.attack_models import (
    AttackOutcome, AttackRequest, ConditionImpactSpec, DamageImpactSpec,
    DamageProfile, HazardImpactSpec, MissConsequence, ResilienceProfile,
)
from towr.domain.brawn_impact_models import (
    BrawnAttackEffect, BrawnDisplacementImpactSpec,
)
from towr.domain.condition_models import Condition
from towr.domain.talent_tie_models import compose_talent_tie_break
from towr.domain.test_models import (
    InlineProfile, OpposedSide, QualityModifier, Skill, TestProfile,
    TestQuality, TestRequest, TieBreak,
)
from towr.rules.attack_resolution import (
    ATTACK_TIE_RULE_ID, _resolve_attack_after_tests, resolve_attack,
)
from towr.rules.test_resolution import RerollAllFailures


class CountingRandom(SequenceRandom):
    def __init__(self, values):
        super().__init__(values)
        self.calls = []

    def randint(self, start, end):
        self.calls.append((start, end))
        return super().randint(start, end)


def ordinary():
    return TieBreak(ATTACK_TIE_RULE_ID, OpposedSide.INITIATOR)


def preferred(winner=OpposedSide.OPPONENT):
    return compose_talent_tie_break(ordinary(),
        (TieBreak('source:actual-inspiration', winner),))


def attack_request(*, source=None, opposed=True, close=True,
        staggered=False, immunity=None, impact=None, profile=None):
    profile = profile or TestProfile(2, 5)
    return AttackRequest('attack', TestRequest('attacker', profile),
        TestRequest('defender', profile) if opposed else None,
        impact if impact is not None else DamageImpactSpec(
            DamageProfile(4), ResilienceProfile(4, 1)),
        close, staggered, immunity, tie_break=source)


def impact_sources():
    return (
        DamageImpactSpec(DamageProfile(4), ResilienceProfile(4, 1)),
        ConditionImpactSpec(Condition.STAGGERED, 'impact:unarmed'),
        HazardImpactSpec(3, Skill.ENDURANCE, 'impact:hazard'),
        BrawnDisplacementImpactSpec(BrawnAttackEffect.SHOVE, 'attacker'),
    )


class AttackTalentTieResolutionTests(unittest.TestCase):
    def test_ordinary_tie_keeps_existing_damage_and_rule_tuple(self):
        result = resolve_attack(attack_request(), SequenceRandom([1, 10, 2, 10]))
        self.assertIs(result.outcome, AttackOutcome.HIT)
        self.assertEqual((result.success_margin, result.damage,
            result.effective_resilience), (0, 4, 5))
        self.assertTrue(result.tie_break_applied)
        self.assertEqual(result.applied_rule_ids, (ATTACK_TIE_RULE_ID,))

    def test_defender_positive_tie_prevents_each_impact_and_traces_actual_source(self):
        source = preferred()
        for profile in (TestProfile(2, 5), InlineProfile(2, 5)):
            for impact in impact_sources():
                with self.subTest(profile=profile, impact=impact):
                    request = attack_request(source=source, profile=profile, impact=impact)
                    rng = CountingRandom([1, 10, 2, 10])
                    result = resolve_attack(request, rng)
                    self.assertIs(result.outcome, AttackOutcome.MISS)
                    self.assertEqual(result.success_margin, 0)
                    self.assertIs(result.impact_spec, impact)
                    self.assertEqual((result.damage, result.effective_resilience,
                        result.impact), (None, None, None))
                    self.assertIs(result.miss_consequence, MissConsequence.STAGGER_ATTACKER)
                    self.assertTrue(result.tie_break_applied)
                    self.assertEqual(result.applied_rule_ids, (source.rule_id,))
                    self.assertEqual(rng.calls, [(1, 10)] * 4)

    def test_attacker_positive_tie_traces_selected_source_for_each_impact(self):
        source = preferred(OpposedSide.INITIATOR)
        for impact in impact_sources():
            with self.subTest(impact=impact):
                result = resolve_attack(attack_request(source=source, impact=impact),
                    SequenceRandom([1, 10, 2, 10]))
                self.assertIs(result.outcome, AttackOutcome.HIT)
                self.assertTrue(result.tie_break_applied)
                self.assertEqual(result.success_margin, 0)
                rules = (() if type(impact) is DamageImpactSpec else (impact.rule_id,))
                self.assertEqual(result.applied_rule_ids, (*rules, source.rule_id))

    def test_opposing_preferences_cancel_to_actual_ordinary_attack_source(self):
        original = ordinary()
        preferences = (TieBreak('source:first', OpposedSide.OPPONENT),
            TieBreak('source:second', OpposedSide.INITIATOR))
        expected = resolve_attack(attack_request(), SequenceRandom([1, 10, 2, 10]))
        for values in (preferences, tuple(reversed(preferences)),
                (*preferences, TieBreak('source:third', OpposedSide.OPPONENT))):
            with self.subTest(preferences=values):
                source = compose_talent_tie_break(original, values)
                self.assertIs(source, original)
                result = resolve_attack(attack_request(source=source),
                    SequenceRandom([1, 10, 2, 10]))
                self.assertEqual(result, expected)

    def test_double_zero_preserves_two_failures_and_never_applies_tie_source(self):
        for side in OpposedSide:
            with self.subTest(side=side):
                result = resolve_attack(attack_request(source=preferred(side)),
                    SequenceRandom([10, 10, 10, 10]))
                baseline = resolve_attack(attack_request(),
                    SequenceRandom([10, 10, 10, 10]))
                self.assertEqual(result, baseline)
                self.assertIs(result.outcome, AttackOutcome.MISS)
                self.assertFalse(result.tie_break_applied)
                self.assertEqual(result.applied_rule_ids, ())

    def test_unopposed_attack_receives_no_tie_benefit(self):
        for values in ([1, 10], [10, 10]):
            with self.subTest(values=values):
                request = attack_request(source=preferred(), opposed=False)
                rng = CountingRandom(values)
                result = resolve_attack(request, rng)
                baseline = resolve_attack(attack_request(opposed=False), SequenceRandom(values))
                self.assertEqual(result, baseline)
                self.assertFalse(result.tie_break_applied)
                self.assertEqual(result.applied_rule_ids, ())
                self.assertEqual(rng.calls, [(1, 10)] * 2)

    def test_unequal_results_keep_outcome_margin_damage_and_rule_trace(self):
        for values in ([1, 2, 1, 10], [1, 10, 1, 2], [10, 10, 1, 10]):
            with self.subTest(values=values):
                result = resolve_attack(attack_request(source=preferred()), SequenceRandom(values))
                baseline = resolve_attack(attack_request(), SequenceRandom(values))
                self.assertEqual(result, baseline)
                self.assertFalse(result.tie_break_applied)

    def test_defender_tie_keeps_close_miss_immunity_and_stagger_policy(self):
        source = preferred()
        for changes, consequence, rules in (
                ({}, MissConsequence.STAGGER_ATTACKER, ()),
                ({'staggered': True}, MissConsequence.NONE, ()),
                ({'close': False}, MissConsequence.NONE, ()),
                ({'immunity': 'source:miss-immunity'}, MissConsequence.NONE,
                    ('source:miss-immunity',))):
            with self.subTest(changes=changes):
                result = resolve_attack(attack_request(source=source, **changes),
                    SequenceRandom([1, 10, 2, 10]))
                self.assertIs(result.miss_consequence, consequence)
                self.assertEqual(result.applied_rule_ids, (*rules, source.rule_id))

    def test_completion_keeps_literal_tests_and_never_rerolls_defender_tie(self):
        request = attack_request(source=preferred())
        resolved = resolve_attack(request, SequenceRandom([1, 10, 2, 10]))
        with patch('towr.rules.attack_resolution.resolve_test',
                side_effect=AssertionError('completed Test was rolled again')):
            completed = _resolve_attack_after_tests(request,
                resolved.attacker_test, resolved.defender_test)
        self.assertEqual(completed, resolved)
        self.assertIs(completed.attacker_test, resolved.attacker_test)
        self.assertIs(completed.defender_test, resolved.defender_test)

    def test_tie_uses_final_successes_after_attacker_rerolls(self):
        request = attack_request(source=preferred())
        request = replace(request, attacker_test=replace(request.attacker_test,
            quality_modifiers=(QualityModifier('source:glorious', TestQuality.GLORIOUS),)))
        rng = CountingRandom([1, 10, 2, 3, 4])
        result = resolve_attack(request, rng, decisions=RerollAllFailures())
        self.assertEqual(result.attacker_test.trace.initial_values, (1, 10))
        self.assertEqual(result.attacker_test.trace.final_values, (1, 2))
        self.assertEqual(result.defender_test.trace.initial_values, (3, 4))
        self.assertIs(result.outcome, AttackOutcome.MISS)
        self.assertTrue(result.tie_break_applied)
        self.assertEqual(result.applied_rule_ids, (request.tie_break.rule_id,))
        self.assertEqual(rng.calls, [(1, 10)] * 5)


class AttackTalentTieAdmissionTests(unittest.TestCase):
    def test_request_requires_exact_typed_tie_and_source_fields(self):
        class AliasTie(TieBreak):
            pass

        class AliasString(str):
            pass

        for source in (False, True, 'opponent', object(),
                AliasTie('source:alias', OpposedSide.OPPONENT),
                TieBreak(AliasString('source:alias'), OpposedSide.OPPONENT)):
            with self.subTest(source=source), self.assertRaises(TypeError):
                attack_request(source=source)
        with self.assertRaises(ValueError):
            attack_request(source=TieBreak(' source:spaced ', OpposedSide.OPPONENT))

    def test_constructor_readmits_cached_tie_break_before_accepting_request(self):
        for field, value, error in (
                ('rule_id', True, TypeError), ('rule_id', '', ValueError),
                ('rule_id', ' source:spaced ', ValueError),
                ('winner', 'opponent', TypeError), ('winner', True, TypeError)):
            source = preferred()
            object.__setattr__(source, field, value)
            with self.subTest(field=field, value=value), self.assertRaises(error):
                attack_request(source=source)

    def test_resolver_and_completion_reject_cached_mutation_before_use(self):
        completed = resolve_attack(attack_request(), SequenceRandom([1, 10, 2, 10]))
        for opposed in (False, True):
            for field, value, error in (
                    ('rule_id', False, TypeError), ('rule_id', '', ValueError),
                    ('rule_id', ' source:spaced ', ValueError),
                    ('winner', 'opponent', TypeError), ('winner', True, TypeError)):
                request = attack_request(source=preferred(), opposed=opposed)
                object.__setattr__(request.tie_break, field, value)
                rng = CountingRandom([1, 10, 2, 10])
                with self.subTest(opposed=opposed, field=field, value=value):
                    with self.assertRaises(error):
                        resolve_attack(request, rng)
                    self.assertEqual(rng.calls, [])
                    with self.assertRaises(error):
                        _resolve_attack_after_tests(request, completed.attacker_test,
                            completed.defender_test if opposed else None)

    def test_cached_request_cannot_replace_tie_source_with_untyped_value(self):
        completed = resolve_attack(attack_request(), SequenceRandom([1, 10, 2, 10]))
        for value in (False, True, 'opponent', object()):
            request = attack_request(source=preferred())
            object.__setattr__(request, 'tie_break', value)
            rng = CountingRandom([1, 10, 2, 10])
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    resolve_attack(request, rng)
                self.assertEqual(rng.calls, [])
                with self.assertRaises(TypeError):
                    _resolve_attack_after_tests(request,
                        completed.attacker_test, completed.defender_test)


if __name__ == '__main__':
    unittest.main()
