"""GM168 Undead Minion effects; the GM135 mount source is admitted natively."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pickle import dumps, loads
import unittest
from unittest.mock import Mock

from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_k1_minion_stagger_defeat import request as ordinary_request
from towr.domain.attack_models import ProneBeforeGiveGroundSpec
from towr.domain.condition_models import (
    Condition, ConditionApplicationRequest, ConditionState, EffectApplicationRequest,
    EffectClassification, StaggerChoice, StaggerOutcome,
)
from towr.domain.injury_models import (
    CharacterInjuryState, MinionStaggerDefeatCause, MinionStaggerDefeatOutcome,
    MinionStaggerDefeatSpec, ProfileInjuryState,
)
from towr.domain.resolution_models import StaggerImpactRequest, TargetInjuryPolicy
from towr.domain.undead_minion_models import (
    UNDEAD_MINION_RULE_ID, UndeadMinionSource, undead_minion_effect_immunities,
    undead_minion_forbidden_stagger_choices, undead_minion_stagger_defeat_spec,
    validate_undead_minion_source,
)
from towr.rules.condition_effect_resolution import resolve_condition_application
from towr.rules.effect_resolution import resolve_effect_application
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.stagger_impact_resolution import resolve_stagger_impact


def kernel(*, staggered=True, base=3):
    ordinary = ordinary_request(staggered=staggered, base=base)
    source = UndeadMinionSource(ordinary.target_id)
    return replace(ordinary,
        minion_stagger_defeat=undead_minion_stagger_defeat_spec(source, ordinary.target_id),
        target_effect_immunities=undead_minion_effect_immunities(source, ordinary.target_id))


def no_choice():
    decisions = Mock()
    decisions.choose_repeated_stagger.side_effect = AssertionError('Undead Minion cannot choose a repeated-Stagger reaction')
    return decisions


class UndeadMinionEffectTests(unittest.TestCase):
    def test_explicit_source_is_immutable_typed_and_actor_bound_without_name_inference(self):
        source = UndeadMinionSource('actual:horse')
        self.assertEqual(loads(dumps(source)), source)
        self.assertTrue(validate_undead_minion_source(source, 'actual:horse'))
        self.assertFalse(validate_undead_minion_source(None, 'Skeletal Steed'))
        self.assertEqual(undead_minion_effect_immunities(None, 'Skeletal Steed'), ())
        self.assertIsNone(undead_minion_stagger_defeat_spec(None, 'Skeletal Steed'))
        self.assertEqual(undead_minion_forbidden_stagger_choices(None, 'Skeletal Steed'), ())
        with self.assertRaises(FrozenInstanceError):
            source.actor_id = 'rider'
        for value in (True, 1, ''):
            with self.subTest(actor=value), self.assertRaises(TypeError):
                UndeadMinionSource(value)
        for value in (True, 'BOOK-GM-GUIDE:1.1:p135:horse'):
            with self.subTest(rule=value), self.assertRaises((TypeError, ValueError)):
                UndeadMinionSource('horse', value)
        with self.assertRaises(ValueError):
            undead_minion_effect_immunities(source, 'its-rider')
        with self.assertRaises(TypeError):
            undead_minion_stagger_defeat_spec(True, 'horse')
        cached = deepcopy(source)
        object.__setattr__(cached, 'rule_id', 'not-the-undead-source')
        with self.assertRaises(ValueError):
            undead_minion_forbidden_stagger_choices(cached, 'actual:horse')

    def test_psychological_effect_and_condition_immunity_keep_actual_rule_provenance(self):
        source = UndeadMinionSource('steed')
        immunities = undead_minion_effect_immunities(source, 'steed')
        self.assertEqual(len(immunities), 1)
        self.assertIs(immunities[0].classification, EffectClassification.PSYCHOLOGICAL)
        effect = resolve_effect_application(EffectApplicationRequest('effect', 'actual:fear',
            EffectClassification.PSYCHOLOGICAL, immunities))
        self.assertTrue(effect.blocked)
        self.assertEqual(effect.blocked_by_rule_id, UNDEAD_MINION_RULE_ID)
        condition = resolve_condition_application(ConditionApplicationRequest('broken', ConditionState(),
            Condition.BROKEN, 'actual:fear', EffectClassification.PSYCHOLOGICAL, immunities))
        self.assertTrue(condition.blocked)
        self.assertFalse(condition.state.has(Condition.BROKEN))
        self.assertEqual(condition.blocked_by_rule_id, UNDEAD_MINION_RULE_ID)

    def test_immunity_does_not_block_forced_physical_prone_or_unclassified_effects(self):
        source = UndeadMinionSource('steed')
        immunities = undead_minion_effect_immunities(source, 'steed')
        for condition in (Condition.PRONE, Condition.ABLAZE, Condition.DRAINED):
            actual = resolve_condition_application(ConditionApplicationRequest('physical', ConditionState(),
                condition, 'actual:physical-effect', EffectClassification.UNCLASSIFIED, immunities))
            with self.subTest(condition=condition):
                self.assertFalse(actual.blocked)
                self.assertTrue(actual.state.has(condition))
        self.assertEqual(undead_minion_forbidden_stagger_choices(source, 'steed'),
            (StaggerChoice.GIVE_GROUND, StaggerChoice.FALL_PRONE))

    def test_second_stagger_destroys_without_choice_wound_or_extra_dice(self):
        original = kernel()
        decisions = no_choice()
        rng = ScriptedD10([1, 10])
        result = resolve_kernel_attack(original, rng, decisions=decisions)
        rng.assert_exhausted()
        decisions.choose_repeated_stagger.assert_not_called()
        cause = result.minion_stagger_defeat.cause
        self.assertIs(cause.outcome, MinionStaggerDefeatOutcome.DESTROYED)
        self.assertEqual((cause.source_id, cause.target_id, cause.rule_id),
            ('kernel:minion-stagger-defeat', original.target_id, UNDEAD_MINION_RULE_ID))
        self.assertEqual((result.target_state.wounds, result.target_state.wound_limit,
            result.target_state.defeated), (0, 1, True))
        self.assertEqual(result.target_state.conditions, original.target_state.conditions)
        self.assertEqual(result.target_state.defeat_cause, cause)
        self.assertEqual(result.follow_ups, (cause,))
        self.assertEqual(result.applied_secondary_rule_ids, (UNDEAD_MINION_RULE_ID,))
        self.assertIsNone(result.stagger)
        self.assertIsNone(result.profile_wound)
        self.assertIsNone(result.character_wound)
        self.assertIsNone(result.pending_character_wound)

    def test_first_stagger_and_miss_do_not_destroy_or_fabricate_choices(self):
        decisions = no_choice()
        first_rng = ScriptedD10([1, 10])
        first = resolve_kernel_attack(kernel(staggered=False), first_rng, decisions=decisions)
        first_rng.assert_exhausted()
        self.assertIs(first.stagger.outcome, StaggerOutcome.CONDITION_ADDED)
        self.assertTrue(first.target_state.conditions.has(Condition.STAGGERED))
        self.assertFalse(first.target_state.defeated)
        self.assertIsNone(first.minion_stagger_defeat)
        self.assertIsNone(first.profile_wound)
        miss_rng = ScriptedD10([10, 1])
        original = kernel()
        miss = resolve_kernel_attack(original, miss_rng, decisions=decisions)
        miss_rng.assert_exhausted()
        self.assertEqual(miss.target_state, original.target_state)
        self.assertIsNone(miss.minion_stagger_defeat)
        decisions.choose_repeated_stagger.assert_not_called()

    def test_real_forced_prone_precedes_destruction_and_is_not_voluntary_fall_prone(self):
        original = kernel()
        forced = ProneBeforeGiveGroundSpec('actual:knockdown')
        original = replace(original, attack=replace(original.attack, secondary_effects=(forced,)))
        rng = ScriptedD10([1, 10])
        result = resolve_kernel_attack(original, rng, decisions=no_choice())
        rng.assert_exhausted()
        self.assertTrue(result.target_state.conditions.has(Condition.PRONE))
        self.assertTrue(result.target_state.conditions.has(Condition.STAGGERED))
        self.assertIs(result.target_state.defeat_cause.outcome, MinionStaggerDefeatOutcome.DESTROYED)
        self.assertEqual(result.target_state.wounds, 0)
        self.assertIn('actual:knockdown', result.applied_secondary_rule_ids)

    def test_direct_wound_and_defenceless_forced_wound_keep_real_profile_wound(self):
        for original in (kernel(base=6), replace(kernel(), target_state=replace(kernel().target_state,
                conditions=ConditionState({Condition.STAGGERED, Condition.DEFENCELESS})))):
            with self.subTest(original=original):
                rng = ScriptedD10([1, 10])
                result = resolve_kernel_attack(original, rng, decisions=no_choice())
                rng.assert_exhausted()
                self.assertEqual((result.target_state.wounds, result.target_state.defeated), (1, True))
                self.assertIsNone(result.target_state.defeat_cause)
                self.assertIsNone(result.minion_stagger_defeat)
                self.assertEqual(result.profile_wound.wounds_inflicted, 1)

    def test_dirty_coward_keeps_fleeing_and_cannot_be_confused_with_destruction(self):
        rng = ScriptedD10([1, 10])
        result = resolve_kernel_attack(ordinary_request(), rng)
        rng.assert_exhausted()
        self.assertIs(result.target_state.defeat_cause.outcome, MinionStaggerDefeatOutcome.FLED)
        self.assertIs(ordinary_request().minion_stagger_defeat.outcome, MinionStaggerDefeatOutcome.FLED)
        destroyed = undead_minion_stagger_defeat_spec(UndeadMinionSource('target'), 'target')
        self.assertNotEqual(destroyed,
            MinionStaggerDefeatSpec(destroyed.rule_id))

    def test_spec_cause_and_profile_require_typed_distinct_outcomes_and_actual_minion(self):
        for value in (True, 'destroyed', 'killed'):
            with self.subTest(outcome=value), self.assertRaises(TypeError):
                MinionStaggerDefeatSpec(UNDEAD_MINION_RULE_ID, outcome=value)
            with self.subTest(cause=value), self.assertRaises(TypeError):
                MinionStaggerDefeatCause('actual:source', 'target', UNDEAD_MINION_RULE_ID, outcome=value)
        original = kernel()
        for policy, state in ((TargetInjuryPolicy.PLAYER, CharacterInjuryState()),
                (TargetInjuryPolicy.BRUTE, ProfileInjuryState(0, 2)),
                (TargetInjuryPolicy.MINION, ProfileInjuryState(1, 1, defeated=True))):
            with self.subTest(policy=policy), self.assertRaises((TypeError, ValueError)):
                replace(original, target_policy=policy, target_state=state)
        cause = MinionStaggerDefeatCause('actual:source', 'target', UNDEAD_MINION_RULE_ID,
            outcome=MinionStaggerDefeatOutcome.DESTROYED)
        with self.assertRaises(ValueError):
            ProfileInjuryState(0, 1, defeated=True, defeat_cause=cause)
        with self.assertRaises(ValueError):
            ProfileInjuryState(1, 1, ConditionState({Condition.STAGGERED}), True, cause)

    def test_cached_outcome_receipt_and_dead_source_reject_before_rng(self):
        original = deepcopy(kernel())
        object.__setattr__(original.minion_stagger_defeat, 'outcome', 'destroyed')
        with self.assertRaises(TypeError):
            resolve_kernel_attack(original, ScriptedD10([]))
        original = kernel()
        direct = StaggerImpactRequest('direct', original.target_id, original.target_policy,
            original.target_state, True, False, minion_stagger_defeat=original.minion_stagger_defeat)
        result = resolve_stagger_impact(direct, ScriptedD10([]), decisions=no_choice())
        receipt = result.minion_stagger_defeat
        for changes in (dict(applied_rule_ids=()), dict(applied_rule_ids=(UNDEAD_MINION_RULE_ID,)*2),
                dict(cause=replace(receipt.cause, outcome=MinionStaggerDefeatOutcome.FLED)),
                dict(cause=replace(receipt.cause, target_id='foreign'))):
            # A different target cause requires a different full state witness too;
            # source/result comparisons must never infer it from just a Rule ID.
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(receipt, **changes)
        with self.assertRaises(ValueError):
            replace(direct, target_state=result.state)
        for policy in (TargetInjuryPolicy.BRUTE, 'minion'):
            with self.subTest(policy=policy), self.assertRaises((TypeError, ValueError)):
                replace(direct, target_state=result.state, target_policy=policy, minion_stagger_defeat=None)


if __name__ == '__main__':
    unittest.main()
