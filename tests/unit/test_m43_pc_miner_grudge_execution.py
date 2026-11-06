"""Declared grudges are encounter facts, not Wounds or automatic target choices."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_m28_pc_beast_orc_modifiers import pure_active
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_models import PcFatePolicy,PcNearMissPolicy,PcMeleeWeapon
from towr.domain.pc_melee_result_models import (
    PcAttackProof,PcMeleeOutcome,PcMeleeStep,initial_pc_melee_state,build_pc_melee_attack,
)
from towr.domain.pc_npc_distraction_models import (
    PcNpcDistractionSource,PcNpcDistractionExpiredProof,DISTRACTED_TEST_RULE_ID,
    expected_pc_npc_distraction_expiry,
)
from towr.domain.pc_npc_grudge_models import (
    PcNpcGrudgeEncounterProof,PcNpcGrudgeDistractionSource,
    expected_pc_npc_grudge_encounter,pc_npc_grudge_melee_modifiers,
)
from towr.domain.pc_npc_grudge_policy_models import PcNpcGrudgePolicy,GRUDGES_TO_SETTLE_RULE_ID
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy
from towr.domain.test_models import DiceModifier
from towr.domain.turn_models import CombatTurnStartRequest
from towr.engine.pc_melee_runner import apply_pc_melee_step,run_pc_melee_scenario
from towr.rules.turn_resolution import start_combat_turn


def scene(*,pcs=2,miners=1,rounds=1,selected=True,focus=None,**counts):
    source=book_pc_scenario(miners=miners,footpads=0,townsfolk=0,pc_count=pcs,max_rounds=rounds,**counts)
    focus=focus or source.party[-1].actor_id
    return replace(source,facts=replace(source.facts,outnumbering_bonus_approved=False),
        party=tuple(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.AXE)) for member in source.party),
        npc_grudge_policies=tuple(PcNpcGrudgePolicy(f'miner{i+1}',focus) for i in range(miners)) if selected else ())


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def attacks(result,actor):
    return tuple(s for s in result.steps if type(s.proof) is PcAttackProof and s.proof.request.actor_id==actor)


def death_values(*,defenceless=False):
    pc_miss=[10]*3+[1]*4
    first=pc_miss+[1]*5+[10]*3+[1]
    second=pc_miss+[1]*5+[10]*3+([10,10,1] if defenceless else [1,1])
    third=([1]*3+[10]*5 if defenceless else pc_miss+[1]*5+[10]*3+[10]*3)
    return first+second+third


class PcMinerGrudgeExecutionTests(unittest.TestCase):
    def test_encounter_precedes_first_turn_and_changes_both_test_roles_without_target_reordering(self):
        source=scene()
        result=execute(source,[10]*3+[1]*3+[10]*3+[1]*4+[1]*3+[10]*3+[1])
        first=result.steps[0]
        self.assertIs(type(first.proof),PcNpcGrudgeEncounterProof)
        self.assertEqual(first.source.round_state,first.state.round_state)
        self.assertFalse(first.source.enemy('miner1').state.injury.conditions.has(Condition.DISTRACTED))
        self.assertTrue(first.state.enemy('miner1').state.injury.conditions.has(Condition.DISTRACTED))
        pc1,=attacks(result,'pc1')
        pc2,=attacks(result,'pc2')
        miner,=attacks(result,'miner1')
        self.assertEqual(pc1.proof.execution.resolution.attack.defender_test.trace.rolled_dice,3)
        self.assertEqual(pc2.proof.execution.resolution.attack.defender_test.trace.rolled_dice,4)
        self.assertEqual(miner.proof.request.target_id,'pc1')
        self.assertEqual(miner.proof.request.kernel_request.attack.attacker_test.dice_modifiers,
            (DiceModifier(DISTRACTED_TEST_RULE_ID,-1),))
        self.assertEqual(miner.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,3)
        self.assertEqual(result.executed_actions,3)

    def test_melee_against_focus_gets_one_ordinary_die_but_protection_does_not(self):
        source=replace(scene(),enemy_target_priority=('pc2','pc1'))
        result=execute(source,[10]*3+[1]*3+[10]*3+[1]*4+[1]*5+[10]*3+[1])
        miner,=attacks(result,'miner1')
        trace=miner.proof.execution.resolution.attack.attacker_test.trace
        self.assertEqual((trace.base_dice,trace.regular_dice_delta,trace.cap_bypassing_dice,trace.pool_cap,trace.rolled_dice),
            (4,1,0,8,5))
        self.assertEqual(miner.proof.request.kernel_request.attack.attacker_test.dice_modifiers,
            (DiceModifier(GRUDGES_TO_SETTLE_RULE_ID,1),))
        self.assertEqual(attacks(result,'pc2')[0].proof.request.kernel_request.attack.defender_test.dice_modifiers,())

    def test_empty_policy_has_no_encounter_condition_or_grudge_bonus(self):
        result=execute(scene(selected=False),([10]*3+[1]*4)*2+[1]*4+[10]*3+[1])
        self.assertFalse(any(type(s.proof) is PcNpcGrudgeEncounterProof for s in result.steps))
        self.assertEqual(result.state.npc_distractions,())
        self.assertEqual(attacks(result,'miner1')[0].proof.request.kernel_request.attack.attacker_test.dice_modifiers,())
        self.assertEqual(result.executed_actions,3)

    def test_multiple_encounters_follow_roster_not_policy_input_order(self):
        source=scene(miners=2)
        source=replace(source,npc_grudge_policies=(PcNpcGrudgePolicy('miner2','pc1'),PcNpcGrudgePolicy('miner1','pc2')))
        state=initial_pc_melee_state(source)
        first=PcMeleeStep(state,expected_pc_npc_grudge_encounter(state))
        second=PcMeleeStep(first.state,expected_pc_npc_grudge_encounter(first.state))
        self.assertEqual((first.proof.policy.actor_id,second.proof.policy.actor_id),('miner1','miner2'))
        self.assertEqual(tuple((c.actor_id,c.focus_actor_id) for c in second.state.npc_distractions),
            (('miner1','pc2'),('miner2','pc1')))
        self.assertEqual(second.state.source.npc_grudge_policies,source.npc_grudge_policies)
        self.assertIsNone(expected_pc_npc_grudge_encounter(second.state))

    def test_encounter_cannot_be_skipped_replayed_retargeted_or_detached(self):
        source=scene()
        state=initial_pc_melee_state(source)
        start=start_combat_turn(CombatTurnStartRequest('pc-melee:r1:pc1:start',state.round_state,'pc1'))
        with self.assertRaises(ValueError):
            PcMeleeStep(state,start)
        proof=expected_pc_npc_grudge_encounter(state)
        step=PcMeleeStep(state,proof)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(step.state,step)
        with self.assertRaises(ValueError):
            PcMeleeStep(step.state,proof)
        for forged in (replace(proof,request_id='foreign'),
                       replace(proof,policy=PcNpcGrudgePolicy('miner1','pc1'))):
            with self.assertRaises(ValueError):
                PcMeleeStep(state,forged)
        with self.assertRaises(ValueError):
            replace(step.state,npc_distractions=())

    def test_confirmed_death_expires_grudge_source_after_completion_without_action(self):
        result=execute(scene(pcs=1,rounds=3),death_values())
        expiry,=tuple(s for s in result.steps if type(s.proof) is PcNpcDistractionExpiredProof)
        self.assertIs(type(expiry.proof.source),PcNpcGrudgeDistractionSource)
        self.assertTrue(expiry.source.participant('pc1').injury.dead)
        self.assertEqual(result.state.npc_distractions,())
        self.assertFalse(result.state.enemy('miner1').state.injury.conditions.has(Condition.DISTRACTED))
        self.assertEqual(result.executed_actions,6)
        self.assertIs(result.outcome,PcMeleeOutcome.PARTY_DEFEATED)

    def test_near_miss_and_living_defenceless_do_not_expire_or_remove_melee_bonus(self):
        source=scene(pcs=1,rounds=3)
        source=replace(source,party=(replace(source.party[0],fate_policy=PcFatePolicy.CONFIGURED,
            near_miss_policy=PcNearMissPolicy(24,0)),))
        saved=execute(source,death_values())
        raw=attacks(saved,'miner1')[-1]
        self.assertTrue(raw.state.participant('pc1').injury.dead)
        self.assertIsNone(expected_pc_npc_distraction_expiry(raw.state))
        self.assertFalse(saved.state.participant('pc1').injury.dead)
        self.assertEqual(len(saved.state.npc_distractions),1)
        prone=execute(scene(pcs=1,rounds=3),death_values(defenceless=True))
        attack=attacks(prone,'miner1')[-1]
        self.assertTrue(attack.source.participant('pc1').injury.conditions.has(Condition.DEFENCELESS))
        self.assertIsNone(attack.proof.request.kernel_request.attack.defender_test)
        self.assertEqual(attack.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,5)
        self.assertEqual(len(prone.state.npc_distractions),1)

    def test_no_reapply_or_reassignment_after_focus_death_on_next_round(self):
        source=scene(rounds=4,focus='pc1')
        pc1_miss=[10]*3+[1]*4
        pc2_miss=[10]*3+[1]*3
        first=pc1_miss+pc2_miss+[1]*5+[10]*3+[1]
        second=pc1_miss+pc2_miss+[1]*5+[10]*3+[1,1]
        third=pc1_miss+pc2_miss+[1]*5+[10]*3+[10]*3
        fourth=[10]*3+[1]*4+[10]*4+[1]*3
        result=execute(source,first+second+third+fourth)
        self.assertEqual(sum(type(s.proof) is PcNpcGrudgeEncounterProof for s in result.steps),1)
        self.assertEqual(result.state.npc_distractions,())
        last=attacks(result,'miner1')[-1]
        self.assertEqual(last.proof.request.target_id,'pc2')
        self.assertEqual(last.proof.request.kernel_request.attack.attacker_test.dice_modifiers,())
        self.assertEqual(attacks(result,'pc2')[-1].proof.execution.resolution.attack.defender_test.trace.rolled_dice,4)

    def test_grudge_and_help_are_ordinary_and_bypass_and_drained_filters_bonuses(self):
        source=scene(peasants=1)
        source=replace(source,enemy_target_priority=('pc2','pc1'),enemy_activation_order=('peasant1','miner1'),
            npc_help_policies=(PcNpcHelpPolicy('peasant1','miner1'),))
        result=execute(source,[10]*3+[1]*3+[10]*3+[1]*4+[1]*6+[10]*3+[1])
        attack,=attacks(result,'miner1')
        trace=attack.proof.execution.resolution.attack.attacker_test.trace
        self.assertEqual((trace.regular_dice_delta,trace.cap_bypassing_dice,trace.rolled_dice),(1,1,6))
        state=attack.source
        miner=state.enemy('miner1')
        miner=replace(miner,state=replace(miner.state,injury=replace(miner.state.injury,
            conditions=miner.state.injury.conditions.with_condition(Condition.DRAINED))))
        state=replace(state,enemies=(miner,*state.enemies[1:]))
        self.assertEqual(build_pc_melee_attack(state)[0].kernel_request.attack.attacker_test.dice_modifiers,())

    def test_higher_ground_is_denied_only_against_miner_preserving_outnumbering(self):
        for counts,actor,expected in (({'miners':1},'miner1',('RULE-COMBAT-007:outnumbering',)),
                ({'footpads':1},'footpad1',('RULE-COMBAT-007:outnumbering','RULE-COMBAT-007:higher-ground'))):
            source=book_pc_scenario(footpads=0,townsfolk=0,pc_count=2,max_rounds=1,**counts) if 'miners' in counts else book_pc_scenario(footpads=1,townsfolk=0,pc_count=2,max_rounds=1)
            state=pure_active(source,'pc1')
            enemy=state.enemy(actor)
            enemy=replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
                conditions=enemy.state.injury.conditions.with_condition(Condition.PRONE))))
            state=replace(state,enemies=(enemy,))
            test=build_pc_melee_attack(state)[0].kernel_request.attack.attacker_test
            self.assertEqual(tuple(mod.rule_id for mod in test.dice_modifiers),expected)

    def test_miner_still_gets_higher_ground_when_attacking_a_prone_pc(self):
        source=replace(scene(),enemy_target_priority=('pc2','pc1'))
        result=execute(source,[10]*3+[1]*3+[10]*3+[1]*4+[10]*5+[1]*3)
        state=attacks(result,'miner1')[0].source
        member=state.participant('pc2')
        member=replace(member,injury=replace(member.injury,conditions=member.injury.conditions.with_condition(Condition.PRONE)))
        state=replace(state,party=(state.party[0],member))
        test=build_pc_melee_attack(state)[0].kernel_request.attack.attacker_test
        self.assertIn(DiceModifier('RULE-COMBAT-007:higher-ground',1),test.dice_modifiers)
        self.assertIn(DiceModifier(GRUDGES_TO_SETTLE_RULE_ID,1),test.dice_modifiers)

    def test_grudge_bonus_is_relationship_based_even_before_condition_application(self):
        state=initial_pc_melee_state(scene())
        self.assertEqual(state.npc_distractions,())
        self.assertEqual(pc_npc_grudge_melee_modifiers(state,'miner1','pc2'),(DiceModifier(GRUDGES_TO_SETTLE_RULE_ID,1),))
        self.assertEqual(pc_npc_grudge_melee_modifiers(state,'miner1','pc1'),())

    def test_miner_and_brewguard_sources_coexist_without_wound_cause_substitution(self):
        source=scene(brewguards=1,focus='pc1')
        source=replace(source,party=tuple(replace(member,target_priority=('brewguard1','miner1'),
            defeat_decisions=tuple(member.defeat_decision(a) for a in ('brewguard1','miner1')))
            for member in source.party))
        result=execute(source,[10]*3+[1]*4+[1]*3+[10]*4+[10]*5+[1]*3+[10]*3+[1]*3)
        miner,brewguard=result.state.npc_distractions
        self.assertIs(type(miner),PcNpcGrudgeDistractionSource)
        self.assertIs(type(brewguard),PcNpcDistractionSource)
        self.assertEqual((miner.focus_actor_id,brewguard.focus_actor_id),('pc1','pc2'))

    def test_cached_grudge_source_ids_and_initial_flag_cannot_be_forged(self):
        state=initial_pc_melee_state(scene())
        proof=expected_pc_npc_grudge_encounter(state)
        step=PcMeleeStep(state,proof)
        forged=deepcopy(step.state)
        object.__setattr__(forged.npc_distractions[0],'encounter_id','foreign')
        with self.assertRaises(ValueError):
            replace(forged)
        enemy=state.enemy('miner1')
        with self.assertRaises(ValueError):
            replace(state,enemies=(replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
                conditions=enemy.state.injury.conditions.with_condition(Condition.DISTRACTED)))),))


if __name__=='__main__':
    unittest.main()
