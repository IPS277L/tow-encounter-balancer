"""Non-Attack NPC causes retain literal target receipts and death dispositions."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
from types import SimpleNamespace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.condition_models import Condition,ConditionState,StaggerChoice
from towr.domain.injury_models import ProfileInjuryState,ProfileNpcType,ProfileStateChangeRequest
from towr.domain.minion_defeat_models import MinionDefeatDecision,NpcDefeatDisposition
from towr.domain.pc_bestigor_models import PcBestigorWaveGloriousSource,pc_bestigor_glorious_source
from towr.domain.pc_npc_distraction_models import (
    PcNpcWaveDistractionSource,PcNpcDistractionExpiredProof,DISTRACTED_TEST_RULE_ID,
    wave_distraction_from_profile_wound,ordered_npc_distractions,validate_pc_npc_distractions,
    expected_pc_npc_distraction_expiry,pc_npc_distraction_test_modifiers,_wave_receipt,
)
from towr.domain.pc_warped_form_models import (
    PcWarpedFormActivationProof,PcWarpedFormTargetProof,PcWarpedFormProfileProof,PcWarpedFormEndProof,
)
from towr.domain.resolution_models import StaggerImpactRequest,TargetInjuryPolicy
from towr.rules.stagger_impact_resolution import resolve_stagger_impact


class WoundPrice:
    def choose_repeated_stagger(self,**kwargs):
        return StaggerChoice.SUFFER_WOUND


def activation(actor='skin_wolf1',targets=('pc1','brewguard1'),wave='wave1'):
    return PcWarpedFormActivationProof(wave,actor,ProfileInjuryState(1,3),
        ProfileInjuryState(0,3,conditions=ConditionState((Condition.STAGGERED,))),targets)


def receipt(act,target,*,wounds=0,limit=2,disposition=None):
    before=ProfileInjuryState(wounds,limit,conditions=ConditionState((Condition.STAGGERED,)))
    request=StaggerImpactRequest(act.activation_id+':'+target,target,TargetInjuryPolicy.BRUTE,before,False,False)
    rng=ScriptedD10(())
    result=resolve_stagger_impact(request,rng,decisions=WoundPrice())
    rng.assert_exhausted()
    step=PcWarpedFormTargetProof(act.activation_id,request,result)
    decision=(MinionDefeatDecision(act.actor_id,target,disposition,True) if disposition else None)
    ack=PcWarpedFormProfileProof(act.activation_id,target,result.profile_wound.state_change,decision)
    return step,ack


def state(source,history,*,causes=(),wounded=(),defeated=()):
    enemies=[]
    for enemy in source.enemies:
        injury=enemy.state.injury
        if enemy.state.actor_id in wounded:
            injury=replace(injury,wounds=1)
        if enemy.state.actor_id in defeated:
            injury=replace(injury,wounds=injury.wound_limit,defeated=True)
        if any(c.actor_id==enemy.state.actor_id for c in causes):
            injury=replace(injury,conditions=injury.conditions.with_condition(Condition.DISTRACTED))
        enemies.append(replace(enemy,state=replace(enemy.state,injury=injury)))
    enemies=tuple(enemies)
    return SimpleNamespace(source=source,history=tuple(history),npc_distractions=tuple(causes),
        enemies=enemies,pending=(),pending_wound=None,
        enemy=lambda actor:next(e for e in enemies if e.state.actor_id==actor))


class WaveFocusTests(unittest.TestCase):
    def setUp(self):
        self.source=book_pc_scenario(skin_wolves=2,brewguards=1,bestigors=1,
            footpads=0,townsfolk=0,pc_count=1,max_rounds=1)
        self.activation=activation()
        self.target,self.ack=receipt(self.activation,'brewguard1')
        self.cause=wave_distraction_from_profile_wound(self.source,self.activation,self.ack)

    def test_first_wave_wound_has_distinct_npc_focus_and_literal_profile_source(self):
        self.assertIs(type(self.cause),PcNpcWaveDistractionSource)
        self.assertEqual((self.cause.actor_id,self.cause.focus_actor_id,self.cause.wave_id),
            ('brewguard1','skin_wolf1','wave1'))
        self.assertEqual(self.cause.profile_change,self.ack.source)
        current=state(self.source,(self.activation,self.target,self.ack),
            causes=(self.cause,),wounded=('brewguard1',))
        validate_pc_npc_distractions(current)
        self.assertEqual(pc_npc_distraction_test_modifiers(current,'brewguard1','pc1')[0].rule_id,
            DISTRACTED_TEST_RULE_ID)
        self.assertEqual(pc_npc_distraction_test_modifiers(current,'brewguard1','skin_wolf1'),())

    def test_second_wound_and_other_profile_never_add_a_new_distraction(self):
        _,second=receipt(self.activation,'brewguard1',wounds=1)
        self.assertIsNone(wave_distraction_from_profile_wound(self.source,self.activation,second))
        other=activation(targets=('pc1','bestigor1'))
        _,ack=receipt(other,'bestigor1')
        self.assertIsNone(wave_distraction_from_profile_wound(self.source,other,ack))

    def test_wave_bank_rejects_removed_or_retargeted_cause(self):
        history=(self.activation,self.target,self.ack)
        missing=state(self.source,history,wounded=('brewguard1',))
        with self.assertRaises(ValueError):validate_pc_npc_distractions(missing)
        wrong=replace(self.cause,focus_actor_id='skin_wolf2')
        changed=state(self.source,history,causes=(wrong,),wounded=('brewguard1',))
        with self.assertRaises(ValueError):validate_pc_npc_distractions(changed)
        with self.assertRaises(ValueError):
            ordered_npc_distractions(self.source,(replace(self.cause,focus_actor_id='pc1'),))

    def test_profile_ack_requires_matching_actual_target_receipt_and_is_once(self):
        prefix=(self.activation,self.target)
        self.assertEqual(_wave_receipt(prefix,self.ack),(self.activation,self.target))
        for history in ((self.activation,),(*prefix,self.ack),
                (*prefix,PcWarpedFormEndProof(self.activation.activation_id))):
            with self.subTest(history=history):
                with self.assertRaises(ValueError):_wave_receipt(history,self.ack)
        with self.assertRaises(ValueError):
            _wave_receipt(prefix,replace(self.ack,target_id='bestigor1'))
        with self.assertRaises(ValueError):
            _wave_receipt(prefix,replace(self.ack,activation_id='foreign'))

    def test_wave_cause_cannot_borrow_another_caster_or_ack(self):
        with self.assertRaises(ValueError):
            wave_distraction_from_profile_wound(self.source,self.activation,
                replace(self.ack,activation_id='foreign'))
        with self.assertRaises(ValueError):
            wave_distraction_from_profile_wound(self.source,
                replace(self.activation,actor_id='bestigor1'),self.ack)
        class ActorAlias(str,Enum):
            BREW='brewguard1'
        forged=deepcopy(self.cause)
        object.__setattr__(forged,'actor_id',ActorAlias.BREW)
        self.assertEqual(forged,self.cause)
        with self.assertRaises(TypeError):replace(forged)

    def test_npc_focus_expires_only_after_actual_killed_wave_disposition(self):
        for disposition in NpcDefeatDisposition:
            with self.subTest(disposition=disposition):
                second=activation('skin_wolf2',('pc1','skin_wolf1'),'wave2')
                hit,ack=receipt(second,'skin_wolf1',wounds=2,limit=3,disposition=disposition)
                history=(self.activation,self.target,self.ack,PcWarpedFormEndProof('wave1'),second,hit,ack)
                current=state(self.source,history,causes=(self.cause,),
                    wounded=('brewguard1',),defeated=('skin_wolf1',))
                validate_pc_npc_distractions(current)
                expiry=expected_pc_npc_distraction_expiry(current)
                if disposition is NpcDefeatDisposition.KILLED:
                    self.assertIs(type(expiry),PcNpcDistractionExpiredProof)
                    self.assertEqual(expiry.death_source_id,'wave2:skin_wolf1:defeat')
                    # A new bank with the actual expiry no longer carries Distracted.
                    after=state(self.source,(*history,expiry),wounded=('brewguard1',),defeated=('skin_wolf1',))
                    validate_pc_npc_distractions(after)
                else:
                    self.assertIsNone(expiry)

    def test_defeated_npc_without_a_confirmed_disposition_does_not_expire_focus(self):
        current=state(self.source,(self.activation,self.target,self.ack),
            causes=(self.cause,),wounded=('brewguard1',),defeated=('skin_wolf1',))
        self.assertIsNone(expected_pc_npc_distraction_expiry(current))

    def test_expiry_waits_for_mandatory_target_queue(self):
        second=activation('skin_wolf2',('pc1','skin_wolf1'),'wave2')
        hit,ack=receipt(second,'skin_wolf1',wounds=2,limit=3,disposition=NpcDefeatDisposition.KILLED)
        current=state(self.source,(self.activation,self.target,self.ack,second,hit,ack),
            causes=(self.cause,),defeated=('skin_wolf1',))
        current.pending=(ack.source,)
        self.assertIsNone(expected_pc_npc_distraction_expiry(current))


class WaveBestigorTests(unittest.TestCase):
    def test_actual_wave_first_wound_grants_its_own_typed_entitlement(self):
        source=book_pc_scenario(skin_wolves=1,bestigors=1,footpads=0,townsfolk=0,pc_count=1)
        act=activation(targets=('pc1','bestigor1'))
        hit,ack=receipt(act,'bestigor1')
        current=state(source,(act,hit,ack),wounded=('bestigor1',))
        entitlement=pc_bestigor_glorious_source(current,'bestigor1')
        self.assertIs(type(entitlement),PcBestigorWaveGloriousSource)
        self.assertEqual((entitlement.actor_id,entitlement.wave_id,entitlement.profile_change),
            ('bestigor1','wave1',ack.source))
        self.assertIsNone(pc_bestigor_glorious_source(current,'skin_wolf1'))

    def test_wound_count_without_actual_wave_ack_does_not_grant_entitlement(self):
        source=book_pc_scenario(skin_wolves=1,bestigors=1,footpads=0,townsfolk=0,pc_count=1)
        act=activation(targets=('pc1','bestigor1'))
        hit,ack=receipt(act,'bestigor1')
        self.assertIsNone(pc_bestigor_glorious_source(state(source,(act,hit),wounded=('bestigor1',)),'bestigor1'))
        with self.assertRaises(ValueError):
            pc_bestigor_glorious_source(state(source,(act,ack),wounded=('bestigor1',)),'bestigor1')
        self.assertIsNone(pc_bestigor_glorious_source(state(source,(act,hit,ack),defeated=('bestigor1',)),'bestigor1'))

    def test_wave_entitlement_rejects_non_first_wound_and_equal_type_alias(self):
        with self.assertRaises(ValueError):
            PcBestigorWaveGloriousSource('bestigor1','wave1',ProfileStateChangeRequest(ProfileNpcType.BRUTE,1,2,True))
        source=PcBestigorWaveGloriousSource('bestigor1','wave1',ProfileStateChangeRequest(ProfileNpcType.BRUTE,0,1,False))
        forged=deepcopy(source)
        object.__setattr__(forged.profile_change,'previous_wounds',False)
        self.assertEqual(forged,source)
        with self.assertRaises(ValueError):replace(forged)


class WaveFocusIntegrationTests(unittest.TestCase):
    def scene(self,*,bestigor=False,pcs=2,rounds=1):
        from towr.domain.pc_melee_models import PcMeleeWeapon
        from towr.domain.pc_warped_form_policy_models import PcWarpedFormPolicy
        source=book_pc_scenario(skin_wolves=1,bestigors=int(bestigor),brewguards=int(not bestigor),
            footpads=0,townsfolk=0,pc_count=pcs,max_rounds=rounds)
        target='bestigor1' if bestigor else 'brewguard1'
        first,*others=source.party
        priority=(target,'skin_wolf1')
        first=replace(first,target_priority=priority,
            defeat_decisions=tuple(first.defeat_decision(a) for a in priority))
        others=tuple(replace(m,pc=replace(m.pc,weapon=PcMeleeWeapon.AXE),
            defeat_decisions=tuple(replace(d,disposition=NpcDefeatDisposition.KILLED) for d in m.defeat_decisions))
            for m in others)
        return replace(source,party=(first,*others),facts=replace(source.facts,outnumbering_bonus_approved=False),
            npc_warped_form_policies=(PcWarpedFormPolicy('skin_wolf1',
                (*source.pc_activation_order,target),
                (MinionDefeatDecision('skin_wolf1',target,NpcDefeatDisposition.KILLED,True),)),))

    def execute(self,source,values):
        from towr.engine.pc_melee_runner import run_pc_melee_scenario
        rng=ScriptedD10(values)
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        return result

    def test_real_wave_w1_penalizes_brewguard_attack_against_every_pc(self):
        from towr.domain.pc_melee_result_models import PcAttackProof
        result=self.execute(self.scene(),[1,10,10,1,10,10,10]+[1]*3+[10]*4
            +[1]*5+[10]*3+[1]+[10]*3+[1]*3)
        cause,=result.state.npc_distractions
        self.assertIs(type(cause),PcNpcWaveDistractionSource)
        self.assertEqual(cause.focus_actor_id,'skin_wolf1')
        attack=next(p for p in result.state.history if type(p) is PcAttackProof and p.request.actor_id=='brewguard1')
        self.assertEqual(attack.request.target_id,'pc1')
        trace=attack.execution.resolution.attack.attacker_test.trace
        self.assertEqual(trace.rolled_dice,3)
        self.assertIn(DISTRACTED_TEST_RULE_ID,trace.applied_rule_ids)
        self.assertEqual(result.executed_actions,4)

    def test_real_wave_bestigor_entitlement_rerolls_failure_then_is_consumed(self):
        from towr.domain.pc_melee_result_models import PcAttackProof
        result=self.execute(self.scene(bestigor=True),[1,10,10,1,10,10,10]+[1]*3+[10]*4
            +[1]*5+[10]*3+[1]+[10,1,1]+[1]+[1]*3+[1,1])
        attack=next(p for p in result.state.history if type(p) is PcAttackProof and p.request.actor_id=='bestigor1')
        self.assertIs(type(attack.npc_glorious_source),PcBestigorWaveGloriousSource)
        trace=attack.execution.resolution.attack.attacker_test.trace
        self.assertEqual(tuple((r.index,r.original,r.replacement) for r in trace.rerolls),((0,10,1),))
        self.assertEqual(trace.final_values,(1,1,1))
        self.assertIsNone(pc_bestigor_glorious_source(result.state,'bestigor1'))
        self.assertEqual(result.executed_actions,4)

    def test_focus_dies_inside_wave_expiry_precedes_remaining_targets(self):
        from towr.domain.pc_melee_models import PcMeleeWeapon,PcWeaponHand
        from towr.domain.pc_warped_form_policy_models import PcWarpedFormPolicy
        source=book_pc_scenario(skin_wolves=3,brewguards=1,footpads=0,townsfolk=0,pc_count=4,max_rounds=1)
        party=[]
        for member,target in zip(source.party,('brewguard1','skin_wolf1','skin_wolf2','skin_wolf3')):
            order=(target,)+tuple(actor for actor in member.target_priority if actor!=target)
            party.append(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.AXE,
                armour_bonus=2 if member.actor_id=='pc1' else 0),initial_weapon_hand=PcWeaponHand.LEFT,
                target_priority=order,defeat_decisions=tuple(member.defeat_decision(actor) for actor in order)))
        source=replace(source,party=tuple(party),facts=replace(source.facts,outnumbering_bonus_approved=False),
            npc_warped_form_policies=tuple(PcWarpedFormPolicy(f'skin_wolf{i}',
                (*source.pc_activation_order,'brewguard1'),
                (MinionDefeatDecision(f'skin_wolf{i}','brewguard1',NpcDefeatDisposition.KNOCKED_OUT,True),))
                for i in (1,2,3)))
        weak_hit=[1,10,10,10,10,1,10,10]
        result=self.execute(source,([1]*3+[10]*4)*4+weak_hit+[1]+weak_hit+[1,1]+[1]*3+weak_hit+[10]*3)
        expiry,=tuple(s for s in result.steps if type(s.proof) is PcNpcDistractionExpiredProof)
        index=result.steps.index(expiry)
        self.assertTrue(expiry.state.participant('pc1').injury.dead)
        self.assertEqual(expiry.proof.source.focus_actor_id,'pc1')
        next_step=result.steps[index+1]
        self.assertIs(type(next_step.proof),PcWarpedFormTargetProof)
        self.assertEqual(next_step.proof.request.target_id,'pc2')
        self.assertEqual(result.state.npc_distractions,())
        self.assertTrue(result.state.participant('pc4').injury.conditions.has(Condition.STAGGERED))

    def test_actual_pc_killed_ack_expires_npc_focus_before_next_brewguard_test(self):
        from towr.domain.pc_melee_result_models import PcAttackProof,PcProfileWoundProof,PcMeleeStep
        source=self.scene(pcs=3,rounds=2)
        result=self.execute(source,[1,10,10,1,10,10,10]+([1]*3+[10]*4)*2
            +[1]*5+[10]*3+[1]+[10]*3+[1]*3
            +[10]*3+[1]*3+([1]*3+[10]*4)*2+[10]*4+[1]*3)
        expiry,=tuple(s for s in result.steps if type(s.proof) is PcNpcDistractionExpiredProof)
        self.assertEqual(expiry.proof.death_source_id,'pc-melee:r2:pc3:execute:defeat')
        self.assertIs(type(result.steps[result.steps.index(expiry)-1].proof),PcProfileWoundProof)
        self.assertEqual(result.state.npc_distractions,())
        attack=tuple(p for p in result.state.history if type(p) is PcAttackProof and p.request.actor_id=='brewguard1')[-1]
        self.assertEqual(attack.execution.resolution.attack.attacker_test.trace.rolled_dice,4)
        self.assertNotIn(DISTRACTED_TEST_RULE_ID,attack.execution.resolution.attack.attacker_test.trace.applied_rule_ids)
        with self.assertRaises(ValueError):
            PcMeleeStep(expiry.source,replace(expiry.proof,death_source_id='unconfirmed'))


if __name__=='__main__':
    unittest.main()
