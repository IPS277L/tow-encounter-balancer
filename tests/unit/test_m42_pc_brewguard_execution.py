"""Attacker-focused NPC Distracted keeps full Wound/Fate/death provenance."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_models import (PcFatePolicy,PcNearMissPolicy,PcMeleeWeapon,
    PcMeleePolicy,PcHelpPolicy,PcHelpTarget)
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy
from towr.domain.pc_melee_result_models import (
    PcAttackProof,PcMeleeOutcome,PcMeleeScenarioResult,PcMeleeStep,PcProfileWoundProof,
    PcTurnEndProof,PcWoundCompletionProof,build_pc_melee_attack,
)
from towr.domain.pc_npc_distraction_models import (
    PcNpcDistractionExpiredProof,DISTRACTED_TEST_RULE_ID,
    expected_pc_npc_distraction_expiry,pc_npc_distraction_test_modifiers,
)
from towr.domain.test_models import DiceModifier,Skill
from towr.domain.turn_models import CombatTurnEndRequest
from towr.engine.pc_melee_runner import apply_pc_melee_step,run_pc_melee_scenario
from towr.rules.turn_resolution import end_combat_turn


def scene(*,pcs=2,rounds=1,guards=1):
    source=book_pc_scenario(brewguards=guards,footpads=0,townsfolk=0,pc_count=pcs,max_rounds=rounds)
    return replace(source,facts=replace(source.facts,outnumbering_bonus_approved=False),
        party=tuple(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.AXE)) for member in source.party))


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def attacks(result,actor):
    return tuple(s for s in result.steps if type(s.proof) is PcAttackProof and s.proof.request.actor_id==actor)


def death_values(*,defenceless=False,critical_death=False):
    first=[1]*3+[10]*4+[1]*4+[10]*3+[1]
    if defenceless:
        second=[10]*3+[1]*4+[1]*4+[10]*3+[10,10,1]
        third=([10]*3 if critical_death else [1]*3+[10]*4)
    else:
        second=[10]*3+[1]*4+[1]*4+[10]*3+[1,1]
        third=[10]*3+[1]*4+[1]*4+[10]*3+[10,10,10]
    return first+second+third


class PcBrewguardExecutionTests(unittest.TestCase):
    def test_first_wound_focus_changes_only_subsequent_other_pc_protection(self):
        result=execute(scene(),[1]*3+[10]*4+[10]*3+[1]*3+[10]*4+[1]*3)
        first,=attacks(result,'pc1')
        other,=attacks(result,'pc2')
        incoming,=attacks(result,'brewguard1')
        self.assertEqual(first.proof.execution.resolution.attack.defender_test.trace.rolled_dice,4)
        self.assertEqual(other.proof.execution.resolution.attack.defender_test.trace.rolled_dice,3)
        self.assertEqual(other.proof.request.kernel_request.attack.defender_test.dice_modifiers,
            (DiceModifier(DISTRACTED_TEST_RULE_ID,-1),))
        self.assertEqual(incoming.proof.request.target_id,'pc1')
        self.assertEqual(incoming.proof.request.kernel_request.attack.attacker_test.dice_modifiers,())
        self.assertEqual(incoming.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,4)
        cause,=result.state.npc_distractions
        self.assertEqual((cause.actor_id,cause.focus_actor_id,cause.attack_id),
            ('brewguard1','pc1',first.proof.execution.request_id))
        self.assertEqual(result.executed_actions,3)

    def test_actual_second_pc_attacker_becomes_focus_without_changing_npc_target_priority(self):
        result=execute(scene(),[10]*3+[1]*4+[1]*3+[10]*4+[1]*3+[10]*3+[1])
        attack,=attacks(result,'brewguard1')
        self.assertEqual(result.state.npc_distractions[0].focus_actor_id,'pc2')
        self.assertEqual(attack.proof.request.target_id,'pc1')
        self.assertEqual(attack.proof.request.kernel_request.attack.attacker_test.dice_modifiers,
            (DiceModifier(DISTRACTED_TEST_RULE_ID,-1),))
        self.assertEqual(attack.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,3)

    def test_confirmed_lethal_focus_death_expires_before_terminal_result_without_action(self):
        result=execute(scene(pcs=1,rounds=3),death_values())
        expiry,=tuple(s for s in result.steps if type(s.proof) is PcNpcDistractionExpiredProof)
        self.assertTrue(expiry.source.participant('pc1').injury.dead)
        self.assertTrue(expiry.source.enemy('brewguard1').state.injury.conditions.has(Condition.DISTRACTED))
        self.assertFalse(expiry.state.enemy('brewguard1').state.injury.conditions.has(Condition.DISTRACTED))
        self.assertEqual(expiry.state.enemy('brewguard1').state.injury.wounds,1)
        self.assertEqual(expiry.state.npc_distractions,())
        self.assertEqual(result.executed_actions,6)
        self.assertIs(result.outcome,PcMeleeOutcome.PARTY_DEFEATED)
        with self.assertRaises(ValueError):
            PcMeleeScenarioResult(result.source,result.steps[:-1],result.outcome)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(expiry.state,expiry)
        with self.assertRaises(ValueError):
            PcMeleeStep(expiry.source,replace(expiry.proof,death_source_id='foreign-death'))

    def test_near_miss_preserves_focus_even_after_raw_lethal_roll(self):
        source=scene(pcs=1,rounds=3)
        source=replace(source,party=(replace(source.party[0],fate_policy=PcFatePolicy.CONFIGURED,
            near_miss_policy=PcNearMissPolicy(24,0)),))
        result=execute(source,death_values())
        raw=attacks(result,'brewguard1')[-1]
        self.assertTrue(raw.state.participant('pc1').injury.dead)
        self.assertIsNotNone(raw.state.pending_wound)
        self.assertIsNone(expected_pc_npc_distraction_expiry(raw.state))
        self.assertFalse(result.state.participant('pc1').injury.dead)
        self.assertEqual(len(result.state.npc_distractions),1)
        self.assertTrue(result.state.enemy('brewguard1').state.injury.conditions.has(Condition.DISTRACTED))
        self.assertFalse(any(type(s.proof) is PcNpcDistractionExpiredProof for s in result.steps))

    def test_living_defenceless_focus_remains_and_is_attacked_unopposed_without_penalty(self):
        result=execute(scene(pcs=1,rounds=3),death_values(defenceless=True))
        final=attacks(result,'brewguard1')[-1]
        self.assertTrue(final.source.participant('pc1').injury.conditions.has(Condition.DEFENCELESS))
        self.assertFalse(final.source.participant('pc1').injury.dead)
        self.assertIsNone(final.proof.request.kernel_request.attack.defender_test)
        self.assertEqual(final.proof.request.kernel_request.attack.attacker_test.dice_modifiers,())
        self.assertEqual(len(result.state.npc_distractions),1)

    def test_confirmed_critical_end_phase_death_also_expires_focus(self):
        result=execute(scene(pcs=1,rounds=3),death_values(defenceless=True,critical_death=True))
        expiry,=tuple(s for s in result.steps if type(s.proof) is PcNpcDistractionExpiredProof)
        self.assertTrue(expiry.proof.death_source_id.endswith(':end'))
        self.assertEqual(result.state.npc_distractions,())
        self.assertEqual(result.executed_actions,4)
        self.assertIs(result.outcome,PcMeleeOutcome.PARTY_DEFEATED)

    def test_multiple_brewguards_keep_independent_focus_and_source_roster_order(self):
        source=scene(guards=2)
        first=source.party[0]
        source=replace(source,party=(replace(first,target_priority=('brewguard2','brewguard1'),
            defeat_decisions=tuple(first.defeat_decision(actor) for actor in ('brewguard2','brewguard1'))),source.party[1]))
        result=execute(source,([1]*3+[10]*4)*2+[10]*3+[1]*3+[10]*4+[1]*3)
        self.assertEqual(tuple((cause.actor_id,cause.focus_actor_id) for cause in result.state.npc_distractions),
            (('brewguard1','pc2'),('brewguard2','pc1')))

    def test_first_wound_ack_and_source_bank_cannot_be_removed_or_retargeted(self):
        result=execute(scene(),[1]*3+[10]*4+[10]*3+[1]*3+[10]*4+[1]*3)
        ack=next(s for s in result.steps if type(s.proof) is PcProfileWoundProof)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(ack.state,ack)
        with self.assertRaises(ValueError):
            replace(ack.state,npc_distractions=())
        with self.assertRaises(ValueError):
            replace(ack.state,npc_distractions=(replace(ack.state.npc_distractions[0],focus_actor_id='pc2'),))
        with self.assertRaises(ValueError):
            enemy=ack.state.enemy('brewguard1')
            replace(ack.state,enemies=(replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
                conditions=enemy.state.injury.conditions.without_condition(Condition.DISTRACTED)))),))
        class Alias(str,Enum):
            PC1='pc1'
        forged=deepcopy(ack.state)
        object.__setattr__(forged.npc_distractions[0],'focus_actor_id',Alias.PC1)
        self.assertEqual(forged,ack.state)
        with self.assertRaises(TypeError):
            replace(forged)

    def test_cannot_prepare_another_test_or_end_turn_before_required_expiry(self):
        result=execute(scene(pcs=1,rounds=3),death_values())
        expiry=next(s for s in result.steps if type(s.proof) is PcNpcDistractionExpiredProof)
        with self.assertRaises(ValueError):
            pc_npc_distraction_test_modifiers(expiry.source,'brewguard1','pc1')
        clock=expiry.source.round_state
        end=end_combat_turn(CombatTurnEndRequest('pc-melee:r3:brewguard1:end',clock,'brewguard1'))
        with self.assertRaises(ValueError):
            PcMeleeStep(expiry.source,PcTurnEndProof(end,None))

    def test_second_wound_defeats_without_replacing_focus_or_counting_an_effect_action(self):
        result=execute(scene(),[1]*3+[10]*4+[1]*3+[10]*3)
        acks=tuple(s for s in result.steps if type(s.proof) is PcProfileWoundProof)
        self.assertEqual(tuple(s.proof.source.current_wounds for s in acks),(1,2))
        self.assertEqual(result.state.npc_distractions[0].focus_actor_id,'pc1')
        self.assertFalse(attacks(result,'brewguard1'))
        self.assertEqual(result.executed_actions,2)
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)

    def test_focus_death_removal_persists_on_w1_during_next_round_and_both_test_roles(self):
        pc2_miss=[10]*3+[1]*3
        pc1_miss=[10]*3+[1]*4
        first=[1]*3+[10]*4+pc2_miss+[1]*4+[10]*3+[1]
        second=pc1_miss+pc2_miss+[1]*4+[10]*3+[1,1]
        third=pc1_miss+pc2_miss+[1]*4+[10]*3+[10,10,10]
        fourth=[10]*3+[1]*4+[10]*4+[1]*3
        result=execute(scene(rounds=4),first+second+third+fourth)
        pc_attack=attacks(result,'pc2')[-1]
        npc_attack=attacks(result,'brewguard1')[-1]
        self.assertEqual(pc_attack.proof.request.kernel_request.attack.defender_test.dice_modifiers,())
        self.assertEqual(pc_attack.proof.execution.resolution.attack.defender_test.trace.rolled_dice,4)
        self.assertEqual(npc_attack.proof.request.target_id,'pc2')
        self.assertEqual(npc_attack.proof.request.kernel_request.attack.attacker_test.dice_modifiers,())
        self.assertEqual(npc_attack.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,4)
        self.assertEqual(result.state.npc_distractions,())
        self.assertEqual(result.state.enemy('brewguard1').state.injury.wounds,1)

    def test_repeated_stagger_wound_binds_its_actual_attacker_once(self):
        source=scene()
        source=replace(source,party=tuple(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.STAFF))
            for member in source.party))
        tied=[1,10,10,1,10,10,10]
        result=execute(source,tied*2+[1]*3+[10]*3+[1])
        ack,=tuple(s for s in result.steps if type(s.proof) is PcProfileWoundProof)
        self.assertEqual(ack.state.npc_distractions[0].focus_actor_id,'pc2')
        self.assertFalse(ack.state.enemy('brewguard1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(ack.state.enemy('brewguard1').state.injury.conditions.has(Condition.DISTRACTED))
        self.assertEqual(ack.state.enemy('brewguard1').state.injury.wounds,1)

    def test_help_does_not_replace_the_pc_who_actually_inflicted_the_wound(self):
        source=scene()
        helper=replace(source.party[0],policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
            help_policy=PcHelpPolicy('pc2',PcHelpTarget.MELEE_ATTACK,None))
        source=replace(source,party=(helper,source.party[1]))
        result=execute(source,[1]*3+[1]*6+[10]*4+[1]*3+[10]*3+[1])
        cause,=result.state.npc_distractions
        self.assertEqual(cause.focus_actor_id,'pc2')
        self.assertEqual(result.executed_actions,3)

    def test_npc_help_bypass_and_distracted_penalty_apply_independently(self):
        source=book_pc_scenario(brewguards=1,peasants=1,footpads=0,townsfolk=0,pc_count=2,max_rounds=1)
        source=replace(source,facts=replace(source.facts,outnumbering_bonus_approved=False),
            party=tuple(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.AXE)) for member in source.party),
            enemy_activation_order=('peasant1','brewguard1'),
            npc_help_policies=(PcNpcHelpPolicy('peasant1','brewguard1'),))
        result=execute(source,[10]*3+[1]*4+[1]*3+[10]*4+[1]*4+[10]*3+[1])
        attack,=attacks(result,'brewguard1')
        trace=attack.proof.execution.resolution.attack.attacker_test.trace
        self.assertEqual((trace.base_dice,trace.regular_dice_delta,trace.cap_bypassing_dice,trace.rolled_dice),(4,-1,1,4))
        self.assertEqual(len(attack.proof.npc_help_applications),1)
        # Pure preparation retains the negative modifier when Drained suppresses Help dice.
        state=attack.source
        enemy=state.enemy('brewguard1')
        enemy=replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
            conditions=enemy.state.injury.conditions.with_condition(Condition.DRAINED))))
        state=replace(state,enemies=(enemy,*state.enemies[1:]))
        test=build_pc_melee_attack(state)[0].kernel_request.attack.attacker_test
        self.assertEqual(test.dice_modifiers,(DiceModifier(DISTRACTED_TEST_RULE_ID,-1),))

    def test_one_confirmed_death_expires_several_sources_separately_in_source_order(self):
        first=[1]*3+[10]*4+[1]*4+[10]*3+[1]+[1]*4+[10]*3+[1,1]
        second=[1]*3+[10]*4+[1]*4+[10]*3+[1,1,1]
        third=[1]*3+[10]*4+[1]*4+[10]*3+[10]*4
        result=execute(scene(pcs=1,guards=2,rounds=3),first+second+third)
        expiries=tuple(s for s in result.steps if type(s.proof) is PcNpcDistractionExpiredProof)
        self.assertEqual(tuple(s.proof.source.actor_id for s in expiries),('brewguard1','brewguard2'))
        self.assertEqual(expiries[0].proof.death_source_id,expiries[1].proof.death_source_id)
        self.assertTrue(result.state.enemy('brewguard1').state.injury.defeated)
        self.assertFalse(result.state.enemy('brewguard2').state.injury.defeated)
        self.assertEqual(result.state.npc_distractions,())
        self.assertEqual(result.executed_actions,7)


if __name__=='__main__':
    unittest.main()
