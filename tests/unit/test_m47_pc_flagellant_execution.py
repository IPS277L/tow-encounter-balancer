"""Actual incoming/miss causes, real Recover receipts and repeated healing cycles."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_m28_pc_beast_orc_modifiers import pure_active
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.pc_flagellant_policy_models import PcFlagellantPolicy,PcFeelNoPainPolicy,FEEL_NO_PAIN_RULE_ID,FLAILS_STAGGERED_RULE_ID
from towr.domain.pc_flagellant_models import (
    PcNpcRecoverProof,PcFlagellantMissWoundProof,flagellant_conditions,build_pc_npc_recover,
    flagellant_recovered_injury,
)
from towr.domain.pc_melee_result_models import (
    PcAttackProof,PcAttackerStaggerProof,PcProfileWoundProof,PcMeleeStep,PcMeleeOutcome,
    build_pc_melee_attack,initial_pc_melee_state,
)
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy
from towr.domain.test_models import DiceModifier
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step


WEAK=[1,10,10,1,10,10]


def scene(*,hooks=False,selected=True,feel=True,recover=True,rounds=1,pcs=1,count=1,axe=False,**counts):
    source=book_pc_scenario(flagellant_hooks=count if hooks else 0,flagellant_flails=0 if hooks else count,
        footpads=0,townsfolk=0,pc_count=pcs,max_rounds=rounds,**counts)
    policies=tuple(PcFlagellantPolicy(e.state.actor_id,
        PcFeelNoPainPolicy.WOUND_AT_ZERO if feel else PcFeelNoPainPolicy.DECLINE,recover)
        for e in source.enemies if e.state.actor_id.startswith('flagellant')) if selected else ()
    return replace(source,npc_flagellant_policies=policies,
        party=tuple(replace(m,pc=replace(m.pc,weapon=PcMeleeWeapon.AXE if axe else PcMeleeWeapon.STAFF)) for m in source.party))


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def proofs(result,kind):
    return tuple(s for s in result.steps if type(s.proof) is kind)


class PcFlagellantExecutionTests(unittest.TestCase):
    def test_first_weak_hit_becomes_one_profile_wound_then_actual_recover_heals(self):
        for hooks in (False,True):
            result=execute(scene(hooks=hooks),WEAK)
            attack,=proofs(result,PcAttackProof)
            raw=attack.proof.execution.resolution
            self.assertEqual((raw.attack.damage,raw.attack.effective_resilience),(3,3))
            self.assertEqual(raw.profile_wound.state.wounds,1)
            self.assertEqual(raw.applied_secondary_rule_ids,(FEEL_NO_PAIN_RULE_ID,))
            self.assertFalse(raw.target_state.conditions.has(Condition.STAGGERED))
            ack,=proofs(result,PcProfileWoundProof)
            recover,=proofs(result,PcNpcRecoverProof)
            self.assertEqual((ack.proof.source.previous_wounds,ack.proof.source.current_wounds),(0,1))
            self.assertEqual((recover.proof.previous_injury.wounds,recover.proof.injury.wounds),(1,0))
            self.assertEqual(result.executed_actions,2)
            self.assertTrue(recover.proof.execution.slot.executed)
            self.assertEqual(recover.proof.execution.slot.declaration.kind.value,'recover')
            self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)

    def test_two_real_wound_recover_cycles_are_not_collapsed_into_current_zero(self):
        result=execute(scene(rounds=2),WEAK*2)
        self.assertEqual(len(proofs(result,PcProfileWoundProof)),2)
        self.assertEqual(len(proofs(result,PcNpcRecoverProof)),2)
        self.assertEqual(result.executed_actions,4)
        self.assertEqual(result.state.enemy('flagellant_flails1').state.injury.wounds,0)

    def test_own_miss_wound_targets_actor_not_the_pc_target_and_waits_until_next_turn_to_heal(self):
        result=execute(scene(rounds=2),[10]*3+[1]*3+[10]*3+[1]*3+[10]*3+[1]*3)
        miss,=proofs(result,PcFlagellantMissWoundProof)
        self.assertEqual(miss.proof.actor_id,'flagellant_flails1')
        npc_attack=next(s for s in proofs(result,PcAttackProof) if s.proof.request.actor_id=='flagellant_flails1')
        self.assertEqual(miss.proof.source.attack_id,npc_attack.proof.request.kernel_request.attack.id)
        self.assertEqual(npc_attack.proof.request.target_id,'pc1')
        self.assertEqual(miss.state.enemy('flagellant_flails1').state.injury.wounds,1)
        self.assertEqual(miss.state.participant('pc1').injury.wounds,())
        self.assertFalse(proofs(result,PcProfileWoundProof))
        recover,=proofs(result,PcNpcRecoverProof)
        self.assertEqual((miss.source.round_state.round_number,recover.source.round_state.round_number),(1,2))
        self.assertEqual(result.executed_actions,4)

    def test_empty_policy_keeps_first_stagger_and_flails_penalty_instead_of_wound(self):
        result=execute(scene(selected=False),WEAK+[10]+[1]*3)
        npc=next(s.proof for s in proofs(result,PcAttackProof) if s.proof.request.actor_id=='flagellant_flails1')
        trace=npc.execution.resolution.attack.attacker_test.trace
        self.assertEqual((trace.base_dice,trace.rolled_dice,trace.threshold),(3,1,4))
        self.assertFalse(trace.minimum_die_rule_applied)
        self.assertEqual(npc.request.kernel_request.attack.attacker_test.dice_modifiers,
            (DiceModifier(FLAILS_STAGGERED_RULE_ID,-2),))
        self.assertFalse(proofs(result,PcNpcRecoverProof))
        self.assertFalse(proofs(result,PcFlagellantMissWoundProof))
        self.assertEqual(result.state.enemy('flagellant_flails1').state.injury.wounds,0)

    def test_hooks_staggered_has_no_flails_penalty(self):
        result=execute(scene(hooks=True,selected=False),WEAK+[10]*3+[1]*3)
        npc=next(s.proof for s in proofs(result,PcAttackProof) if s.proof.request.actor_id=='flagellant_hooks1')
        self.assertEqual(npc.execution.resolution.attack.attacker_test.trace.rolled_dice,3)
        self.assertEqual(npc.request.kernel_request.attack.attacker_test.dice_modifiers,())

    def test_attack_only_policy_does_not_heal_after_selected_wound(self):
        result=execute(scene(recover=False),WEAK+[10]*3+[1]*3)
        self.assertFalse(proofs(result,PcNpcRecoverProof))
        self.assertTrue(proofs(result,PcAttackProof)[1].proof.request.actor_id.startswith('flagellant'))
        self.assertEqual(result.state.enemy('flagellant_flails1').state.injury.wounds,1)

    def test_direct_wound_is_not_doubled_and_wounded_actor_declines_self_defeating_miss_replacement(self):
        result=execute(scene(recover=False,axe=True),[1]*3+[10]*3+[10]*3+[1]*3)
        ack,=proofs(result,PcProfileWoundProof)
        self.assertEqual(ack.proof.source.current_wounds,1)
        self.assertFalse(proofs(result,PcFlagellantMissWoundProof))
        self.assertTrue(result.state.enemy('flagellant_flails1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(result.state.enemy('flagellant_flails1').state.injury.defeated)

    def test_second_direct_wound_defeats_before_own_recover_and_keeps_disposition(self):
        result=execute(scene(pcs=2,axe=True),([1]*4+[10]*3)*2)
        acks=proofs(result,PcProfileWoundProof)
        self.assertEqual(tuple(s.proof.source.current_wounds for s in acks),(1,2))
        self.assertIsNotNone(acks[1].proof.decision)
        self.assertFalse(proofs(result,PcNpcRecoverProof))
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)

    def test_w1_first_stagger_is_kept_then_removed_by_real_standard_recover(self):
        # The second PC ties with one success: Staff Damage3 adds Staggered at W1.
        result=execute(scene(pcs=2),[1]*4+[10]*3+[1,10,10,10]+[1,10,10])
        recover,=proofs(result,PcNpcRecoverProof)
        self.assertTrue(recover.proof.previous_injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(recover.proof.injury.conditions.has(Condition.STAGGERED))
        changes=recover.proof.execution.resolution.condition_changes
        self.assertEqual(len(changes),1)
        self.assertIn(Condition.STAGGERED,changes[0].removed_conditions)
        self.assertEqual(result.executed_actions,3)

    def test_repeated_stagger_keeps_normal_wound_price_then_recover(self):
        result=execute(scene(feel=False,rounds=2),WEAK+[10]+[1]*3+WEAK)
        acks=proofs(result,PcProfileWoundProof)
        self.assertEqual(len(acks),1)
        attack=proofs(result,PcAttackProof)[-1].proof.execution.resolution
        self.assertEqual(attack.stagger.selected_choice.value,'suffer_wound')
        self.assertEqual(attack.applied_secondary_rule_ids,())
        self.assertEqual(len(proofs(result,PcNpcRecoverProof)),1)

    def test_repeated_stagger_at_w1_defeats_without_heal_or_revive(self):
        weak4=[1,10,10,10,1,10,10]
        result=execute(scene(pcs=3),[1]*4+[10]*3+weak4*2)
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(proofs(result,PcProfileWoundProof)[-1].proof.source.current_wounds,2)
        self.assertFalse(proofs(result,PcNpcRecoverProof))

    def test_standard_self_recover_removes_stagger_and_prone_but_retains_other_conditions(self):
        before=replace(initial_pc_melee_state(scene()).enemy('flagellant_flails1').state.injury,
            wounds=1,conditions=ConditionState(frozenset({Condition.STAGGERED,Condition.PRONE,Condition.DRAINED})))
        after=flagellant_recovered_injury(before)
        self.assertEqual(after.wounds,0)
        self.assertEqual(after.conditions.conditions,frozenset({Condition.DRAINED}))
        for invalid in (replace(before,wounds=0),replace(before,wounds=2,defeated=True)):
            with self.assertRaises(ValueError):flagellant_recovered_injury(invalid)

    def test_recover_receipt_cannot_be_replayed_retargeted_or_heal_twice(self):
        recover=proofs(execute(scene(),WEAK),PcNpcRecoverProof)[0]
        with self.assertRaises(ValueError):apply_pc_melee_step(recover.state,recover)
        with self.assertRaises(ValueError):PcMeleeStep(recover.state,recover.proof)
        with self.assertRaises(ValueError):replace(recover.proof,injury=recover.proof.previous_injury)
        forged=deepcopy(recover.proof)
        object.__setattr__(forged.request,'actor_id','pc1')
        with self.assertRaises(ValueError):PcMeleeStep(recover.source,forged)

    def test_selected_miss_replacement_cannot_be_skipped_or_detached(self):
        result=execute(scene(),[10]*3+[1]*3+[10]*3+[1]*3)
        miss,=proofs(result,PcFlagellantMissWoundProof)
        with self.assertRaises(ValueError):PcMeleeStep(miss.source,PcAttackerStaggerProof(miss.proof.source))
        with self.assertRaises(ValueError):apply_pc_melee_step(miss.state,miss)
        with self.assertRaises(ValueError):PcMeleeStep(miss.source,replace(miss.proof,actor_id='pc1'))
        with self.assertRaises(ValueError):PcMeleeStep(result.steps[0].source,miss.proof)

    def test_cached_equal_miss_wound_counts_and_ack_aliases_are_readmitted(self):
        miss=proofs(execute(scene(),[10]*3+[1]*3+[10]*3+[1]*3),PcFlagellantMissWoundProof)[0]
        for field,value in (('wounds_requested',True),('wounds_inflicted',1.0)):
            forged=deepcopy(miss.proof)
            object.__setattr__(forged.wound,field,value)
            self.assertEqual(forged,miss.proof)
            with self.assertRaises(TypeError):PcMeleeStep(miss.source,forged)
        forged=deepcopy(miss.proof)
        object.__setattr__(forged.wound.state_change,'current_wounds',1.0)
        with self.assertRaises(TypeError):PcMeleeStep(miss.source,forged)

    def test_unbreakable_blocks_only_broken_and_owner_rejects_injected_broken(self):
        state=initial_pc_melee_state(scene())
        enemy=state.enemy('flagellant_flails1')
        conditions=ConditionState(frozenset({Condition.BROKEN,Condition.STAGGERED,Condition.PRONE,Condition.DRAINED,Condition.DISTRACTED}))
        self.assertEqual(flagellant_conditions(enemy.definition,conditions).conditions,
            conditions.conditions-frozenset({Condition.BROKEN}))
        broken=replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,conditions=conditions)))
        with self.assertRaises(ValueError):replace(state,enemies=(broken,))

    def test_helper_attacks_instead_when_named_flagellant_will_recover(self):
        source=scene(orcs=1)
        source=replace(source,enemy_activation_order=('orc1','flagellant_flails1'),
            npc_help_policies=(PcNpcHelpPolicy('orc1','flagellant_flails1'),))
        result=execute(source,WEAK+[10]*4+[1]*3)
        self.assertEqual(tuple(s.proof.request.actor_id for s in proofs(result,PcAttackProof)),('pc1','orc1'))
        self.assertEqual(len(proofs(result,PcNpcRecoverProof)),1)
        self.assertEqual(result.executed_actions,3)

    def test_flails_negative_modifier_survives_drained_filter(self):
        # Pure preparation of Conditions the fixed scene does not itself produce on this NPC.
        state=pure_active(scene(selected=False),'flagellant_flails1')
        enemy=state.enemy('flagellant_flails1')
        changed=replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
            conditions=ConditionState(frozenset({Condition.STAGGERED,Condition.DRAINED})))))
        state=replace(state,enemies=(changed,))
        request,_=build_pc_melee_attack(state)
        self.assertEqual(request.kernel_request.attack.attacker_test.dice_modifiers,(DiceModifier(FLAILS_STAGGERED_RULE_ID,-2),))

    def test_recover_policy_at_zero_does_not_create_empty_action(self):
        result=execute(scene(feel=False),[10]*3+[1]*3+[10]*3+[1]*3)
        self.assertFalse(proofs(result,PcNpcRecoverProof))
        self.assertEqual(result.executed_actions,2)
