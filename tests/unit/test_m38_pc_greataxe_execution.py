"""Canonical Greataxe starts at3d while retaining cap8 through PC execution."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_m28_pc_beast_orc_modifiers import pure_active
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_melee_result_models import (
    PcAttackProof,PcNpcHelpProof,PcProfileWoundProof,PcMeleeStep,PcMeleeOutcome,build_pc_melee_attack,
)
from towr.domain.pc_npc_ability_models import MINOTAUR_DEVOUR_RULE_ID
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy
from towr.domain.test_models import DiceModifier
from towr.domain.injury_models import WoundDiceModifier
from towr.rules.test_resolution import resolve_test
from towr.engine.pc_melee_runner import run_pc_melee_scenario


ACTOR='minotaur_greataxe1'


def scene(*,pcs=1,rounds=1,axe=False,**counts):
    source=book_pc_scenario(minotaur_greataxes=1,footpads=0,townsfolk=0,
        pc_count=pcs,max_rounds=rounds,**counts)
    if axe:
        source=replace(source,party=tuple(replace(m,pc=replace(m.pc,weapon=PcMeleeWeapon.AXE)) for m in source.party))
    return source


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def incoming(result):
    return tuple(s for s in result.steps if type(s.proof) is PcAttackProof and s.proof.request.actor_id==ACTOR)


class PcGreataxeExecutionTests(unittest.TestCase):
    def test_actual_unwounded_attack_keeps_three_dice_cap8_and_printed_damage8(self):
        # PC hits without becoming Staggered; Greataxe hits a healthy target.
        result=execute(scene(),[1,10,10]+[10]*4+[1]*3+[10]*3+[1])
        step,=incoming(result)
        raw=step.proof.execution.resolution.attack
        self.assertEqual((raw.attacker_test.trace.base_dice,raw.attacker_test.trace.rolled_dice,
            raw.attacker_test.trace.pool_cap,raw.attacker_test.trace.threshold),(3,3,8,5))
        self.assertEqual((raw.impact_spec.damage.base,raw.damage,raw.impact_spec.damage_modifiers),(8,11,()))
        self.assertEqual(step.proof.request.kernel_request.wound_dice_modifiers,())
        self.assertEqual(step.proof.execution.resolution.pending_character_wound.wound_result.table_roll.dice,1)

    def test_actual_first_second_wound_pools_are_four_five_and_third_defeats(self):
        values=[1]*3+[10]*4+[10]*4+[1]*3+[1]*3+[10]*4+[10]*5+[1]*3+[1]*3+[10]*4
        result=execute(scene(axe=True,rounds=3),values)
        self.assertEqual(tuple(s.proof.execution.resolution.attack.attacker_test.trace.rolled_dice
            for s in incoming(result)),(4,5))
        self.assertEqual(tuple(s.proof.execution.resolution.attack.attacker_test.trace.pool_cap
            for s in incoming(result)),(8,8))
        acks=tuple(s for s in result.steps if type(s.proof) is PcProfileWoundProof)
        self.assertEqual(tuple(s.proof.source.current_wounds for s in acks),(1,2,3))
        self.assertFalse(any(s.state.enemy(ACTOR).state.injury.conditions.has(Condition.DRAINED) for s in acks))
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)

    def test_real_rage_higher_ground_outnumbering_and_two_help_dice_exceed_old_cap6(self):
        source=scene(pcs=2,axe=True,watch=1,cultists=2)
        source=replace(source,enemy_activation_order=('watch1','cultist1','cultist2',ACTOR),
            npc_help_policies=(PcNpcHelpPolicy('cultist1',ACTOR),PcNpcHelpPolicy('cultist2',ACTOR)))
        values=([1]*3+[10]*4)*2+[1]*4+[10]*3+[9]+[10]*9+[1]*3
        result=execute(source,values)
        step,=incoming(result)
        self.assertEqual(step.source.enemy(ACTOR).state.injury.wounds,2)
        self.assertTrue(step.source.party[0].injury.conditions.has(Condition.PRONE))
        trace=step.proof.execution.resolution.attack.attacker_test.trace
        self.assertEqual((trace.base_dice,trace.regular_dice_delta,trace.pool_cap,
            trace.cap_bypassing_dice,trace.rolled_dice),(3,4,8,2,9))
        self.assertEqual(len(step.proof.npc_help_applications),2)
        self.assertEqual(sum(type(s.proof) is PcNpcHelpProof for s in result.steps),2)
        self.assertEqual(step.proof.request.kernel_request.wound_dice_modifiers,
            (WoundDiceModifier(MINOTAUR_DEVOUR_RULE_ID,1),))

    def test_prepared_profile_caps_large_regular_bonus_at8_then_adds_bypass(self):
        state=pure_active(scene(),ACTOR)
        request,_=build_pc_melee_attack(state)
        prepared=request.kernel_request.attack.attacker_test
        test=replace(prepared,dice_modifiers=(DiceModifier('authored:cap-check',20),
            DiceModifier('authored:bypass-check',2,True)))
        rng=ScriptedD10([1]*10)
        trace=resolve_test(test,rng).trace
        rng.assert_exhausted()
        self.assertEqual((trace.base_dice,trace.pool_cap,trace.cap_bypassing_dice,trace.rolled_dice),(3,8,2,10))

    def test_drained_filters_rage_and_other_test_bonuses_while_retaining_cap_and_devour(self):
        state=pure_active(scene(watch=1),ACTOR)
        enemy=state.enemy(ACTOR)
        enemy=replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,wounds=2,
            conditions=ConditionState(frozenset({Condition.DRAINED})))))
        member=state.party[0]
        member=replace(member,injury=replace(member.injury,
            conditions=ConditionState(frozenset({Condition.PRONE,Condition.STAGGERED}))))
        state=replace(state,enemies=tuple(enemy if e.state.actor_id==ACTOR else e for e in state.enemies),party=(member,))
        request,_=build_pc_melee_attack(state)
        self.assertEqual(request.kernel_request.attack.attacker_test.dice_modifiers,())
        self.assertEqual(request.kernel_request.attack.attacker_test.profile.maximum_dice,8)
        self.assertEqual(request.kernel_request.wound_dice_modifiers,(WoundDiceModifier(MINOTAUR_DEVOUR_RULE_ID,1),))
        self.assertEqual(request.kernel_request.attack.impact_spec.damage_modifiers,())

    def test_actual_staggered_target_uses_two_table_dice_without_a_second_weapon_penalty(self):
        result=execute(scene(),[10]*3+[1]*4+[1]*3+[10]*3+[1,1])
        step,=incoming(result)
        self.assertTrue(step.source.party[0].injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(step.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,3)
        self.assertEqual(step.proof.execution.resolution.pending_character_wound.wound_result.table_roll.dice,2)
        self.assertEqual(len(result.state.party[0].injury.wounds),1)

    def test_native_proof_cannot_change_cap_to_implicit6_or_equal_float8(self):
        result=execute(scene(),[1,10,10]+[10]*4+[10]*3+[1]*3)
        step,=incoming(result)
        for cap in (None,6,8.0):
            forged=deepcopy(step.proof)
            object.__setattr__(forged.request.kernel_request.attack.attacker_test.profile,'pool_cap',cap)
            with self.subTest(cap=cap),self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(step.source,forged)

    def test_other_book_authored_and_protection_profiles_cannot_opt_into_explicit_cap(self):
        sources=(scene(),book_pc_scenario(minotaurs=1,footpads=0,townsfolk=0,pc_count=1),
            make_pc_melee_scenario())
        for source in sources:
            enemy=source.enemies[0]
            protection=enemy.definition.protection[0]
            wrong_protection=replace(protection,test_profile=replace(protection.test_profile,pool_cap=8))
            with self.subTest(id=enemy.definition.id,role='protection'),self.assertRaises((TypeError,ValueError)):
                definition=replace(enemy.definition,protection=(wrong_protection,))
                replace(source,enemies=(replace(enemy,definition=definition),*source.enemies[1:]))
            if enemy.definition.id!='pc-book-npc:minotaur_greataxe':
                attack=enemy.definition.attacks[0]
                definition=replace(enemy.definition,attacks=(replace(attack,
                    test_profile=replace(attack.test_profile,pool_cap=8)),))
                with self.subTest(id=enemy.definition.id,role='attack'),self.assertRaises((TypeError,ValueError)):
                    replace(source,enemies=(replace(enemy,definition=definition),*source.enemies[1:]))


if __name__=='__main__':
    unittest.main()
