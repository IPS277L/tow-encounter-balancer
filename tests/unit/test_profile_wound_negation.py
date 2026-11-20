"""Profile Near Miss is selected before Wound traits, HP clamping and follow-ups."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.unit.test_k1_hazard_resolution import avoidance_test, exposure
from tests.unit.test_k1_kernel import kernel_request
from tests.unit.test_k1_miscast_effect_resolution import effect_request
from tests.unit.test_k1_monstrosity_reaction_resolution import request as reaction_request, source as reaction_source
from tests.unit.test_weapon_magic_lifecycle import inventory
from towr.domain.condition_models import Condition, ConditionState, StaggerChoice
from towr.domain.injury_models import (
    AdditionalProfileWound, ProfileDecapitationCause, ProfileInjuryState, ProfileNpcType,
    ProfileStateChangeRequest, ProfileWoundRequest, WoundDiceModifier, WoundNegationOption,
    validate_profile_wound_result_provenance,
)
from towr.domain.magic_models import WizardMagicState
from towr.domain.miscast_effect_models import (
    MiscastEffectTarget, MiscastEarsRingingRequest, MiscastInternalDamageRequest,
)
from towr.domain.resolution_models import (
    ConsumeWoundNegationRequest, HazardResolutionRequest, StaggerImpactRequest, TargetInjuryPolicy,
)
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_magic_lifecycle import prepare_scarab_wound_charge
from towr.domain.weapon_use_models import build_weapon_use
from towr.rules.hazard_resolution import resolve_hazard
from towr.rules.injury_resolution import (
    InvalidWoundDecisionError, MissingWoundDecisionError, resolve_profile_wound,
)
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.miscast_effect_resolution import resolve_ears_ringing, resolve_internal_damage
from towr.rules.monstrosity_reaction_resolution import resolve_monstrosity_reaction
from towr.rules.stagger_impact_resolution import resolve_stagger_impact


OPTION = WoundNegationOption('actual:owned-negation')


class NegationDecision:
    def __init__(self, selected=OPTION.rule_id):
        self.selected = selected
        self.calls = []

    def choose_profile_wound_negation(self, *, request, options):
        self.calls.append((request, options))
        return self.selected

    def choose_repeated_stagger(self, **kwargs):
        return StaggerChoice.SUFFER_WOUND


def wound(*, kind=ProfileNpcType.BRUTE, count=0, limit=2, additional=(), decapitation=False):
    conditions = ConditionState(frozenset({Condition.STAGGERED, Condition.PRONE}))
    return ProfileWoundRequest('actual:wound', kind, ProfileInjuryState(count, limit, conditions),
        additional, negation_options=(OPTION,), decapitation_cause=(
            ProfileDecapitationCause('actual:wound', 'target') if decapitation else None))


class ProfileWoundNegationTests(unittest.TestCase):
    def test_one_actual_negation_preserves_original_state_without_profile_conversion(self):
        for kind, count, limit in ((ProfileNpcType.MINION, 0, 1),
                (ProfileNpcType.BRUTE, 1, 2), (ProfileNpcType.MONSTROSITY, 2, 4)):
            with self.subTest(kind=kind):
                request = wound(kind=kind, count=count, limit=limit)
                decisions = NegationDecision()
                result = resolve_profile_wound(request, decisions=decisions)
                self.assertIs(result.state, request.state)
                self.assertEqual((result.wounds_requested, result.wounds_negated, result.wounds_inflicted), (1, 1, 0))
                self.assertEqual(result.negated_by_rule_id, OPTION.rule_id)
                self.assertEqual(decisions.calls, [(request, (OPTION,))])
                validate_profile_wound_result_provenance(request, result)
                self.assertEqual(len(decisions.calls), 1)  # Validation cannot repeat the decision.

    def test_negation_before_clamping_cannot_spare_minion_from_a_second_actual_wound(self):
        request = wound(kind=ProfileNpcType.MINION, limit=1,
            additional=(AdditionalProfileWound('actual:extra'),))
        result = resolve_profile_wound(request, decisions=NegationDecision())
        self.assertEqual((result.wounds_requested, result.wounds_negated, result.wounds_inflicted), (2, 1, 1))
        self.assertTrue(result.state.defeated)
        self.assertFalse(result.state.conditions.has(Condition.STAGGERED))
        self.assertIn('actual:extra', result.applied_rule_ids)

    def test_full_cancellation_stops_decapitation_but_remaining_wound_still_kills(self):
        for extra in ((), (AdditionalProfileWound('actual:extra'),)):
            with self.subTest(extra=extra):
                request = wound(limit=3, additional=extra, decapitation=True)
                result = resolve_profile_wound(request, decisions=NegationDecision())
                self.assertEqual(result.state.defeated, bool(extra))
                self.assertEqual(result.state.defeat_cause, request.decapitation_cause if extra else None)
                self.assertEqual(result.state.wounds, int(bool(extra)))

    def test_explicit_decline_has_original_wounds_and_no_consumption_receipt(self):
        request = wound()
        result = resolve_profile_wound(request, decisions=NegationDecision(None))
        self.assertEqual(result.wounds_inflicted, 1)
        self.assertEqual(result.wounds_negated, 0)
        self.assertIsNone(result.negated_by_rule_id)
        validate_profile_wound_result_provenance(request, result)

    def test_options_require_real_selector_and_valid_choice_while_no_options_do_not_call_it(self):
        request = wound()
        with self.assertRaises(MissingWoundDecisionError):
            resolve_profile_wound(request)
        for invalid in ('another:rule', 1, True):
            with self.subTest(choice=invalid), self.assertRaises(InvalidWoundDecisionError):
                resolve_profile_wound(request, decisions=NegationDecision(invalid))
        decisions = NegationDecision('unavailable')
        result = resolve_profile_wound(replace(request, negation_options=()), decisions=decisions)
        self.assertEqual(result.wounds_inflicted, 1)
        self.assertEqual(decisions.calls, [])

    def test_cached_nested_corruption_and_forged_result_cannot_hide_behind_int_bool_equality(self):
        request = wound(additional=(AdditionalProfileWound('actual:extra'),))
        result = resolve_profile_wound(request, decisions=NegationDecision())
        for changes in ({'wounds_negated': True}, {'wounds_inflicted': True},
                {'negated_by_rule_id': 'other:rule'}, {'applied_rule_ids': ()}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                validate_profile_wound_result_provenance(request, replace(result, **changes))
        malformed = deepcopy(request)
        object.__setattr__(malformed.additional_wounds[0], 'count', True)
        with self.assertRaises(TypeError):
            resolve_profile_wound(malformed, decisions=NegationDecision())
        malformed_result = deepcopy(result)
        object.__setattr__(malformed_result.state, 'wounds', True)
        with self.assertRaises(TypeError):
            validate_profile_wound_result_provenance(request, malformed_result)

    def test_kernel_cancellation_emits_consumption_without_profile_wound_change(self):
        request = kernel_request(policy=TargetInjuryPolicy.MINION,
            state=ProfileInjuryState(0, 1, ConditionState(frozenset({Condition.STAGGERED}))),
            base_damage=5, negation_options=(OPTION,))
        result = resolve_kernel_attack(request, SequenceRandom([1, 10, 10]), decisions=NegationDecision())
        self.assertEqual(result.profile_wound.wounds_inflicted, 0)
        self.assertEqual(result.target_state, request.target_state)
        self.assertEqual(result.follow_ups, (ConsumeWoundNegationRequest(request.id, OPTION.rule_id),))
        with self.assertRaises(ValueError):
            replace(request, wound_dice_modifiers=(WoundDiceModifier('table:modifier', 1),))

    def test_repeated_stagger_cancellation_keeps_actual_staggered_without_a_wound_followup(self):
        original = ProfileInjuryState(0, 2, ConditionState(frozenset({Condition.STAGGERED})))
        request = StaggerImpactRequest('stagger', 'target', TargetInjuryPolicy.BRUTE,
            original, False, False, wound_negation_options=(OPTION,))
        result = resolve_stagger_impact(request, SequenceRandom([]), decisions=NegationDecision())
        self.assertEqual(result.state, original)
        self.assertEqual(result.profile_wound.wounds_inflicted, 0)
        self.assertEqual(result.follow_ups, (ConsumeWoundNegationRequest('stagger', OPTION.rule_id),))

    def test_hazard_shortfall_cancels_only_one_wound_and_preserves_other_failure_conditions(self):
        original = ProfileInjuryState(0, 4, ConditionState(frozenset({Condition.STAGGERED})))
        for rating, wounds in ((1, 0), (3, 2)):
            with self.subTest(rating=rating):
                source = exposure(rating=rating, failure_conditions=(Condition.PRONE,))
                request = HazardResolutionRequest(id='hazard', exposure=source, target_id='target',
                    target_policy=TargetInjuryPolicy.MONSTROSITY, target_state=original,
                    avoidance_test=avoidance_test(source, [10]),
                    wound_negation_options=(OPTION,))
                result = resolve_hazard(request, SequenceRandom([]), decisions=NegationDecision())
                self.assertEqual(result.state.wounds, wounds)
                self.assertTrue(result.state.conditions.has(Condition.PRONE))
                self.assertEqual(result.state.conditions.has(Condition.STAGGERED), wounds == 0)
                self.assertTrue(any(type(item) is ConsumeWoundNegationRequest for item in result.follow_ups))
                self.assertEqual(any(type(item) is ProfileStateChangeRequest for item in result.follow_ups), wounds > 0)

    def test_internal_damage_and_ears_ringing_forward_actual_profile_negation(self):
        original = ProfileInjuryState(0, 2, ConditionState(frozenset({Condition.STAGGERED})))
        internal = MiscastInternalDamageRequest('internal', effect_request((8, 8, 8, 8)),
            WizardMagicState(miscast_dice=4), MiscastEffectTarget('wizard', TargetInjuryPolicy.BRUTE, original),
            wound_negation_options=(OPTION,))
        result = resolve_internal_damage(internal, SequenceRandom([]), decisions=NegationDecision())
        self.assertEqual(result.state, original)
        self.assertEqual(result.magic_state.miscast_dice, 0)
        self.assertIsNotNone(result.consume_wound_negation)
        ears = MiscastEarsRingingRequest('ears', effect_request((9, 9, 9, 9)),
            WizardMagicState(miscast_dice=4), (MiscastEffectTarget('wizard', TargetInjuryPolicy.BRUTE,
                original, wound_negation_options=(OPTION,)),))
        result = resolve_ears_ringing(ears, decisions=NegationDecision())
        self.assertEqual(result.targets[0].state, original)
        self.assertEqual(result.targets[0].profile_wound.wounds_inflicted, 0)
        self.assertIsNotNone(result.targets[0].consume_wound_negation)

    def test_monstrosity_reaction_cancelled_wound_does_not_trigger_terrifying(self):
        source = replace(reaction_source(terrifying=True), wound_negation_options=(OPTION,))
        request = reaction_request(reaction_source=source, has_given_ground=True)
        result = resolve_monstrosity_reaction(request, decisions=NegationDecision())
        self.assertEqual(result.profile_wound.wounds_inflicted, 0)
        self.assertEqual(result.state, request.state)
        self.assertFalse(result.state.conditions.has(Condition.BROKEN))
        self.assertEqual(result.condition_applications, ())
        self.assertEqual(result.follow_ups,
            (ConsumeWoundNegationRequest(request.id, OPTION.rule_id),))

    def test_scarab_gains_charges_from_only_remaining_actual_wounds_without_reasking_choice(self):
        weapon_inventory = inventory(WeaponKind.SCARAB_KNIFE)
        use = build_weapon_use('actor', weapon_inventory, weapon_inventory.active_item_id)
        for additional in ((), (AdditionalProfileWound('actual:extra'),)):
            with self.subTest(additional=additional):
                request = wound(limit=3, additional=additional)
                decisions = NegationDecision()
                result = resolve_profile_wound(request, decisions=decisions)
                transition = prepare_scarab_wound_charge(use, weapon_inventory, result, profile_request=request)
                self.assertEqual(transition.after_inventory.item(weapon_inventory.active_item_id).charges,
                    int(bool(additional)))
                self.assertEqual(len(decisions.calls), 1)


if __name__ == '__main__':
    unittest.main()
