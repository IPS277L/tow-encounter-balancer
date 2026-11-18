"""Pure Briarroot projections around real, fully executed Attack receipts.

Observation views represent equipment/position changes owned by other modules;
they do not pretend to be standalone replayable combat journals.
"""
from tests.support.generated_weapon_sources import initial_generated_weapons
from dataclasses import fields,replace
import unittest

from tests.helpers import SequenceRandom
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_shield_scenarios import shield_loadout
from towr.domain.armour_models import ArmourLoadout,BodyArmour,ShieldKind
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon
from towr.domain.pc_briarroot_models import (
    PcBriarrootBinding,PcBriarrootProof,PcBriarrootReleaseProof,BriarrootReleaseReason,
    expected_briarroot_update,apply_briarroot_update,validate_briarroot_bindings,
    external_briarroot_conditions,bound_weapon_ids,can_leave_close_with_weapon,
    build_briarroot_release,apply_briarroot_release,briarroot_recovery_options,
    BriarrootWeaponKind,
)
from towr.domain.pc_melee_result_models import PcAttackProof,PcFateDecline
from towr.domain.pc_melee_models import PcWeaponHand,PcMeleeWeapon,PcMeleePolicy
from towr.domain.pc_npc_catalog import create_pc_book_npc,PcBookNpcProfile
from towr.domain.pc_mount_models import CombatMount
from towr.domain.pc_combat_equipment_models import PcWeaponItem,PcItemLocation
from towr.domain.pc_weapon_inventory import replace_pc_member
from towr.domain.pc_battlefield_models import PcBattlefieldSpec,with_actor_placement
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.pc_shield_models import PcShieldLocation,PcShieldState
from towr.domain.test_models import Skill
from towr.domain.turn_models import CombatActionDeclaration,CombatActionKind
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.rules.recover_resolution import execute_recover_action


class Observation:
    def __init__(self,state,**changes):
        values=({item.name:getattr(state,item.name) for item in fields(state)}
            if not isinstance(state,Observation) else state.__dict__.copy())
        values.setdefault('briarroot_bindings',())
        values.update(changes)
        self.__dict__.update(values)

    def participant(self,actor):
        return next(member for member in self.party if member.actor_id==actor)

    def enemy(self,actor):
        return next(enemy for enemy in self.enemies if enemy.state.actor_id==actor)

    @property
    def exited_npc_ids(self):
        return ()

    @property
    def live_party(self):
        return tuple(member for member in self.party if not member.injury.dead)

    @property
    def live_enemies(self):
        return tuple(enemy for enemy in self.enemies if not enemy.state.injury.defeated)


def actual_attack(*,pc_bearer=False,heavy=False,both_fail=False,athletics=False,attacker_hits=False,inventory=False,
        spatial=False,mount=None,airspace=None):
    source=make_pc_melee_scenario(max_rounds=1)
    member=replace(source.party[0],pc=replace(source.party[0].pc,brawn=4))
    if inventory or spatial:
        member=replace(member,policy=PcMeleePolicy.AUTOMATIC_COMBAT)
    if mount is not None:
        member=replace(member,mount=mount)
    if inventory:
        member=replace(member,combat_equipment=(PcWeaponItem('staff',PcMeleeWeapon.STAFF,
            PcItemLocation.HELD,member.initial_weapon_hand),))
    if pc_bearer:
        member=replace(member,shield=shield_loadout(PcWeaponHand.RIGHT),armour=ArmourLoadout(shield=ShieldKind.BRIARROOT))
    if heavy:
        member=replace(member,pc=replace(member.pc,strength=2,armour_bonus=2),
            armour=ArmourLoadout((BodyArmour.HEAVY,),BodyArmour.HEAVY))
    enemy=GeneratedNpc(2,1,20,5 if athletics else 1,3,5 if athletics else 2,
        initial_generated_weapons(GeneratedWeapon.STAFF),ArmourLoadout(shield=None if pc_bearer else ShieldKind.BRIARROOT),
        defence=5,brawn=4).participant('minion1')
    scene=(dict(battlefield=PcBattlefieldSpec(RangedWeaponRange.CLOSE,RangedWeaponRange.LONG,airspace=airspace),
        facts=replace(source.facts,can_leave_zone=True,unmounted=mount is None)) if spatial else {})
    source=replace(source,party=(member,),enemies=(enemy,),**scene)
    values=(([1]*3 if attacker_hits else [10]*3)
        +[10 if both_fail else 1]*(5 if athletics else 2)+[10]*2+[1]*3)
    result=run_pc_melee_scenario(source,SequenceRandom(values))
    selected='minion1' if pc_bearer else 'pc'
    step=next(step for step in result.steps if type(step.proof) is PcAttackProof
        and step.proof.request.actor_id==selected)
    return Observation(step.state),step.proof


def react(state):
    proof=expected_briarroot_update(state)
    if proof is None:
        raise AssertionError('fixture did not produce an actual Briarroot reaction')
    updated=Observation(state,history=(*state.history,proof),**apply_briarroot_update(state,proof))
    return updated,proof


def recover_slot(state,actor):
    # A genuine existing action slot is re-prepared for the alternative Recover;
    # the release owner subsequently checks the normal typed Recover contract.
    turn=state.round_state.active_turn
    slot=replace(turn.action_slots[-1],declaration=CombatActionDeclaration(CombatActionKind.RECOVER),execution=None)
    clock=replace(state.round_state,active_turn=replace(turn,actor_id=actor,action_slots=(slot,)))
    return Observation(state,round_state=clock,pending=(),pending_wound=None,magic_pending=None)


def release_proof(state,request,result,bindings):
    return PcBriarrootReleaseProof(request,result,state.briarroot_bindings[0].id,
        state.briarroot_bindings,bindings,fate_decline=PcFateDecline(request.actor_id,
            request.choice.test.id,'test',state.source.participant(request.actor_id).fate_policy))


class BriarrootBindingTests(unittest.TestCase):
    def test_paid_mount_attack_binds_its_natural_source_instead_of_the_rider_weapon(self):
        source=make_pc_melee_scenario(max_rounds=1)
        member=replace(source.party[0],pc=replace(source.party[0].pc,
            weapon_skill=1,melee=2,strength=1),mount=CombatMount.HORSE,
            policy=PcMeleePolicy.AUTOMATIC_COMBAT)
        enemy=GeneratedNpc(2,1,20,1,3,2,initial_generated_weapons(GeneratedWeapon.STAFF),
            ArmourLoadout(shield=ShieldKind.BRIARROOT),defence=5).participant('minion1')
        source=replace(source,party=(member,),enemies=(enemy,),
            facts=replace(source.facts,can_leave_zone=True,unmounted=False),
            battlefield=PcBattlefieldSpec(RangedWeaponRange.CLOSE,RangedWeaponRange.LONG))
        result=run_pc_melee_scenario(source,SequenceRandom([10]*3+[1]*2+[10]*50))
        step=next(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='pc')
        self.assertIsNotNone(step.proof.mount_attack)
        bound,_=react(Observation(step.state))
        binding,=bound.briarroot_bindings
        self.assertIs(binding.kind,BriarrootWeaponKind.MOUNT_NATURAL)
        self.assertEqual(binding.weapon_id,'pc:mount:horse:hooves')
        self.assertNotIn(step.state.participant('pc').weapon_inventory.active_item_id,bound_weapon_ids(bound,'pc'))
        self.assertFalse(can_leave_close_with_weapon(bound,'pc','minion1'))
        validate_briarroot_bindings(bound)

    def test_successful_defence_against_natural_melee_binds_the_natural_source(self):
        source=make_pc_melee_scenario(max_rounds=1)
        member=replace(source.party[0],shield=shield_loadout(PcWeaponHand.RIGHT),
            armour=ArmourLoadout(shield=ShieldKind.BRIARROOT))
        source=replace(source,party=(member,),enemies=(create_pc_book_npc(PcBookNpcProfile.HORSE,'minion1'),))
        result=run_pc_melee_scenario(source,SequenceRandom([10]*3+[1]*4+[10]*3+[1]*3))
        step=next(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='minion1')
        bound,_=react(Observation(step.state))
        binding,=bound.briarroot_bindings
        self.assertIs(binding.kind,BriarrootWeaponKind.NATURAL)
        self.assertIn(':natural:',binding.weapon_id)
        self.assertFalse(can_leave_close_with_weapon(bound,'minion1','pc'))
        validate_briarroot_bindings(bound)

    def test_actual_defence_creates_one_source_bound_weapon_binding(self):
        state,attack=actual_attack()
        updated,proof=react(state)
        binding,=updated.briarroot_bindings
        self.assertEqual((binding.bearer_id,binding.attacker_id),('minion1','pc'))
        self.assertEqual(binding.attack_id,attack.request.id)
        self.assertEqual(state.history[binding.attack_history_index],attack)
        self.assertTrue(updated.participant('pc').injury.conditions.has(Condition.BURDENED))
        self.assertFalse(can_leave_close_with_weapon(updated,'pc','minion1'))
        self.assertEqual(bound_weapon_ids(updated,'pc'),(binding.weapon_id,))
        validate_briarroot_bindings(updated)
        self.assertIsNone(expected_briarroot_update(updated))
        self.assertIs(proof.attack,attack)

    def test_player_briarroot_shield_uses_the_same_reaction_for_an_npc_attacker(self):
        state,_=actual_attack(pc_bearer=True)
        updated,_=react(state)
        binding,=updated.briarroot_bindings
        self.assertEqual((binding.bearer_id,binding.attacker_id),('pc','minion1'))
        self.assertTrue(updated.enemy('minion1').state.injury.conditions.has(Condition.BURDENED))
        self.assertEqual(external_briarroot_conditions(updated,'minion1'),frozenset((Condition.BURDENED,)))

    def test_double_zero_miss_is_not_a_successful_defence(self):
        state,attack=actual_attack(both_fail=True)
        self.assertEqual(attack.execution.resolution.attack.defender_test.successes,0)
        self.assertIsNone(expected_briarroot_update(state))

    def test_an_athletics_win_and_a_losing_defence_do_not_activate_the_shield(self):
        state,attack=actual_attack(athletics=True)
        self.assertIs(attack.protection.source_request.selected_skill,Skill.ATHLETICS)
        self.assertIsNone(expected_briarroot_update(state))
        state,attack=actual_attack(attacker_hits=True)
        self.assertGreater(attack.execution.resolution.attack.defender_test.successes,0)
        self.assertIsNone(expected_briarroot_update(state))

    def test_weapon_drop_removes_only_its_binding_and_does_not_rebind_after_pickup(self):
        state,_=actual_attack()
        bound,_=react(state)
        dropped=Observation(bound,party=(replace_pc_member(bound.party[0],weapon_hand=None),))
        cleaned,proof=react(dropped)
        self.assertEqual(proof.removed,((bound.briarroot_bindings[0].id,BriarrootReleaseReason.WEAPON_RELEASED),))
        self.assertEqual(cleaned.briarroot_bindings,())
        self.assertFalse(cleaned.participant('pc').injury.conditions.has(Condition.BURDENED))
        picked=Observation(cleaned,party=(replace_pc_member(cleaned.party[0],weapon_hand=state.party[0].weapon_hand),))
        self.assertIsNone(expected_briarroot_update(picked))
        validate_briarroot_bindings(cleaned)

    def test_heavy_armour_burden_survives_freeing_the_weapon(self):
        state,_=actual_attack(heavy=True)
        bound,_=react(state)
        dropped=Observation(bound,party=(replace_pc_member(bound.party[0],weapon_hand=None),))
        cleaned,_=react(dropped)
        self.assertEqual(cleaned.briarroot_bindings,())
        self.assertTrue(cleaned.participant('pc').injury.conditions.has(Condition.BURDENED))

    def test_stowing_the_actual_bound_weapon_is_not_a_free_release(self):
        state,_=actual_attack(inventory=True)
        bound,_=react(state)
        member=bound.participant('pc')
        item=member.weapon_inventory.active
        stowed=replace_pc_member(member,weapon_inventory=replace(member.weapon_inventory,
            items=(replace(item,location=PcItemLocation.CARRIED,grip=None),)))
        with self.assertRaises(ValueError):
            expected_briarroot_update(Observation(bound,party=(stowed,)))
        dropped=replace_pc_member(member,weapon_inventory=replace(member.weapon_inventory,
            items=(replace(item,location=PcItemLocation.DROPPED,grip=None),)))
        cleaned,_=react(Observation(bound,party=(dropped,)))
        self.assertEqual(cleaned.briarroot_bindings,())

    def test_shield_drop_cleans_the_briarroot_cause(self):
        state,_=actual_attack(pc_bearer=True)
        bound,_=react(state)
        member=replace_pc_member(bound.party[0],shield=PcShieldState(PcShieldLocation.DROPPED,None))
        cleaned,proof=react(Observation(bound,party=(member,)))
        self.assertEqual(proof.removed[0][1],BriarrootReleaseReason.SHIELD_RELEASED)
        self.assertFalse(cleaned.enemy('minion1').state.injury.conditions.has(Condition.BURDENED))

    def test_shield_bearer_moving_away_cleans_its_independent_cause(self):
        state,_=actual_attack(spatial=True)
        bound,_=react(state)
        origin=bound.battlefield.spatial.placement_for('minion1').zone_id
        destination=bound.battlefield.spatial.graph.adjacent_zone_ids(origin)[0]
        moved=with_actor_placement(bound.battlefield,'minion1',destination,close_to_ids=())
        cleaned,proof=react(Observation(bound,battlefield=moved))
        self.assertEqual(proof.removed[0][1],BriarrootReleaseReason.BEARER_LEFT_CLOSE)
        self.assertFalse(cleaned.participant('pc').injury.conditions.has(Condition.BURDENED))

    def test_defeated_bearer_cannot_keep_active_vines(self):
        state,_=actual_attack()
        bound,_=react(state)
        enemy=bound.enemy('minion1')
        defeated=replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,wounds=1,defeated=True)))
        cleaned,proof=react(Observation(bound,enemies=(defeated,)))
        self.assertEqual(proof.removed[0][1],BriarrootReleaseReason.ACTOR_UNAVAILABLE)
        self.assertFalse(cleaned.participant('pc').injury.conditions.has(Condition.BURDENED))

    def test_receipt_prefix_and_condition_cannot_be_removed_independently(self):
        state,_=actual_attack()
        bound,proof=react(state)
        with self.assertRaises(ValueError):
            validate_briarroot_bindings(Observation(bound,history=state.history))
        changed=replace(bound.party[0],injury=replace(bound.party[0].injury,
            conditions=bound.party[0].injury.conditions.without_condition(Condition.BURDENED)))
        with self.assertRaises(ValueError):
            validate_briarroot_bindings(Observation(bound,party=(changed,)))
        with self.assertRaises(ValueError):
            apply_briarroot_update(state,replace(proof,id='forged'))

    def test_binding_values_reject_duplicate_sources_and_equal_aliases(self):
        state,_=actual_attack()
        bound,proof=react(state)
        binding,=bound.briarroot_bindings
        with self.assertRaises(ValueError):
            replace(proof,bindings=(binding,binding))
        with self.assertRaises(ValueError):
            replace(binding,attack_history_index=True)
        with self.assertRaises(ValueError):
            replace(binding,bearer_id=binding.attacker_id)
        with self.assertRaises(TypeError):
            replace(proof,removed=((binding.id,'weapon_released'),))


class BriarrootRecoverTests(unittest.TestCase):
    def test_successful_brawn_recover_releases_the_selected_binding(self):
        state,_=actual_attack()
        bound,_=react(state)
        current=recover_slot(bound,'pc')
        binding,=current.briarroot_bindings
        self.assertEqual(briarroot_recovery_options(current,'pc'),(binding.id,))
        request=build_briarroot_release(current,binding.id)
        result=execute_recover_action(request,SequenceRandom((1,1,1)))
        proof=release_proof(current,request,result,())
        updates=apply_briarroot_release(current,proof)
        released=Observation(current,history=(*current.history,proof),**updates)
        self.assertFalse(released.participant('pc').injury.conditions.has(Condition.BURDENED))
        self.assertTrue(can_leave_close_with_weapon(released,'pc','minion1'))
        validate_briarroot_bindings(released)

    def test_failed_recover_spends_its_action_and_preserves_the_binding(self):
        state,_=actual_attack()
        bound,_=react(state)
        current=recover_slot(bound,'pc')
        binding,=current.briarroot_bindings
        request=build_briarroot_release(current,binding.id)
        result=execute_recover_action(request,SequenceRandom((10,10,10)))
        proof=release_proof(current,request,result,current.briarroot_bindings)
        updates=apply_briarroot_release(current,proof)
        self.assertEqual(updates['briarroot_bindings'],current.briarroot_bindings)
        self.assertTrue(updates['round_state'].active_turn.action_slots[0].executed)
        self.assertTrue(updates['party'][0].injury.conditions.has(Condition.BURDENED))

    def test_successful_recover_preserves_independent_armour_weight(self):
        state,_=actual_attack(heavy=True)
        bound,_=react(state)
        current=recover_slot(bound,'pc')
        binding,=current.briarroot_bindings
        request=build_briarroot_release(current,binding.id)
        result=execute_recover_action(request,SequenceRandom((1,1)))
        proof=release_proof(current,request,result,())
        updates=apply_briarroot_release(current,proof)
        self.assertEqual(updates['briarroot_bindings'],())
        self.assertTrue(updates['party'][0].injury.conditions.has(Condition.BURDENED))

    def test_release_receipt_cannot_claim_two_independent_bindings_for_one_test(self):
        state,_=actual_attack()
        bound,_=react(state)
        current=recover_slot(bound,'pc')
        binding,=current.briarroot_bindings
        request=build_briarroot_release(current,binding.id)
        result=execute_recover_action(request,SequenceRandom((1,1,1)))
        # This is the receipt value invariant, not a fabricated owner journal.
        other=PcBriarrootBinding('another-binding','another-bearer','pc',binding.weapon_id,
            'another-attack',binding.attack_history_index+1)
        with self.assertRaises(ValueError):
            PcBriarrootReleaseProof(request,result,binding.id,(binding,other),())
        proof=PcBriarrootReleaseProof(request,result,binding.id,(binding,other),(other,))
        self.assertEqual(proof.bindings,(other,))


if __name__=='__main__':
    unittest.main()
