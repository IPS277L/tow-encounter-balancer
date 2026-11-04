"""Complete actual Recover resolutions without another Test or RNG pass."""
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.unit.test_k1_recover_resolution import (
    active_round, reserve_action, recover_request, self_target, ally_target,
)
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.magic_models import WizardMagicState
from towr.domain.recover_models import (
    RecoverConditionRemovalChoice, RecoverMode, RecoverObjectInteractionFollowUp,
    RecoverStandardChoice, RecoverStandardResult,
    _expected_recover_execution, _expected_standard_changes, _validate_recover_action,
)
from towr.domain.test_models import Skill, TestProfile, TestRequest
from towr.domain.turn_models import CombatActionKind
from towr.rules.recover_resolution import execute_recover_action


class NoRandom:
    def randint(self, low, high):
        raise AssertionError('a completed/standard Recover must not roll')


def standard_source():
    own = ConditionState({Condition.STAGGERED,Condition.DISTRACTED})
    ally = ConditionState({Condition.PRONE,Condition.DEFENCELESS})
    choice = RecoverStandardChoice(WizardMagicState(miscast_dice=2),
        staggered_target=self_target(own),prone_target=ally_target(ally),
        object_interaction=RecoverObjectInteractionFollowUp('pickup','hero','weapon',True))
    return recover_request(reserve_action(active_round(),CombatActionKind.RECOVER),
        actor_conditions=own,mode=RecoverMode.STANDARD,choice=choice)


def standard_resolution(choice):
    removed = min(1,choice.magic_state.miscast_dice)
    return RecoverStandardResult(choice,_expected_standard_changes(choice),choice.magic_state,
        replace(choice.magic_state,miscast_dice=choice.magic_state.miscast_dice-removed),
        removed,choice.mount,choice.object_interaction)


class RecoverCompletionTests(unittest.TestCase):
    def test_mixed_targets_keep_independent_conditions_and_exact_slot_clock(self):
        request = standard_source()
        actual = execute_recover_action(request,NoRandom())
        completed = _expected_recover_execution(request,standard_resolution(request.choice))
        self.assertEqual(completed,actual)
        own,ally = completed.resolution.condition_changes
        self.assertEqual((own.entity_id,own.conditions),('hero',ConditionState({Condition.DISTRACTED})))
        self.assertEqual((ally.entity_id,ally.conditions),('ally',ConditionState({Condition.DEFENCELESS})))
        self.assertEqual(own.removed_conditions,(Condition.STAGGERED,))
        self.assertEqual(ally.removed_conditions,(Condition.PRONE,))
        self.assertEqual(completed.resolution.magic_state.miscast_dice,1)
        self.assertEqual(completed.resolution.object_interaction_follow_up.object_id,'weapon')
        receipt = completed.slot.execution
        self.assertEqual((receipt.actor_id,receipt.round_number,receipt.slot_index),('hero',1,1))
        self.assertEqual(receipt.result_request_id,request.id)
        self.assertEqual(completed.round_state.active_turn.action_slots,(completed.slot,))
        self.assertEqual(replace(completed.round_state,active_turn=request.round_state.active_turn),request.round_state)

    def test_zero_benefits_and_both_ally_conditions_complete_without_a_roll(self):
        request = standard_source()
        for choice in (RecoverStandardChoice(WizardMagicState()),
                RecoverStandardChoice(WizardMagicState(),
                    staggered_target=ally_target(ConditionState({Condition.STAGGERED,Condition.PRONE})),
                    prone_target=ally_target(ConditionState({Condition.STAGGERED,Condition.PRONE})))):
            with self.subTest(choice=choice):
                result = execute_recover_action(replace(request,choice=choice),NoRandom())
                self.assertEqual(result,_expected_recover_execution(replace(request,choice=choice),result.resolution))
                self.assertEqual(len(result.resolution.condition_changes),int(choice.prone_target is not None))
                if choice.prone_target is not None:
                    self.assertEqual(result.resolution.condition_changes[0].conditions,ConditionState())

    def test_existing_condition_test_is_completed_once_and_keeps_result_id(self):
        conditions = ConditionState({Condition.BLINDED,Condition.DISTRACTED})
        choice = RecoverConditionRemovalChoice(self_target(conditions),Condition.BLINDED,
            TestRequest('remove-blinded-test',TestProfile(2,5)),Skill.AWARENESS,True)
        request = recover_request(reserve_action(active_round(),CombatActionKind.RECOVER),
            actor_conditions=conditions,mode=RecoverMode.REMOVE_CONDITION,choice=choice)
        result = execute_recover_action(request,SequenceRandom([1,10]))
        completed = _expected_recover_execution(request,result.resolution)
        self.assertEqual(completed,result)
        self.assertEqual(completed.slot.execution.result_request_id,'remove-blinded-test')
        self.assertEqual(completed.resolution.conditions,ConditionState({Condition.DISTRACTED}))
        self.assertEqual(completed.resolution.test_result.trace.initial_values,(1,10))

    def test_unavailable_actions_reject_before_alternative_test_rng(self):
        for conditions,enemy,kind,reserved in (
                (ConditionState({Condition.BLINDED,Condition.DEFENCELESS}),False,CombatActionKind.RECOVER,True),
                (ConditionState({Condition.BLINDED,Condition.BROKEN}),True,CombatActionKind.RECOVER,True),
                (ConditionState({Condition.BLINDED}),False,CombatActionKind.ATTACK,True),
                (ConditionState({Condition.BLINDED}),False,CombatActionKind.RECOVER,False)):
            with self.subTest(conditions=conditions,kind=kind,reserved=reserved):
                state = reserve_action(active_round(),kind) if reserved else active_round()
                choice = RecoverConditionRemovalChoice(self_target(conditions),Condition.BLINDED,
                    TestRequest('remove-blinded-test',TestProfile(2,5)),Skill.AWARENESS,True)
                request = recover_request(state,actor_conditions=conditions,
                    actor_has_enemy_in_zone=enemy,mode=RecoverMode.REMOVE_CONDITION,choice=choice)
                with self.assertRaises(ValueError):
                    execute_recover_action(request,NoRandom())
                with self.assertRaises(ValueError):
                    _validate_recover_action(request)

    def test_completion_refuses_consumed_slot_foreign_resolution_and_untyped_input(self):
        request = standard_source()
        result = execute_recover_action(request,NoRandom())
        with self.assertRaises(ValueError):
            _expected_recover_execution(replace(request,round_state=result.round_state),result.resolution)
        other = standard_resolution(replace(request.choice,magic_state=WizardMagicState()))
        with self.assertRaises(ValueError):
            _expected_recover_execution(request,other)
        for value in (None,object()):
            with self.assertRaises(TypeError):
                _expected_recover_execution(value,result.resolution)
            with self.assertRaises(TypeError):
                _expected_recover_execution(request,value)


if __name__=='__main__':
    unittest.main()
