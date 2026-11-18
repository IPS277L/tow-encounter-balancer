"""Ordinary Wound drops retain one finite item and pay for its real pickup."""
from tests.support.generated_weapon_sources import initial_generated_weapons
from dataclasses import replace
from random import Random
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_tactics_fixtures import automatic_source
from tests.integration.test_pc_falling_native import falling_source
from tests.unit.test_pc_briarroot import Observation
from towr.domain.attack_models import DamageProfile
from towr.domain.pc_battlefield_models import PcBattlefieldSpec, with_actor_placement, battlefield_is_midair
from towr.domain.pc_briarroot_weapon_models import (
    PcBriarrootWeaponDropProof, PcBriarrootWeaponApproachProof,
    can_pickup_pc_weapon, build_briarroot_weapon_drop, apply_briarroot_weapon_drop,
    build_briarroot_weapon_pickup, complete_briarroot_weapon_pickup, apply_briarroot_weapon_pickup,
)
from towr.domain.pc_combat_equipment_models import PcItemLocation, PcWeaponItem
from towr.domain.pc_melee_models import PcMeleeWeapon, PcWeaponHand
from towr.domain.pc_melee_result_models import (
    PcHandDropProof, PcMeleeStep, PcRecoverProof, initial_pc_melee_state,
)
from towr.domain.pc_weapon_inventory import pc_weapon_pickup_member, pc_weapon_pickup_view
from towr.domain.weapon_inventory_models import weapon_unit_id
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as R
from towr.domain.turn_models import (
    CombatActionKind, CombatTurnStartResult, CombatActionDeclaration, CombatActionSlotRequest, ActionSlotGrant,
)
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon
from towr.domain.armour_models import ArmourLoadout
from towr.rules.turn_resolution import reserve_combat_action_slot
from towr.rules.recover_resolution import execute_recover_action
from towr.engine.pc_melee_runner import run_pc_melee_scenario, apply_pc_melee_step


def sword_source(*, rounds=2):
    source = automatic_source(pc_count=1, enemy_count=1, rounds=rounds)
    member = replace(source.party[0], pc=replace(source.party[0].pc, weapon=PcMeleeWeapon.SWORD),
        initial_weapon_hand=PcWeaponHand.LEFT,
        combat_equipment=(PcWeaponItem('sword', PcMeleeWeapon.SWORD,
            PcItemLocation.HELD, PcWeaponHand.LEFT),))
    enemy = source.enemies[0]
    enemy = replace(enemy, definition=replace(enemy.definition,
        attacks=(replace(enemy.definition.attacks[0], damage=DamageProfile(50)),)))
    return replace(source, party=(member,), enemies=(enemy,),
        facts=replace(source.facts, can_leave_zone=True),
        battlefield=PcBattlefieldSpec(R.CLOSE, R.LONG))


class OrdinaryWeaponGroundIntegrationTests(unittest.TestCase):
    def test_actual_wound_eight_drop_then_paid_recover_and_full_replay(self):
        source = sword_source()
        rng = ScriptedD10([10,10,10,1,1,1,1,10,10,10,8,1] + [1,1,10,10,10,10,1,1])
        result = run_pc_melee_scenario(source, rng)
        self.assertIsNone(result.unsupported)
        rng.assert_exhausted()
        drop, = [step for step in result.steps if type(step.proof) is PcBriarrootWeaponDropProof]
        recover, = [step for step in result.steps if type(step.proof) is PcRecoverProof]
        self.assertEqual(drop.proof.binding_ids, ())
        self.assertIs(type(drop.proof.loss_witness), PcHandDropProof)
        self.assertEqual(result.steps[drop.proof.loss_witness_history_index].proof, drop.proof.loss_witness)
        self.assertEqual(drop.source.round_state, drop.state.round_state)
        item, = drop.state.briarroot_dropped_weapons
        self.assertEqual(item.weapon_id, weapon_unit_id('pc1', 'sword', 0))
        self.assertIs(drop.state.participant('pc1').weapon_inventory.active.location, PcItemLocation.DROPPED)
        self.assertTrue(can_pickup_pc_weapon(drop.state, 'pc1', item.weapon_id))
        receipt = recover.proof.briarroot_weapon_pickup
        self.assertEqual(receipt.previous_item, item)
        self.assertTrue(recover.proof.result.slot.executed)
        self.assertIs(recover.proof.result.slot.declaration.kind, CombatActionKind.RECOVER)
        self.assertIsNone(recover.state.briarroot_dropped_weapons[0].ground)
        self.assertIs(recover.state.participant('pc1').weapon_inventory.active.location, PcItemLocation.HELD)
        self.assertFalse(any(placement.entity_id == item.marker_id
            for placement in recover.state.battlefield.spatial.placements))
        replay = initial_pc_melee_state(source)
        for step in result.steps:
            replay = apply_pc_melee_step(replay, step)
        self.assertEqual(replay, result.state)
        with self.assertRaises(ValueError):
            PcMeleeStep(drop.state, drop.proof)
        with self.assertRaises(ValueError):
            PcMeleeStep(recover.source, replace(recover.proof, briarroot_weapon_pickup=None))

    def test_airborne_ordinary_bow_drop_descends_before_actual_paid_pickup(self):
        source = replace(falling_source(), max_rounds=2)
        rng = ScriptedD10([10,10]+[1]*6+[10,8,1]+[1]*3)
        result = run_pc_melee_scenario(source, rng)
        self.assertIsNone(result.unsupported)
        rng.assert_exhausted()
        drop, = [step for step in result.steps if type(step.proof) is PcBriarrootWeaponDropProof]
        item = drop.proof.item
        self.assertEqual(drop.proof.binding_ids, ())
        self.assertTrue(battlefield_is_midair(drop.state.battlefield, 'pc1'))
        self.assertFalse(battlefield_is_midair(drop.state.battlefield, item.marker_id))
        self.assertEqual(item.ground.initial_close_actor_ids, ())
        self.assertEqual(item.weapon_id, weapon_unit_id('pc1', 'bow', 0))
        self.assertFalse(can_pickup_pc_weapon(drop.state, 'pc1', item.weapon_id))
        self.assertIsNone(pc_weapon_pickup_member(drop.state, 'pc1', item.weapon_id))
        self.assertIsNone(pc_weapon_pickup_view(drop.state, 'pc1', item.weapon_id))
        approach, = [step for step in result.steps if type(step.proof) is PcBriarrootWeaponApproachProof]
        recover, = [step for step in result.steps if type(step.proof) is PcRecoverProof]
        self.assertEqual(approach.source.round_state, approach.state.round_state)
        self.assertFalse(battlefield_is_midair(approach.state.battlefield, 'pc1'))
        self.assertIn('pc1', approach.state.battlefield.spatial.free_move_used_entity_ids)
        self.assertEqual(approach.state.battlefield.air_to_ground, drop.state.battlefield.air_to_ground)
        self.assertLess(result.steps.index(drop), result.steps.index(approach))
        self.assertLess(result.steps.index(approach), result.steps.index(recover))
        self.assertEqual(recover.proof.briarroot_weapon_pickup.previous_item, item)
        self.assertTrue(recover.proof.result.slot.executed)

    def test_distant_and_missing_physical_markers_cannot_authorize_spatial_pickup(self):
        source = sword_source(rounds=1)
        rng = ScriptedD10([10,10,10,1,1,1,1,10,10,10,8,1])
        result = run_pc_melee_scenario(source, rng)
        rng.assert_exhausted()
        drop, = [step for step in result.steps if type(step.proof) is PcBriarrootWeaponDropProof]
        item = drop.proof.item
        moved = Observation(drop.state, battlefield=with_actor_placement(
            drop.state.battlefield, 'pc1', 'arena:zone:2'))
        self.assertEqual(moved.briarroot_dropped_weapons[0].ground, item.ground)
        self.assertFalse(can_pickup_pc_weapon(moved, 'pc1', item.weapon_id))
        self.assertIsNone(pc_weapon_pickup_member(moved, 'pc1', item.weapon_id))
        missing = Observation(drop.source, briarroot_dropped_weapons=())
        self.assertFalse(can_pickup_pc_weapon(missing, 'pc1', item.weapon_id))
        self.assertIsNone(pc_weapon_pickup_member(missing, 'pc1', item.weapon_id))

    def test_ordinary_voluntary_drop_has_no_binding_requirement_or_extra_action(self):
        # The existing finite owner also admits a future equipment controller's
        # explicit voluntary drop. Its typed full before/after source is kept.
        source = sword_source(rounds=1)
        from tests.support.pc_tactics_fixtures import tactical_snapshot
        state = tactical_snapshot(source)
        item_id = weapon_unit_id('pc1', 'sword', 0)
        proof = build_briarroot_weapon_drop(state, 'pc1', item_id)
        updates = apply_briarroot_weapon_drop(state, proof)
        self.assertEqual(proof.binding_ids, ())
        self.assertIsNone(proof.loss_witness)
        self.assertEqual(state.round_state.active_turn.action_slots, ())
        self.assertIs(updates['party'][0].weapon_inventory.active.location, PcItemLocation.DROPPED)
        self.assertEqual(updates['briarroot_dropped_weapons'][0].weapon_id, item_id)
        with self.assertRaises(ValueError):
            build_briarroot_weapon_drop(state, 'pc1', 'invented')

    def test_generated_npc_ordinary_drop_owner_recovers_exact_same_source_attacks(self):
        source = sword_source(rounds=1)
        npc = GeneratedNpc(3, 3, 20, 3, 4, 4, initial_generated_weapons(GeneratedWeapon.STAFF), ArmourLoadout(), defence=4)
        source = replace(source, enemies=(npc.participant('minion1'),))
        native = run_pc_melee_scenario(source, Random(4))
        # Begin at an actually admitted NPC turn. The future equip controller
        # will supply its frozen voluntary intent to the same finite owner.
        before = next(step.state for step in native.steps
            if type(step.proof) is CombatTurnStartResult
                and step.proof.state.active_turn.actor_id == 'minion1')
        drop = build_briarroot_weapon_drop(before, 'minion1')
        self.assertEqual(drop.binding_ids, ())
        state = Observation(before, history=(*before.history, drop), **apply_briarroot_weapon_drop(before, drop))
        self.assertEqual(state.enemy('minion1').state.available_attack_ids, ())
        self.assertFalse(state.enemy('minion1').state.wields_weapon)
        self.assertEqual(state.round_state, before.round_state)
        clock = reserve_combat_action_slot(CombatActionSlotRequest('ordinary:npc:reserve',
            state.round_state, 'minion1', CombatActionDeclaration(CombatActionKind.RECOVER),
            ActionSlotGrant.STANDARD)).state
        state = Observation(state, round_state=clock)
        request = build_briarroot_weapon_pickup(state, 'minion1', drop.weapon_id)
        result = execute_recover_action(request, ScriptedD10([]))
        receipt = complete_briarroot_weapon_pickup(state, request, result, drop.weapon_id)
        updates = apply_briarroot_weapon_pickup(state, receipt)
        enemy, = updates['enemies']
        self.assertEqual(enemy.definition, before.enemy('minion1').definition)
        self.assertEqual(enemy.state.available_attack_ids, before.enemy('minion1').state.available_attack_ids)
        self.assertTrue(enemy.state.wields_weapon)
        self.assertTrue(result.slot.executed)


if __name__ == '__main__':
    unittest.main()
