"""Printed Stealth is used by the real PC owner and retained in replay proofs."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.pc_melee_result_models import PcAttackProof,PcMeleeStep,PcMeleeOutcome
from towr.domain.protection_models import NOW_YOU_SEE_ME_RULE_ID
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario


def thief_scene(*,thieves=1,pcs=1):
    source=book_pc_scenario(thieves=thieves,footpads=0,townsfolk=0,pc_count=pcs,max_rounds=1)
    return replace(source,facts=replace(source.facts,outnumbering_bonus_approved=False))


def miss_both():
    rng=ScriptedD10([10,10,10,1,1,1,10,10,1,1,1])
    result=run_pc_melee_scenario(thief_scene(),rng)
    rng.assert_exhausted()
    return result


class PcHalflingExecutionTests(unittest.TestCase):
    def test_native_stealth_then_dagger_use_printed_pools_and_ordinary_turn_costs(self):
        result=miss_both()
        pc,npc=tuple(s for s in result.steps if type(s.proof) is PcAttackProof)
        protection=pc.proof.protection
        self.assertIs(protection.source_request.selected_skill,Skill.STEALTH)
        self.assertEqual(protection.source_request.halfling_stealth_permission.definition,
            result.source.enemy('thief1').definition)
        self.assertEqual((protection.attack.defender_test.profile.dice,
            protection.attack.defender_test.profile.threshold),(3,5))
        self.assertEqual(pc.proof.execution.resolution.attack.defender_test.trace.rolled_dice,3)
        self.assertIn(NOW_YOU_SEE_ME_RULE_ID,protection.applied_rule_ids)
        self.assertEqual(npc.proof.request.actor_id,'thief1')
        self.assertEqual(npc.proof.request.target_id,'pc1')
        self.assertEqual(npc.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,2)
        self.assertIsNone(npc.proof.protection.source_request.halfling_stealth_permission)
        self.assertEqual(result.executed_actions,2)
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)

    def test_changed_permission_cannot_replace_a_completed_source_bound_proof(self):
        result=miss_both()
        step=next(s for s in result.steps if type(s.proof) is PcAttackProof)
        for replacement in (None,):
            forged=deepcopy(step.proof)
            object.__setattr__(forged.protection.source_request,'halfling_stealth_permission',replacement)
            with self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(step.source,forged)
        forged=deepcopy(step.proof)
        object.__setattr__(forged.protection.source_request.halfling_stealth_permission,'defender_id','other')
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(step.source,forged)

    def test_multiple_thieves_keep_each_defender_and_existing_target_priority(self):
        # Both PCs miss thief1. Both thieves miss pc1. All literal rolls.
        rng=ScriptedD10(([10]*3+[1]*3)*2+([10]*2+[1]*3)*2)
        result=run_pc_melee_scenario(thief_scene(thieves=2,pcs=2),rng)
        rng.assert_exhausted()
        attacks=tuple(s.proof for s in result.steps if type(s.proof) is PcAttackProof)
        self.assertEqual(tuple(p.request.target_id for p in attacks),('thief1','thief1','pc1','pc1'))
        self.assertEqual(result.executed_actions,4)
        self.assertTrue(all(p.protection.source_request.halfling_stealth_permission.defender_id=='thief1'
            for p in attacks[:2]))

    def test_successful_attack_defeats_minion_without_invented_stealth_action(self):
        rng=ScriptedD10([1,1,1,10,10,10])
        result=run_pc_melee_scenario(thief_scene(),rng)
        rng.assert_exhausted()
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(result.executed_actions,1)
        self.assertTrue(result.state.enemy('thief1').state.injury.defeated)

    def test_defeated_first_thief_moves_the_next_attack_permission_to_actual_second_target(self):
        rng=ScriptedD10([1]*3+[10]*3+[10]*3+[1]*3+[10]*2+[1]*3)
        result=run_pc_melee_scenario(thief_scene(thieves=2,pcs=2),rng)
        rng.assert_exhausted()
        attacks=tuple(s.proof for s in result.steps if type(s.proof) is PcAttackProof)
        self.assertEqual(tuple(p.request.target_id for p in attacks),('thief1','thief2','pc1'))
        self.assertEqual(tuple(p.protection.source_request.halfling_stealth_permission.defender_id
            for p in attacks[:2]),('thief1','thief2'))
        self.assertEqual(result.executed_actions,3)
