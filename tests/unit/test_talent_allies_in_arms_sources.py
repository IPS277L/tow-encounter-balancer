"""Allies in Arms is one source-bound removal after an actual final Help Test."""
from copy import deepcopy
from dataclasses import FrozenInstanceError,replace
import pickle
import unittest

from tests.helpers import SequenceRandom
from tests.support.talent_sources import paid_talent,free_talent
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.help_models import HelpActionExecutionRequest
from towr.domain.talent_allies_in_arms_models import AlliesInArmsApplication
from towr.domain.talent_catalog import TalentId
from towr.domain.test_models import Skill,TestProfile,TestRequest,TestQuality,QualityModifier
from towr.domain.turn_models import (
    ActionSlotGrant,CombatActionDeclaration,CombatActionKind,CombatActionSlotRequest,
    CombatRoundState,CombatSide,CombatTurnParticipant,CombatTurnStartRequest,
)
from towr.rules.help_resolution import execute_help_action
from towr.rules.turn_resolution import reserve_combat_action_slot,start_combat_turn


STAGGERED=ConditionState(frozenset((Condition.STAGGERED,)))


def execution(*,conditions=STAGGERED,values=(10,10,10),skill=Skill.MELEE,
        side=CombatSide.PLAYERS_AND_ALLIES,test=None,decisions=None):
    opposite=(CombatSide.OPPOSITION if side is CombatSide.PLAYERS_AND_ALLIES
        else CombatSide.PLAYERS_AND_ALLIES)
    round=CombatRoundState(1,(CombatTurnParticipant('helper',side),
        CombatTurnParticipant('ally',side),CombatTurnParticipant('other-ally',side),
        CombatTurnParticipant('enemy',opposite)),side_order=(side,opposite))
    round=start_combat_turn(CombatTurnStartRequest('help:start',round,'helper')).state
    round=reserve_combat_action_slot(CombatActionSlotRequest('help:reserve',round,'helper',
        CombatActionDeclaration(CombatActionKind.HELP),ActionSlotGrant.STANDARD)).state
    request=HelpActionExecutionRequest('help:execute',round,'helper',conditions,'ally',
        'ally:upcoming-test',1,TestRequest('help:test',TestProfile(3,5)) if test is None else test,
        skill,skill)
    return execute_help_action(request,SequenceRandom(values),decisions=decisions)


def application(result,*,target='helper',previous=STAGGERED,talent=None):
    return AlliesInArmsApplication(result,paid_talent(TalentId.ALLIES_IN_ARMS) if talent is None else talent,
        target,previous)


class AlliesInArmsSourceTests(unittest.TestCase):
    def test_zero_success_help_removes_helper_staggered_without_changing_help_or_clock(self):
        previous=ConditionState(frozenset((Condition.STAGGERED,Condition.DRAINED)))
        result=execution(conditions=previous)
        applied=application(result,previous=previous)
        self.assertEqual(result.help_test_result.successes,0)
        self.assertEqual(result.bonus.bonus_dice,0)
        self.assertEqual(applied.conditions.conditions,frozenset((Condition.DRAINED,)))
        self.assertTrue(applied.previous.has(Condition.STAGGERED))
        self.assertEqual(applied.execution,result)
        self.assertEqual(len(applied.execution.round_state.active_turn.action_slots),1)
        self.assertTrue(applied.execution.slot.executed)
        with self.assertRaises(FrozenInstanceError):
            applied.target_id='ally'

    def test_ally_removal_keeps_independent_conditions_and_is_not_a_group_effect(self):
        result=execution(conditions=ConditionState(),values=(1,1,10))
        previous=ConditionState(frozenset((Condition.STAGGERED,Condition.DRAINED,Condition.PRONE)))
        applied=application(result,target='ally',previous=previous)
        self.assertEqual(applied.conditions.conditions,frozenset((Condition.DRAINED,Condition.PRONE)))
        self.assertEqual(result.help_test_result.successes,2)
        self.assertEqual(result.source_request.actor_conditions,ConditionState())
        for target in ('other-ally','enemy',('helper','ally'),True):
            with self.subTest(target=target),self.assertRaises((TypeError,ValueError)):
                application(result,target=target,previous=previous)

    def test_normal_help_for_both_sides_and_all_real_skills_uses_the_same_source(self):
        for side in CombatSide:
            for skill in (Skill.MELEE,Skill.DEFENCE,Skill.ATHLETICS,Skill.ENDURANCE,Skill.SHOOTING,
                    Skill.THROWING,Skill.BRAWN,Skill.DEXTERITY,Skill.AWARENESS,Skill.WILLPOWER):
                with self.subTest(side=side,skill=skill):
                    applied=application(execution(side=side,skill=skill))
                    self.assertFalse(applied.conditions.has(Condition.STAGGERED))
                    self.assertIs(applied.execution.source_request.help_skill,skill)

    def test_current_removed_state_cannot_be_reused_as_another_removal(self):
        first=application(execution())
        with self.assertRaises(ValueError):
            application(first.execution,previous=first.conditions)
        with self.assertRaises(ValueError):
            application(first.execution,previous=STAGGERED.with_condition(Condition.DRAINED))

    def test_helper_baseline_does_not_erase_new_post_test_critical_condition(self):
        applied=application(execution())
        # The owner applies the Staggered-only directive to its real post-Test
        # state. The baseline property is intentionally not that final state.
        after_test=STAGGERED.with_condition(Condition.CRITICALLY_INJURED)
        actual=after_test.without_condition(Condition.STAGGERED)
        self.assertTrue(actual.has(Condition.CRITICALLY_INJURED))
        self.assertEqual(applied.previous,STAGGERED)
        self.assertNotEqual(applied.conditions,actual)

    def test_paid_or_free_acquisition_is_retained_and_other_talents_reject(self):
        result=execution()
        for talent in (paid_talent(TalentId.ALLIES_IN_ARMS),free_talent(TalentId.ALLIES_IN_ARMS)):
            applied=application(result,talent=talent)
            self.assertEqual(applied.talent,talent)
            self.assertEqual(pickle.loads(pickle.dumps(applied)),applied)
        for talent in (TalentId.ALLIES_IN_ARMS,paid_talent(TalentId.HARDY),()):
            with self.subTest(talent=talent),self.assertRaises((TypeError,ValueError)):
                application(result,talent=talent)

    def test_changed_final_dice_profile_success_counter_or_receipt_are_rejected(self):
        result=execution(values=(1,10,10))
        bad=deepcopy(result)
        object.__setattr__(bad.help_test_result.trace,'successes',True)
        variants=[bad]
        bad=deepcopy(result)
        object.__setattr__(bad.source_request.help_test,'profile',TestProfile(3,6))
        variants.append(bad)
        bad=deepcopy(result)
        object.__setattr__(bad.help_test_result.trace,'final_values',(1,1,1))
        variants.append(bad)
        bad=deepcopy(result)
        object.__setattr__(bad.slot.execution,'actor_id','other-ally')
        variants.append(bad)
        bad=deepcopy(result)
        object.__setattr__(bad.round_state.active_turn,'action_slots',())
        variants.append(bad)
        bad=deepcopy(result)
        object.__setattr__(bad.source_request.round_state.participants[0],'side','players_and_allies')
        variants.append(bad)
        for bad in variants:
            with self.subTest(bad=bad),self.assertRaises((TypeError,ValueError)):
                application(bad)

    def test_foreign_bonus_source_and_noncanonical_condition_collection_reject(self):
        result=execution()
        bad=deepcopy(result)
        object.__setattr__(bad.bonus,'beneficiary_test_id','another:test')
        with self.assertRaises(ValueError):
            application(bad)
        previous=deepcopy(STAGGERED)
        object.__setattr__(previous,'conditions',{Condition.STAGGERED})
        with self.assertRaises(TypeError):
            application(result,previous=previous)

    def test_underlying_help_rejects_deafened_and_defenceless_helpers(self):
        for condition in (Condition.DEAFENED,Condition.DEFENCELESS):
            with self.subTest(condition=condition),self.assertRaises(ValueError):
                execution(conditions=STAGGERED.with_condition(condition))

    def test_grim_zero_success_and_legal_partial_glorious_rerolls_remain_actual_sources(self):
        grim=TestRequest('help:test',TestProfile(3,5),quality_modifiers=(
            QualityModifier('source:grim',TestQuality.GRIM),))
        grim_result=execution(test=grim,values=(1,10,1,10,10))
        self.assertEqual(grim_result.help_test_result.successes,0)
        self.assertFalse(application(grim_result).conditions.has(Condition.STAGGERED))
        class OneFailure:
            def choose_glorious_rerolls(self,*,request,initial_values,eligible_indices):
                return (eligible_indices[0],)
        glorious=TestRequest('help:test',TestProfile(3,5),quality_modifiers=(
            QualityModifier('source:glorious',TestQuality.GLORIOUS),))
        glorious_result=execution(test=glorious,values=(10,10,1,1),decisions=OneFailure())
        self.assertEqual(glorious_result.help_test_result.successes,2)
        self.assertEqual(len(glorious_result.help_test_result.trace.rerolls),1)
        self.assertFalse(application(glorious_result).conditions.has(Condition.STAGGERED))


if __name__=='__main__':
    unittest.main()
