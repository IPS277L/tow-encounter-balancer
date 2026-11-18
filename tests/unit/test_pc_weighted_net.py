"""Literal Net rules and physical-item preparation snapshots.

The small namespace contexts below deliberately exercise pure preparation and
projection boundaries. They do not claim to be completed native journals.
"""
from copy import deepcopy
from dataclasses import fields,replace
from random import Random
from types import SimpleNamespace
import unittest

from tests.support.pc_tactics_fixtures import automatic_source,tactical_snapshot
from tests.support.pc_melee_scripted import ScriptedD10
from towr.application.dynamic_encounter import NpcSearchSpace
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.attack_models import AttackRequest,ConditionImpactSpec,ProneBeforeGiveGroundSpec
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon,validate_generated_definition
from towr.domain.injury_models import WoundConditionEffect,WoundEffectDuration,WoundEntryId,WoundRecord
from towr.domain.pc_battlefield_models import PcBattlefieldSpec,battlefield_range,with_actor_placement
from towr.domain.pc_combat_equipment_models import PcItemLocation,PcWeaponItem
from towr.domain.pc_melee_models import PcMeleeWeapon,PcTwoHandedGrip
from towr.domain.pc_melee_result_models import (
    PcFateDecline,PcHandDropProof,PcBodyConsequenceProof,PcMinionStaggerDefeatProof,
)
from towr.domain.pc_mount_models import HORSE_NOBLE_STEED_RULE_ID
from towr.domain.pc_net_models import PcNetConditionSource,expected_net_resolution
from towr.domain.pc_npc_net_policy_models import NET_RULE_ID
from towr.domain.pc_weighted_net_models import (
    PcNetLocation,PcNetGroundPosition,PcWeightedNetState,PcNetReleaseProof,PcNetPickupProof,
    PcNetRecoverKind,weighted_net_profile,weighted_net_for_actor,weighted_net_item_close,
    complete_weighted_net_throw,weighted_net_updates_from_attack,weighted_net_condition_sources,
    build_weighted_net_release,weighted_net_release_item,build_weighted_net_pickup,weighted_net_pickup_item,
    project_weighted_net_step,weighted_net_recovery_options,weighted_net_has_usable_attack,
    expected_weighted_net_incidental_pickup,
    expected_weighted_net_approach,complete_weighted_net_equipment_proof,weighted_nets_after_equipment,
    validate_weighted_net_bank,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands,RangedWeaponRange
from towr.domain.resolution_models import KernelAttackRequest,TargetInjuryPolicy
from towr.domain.test_models import DiceModifier,InlineProfile,TestRequest
from towr.domain.turn_models import (
    CombatActionKind,CombatActionDeclaration,CombatActionSlotRequest,ActionSlotGrant,
)
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.recover_resolution import (
    execute_recover_action,_complete_condition_removal_after_test,
)
from towr.domain.recover_models import _expected_recover_execution
from towr.rules.test_resolution import resolve_test
from towr.rules.turn_resolution import reserve_combat_action_slot
from towr.domain.injury_models import WoundConsequence,WoundConsequenceRequest,MinionStaggerDefeatCause
from towr.domain.pc_melee_models import PcWeaponHand
from towr.domain.pc_warped_form_models import PcWarpedFormMinionDefeatProof


R = RangedWeaponRange


def component(*,bs=2,strength=3,**changes):
    values = dict(weapon_skill=3,strength=strength,toughness=4,agility=3,melee=4,athletics=4,
        defence=4,weapon=GeneratedWeapon.WEIGHTED_NET,light_armour=False,shield=False,
        ballistic_skill=bs,throwing=4,brawn=4)
    values.update(changes)
    return GeneratedNpc(**values)


def source(*,distance=None,npcs=1):
    original = automatic_source(pc_count=2,enemy_count=npcs,rounds=3)
    member = original.party[0]
    pc = replace(member.pc,weapon=PcMeleeWeapon.WEIGHTED_NET,throwing=4,ballistic_skill=2,brawn=4)
    member = replace(member,pc=pc,initial_weapon_hand=PcTwoHandedGrip.BOTH,
        combat_equipment=(PcWeaponItem('net',PcMeleeWeapon.WEIGHTED_NET,PcItemLocation.HELD,PcTwoHandedGrip.BOTH),))
    ally = replace(original.party[1],pc=replace(original.party[1].pc,brawn=4))
    return replace(original,party=(member,ally),enemies=tuple(component().participant(actor)
        for actor in original.enemy_activation_order),
        facts=replace(original.facts,all_opponents_close=distance is None or distance is R.CLOSE,
            can_leave_zone=distance is not None),
        battlefield=None if distance is None else PcBattlefieldSpec(distance,R.LONG))


def context(scenario,*,actor='pc1',kind=CombatActionKind.ATTACK):
    actual = tactical_snapshot(scenario,actor=actor)
    prepared = SimpleNamespace(**{field.name:getattr(actual,field.name) for field in fields(actual)})
    prepared.participant = lambda actor:next(member for member in prepared.party if member.actor_id == actor)
    prepared.enemy = lambda actor:next(enemy for enemy in prepared.enemies if enemy.state.actor_id == actor)
    prepared.live_party = tuple(member for member in prepared.party if not member.injury.dead)
    prepared.live_enemies = tuple(enemy for enemy in prepared.enemies if not enemy.state.injury.defeated)
    prepared.exited_npc_ids = actual.exited_npc_ids
    if kind is not None:
        prepared.round_state = reserve_combat_action_slot(CombatActionSlotRequest('pure:reserve',
            prepared.round_state,actor,CombatActionDeclaration(kind),ActionSlotGrant.STANDARD)).state
    return prepared


def bound_item(item,target,number):
    binding = PcNetConditionSource(f'attack:{number}',item.owner_id,target,f'application:{number}',NET_RULE_ID)
    return replace(item,location=PcNetLocation.BOUND,bound_target_id=target,binding=binding)


class WeightedNetSourceTests(unittest.TestCase):
    def test_inventory_location_must_mirror_the_actual_physical_net_bank(self):
        prepared = context(source(),kind=None)
        validate_weighted_net_bank(prepared)
        member = prepared.participant('pc1')
        inventory = replace(member.weapon_inventory,items=tuple(replace(item,
            location=PcItemLocation.CARRIED,hand=None) for item in member.weapon_inventory.items))
        prepared.party = tuple(replace(member,weapon_hand=None,weapon_inventory=inventory)
            if current.actor_id == member.actor_id else current for current in prepared.party)
        with self.assertRaises(ValueError):
            validate_weighted_net_bank(prepared)

    def test_ballistic_skill_caps_throwing_while_strength_only_extends_optimum(self):
        for strength,maximum in ((1,R.SHORT),(3,R.SHORT),(4,R.MEDIUM),(8,R.MEDIUM)):
            for bs in (1,2,4):
                profile = weighted_net_profile(bs,5,strength)
                self.assertEqual(profile.test_profile,InlineProfile(bs,5))
                self.assertEqual(profile.test_profile.maximum_dice,2*bs)
                self.assertEqual((profile.range_min,profile.range_max),(R.CLOSE,maximum))
                self.assertIs(profile.hands,RangedWeaponHands.TWO_HANDED)
                self.assertIsNone(profile.damage)
                self.assertEqual(profile.condition_impact,ConditionImpactSpec(Condition.BURDENED,NET_RULE_ID))
        high = weighted_net_profile(1,10,4)
        rng = ScriptedD10([2])
        test = resolve_test(TestRequest('single',high.test_profile),rng)
        rng.assert_exhausted()
        self.assertTrue(test.succeeded)
        self.assertEqual(test.trace.threshold,10)
        reduced = resolve_test(TestRequest('minimum',high.test_profile,
            (DiceModifier('fixture:penalty',-1),)),ScriptedD10([2]))
        self.assertFalse(reduced.succeeded)
        self.assertEqual(reduced.trace.threshold,1)

    def test_generated_net_requires_full_source_and_cannot_acquire_damage_secondaries(self):
        npc = component()
        definition = npc.participant('unrelated-name').definition
        self.assertIsNone(definition.attacks[0].damage)
        validate_generated_definition(definition)
        for changes in (dict(throwing=None),dict(ballistic_skill=None),dict(ballistic_skill=True),dict(shield=True)):
            with self.subTest(changes=changes),self.assertRaises((ValueError,TypeError)):
                replace(npc,**changes)
        forged = deepcopy(definition)
        object.__setattr__(forged.attacks[0].test_profile,'dice',7)
        with self.assertRaises((ValueError,TypeError)):
            validate_generated_definition(forged)

    def test_generation_and_numeric_resampling_keep_net_and_admitted_bs_throwing_brawn(self):
        envelope = NpcSearchSpace(weapon=(GeneratedWeapon.WEIGHTED_NET,),shield=(False,),
            allowed_talents=(),ballistic_skill=(1,2,4),strength=(1,4),throwing=(2,5),brawn=(3,5))
        for seed in range(12):
            npc = envelope.sample(Random(seed))
            self.assertTrue(envelope.contains(npc))
            self.assertIn(npc.ballistic_skill,(1,2,4))
            self.assertIn(npc.brawn,(3,5))
            self.assertIsNone(npc.ranged)
            self.assertFalse(npc.shield)
            sampled, = envelope.resample_numeric((npc,),Random(seed+30)).composition
            self.assertTrue(envelope.contains(sampled))
            self.assertIs(sampled.weapon,GeneratedWeapon.WEIGHTED_NET)
            self.assertIsNone(sampled.weapon_grip)

    def test_active_inventory_uid_wins_over_an_earlier_carried_net(self):
        first = PcWeightedNetState('pc:weapon:first','pc',PcNetLocation.CARRIED)
        active = PcWeightedNetState('pc:weapon:active','pc',PcNetLocation.HELD)
        member = SimpleNamespace(weapon_inventory=SimpleNamespace(active_item_id='active'))
        prepared = SimpleNamespace(source=SimpleNamespace(pc_activation_order=('pc',)),
            weighted_nets=(first,active),participant=lambda actor:member)
        self.assertIs(weighted_net_for_actor(prepared,'pc'),active)


class WeightedNetLandingTests(unittest.TestCase):
    def landing(self,*,distance=None,hit=False,horse=False,defenceless=False):
        prepared = context(source(distance=distance))
        target = prepared.enemy('minion1').state.injury
        if defenceless:
            target = replace(target,conditions=target.conditions.with_condition(Condition.DEFENCELESS))
        profile = weighted_net_profile(2,4,3)
        attack = AttackRequest('net:test',TestRequest('net:throwing',profile.test_profile),None,
            profile.condition_impact,distance is None or distance is R.CLOSE,False,
            secondary_effects=(ProneBeforeGiveGroundSpec(HORSE_NOBLE_STEED_RULE_ID,False),) if horse else ())
        kernel = KernelAttackRequest('net:kernel','minion1',attack,TargetInjuryPolicy.MINION,target,False,False)
        request = AttackActionExecutionRequest('net:execute',prepared.round_state,'pc1','minion1',1,kernel)
        rng = ScriptedD10([1,10] if hit else [10,10])
        execution = execute_attack_action(request,rng)
        rng.assert_exhausted()
        self.assertEqual(execution.resolution,expected_net_resolution(kernel,execution.resolution.attack))
        return prepared,request,execution,complete_weighted_net_throw(prepared,request,execution)

    def test_miss_leaves_one_same_item_at_frozen_target_position_and_close_miss_keeps_stagger_followup(self):
        prepared,request,execution,landing = self.landing(distance=R.SHORT)
        self.assertIs(landing.item.location,PcNetLocation.FREE)
        updates = weighted_net_updates_from_attack(prepared,request,execution,landing)
        prepared.weighted_nets,prepared.battlefield = updates['weighted_nets'],updates['battlefield']
        marker = prepared.battlefield.spatial.placement_for(landing.item.marker_id)
        self.assertEqual(marker.zone_id,landing.item.ground.zone_id)
        self.assertFalse(weighted_net_item_close(prepared,'pc1',landing.item_id))
        self.assertTrue(weighted_net_item_close(prepared,'minion1',landing.item_id))
        target_zone = prepared.battlefield.spatial.graph.adjacent_zone_ids(marker.zone_id)[0]
        prepared.battlefield = with_actor_placement(prepared.battlefield,'minion1',target_zone)
        self.assertEqual(prepared.battlefield.spatial.placement_for(landing.item.marker_id),marker)
        self.assertFalse(weighted_net_item_close(prepared,'minion1',landing.item_id))
        _,_,close,_ = self.landing()
        self.assertEqual(len(close.resolution.follow_ups),1)
        self.assertIsNone(close.resolution.stagger)

    def test_hit_and_horse_hit_on_defenceless_bind_without_damage_wound_or_stagger(self):
        for horse in (False,True):
            prepared,request,execution,landing = self.landing(hit=True,horse=horse,defenceless=True)
            result = execution.resolution
            self.assertIs(landing.item.location,PcNetLocation.BOUND)
            self.assertEqual(landing.item.bound_target_id,'minion1')
            self.assertIsNone(landing.item.ground)
            self.assertTrue(result.target_state.conditions.has(Condition.BURDENED))
            self.assertIs(result.target_state.conditions.has(Condition.PRONE),horse)
            self.assertIsNone(result.attack.damage)
            self.assertIsNone(result.character_wound)
            self.assertIsNone(result.profile_wound)
            self.assertIsNone(result.stagger)
            self.assertEqual(landing.previous,landing.state)


class WeightedNetRecoverTests(unittest.TestCase):
    def prepared_bound(self,*,wound=False):
        prepared = context(source(npcs=2),actor='pc2',kind=CombatActionKind.RECOVER)
        bank = tuple(bound_item(item,'pc2',index) if item.owner_id.startswith('minion') else item
            for index,item in enumerate(prepared.weighted_nets))
        member = prepared.participant('pc2')
        injury = replace(member.injury,conditions=member.injury.conditions.with_condition(Condition.BURDENED))
        if wound:
            record = WoundRecord(1,WoundEntryId.SHATTERED_KNEE,17,(7,10),treated=True,effect_resolved=True)
            injury = replace(injury,wounds=(record,),active_wound_effects=(
                WoundConditionEffect(1,Condition.BURDENED,WoundEffectDuration.UNTIL_HEALED),))
        member = replace(member,injury=injury,net_condition_sources=tuple(item.binding for item in bank
            if item.location is PcNetLocation.BOUND))
        prepared.party = tuple(member if other.actor_id == 'pc2' else other for other in prepared.party)
        prepared.weighted_nets = bank
        return prepared

    def release(self,prepared,item):
        request = build_weighted_net_release(prepared,'pc2',item.item_id)
        rng = ScriptedD10([1,1,1])
        test = resolve_test(request.choice.test,rng)
        rng.assert_exhausted()
        result = _expected_recover_execution(request,_complete_condition_removal_after_test(request.choice,test))
        after,battlefield = weighted_net_release_item(prepared,item.item_id,result)
        proof = PcNetReleaseProof(request,result,item.item_id,item,after,prepared.battlefield,battlefield,
            PcFateDecline('pc2',request.choice.test.id,'test',prepared.source.participant('pc2').fate_policy))
        return proof,project_weighted_net_step(prepared,proof)

    def test_one_brawn_recover_releases_one_binding_and_preserves_the_other(self):
        prepared = self.prepared_bound()
        item = next(item for item in prepared.weighted_nets if item.location is PcNetLocation.BOUND)
        proof,updates = self.release(prepared,item)
        self.assertIs(proof.item.location,PcNetLocation.FREE)
        self.assertEqual(len(weighted_net_condition_sources(prepared,'pc2',bank=updates['weighted_nets'])),1)
        member = next(member for member in updates['party'] if member.actor_id == 'pc2')
        self.assertTrue(member.injury.conditions.has(Condition.BURDENED))
        self.assertFalse(hasattr(proof.result.resolution,'miscast_dice_removed'))
        with self.assertRaises(ValueError):
            project_weighted_net_step(prepared,replace(proof,item_id='missing'))

    def test_releasing_last_net_does_not_heal_independent_burdened_wound(self):
        prepared = self.prepared_bound(wound=True)
        bound = [item for item in prepared.weighted_nets if item.location is PcNetLocation.BOUND]
        prepared.weighted_nets = tuple(replace(item,location=PcNetLocation.CARRIED,
            bound_target_id=None,binding=None) if item is bound[1] else item for item in prepared.weighted_nets)
        member = prepared.participant('pc2')
        prepared.party = tuple(replace(member,net_condition_sources=(bound[0].binding,))
            if other.actor_id == 'pc2' else other for other in prepared.party)
        _,updates = self.release(prepared,bound[0])
        after = next(member for member in updates['party'] if member.actor_id == 'pc2')
        self.assertTrue(after.injury.conditions.has(Condition.BURDENED))
        self.assertEqual(after.injury.wounds,member.injury.wounds)
        self.assertEqual(after.net_condition_sources,())

    def test_free_net_requires_close_and_real_recover_with_enemy_and_pickup_has_no_fate_test(self):
        prepared = context(source(),kind=CombatActionKind.RECOVER)
        item = weighted_net_for_actor(prepared,'pc1')
        item = replace(item,location=PcNetLocation.FREE,
            ground=PcNetGroundPosition(prepared.source.facts.zone_id,('pc1','pc2','minion1')))
        prepared.weighted_nets = tuple(item if other.owner_id == 'pc1' else other for other in prepared.weighted_nets)
        self.assertFalse(weighted_net_has_usable_attack(prepared,'pc1'))
        options = weighted_net_recovery_options(prepared,'pc1')
        self.assertTrue(any(option.kind is PcNetRecoverKind.PICKUP for option in options))
        self.assertIsNone(expected_weighted_net_incidental_pickup(prepared))
        request = build_weighted_net_pickup(prepared,item.item_id)
        result = execute_recover_action(request,ScriptedD10([]))
        after,battlefield = weighted_net_pickup_item(prepared,item.item_id)
        proof = PcNetPickupProof(request,result,item.item_id,item,after,None,battlefield)
        updates = project_weighted_net_step(prepared,proof)
        self.assertIs(updates['weighted_nets'][0].location,PcNetLocation.HELD)
        self.assertEqual(updates['party'][0].weapon_hand,PcTwoHandedGrip.BOTH)
        self.assertTrue(result.slot.executed)

    def test_approach_to_item_with_enemy_still_there_requires_recover_but_departed_enemy_allows_free_pickup(self):
        for departed in (False,True):
            prepared = context(source(distance=R.SHORT),kind=None)
            item = weighted_net_for_actor(prepared,'pc1')
            from towr.domain.pc_weighted_net_models import _add_marker
            target_zone = prepared.battlefield.spatial.placement_for('minion1').zone_id
            free = replace(item,location=PcNetLocation.FREE,
                ground=PcNetGroundPosition(target_zone,('minion1',)))
            prepared.weighted_nets = tuple(free if other.item_id == item.item_id else other
                for other in prepared.weighted_nets)
            prepared.battlefield = _add_marker(prepared.battlefield,free)
            if departed:
                destination = prepared.battlefield.spatial.graph.adjacent_zone_ids(target_zone)[0]
                prepared.battlefield = with_actor_placement(prepared.battlefield,'minion1',destination)
            approach = expected_weighted_net_approach(prepared,'pc1',item.item_id)
            self.assertIsNotNone(approach)
            updates = project_weighted_net_step(prepared,approach)
            prepared.battlefield = updates['battlefield']
            self.assertTrue(weighted_net_item_close(prepared,'pc1',item.item_id))
            self.assertIs(battlefield_range(prepared.battlefield,'pc1','pc2'),R.SHORT)
            pickup = expected_weighted_net_incidental_pickup(prepared)
            with self.subTest(departed=departed):
                self.assertIs(pickup is not None,departed)
                if pickup is not None:
                    updates = project_weighted_net_step(prepared,pickup)
                    self.assertEqual(updates.get('round_state',prepared.round_state),prepared.round_state)
                    self.assertIs(updates['weighted_nets'][0].location,PcNetLocation.HELD)

    def test_all_four_actual_drop_proof_variants_capture_one_fixed_physical_item_and_reject_replay(self):
        for kind in ('hand','body','minion','wave'):
            prepared = context(source(distance=R.SHORT),kind=None)
            if kind in ('hand','body'):
                actor = 'pc1'
                prepared.pending_actor_id = actor
                member = prepared.participant(actor)
                record = WoundRecord(1,WoundEntryId.SHAKING_GRIP,8,(8,),effect_resolved=True)
                prepared.party = tuple(replace(member,injury=replace(member.injury,wounds=(record,)))
                    if current.actor_id == actor else current for current in prepared.party)
                consequence = WoundConsequenceRequest(1,WoundConsequence.DROP_RANDOM_HAND_ITEM,'fixture:wound')
                raw = (PcHandDropProof(consequence,1,PcWeaponHand.LEFT) if kind == 'hand'
                    else PcBodyConsequenceProof(consequence,1,PcWeaponHand.LEFT))
            else:
                actor = 'minion1'
                raw = (PcMinionStaggerDefeatProof(MinionStaggerDefeatCause('attack',actor,'fixture:dirty-coward'))
                    if kind == 'minion' else PcWarpedFormMinionDefeatProof('wave',actor))
            proof = complete_weighted_net_equipment_proof(prepared,raw)
            with self.subTest(kind=kind):
                self.assertEqual(len(proof.weighted_net_drops),1)
                drop, = proof.weighted_net_drops
                self.assertEqual(drop.actor_id,actor)
                self.assertIs(drop.item.location,PcNetLocation.FREE)
                self.assertEqual(drop.item.ground.zone_id,prepared.battlefield.spatial.placement_for(actor).zone_id)
                updates = weighted_nets_after_equipment(prepared,proof,{})
                self.assertEqual(updates['battlefield'],drop.state)
                prepared.weighted_nets = updates['weighted_nets']
                prepared.battlefield = updates['battlefield']
                with self.assertRaises(ValueError):
                    complete_weighted_net_equipment_proof(prepared,proof)


if __name__ == '__main__':
    unittest.main()
