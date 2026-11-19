"""Headsman GM83 replaces an actual Wound, without a fictitious table roll."""
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from towr.domain.attack_models import (
    AttackRequest, ConditionImpactSpec, DamageImpactSpec, DamageProfile, ResilienceProfile,
)
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.fate_models import FATE_NEAR_MISS_RULE_ID, FateNearMissBurnRequest, FateSessionState
from towr.domain.infection_models import DailyWoundState
from towr.domain.injury_models import (
    CharacterInjuryState, CharacterWoundRequest, CharacterWoundType,
    FixedWoundSelection, FixedWoundTableSelection, ProfileInjuryState,
    ProfileDecapitationCause, ProfileNpcType, ProfileWoundRequest,
    WoundDiceModifier, WoundEntryId, WoundNegationOption, WoundRecordOrigin,
    WoundTableRoll, validate_character_wound_result_provenance,
)
from towr.domain.resolution_models import (
    ConsumeWoundNegationRequest, KernelAttackRequest, TargetInjuryPolicy,
)
from towr.domain.test_models import InlineProfile, QualityModifier, TestQuality, TestRequest
from towr.domain.weapon_quality_preparation import HEADSMAN_EXECUTION_RULE_ID
from towr.domain.wound_lifecycle_models import (
    CharacterWoundLifecycleRollRequest, CharacterWoundLifecycleCompletionRequest,
    CharacterWoundLifecycleOutcome,
)
from towr.rules.kernel import resolve_kernel_attack, apply_kernel_character_wound_completion
from towr.rules.wound_lifecycle_resolution import (
    roll_character_wound_lifecycle, complete_character_wound_lifecycle,
)
from towr.rules.wound_table import lookup_wound
from towr.rules.injury_resolution import resolve_profile_wound


HEADSMAN = FixedWoundSelection(WoundEntryId.DECAPITATION, 27, HEADSMAN_EXECUTION_RULE_ID)


class NoRandom:
    def randint(self, *_):
        raise AssertionError('fixed Wound cannot consume invented d10')


class Negate:
    def choose_wound_negation(self, **_):
        return 'negate'


def roll_fixed(*, subject=CharacterWoundType.PLAYER, negate=False):
    source = CharacterWoundRequest('wound', CharacterInjuryState(), subject,
        dice_modifiers=(WoundDiceModifier('existing-table-die', 1),),
        negation_options=(WoundNegationOption('negate'),) if negate else (), fixed_entry=HEADSMAN)
    return roll_character_wound_lifecycle(CharacterWoundLifecycleRollRequest('roll', 'hero', source),
        NoRandom(), decisions=Negate() if negate else None)


def complete(roll, *, near_miss=False, consumed=()):
    burn = FateNearMissBurnRequest('burn',
        FateSessionState('session', 'hero', rating=1, session_spend_limit=1),
        ConsumeWoundNegationRequest(roll.source_request.wound.id, FATE_NEAR_MISS_RULE_ID)) if near_miss else None
    return complete_character_wound_lifecycle(CharacterWoundLifecycleCompletionRequest(
        'complete', roll, roll.wound_result.state, DailyWoundState('day', 'hero'),
        None if near_miss or not roll.wound_result.wound_accepted else 'register', burn,
        consumed_roll_ids=consumed))


def kernel(*, damage=5, staggered=False, policy=TargetInjuryPolicy.PLAYER):
    conditions = ConditionState(frozenset({Condition.PRONE, *({Condition.STAGGERED} if staggered else set())}))
    state = CharacterInjuryState(conditions=conditions)
    test = TestRequest('attack:test', InlineProfile(2, 8),
        quality_modifiers=(QualityModifier(HEADSMAN_EXECUTION_RULE_ID, TestQuality.GRIM),))
    attack = AttackRequest('attack', test, None,
        DamageImpactSpec(DamageProfile(damage), ResilienceProfile(2), magical_source=True), True, False)
    return KernelAttackRequest('kernel', 'hero', attack, policy, state, False, False,
        physical_attack=True, fixed_character_wound=HEADSMAN)


class HeadsmanWoundLifecycleTests(unittest.TestCase):
    def test_named_entry_has_no_roll_and_keeps_original_modifier_and_item_sources(self):
        roll = roll_fixed()
        wound = roll.wound_result
        self.assertIs(type(wound.table_roll), FixedWoundTableSelection)
        self.assertEqual(wound.table_roll.source, HEADSMAN)
        self.assertEqual(wound.table_roll.dice, 0)
        self.assertEqual(wound.table_roll.values, ())
        self.assertEqual(wound.table_roll.total, 27)
        self.assertEqual(wound.state.wounds[0].origin, WoundRecordOrigin.FIXED_ENTRY)
        self.assertEqual(wound.state.wounds[0].roll_values, ())
        self.assertTrue(wound.state.dead)
        self.assertTrue(roll.near_miss_eligible)
        self.assertEqual(wound.applied_rule_ids, ('existing-table-die', HEADSMAN_EXECUTION_RULE_ID))
        self.assertEqual(roll.source_request.wound.dice_modifiers,
            (WoundDiceModifier('existing-table-die', 1),))

    def test_acceptance_resolves_decapitation_and_daily_registration_once(self):
        roll = roll_fixed()
        result = complete(roll)
        self.assertIs(result.outcome, CharacterWoundLifecycleOutcome.ACCEPTED)
        self.assertTrue(result.state.dead)
        self.assertTrue(result.state.wounds[0].effect_resolved)
        self.assertEqual(result.wound_effect.request.entry_id, WoundEntryId.DECAPITATION)
        self.assertEqual(result.daily_wounds.wound_count, 1)
        self.assertEqual(result.daily_registration.receipt.wound.origin, WoundRecordOrigin.FIXED_ENTRY)
        self.assertEqual(result.consumed_roll_ids, ('roll',))
        with self.assertRaises(ValueError):
            complete(roll, consumed=result.consumed_roll_ids)

    def test_near_miss_cancels_named_death_without_table_reroll_or_daily_wound(self):
        result = complete(roll_fixed(), near_miss=True)
        self.assertIs(result.outcome, CharacterWoundLifecycleOutcome.NEAR_MISS)
        self.assertEqual(result.state, CharacterInjuryState())
        self.assertFalse(result.state.dead)
        self.assertEqual(result.fate_burn.state.rating, 0)
        self.assertEqual(result.near_miss_application.cancelled_wound.origin, WoundRecordOrigin.FIXED_ENTRY)
        self.assertEqual(result.near_miss_application.cancelled_wound.roll_values, ())
        self.assertEqual(result.daily_wounds.wound_count, 0)
        self.assertIsNone(result.daily_registration)
        self.assertIsNone(result.wound_effect)

    def test_actual_wound_negation_precedes_named_death_and_near_miss(self):
        roll = roll_fixed(negate=True)
        result = complete(roll)
        self.assertFalse(roll.wound_result.wound_accepted)
        self.assertEqual(roll.wound_result.negated_by_rule_id, 'negate')
        self.assertFalse(roll.near_miss_eligible)
        self.assertIs(result.outcome, CharacterWoundLifecycleOutcome.NEGATED)
        self.assertEqual(result.state.wounds, ())
        self.assertFalse(result.state.dead)
        self.assertEqual(result.daily_wounds.wound_count, 0)
        with self.assertRaises(ValueError):
            complete(roll, near_miss=True)

    def test_champion_accepts_same_named_entry_but_never_player_fate(self):
        roll = roll_fixed(subject=CharacterWoundType.CHAMPION)
        self.assertFalse(roll.near_miss_eligible)
        self.assertTrue(complete(roll).state.dead)
        with self.assertRaises(ValueError):
            complete(roll, near_miss=True)

    def test_table_roll_and_fixed_selection_families_cannot_impersonate_each_other(self):
        roll = roll_fixed()
        source = roll.source_request.wound
        wound = roll.wound_result
        fake_roll = WoundTableRoll(3, (9, 9, 9), 27, lookup_wound(27))
        with self.assertRaises(TypeError):
            validate_character_wound_result_provenance(source, replace(wound, table_roll=fake_roll))
        with self.assertRaises(TypeError):
            validate_character_wound_result_provenance(replace(source, fixed_entry=None), wound)
        altered = replace(HEADSMAN, rule_id='other-source')
        with self.assertRaises(ValueError):
            validate_character_wound_result_provenance(replace(source, fixed_entry=altered), wound)
        with self.assertRaises(TypeError):
            replace(HEADSMAN, table_total=True)
        with self.assertRaises(ValueError):
            FixedWoundTableSelection(replace(HEADSMAN, table_total=24), lookup_wound(24))

    def test_real_numeric_kernel_hit_creates_only_fixed_wound_after_four_attack_dice(self):
        source = kernel()
        result = resolve_kernel_attack(source, SequenceRandom([1, 1, 1, 1]))
        self.assertIs(result.character_wound.table_roll.entry.id, WoundEntryId.DECAPITATION)
        self.assertEqual(result.character_wound.table_roll.values, ())
        self.assertEqual(result.pending_character_wound.source_request.wound.fixed_entry, HEADSMAN)
        completion = complete(result.pending_character_wound, near_miss=True)
        after = apply_kernel_character_wound_completion(result, completion)
        self.assertEqual(after.target_state, source.target_state)
        self.assertIsNone(after.pending_character_wound)
        self.assertIs(after.character_wound_completion.outcome, CharacterWoundLifecycleOutcome.NEAR_MISS)

    def test_repeated_stagger_wound_uses_same_fixed_entry_without_hidden_d10(self):
        result = resolve_kernel_attack(kernel(damage=0, staggered=True), SequenceRandom([1, 1, 1, 1]))
        self.assertTrue(result.stagger.wound_requested)
        self.assertEqual(result.character_wound.table_roll.values, ())
        self.assertIs(result.character_wound.table_roll.entry.id, WoundEntryId.DECAPITATION)

    def test_miss_or_first_stagger_is_not_an_executed_wound(self):
        source = kernel(damage=0)
        for values in ([10, 10], [1, 1, 1, 1]):
            with self.subTest(values=values):
                result = resolve_kernel_attack(source, SequenceRandom(values))
                self.assertIsNone(result.character_wound)
                self.assertIsNone(result.pending_character_wound)
                self.assertFalse(result.target_state.dead)
                self.assertEqual(result.target_state.wounds, ())

    def test_kernel_cannot_smuggle_fixed_death_without_actual_execution_source(self):
        source = kernel()
        for change in ({'physical_attack': False},
                {'fixed_character_wound': replace(HEADSMAN, table_total=28)},
                {'fixed_character_wound': replace(HEADSMAN, rule_id='not-headsman')},
                {'target_state': CharacterInjuryState()},
                {'attack': replace(source.attack,
                    attacker_test=replace(source.attack.attacker_test, quality_modifiers=()))},
                {'attack': replace(source.attack,
                    impact_spec=ConditionImpactSpec(Condition.STAGGERED, 'unarmed'))},
                {'target_policy': TargetInjuryPolicy.BRUTE}):
            with self.subTest(change=change), self.assertRaises((TypeError, ValueError)):
                replace(source, **change)

    def test_profile_brute_is_instantly_killed_by_one_actual_wound_not_fake_remaining_wounds(self):
        source = kernel()
        profile = ProfileInjuryState(0, 3, source.target_state.conditions)
        source = replace(source, target_policy=TargetInjuryPolicy.BRUTE, target_state=profile)
        result = resolve_kernel_attack(source, SequenceRandom([1, 1, 1, 1]))
        wound = result.profile_wound
        self.assertEqual(wound.wounds_requested, 1)
        self.assertEqual(wound.wounds_inflicted, 1)
        self.assertEqual(wound.state.wounds, 1)
        self.assertEqual(wound.state.wound_limit, 3)
        self.assertTrue(wound.state.defeated)
        self.assertEqual(wound.state.defeat_cause, ProfileDecapitationCause('kernel:wound', 'hero'))
        self.assertTrue(wound.state_change.defeated)
        self.assertEqual(wound.state_change.current_wounds, 1)
        self.assertEqual(wound.applied_rule_ids, (HEADSMAN_EXECUTION_RULE_ID,))
        self.assertIsNone(result.character_wound)
        self.assertIsNone(result.pending_character_wound)

    def test_profile_brute_repeated_stagger_lethal_wound_retains_same_real_source(self):
        source = kernel(damage=0, staggered=True)
        source = replace(source, target_policy=TargetInjuryPolicy.BRUTE,
            target_state=ProfileInjuryState(0, 3, source.target_state.conditions))
        result = resolve_kernel_attack(source, SequenceRandom([1, 1, 1, 1]))
        self.assertTrue(result.stagger.wound_requested)
        self.assertEqual(result.profile_wound.wounds_inflicted, 1)
        self.assertEqual(result.target_state.wounds, 1)
        self.assertTrue(result.target_state.defeated)
        self.assertEqual(result.target_state.defeat_cause,
            ProfileDecapitationCause('kernel:wound', 'hero'))

    def test_without_execution_source_an_ordinary_brute_wound_does_not_kill(self):
        state = ProfileInjuryState(0, 3)
        request = ProfileWoundRequest('wound', ProfileNpcType.BRUTE, state)
        result = resolve_profile_wound(request)
        self.assertEqual(result.wounds_inflicted, 1)
        self.assertEqual(result.state.wounds, 1)
        self.assertFalse(result.state.defeated)
        self.assertIsNone(result.state.defeat_cause)
        self.assertFalse(result.state_change.defeated)

    def test_profile_execution_is_not_triggered_by_miss_or_first_stagger(self):
        source = kernel(damage=0)
        source = replace(source, target_policy=TargetInjuryPolicy.BRUTE,
            target_state=ProfileInjuryState(0, 3, source.target_state.conditions))
        for values in ([10, 10], [1, 1, 1, 1]):
            with self.subTest(values=values):
                result = resolve_kernel_attack(source, SequenceRandom(values))
                self.assertIsNone(result.profile_wound)
                self.assertFalse(result.target_state.defeated)
                self.assertEqual(result.target_state.wounds, 0)
                self.assertIsNone(result.target_state.defeat_cause)

    def test_profile_cause_preserves_specific_wound_target_and_rejects_unwounded_or_live_death(self):
        cause = ProfileDecapitationCause('wound', 'brute')
        state = ProfileInjuryState(0, 3, ConditionState(frozenset({Condition.PRONE})))
        request = ProfileWoundRequest('wound', ProfileNpcType.BRUTE, state, decapitation_cause=cause)
        result = resolve_profile_wound(request)
        self.assertEqual(result.state.defeat_cause, cause)
        with self.assertRaises(ValueError):
            replace(cause, rule_id='not-headsman')
        with self.assertRaises(ValueError):
            replace(request, id='different-wound')
        with self.assertRaises(ValueError):
            replace(request, state=ProfileInjuryState(0, 3))
        with self.assertRaises(ValueError):
            replace(state, defeated=True, defeat_cause=cause)
        with self.assertRaises(ValueError):
            replace(result.state, defeated=False)
        with self.assertRaises(ValueError):
            replace(result.state, wounds=0)


if __name__ == '__main__':
    unittest.main()
