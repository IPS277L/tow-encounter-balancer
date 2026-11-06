"""Actual three-Wound rage and pre-Attack Devour through PC Wound/Fate lifecycle."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_m12_pc_heavy_wounds import heavy_prefix
from tests.unit.test_m13_pc_near_miss import active
from tests.unit.test_m28_pc_beast_orc_modifiers import pure_active
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.attack_models import DamageModifier
from towr.domain.injury_models import WoundDiceModifier
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_melee_result_models import (
    PcAttackProof,PcProfileWoundProof,PcWoundCompletionProof,PcMeleeStep,PcMeleeOutcome,build_pc_melee_attack,
)
from towr.domain.pc_npc_ability_models import (
    RAZORGOR_DEVOUR_RULE_ID,MINOTAUR_DEVOUR_RULE_ID,RAZORGOR_WOUNDED_MELEE_RULE_ID,
    MINOTAUR_WOUNDED_MELEE_RULE_ID,MINOTAUR_DUAL_AXES_RULE_ID,pc_npc_wound_dice_modifiers,
)
from towr.domain.pc_npc_catalog import PcBookNpcProfile,create_pc_book_npc,get_pc_book_npc_entry
from towr.domain.test_models import DiceModifier,TestQuality
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step
from towr.rules.test_resolution import resolve_test


CASES=(('razorgors','razorgor1',3,3,RAZORGOR_DEVOUR_RULE_ID,RAZORGOR_WOUNDED_MELEE_RULE_ID),
       ('minotaurs','minotaur1',4,4,MINOTAUR_DEVOUR_RULE_ID,MINOTAUR_WOUNDED_MELEE_RULE_ID),
       ('minotaur_dual_axes','minotaur_dual1',4,4,MINOTAUR_DEVOUR_RULE_ID,MINOTAUR_WOUNDED_MELEE_RULE_ID))


def scene(*,pcs=1,rounds=1,axe=False,**counts):
    source=book_pc_scenario(footpads=0,townsfolk=0,pc_count=pcs,max_rounds=rounds,**counts)
    if axe:
        source=replace(source,party=tuple(replace(m,pc=replace(m.pc,weapon=PcMeleeWeapon.AXE)) for m in source.party))
    return source


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def attacks(result,actor):
    return tuple(s for s in result.steps if type(s.proof) is PcAttackProof and s.proof.request.actor_id==actor)


def completions(result):
    return tuple(s for s in result.steps if type(s.proof) is PcWoundCompletionProof)


def healthy_first_wound():
    # PC hits for Damage4<=Res6; it is not Staggered before the creature hits.
    return execute(scene(razorgors=1),[1,10,10]+[10]*3+[1]*3+[10]*3+[1])


class DevourExecutionTests(unittest.TestCase):
    def test_actual_first_second_and_third_brute_wounds_update_pools_then_defeat(self):
        for keyword,actor,pdice,adice,_,rage_rule in CASES:
            with self.subTest(profile=keyword):
                values=([1]*3+[10]*pdice+[10]*(adice+1)+[1]*3
                    +[1]*3+[10]*pdice+[10]*(adice+2)+[1]*3+[1]*3+[10]*pdice)
                result=execute(scene(**{keyword:1},axe=True,rounds=3),values)
                incoming=attacks(result,actor)
                self.assertEqual(tuple(s.proof.execution.resolution.attack.attacker_test.trace.rolled_dice
                    for s in incoming),(adice+1,adice+2))
                self.assertEqual(tuple(s.proof.request.kernel_request.attack.attacker_test.dice_modifiers
                    for s in incoming),((DiceModifier(rage_rule,1),),(DiceModifier(rage_rule,2),)))
                acks=tuple(s for s in result.steps if type(s.proof) is PcProfileWoundProof)
                self.assertEqual(tuple(s.proof.source.current_wounds for s in acks),(1,2,3))
                self.assertTrue(all(not s.state.enemy(actor).state.injury.conditions.has(Condition.DRAINED) for s in acks))
                self.assertTrue(result.state.enemy(actor).state.injury.defeated)
                self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)

    def test_actual_staggered_target_keeps_devour_die_when_wound_clears_stagger(self):
        for keyword,actor,pdice,adice,devour_rule,_ in CASES:
            with self.subTest(profile=keyword):
                result=execute(scene(**{keyword:1}),[10]*3+[1]*pdice+[1]*adice+[10]*3+[1,1])
                step,=attacks(result,actor)
                self.assertTrue(step.source.party[0].injury.conditions.has(Condition.STAGGERED))
                self.assertEqual(step.proof.request.kernel_request.wound_dice_modifiers,(WoundDiceModifier(devour_rule,1),))
                pending=step.proof.execution.resolution.pending_character_wound
                self.assertEqual((pending.wound_result.table_roll.dice,pending.wound_result.table_roll.total),(2,2))
                self.assertFalse(result.state.party[0].injury.conditions.has(Condition.STAGGERED))
                self.assertEqual(len(result.state.party[0].injury.wounds),1)

    def test_new_wound_does_not_qualify_itself_but_prior_wound_adds_one_on_next_attack(self):
        values=[1,10,10]+[10]*3+[1]*3+[10]*3+[1]
        values += [1,10,10]+[10]*3+[1]*4+[10]*3+[1,1,1]
        result=execute(scene(razorgors=1,rounds=2),values)
        first,second=attacks(result,'razorgor1')
        self.assertEqual(first.proof.request.kernel_request.wound_dice_modifiers,())
        self.assertFalse(second.source.party[0].injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(len(second.source.party[0].injury.wounds),1)
        self.assertEqual(second.proof.request.kernel_request.wound_dice_modifiers,
            (WoundDiceModifier(RAZORGOR_DEVOUR_RULE_ID,1),))
        self.assertEqual(tuple(s.proof.completion.source_request.roll.wound_result.table_roll.dice
            for s in completions(result)),(1,3))

    def test_repeated_stagger_wound_uses_same_bound_devour_die(self):
        source=scene(razorgors=1)
        member=source.party[0]
        source=replace(source,party=(replace(member,pc=replace(member.pc,armour_bonus=10)),))
        result=execute(source,[10]*3+[1]*3+[1]*3+[10]*3+[1,1])
        step,=attacks(result,'razorgor1')
        self.assertIsNotNone(step.proof.execution.resolution.stagger)
        self.assertEqual(step.proof.execution.resolution.pending_character_wound.wound_result.table_roll.dice,2)
        self.assertEqual(len(result.state.party[0].injury.wounds),1)

    def test_near_miss_burn_preserves_devour_source_without_adding_wound_or_future_dice(self):
        result=execute(active(scene(razorgors=1),20),[10]*3+[1]*3+[1]*3+[10]*3+[10,10])
        step,=completions(result)
        raw=step.proof.completion.source_request.roll
        self.assertEqual(raw.wound_result.table_roll.total,20)
        self.assertEqual(raw.wound_result.table_roll.dice,2)
        self.assertEqual(raw.source_request.wound.dice_modifiers,(WoundDiceModifier(RAZORGOR_DEVOUR_RULE_ID,1),))
        self.assertEqual(result.state.party[0].injury.wounds,())
        self.assertEqual(result.state.party[0].injury.untreated_wounds,0)
        self.assertEqual(result.state.party[0].fate.rating,2)
        self.assertTrue(result.state.party[0].injury.conditions.has(Condition.STAGGERED))

    def test_actual_drained_target_still_rolls_untreated_plus_devour_table_dice(self):
        source=scene(razorgors=1,watch=1)
        member=source.party[0]
        priority=('watch1','razorgor1')
        source=replace(source,enemy_activation_order=priority,
            party=(replace(member,target_priority=priority,
                defeat_decisions=tuple(member.defeat_decision(actor) for actor in priority)),))
        values=[10]*3+[1]*3+[1]*4+[10]*3+[10]+[1]*4+[10]*3+[1,1,1]
        result=execute(source,values)
        step,=attacks(result,'razorgor1')
        self.assertTrue(step.source.party[0].injury.conditions.has(Condition.DRAINED))
        raw=step.proof.execution.resolution.attack
        self.assertIs(raw.defender_test.trace.quality,TestQuality.GRIM)
        self.assertEqual(step.proof.execution.resolution.pending_character_wound.wound_result.table_roll.dice,3)

    def test_actual_defenceless_target_gets_one_forced_wound_with_extra_table_die(self):
        source=make_pc_melee_scenario(enemy_count=4,max_rounds=1)
        source=replace(source,enemies=(*source.enemies[:3],create_pc_book_npc(PcBookNpcProfile.RAZORGOR,'minion4')))
        result=execute(source,heavy_prefix(22)+[1]*4+[10]*5)
        step,=attacks(result,'minion4')
        self.assertTrue(step.source.party[0].injury.conditions.has(Condition.DEFENCELESS))
        self.assertIsNone(step.proof.execution.resolution.attack.defender_test)
        roll=step.proof.execution.resolution.pending_character_wound.wound_result.table_roll
        self.assertEqual((roll.dice,roll.total),(5,50))
        self.assertEqual(len(result.state.party[0].injury.wounds),len(step.source.party[0].injury.wounds)+1)
        self.assertIs(result.outcome,PcMeleeOutcome.PARTY_DEFEATED)

    def test_union_is_one_die_and_treatment_is_distinct_from_healing(self):
        injury=healthy_first_wound().state.party[0].injury
        definition=get_pc_book_npc_entry(PcBookNpcProfile.RAZORGOR).definition
        modifier=(WoundDiceModifier(RAZORGOR_DEVOUR_RULE_ID,1),)
        healthy=replace(injury,wounds=())
        for flags,expected in ((frozenset(),()),(frozenset({Condition.DRAINED}),()),
                (frozenset({Condition.STAGGERED}),modifier),(frozenset({Condition.PRONE}),modifier),
                (frozenset({Condition.STAGGERED,Condition.PRONE}),modifier)):
            self.assertEqual(pc_npc_wound_dice_modifiers(definition,
                replace(healthy,conditions=ConditionState(flags))),expected)
        for flags in (frozenset(),frozenset({Condition.STAGGERED}),
                frozenset({Condition.PRONE}),frozenset({Condition.STAGGERED,Condition.PRONE,Condition.DRAINED})):
            target=replace(injury,conditions=ConditionState(flags))
            self.assertEqual(pc_npc_wound_dice_modifiers(definition,target),modifier)
        treated=replace(injury,wounds=(replace(injury.wounds[0],treated=True),))
        self.assertEqual(treated.untreated_wounds,0)
        self.assertEqual(pc_npc_wound_dice_modifiers(definition,treated),modifier)
        healed=replace(treated,wounds=(replace(treated.wounds[0],healed=True),))
        self.assertEqual(pc_npc_wound_dice_modifiers(definition,healed),())

    def test_pure_rage_cap_and_drained_filter_do_not_touch_devour_or_dual_damage(self):
        for keyword,actor,base,cap in (('razorgors','razorgor1',3,6),('minotaur_dual_axes','minotaur_dual1',4,8)):
            state=pure_active(scene(**{keyword:1},watch=1),actor)
            enemy=state.enemy(actor)
            enemy=replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,wounds=2)))
            pc=state.party[0]
            pc=replace(pc,injury=replace(pc.injury,conditions=ConditionState(frozenset({Condition.PRONE,Condition.STAGGERED}))))
            state=replace(state,enemies=tuple(enemy if e.state.actor_id==actor else e for e in state.enemies),party=(pc,))
            request,_=build_pc_melee_attack(state)
            rng=ScriptedD10([1]*cap)
            trace=resolve_test(request.kernel_request.attack.attacker_test,rng).trace
            rng.assert_exhausted()
            self.assertEqual((trace.base_dice,trace.regular_dice_delta,trace.pool_cap,trace.rolled_dice),(base,4,cap,cap))
            enemy=replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
                conditions=ConditionState(frozenset({Condition.DRAINED})))))
            state=replace(state,enemies=tuple(enemy if e.state.actor_id==actor else e for e in state.enemies))
            request,_=build_pc_melee_attack(state)
            self.assertEqual(request.kernel_request.attack.attacker_test.dice_modifiers,())
            self.assertEqual(len(request.kernel_request.wound_dice_modifiers),1)
            self.assertEqual(request.kernel_request.attack.impact_spec.damage_modifiers,
                (DamageModifier(MINOTAUR_DUAL_AXES_RULE_ID,1),) if actor=='minotaur_dual1' else ())

    def test_actual_named_target_does_not_inherit_other_pcs_vulnerability(self):
        injury=healthy_first_wound().state.party[0].injury
        source=scene(razorgors=1,pcs=2)
        source=replace(source,enemy_target_priority=('pc2','pc1'))
        state=pure_active(source,'razorgor1')
        state=replace(state,party=(replace(state.party[0],injury=injury),state.party[1]))
        request,_=build_pc_melee_attack(state)
        self.assertEqual(request.target_id,'pc2')
        self.assertEqual(request.kernel_request.wound_dice_modifiers,())

    def test_wound_modifier_and_cached_receipt_cannot_be_dropped_duplicated_or_forged(self):
        result=execute(scene(razorgors=1),[10]*3+[1]*3+[1]*3+[10]*3+[1,1])
        step,=attacks(result,'razorgor1')
        for value in (True,2):
            forged=deepcopy(step.proof)
            object.__setattr__(forged.request.kernel_request.wound_dice_modifiers[0],'amount',value)
            with self.subTest(value=value),self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(step.source,forged)
        for duplicate in (False,True):
            forged=deepcopy(step.proof)
            kernel=forged.request.kernel_request
            object.__setattr__(kernel,'wound_dice_modifiers',kernel.wound_dice_modifiers*2 if duplicate else ())
            with self.subTest(duplicate=duplicate),self.assertRaises(ValueError):
                PcMeleeStep(step.source,forged)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(step.state,step)


if __name__=='__main__':
    unittest.main()
