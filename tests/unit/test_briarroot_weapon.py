"""Finite physical abandonment/pickup, using actual Briarroot Attack sources."""
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.unit.test_pc_briarroot import Observation,actual_attack,react
from towr.domain.condition_models import Condition
from towr.domain.magic_models import WizardMagicState
from towr.domain.pc_battlefield_models import with_actor_placement,PcAirspaceSpec
from towr.domain.pc_mount_models import CombatMount
from towr.domain.pc_briarroot_weapon_models import (
    PcBriarrootWeaponGround,PcBriarrootDroppedWeapon,
    build_briarroot_weapon_drop,apply_briarroot_weapon_drop,
    briarroot_weapon_on_ground,can_pickup_briarroot_weapon,
    complete_briarroot_pc_pickup,briarroot_pc_pickup_updates,
    build_briarroot_weapon_pickup,complete_briarroot_weapon_pickup,apply_briarroot_weapon_pickup,
    expected_briarroot_weapon_approach,apply_briarroot_weapon_approach,
    validate_briarroot_dropped_weapons,
    _ground,
    expected_briarroot_weapon_loss,
)
from towr.domain.pc_combat_equipment_models import PcItemLocation
from towr.domain.pc_melee_result_models import PcRecoverProof,PcHandDropProof
from towr.domain.recover_models import (
    RecoverActionExecutionRequest,RecoverMode,RecoverObjectInteractionFollowUp,RecoverStandardChoice,
)
from towr.domain.turn_models import CombatActionDeclaration,CombatActionKind,CombatActionSlot,ActionSlotGrant
from towr.rules.recover_resolution import execute_recover_action
from towr.engine.pc_melee_runner import run_pc_melee_scenario


def turn(state,actor,*,recover=False):
    active=state.round_state.active_turn
    slots=(CombatActionSlot(1,CombatActionDeclaration(CombatActionKind.RECOVER),ActionSlotGrant.STANDARD),) if recover else ()
    return Observation(state,round_state=replace(state.round_state,
        active_turn=replace(active,actor_id=actor,action_slots=slots)),pending=(),pending_wound=None,magic_pending=None)


def bound_state(*,npc=False,spatial=True,mount=None,airspace=None):
    source,_=actual_attack(pc_bearer=npc,inventory=not npc,spatial=spatial,mount=mount,airspace=airspace)
    bound,_=react(source)
    actor='minion1' if npc else 'pc'
    return turn(Observation(bound,briarroot_dropped_weapons=()),actor),actor


def dropped_state(*,npc=False,spatial=True,mount=None):
    state,actor=bound_state(npc=npc,spatial=spatial,mount=mount)
    proof=build_briarroot_weapon_drop(state,actor)
    dropped=Observation(state,history=(*state.history,proof),**apply_briarroot_weapon_drop(state,proof))
    cleaned,_=react(dropped)
    return cleaned,proof


def pc_recover(state,weapon_id):
    state=turn(state,'pc',recover=True)
    request=RecoverActionExecutionRequest('physical:recover',state.round_state,'pc',
        state.participant('pc').injury.conditions,True,1,RecoverMode.STANDARD,
        RecoverStandardChoice(WizardMagicState(),object_interaction=
            RecoverObjectInteractionFollowUp('physical:object','pc',weapon_id,True)))
    return state,execute_recover_action(request,SequenceRandom(()))


class BriarrootPhysicalWeaponTests(unittest.TestCase):
    def test_drop_is_incidental_and_creates_one_frozen_physical_item(self):
        state,proof=dropped_state()
        item,=state.briarroot_dropped_weapons
        self.assertIs(state.participant('pc').weapon_inventory.active.location,PcItemLocation.DROPPED)
        self.assertIsNone(state.participant('pc').weapon_hand)
        self.assertEqual(state.round_state.active_turn.action_slots,())
        self.assertEqual(state.briarroot_bindings,())
        self.assertFalse(state.participant('pc').injury.conditions.has(Condition.BURDENED))
        marker=state.battlefield.spatial.placement_for(item.marker_id)
        self.assertEqual(marker.zone_id,item.ground.zone_id)
        self.assertTrue(can_pickup_briarroot_weapon(state,'pc',item.weapon_id))
        validate_briarroot_dropped_weapons(state)

    def test_source_item_and_ground_position_cannot_be_forged_or_duplicated(self):
        before,actor=bound_state()
        proof=build_briarroot_weapon_drop(before,actor)
        with self.assertRaises(ValueError):
            apply_briarroot_weapon_drop(before,replace(proof,weapon_id='invented'))
        with self.assertRaises((TypeError,ValueError)):
            apply_briarroot_weapon_drop(before,replace(proof,item=replace(proof.item,
                ground=replace(proof.item.ground,zone_id='invented'))))
        dropped=Observation(before,history=(*before.history,proof),**apply_briarroot_weapon_drop(before,proof))
        with self.assertRaises(ValueError):
            build_briarroot_weapon_drop(dropped,actor)
        with self.assertRaises(ValueError):
            validate_briarroot_dropped_weapons(Observation(dropped,
                briarroot_dropped_weapons=(*dropped.briarroot_dropped_weapons,*dropped.briarroot_dropped_weapons)))

    def test_moving_away_does_not_move_the_item_or_allow_teleport_pickup(self):
        state,_=dropped_state()
        item,=state.briarroot_dropped_weapons
        origin=item.ground.zone_id
        destination=state.battlefield.spatial.graph.adjacent_zone_ids(origin)[0]
        moved=Observation(state,battlefield=with_actor_placement(state.battlefield,'pc',destination,close_to_ids=()))
        self.assertEqual(briarroot_weapon_on_ground(moved,'pc').ground,item.ground)
        self.assertFalse(can_pickup_briarroot_weapon(moved,'pc',item.weapon_id))
        current,result=pc_recover(moved,item.weapon_id)
        with self.assertRaises(ValueError):
            complete_briarroot_pc_pickup(current,result)

    def test_actual_free_approach_returns_to_the_marker(self):
        state,_=dropped_state()
        item,=state.briarroot_dropped_weapons
        destination=state.battlefield.spatial.graph.adjacent_zone_ids(item.ground.zone_id)[0]
        moved=Observation(state,battlefield=with_actor_placement(state.battlefield,'pc',destination,close_to_ids=()))
        proof=expected_briarroot_weapon_approach(moved,'pc',item.weapon_id)
        self.assertIsNotNone(proof.request)
        self.assertIn('pc',proof.result.state.free_move_used_entity_ids)
        arrived=Observation(moved,history=(*moved.history,proof),**apply_briarroot_weapon_approach(moved,proof))
        self.assertTrue(can_pickup_briarroot_weapon(arrived,'pc',item.weapon_id))
        self.assertEqual(arrived.briarroot_dropped_weapons,state.briarroot_dropped_weapons)
        self.assertIsNone(expected_briarroot_weapon_approach(arrived,'pc',item.weapon_id))

    def test_short_within_the_same_zone_requires_a_real_approach(self):
        state,_=dropped_state()
        item,=state.briarroot_dropped_weapons
        moved=Observation(state,battlefield=with_actor_placement(state.battlefield,'pc',item.ground.zone_id,close_to_ids=()))
        self.assertFalse(can_pickup_briarroot_weapon(moved,'pc',item.weapon_id))
        proof=expected_briarroot_weapon_approach(moved,'pc',item.weapon_id)
        self.assertIsNone(proof.request)
        arrived=Observation(moved,**apply_briarroot_weapon_approach(moved,proof))
        self.assertTrue(can_pickup_briarroot_weapon(arrived,'pc',item.weapon_id))

    def test_fast_two_zone_approach_does_not_keep_stale_distant_close_pairs(self):
        state,_=dropped_state(mount=CombatMount.HORSE)
        item,=state.briarroot_dropped_weapons
        graph=state.battlefield.spatial.graph
        origin=item.ground.zone_id
        adjacent=next(zone for zone in graph.adjacent_zone_ids(origin)
            if zone not in dict(state.battlefield.air_to_ground))
        distant=next(zone for zone in graph.adjacent_zone_ids(adjacent)
            if zone!=origin and zone not in dict(state.battlefield.air_to_ground))
        battlefield=with_actor_placement(state.battlefield,'pc',distant,close_to_ids=())
        battlefield=with_actor_placement(battlefield,'minion1',distant,close_to_ids=('pc',))
        moved=Observation(state,battlefield=battlefield)
        proof=expected_briarroot_weapon_approach(moved,'pc',item.weapon_id)
        self.assertEqual(len(proof.request.traversed_zone_ids),2)
        arrived=Observation(moved,**apply_briarroot_weapon_approach(moved,proof))
        self.assertTrue(can_pickup_briarroot_weapon(arrived,'pc',item.weapon_id))

    def test_standard_pc_recover_has_one_atomic_pickup_receipt(self):
        state,_=dropped_state()
        item,=state.briarroot_dropped_weapons
        current,result=pc_recover(state,item.weapon_id)
        receipt=complete_briarroot_pc_pickup(current,result)
        self.assertEqual(receipt.previous_item,item)
        self.assertIsNone(receipt.item.ground)
        updates=briarroot_pc_pickup_updates(current,result,receipt)
        self.assertIsNone(updates['briarroot_dropped_weapons'][0].ground)
        self.assertFalse(any(placement.entity_id==item.marker_id for placement in updates['battlefield'].spatial.placements))
        with self.assertRaises(ValueError):
            briarroot_pc_pickup_updates(current,result,replace(receipt,action_id='another-action'))

    def test_npc_paid_standard_recover_restores_exact_pre_drop_attacks(self):
        state,drop=dropped_state(npc=True)
        item,=state.briarroot_dropped_weapons
        self.assertFalse(state.enemy('minion1').state.wields_weapon)
        self.assertEqual(state.enemy('minion1').state.available_attack_ids,())
        current=turn(state,'minion1',recover=True)
        request=build_briarroot_weapon_pickup(current,'minion1',item.weapon_id)
        result=execute_recover_action(request,SequenceRandom(()))
        proof=complete_briarroot_weapon_pickup(current,request,result,item.weapon_id)
        updates=apply_briarroot_weapon_pickup(current,proof)
        recovered=Observation(current,history=(*current.history,proof),**updates)
        self.assertTrue(recovered.enemy('minion1').state.wields_weapon)
        self.assertEqual(recovered.enemy('minion1').state.available_attack_ids,
            drop.previous_actor.state.available_attack_ids)
        self.assertTrue(recovered.round_state.active_turn.action_slots[0].executed)
        self.assertIsNone(recovered.briarroot_dropped_weapons[0].ground)
        self.assertNotIn('npc_ranged_weapons',updates)
        validate_briarroot_dropped_weapons(recovered)

    def test_another_actor_cannot_pick_up_this_source_weapon(self):
        state,_=dropped_state()
        item,=state.briarroot_dropped_weapons
        self.assertFalse(can_pickup_briarroot_weapon(state,'minion1',item.weapon_id))
        self.assertIsNone(briarroot_weapon_on_ground(state,'minion1',item.weapon_id))

    def test_finite_item_recovery_does_not_remove_its_source_receipt(self):
        state,proof=dropped_state()
        with self.assertRaises(ValueError):
            validate_briarroot_dropped_weapons(Observation(state,history=tuple(
                previous for previous in state.history if previous is not proof)))
        with self.assertRaises(ValueError):
            validate_briarroot_dropped_weapons(Observation(state,briarroot_dropped_weapons=()))

    def test_ground_and_item_facts_require_exact_source_types(self):
        with self.assertRaises(TypeError):
            PcBriarrootWeaponGround('zone',['actor'])
        with self.assertRaises(ValueError):
            PcBriarrootWeaponGround('zone',('actor','actor'))
        with self.assertRaises(TypeError):
            PcBriarrootDroppedWeapon('actor','weapon',{'zone_id':'zone'})

    def test_midair_drop_uses_the_explicit_ground_shadow_without_guessed_close_actors(self):
        state,_=bound_state(airspace=PcAirspaceSpec(2,True))
        origin=state.battlefield.spatial.placement_for('pc').zone_id
        air=next(air for air,ground in state.battlefield.air_to_ground if ground==origin)
        elevated=Observation(state,battlefield=with_actor_placement(state.battlefield,'pc',air,close_to_ids=()))
        position=_ground(elevated,'pc')
        self.assertEqual(position.zone_id,origin)
        self.assertEqual(position.initial_close_actor_ids,())

    def test_colons_in_actor_and_item_names_do_not_alias_physical_markers(self):
        first=PcBriarrootDroppedWeapon('actor:weapon','one',None)
        second=PcBriarrootDroppedWeapon('actor','weapon:one',None)
        self.assertNotEqual(first.marker_id,second.marker_id)

    def test_actual_wound_owned_drop_gets_a_physical_ack_before_binding_cleanup(self):
        state,_=actual_attack(inventory=True,spatial=True)
        result=run_pc_melee_scenario(state.source,
            SequenceRandom([10,10,10,1,1,1,1,10,10,10,8,1]))
        step=next(step for step in result.steps if type(step.proof) is PcHandDropProof)
        current=Observation(step.state,briarroot_dropped_weapons=())
        proof=expected_briarroot_weapon_loss(current)
        self.assertIsNotNone(proof)
        self.assertIs(proof.loss_witness,step.proof)
        self.assertEqual(proof.previous_actor,proof.actor)
        self.assertIsNone(proof.actor.weapon_hand)
        dropped=Observation(current,history=(*current.history,proof),**apply_briarroot_weapon_drop(current,proof))
        cleaned,_=react(dropped)
        self.assertEqual(len(cleaned.briarroot_dropped_weapons),1)
        self.assertIsNone(expected_briarroot_weapon_loss(cleaned))
        self.assertEqual(cleaned.briarroot_bindings,())
        validate_briarroot_dropped_weapons(cleaned)


if __name__=='__main__':
    unittest.main()
