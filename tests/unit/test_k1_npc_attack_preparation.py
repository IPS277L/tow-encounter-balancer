from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from itertools import product
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from towr.domain.attack_models import AttackOutcome, DamageProfile, ResilienceProfile, ConditionOnHitSpec
from towr.domain.condition_models import Condition
from towr.domain.npc_attack_preparation_models import (
    NPC_OUTSIDE_OPTIMUM_RULE_ID, NpcAttackProfile, NpcAttackSelectionSnapshot,
    NpcAttackPreparationRequest,
)
from towr.domain.protection_models import ProtectionPreparationRequest, ProtectionTestOption
from towr.domain.ranged_weapon_profiles import RangedWeaponHands as Hands, RangedWeaponRange as Range
from towr.domain.test_models import DiceModifier, InlineProfile, Skill, TestRequest
from towr.rules.attack_resolution import resolve_attack
from towr.rules import npc_attack_preparation as preparation


def brigand():
    # BOOK-GM-GUIDE 1.1, Allies and Antagonists / Brigands & Footpads, p97.
    # Neither Axe armour bonus nor PC Warbow properties are inferred by name.
    return NpcAttackSelectionSnapshot("snapshot:brigand", "brigand", (
        NpcAttackProfile("axe", "RULE-PROFILE-TALABEC-004:axe", Skill.MELEE,
            InlineProfile(3, 3), DamageProfile(3), Range.CLOSE, Range.CLOSE, Hands.ONE_HANDED),
        NpcAttackProfile("warbow", "RULE-PROFILE-TALABEC-004:warbow", Skill.SHOOTING,
            InlineProfile(3, 3), DamageProfile(3), Range.MEDIUM, Range.LONG, Hands.TWO_HANDED),
    ), ("axe", "warbow"))


def request(**changes):
    values = dict(id="prepare:npc", attack_id="attack:npc", attacker_test_id="test:npc",
        snapshot=brigand(), selected_attack_id="axe", target_id="target", target_range=Range.CLOSE,
        target_resilience=ResilienceProfile(3, 1), has_enemy_in_close_range=True,
        attacker_is_staggered=False, range_approved_by_gm=False)
    values.update(changes)
    return NpcAttackPreparationRequest(**values)


def protection(npc, *, opposed=True):
    return ProtectionPreparationRequest("prepare:protection", "target", npc.attack,
        npc.selected_profile.skill, opposed, False, False, False,
        Skill.ATHLETICS if opposed else None,
        (ProtectionTestOption("target", Skill.ATHLETICS, TestRequest("test:target", InlineProfile(3, 3))),))


class K1NpcAttackPreparationTests(unittest.TestCase):
    def test_brigand_exact_numeric_profiles_do_not_inherit_pc_weapon_traits(self):
        for selected, distance in (("axe", Range.CLOSE), ("warbow", Range.MEDIUM)):
            source = request(selected_attack_id=selected, target_range=distance,
                             has_enemy_in_close_range=distance is Range.CLOSE)
            before = deepcopy(source)
            result = preparation.prepare_npc_attack(source)
            self.assertIs(result.source_request, source)
            self.assertIs(result.attack.attacker_test.profile, result.selected_profile.test_profile)
            self.assertEqual(result.attack.attacker_test.profile, InlineProfile(3, 3))
            self.assertEqual(result.attack.impact_spec.damage.base, 3)
            self.assertEqual(result.attack.impact_spec.damage_modifiers, ())
            self.assertFalse(result.attack.impact_spec.ignores_armour)
            self.assertEqual(result.attack.secondary_effects, ())
            self.assertIsNone(result.attack.defender_test)
            self.assertEqual(source, before)
            with self.assertRaises(FrozenInstanceError):
                result.attack = None

    def test_unknown_or_unavailable_selected_id_never_falls_back(self):
        for selected in ("missing", "warbow"):
            with self.assertRaisesRegex(ValueError, "unavailable"):
                request(snapshot=replace(brigand(), available_attack_ids=("axe",)), selected_attack_id=selected)
        with self.assertRaisesRegex(ValueError, "unavailable"):
            request(snapshot=replace(brigand(), available_attack_ids=()))
        # No selection based on snapshot order or damage.
        source = request(snapshot=replace(brigand(), profiles=tuple(reversed(brigand().profiles))))
        self.assertEqual(preparation.prepare_npc_attack(source).selected_profile.id, "axe")

    def test_town_watch_polearm_maximum_short_includes_close_but_not_medium(self):
        # GM 1.1 p97: Polearm (Short, 3d/3, Dam 5, 2H).
        polearm = NpcAttackProfile("polearm", "RULE-PROFILE-TALABEC-006:polearm", Skill.MELEE,
            InlineProfile(3, 3), DamageProfile(5), Range.CLOSE, Range.SHORT, Hands.TWO_HANDED)
        snapshot = NpcAttackSelectionSnapshot("snapshot:watch", "watch", (polearm,), (polearm.id,))
        for distance in (Range.CLOSE, Range.SHORT):
            result = preparation.prepare_npc_attack(request(snapshot=snapshot,
                selected_attack_id=polearm.id, target_range=distance))
            self.assertEqual(result.attack.impact_spec.damage.base, 5)
            self.assertEqual(result.attack.is_close_range, distance is Range.CLOSE)
            self.assertEqual(result.attack.attacker_test.dice_modifiers, ())
        for distance in (Range.MEDIUM, Range.LONG):
            with self.assertRaisesRegex(ValueError, "maximum range"):
                request(snapshot=snapshot, selected_attack_id=polearm.id, target_range=distance)

    def test_shooting_optimum_penalty_is_added_once_and_modifiers_preserved(self):
        for distance, penalty in ((Range.SHORT, -1), (Range.MEDIUM, 0), (Range.LONG, 0)):
            source = request(selected_attack_id="warbow", target_range=distance,
                has_enemy_in_close_range=False, dice_modifiers=(DiceModifier("scenario:help", 1),))
            result = preparation.prepare_npc_attack(source)
            mods = result.attack.attacker_test.dice_modifiers
            self.assertEqual(mods[:1], source.dice_modifiers)
            self.assertEqual(sum(m.amount for m in mods if m.rule_id == NPC_OUTSIDE_OPTIMUM_RULE_ID), penalty)
            self.assertEqual(NPC_OUTSIDE_OPTIMUM_RULE_ID in result.applied_rule_ids, bool(penalty))
        with self.assertRaisesRegex(ValueError, "owned by preparation"):
            request(dice_modifiers=(DiceModifier(NPC_OUTSIDE_OPTIMUM_RULE_ID, -1),))

    def test_any_close_enemy_blocks_warbow_even_when_target_far(self):
        for distance in (Range.CLOSE, Range.SHORT, Range.MEDIUM, Range.LONG):
            with self.assertRaisesRegex(ValueError, "Close in Optimum"):
                request(selected_attack_id="warbow", target_range=distance)
        with self.assertRaisesRegex(ValueError, "Close in Optimum"):
            request(selected_attack_id="warbow", has_enemy_in_close_range=False)

    def test_explicit_shooting_profile_close_and_two_handed_gm_range(self):
        # Synthetic numeric profile: exercise generic range rules, not a catalog item.
        base = replace(brigand().profiles[1], range_min=Range.CLOSE, range_max=Range.SHORT)
        for hands, distance in product((Hands.ONE_HANDED, Hands.TWO_HANDED), (Range.CLOSE, Range.LONG)):
            profile = replace(base, hands=hands)
            snapshot = replace(brigand(), profiles=(profile,), available_attack_ids=(profile.id,))
            approved = hands is Hands.TWO_HANDED and distance is Range.LONG
            result = preparation.prepare_npc_attack(request(snapshot=snapshot, selected_attack_id=profile.id,
                target_range=distance, range_approved_by_gm=approved))
            self.assertEqual(result.attack.is_close_range, distance is Range.CLOSE)
            self.assertEqual(len(result.attack.attacker_test.dice_modifiers), int(distance is Range.LONG))
            if approved:
                with self.assertRaisesRegex(ValueError, "GM approval"):
                    replace(result.source_request, range_approved_by_gm=False)

    def test_unsupported_skills_extreme_and_inapplicable_approval_are_explicit(self):
        for skill in (Skill.BRAWN, Skill.THROWING, Skill.AWARENESS):
            with self.assertRaisesRegex(ValueError, "Melee/Shooting"):
                replace(brigand().profiles[0], skill=skill)
        for approval in (False, True):
            with self.assertRaisesRegex(ValueError, "Extreme/Aim"):
                request(selected_attack_id="warbow", target_range=Range.EXTREME,
                    has_enemy_in_close_range=False, range_approved_by_gm=approval)
        with self.assertRaisesRegex(ValueError, "cannot extend Melee"):
            request(range_approved_by_gm=True)
        with self.assertRaisesRegex(ValueError, "not applicable"):
            request(selected_attack_id="warbow", target_range=Range.MEDIUM,
                    has_enemy_in_close_range=False, range_approved_by_gm=True)

    def test_explicit_profile_traits_and_staggered_context_survive(self):
        profile = replace(brigand().profiles[0], ignores_armour=True,
            secondary_effects=(ConditionOnHitSpec(Condition.PRONE, "fixture:prone"),))
        source = request(snapshot=replace(brigand(), profiles=(profile,), available_attack_ids=(profile.id,)),
                         attacker_is_staggered=True)
        result = preparation.prepare_npc_attack(source)
        self.assertTrue(result.attack.impact_spec.ignores_armour)
        self.assertEqual(result.attack.secondary_effects, profile.secondary_effects)
        self.assertTrue(result.attack.attacker_is_staggered)
        self.assertIn("fixture:prone", result.applied_rule_ids)
        self.assertIn(profile.source_rule_id, result.applied_rule_ids)

    def test_snapshot_request_and_profile_validation(self):
        snapshot = brigand()
        for changes in ({"profiles": (None,)}, {"profiles": (snapshot.profiles[0],) * 2},
                        {"available_attack_ids": ("unknown",)}, {"available_attack_ids": ("axe", "axe")},
                        {"actor_id": ""}, {"id": ""}):
            with self.assertRaises((ValueError, TypeError)):
                replace(snapshot, **changes)
        for changes in ({"id": ""}, {"source_rule_id": ""}, {"skill": "melee"},
                        {"test_profile": None}, {"damage": None}, {"hands": "1h"},
                        {"range_min": Range.SHORT}, {"range_max": "long"},
                        {"ignores_armour": 1}, {"secondary_effects": (None,)}):
            with self.assertRaises((ValueError, TypeError)):
                replace(snapshot.profiles[0], **changes)
        source = request()
        for changes in ({"id": ""}, {"snapshot": None}, {"target_id": "brigand"},
                        {"target_range": "close"}, {"target_resilience": None}, {"rule_id": "other"},
                        {"dice_modifiers": (None,)}, {"has_enemy_in_close_range": None},
                        {"attacker_is_staggered": 1}, {"range_approved_by_gm": "yes"}):
            with self.assertRaises((ValueError, TypeError)):
                replace(source, **changes)
        with self.assertRaises(TypeError):
            preparation.prepare_npc_attack(None)

    def test_result_rejects_changed_profile_attack_and_trace_even_with_same_ids(self):
        source = request()
        result = preparation.prepare_npc_attack(source)
        changed = replace(source.snapshot.profiles[0], damage=DamageProfile(9))
        for changes in (
            {"request_id": "other"}, {"source_request": None},
            {"target_id": "other"}, {"snapshot": replace(source.snapshot, actor_id="other")},
            {"source_request": replace(source, target_id="other")},
            {"source_request": replace(source, snapshot=replace(source.snapshot, id="other"))},
            {"source_request": replace(source, snapshot=replace(source.snapshot, available_attack_ids=("axe",)))},
            {"selected_profile": changed}, {"attack": replace(result.attack, attacker_is_staggered=True)},
            {"applied_rule_ids": ()}, {"applied_rule_ids": (*result.applied_rule_ids, "foreign")},
            {"source_request": replace(source, snapshot=replace(source.snapshot,
                profiles=(changed, source.snapshot.profiles[1])))},
        ):
            with self.assertRaises((ValueError, TypeError)):
                replace(result, **changes)

    def test_protection_pair_rejects_same_id_attack_substitution_skill_or_target_before_prepare(self):
        npc = preparation.prepare_npc_attack(request())
        source = protection(npc)
        for candidate in (
            replace(source, attack=replace(source.attack, attacker_is_staggered=True)),
            replace(source, attack=replace(source.attack, impact_spec=replace(source.attack.impact_spec,
                damage=DamageProfile(9)))),
            replace(source, attack_skill=Skill.SHOOTING),
            replace(source, defender_id="other", options=tuple(replace(o, defender_id="other") for o in source.options)),
        ):
            with patch.object(preparation, "prepare_protection") as prepare:
                with self.assertRaisesRegex(ValueError, "exact prepared NPC"):
                    preparation.prepare_npc_attack_protection(npc, candidate)
            prepare.assert_not_called()

    def test_composition_keeps_nested_results_and_unified_trace(self):
        npc = preparation.prepare_npc_attack(request())
        source = protection(npc)
        with patch.object(preparation, "prepare_protection", wraps=preparation.prepare_protection) as prepare:
            result = preparation.prepare_npc_attack_protection(npc, source)
        prepare.assert_called_once_with(source)
        self.assertIs(result.npc_attack, npc)
        self.assertIs(result.protection.source_request, source)
        self.assertIs(result.attack, result.protection.attack)
        self.assertEqual(result.applied_rule_ids, tuple(dict.fromkeys((*npc.applied_rule_ids, *result.protection.applied_rule_ids))))
        for changes in ({"npc_attack": None}, {"protection": None}, {"applied_rule_ids": ()},
                        {"npc_attack": preparation.prepare_npc_attack(replace(npc.source_request, attacker_is_staggered=True))}):
            with self.assertRaises((ValueError, TypeError)):
                replace(result, **changes)

    def test_single_opposed_or_unopposed_execution_after_pure_preparation(self):
        for opposed, hit, selected in product((False, True), (False, True), ("axe", "warbow")):
            source = request(selected_attack_id=selected,
                target_range=Range.CLOSE if selected == "axe" else Range.MEDIUM,
                has_enemy_in_close_range=selected == "axe")
            before = deepcopy(source)
            rng = SequenceRandom([1 if hit else 10, 10, 10, *([10, 10, 10] if opposed else []), 7])
            npc = preparation.prepare_npc_attack(source)
            prepared = preparation.prepare_npc_attack_protection(npc, protection(npc, opposed=opposed))
            result = resolve_attack(prepared.attack, rng)
            self.assertEqual(rng.randint(1, 10), 7)
            self.assertIs(result.outcome, AttackOutcome.HIT if hit else AttackOutcome.MISS)
            self.assertEqual(result.attacker_test.trace.rolled_dice, 3)
            self.assertEqual(result.defender_test is not None, opposed)
            self.assertEqual(result.request_id, source.attack_id)
            self.assertEqual(source, before)
            self.assertIn(npc.selected_profile.source_rule_id, prepared.applied_rule_ids)


if __name__ == "__main__":
    unittest.main()
