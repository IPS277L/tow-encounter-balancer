"""An explicit repeated-Staggered Minion defeat is neither a Wound nor a GM choice."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import Mock

from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.attack_models import AttackRequest,DamageImpactSpec,DamageProfile,ResilienceProfile
from towr.domain.condition_models import Condition,ConditionState,StaggerChoice,StaggerOutcome
from towr.domain.injury_models import (
    CharacterInjuryState,MinionStaggerDefeatCause,MinionStaggerDefeatResult,
    MinionStaggerDefeatSpec,ProfileInjuryState,
)
from towr.domain.resolution_models import (
    ConditionAfterGiveGroundRequest,HazardExposureRequest,HazardResolutionRequest,
    KernelAttackRequest,StaggerImpactRequest,TargetInjuryPolicy,
)
from towr.domain.test_models import InlineProfile,Skill,TestRequest
from towr.rules.condition_effect_resolution import resolve_condition_after_give_ground
from towr.rules.hazard_resolution import resolve_hazard
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.stagger_impact_resolution import resolve_stagger_impact
from towr.rules.test_resolution import resolve_test


RULE='RULE-PROFILE-GREENSKIN-001:dirty-coward'


def request(*,staggered=True,base=3):
    conditions=ConditionState(frozenset({Condition.STAGGERED})) if staggered else ConditionState()
    attack=AttackRequest('attack',TestRequest('a',InlineProfile(1,3)),
        TestRequest('d',InlineProfile(1,3)),DamageImpactSpec(DamageProfile(base),ResilienceProfile(5)),True,False)
    return KernelAttackRequest('kernel','goblin',attack,TargetInjuryPolicy.MINION,
        ProfileInjuryState(0,1,conditions),True,False,physical_attack=True,
        minion_stagger_defeat=MinionStaggerDefeatSpec(RULE))


def execute(source,values):
    rng=ScriptedD10(values)
    result=resolve_kernel_attack(source,rng)
    rng.assert_exhausted()
    return result


class MinionStaggerDefeatTests(unittest.TestCase):
    def test_repeated_stagger_defeats_without_wound_choice_or_extra_rng(self):
        source=request()
        decisions=Mock()
        decisions.choose_repeated_stagger.side_effect=AssertionError('printed defeat cannot ask GM')
        rng=ScriptedD10([1,10])
        result=resolve_kernel_attack(source,rng,decisions=decisions)
        rng.assert_exhausted()
        decisions.choose_repeated_stagger.assert_not_called()
        cause=MinionStaggerDefeatCause('kernel:minion-stagger-defeat','goblin',RULE)
        self.assertEqual(result.minion_stagger_defeat,MinionStaggerDefeatResult(cause.source_id,
            replace(source.target_state,defeated=True,defeat_cause=cause),cause,(RULE,)))
        self.assertEqual((result.target_state.wounds,result.target_state.wound_limit,
            result.target_state.defeated,result.target_state.defeat_cause),(0,1,True,cause))
        self.assertEqual(result.target_state.conditions,source.target_state.conditions)
        self.assertEqual(result.follow_ups,(cause,))
        self.assertEqual(result.applied_secondary_rule_ids,(RULE,))
        self.assertIsNone(result.stagger)
        self.assertIsNone(result.profile_wound)
        self.assertIsNone(result.character_wound)
        self.assertIsNone(result.pending_character_wound)

    def test_first_stagger_adds_condition_without_a_defeat_or_cause(self):
        result=execute(request(staggered=False),[1,10])
        self.assertIs(result.stagger.outcome,StaggerOutcome.CONDITION_ADDED)
        self.assertEqual(result.target_state,ProfileInjuryState(0,1,
            ConditionState(frozenset({Condition.STAGGERED}))))
        self.assertIsNone(result.minion_stagger_defeat)
        self.assertEqual(result.follow_ups,())

    def test_direct_damaging_hit_keeps_normal_one_wound_defeat(self):
        result=execute(request(base=6),[1,10])
        self.assertEqual((result.target_state.wounds,result.target_state.defeated),(1,True))
        self.assertIsNone(result.target_state.defeat_cause)
        self.assertIsNone(result.minion_stagger_defeat)
        self.assertEqual(result.profile_wound.wounds_inflicted,1)
        self.assertEqual(result.follow_ups,(result.profile_wound.state_change,))

    def test_miss_leaves_target_alive_and_never_applies_its_spec(self):
        source=request()
        result=execute(source,[10,1])
        self.assertEqual(result.target_state,source.target_state)
        self.assertIsNone(result.minion_stagger_defeat)
        self.assertIsNone(result.profile_wound)
        self.assertEqual(len(result.follow_ups),1)  # Attacker's ordinary first Staggered.

    def test_already_staggered_attacker_miss_does_not_invent_repeated_stagger(self):
        source=request()
        source=replace(source,attack=replace(source.attack,attacker_is_staggered=True))
        result=execute(source,[10,1])
        self.assertEqual(result.target_state,source.target_state)
        self.assertEqual(result.follow_ups,())
        self.assertIsNone(result.minion_stagger_defeat)

    def test_defenceless_forced_wound_precedes_repeated_stagger_replacement(self):
        source=request()
        source=replace(source,target_state=replace(source.target_state,conditions=ConditionState(
            frozenset({Condition.STAGGERED,Condition.DEFENCELESS}))))
        result=execute(source,[1,10])
        self.assertEqual((result.target_state.wounds,result.target_state.defeated),(1,True))
        self.assertIsNone(result.minion_stagger_defeat)
        self.assertIsNone(result.target_state.defeat_cause)

    def test_absent_spec_keeps_the_ordinary_minion_stagger_choice(self):
        source=replace(request(),minion_stagger_defeat=None)
        decisions=Mock()
        decisions.choose_repeated_stagger.return_value=StaggerChoice.SUFFER_WOUND
        rng=ScriptedD10([1,10])
        result=resolve_kernel_attack(source,rng,decisions=decisions)
        rng.assert_exhausted()
        decisions.choose_repeated_stagger.assert_called_once()
        self.assertIs(result.stagger.outcome,StaggerOutcome.WOUND_REQUESTED)
        self.assertEqual((result.target_state.wounds,result.target_state.defeated),(1,True))
        self.assertIsNone(result.target_state.defeat_cause)
        self.assertIsNone(result.minion_stagger_defeat)

    def test_stagger_entry_itself_uses_same_typed_result_without_a_decision(self):
        source=request()
        impact=StaggerImpactRequest(source.id,source.target_id,source.target_policy,
            source.target_state,True,False,minion_stagger_defeat=source.minion_stagger_defeat)
        rng=ScriptedD10([])
        result=resolve_stagger_impact(impact,rng)
        rng.assert_exhausted()
        self.assertEqual(result.minion_stagger_defeat.cause,result.state.defeat_cause)
        self.assertIsNone(result.stagger)

    def test_spec_is_restricted_to_exact_one_wound_live_minions(self):
        source=request()
        for policy,state in ((TargetInjuryPolicy.BRUTE,ProfileInjuryState(0,2)),
                (TargetInjuryPolicy.PLAYER,CharacterInjuryState()),
                ('minion',ProfileInjuryState(0,1)),
                (TargetInjuryPolicy.MINION,ProfileInjuryState(1,1,defeated=True))):
            with self.subTest(policy=policy,state=state),self.assertRaises((TypeError,ValueError)):
                replace(source,target_policy=policy,target_state=state)
        for value in (False,{},'dirty-coward'):
            with self.subTest(spec=value),self.assertRaises(TypeError):
                replace(source,minion_stagger_defeat=value)

    def test_original_profile_defeat_invariant_still_holds_without_explicit_cause(self):
        with self.assertRaises(ValueError):
            ProfileInjuryState(0,1,defeated=True)
        with self.assertRaises(ValueError):
            ProfileInjuryState(1,1,defeated=False)
        cause=MinionStaggerDefeatCause('source','target',RULE)
        for kwargs in ({'wounds':0,'wound_limit':2,'defeated':True},
                {'wounds':1,'wound_limit':1,'defeated':True},
                {'wounds':0,'wound_limit':1,'defeated':False}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                ProfileInjuryState(**kwargs,defeat_cause=cause)

    def test_cause_and_receipt_cannot_change_source_or_apply_to_different_state(self):
        result=execute(request(),[1,10]).minion_stagger_defeat
        for cause in (replace(result.cause,source_id='other'),replace(result.cause,rule_id='other')):
            with self.subTest(cause=cause),self.assertRaises(ValueError):
                replace(result,cause=cause)
        for value in ((),[RULE],('other',),(RULE,RULE)):
            with self.subTest(rules=value),self.assertRaises(ValueError):
                replace(result,applied_rule_ids=value)
        with self.assertRaises(ValueError):
            replace(result,state=ProfileInjuryState(0,1))

    def test_cached_wrong_spec_or_cause_types_are_rejected_before_rng(self):
        source=deepcopy(request())
        object.__setattr__(source.minion_stagger_defeat,'rule_id',True)
        rng=Mock(side_effect=AssertionError('bad source cannot consume RNG'))
        with self.assertRaises(TypeError):
            resolve_kernel_attack(source,rng)
        rng.randint.assert_not_called()
        for values in ((True,'goblin',RULE),('source',False,RULE),('source','goblin',False)):
            with self.subTest(values=values),self.assertRaises(TypeError):
                MinionStaggerDefeatCause(*values)

    def test_forced_minion_defeat_cause_cannot_be_relabelled_as_another_npc_policy(self):
        source=request()
        state=execute(source,[1,10]).target_state
        for policy in (TargetInjuryPolicy.BRUTE,TargetInjuryPolicy.MONSTROSITY,'minion'):
            with self.subTest(policy=policy),self.assertRaises((TypeError,ValueError)):
                replace(source,target_policy=policy,target_state=state,minion_stagger_defeat=None)
            with self.subTest(impact=policy),self.assertRaises((TypeError,ValueError)):
                StaggerImpactRequest('impact','goblin',policy,state,True,False)

    def test_shared_condition_projection_preserves_explicit_defeat_cause(self):
        state=execute(request(),[1,10]).target_state
        effect=ConditionAfterGiveGroundRequest('external-give-ground',Condition.DRAINED,'RULE:test-condition')
        result=resolve_condition_after_give_ground(effect,state)
        self.assertEqual(result.state.defeat_cause,state.defeat_cause)
        self.assertEqual((result.state.wounds,result.state.defeated),(0,True))
        self.assertTrue(result.state.conditions.has(Condition.DRAINED))

    def test_shared_non_wounding_hazard_projection_preserves_explicit_defeat_cause(self):
        state=execute(request(),[1,10]).target_state
        exposure=HazardExposureRequest('external-hazard','avoidance',1,Skill.ENDURANCE,
            'RULE:test-hazard',False,(Condition.DRAINED,))
        rng=ScriptedD10([10])
        test=resolve_test(TestRequest('avoidance',InlineProfile(1,3)),rng)
        source=HazardResolutionRequest('hazard','goblin',exposure,test,TargetInjuryPolicy.MINION,state)
        result=resolve_hazard(source,rng)
        rng.assert_exhausted()
        self.assertEqual(result.state.defeat_cause,state.defeat_cause)
        self.assertEqual((result.state.wounds,result.state.defeated),(0,True))
        self.assertTrue(result.state.conditions.has(Condition.DRAINED))


if __name__=='__main__':
    unittest.main()
