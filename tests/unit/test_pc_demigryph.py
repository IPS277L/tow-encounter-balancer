"""Preparation-only snapshots for the source-bound two-strike Attack bridge.

These tests use actual K1 receipts; they do not claim a native replay prefix.
The native owner separately projects its complete journal and consequences.
"""
from tests.support.generated_weapon_sources import initial_generated_weapons
from dataclasses import replace
import unittest

from tests.support.pc_tactics_fixtures import automatic_source, tactical_snapshot
from towr.domain.armour_models import ArmourLoadout, BodyArmour
from towr.domain.condition_models import Condition, ConditionState, StaggerChoice
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_demigryph_models import (
    DEMIGRYPH_GRIM_RULE_ID, DemigryphGrimLeg, PcDemigryphIntentProof,
    PcDemigryphStrikeProof, build_pc_demigryph_strike, current_pc_demigryph_intent,
    demigryph_primary_qualities, expected_pc_demigryph_intent,
    latest_pc_kernel_attack, pc_kernel_resolution,
)
from towr.domain.pc_melee_result_models import PcAttackProof, PcFateDecline, build_pc_melee_attack, initial_pc_melee_state
from towr.domain.pc_combat_equipment_models import PcItemLocation, PcWeaponItem
from towr.domain.pc_melee_models import PcMeleeWeapon, PcWeaponHand
from towr.domain.pc_weapon_intent_models import (
    build_pc_attack_weapon_intent, build_pc_explicit_attack_weapon_intent,
)
from towr.domain.pc_mount_models import CombatMount, RiderKind, expected_pc_dismount, updated_pc_mounts
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.test_models import InlineProfile, QualityModifier, TestQuality
from towr.domain.resolution_models import AttackerStaggerRequest
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest, ManoeuvreKind,
    CombatTurnStartRequest,
)
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.protection_preparation import prepare_protection
from towr.rules.test_resolution import KeepAllFailures
from towr.rules.turn_resolution import reserve_combat_action_slot, start_combat_turn


class Ones:
    def randint(self, low, high):
        if (low, high) != (1, 10):
            raise AssertionError('literal Demigryph preparation uses d10 only')
        return 1


class TakeWound(KeepAllFailures):
    def choose_repeated_stagger(self, *, request, allowed_choices):
        if StaggerChoice.SUFFER_WOUND not in allowed_choices:
            raise AssertionError('literal Claws trace requires the Wound option')
        return StaggerChoice.SUFFER_WOUND


def reserved(*, actor='pc1', enemies=1, armour=None, mount=CombatMount.DEMIGRYPH,
        declaration=None, combat_equipment=None):
    source = automatic_source(pc_count=1, enemy_count=enemies)
    rider = replace(source.party[0], pc=replace(source.party[0].pc, weapon_skill=6), mount=mount,
        rider_kind=RiderKind.HUMAN if mount is CombatMount.DEMIGRYPH else None)
    if combat_equipment is not None:
        primary = next(item for item in combat_equipment if item.location is PcItemLocation.HELD)
        rider = replace(rider, pc=replace(rider.pc, weapon=primary.weapon),
            initial_weapon_hand=primary.hand, combat_equipment=combat_equipment)
    if armour is not None:
        from towr.domain.armour_models import body_resilience_bonus, helmet_resilience_bonus, armour_is_worn
        rider = replace(rider, armour=armour, armour_worn=armour_is_worn(armour),
            agilulf_code_confirmed=True if BodyArmour.AGILULF in armour.body else None,
            pc=replace(rider.pc, armour_bonus=body_resilience_bonus(armour)+helmet_resilience_bonus(armour)))
    opposition = tuple(GeneratedNpc(4 if actor==old.state.actor_id else 3, 3, 20, 3, 4, 4, initial_generated_weapons(GeneratedWeapon.SWORD), ArmourLoadout(), defence=4,
        mount=CombatMount.DEMIGRYPH if actor == old.state.actor_id else None,
        rider_kind=RiderKind.HUMAN if actor == old.state.actor_id else None).participant(old.state.actor_id)
        for old in source.enemies)
    source = replace(source, party=(rider,), enemies=opposition,
        facts=replace(source.facts, unmounted=False, can_leave_zone=True),
        battlefield=PcBattlefieldSpec(RangedWeaponRange.CLOSE, RangedWeaponRange.LONG))
    if actor in source.pc_activation_order:
        state = tactical_snapshot(source, actor)
    else:
        state = initial_pc_melee_state(source)
        clock = replace(state.round_state, completed_turn_entity_ids=source.pc_activation_order)
        state = replace(state, round_state=start_combat_turn(CombatTurnStartRequest('pure:start', clock, actor)).state)
    declaration = declaration or CombatActionDeclaration(CombatActionKind.ATTACK)
    clock = reserve_combat_action_slot(CombatActionSlotRequest('pure:reserve', state.round_state,
        actor, declaration, ActionSlotGrant.STANDARD)).state
    return replace(state, round_state=clock)


def after_primary(state):
    intent = expected_pc_demigryph_intent(state)
    state = replace(state, history=(*state.history, intent))
    request, preparation = build_pc_melee_attack(state)
    execution = execute_attack_action(request, Ones(), decisions=KeepAllFailures())
    protection = prepare_protection(preparation)
    pc_actor = request.actor_id if request.actor_id in state.source.pc_activation_order else request.target_id
    test = request.kernel_request.attack.attacker_test if request.actor_id == pc_actor else request.kernel_request.attack.defender_test
    decline = PcFateDecline(pc_actor, test.id, 'test', state.source.participant(pc_actor).fate_policy)
    primary = PcAttackProof(request, protection, execution, decline,
        weapon_intent=build_pc_attack_weapon_intent(state))
    if request.target_id in state.source.enemy_activation_order:
        enemies = tuple(replace(enemy, state=replace(enemy.state, injury=execution.resolution.target_state))
            if enemy.state.actor_id == request.target_id else enemy for enemy in state.enemies)
        state = replace(state, enemies=enemies)
    else:
        state = replace(state, party=tuple(replace(member, injury=execution.resolution.target_state)
            if member.actor_id == request.target_id else member for member in state.party))
    return replace(state, round_state=execution.state, pending=execution.resolution.follow_ups,
        pending_wound=execution.resolution.pending_character_wound,
        pending_actor_id=(request.target_id if execution.resolution.follow_ups
            or execution.resolution.pending_character_wound is not None else None),
        history=(*state.history, primary)), intent, primary


class PcDemigryphTests(unittest.TestCase):
    def test_frozen_mount_protection_keeps_implements_but_uses_current_conditions(self):
        from towr.domain.pc_mount_attack_models import prepare_pc_mounted_attack
        from towr.domain.pc_weapon_inventory import pc_protection_weapon_use
        from towr.domain.test_models import Skill
        weapons = tuple(PcWeaponItem('sword:'+hand.value, PcMeleeWeapon.SWORD,
            PcItemLocation.HELD, hand) for hand in PcWeaponHand)
        state = reserved(actor='minion1', combat_equipment=weapons)
        intent = build_pc_explicit_attack_weapon_intent(state, 'minion1', 'pc1', 'mount:prepared',
            mount_attack=True)
        self.assertEqual(len(intent.protection_use.item_ids), 2)
        _, before = prepare_pc_mounted_attack(state, 'minion1', 'pc1', intent.action_id,
            weapon_intent=intent)
        member = state.participant('pc1')
        changed = replace(state, party=(replace(member, injury=replace(member.injury,
            conditions=member.injury.conditions.with_condition(Condition.STAGGERED))),))
        # This preparation snapshot separates choice from current modifiers;
        # it does not claim a journaled reaction that adds the defender's state.
        self.assertEqual(len(pc_protection_weapon_use(changed.participant('pc1'),
            Skill.DEFENCE, Skill.MELEE).item_ids), 1)
        _, after = prepare_pc_mounted_attack(changed, 'minion1', 'pc1', intent.action_id,
            weapon_intent=intent)
        self.assertEqual(sum(item.amount for item in before.options[0].test.dice_modifiers), 2)
        self.assertEqual(sum(item.amount for item in after.options[0].test.dice_modifiers), 0)
        self.assertEqual(len(intent.protection_use.item_ids), 2)

    def test_frozen_mount_attack_cannot_invent_protection_for_defenceless_target(self):
        from towr.domain.pc_mount_attack_models import prepare_pc_mounted_attack
        state = reserved(actor='minion1')
        member = state.participant('pc1')
        state = replace(state, party=(replace(member, injury=replace(member.injury,
            conditions=member.injury.conditions.with_condition(Condition.DEFENCELESS))),))
        intent = build_pc_explicit_attack_weapon_intent(state, 'minion1', 'pc1', 'mount:prepared',
            mount_attack=True)
        self.assertIsNone(intent.protection_skill)
        self.assertIsNone(intent.protection_use)
        kernel, protection = prepare_pc_mounted_attack(state, 'minion1', 'pc1', intent.action_id,
            weapon_intent=intent)
        self.assertIsNone(kernel.attack.defender_test)
        self.assertEqual(protection.options, ())
        self.assertEqual(kernel.target_state, state.participant('pc1').injury)

    def test_intent_commits_claws_grim_before_the_actual_primary_roll(self):
        state = reserved()
        intent = expected_pc_demigryph_intent(state)
        self.assertIs(type(intent), PcDemigryphIntentProof)
        self.assertIs(intent.grim_leg, DemigryphGrimLeg.CLAWS)
        self.assertEqual(demigryph_primary_qualities(intent), ())
        self.assertFalse(intent.source_round.active_turn.action_slots[0].executed)
        self.assertIsNone(expected_pc_demigryph_intent(replace(state, history=(intent,))))
        self.assertEqual(demigryph_primary_qualities(replace(intent, grim_leg=DemigryphGrimLeg.RIDER)),
            (QualityModifier(DEMIGRYPH_GRIM_RULE_ID, TestQuality.GRIM),))

    def test_horse_and_charge_do_not_grant_the_demigryph_pair(self):
        self.assertIsNone(expected_pc_demigryph_intent(reserved(mount=CombatMount.HORSE)))
        state = reserved(declaration=CombatActionDeclaration(CombatActionKind.MANOEUVRE,
            manoeuvre=ManoeuvreKind.CHARGE))
        self.assertIsNone(expected_pc_demigryph_intent(state))

    def test_claws_use_mount_abilities_and_keep_the_original_single_action_receipt(self):
        state, intent, primary = after_primary(reserved())
        strike, protection = build_pc_demigryph_strike(state)
        self.assertEqual(strike.parent_receipt, primary.execution.slot.execution)
        self.assertEqual(strike.source_round, state.round_state)
        self.assertEqual(len(strike.source_round.active_turn.action_slots), 1)
        self.assertEqual(strike.kernel_request.attack.attacker_test.profile, InlineProfile(4, 4, 8))
        self.assertEqual(strike.kernel_request.attack.impact_spec.damage.base, 5)
        self.assertEqual(strike.kernel_request.attack.attacker_test.quality_modifiers,
            (QualityModifier(DEMIGRYPH_GRIM_RULE_ID, TestQuality.GRIM),))
        self.assertEqual(strike.target_id, primary.request.target_id)
        self.assertEqual(protection.attack_skill.value, 'melee')
        self.assertEqual(current_pc_demigryph_intent(state), intent)

    def test_agilulf_five_and_rider_weapon_traits_do_not_replace_mount_profile(self):
        source = ArmourLoadout((BodyArmour.AGILULF,), BodyArmour.AGILULF)
        state, _, _ = after_primary(reserved(armour=source))
        strike, _ = build_pc_demigryph_strike(state)
        self.assertEqual(strike.kernel_request.attack.attacker_test.profile, InlineProfile(4, 4, 8))
        self.assertEqual(strike.kernel_request.attack.impact_spec.damage_modifiers, ())

    def test_first_pending_consequences_must_finish_and_actual_dismount_cancels_followup(self):
        state, _, _ = after_primary(reserved())
        self.assertIsNone(build_pc_demigryph_strike(replace(state,
            pending=(AttackerStaggerRequest('pending:before-claws'),), pending_actor_id='pc1')))
        member = state.participant('pc1')
        state = replace(state, party=(replace(member, injury=replace(member.injury,
            conditions=member.injury.conditions.with_condition(Condition.PRONE))),))
        dismount = expected_pc_dismount(state)
        state = replace(state, mounts=updated_pc_mounts(state, dismount), history=(*state.history, dismount))
        self.assertIsNone(build_pc_demigryph_strike(state))

    def test_other_living_close_target_is_selected_if_primary_has_been_defeated(self):
        state, _, primary = after_primary(reserved(enemies=2))
        state = replace(state, enemies=tuple(replace(enemy, state=replace(enemy.state,
            injury=replace(enemy.state.injury, wounds=1, defeated=True)))
            if enemy.state.actor_id == primary.request.target_id else enemy for enemy in state.enemies))
        strike, _ = build_pc_demigryph_strike(state)
        self.assertNotEqual(strike.target_id, primary.request.target_id)
        self.assertEqual(strike.target_id, 'minion2')

    def test_generated_rider_prepares_real_pc_defence_after_its_miss_stagger(self):
        state, _, _ = after_primary(reserved(actor='minion1'))
        self.assertTrue(state.pending)
        enemy = state.enemy('minion1')
        state = replace(state, enemies=(replace(enemy, state=replace(enemy.state,
            injury=replace(enemy.state.injury,
                conditions=enemy.state.injury.conditions.with_condition(Condition.STAGGERED)))),),
            pending=(), pending_actor_id=None)
        strike, protection = build_pc_demigryph_strike(state)
        self.assertEqual(strike.actor_id, 'minion1')
        self.assertEqual(strike.target_id, 'pc1')
        self.assertEqual(strike.kernel_request.target_policy.value, 'player')
        self.assertEqual(strike.kernel_request.attack.attacker_test.profile, InlineProfile(4, 4, 8))
        # C13: the rider's failed weapon Test did not Stagger the animal.
        self.assertFalse(strike.kernel_request.attack.attacker_is_staggered)
        self.assertEqual(protection.defender_id, 'pc1')
        self.assertEqual(protection.options[0].test.profile.characteristic, 6)

    def test_consumed_strike_cannot_repeat_and_followup_lookup_finds_real_kernel(self):
        state, _, primary = after_primary(reserved())
        strike, protection = build_pc_demigryph_strike(state)
        result = resolve_kernel_attack(strike.kernel_request, Ones(), decisions=TakeWound())
        weapon_intent = build_pc_explicit_attack_weapon_intent(state, strike.actor_id,
            strike.target_id, strike.id, mount_attack=True)
        proof = PcDemigryphStrikeProof(strike, prepare_protection(protection), result,
            weapon_intent=weapon_intent)
        for changed in (replace(weapon_intent, action_id='foreign'),
                replace(weapon_intent, mount_attack=False)):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                replace(proof, weapon_intent=changed)
        consumed = replace(state, history=(*state.history, proof))
        self.assertIsNone(build_pc_demigryph_strike(consumed))
        self.assertIs(latest_pc_kernel_attack(consumed), proof)
        self.assertEqual(pc_kernel_resolution(proof), result)
        self.assertIs(latest_pc_kernel_attack(consumed,
            kernel_request_id=primary.request.kernel_request.id), primary)
        with self.assertRaises(ValueError):
            latest_pc_kernel_attack(consumed, kernel_request_id='foreign')

    def test_another_receipt_actor_round_or_uncommitted_grim_shape_is_rejected(self):
        state, intent, primary = after_primary(reserved())
        strike, _ = build_pc_demigryph_strike(state)
        for receipt in (replace(strike.parent_receipt, actor_id='foreign'),
                replace(strike.parent_receipt, id='foreign'), replace(strike.parent_receipt, round_number=2)):
            with self.subTest(receipt=receipt), self.assertRaises(ValueError):
                replace(strike, parent_receipt=receipt)
        with self.assertRaises(TypeError):
            replace(intent, grim_leg='claws')
        detached = replace(state, history=(primary, intent))
        with self.assertRaises(ValueError):
            build_pc_demigryph_strike(detached)


if __name__ == '__main__':
    unittest.main()
