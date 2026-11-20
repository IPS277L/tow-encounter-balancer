"""Finite Throwing receipts over real K1 actions and prepared physical states.

These unit fixtures reserve genuine action slots but do not claim a complete
PC-owner journal. Native owner replay is verified by its integration tests.
"""
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.integration.test_inventory_source_adapters import profile as ranged_facts
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.armour_models import ArmourLoadout, ShieldKind
from towr.domain.attack_models import AttackRequest, AttackOutcome, ResilienceProfile
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedRangedFacts
from towr.domain.pc_battlefield_models import (
    PcAirspaceSpec, PcBattlefieldSpec, battlefield_range, with_actor_placement,
)
from towr.domain.pc_briarroot_weapon_models import (
    can_pickup_pc_weapon, can_pickup_briarroot_weapon, expected_briarroot_weapon_approach,
    build_briarroot_weapon_pickup, complete_briarroot_weapon_pickup, apply_briarroot_weapon_pickup,
)
from towr.domain.pc_combat_equipment_models import PcWeaponItem
from towr.domain.pc_melee_models import (
    PcMeleePolicy, PcShieldLoadout, PcShieldHandConflictPolicy, PcShieldRecoveryPolicy, PcWeaponHand,
)
from towr.domain.pc_melee_result_models import initial_pc_melee_state
from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
from towr.domain.pc_throwing_inventory_models import (
    prepare_throwing_inventory, throwing_inventory_updates,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as R
from towr.domain.resolution_models import KernelAttackRequest, TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatSide, CombatTurnStartRequest,
)
from towr.domain.weapon_catalog import WeaponKind as W
from towr.domain.weapon_impact_preparation import prepare_weapon_impact
from towr.domain.weapon_inventory_models import (
    WeaponGrip as G, WeaponItemLocation as L, WeaponItemSource,
)
from towr.domain.weapon_use_models import WeaponUse
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.recover_resolution import execute_recover_action
from towr.rules.spatial_resolution import start_next_spatial_round
from towr.rules.turn_resolution import reserve_combat_action_slot, start_combat_turn


class PreparedPhysicalView:
    """Inspect a proposed physical transition without claiming owner history."""
    def __init__(self, previous, **updates):
        self.previous=previous
        self.updates=updates

    def __getattr__(self, name):
        return self.updates[name] if name in self.updates else getattr(self.previous,name)

    def participant(self, actor):
        return next(member for member in self.party if member.actor_id==actor)

    def enemy(self, actor):
        return next(enemy for enemy in self.enemies if enemy.state.actor_id==actor)


class FixedD10:
    def __init__(self, value=10):
        self.value=value

    def randint(self, low, high):
        if (low,high)!=(1,10):
            raise AssertionError('only literal d10 rolls are expected')
        return self.value


class NoDice:
    def randint(self, low, high):
        raise AssertionError('standard physical pickup does not roll dice')


def prepared(kind=W.THROWING_SPEAR, *, actor='pc', shield=False, quantity=2, distance=R.MEDIUM):
    source=make_pc_melee_scenario()
    hand=PcWeaponHand.LEFT
    pc=source.party[0]
    items=(PcWeaponItem('throw',kind,L.HELD,hand,quantity=quantity),
        PcWeaponItem('pistol',W.PISTOL,L.CARRIED,None,initially_loaded=False),
        PcWeaponItem('sword',W.SWORD,L.CARRIED if shield else L.HELD,None if shield else PcWeaponHand.RIGHT))
    pc=replace(pc,pc=replace(pc.pc,weapon=kind if actor=='pc' else W.STAFF,
        ballistic_skill=3,throwing=4,brawn=4,toughness=20,strength=4,
        ranged=ranged_facts() if actor=='pc' else None),
        policy=PcMeleePolicy.AUTOMATIC_COMBAT,combat_equipment=items if actor=='pc' else None,
        shield=(PcShieldLoadout(PcWeaponHand.RIGHT,PcShieldHandConflictPolicy.WEAPON_FIRST,
            PcShieldRecoveryPolicy.RESTORE_BEFORE_ATTACK) if shield and actor=='pc' else None))
    weapons=(WeaponItemSource('throw',kind,L.HELD,G.LEFT,quantity=quantity),
        WeaponItemSource('pistol',W.PISTOL,L.CARRIED,None,initially_loaded=False),
        WeaponItemSource('sword',W.SWORD,L.CARRIED if shield else L.HELD,None if shield else G.RIGHT))
    npc=GeneratedNpc(3,4,20,3,4,4,
        weapons if actor!='pc' else (WeaponItemSource('staff',W.STAFF,L.HELD,G.LEFT),),
        ArmourLoadout(shield=ShieldKind.SHIELD if shield and actor!='pc' else None),defence=4,
        ranged=GeneratedRangedFacts(3, 4,  True, True, True) if actor!='pc' else None,
        throwing=4 if actor!='pc' else None,ballistic_skill=3 if actor!='pc' else None,
        brawn=4,endurance=4, initiative=3, dexterity=4)
    enemy=npc.participant('minion1')
    source=replace(source,party=(pc,),enemies=(enemy,),facts=replace(source.facts,
        can_leave_zone=True,all_opponents_close=distance is R.CLOSE),
        battlefield=PcBattlefieldSpec(distance,R.LONG,airspace=PcAirspaceSpec()),
        npc_ranged_policies=(pc_npc_ranged_policy_for_generated(npc,'minion1'),) if actor!='pc' else ())
    state=initial_pc_melee_state(source)
    side=CombatSide.PLAYERS_AND_ALLIES if actor=='pc' else CombatSide.OPPOSITION
    clock=replace(state.round_state,side_order=(side,CombatSide.OPPOSITION
        if side is CombatSide.PLAYERS_AND_ALLIES else CombatSide.PLAYERS_AND_ALLIES))
    clock=start_combat_turn(CombatTurnStartRequest('prepared:start',clock,actor)).state
    clock=reserve_combat_action_slot(CombatActionSlotRequest('prepared:slot',clock,actor,
        CombatActionDeclaration(CombatActionKind.ATTACK),ActionSlotGrant.STANDARD)).state
    return replace(state,round_state=clock)


def actual_attack(state, actor='pc', *, roll=10):
    target='minion1' if actor=='pc' else 'pc'
    inventory=(state.participant(actor).weapon_inventory if actor=='pc'
        else state.enemy(actor).state.weapon_inventory)
    use=WeaponUse(actor,inventory,inventory.active_item_id)
    impact=prepare_weapon_impact(use,4,ResilienceProfile(20)).impact_spec
    attack=AttackRequest('prepared:attack',TestRequest('prepared:attacker',InlineProfile(3,4)),
        TestRequest('prepared:defender',InlineProfile(3,4)),impact,False,False)
    injury=(state.enemy(target).state.injury if actor=='pc' else state.participant(target).injury)
    kernel=KernelAttackRequest('prepared:kernel',target,attack,
        TargetInjuryPolicy.MINION if actor=='pc' else TargetInjuryPolicy.PLAYER,injury,True,False)
    request=AttackActionExecutionRequest('prepared:execute',state.round_state,actor,target,1,kernel)
    result=execute_attack_action(request,FixedD10(roll))
    return request,result,use


class ThrowingInventoryTests(unittest.TestCase):
    def test_recoverable_hit_and_miss_land_one_real_unit_at_the_original_target(self):
        for kind in (W.ROCK,W.THROWING_SPEAR,W.THROWING_AXE):
            for roll,outcome in ((1,AttackOutcome.HIT),(10,AttackOutcome.MISS)):
                with self.subTest(kind=kind,roll=roll):
                    state=prepared(kind)
                    request,result,use=actual_attack(state,roll=roll)
                    self.assertIs(result.resolution.attack.outcome,outcome)
                    receipt=prepare_throwing_inventory(state,request,result,use)
                    self.assertEqual(receipt.item.ground.zone_id,state.battlefield.spatial.placement_for('minion1').zone_id)
                    self.assertNotEqual(receipt.item.ground.zone_id,state.battlefield.spatial.placement_for('pc').zone_id)
                    self.assertIs(receipt.after_inventory.active.location,L.DROPPED)
                    self.assertEqual(receipt.after_inventory.items[1:],use.inventory.items[1:])
                    self.assertIn('minion1',receipt.item.ground.initial_close_actor_ids)
                    self.assertNotIn('pc',receipt.item.ground.initial_close_actor_ids)
                    updates=throwing_inventory_updates(state,request,result,use,receipt,{})
                    after=PreparedPhysicalView(state,**updates)
                    self.assertFalse(can_pickup_pc_weapon(after,'pc',receipt.item.weapon_id))
                    self.assertIsNone(expected_briarroot_weapon_approach(after,'pc',receipt.item.weapon_id))
                    next_round=replace(result.state,round_number=2,active_turn=None,
                        completed_turn_entity_ids=(),excluded_turn_entity_ids=())
                    next_turn=start_combat_turn(CombatTurnStartRequest('next:turn',next_round,'pc')).state
                    following=PreparedPhysicalView(after,round_state=next_turn,
                        battlefield=replace(after.battlefield,spatial=start_next_spatial_round(after.battlefield.spatial)))
                    self.assertIsNotNone(expected_briarroot_weapon_approach(following,'pc',receipt.item.weapon_id))

    def test_volatile_miss_spends_exactly_one_unit_without_creating_pickup_or_refilling_gun(self):
        for kind in (W.OIL_FLASK,W.BLASTING_CHARGE):
            with self.subTest(kind=kind):
                state=prepared(kind,shield=True)
                request,result,use=actual_attack(state)
                receipt=prepare_throwing_inventory(state,request,result,use)
                self.assertIs(receipt.after_inventory.active.location,L.SPENT)
                self.assertEqual(receipt.after_inventory.items[1:],use.inventory.items[1:])
                self.assertIs(receipt.after_inventory.shield_hand,G.RIGHT)
                self.assertFalse(receipt.after_inventory.items[-2].reload.loaded)
                self.assertIsNone(receipt.item)
                self.assertEqual(receipt.state,state.battlefield)
                after=PreparedPhysicalView(state,**throwing_inventory_updates(state,request,result,use,receipt,{}))
                self.assertEqual(after.briarroot_dropped_weapons,())
                self.assertFalse(can_pickup_pc_weapon(after,'pc',receipt.weapon_use.primary_item_id))
                with self.assertRaises(ValueError):
                    receipt.after_inventory.with_item(replace(receipt.after_inventory.active,location=L.HELD,grip=G.LEFT))

    def test_knives_keep_the_whole_battle_set_but_still_require_the_actual_action(self):
        state=prepared(W.THROWING_KNIVES,quantity=1)
        request,result,use=actual_attack(state)
        receipt=prepare_throwing_inventory(state,request,result,use)
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.after_inventory,use.inventory)
        self.assertIsNone(receipt.item)
        with self.assertRaises(ValueError):
            throwing_inventory_updates(state,request,result,use,None,{})
        after=PreparedPhysicalView(state,round_state=result.state)
        with self.assertRaises(ValueError):
            prepare_throwing_inventory(after,request,result,use)

    def test_frozen_landing_is_projected_to_the_ground_below_an_airborne_target(self):
        state=prepared()
        target_zone=state.battlefield.spatial.placement_for('minion1').zone_id
        air=next(zone for zone,ground in state.battlefield.air_to_ground if ground==target_zone)
        state=PreparedPhysicalView(state,battlefield=with_actor_placement(state.battlefield,'minion1',air))
        request,result,use=actual_attack(state)
        receipt=prepare_throwing_inventory(state,request,result,use)
        self.assertEqual(receipt.item.ground.zone_id,target_zone)
        self.assertEqual(receipt.item.ground.initial_close_actor_ids,())
        self.assertEqual(receipt.state.spatial.placement_for(receipt.item.marker_id).zone_id,target_zone)
        # Outcome work may move the target, but never relocates the frozen item.
        moved=with_actor_placement(state.battlefield,'minion1',state.battlefield.spatial.placement_for('pc').zone_id)
        with self.assertRaises(ValueError):
            throwing_inventory_updates(PreparedPhysicalView(state,battlefield=moved),request,result,use,receipt,{})

    def test_receipt_cannot_change_target_another_item_resource_or_ground_prefix(self):
        state=prepared()
        request,result,use=actual_attack(state)
        receipt=prepare_throwing_inventory(state,request,result,use)
        with self.assertRaises(ValueError):
            throwing_inventory_updates(state,replace(request,target_id='foreign'),result,use,receipt,{})
        with self.assertRaises(ValueError):
            replace(receipt,after_inventory=replace(receipt.after_inventory,shield_hand=G.LEFT))
        with self.assertRaises(ValueError):
            replace(receipt,previous_item=receipt.item)
        with self.assertRaises(ValueError):
            throwing_inventory_updates(state,request,result,replace(use,actor_id='minion1'),receipt,{})
        altered=PreparedPhysicalView(state,party=(replace(state.party[0],weapon_inventory=receipt.after_inventory),))
        with self.assertRaises(ValueError):
            prepare_throwing_inventory(altered,request,result,use)

    def test_generated_owner_lands_same_unit_and_uses_real_paid_recover(self):
        state=prepared(actor='minion1',distance=R.SHORT)
        request,result,use=actual_attack(state,'minion1')
        receipt=prepare_throwing_inventory(state,request,result,use)
        updates=throwing_inventory_updates(state,request,result,use,receipt,{})
        after=PreparedPhysicalView(state,**updates)
        enemy=after.enemy('minion1')
        self.assertTrue(enemy.state.wields_weapon)  # Its other actual Sword remains held.
        self.assertEqual(enemy.state.weapon_inventory.items[1:],use.inventory.items[1:])
        self.assertFalse(can_pickup_briarroot_weapon(after,'minion1',receipt.item.weapon_id))
        self.assertEqual(battlefield_range(after.battlefield,'pc',receipt.item.marker_id),R.CLOSE)
        # Prepare its next own Recover with actual Close position and a free
        # left hand. This tests the existing paid pickup without fake actions.
        battlefield=with_actor_placement(after.battlefield,'minion1',receipt.item.ground.zone_id,
            close_to_ids=(receipt.item.marker_id,))
        fresh=replace(after.round_state,active_turn=None)
        fresh=start_combat_turn(CombatTurnStartRequest('pickup:start',fresh,'minion1')).state
        fresh=reserve_combat_action_slot(CombatActionSlotRequest('pickup:slot',fresh,'minion1',
            CombatActionDeclaration(CombatActionKind.RECOVER),ActionSlotGrant.STANDARD)).state
        recovery=PreparedPhysicalView(after,round_state=fresh,battlefield=battlefield)
        recover=build_briarroot_weapon_pickup(recovery,'minion1',receipt.item.weapon_id)
        completed=execute_recover_action(recover,NoDice())
        proof=complete_briarroot_weapon_pickup(recovery,recover,completed,receipt.item.weapon_id)
        restored=PreparedPhysicalView(recovery,**apply_briarroot_weapon_pickup(recovery,proof))
        self.assertIs(restored.enemy('minion1').state.weapon_inventory.active.location,L.HELD)
        self.assertEqual(restored.enemy('minion1').state.weapon_inventory.active.id,use.primary_item_id)
        self.assertIsNone(restored.briarroot_dropped_weapons[0].ground)
        self.assertEqual(restored.enemy('minion1').state.weapon_inventory.items[1:],use.inventory.items[1:])


if __name__=='__main__':
    unittest.main()
