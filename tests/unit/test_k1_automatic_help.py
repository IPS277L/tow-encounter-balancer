"""No-Test Help spends a real action and binds a typed effect to one allied Test."""
from copy import deepcopy
from dataclasses import MISSING,fields,replace
import inspect
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_help_resolution import active_round,reserve_action
from towr.domain.automatic_help_models import (
    AUTOMATIC_HELP_ACTION_RULE_ID,AutomaticHelpActionRequest,AutomaticHelpActionResult,
    AutomaticHelpBonusSnapshot,AutomaticHelpBonusApplicationRequest,AutomaticHelpEffectKind,
    expected_automatic_help_action,
)
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.test_models import DiceModifier,SuccessModifier,InlineProfile,Skill,TestRequest,QualityModifier,TestQuality
from towr.domain.turn_models import (
    ActionSlotGrant,CombatActionDeclaration,CombatActionKind,CombatActionSlotRequest,
    CombatRoundState,CombatSide,CombatTurnEndRequest,CombatTurnParticipant,CombatTurnStartRequest,
)
from towr.rules.automatic_help_resolution import execute_automatic_help_action,apply_automatic_help_bonus
from towr.rules.test_resolution import resolve_test
from towr.rules.turn_resolution import start_combat_turn,reserve_combat_action_slot,end_combat_turn


SOURCE_RULE='RULE-PROFILE-TALABEC-001:torches-and-pitchforks'
SUCCESS_RULE='RULE-PROFILE-GREENSKIN-004:power-of-the-waaagh'
DIE=AutomaticHelpEffectKind.BONUS_DIE_BEYOND_CAP
SUCCESS=AutomaticHelpEffectKind.FREE_SUCCESS


def request(kind=DIE):
    return AutomaticHelpActionRequest('automatic-help',reserve_action(active_round(),CombatActionKind.HELP),
        'helper',ConditionState(),'ally','beneficiary:test',1,Skill.MELEE,
        SUCCESS_RULE if kind is SUCCESS else SOURCE_RULE,kind)


def application(help_result=None,test=None):
    return AutomaticHelpBonusApplicationRequest('apply-automatic-help',
        help_result or execute_automatic_help_action(request()),'ally',Skill.MELEE,
        test or TestRequest('beneficiary:test',InlineProfile(2,3)))


def two_help_results(kinds):
    clock=CombatRoundState(1,(
        CombatTurnParticipant('helper1',CombatSide.PLAYERS_AND_ALLIES),
        CombatTurnParticipant('helper2',CombatSide.PLAYERS_AND_ALLIES),
        CombatTurnParticipant('ally',CombatSide.PLAYERS_AND_ALLIES),
        CombatTurnParticipant('enemy',CombatSide.OPPOSITION)))
    results=[]
    for actor,kind in zip(('helper1','helper2'),kinds,strict=True):
        clock=start_combat_turn(CombatTurnStartRequest(actor+':start',clock,actor)).state
        clock=reserve_combat_action_slot(CombatActionSlotRequest(actor+':reserve',clock,actor,
            CombatActionDeclaration(CombatActionKind.HELP),ActionSlotGrant.STANDARD)).state
        result=execute_automatic_help_action(AutomaticHelpActionRequest(actor+':help',clock,actor,
            ConditionState(),'ally','beneficiary:test',1,Skill.MELEE,
            SUCCESS_RULE if kind is SUCCESS else SOURCE_RULE,kind))
        results.append(result)
        clock=end_combat_turn(CombatTurnEndRequest(actor+':end',result.round_state,actor)).state
    return clock,results


class K1AutomaticHelpTests(unittest.TestCase):
    def test_real_action_and_bonus_have_no_test_or_rng(self):
        source=request()
        with patch('towr.rules.test_resolution.resolve_test',side_effect=AssertionError('automatic Help rolled')):
            result=execute_automatic_help_action(source)
        self.assertEqual(result,expected_automatic_help_action(source))
        self.assertEqual(tuple(inspect.signature(execute_automatic_help_action).parameters),('request',))
        self.assertIs(result.source_request,source)
        self.assertEqual(result.previous_round_state,source.round_state)
        self.assertTrue(result.slot.executed)
        self.assertEqual(result.slot.execution.executor_rule_id,AUTOMATIC_HELP_ACTION_RULE_ID)
        self.assertEqual(result.slot.execution.result_request_id,result.bonus.id)
        self.assertEqual((result.bonus.helper_id,result.bonus.beneficiary_id,result.bonus.beneficiary_test_id,
            result.bonus.bonus_dice,result.bonus.bypasses_pool_cap,result.bonus.rule_id),
            ('helper','ally','beneficiary:test',1,True,SOURCE_RULE))
        self.assertFalse(hasattr(result,'help_test_result'))
        self.assertFalse(hasattr(source,'help_test'))
        self.assertEqual(result.round_state,replace(source.round_state,
            active_turn=replace(source.round_state.active_turn,action_slots=(result.slot,))))

    def test_staggered_and_drained_helper_need_no_test_and_keep_their_conditions(self):
        for kind in (DIE,SUCCESS):
            source=request(kind)
            for flags in (frozenset({Condition.STAGGERED}),frozenset({Condition.DRAINED}),
                    frozenset({Condition.STAGGERED,Condition.DRAINED})):
                with self.subTest(kind=kind,flags=flags):
                    result=execute_automatic_help_action(replace(source,actor_conditions=ConditionState(flags)))
                    self.assertEqual(result.source_request.actor_conditions.conditions,flags)
                    self.assertIs(result.bonus.effect_kind,kind)

    def test_helper_deafened_and_defenceless_are_rejected(self):
        for condition in (Condition.DEAFENED,Condition.DEFENCELESS):
            with self.subTest(condition=condition),self.assertRaises(ValueError):
                replace(request(),actor_conditions=ConditionState(frozenset({condition})))

    def test_requires_actual_actor_ally_reserved_help_and_unexecuted_slot(self):
        source=request()
        for change in ({'actor_id':'ally'},{'beneficiary_id':'helper'},{'beneficiary_id':'enemy'},
                {'round_state':active_round()},
                {'round_state':reserve_action(active_round(),CombatActionKind.ATTACK)},
                {'rule_id':'other-rule'},{'slot_index':2}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                replace(source,**change)
        executed=execute_automatic_help_action(source)
        with self.assertRaises(ValueError):
            replace(source,round_state=executed.round_state)

    def test_bonus_effect_has_required_kind_and_readonly_derived_values(self):
        bonus=execute_automatic_help_action(request()).bonus
        for kind,expected in ((DIE,(1,0,True)),(SUCCESS,(0,1,False))):
            actual=execute_automatic_help_action(request(kind)).bonus
            self.assertEqual((actual.bonus_dice,actual.bonus_successes,actual.bypasses_pool_cap),expected)
            self.assertIs(type(actual.bonus_dice),int)
            self.assertIs(type(actual.bonus_successes),int)
            self.assertIs(type(actual.bypasses_pool_cap),bool)
        for cls in (AutomaticHelpActionRequest,AutomaticHelpBonusSnapshot):
            field=next(f for f in fields(cls) if f.name=='effect_kind')
            self.assertIs(field.default,MISSING)
        self.assertFalse({'bonus_dice','bonus_successes','bypasses_pool_cap'}&{f.name for f in fields(bonus)})
        for change in ({'helper_id':'ally'},{'id':'other-bonus'}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                replace(bonus,**change)
        for change in ({'effect_kind':'bonus_die_beyond_cap'},{'effect_kind':'free_success'},
                {'effect_kind':True},{'beneficiary_skill':'melee'}):
            with self.subTest(change=change),self.assertRaises(TypeError):
                replace(bonus,**change)
        with self.assertRaises(TypeError):
            replace(bonus,bonus_dice=2)

    def test_actual_help_result_refuses_foreign_clock_bonus_receipt_and_incomplete_trace(self):
        result=execute_automatic_help_action(request())
        for change in ({'request_id':'another-action'},
                {'previous_round_state':replace(result.previous_round_state,round_number=2)},
                {'bonus':replace(result.bonus,rule_id='another-ability')},
                {'slot':replace(result.slot,execution=replace(result.slot.execution,result_request_id='fake-test'))},
                {'applied_rule_ids':()}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                replace(result,**change)

    def test_result_and_request_readmission_reject_equal_nested_type_aliases(self):
        for field in ('round','skill','kind'):
            result=deepcopy(execute_automatic_help_action(request()))
            if field=='round':object.__setattr__(result.round_state,'round_number',True)
            elif field=='skill':object.__setattr__(result.bonus,'beneficiary_skill','melee')
            else:object.__setattr__(result.bonus,'effect_kind','bonus_die_beyond_cap')
            self.assertEqual(result,execute_automatic_help_action(request()))
            with self.subTest(field=field),self.assertRaises(TypeError):
                replace(result)
        source=deepcopy(request())
        object.__setattr__(source.round_state,'side_order',('players_and_allies','opposition'))
        with self.assertRaises(TypeError):
            execute_automatic_help_action(source)

    def test_application_preserves_other_test_fields_and_only_uncaps_its_own_die(self):
        test=TestRequest('beneficiary:test',InlineProfile(2,3),(DiceModifier('ordinary',10),))
        source=application(test=test)
        result=apply_automatic_help_bonus(source)
        self.assertEqual(result.test,replace(test,dice_modifiers=(*test.dice_modifiers,DiceModifier(SOURCE_RULE,1,True))))
        self.assertEqual(result.modifier,DiceModifier(SOURCE_RULE,1,True))
        self.assertEqual(result.applied_rule_ids,(AUTOMATIC_HELP_ACTION_RULE_ID,SOURCE_RULE))
        actual=resolve_test(result.test,SequenceRandom([1]*5))
        self.assertEqual((actual.trace.pool_cap,actual.trace.cap_bypassing_dice,actual.trace.rolled_dice),(4,1,5))

    def test_wrong_actor_skill_and_test_cannot_consume_help(self):
        for kind in (DIE,SUCCESS):
            source=application(execute_automatic_help_action(request(kind)))
            for change in ({'beneficiary_id':'enemy'},{'beneficiary_skill':Skill.DEFENCE},
                    {'test':replace(source.test,id='next-round:test')}):
                with self.subTest(kind=kind,change=change),self.assertRaises(ValueError):
                    replace(source,**change)

    def test_application_rejects_forged_source_cached_test_flags_and_wrong_modifier(self):
        source=application(test=TestRequest('beneficiary:test',InlineProfile(2,3),
            (DiceModifier('other-bonus',1,True),)))
        forged=deepcopy(source)
        object.__setattr__(forged.test.dice_modifiers[0],'bypasses_pool_cap',1)
        self.assertEqual(forged,source)
        with self.assertRaises(TypeError):
            apply_automatic_help_bonus(forged)
        result=apply_automatic_help_bonus(source)
        for change in ({'modifier':DiceModifier(SOURCE_RULE,2,True)},
                {'test':replace(result.test,id='other-test')},{'applied_rule_ids':()}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                replace(result,**change)

    def test_two_real_helpers_stack_two_bypass_dice_in_actual_execution_order(self):
        clock,results=two_help_results((DIE,DIE))
        test=TestRequest('beneficiary:test',InlineProfile(2,3),(DiceModifier('ordinary',10),))
        for result in results:
            test=apply_automatic_help_bonus(AutomaticHelpBonusApplicationRequest('apply:'+result.request_id,
                result,'ally',Skill.MELEE,test)).test
        actual=resolve_test(test,SequenceRandom([1]*6))
        self.assertEqual(actual.trace.rolled_dice,6)
        self.assertEqual(actual.trace.cap_bypassing_dice,2)
        self.assertEqual(tuple(r.bonus.helper_id for r in results),('helper1','helper2'))
        self.assertEqual(clock.completed_turn_entity_ids,('helper1','helper2'))

    def test_free_success_has_no_test_and_resolves_zero_rolled_successes_as_one(self):
        help_result=execute_automatic_help_action(request(SUCCESS))
        self.assertFalse(hasattr(help_result,'help_test_result'))
        self.assertTrue(help_result.slot.executed)
        result=apply_automatic_help_bonus(application(help_result))
        self.assertEqual(result.modifier,SuccessModifier(SUCCESS_RULE,1))
        self.assertEqual(result.test.dice_modifiers,())
        self.assertEqual(result.test.success_modifiers,(SuccessModifier(SUCCESS_RULE,1),))
        actual=resolve_test(result.test,SequenceRandom([10,10]))
        self.assertEqual((actual.trace.rolled_dice,actual.trace.rolled_successes,
            actual.trace.success_delta,actual.successes),(2,0,1,1))

    def test_grim_rerolls_rolled_successes_but_does_not_remove_the_free_success(self):
        source=application(execute_automatic_help_action(request(SUCCESS)),
            TestRequest('beneficiary:test',InlineProfile(2,3),quality_modifiers=(QualityModifier('grim',TestQuality.GRIM),)))
        result=apply_automatic_help_bonus(source)
        actual=resolve_test(result.test,SequenceRandom([1,10,10]))
        self.assertEqual((actual.trace.rolled_successes,actual.trace.success_delta,actual.successes),(0,1,1))
        self.assertEqual(len(actual.trace.rerolls),1)

    def test_mixed_effects_preserve_normal_cap_and_add_to_different_modifier_tuples(self):
        test=TestRequest('beneficiary:test',InlineProfile(2,3),(DiceModifier('ordinary',10),))
        _,(die,free)=two_help_results((DIE,SUCCESS))
        test=apply_automatic_help_bonus(application(die,test)).test
        test=apply_automatic_help_bonus(application(free,test)).test
        self.assertEqual(test.dice_modifiers,(DiceModifier('ordinary',10),DiceModifier(SOURCE_RULE,1,True)))
        self.assertEqual(test.success_modifiers,(SuccessModifier(SUCCESS_RULE,1),))
        actual=resolve_test(test,SequenceRandom([10]*5))
        self.assertEqual((actual.trace.pool_cap,actual.trace.cap_bypassing_dice,actual.trace.rolled_dice,
            actual.trace.rolled_successes,actual.successes),(4,1,5,0,1))

    def test_kind_changes_cannot_forge_an_action_result_or_cached_request(self):
        for kind,other in ((DIE,SUCCESS),(SUCCESS,DIE)):
            result=execute_automatic_help_action(request(kind))
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                replace(result,bonus=replace(result.bonus,effect_kind=other))
            forged=deepcopy(result.source_request)
            object.__setattr__(forged,'effect_kind',kind.value)
            self.assertEqual(forged,result.source_request)
            with self.assertRaises(TypeError):
                execute_automatic_help_action(forged)

    def test_both_effects_reject_duplicate_result_modifiers_and_wrong_effect_type(self):
        for kind in (DIE,SUCCESS):
            result=apply_automatic_help_bonus(application(execute_automatic_help_action(request(kind))))
            target='dice_modifiers' if kind is DIE else 'success_modifiers'
            duplicate=replace(result.test,**{target:(result.modifier,result.modifier)})
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                replace(result,test=duplicate)
            wrong=SuccessModifier(result.modifier.rule_id,1) if kind is DIE else DiceModifier(result.modifier.rule_id,1,True)
            with self.subTest(kind=kind),self.assertRaises((TypeError,ValueError)):
                replace(result,modifier=wrong)


if __name__=='__main__':
    unittest.main()
