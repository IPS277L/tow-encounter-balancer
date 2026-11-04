"""Standard Recover has explicit recipients and no imaginary healing/Test."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario,make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_m12_pc_heavy_wounds import heavy_prefix
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.injury_models import WoundConditionEffect,WoundEffectDuration,WoundRestriction,WoundRestrictionEffect
from towr.domain.pc_ally_recover_models import (
    expected_pc_standard_recover,pc_after_standard_recover,pc_ally_recover_beneficiary,
)
from towr.domain.pc_melee_models import PcAllyRecoverPolicy,PcMeleePolicy
from towr.domain.pc_melee_result_models import (
    PcRecoverProof,PcAttackProof,PcTurnEndProof,PcMeleeOutcome,PcMeleeStep,
    initial_pc_melee_state,build_pc_melee_recover,pc_melee_selected_action,
)
from towr.domain.turn_models import (CombatActionKind,CombatTurnStartRequest,CombatActionSlotRequest,
    CombatActionDeclaration,ActionSlotGrant)
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step
from towr.rules.turn_resolution import start_combat_turn,reserve_combat_action_slot


def ally_source(*, actor='pc1',beneficiary='pc2',enemies=2,rounds=2):
    source=make_pc_melee_party_scenario(enemy_count=enemies,max_rounds=rounds)
    return replace(source,party=tuple(replace(member,
        policy=PcMeleePolicy.RECOVER_ALLY_OR_ATTACK_OR_RECOVER_SELF,
        ally_recover_policy=PcAllyRecoverPolicy(beneficiary)) if member.actor_id==actor else member
        for member in source.party))


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def recover_steps(result):
    return tuple(step for step in result.steps if isinstance(step.proof,PcRecoverProof))


def pure_active(source,actor='pc1'):
    """A preparation/projection boundary, not a claim of a native prefix."""
    state=initial_pc_melee_state(source)
    clock=start_combat_turn(CombatTurnStartRequest('pure:start',state.round_state,actor)).state
    return replace(state,round_state=clock)


def pure_reserved(state):
    actor=state.round_state.active_turn.actor_id
    clock=reserve_combat_action_slot(CombatActionSlotRequest('pure:reserve',state.round_state,actor,
        CombatActionDeclaration(CombatActionKind.RECOVER),ActionSlotGrant.STANDARD)).state
    return replace(state,round_state=clock)


def pure_member(state,actor,*,conditions=(),effects=(),hand='unchanged',dead=False):
    member=state.participant(actor)
    injury=member.injury
    if effects and not injury.wounds:
        actual=execute(make_pc_melee_scenario(enemy_count=3,max_rounds=1),heavy_prefix(13))
        injury=replace(injury,wounds=actual.state.party[0].injury.wounds)
    changed=replace(member,injury=replace(injury,conditions=ConditionState(frozenset(conditions)),
        active_wound_effects=effects,dead=dead),
        weapon_hand=member.weapon_hand if hand=='unchanged' else hand)
    return replace(state,party=tuple(changed if item.actor_id==actor else item for item in state.party))


class PcAllyRecoverTests(unittest.TestCase):
    def test_native_later_healer_removes_already_acted_ally_stagger_without_rng(self):
        source=ally_source(actor='pc2',beneficiary='pc1',rounds=1)
        result=execute(source,[10,10,10,1,1]+[10,10,1,1,1]*2)
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
        step,=recover_steps(result)
        request=step.proof.result.source_request
        self.assertEqual(request.actor_id,'pc2')
        self.assertEqual(request.choice.staggered_target.entity_id,'pc1')
        self.assertIs(request.choice.staggered_target.in_close_range,True)
        self.assertFalse(step.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(step.state.participant('pc2').injury,step.source.participant('pc2').injury)
        self.assertEqual(result.executed_actions,4)

    def test_native_ally_first_removes_ally_stagger_and_preserves_actor_stagger(self):
        source=ally_source()
        result=execute(source,[10,10,10,1,1]*2+[10,10,1,1,1]*2
            +[1,1,1,10,10]+[10,10,1,1,1])
        step,=recover_steps(result)
        self.assertEqual(step.proof.result.source_request.choice.staggered_target.entity_id,'pc2')
        self.assertTrue(step.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(step.state.participant('pc2').injury.conditions.has(Condition.STAGGERED))
        ally_attack=next(step for step in result.steps if isinstance(step.proof,PcAttackProof)
            and step.source.round_state.round_number==2)
        self.assertEqual(ally_attack.proof.request.actor_id,'pc2')

    def test_native_mixed_self_stagger_and_ally_prone_gives_w13_critical_only_to_ally(self):
        source=replace(ally_source(enemies=3),enemy_target_priority=('pc2','pc1'))
        values=([10,10,10,1,1]*2+[1,1,1,10,10,10,1]
            +[1,1,1,10,10,10,1,1]+[1,1,1,10,10,10,5,4,4]
            +[1,1,1,10,10]+[1,10,10]+[10,10,1,1,1]*2)
        result=execute(source,values)
        step,=recover_steps(result)
        choice=step.proof.result.source_request.choice
        self.assertEqual((choice.staggered_target.entity_id,choice.prone_target.entity_id),('pc1','pc2'))
        self.assertFalse(step.state.participant('pc1').injury.conditions.has(Condition.CRITICALLY_INJURED))
        ally=step.state.participant('pc2')
        self.assertFalse(ally.injury.conditions.has(Condition.PRONE))
        self.assertTrue(ally.injury.conditions.has(Condition.CRITICALLY_INJURED))
        critical=next(step for step in result.steps if isinstance(step.proof,PcTurnEndProof)
            and step.proof.critical is not None)
        self.assertEqual(critical.source.round_state.active_turn.actor_id,'pc2')
        self.assertEqual(critical.source.round_state.round_number,2)
        self.assertEqual(ally.fate,step.source.participant('pc2').fate)
        self.assertEqual(ally.daily_wounds,step.source.participant('pc2').daily_wounds)

    def test_native_self_prone_priority_can_clear_other_ally_stagger_in_same_action(self):
        source=ally_source(enemies=3)
        values=([10,10,10,1,1]*2+[1,1,1,10,10,10,1]
            +[1,1,1,10,10,10,1,1]+[1,1,1,10,10,10,5,4,4]
            +[1,10,10]+[1,1,1,10,10]+[10,10,1,1,1]*2)
        result=execute(source,values)
        step,=recover_steps(result)
        choice=step.proof.result.source_request.choice
        self.assertEqual((choice.staggered_target.entity_id,choice.prone_target.entity_id),('pc2','pc1'))
        self.assertTrue(step.state.participant('pc1').injury.conditions.has(Condition.CRITICALLY_INJURED))
        self.assertFalse(step.state.participant('pc2').injury.conditions.has(Condition.CRITICALLY_INJURED))

    def test_native_own_weapon_pickup_and_ally_condition_removal_share_one_action(self):
        result=execute(ally_source(),[10,10,10,1,1]*2
            +[1,1,10,10,10,4,10,10,10,1]+[10,10,1,1,1]
            +[1,1,1,10,10]+[10,10,1,1,1])
        step,=recover_steps(result)
        self.assertIsNone(step.source.participant('pc1').weapon_hand)
        self.assertIsNotNone(step.state.participant('pc1').weapon_hand)
        choice=step.proof.result.source_request.choice
        self.assertEqual(choice.object_interaction.actor_id,'pc1')
        self.assertEqual(choice.staggered_target.entity_id,'pc2')
        self.assertFalse(step.state.participant('pc2').injury.conditions.has(Condition.STAGGERED))

    def test_native_actor_w14_recover_exception_and_w15_action_critical_are_preserved(self):
        for total in (14,15):
            with self.subTest(total=total):
                values=([10,10,10,1,1]*2+[1,1,1,10,10,10,1]
                    +[1,1,1,10,10,10,1,1]+[1,1,1,10,10,10,5,5,total-10])
                if total==15:
                    values += [1,10,10]
                values += [1,1,1,10,10]+[10,10,1,1,1]*2
                result=execute(ally_source(enemies=3),values)
                step,=recover_steps(result)
                actor=step.state.participant('pc1')
                self.assertEqual(step.proof.result.source_request.choice.staggered_target.entity_id,'pc2')
                self.assertEqual(actor.injury.conditions.has(Condition.CRITICALLY_INJURED),total==15)
                self.assertEqual(actor.injury.conditions.has(Condition.DRAINED),total==14)
                if total==15:
                    self.assertTrue(actor.injury.conditions.has(Condition.STAGGERED))
                self.assertFalse(step.state.participant('pc2').injury.conditions.has(Condition.CRITICALLY_INJURED))

    def test_pure_ongoing_stagger_or_prone_is_not_removed_or_selected(self):
        for condition,duration in ((Condition.STAGGERED,WoundEffectDuration.UNTIL_HEALED),
                (Condition.PRONE,WoundEffectDuration.UNTIL_TREATED)):
            with self.subTest(condition=condition):
                state=pure_active(ally_source())
                state=pure_member(state,'pc2',conditions=(condition,),
                    effects=(WoundConditionEffect(1,condition,duration),))
                self.assertIsNone(pc_ally_recover_beneficiary(state))
                self.assertIs(pc_melee_selected_action(state),CombatActionKind.ATTACK)
        state=pure_member(pure_active(ally_source()),'pc1',hand=None)
        state=pure_member(state,'pc2',conditions=(Condition.PRONE,),
            effects=(WoundConditionEffect(1,Condition.PRONE,WoundEffectDuration.UNTIL_TREATED),))
        request=build_pc_melee_recover(state)
        self.assertIsNone(request.choice.prone_target)
        self.assertIsNotNone(request.choice.object_interaction)

    def test_pure_defenceless_ally_can_lose_stagger_but_is_not_revived_or_cured(self):
        state=pure_active(ally_source())
        state=pure_member(state,'pc2',conditions=(Condition.STAGGERED,Condition.DEFENCELESS,Condition.CRITICALLY_INJURED))
        state=pure_reserved(state)
        request=build_pc_melee_recover(state)
        result=expected_pc_standard_recover(request)
        party=pc_after_standard_recover(state,request,result)
        ally=party[1]
        self.assertFalse(ally.injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(ally.injury.conditions.has(Condition.DEFENCELESS))
        self.assertTrue(ally.injury.conditions.has(Condition.CRITICALLY_INJURED))
        self.assertFalse(ally.injury.dead)

    def test_pure_dead_ally_falls_back_without_removal_or_resource_change(self):
        state=pure_member(pure_active(ally_source()),'pc2',conditions=(Condition.STAGGERED,),dead=True)
        self.assertIsNone(pc_ally_recover_beneficiary(state))
        self.assertIs(pc_melee_selected_action(state),CombatActionKind.ATTACK)

    def test_pure_receiving_aid_does_not_trigger_w14_w15_or_consume_next_test_grim(self):
        effects=(WoundRestrictionEffect(1,WoundRestriction.NON_RECOVER_ACTION_CAUSES_CRITICAL,WoundEffectDuration.UNTIL_TREATED),
            WoundRestrictionEffect(2,WoundRestriction.NON_FACE_PROTECTION_ACTION_CAUSES_CRITICAL,WoundEffectDuration.UNTIL_TREATED),
            WoundRestrictionEffect(3,WoundRestriction.NEXT_TEST_IS_GRIM,WoundEffectDuration.UNTIL_REMOVED))
        state=pure_member(pure_active(ally_source()),'pc2',conditions=(Condition.STAGGERED,),effects=effects)
        state=pure_reserved(state)
        request=build_pc_melee_recover(state)
        result=expected_pc_standard_recover(request)
        party=pc_after_standard_recover(state,request,result)
        self.assertFalse(party[1].injury.conditions.has(Condition.CRITICALLY_INJURED))
        self.assertEqual(party[1].injury.active_wound_effects,effects)
        self.assertEqual(party[1].fate,state.party[1].fate)

    def test_pure_ally_removal_strips_only_its_removed_effect_and_keeps_other_sources(self):
        actor_effect=WoundConditionEffect(1,Condition.BLINDED,WoundEffectDuration.END_OF_NEXT_TURN)
        prone_effect=WoundConditionEffect(3,Condition.PRONE,WoundEffectDuration.UNTIL_REMOVED)
        restriction=WoundRestrictionEffect(3,WoundRestriction.REMOVING_PRONE_CAUSES_CRITICAL,
            WoundEffectDuration.UNTIL_TREATED)
        state=pure_member(pure_active(ally_source()),'pc1',conditions=(Condition.BLINDED,),effects=(actor_effect,))
        state=pure_member(state,'pc2',conditions=(Condition.PRONE,),effects=(prone_effect,restriction))
        state=pure_reserved(state)
        request=build_pc_melee_recover(state)
        result=expected_pc_standard_recover(request)
        party=pc_after_standard_recover(state,request,result)
        self.assertEqual(party[0].injury.active_wound_effects,(actor_effect,))
        self.assertNotIn(prone_effect,party[1].injury.active_wound_effects)
        self.assertIn(restriction,party[1].injury.active_wound_effects)
        self.assertTrue(party[1].injury.conditions.has(Condition.CRITICALLY_INJURED))
        for before,after in zip(state.party,party,strict=True):
            self.assertEqual((after.injury.wounds,after.daily_wounds,after.fate,after.body_facts),
                (before.injury.wounds,before.daily_wounds,before.fate,before.body_facts))

    def test_native_full_result_receipts_reject_foreign_headers_ranges_changes_and_replay(self):
        result=execute(ally_source(actor='pc2',beneficiary='pc1',rounds=1),
            [10,10,10,1,1]+[10,10,1,1,1]*2)
        step,=recover_steps(result)
        for field in ('request_id','rule_id','applied_rule_ids'):
            with self.subTest(field=field):
                proof=deepcopy(step.proof)
                value=getattr(proof.result,field)
                text=value[0] if type(value) is tuple else value
                alias=Enum('ForeignString',{'VALUE':text},type=str).VALUE
                object.__setattr__(proof.result,field,(alias,*value[1:]) if type(value) is tuple else alias)
                self.assertEqual(proof,step.proof)
                with self.assertRaises(TypeError):
                    PcMeleeStep(step.source,proof)
        proof=deepcopy(step.proof)
        object.__setattr__(proof.result.resolution.condition_changes[0],'entity_id','pc2')
        with self.assertRaises(ValueError):
            PcMeleeStep(step.source,proof)
        proof=deepcopy(step.proof)
        object.__setattr__(proof.result.source_request.choice.staggered_target,'in_close_range',1)
        self.assertEqual(proof,step.proof)
        with self.assertRaises(TypeError):
            PcMeleeStep(step.source,proof)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(step.state,step)


if __name__=='__main__':
    unittest.main()
