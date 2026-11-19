"""Finite PC Shield positions and actual geometry of their paid recovery."""
from dataclasses import replace
from random import Random
import unittest

from tests.support.pc_pistol_scenarios import make_pc_pistol_scenario
from tests.support.pc_shield_scenarios import shield_loadout
from tests.support.pc_tactics_fixtures import automatic_source
from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_pc_flight import preparation_view
from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.pc_ally_recover_models import expected_pc_standard_recover, pc_after_standard_recover
from towr.domain.pc_battlefield_models import (
    PcAirspaceSpec, PcBattlefieldSpec, with_actor_placement, battlefield_is_midair,
)
from towr.domain.pc_combat_equipment_models import PcItemLocation, PcWeaponItem
from towr.domain.pc_melee_models import PcMeleePolicy, PcMeleeWeapon, PcWeaponHand, PcShortRangeOpening
from towr.domain.pc_melee_result_models import (
    PcMeleeStep, PcRecoverProof, PcHandDropProof, build_pc_melee_recover, initial_pc_melee_state,
)
from towr.domain.pc_mount_models import CombatMount, RiderKind
from towr.domain.pc_shield_models import (
    PcShieldState, PcShieldLocation, PcShieldReleaseProof, PcShieldDropProof,
    PcShieldApproachProof, expected_pc_shield_drop, expected_pc_shield_approach,
    pc_shield_recover_hand, complete_pc_shield_pickup, pc_shield_pickup_updates,
    _shield_ground, _add_shield_marker,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as R
from towr.domain.recover_models import RecoverObjectInteractionFollowUp
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind,
    CombatActionSlotRequest,
)
from towr.rules.turn_resolution import reserve_combat_action_slot
from towr.engine.pc_melee_runner import run_pc_melee_scenario


def shield_view(*, airborne=True):
    """Explicit preparation geometry; this is not an invented native journal."""
    original = automatic_source(pc_count=1, enemy_count=1, rounds=1)
    member = replace(original.party[0], shield=shield_loadout(PcWeaponHand.RIGHT),
        pc=replace(original.party[0].pc, weapon=PcMeleeWeapon.SWORD),
        initial_weapon_hand=PcWeaponHand.LEFT, mount=CombatMount.PEGASUS, rider_kind=RiderKind.HUMAN)
    original = replace(original, party=(member,),
        facts=replace(original.facts, all_opponents_close=False, can_leave_zone=True, unmounted=False),
        battlefield=PcBattlefieldSpec(R.SHORT, R.LONG, airspace=PcAirspaceSpec()))
    state = preparation_view(original)
    if airborne:
        ground = state.battlefield.spatial.placement_for('pc1').zone_id
        air = next(air for air, below in state.battlefield.air_to_ground if below == ground)
        state.battlefield = with_actor_placement(state.battlefield, 'pc1', air)
    shield = PcShieldState(PcShieldLocation.DROPPED, None, ground=_shield_ground(state, 'pc1'))
    state.party = (replace(state.party[0], shield=shield),)
    state.battlefield = _add_shield_marker(state.battlefield, 'pc1', shield)
    return state


def reserve_recover(state):
    state.round_state = reserve_combat_action_slot(CombatActionSlotRequest('shield:reserve',
        state.round_state, 'pc1', CombatActionDeclaration(CombatActionKind.RECOVER),
        ActionSlotGrant.STANDARD)).state


def actual_pistol_shield_source():
    source = make_pc_pistol_scenario(max_rounds=6, initiative=6, dexterity=6)
    member = replace(source.party[0], policy=PcMeleePolicy.AUTOMATIC_COMBAT,
        shield=shield_loadout(PcWeaponHand.RIGHT), pc=replace(source.party[0].pc, toughness=20),
        combat_equipment=(PcWeaponItem('pistol', PcMeleeWeapon.PISTOL,
            PcItemLocation.HELD, PcWeaponHand.LEFT,initially_loaded=True),))
    enemy = source.enemies[0]
    resilience = ResilienceProfile(20)
    enemy = replace(enemy, definition=replace(enemy.definition, resilience=resilience),
        state=replace(enemy.state, current_resilience=resilience))
    return replace(source, party=(member,), enemies=(enemy,),
        facts=replace(source.facts, can_leave_zone=True),
        battlefield=PcBattlefieldSpec(R.CLOSE, R.LONG))


class PcShieldGroundTests(unittest.TestCase):
    def test_stationary_short_opening_keeps_own_dropped_shield_close(self):
        source = actual_pistol_shield_source()
        source = replace(source, battlefield=None,
            party=(replace(source.party[0], policy=PcMeleePolicy.ATTACK_OR_RECOVER_SELF),),
            short_range_opening=PcShortRangeOpening(True, True),
            facts=replace(source.facts, all_opponents_close=False,
                can_leave_zone=False))
        result = run_pc_melee_scenario(source, Random(42))
        self.assertIsNone(result.unsupported)
        pickups = [step for step in result.steps
            if type(step.proof) is PcRecoverProof and step.proof.pc_shield_pickup is not None]
        self.assertTrue(pickups)
        for step in pickups:
            self.assertIsNone(step.source.battlefield)
            self.assertEqual(step.proof.result.source_request.choice.object_interaction.object_id,
                'pc1:shield')
            self.assertTrue(step.proof.result.slot.executed)
            self.assertIs(step.state.participant('pc1').shield.location, PcShieldLocation.HELD)

    def test_actual_wound_hand_drop_grounds_the_shield_before_continuation(self):
        source = automatic_source(pc_count=1, enemy_count=1, rounds=1)
        member = replace(source.party[0], shield=shield_loadout(PcWeaponHand.RIGHT),
            pc=replace(source.party[0].pc, weapon=PcMeleeWeapon.SWORD),
            initial_weapon_hand=PcWeaponHand.LEFT)
        enemy = source.enemies[0]
        enemy = replace(enemy, definition=replace(enemy.definition,
            attacks=(replace(enemy.definition.attacks[0], damage=DamageProfile(50)),)))
        source = replace(source, party=(member,), enemies=(enemy,),
            facts=replace(source.facts, can_leave_zone=True),
            battlefield=PcBattlefieldSpec(R.CLOSE, R.LONG))
        rng = ScriptedD10([10,10,10,1,1,1,1,10,10,10,8,10])
        result = run_pc_melee_scenario(source, rng)
        rng.assert_exhausted()
        self.assertIsNone(result.unsupported)
        drop, = [step for step in result.steps if type(step.proof) is PcShieldDropProof]
        self.assertIs(type(drop.proof.loss_witness), PcHandDropProof)
        self.assertIs(drop.proof.loss_witness.hand, PcWeaponHand.RIGHT)
        self.assertEqual(drop.source.round_state, drop.state.round_state)
        self.assertEqual(drop.state.battlefield.spatial.placement_for('pc1:shield:ground').zone_id,
            drop.source.battlefield.spatial.placement_for('pc1').zone_id)
        self.assertIs(result.state.participant('pc1').shield.location, PcShieldLocation.DROPPED)

    def test_air_drop_lands_below_and_cannot_be_recovered_from_the_air(self):
        state = shield_view()
        shield = state.participant('pc1').shield
        self.assertEqual(shield.ground.initial_close_actor_ids, ())
        self.assertFalse(battlefield_is_midair(state.battlefield, 'pc1:shield:ground'))
        self.assertTrue(battlefield_is_midair(state.battlefield, 'pc1'))
        self.assertIsNone(pc_shield_recover_hand(state.participant('pc1'), state=state))
        reserve_recover(state)
        request = build_pc_melee_recover(state)
        self.assertIsNone(request.choice.object_interaction)
        forged = replace(request, choice=replace(request.choice,
            object_interaction=RecoverObjectInteractionFollowUp('forged', 'pc1', 'pc1:shield', True)))
        result = expected_pc_standard_recover(forged)
        with self.assertRaises(ValueError):
            complete_pc_shield_pickup(state, result)
        with self.assertRaises(ValueError):
            pc_after_standard_recover(state, forged, result)

    def test_actual_approach_descends_before_paid_standard_recover_pickup(self):
        state = shield_view()
        original_clock = state.round_state
        original_map = state.battlefield.air_to_ground
        approach = expected_pc_shield_approach(state)
        self.assertIs(type(approach), PcShieldApproachProof)
        self.assertEqual(approach.movement_request.traversed_zone_ids,
            (state.participant('pc1').shield.ground.zone_id,))
        state.battlefield = approach.state
        state.history = (*state.history, approach)
        self.assertEqual(state.round_state, original_clock)
        self.assertIn('pc1', state.battlefield.spatial.free_move_used_entity_ids)
        self.assertEqual(state.battlefield.air_to_ground, original_map)
        self.assertIs(pc_shield_recover_hand(state.participant('pc1'), state=state), PcWeaponHand.RIGHT)
        reserve_recover(state)
        request = build_pc_melee_recover(state)
        self.assertEqual(request.choice.object_interaction.object_id, 'pc1:shield')
        result = expected_pc_standard_recover(request)
        pickup = complete_pc_shield_pickup(state, result)
        updates = pc_shield_pickup_updates(state, result, pickup)
        self.assertTrue(result.slot.executed)
        self.assertIs(result.slot.declaration.kind, CombatActionKind.RECOVER)
        self.assertFalse(any(item.entity_id == 'pc1:shield:ground'
            for item in updates['battlefield'].spatial.placements))
        self.assertEqual(updates['battlefield'].air_to_ground, original_map)
        self.assertIsNone(pc_after_standard_recover(state, request, result)[0].shield.ground)

    def test_frozen_shield_position_does_not_follow_the_owner(self):
        state = shield_view(airborne=False)
        ground = state.participant('pc1').shield.ground
        self.assertIs(pc_shield_recover_hand(state.participant('pc1'), state=state), PcWeaponHand.RIGHT)
        state.battlefield = with_actor_placement(state.battlefield, 'pc1', 'arena:zone:2')
        self.assertEqual(state.participant('pc1').shield.ground, ground)
        self.assertEqual(state.battlefield.spatial.placement_for('pc1:shield:ground').zone_id, ground.zone_id)
        self.assertIsNone(pc_shield_recover_hand(state.participant('pc1'), state=state))

    def test_unavailable_shield_is_attached_and_never_becomes_a_ground_pickup(self):
        state = shield_view()
        # Remove only the preparation marker; an attached unavailable item
        # retains its original hand and has no physical ground state.
        from towr.domain.pc_shield_models import _remove_shield_marker
        state.battlefield = _remove_shield_marker(state.battlefield, 'pc1')
        state.party = (replace(state.party[0], shield=PcShieldState(
            PcShieldLocation.UNAVAILABLE, PcWeaponHand.RIGHT)),)
        self.assertIsNone(expected_pc_shield_drop(state))
        self.assertIsNone(expected_pc_shield_approach(state))
        self.assertIsNone(pc_shield_recover_hand(state.participant('pc1'), state=state))

    def test_real_reload_drop_and_paid_pickup_preserve_one_source_item(self):
        source = actual_pistol_shield_source()
        result = run_pc_melee_scenario(source, Random(42))
        self.assertIsNone(result.unsupported)
        drops = [(index, step) for index, step in enumerate(result.steps)
            if type(step.proof) is PcShieldDropProof]
        pickups = [(index, step) for index, step in enumerate(result.steps)
            if type(step.proof) is PcRecoverProof and step.proof.pc_shield_pickup is not None]
        self.assertTrue(drops)
        self.assertTrue(pickups)
        drop_index, drop = drops[0]
        pickup_index, pickup = pickups[0]
        self.assertLess(drop_index, pickup_index)
        self.assertIs(type(drop.proof.loss_witness), PcShieldReleaseProof)
        self.assertEqual(result.steps[drop.proof.loss_witness_history_index].proof, drop.proof.loss_witness)
        self.assertEqual(drop.source.round_state, drop.state.round_state)
        self.assertEqual(drop.proof.shield.ground, pickup.proof.pc_shield_pickup.previous_shield.ground)
        self.assertEqual(pickup.proof.result.source_request.choice.object_interaction.object_id, 'pc1:shield')
        self.assertTrue(pickup.proof.result.slot.executed)
        self.assertIs(pickup.proof.result.slot.declaration.kind, CombatActionKind.RECOVER)
        with self.assertRaises(ValueError):
            PcMeleeStep(drop.state, drop.proof)
        with self.assertRaises(ValueError):
            PcMeleeStep(pickup.state, pickup.proof)
        forged = replace(pickup.proof, pc_shield_pickup=None)
        with self.assertRaises(ValueError):
            PcMeleeStep(pickup.source, forged)
        # A new source cannot start with a ground Shield fabricated from an
        # unrelated journal; it must begin with the authored held item.
        initial = initial_pc_melee_state(source)
        with self.assertRaises(ValueError):
            replace(initial, party=(replace(initial.party[0], shield=drop.proof.shield),))


if __name__ == '__main__':
    unittest.main()
