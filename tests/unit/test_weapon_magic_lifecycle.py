"""Actual-source and finite-stock boundaries for GM83–84 Magic Weapons."""
from dataclasses import FrozenInstanceError, replace
import unittest

from tests.helpers import SequenceRandom
from towr.domain.attack_models import AttackOutcome
from towr.domain.fate_models import FATE_NEAR_MISS_RULE_ID, FateNearMissBurnRequest, FateSessionState
from towr.domain.infection_models import DailyWoundState
from towr.domain.injury_models import (
    CharacterInjuryState, CharacterWoundRequest, ProfileInjuryState,
    ProfileNpcType, ProfileWoundRequest, WoundNegationOption,
)
from towr.domain.resolution_models import ConsumeWoundNegationRequest
from towr.domain.test_models import (
    DiceModifier, InlineProfile, QualityModifier, TestQuality, TestRequest,
)
from towr.domain.weapon_catalog import WeaponKind as W
from towr.domain.weapon_inventory_models import (
    WeaponGrip as G, WeaponItemLocation as L, WeaponItemSource,
    initial_weapon_inventory,
)
from towr.domain.weapon_magic_lifecycle import (
    GROTARGG_RETRIEVE_RULE_ID, prepare_weapon_magic_attack, apply_weapon_magic_attack,
    prepare_scarab_wound_charge, apply_scarab_wound_charge,
    prepare_scarab_healing_resources, apply_scarab_healing_resources,
    prepare_hammer_retrieval_test, prepare_hammer_retrieval, apply_hammer_retrieval,
)
from towr.domain.weapon_use_models import build_weapon_use
from towr.domain.wound_lifecycle_models import (
    CharacterWoundLifecycleRollRequest, CharacterWoundLifecycleCompletionRequest,
)
from towr.rules.injury_resolution import resolve_profile_wound
from towr.rules.test_resolution import resolve_test, RerollAllFailures
from towr.rules.wound_lifecycle_resolution import (
    roll_character_wound_lifecycle, complete_character_wound_lifecycle,
)


def inventory(kind, *, actor='actor', grip=G.LEFT, charges=0, spare=True):
    sources = (WeaponItemSource('main', kind, L.HELD, grip, initial_charges=charges),)
    if spare:
        sources += (WeaponItemSource('gun', W.PISTOL, L.CARRIED, None, initially_loaded=True),)
    result = initial_weapon_inventory(actor, sources)
    return replace(result, active_item_id=result.items[0].id)


def profile_wound(*, count=1):
    source = ProfileWoundRequest('wound', ProfileNpcType.BRUTE,
        ProfileInjuryState(wounds=0, wound_limit=3), base_wounds=count)
    return source, resolve_profile_wound(source)


def character_wound(*, near_miss=False, negated=False):
    class Negate:
        def choose_wound_negation(self, **_):
            return 'negate'
    wound = CharacterWoundRequest('wound', CharacterInjuryState(),
        negation_options=(WoundNegationOption('negate'),) if negated else ())
    roll = roll_character_wound_lifecycle(
        CharacterWoundLifecycleRollRequest('roll', 'hero', wound), SequenceRandom([1]),
        decisions=Negate() if negated else None)
    burn = FateNearMissBurnRequest('burn',
        FateSessionState('session', 'hero', rating=1, session_spend_limit=1),
        ConsumeWoundNegationRequest('wound', FATE_NEAR_MISS_RULE_ID)) if near_miss else None
    return complete_character_wound_lifecycle(CharacterWoundLifecycleCompletionRequest(
        'complete', roll, roll.wound_result.state, DailyWoundState('day', 'hero'),
        None if near_miss or negated else 'register', burn))


def stuck_hammer():
    before = inventory(W.GROTARGGS_HAMMER, grip=G.BOTH)
    use = build_weapon_use('actor', before, before.active_item_id)
    transition = prepare_weapon_magic_attack(use, AttackOutcome.MISS, higher_ground=True)
    return transition.actor_inventory


def retrieval_test(values, *, glorious=False):
    test = TestRequest('retrieve', InlineProfile(4, 6),
        quality_modifiers=(QualityModifier('glory', TestQuality.GLORIOUS),) if glorious else ())
    test = prepare_hammer_retrieval_test(test)
    result = resolve_test(test, SequenceRandom(values), decisions=RerollAllFailures())
    return test, result


class WeaponMagicLifecycleTests(unittest.TestCase):
    def test_hammer_embeds_only_on_real_higher_ground_miss(self):
        before = inventory(W.GROTARGGS_HAMMER, grip=G.BOTH)
        use = build_weapon_use('actor', before, before.active_item_id)
        for outcome, higher, expected in ((AttackOutcome.HIT, True, L.HELD),
                (AttackOutcome.MISS, False, L.HELD), (AttackOutcome.MISS, True, L.STUCK)):
            with self.subTest(outcome=outcome, higher=higher):
                transition = prepare_weapon_magic_attack(use, outcome, higher_ground=higher)
                after, target = apply_weapon_magic_attack(before, None, transition)
                self.assertEqual(after.items[0].location, expected)
                self.assertEqual(after.items[1], before.items[1])
                self.assertEqual(after.active_item_id, before.active_item_id)
                self.assertIsNone(target)
                if expected is L.STUCK:
                    self.assertIsNone(after.items[0].grip)
                    with self.assertRaises(ValueError):
                        apply_weapon_magic_attack(after, None, transition)

    def test_fracasse_disarms_exactly_one_held_magic_unit_and_preserves_other_sources(self):
        before = inventory(W.MORNING_STAR_OF_FRACASSE)
        target = initial_weapon_inventory('target', (
            WeaponItemSource('knife', W.SCARAB_KNIFE, L.HELD, G.LEFT, initial_charges=5),
            WeaponItemSource('trickster', W.TRICKSTER_BLADE, L.HELD, G.RIGHT),
            WeaponItemSource('dragon', W.DRAGON_BOW, L.CARRIED, None)))
        use = build_weapon_use('actor', before, before.active_item_id)
        transition = prepare_weapon_magic_attack(use, AttackOutcome.HIT,
            target_inventory=target, disarmed_item_id=target.items[0].id)
        attacker_after, after = apply_weapon_magic_attack(before, target, transition)
        self.assertEqual(attacker_after, before)
        self.assertEqual(after.items[0].location, L.DROPPED)
        self.assertEqual(after.items[0].charges, 5)
        self.assertEqual(after.items[0].source, target.items[0].source)
        self.assertEqual(after.items[1:], target.items[1:])
        with self.assertRaises(ValueError):
            apply_weapon_magic_attack(before, after, transition)
        with self.assertRaises(ValueError):
            replace(transition, after_target_inventory=target)

    def test_fracasse_rejects_miss_carried_mundane_missing_or_foreign_disarm(self):
        before = inventory(W.MORNING_STAR_OF_FRACASSE)
        use = build_weapon_use('actor', before, before.active_item_id)
        target = inventory(W.SCARAB_KNIFE, actor='target')
        for outcome, selected in ((AttackOutcome.MISS, target.items[0].id),
                (AttackOutcome.HIT, target.items[1].id), (AttackOutcome.HIT, 'foreign'),
                (AttackOutcome.HIT, None)):
            with self.subTest(outcome=outcome, selected=selected), self.assertRaises(ValueError):
                prepare_weapon_magic_attack(use, outcome, target_inventory=target, disarmed_item_id=selected)
        ordinary = inventory(W.SWORD, actor='target')
        self.assertEqual(prepare_weapon_magic_attack(use, AttackOutcome.HIT,
            target_inventory=ordinary).after_target_inventory, ordinary)
        with self.assertRaises(TypeError):
            prepare_weapon_magic_attack(use, 'hit')

    def test_non_fracasse_contributor_cannot_disarm_and_held_second_fracasse_can(self):
        target = inventory(W.SCARAB_KNIFE, actor='target')
        normal = inventory(W.SWORD)
        use = build_weapon_use('actor', normal, normal.active_item_id)
        with self.assertRaises(ValueError):
            prepare_weapon_magic_attack(use, AttackOutcome.HIT,
                target_inventory=target, disarmed_item_id=target.items[0].id)
        mixed = initial_weapon_inventory('actor', (
            WeaponItemSource('sword', W.SWORD, L.HELD, G.LEFT),
            WeaponItemSource('star', W.MORNING_STAR_OF_FRACASSE, L.HELD, G.RIGHT)))
        combined = build_weapon_use('actor', mixed, mixed.items[0].id, (mixed.items[1].id,))
        transition = prepare_weapon_magic_attack(combined, AttackOutcome.HIT,
            target_inventory=target, disarmed_item_id=target.items[0].id)
        self.assertEqual(transition.after_target_inventory.items[0].location, L.DROPPED)

    def test_actual_profile_wound_charges_only_used_knives_preserving_source_and_gun(self):
        before = inventory(W.SCARAB_KNIFE, charges=2)
        use = build_weapon_use('actor', before, before.active_item_id)
        request, wound = profile_wound()
        transition = prepare_scarab_wound_charge(use, before, wound, profile_request=request)
        after = apply_scarab_wound_charge(before, transition)
        self.assertEqual(after.items[0].charges, 3)
        self.assertEqual(after.items[0].source.initial_charges, 2)
        self.assertEqual(after.items[1], before.items[1])
        with self.assertRaises(ValueError):
            apply_scarab_wound_charge(after, transition)
        with self.assertRaises(ValueError):
            replace(transition, after_inventory=before)

    def test_dual_knives_retain_two_charge_sources_but_carried_knife_does_not_charge(self):
        before = initial_weapon_inventory('actor', (
            WeaponItemSource('left', W.SCARAB_KNIFE, L.HELD, G.LEFT),
            WeaponItemSource('right', W.SCARAB_KNIFE, L.HELD, G.RIGHT, initial_charges=2),
            WeaponItemSource('carried', W.SCARAB_KNIFE, L.CARRIED, None, initial_charges=4)))
        use = build_weapon_use('actor', before, before.items[0].id, (before.items[1].id,))
        request, result = profile_wound(count=5)
        transition = prepare_scarab_wound_charge(use, before, result, profile_request=request)
        self.assertEqual(result.wounds_requested, 5)
        self.assertEqual(result.wounds_inflicted, 3)
        self.assertEqual(tuple(item.charges for item in transition.after_inventory.items), (3, 5, 4))

    def test_profile_charge_rejects_forged_wound_and_non_knife_attack(self):
        before = inventory(W.SCARAB_KNIFE)
        use = build_weapon_use('actor', before, before.active_item_id)
        request, wound = profile_wound()
        for bad in (replace(wound, wounds_inflicted=9), replace(wound, request_id='other'),
                replace(wound, wounds_inflicted=True),
                replace(wound, state_change=replace(wound.state_change, current_wounds=True))):
            with self.subTest(bad=bad), self.assertRaises((TypeError, ValueError)):
                prepare_scarab_wound_charge(use, before, bad, profile_request=request)
        sword = inventory(W.SWORD)
        with self.assertRaises(ValueError):
            prepare_scarab_wound_charge(build_weapon_use('actor', sword, sword.active_item_id),
                sword, wound, profile_request=request)
        with self.assertRaises(TypeError):
            prepare_scarab_wound_charge(use, before, wound)

    def test_character_credit_waits_for_actual_completion_and_near_miss_or_negation_gives_zero(self):
        before = inventory(W.SCARAB_KNIFE)
        use = build_weapon_use('actor', before, before.active_item_id)
        for near_miss, negated, expected in ((False, False, 1), (True, False, 0), (False, True, 0)):
            with self.subTest(near_miss=near_miss, negated=negated):
                completion = character_wound(near_miss=near_miss, negated=negated)
                transition = prepare_scarab_wound_charge(use, before, completion)
                self.assertEqual(transition.after_inventory.items[0].charges, expected)
        completion = character_wound()
        with self.assertRaises(TypeError):
            prepare_scarab_wound_charge(use, before, completion.wound_result)

    def test_deferred_credit_retains_current_dropped_unit_instead_of_restoring_old_grip(self):
        before = inventory(W.SCARAB_KNIFE, charges=2)
        use = build_weapon_use('actor', before, before.active_item_id)
        dropped = before.with_item(replace(before.items[0], location=L.DROPPED, grip=None))
        transition = prepare_scarab_wound_charge(use, dropped, character_wound())
        after = apply_scarab_wound_charge(dropped, transition)
        self.assertEqual(after.items[0].location, L.DROPPED)
        self.assertIsNone(after.items[0].grip)
        self.assertEqual(after.items[0].charges, 3)

    def test_scarab_heal_spends_exact_same_three_charges_and_never_grants_healing_itself(self):
        before = inventory(W.SCARAB_KNIFE, charges=5)
        use = build_weapon_use('actor', before, before.active_item_id)
        transition = prepare_scarab_healing_resources(use, before.items[0].id)
        after = apply_scarab_healing_resources(before, transition)
        self.assertEqual(after.items[0].charges, 2)
        self.assertEqual(after.items[1], before.items[1])
        self.assertEqual(after.items[0].source, before.items[0].source)
        with self.assertRaises(ValueError):
            apply_scarab_healing_resources(after, transition)
        with self.assertRaises(ValueError):
            prepare_scarab_healing_resources(build_weapon_use('actor', after, after.active_item_id),
                after.items[0].id)
        with self.assertRaises(ValueError):
            prepare_scarab_healing_resources(use, before.items[1].id)

    def test_hammer_actual_recover_test_cost_is_minus_two_once_then_only_success_retrieves(self):
        before = stuck_hammer()
        for dice, location in (([1, 10], L.HELD), ([10, 10], L.STUCK)):
            with self.subTest(dice=dice):
                test, result = retrieval_test(dice)
                self.assertEqual(result.trace.rolled_dice, 2)
                self.assertEqual(test.dice_modifiers, (DiceModifier(GROTARGG_RETRIEVE_RULE_ID, -2),))
                transition = prepare_hammer_retrieval(before, before.items[0].id, (G.LEFT, G.RIGHT), test, result)
                after = apply_hammer_retrieval(before, transition)
                self.assertEqual(after.items[0].location, location)
                self.assertEqual(after.items[0].grip, G.BOTH if location is L.HELD else None)
                self.assertEqual(after.items[1], before.items[1])
                self.assertEqual(after.items[0].source, before.items[0].source)
                if result.succeeded:
                    with self.assertRaises(ValueError):
                        apply_hammer_retrieval(after, transition)
                with self.assertRaises(ValueError):
                    prepare_hammer_retrieval_test(test)

    def test_hammer_retrieval_keeps_real_glorious_rerolls_and_rejects_counter_forgery(self):
        before = stuck_hammer()
        test, result = retrieval_test([10, 10, 1, 10], glorious=True)
        transition = prepare_hammer_retrieval(before, before.items[0].id, (G.LEFT, G.RIGHT), test, result)
        self.assertEqual(transition.after_inventory.items[0].location, L.HELD)
        self.assertEqual(len(transition.result.trace.rerolls), 2)
        for trace in (replace(result.trace, successes=9), replace(result.trace, threshold=9),
                replace(result.trace, request_id='other'), replace(result.trace, successes=True),
                replace(result.trace, rerolls=())):
            with self.subTest(trace=trace), self.assertRaises((ValueError, TypeError)):
                prepare_hammer_retrieval(before, before.items[0].id, (G.LEFT, G.RIGHT),
                    test, replace(result, trace=trace))

    def test_hammer_retrieval_rejects_missing_hand_shield_and_other_held_weapon(self):
        before = stuck_hammer()
        test, result = retrieval_test([1, 1])
        for hands in ((G.LEFT,), (G.RIGHT,), (G.LEFT, G.LEFT)):
            with self.subTest(hands=hands), self.assertRaises((ValueError, TypeError)):
                prepare_hammer_retrieval(before, before.items[0].id, hands, test, result)
        with self.assertRaises(ValueError):
            prepare_hammer_retrieval(replace(before, shield_hand=G.LEFT), before.items[0].id,
                (G.LEFT, G.RIGHT), test, result)
        gun = before.items[1]
        occupied = before.with_item(replace(gun, location=L.HELD, grip=G.LEFT))
        with self.assertRaises(ValueError):
            prepare_hammer_retrieval(occupied, before.items[0].id, (G.LEFT, G.RIGHT), test, result)

    def test_transitions_are_frozen_and_reject_unrelated_resource_or_source_mutation(self):
        before = inventory(W.SCARAB_KNIFE, charges=3)
        use = build_weapon_use('actor', before, before.active_item_id)
        transition = prepare_scarab_healing_resources(use, before.items[0].id)
        with self.assertRaises(FrozenInstanceError):
            transition.item_id = 'other'
        with self.assertRaises(ValueError):
            replace(transition, after_inventory=before)
        changed_source = replace(before.items[0].source, initial_charges=2)
        forged = replace(before, items=(replace(before.items[0], source=changed_source), *before.items[1:]))
        with self.assertRaises(ValueError):
            prepare_scarab_wound_charge(use, forged, character_wound())


if __name__ == '__main__':
    unittest.main()
