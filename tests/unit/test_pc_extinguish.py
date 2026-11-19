"""Prepared Recover and replay boundaries, not fabricated complete journals."""
from dataclasses import fields,replace
from types import SimpleNamespace
import unittest

from tests.support.pc_tactics_fixtures import automatic_source
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.armour_models import ArmourLoadout,BodyArmour,body_resilience_bonus
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.generated_npc_models import GeneratedNpc
from towr.domain.injury_models import (
    WoundEntryId,WoundRecord,WoundRestriction,WoundRestrictionEffect,WoundEffectDuration,
)
from towr.domain.pc_extinguish_models import (
    PcExtinguishProof,build_pc_extinguish,project_pc_extinguish,extinguish_value,
)
from towr.domain.pc_melee_models import PcFatePolicy
from towr.domain.pc_melee_result_models import PcFateDecline,initial_pc_melee_state
from towr.domain.pc_magic_models import PcMagicModifier,PcMagicTaskKind
from towr.domain.recover_models import RecoverMode
from towr.domain.test_models import InlineProfile,Skill,TestQuality
from towr.domain.turn_models import CombatActionKind,CombatActionDeclaration,CombatActionSlotRequest,ActionSlotGrant,CombatTurnStartRequest
from towr.domain.weapon_inventory_models import WeaponItemSource,WeaponItemLocation,WeaponGrip
from towr.domain.weapon_catalog import WeaponKind
from towr.rules.recover_resolution import execute_recover_action
from towr.rules.turn_resolution import reserve_combat_action_slot,start_combat_turn


def prepared(*,npc=False,conditions=(Condition.ABLAZE,),armour=None,reserved=True):
    source=automatic_source(pc_count=1,enemy_count=1,rounds=2)
    pc=replace(source.party[0],pc=replace(source.party[0].pc,agility=2,toughness=2,athletics=5,endurance=5,
        armour_bonus=body_resilience_bonus(armour) if armour is not None else 0),
        fate_policy=PcFatePolicy.DECLINE_OPTIONAL_FATE,armour=armour)
    enemy=GeneratedNpc(3,3,2,2,4,5,
        (WeaponItemSource('staff',WeaponKind.STAFF,WeaponItemLocation.HELD,WeaponGrip.LEFT),),
        armour or ArmourLoadout(),defence=4,endurance=5)
    source=replace(source,party=(pc,),enemies=(enemy.participant(source.enemy_activation_order[0]),))
    actor=source.enemy_activation_order[0] if npc else source.pc_activation_order[0]
    actual=initial_pc_melee_state(source)
    state=SimpleNamespace(**{field.name:getattr(actual,field.name) for field in fields(actual)})
    state.exited_npc_ids=actual.exited_npc_ids
    clock=replace(actual.round_state,side_order=tuple(reversed(actual.round_state.side_order))) if npc else actual.round_state
    state.round_state=start_combat_turn(CombatTurnStartRequest('prepared:start',clock,actor)).state
    if npc:
        old=state.enemies[0]
        state.enemies=(replace(old,state=replace(old.state,injury=replace(old.state.injury,
            conditions=ConditionState(frozenset(conditions))))),)
    else:
        state.party=(replace(state.party[0],injury=replace(state.party[0].injury,
            conditions=ConditionState(frozenset(conditions)))),)
    state.participant=lambda actor:next(member for member in state.party if member.actor_id==actor)
    state.enemy=lambda actor:next(enemy for enemy in state.enemies if enemy.state.actor_id==actor)
    state.live_party=tuple(member for member in state.party if not member.injury.dead)
    state.live_enemies=tuple(enemy for enemy in state.enemies if not enemy.state.injury.defeated)
    if reserved:
        state.round_state=reserve_combat_action_slot(CombatActionSlotRequest('prepared:recover',state.round_state,
            actor,CombatActionDeclaration(CombatActionKind.RECOVER),ActionSlotGrant.STANDARD)).state
    return state,actor


def proof_for(state,values):
    request=build_pc_extinguish(state)
    rng=ScriptedD10(values)
    result=execute_recover_action(request,rng)
    rng.assert_exhausted()
    decline=(PcFateDecline(request.actor_id,request.choice.test.id,'test',
        state.source.participant(request.actor_id).fate_policy)
        if request.actor_id in state.source.pc_activation_order else None)
    return PcExtinguishProof(request,result,decline)


class PcExtinguishTests(unittest.TestCase):
    def test_pc_request_is_a_real_alternate_recover_with_its_athletics(self):
        state,actor=prepared()
        request=build_pc_extinguish(state)
        self.assertIs(request.mode,RecoverMode.REMOVE_CONDITION)
        self.assertEqual(request.choice.target.entity_id,actor)
        self.assertIs(request.choice.condition,Condition.ABLAZE)
        self.assertIs(request.choice.test_skill,Skill.ATHLETICS)
        self.assertEqual((request.choice.test.profile.base_dice,request.choice.test.profile.threshold),(2,5))
        self.assertIsNone(request.healing_potion)
        self.assertFalse(hasattr(request.choice,'object_interaction'))

    def test_success_removes_only_ablaze_and_preserves_items_fate_and_other_conditions(self):
        remaining=(Condition.STAGGERED,Condition.PRONE,Condition.BURDENED)
        for npc in (False,True):
            with self.subTest(npc=npc):
                state,actor=prepared(npc=npc,conditions=(Condition.ABLAZE,*remaining))
                before=state.enemy(actor) if npc else state.participant(actor)
                proof=proof_for(state,(1,10))
                updates=project_pc_extinguish(state,proof)
                after=updates['enemies'][0].state if npc else updates['party'][0]
                original=before.state if npc else before
                self.assertEqual(after.injury.conditions,ConditionState(frozenset(remaining)))
                self.assertEqual(after.weapon_inventory,original.weapon_inventory)
                self.assertEqual(after.injury.wounds,original.injury.wounds)
                self.assertTrue(updates['round_state'].active_turn.action_slots[-1].executed)
                self.assertNotIn('battlefield',updates)
                if not npc:self.assertEqual(after.fate,original.fate)

    def test_failure_still_uses_one_action_without_free_standard_benefits(self):
        for npc in (False,True):
            with self.subTest(npc=npc):
                state,actor=prepared(npc=npc,conditions=(Condition.ABLAZE,Condition.STAGGERED,Condition.PRONE))
                proof=proof_for(state,(10,10))
                updates=project_pc_extinguish(state,proof)
                injury=updates['enemies'][0].state.injury if npc else updates['party'][0].injury
                self.assertEqual(injury.conditions,proof.request.actor_conditions)
                self.assertFalse(proof.result.resolution.removed)
                self.assertTrue(updates['round_state'].active_turn.action_slots[-1].executed)

    def test_real_athletics_consumes_next_test_grim_and_keeps_action_critical_price(self):
        state,actor=prepared()
        member=state.participant(actor)
        wounds=(WoundRecord(1,WoundEntryId.SCARRING_STRIKE,15,(5,10),effect_resolved=True),
            WoundRecord(2,WoundEntryId.CRUSHED_RIB,10,(5,5),effect_resolved=True))
        effects=(WoundRestrictionEffect(1,WoundRestriction.NON_FACE_PROTECTION_ACTION_CAUSES_CRITICAL,
                WoundEffectDuration.UNTIL_TREATED),
            WoundRestrictionEffect(2,WoundRestriction.NEXT_TEST_IS_GRIM,WoundEffectDuration.NEXT_TEST))
        state.party=(replace(member,injury=replace(member.injury,wounds=wounds,active_wound_effects=effects)),)
        request=build_pc_extinguish(state)
        self.assertTrue(any(quality.quality is TestQuality.GRIM for quality in request.choice.test.quality_modifiers))
        proof=proof_for(state,(1,10,1))
        after=project_pc_extinguish(state,proof)['party'][0]
        self.assertFalse(after.injury.conditions.has(Condition.ABLAZE))
        self.assertTrue(after.injury.conditions.has(Condition.CRITICALLY_INJURED))
        self.assertEqual(after.injury.wounds,wounds)
        self.assertFalse(any(isinstance(effect,WoundRestrictionEffect)
            and effect.restriction is WoundRestriction.NEXT_TEST_IS_GRIM for effect in after.injury.active_wound_effects))

    def test_npc_uses_actual_athletics_and_cannot_invent_fate(self):
        state,actor=prepared(npc=True)
        proof=proof_for(state,(1,10))
        self.assertEqual(proof.request.choice.test.profile,InlineProfile(2,5))
        decline=PcFateDecline(actor,proof.request.choice.test.id,'test',PcFatePolicy.DECLINE_OPTIONAL_FATE)
        with self.assertRaises(ValueError):project_pc_extinguish(state,replace(proof,fate_decline=decline))

    def test_builder_rejects_unreserved_executed_missing_fire_or_defenceless_contexts(self):
        for changes in (dict(reserved=False),dict(conditions=()),dict(conditions=(Condition.ABLAZE,Condition.DEFENCELESS))):
            with self.subTest(changes=changes):
                state,_=prepared(**changes)
                with self.assertRaises(ValueError):build_pc_extinguish(state)
        state,_=prepared()
        proof=proof_for(state,(1,10))
        state.round_state=proof.result.round_state
        with self.assertRaises(ValueError):build_pc_extinguish(state)

    def test_preparation_preserves_real_armour_magic_and_blinded_penalties(self):
        armour=ArmourLoadout((BodyArmour.HEAVY,),BodyArmour.HEAVY)
        for npc in (False,True):
            with self.subTest(npc=npc):
                state,actor=prepared(npc=npc,armour=armour,conditions=(Condition.ABLAZE,Condition.BLINDED,Condition.DRAINED))
                state.magic_modifiers=(PcMagicModifier('actual:one-use',actor,PcMagicTaskKind.NEXT_TEST_PENALTY),)
                test=build_pc_extinguish(state).choice.test
                self.assertEqual(sum(mod.amount for mod in test.dice_modifiers),-2)
                self.assertTrue(any(mod.quality is TestQuality.GRIM for mod in test.quality_modifiers))

    def test_source_result_and_actual_roll_forgery_are_rejected_without_new_rng(self):
        state,_=prepared()
        proof=proof_for(state,(1,10))
        changed=replace(proof.request,id=proof.request.id+':fake')
        with self.assertRaises(ValueError):project_pc_extinguish(state,replace(proof,request=changed))
        wrong=proof_for(state,(10,10))
        with self.assertRaises(ValueError):project_pc_extinguish(state,replace(proof,result=wrong.result,
            request=replace(proof.request,choice=replace(proof.request.choice,test=replace(
                proof.request.choice.test,id='forged-test')))))
        with self.assertRaises(TypeError):project_pc_extinguish(state,replace(proof,result=None))

    def test_value_uses_exact_small_distributions_without_sampling_or_mutating_source(self):
        for npc in (False,True):
            with self.subTest(npc=npc):
                state,actor=prepared(npc=npc,reserved=False)
                original=state.party,state.enemies,state.round_state
                # Ath2d/5 succeeds with .75; End2d/5 has shortfall1 at Hazard2.
                self.assertAlmostEqual(extinguish_value(state,actor),1.5)
                self.assertEqual((state.party,state.enemies,state.round_state),original)
        state,actor=prepared(conditions=(),reserved=False)
        self.assertEqual(extinguish_value(state,actor),0)
        with self.assertRaises(ValueError):extinguish_value(state,'absent')
