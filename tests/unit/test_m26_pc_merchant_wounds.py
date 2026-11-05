"""GM107 first-Wound Staggered follows the actual Wound's PG123 condition removal."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_fixtures import make_pc_melee_scenario,with_pc_melee_brute
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.attack_models import MissConsequence,ImpactOutcome
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.injury_models import ProfileInjuryState,ProfileNpcType,ProfileStateChangeRequest
from towr.domain.pc_npc_catalog import PcBookNpcProfile,get_pc_book_npc_entry
from towr.domain.pc_npc_wound_models import elf_merchant_profile_wound_state
from towr.domain.pc_melee_result_models import (PcAttackProof,PcProfileWoundProof,PcMeleeOutcome,
    PcMeleeStep,initial_pc_melee_state)
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step


def merchant_scene(*,pcs=1,merchants=1):
    return book_pc_scenario(merchants=merchants,footpads=0,townsfolk=0,pc_count=pcs,max_rounds=1)


def execute(scene,values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(scene,rng)
    rng.assert_exhausted()
    return result


def direct_first_wound():
    return execute(merchant_scene(),[1]*3+[10]*4+[10]*4+[1]*3)


class MerchantWoundTests(unittest.TestCase):
    def test_first_actual_wound_adds_one_stagger_then_ordinary_merchant_turn_continues(self):
        result = direct_first_wound()
        ack, = tuple(step for step in result.steps if isinstance(step.proof,PcProfileWoundProof))
        self.assertEqual(ack.source.enemy('merchant1').state.injury.conditions.conditions,frozenset())
        self.assertEqual(ack.state.enemy('merchant1').state.injury.conditions.conditions,frozenset({Condition.STAGGERED}))
        self.assertEqual((ack.state.enemy('merchant1').state.injury.wounds,
            ack.state.enemy('merchant1').state.injury.defeated),(1,False))
        attacks = tuple(step.proof for step in result.steps if isinstance(step.proof,PcAttackProof))
        self.assertEqual(len(attacks),2)
        incoming = attacks[-1]
        self.assertEqual(incoming.request.actor_id,'merchant1')
        self.assertEqual((incoming.execution.resolution.attack.attacker_test.trace.rolled_dice,
            incoming.execution.resolution.attack.attacker_test.trace.threshold),(4,3))
        self.assertIs(incoming.execution.resolution.attack.miss_consequence,MissConsequence.NONE)
        protection = attacks[0].execution.resolution.attack.defender_test
        self.assertIs(attacks[0].protection.source_request.selected_skill,Skill.ATHLETICS)
        self.assertEqual(protection.trace.rolled_dice,4)
        self.assertEqual(attacks[0].request.kernel_request.attack.defender_test.dice_modifiers,())
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
        self.assertIsNone(result.unsupported)
        self.assertEqual(result.exited_npc_ids,())
        self.assertFalse(result.state.enemy('merchant1').state.injury.conditions.has(Condition.BROKEN))

    def test_existing_stagger_is_removed_by_direct_wound_then_new_profile_stagger_is_added(self):
        result = execute(merchant_scene(pcs=2),[1,10,10,10]+[10]*4
            +[1,1,1,10]+[10]*4+[10]*4+[1]*3)
        own = tuple(step for step in result.steps if isinstance(step.proof,PcAttackProof)
            and step.proof.request.actor_id in ('pc1','pc2'))
        self.assertEqual((own[0].proof.execution.resolution.attack.damage,
            own[0].proof.execution.resolution.attack.effective_resilience),(4,4))
        self.assertIs(own[0].proof.execution.resolution.attack.impact,ImpactOutcome.STAGGERED)
        self.assertTrue(own[1].source.enemy('merchant1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(own[1].source.enemy('merchant1').state.injury.wounds,0)
        self.assertIs(own[1].proof.execution.resolution.attack.impact,ImpactOutcome.WOUND)
        self.assertFalse(own[1].proof.execution.resolution.target_state.conditions.has(Condition.STAGGERED))
        ack, = tuple(step for step in result.steps if isinstance(step.proof,PcProfileWoundProof))
        self.assertEqual(ack.state.enemy('merchant1').state.injury.wounds,1)
        self.assertFalse(ack.state.enemy('merchant1').state.injury.defeated)
        self.assertTrue(ack.state.enemy('merchant1').state.injury.conditions.has(Condition.STAGGERED))

    def test_three_low_damage_hits_stagger_then_wound_one_reapply_then_wound_two_defeat(self):
        result = execute(merchant_scene(pcs=3),([1,10,10,10]+[10]*4)*3)
        attacks = tuple(step for step in result.steps if isinstance(step.proof,PcAttackProof))
        self.assertEqual(tuple(step.proof.execution.resolution.attack.damage for step in attacks),(4,4,4))
        self.assertTrue(all(step.proof.execution.resolution.attack.impact is ImpactOutcome.STAGGERED for step in attacks))
        changes = tuple(step for step in result.steps if isinstance(step.proof,PcProfileWoundProof))
        self.assertEqual(tuple((step.proof.source.previous_wounds,step.proof.source.current_wounds,
            step.proof.source.defeated) for step in changes),((0,1,False),(1,2,True)))
        middle = changes[0].state.enemy('merchant1').state.injury
        self.assertEqual((middle.wounds,middle.defeated,middle.conditions.conditions),
            (1,False,frozenset({Condition.STAGGERED})))
        final = result.state.enemy('merchant1').state.injury
        self.assertEqual((final.wounds,final.defeated,final.conditions.conditions),(2,True,frozenset()))
        self.assertIsNotNone(changes[-1].proof.decision)
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)

    def test_direct_wound_then_later_real_stagger_causes_second_wound(self):
        result = execute(merchant_scene(pcs=2),[1]*4+[10]*4+[1,10,10,10]+[10]*4)
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        attacks = tuple(step.proof for step in result.steps if isinstance(step.proof,PcAttackProof))
        self.assertIs(attacks[0].execution.resolution.attack.impact,ImpactOutcome.WOUND)
        self.assertIs(attacks[1].execution.resolution.attack.impact,ImpactOutcome.STAGGERED)
        self.assertEqual(result.state.enemy('merchant1').state.injury.wounds,2)
        self.assertFalse(result.state.enemy('merchant1').state.injury.conditions.has(Condition.STAGGERED))

    def test_later_pc_miss_and_already_staggered_merchant_miss_do_not_stack_wounds(self):
        result = execute(merchant_scene(pcs=2),[1]*4+[10]*4+[10]*4+[1]*4+[10]*4+[1]*3)
        self.assertEqual(sum(isinstance(step.proof,PcProfileWoundProof) for step in result.steps),1)
        injury = result.state.enemy('merchant1').state.injury
        self.assertEqual((injury.wounds,injury.defeated,injury.conditions.conditions),
            (1,False,frozenset({Condition.STAGGERED})))
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)

    def test_pure_profile_effect_preserves_other_conditions_and_ignores_other_or_defeated_profiles(self):
        # Direct effect-preparation boundary; current ordinary NPC encounters cannot acquire these extra conditions.
        definition = get_pc_book_npc_entry(PcBookNpcProfile.ELF_MERCHANT_JEWELLED_BLADE).definition
        injury = ProfileInjuryState(1,2,ConditionState(frozenset({Condition.DRAINED,Condition.PRONE})))
        change = ProfileStateChangeRequest(ProfileNpcType.BRUTE,0,1,False)
        updated = elf_merchant_profile_wound_state(definition,injury,change)
        self.assertEqual(updated.conditions.conditions,frozenset({Condition.DRAINED,Condition.PRONE,Condition.STAGGERED}))
        final = ProfileInjuryState(2,2,defeated=True)
        self.assertIs(elf_merchant_profile_wound_state(definition,final,
            ProfileStateChangeRequest(ProfileNpcType.BRUTE,1,2,True)),final)
        numeric = with_pc_melee_brute(make_pc_melee_scenario(),'minion1',wound_limit=2).enemies[0].definition
        self.assertIs(elf_merchant_profile_wound_state(numeric,injury,change),injury)

    def test_acknowledgement_cannot_be_skipped_replayed_duplicated_or_forged(self):
        result = direct_first_wound()
        current = initial_pc_melee_state(result.source)
        for step in result.steps:
            current = apply_pc_melee_step(current,step)
        self.assertEqual(current,result.state)
        ack = next(step for step in result.steps if isinstance(step.proof,PcProfileWoundProof))
        with self.assertRaises(ValueError):
            replace(result,steps=tuple(step for step in result.steps if step is not ack))
        with self.assertRaises(ValueError):
            apply_pc_melee_step(ack.state,ack)
        with self.assertRaises(ValueError):
            PcMeleeStep(ack.state,ack.proof)
        for field,value in (('previous_wounds',1),('current_wounds',2),('npc_type','brute')):
            forged = replace(ack.proof,source=replace(ack.proof.source,**{field:value}))
            with self.subTest(field=field),self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(ack.source,forged)
        forged = deepcopy(result)
        forged_ack = next(step for step in forged.steps if isinstance(step.proof,PcProfileWoundProof))
        enemy = forged_ack.state.enemy('merchant1')
        object.__setattr__(forged_ack.state,'enemies',(replace(enemy,state=replace(enemy.state,
            injury=replace(enemy.state.injury,conditions=ConditionState()))),))
        with self.assertRaises(ValueError):
            replace(forged)

    def test_equal_first_wound_receipts_for_different_targets_stay_bound_to_full_source(self):
        scene = merchant_scene(pcs=2,merchants=2)
        first,second = scene.party
        priority = ('merchant2','merchant1')
        scene = replace(scene,party=(first,replace(second,target_priority=priority,
            defeat_decisions=tuple(second.defeat_decision(actor) for actor in priority))))
        result = execute(scene,[1]*3+[10]*4+[1]*3+[10]*4+[10]*4+[1]*3+[10]*4+[1]*3)
        acks = tuple(step for step in result.steps if isinstance(step.proof,PcProfileWoundProof))
        self.assertEqual(acks[0].proof.source,acks[1].proof.source)
        self.assertTrue(result.state.enemy('merchant1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(result.state.enemy('merchant2').state.injury.conditions.has(Condition.STAGGERED))
        with self.assertRaises(ValueError):
            apply_pc_melee_step(acks[1].source,acks[0])
        forged = deepcopy(result)
        ack = next(step for step in forged.steps if isinstance(step.proof,PcProfileWoundProof))
        object.__setattr__(ack.state,'enemies',tuple(replace(enemy,state=replace(enemy.state,
            injury=replace(enemy.state.injury,conditions=ConditionState(frozenset({Condition.STAGGERED})))))
            if enemy.state.actor_id=='merchant2' else enemy for enemy in ack.state.enemies))
        with self.assertRaises(ValueError):
            replace(forged)


if __name__ == '__main__':
    unittest.main()
