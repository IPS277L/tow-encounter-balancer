"""Per-item generated NPC Shield and ground-weapon owners with real Recover."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from towr.domain.armour_models import ArmourLoadout,ShieldKind
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedRangedFacts,generated_initial_weapon_inventory
from towr.domain.injury_models import CharacterInjuryState
from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
from towr.domain.pc_npc_shield_models import (
    NpcShieldLocation,NpcShieldGroundPosition,PcNpcShieldDropProof,
    initial_npc_shields,expected_npc_shield_drop,npc_shield_drop_updates,
    build_npc_shield_pickup,complete_npc_shield_pickup,npc_shield_pickup_updates,
    validate_npc_shields,_with_shield,
)
from towr.domain.pc_briarroot_weapon_models import (
    build_briarroot_weapon_drop,apply_briarroot_weapon_drop,
    can_pickup_briarroot_weapon,build_briarroot_weapon_pickup,
    complete_briarroot_weapon_pickup,apply_briarroot_weapon_pickup,
    validate_briarroot_dropped_weapons,_is_dropped,
)
from towr.domain.turn_models import (
    CombatRoundState,CombatTurnParticipant,CombatTurnState,CombatSide,
    ActionSlotGrant,CombatActionDeclaration,CombatActionKind,CombatActionSlotRequest,
)
from towr.domain.weapon_catalog import WeaponKind as W
from towr.domain.weapon_inventory_models import WeaponItemSource,WeaponItemLocation as L,WeaponGrip as G,WeaponUnitState
from towr.rules.turn_resolution import reserve_combat_action_slot
from towr.rules.recover_resolution import execute_recover_action


class NoDice:
    def randint(self,low,high):raise AssertionError('standard physical Recover has no dice')


def item(kind=W.SWORD,*,id='weapon',location=L.HELD,grip=G.LEFT,loaded=None):
    return WeaponItemSource(id,kind,location,grip,initially_loaded=loaded)


def view(items,*,shield=False,ranged=None):
    components=GeneratedNpc(3,3,3,3,4,4,items,
        ArmourLoadout(shield=ShieldKind.SHIELD if shield else None),defence=4,ranged=ranged)
    original=components.participant('enemy')
    enemy=replace(original,state=replace(original.state,
        weapon_inventory=generated_initial_weapon_inventory(components,'enemy')))
    source=SimpleNamespace(id='physical-fixture',enemies=(original,),pc_activation_order=('pc',),
        enemy_activation_order=('enemy',),enemy_target_priority=('pc',),
        npc_ranged_policies=(pc_npc_ranged_policy_for_generated(components,'enemy'),) if ranged else (),
        facts=SimpleNamespace(zone_id='arena',all_opponents_close=True),enemy=lambda actor:original)
    clock=CombatRoundState(1,(CombatTurnParticipant('pc',CombatSide.PLAYERS_AND_ALLIES),
        CombatTurnParticipant('enemy',CombatSide.OPPOSITION)),completed_turn_entity_ids=('pc',),
        active_turn=CombatTurnState('enemy',CombatSide.OPPOSITION))
    state=SimpleNamespace(source=source,enemies=(enemy,),round_state=clock,
        participant=lambda actor:SimpleNamespace(injury=CharacterInjuryState()),
        live_party=(SimpleNamespace(actor_id='pc',injury=CharacterInjuryState()),),
        pending=(),pending_wound=None,magic_pending=None,exited_npc_ids=(),history=(),
        battlefield=None,npc_shields=initial_npc_shields(source),briarroot_dropped_weapons=(),briarroot_bindings=())
    state.enemy=lambda actor:next(enemy for enemy in state.enemies if enemy.state.actor_id==actor)
    return state


def updates(state,changes,proof):
    for key,value in changes.items():setattr(state,key,value)
    state.history=(*state.history,proof)
    return state


def reserve_recover(state):
    state.round_state=reserve_combat_action_slot(CombatActionSlotRequest('reserve:recover',state.round_state,
        'enemy',CombatActionDeclaration(CombatActionKind.RECOVER),ActionSlotGrant.STANDARD)).state
    return state


def drop_shield(state,weapon):
    with patch('towr.domain.pc_npc_weapon_inventory.npc_shield_release_weapon',return_value=weapon):
        proof=expected_npc_shield_drop(state)
        changes=npc_shield_drop_updates(state,proof)
    updates(state,changes,proof)
    return proof


class GeneratedInventoryPhysicalTests(unittest.TestCase):
    def test_carrying_after_drop_is_removed_without_erasing_a_different_binding(self):
        from towr.domain.condition_models import Condition
        from towr.domain.pc_briarroot_models import PcBriarrootBinding
        from towr.domain.pc_inventory_conditions import reconcile_npc_inventory_burden
        for bound in (False,True):
            with self.subTest(bound=bound):
                state=view((item(id='sword'),item(W.DAGGER,id='offhand',grip=G.RIGHT),
                    item(W.STAFF,id='spare-1',location=L.CARRIED,grip=None),
                    item(W.STAFF,id='spare-2',location=L.CARRIED,grip=None)))
                enemy=state.enemy('enemy')
                enemy=replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
                    conditions=enemy.state.injury.conditions.with_condition(Condition.BURDENED))))
                state.enemies=(enemy,);state.weighted_nets=();state.magic_modifiers=()
                if bound:
                    state.briarroot_bindings=(PcBriarrootBinding('binding','pc','enemy',
                        enemy.state.weapon_inventory.items[0].id,'attack',0),)
                unit=enemy.state.weapon_inventory.items[1]
                proof=build_briarroot_weapon_drop(state,'enemy',unit.id)
                changed=reconcile_npc_inventory_burden(state,proof.actor)
                self.assertEqual(changed.state.injury.conditions.has(Condition.BURDENED),bound)
                self.assertEqual(changed.state.weapon_inventory.item(unit.id).location,L.DROPPED)

    def test_natural_mount_binding_is_not_an_inventory_stow_restriction(self):
        from towr.domain.pc_briarroot_models import PcBriarrootBinding,BriarrootWeaponKind
        from towr.domain.pc_npc_weapon_inventory import _plan
        state=view((item(id='sword'),item(W.HALBERD,id='carried',location=L.CARRIED,grip=None)))
        binding=PcBriarrootBinding('binding','pc','enemy','mount-claws','attack',0,
            kind=BriarrootWeaponKind.MOUNT_NATURAL)
        state.briarroot_bindings=(binding,)
        target=state.enemy('enemy').state.weapon_inventory.items[1]
        plan=_plan(state,'enemy',target,G.BOTH)
        self.assertEqual(plan.after.active.source_item_id,'carried')
        self.assertEqual(plan.after.active.grip,G.BOTH)
        state.briarroot_bindings=(replace(binding,weapon_id=state.enemy('enemy').state.weapon_inventory.active.id,
            kind=BriarrootWeaponKind.HELD),)
        with self.assertRaises(ValueError):_plan(state,'enemy',target,G.BOTH)

    def test_held_briarroot_binding_follows_its_unit_when_another_weapon_is_selected(self):
        from towr.domain.pc_briarroot_models import PcBriarrootBinding,_weapon_released
        state=view((item(id='left'),item(id='right',grip=G.RIGHT)))
        enemy=state.enemy('enemy');inventory=enemy.state.weapon_inventory
        bound,other=inventory.items
        state.enemies=(replace(enemy,state=replace(enemy.state,
            weapon_inventory=replace(inventory,active_item_id=other.id))),)
        binding=PcBriarrootBinding('binding','pc','enemy',bound.id,'attack',0)
        self.assertFalse(_weapon_released(state,binding))
        inventory=state.enemy('enemy').state.weapon_inventory
        state.enemies=(replace(enemy,state=replace(enemy.state,
            weapon_inventory=inventory.with_item(replace(bound,location=L.DROPPED,grip=None)))),)
        self.assertTrue(_weapon_released(state,binding))

    def test_melee_source_shield_bank_has_the_actual_free_hand(self):
        for grip,shield_hand in ((G.LEFT,G.RIGHT),(G.RIGHT,G.LEFT)):
            state=view((item(grip=grip),),shield=True)
            self.assertEqual(len(state.npc_shields),1)
            self.assertIs(state.enemy('enemy').state.weapon_inventory.shield_hand,shield_hand)
            validate_npc_shields(state)

    def test_weapon_first_shield_release_keeps_actual_carried_two_hand_witness(self):
        state=view((item(),item(W.GLAIVE,id='back',location=L.CARRIED,grip=None)),shield=True)
        before=state.enemy('enemy')
        carried=before.state.weapon_inventory.items[1]
        proof=drop_shield(state,carried)
        self.assertIs(type(proof.weapon),WeaponUnitState)
        self.assertEqual(proof.weapon,carried)
        self.assertEqual(proof.enemy.state.weapon_inventory.items,before.state.weapon_inventory.items)
        self.assertIsNone(proof.enemy.state.weapon_inventory.shield_hand)
        self.assertEqual(proof.enemy.state.current_resilience.bonus,before.state.current_resilience.bonus-1)
        validate_npc_shields(state)
        with self.assertRaises(ValueError):replace(proof,weapon=before.state.weapon_inventory.active)
        foreign=generated_initial_weapon_inventory(before.definition.generated_components,'foreign').items[1]
        with self.assertRaises(ValueError):replace(proof,weapon=foreign)

    def test_melee_shield_pickup_is_one_paid_recover_without_inventing_reload(self):
        state=view((item(),item(W.GLAIVE,id='back',location=L.CARRIED,grip=None)),shield=True)
        drop_shield(state,state.enemy('enemy').state.weapon_inventory.items[1])
        reserve_recover(state)
        before=state.enemy('enemy')
        request=build_npc_shield_pickup(state)
        self.assertIsNotNone(request)
        result=execute_recover_action(request,NoDice())
        proof=complete_npc_shield_pickup(state,request,result)
        self.assertIs(type(proof.weapon),WeaponUnitState)
        self.assertIsNone(proof.weapon.reload)
        self.assertTrue(result.round_state.active_turn.action_slots[0].executed)
        self.assertEqual(proof.enemy.state.weapon_inventory.items,before.state.weapon_inventory.items)
        updates(state,npc_shield_pickup_updates(state,proof),proof)
        self.assertIs(state.npc_shields[0].location,NpcShieldLocation.HELD)
        validate_npc_shields(state)
        with self.assertRaises(ValueError):npc_shield_pickup_updates(state,proof)

    def test_exacting_shield_pickup_retains_genuine_loaded_k1_instead_of_a_unit_bypass(self):
        from towr.domain.reload_models import ReloadableWeaponState
        facts=GeneratedRangedFacts(3,4,3,4,True,True,True)
        state=view((item(W.PISTOL,loaded=True),
            item(W.GLAIVE,id='back',location=L.CARRIED,grip=None)),shield=True,ranged=facts)
        drop_shield(state,state.enemy('enemy').state.weapon_inventory.items[1])
        reserve_recover(state)
        unit=state.enemy('enemy').state.weapon_inventory.active
        request=build_npc_shield_pickup(state)
        result=execute_recover_action(request,NoDice())
        proof=complete_npc_shield_pickup(state,request,result)
        self.assertIs(type(proof.weapon),ReloadableWeaponState)
        self.assertEqual(proof.weapon,unit.reload)
        self.assertEqual(proof.enemy.state.weapon_inventory.active.reload,unit.reload)
        with self.assertRaises(ValueError):replace(proof,weapon=unit)

    def test_shield_pickup_cannot_erase_another_held_item_or_a_two_hand_grip(self):
        for two_handed in (False,True):
            items=(item(),item(W.GLAIVE if two_handed else W.DAGGER,id='back',location=L.CARRIED,grip=None))
            state=view(items,shield=True)
            enemy=state.enemy('enemy')
            dropped=replace(state.npc_shields[0],location=NpcShieldLocation.DROPPED,
                ground=NpcShieldGroundPosition('arena',('enemy','pc')))
            enemy=_with_shield(enemy,False)
            inventory=enemy.state.weapon_inventory
            if two_handed:
                sword,back=inventory.items
                inventory=inventory.with_item(replace(sword,location=L.CARRIED,grip=None))
                inventory=inventory.with_item(replace(back,location=L.HELD,grip=G.BOTH))
                inventory=replace(inventory,active_item_id=back.id)
            else:
                back=inventory.items[1]
                inventory=inventory.with_item(replace(back,location=L.HELD,grip=G.RIGHT))
            state.enemies=(replace(enemy,state=replace(enemy.state,weapon_inventory=inventory)),)
            state.npc_shields=(dropped,)
            self.assertIsNone(build_npc_shield_pickup(state))

    def test_drop_of_unselected_unit_preserves_other_held_weapon_and_attack_sources(self):
        state=view((item(),item(W.DAGGER,id='offhand',grip=G.RIGHT)))
        before=state.enemy('enemy')
        dropped=before.state.weapon_inventory.items[1]
        proof=build_briarroot_weapon_drop(state,'enemy',dropped.id)
        self.assertTrue(proof.actor.state.wields_weapon)
        self.assertEqual(proof.actor.state.available_attack_ids,before.state.available_attack_ids)
        self.assertEqual(proof.actor.state.weapon_inventory.active_item_id,before.state.weapon_inventory.active_item_id)
        self.assertEqual(proof.actor.state.weapon_inventory.items[0],before.state.weapon_inventory.items[0])
        updates(state,apply_briarroot_weapon_drop(state,proof),proof)
        self.assertTrue(_is_dropped(state,'enemy',dropped.id))
        self.assertFalse(_is_dropped(state,'enemy',before.state.weapon_inventory.active_item_id))
        validate_briarroot_dropped_weapons(state)

    def test_recover_restores_only_same_unit_without_stowing_or_changing_selection(self):
        state=view((item(),item(W.DAGGER,id='offhand',grip=G.RIGHT)))
        unit=state.enemy('enemy').state.weapon_inventory.items[1]
        drop=build_briarroot_weapon_drop(state,'enemy',unit.id)
        updates(state,apply_briarroot_weapon_drop(state,drop),drop)
        reserve_recover(state)
        before=state.enemy('enemy')
        request=build_briarroot_weapon_pickup(state,'enemy',unit.id)
        result=execute_recover_action(request,NoDice())
        proof=complete_briarroot_weapon_pickup(state,request,result,unit.id)
        self.assertEqual(proof.actor.state.weapon_inventory.active_item_id,before.state.weapon_inventory.active_item_id)
        self.assertEqual(proof.actor.state.weapon_inventory.items[0],before.state.weapon_inventory.items[0])
        self.assertEqual(proof.actor.state.weapon_inventory.item(unit.id),unit)
        updates(state,apply_briarroot_weapon_pickup(state,proof),proof)
        validate_briarroot_dropped_weapons(state)
        with self.assertRaises(ValueError):apply_briarroot_weapon_pickup(state,proof)

    def test_pickup_uses_other_free_hand_and_never_refills_the_actual_gun(self):
        facts=GeneratedRangedFacts(3,4,3,4,True,True,True)
        state=view((item(W.PISTOL,loaded=False),item(W.SWORD,id='other',grip=G.RIGHT)),ranged=facts)
        unit,other=state.enemy('enemy').state.weapon_inventory.items
        drop=build_briarroot_weapon_drop(state,'enemy',unit.id)
        updates(state,apply_briarroot_weapon_drop(state,drop),drop)
        enemy=state.enemy('enemy')
        inventory=enemy.state.weapon_inventory.with_item(replace(other,grip=G.LEFT))
        state.enemies=(replace(enemy,state=replace(enemy.state,weapon_inventory=inventory)),)
        reserve_recover(state)
        request=build_briarroot_weapon_pickup(state,'enemy',unit.id)
        proof=complete_briarroot_weapon_pickup(state,request,execute_recover_action(request,NoDice()),unit.id)
        recovered=proof.actor.state.weapon_inventory.item(unit.id)
        self.assertIs(recovered.grip,G.RIGHT)
        self.assertEqual(recovered.reload,unit.reload)
        self.assertFalse(recovered.reload.loaded)
        self.assertEqual(proof.actor.state.weapon_inventory.item(other.id),replace(other,grip=G.LEFT))

    def test_pickup_fails_when_another_held_item_occupies_the_last_free_hand(self):
        state=view((item(),item(W.DAGGER,id='offhand',grip=G.RIGHT),
            item(W.AXE,id='back',location=L.CARRIED,grip=None)))
        dropped=state.enemy('enemy').state.weapon_inventory.items[1]
        proof=build_briarroot_weapon_drop(state,'enemy',dropped.id)
        updates(state,apply_briarroot_weapon_drop(state,proof),proof)
        enemy=state.enemy('enemy');inventory=enemy.state.weapon_inventory
        back=inventory.items[2]
        inventory=inventory.with_item(replace(back,location=L.HELD,grip=G.RIGHT))
        state.enemies=(replace(enemy,state=replace(enemy.state,weapon_inventory=inventory)),)
        reserve_recover(state)
        self.assertFalse(can_pickup_briarroot_weapon(state,'enemy',dropped.id))
        with self.assertRaises(ValueError):build_briarroot_weapon_pickup(state,'enemy',dropped.id)

    def test_ground_validator_checks_same_unit_even_with_other_weapon_held(self):
        state=view((item(),item(W.DAGGER,id='offhand',grip=G.RIGHT)))
        unit=state.enemy('enemy').state.weapon_inventory.items[1]
        proof=build_briarroot_weapon_drop(state,'enemy',unit.id)
        updates(state,apply_briarroot_weapon_drop(state,proof),proof)
        validate_briarroot_dropped_weapons(state)
        enemy=state.enemy('enemy')
        inventory=enemy.state.weapon_inventory.with_item(unit)
        state.enemies=(replace(enemy,state=replace(enemy.state,weapon_inventory=inventory)),)
        with self.assertRaises(ValueError):validate_briarroot_dropped_weapons(state)


if __name__=='__main__':unittest.main()
