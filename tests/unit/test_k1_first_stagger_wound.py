"""An explicit first-Staggered replacement retains the real Attack and one Wound ACK."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import unittest
from unittest.mock import Mock

from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.attack_models import (
    AttackRequest,AttackOutcome,ConditionImpactSpec,ConditionOnGiveGroundOrWoundSpec,
    ConditionOnHitSpec,DamageImpactSpec,DamageProfile,ImpactOutcome,ResilienceProfile,
)
from towr.domain.condition_models import Condition,ConditionState,StaggerChoice,StaggerOutcome
from towr.domain.injury_models import (
    AdditionalProfileWound,CharacterInjuryState,MinionStaggerDefeatSpec,
    ProfileInjuryState,ProfileNpcType,
)
from towr.domain.resolution_models import (
    FirstStaggerWoundSpec,KernelAttackRequest,StaggerImpactRequest,TargetInjuryPolicy,
)
from towr.domain.test_models import InlineProfile,TestRequest
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.stagger_impact_resolution import resolve_stagger_impact


RULE='RULE-PROFILE-IMPERIAL-006:feel-no-pain'


def request(*,base=3,conditions=(),selected=True):
    attack=AttackRequest('attack',TestRequest('a',InlineProfile(1,3)),
        TestRequest('d',InlineProfile(1,3)),DamageImpactSpec(DamageProfile(base),ResilienceProfile(5)),True,False)
    return KernelAttackRequest('kernel','target',attack,TargetInjuryPolicy.BRUTE,
        ProfileInjuryState(0,2,ConditionState(frozenset(conditions))),True,False,
        physical_attack=True,first_stagger_wound=FirstStaggerWoundSpec(RULE) if selected else None)


def execute(source,values):
    rng=ScriptedD10(values)
    result=resolve_kernel_attack(source,rng)
    rng.assert_exhausted()
    return result


class FirstStaggerWoundTests(unittest.TestCase):
    def test_weak_hit_preserves_real_damage_impact_and_replaces_first_stagger_with_one_wound(self):
        source=request()
        result=execute(source,[1,10])
        self.assertIs(result.attack.outcome,AttackOutcome.HIT)
        self.assertIs(result.attack.impact,ImpactOutcome.STAGGERED)
        self.assertEqual((result.attack.damage,result.attack.effective_resilience),(4,5))
        self.assertEqual(result.attack.impact_spec,source.attack.impact_spec)
        self.assertEqual((result.target_state.wounds,result.target_state.defeated),(1,False))
        self.assertFalse(result.target_state.conditions.has(Condition.STAGGERED))
        self.assertIs(result.stagger.outcome,StaggerOutcome.WOUND_REQUESTED)
        self.assertEqual((result.stagger.state,result.stagger.allowed_choices,result.stagger.selected_choice,
            result.stagger.wound_requested,result.stagger.gave_ground),
            (source.target_state.conditions,(),None,True,False))
        self.assertEqual(result.applied_secondary_rule_ids,(RULE,))
        self.assertEqual((result.profile_wound.wounds_requested,result.profile_wound.wounds_inflicted),(1,1))
        self.assertEqual(result.follow_ups,(result.profile_wound.state_change,))
        self.assertEqual((result.profile_wound.state_change.npc_type,
            result.profile_wound.state_change.previous_wounds,result.profile_wound.state_change.current_wounds),
            (ProfileNpcType.BRUTE,0,1))
        self.assertIsNone(result.character_wound)
        self.assertIsNone(result.pending_character_wound)

    def test_direct_impact_entry_uses_no_rng_or_repeated_stagger_decision(self):
        source=request(conditions=(Condition.PRONE,Condition.DRAINED))
        impact=StaggerImpactRequest(source.id,source.target_id,source.target_policy,
            source.target_state,True,False,first_stagger_wound=source.first_stagger_wound)
        rng=ScriptedD10([]);decisions=Mock()
        result=resolve_stagger_impact(impact,rng,decisions=decisions)
        rng.assert_exhausted();decisions.choose_repeated_stagger.assert_not_called()
        self.assertEqual(result.state.conditions,source.target_state.conditions)
        self.assertEqual(result.applied_rule_ids,(RULE,))
        self.assertEqual(result.follow_ups,(result.profile_wound.state_change,))

    def test_absent_spec_keeps_ordinary_first_stagger_without_wound_or_source(self):
        result=execute(request(selected=False),[1,10])
        self.assertIs(result.stagger.outcome,StaggerOutcome.CONDITION_ADDED)
        self.assertEqual(result.target_state.wounds,0)
        self.assertTrue(result.target_state.conditions.has(Condition.STAGGERED))
        self.assertIsNone(result.profile_wound)
        self.assertEqual(result.applied_secondary_rule_ids,())

    def test_direct_wound_is_not_replaced_or_doubled(self):
        result=execute(request(base=6),[1,10])
        self.assertIs(result.attack.impact,ImpactOutcome.WOUND)
        self.assertEqual(result.target_state.wounds,1)
        self.assertIsNone(result.stagger)
        self.assertEqual(result.profile_wound.wounds_inflicted,1)
        self.assertEqual(result.applied_secondary_rule_ids,())

    def test_miss_leaves_target_unchanged_and_keeps_the_attackers_ordinary_pending_stagger(self):
        source=request()
        result=execute(source,[10,1])
        self.assertIs(result.attack.outcome,AttackOutcome.MISS)
        self.assertEqual(result.target_state,source.target_state)
        self.assertIsNone(result.profile_wound)
        self.assertIsNone(result.stagger)
        self.assertEqual(len(result.follow_ups),1)
        self.assertEqual(result.follow_ups[0].attack_id,'attack')
        self.assertEqual(result.applied_secondary_rule_ids,())

    def test_defenceless_forced_wound_precedes_first_stagger_replacement(self):
        result=execute(request(conditions=(Condition.DEFENCELESS,)),[1,10])
        self.assertEqual(result.target_state.wounds,1)
        self.assertIsNone(result.stagger)
        self.assertEqual(result.applied_secondary_rule_ids,())

    def test_other_policy_wounded_defeated_or_already_staggered_states_reject_spec(self):
        source=request()
        impact=StaggerImpactRequest(source.id,source.target_id,source.target_policy,
            source.target_state,True,False,first_stagger_wound=source.first_stagger_wound)
        cases=((TargetInjuryPolicy.PLAYER,CharacterInjuryState()),
            (TargetInjuryPolicy.CHAMPION,CharacterInjuryState()),
            (TargetInjuryPolicy.MINION,ProfileInjuryState(0,1)),
            (TargetInjuryPolicy.MONSTROSITY,ProfileInjuryState(0,3)),
            ('brute',ProfileInjuryState(0,2)),
            (TargetInjuryPolicy.BRUTE,ProfileInjuryState(1,2)),
            (TargetInjuryPolicy.BRUTE,ProfileInjuryState(2,2,defeated=True)),
            (TargetInjuryPolicy.BRUTE,ProfileInjuryState(0,2,ConditionState(frozenset({Condition.STAGGERED})))))
        for original in (source,impact):
            for policy,state in cases:
                with self.subTest(request=type(original),policy=policy,state=state),self.assertRaises((TypeError,ValueError)):
                    replace(original,target_policy=policy,target_state=state)

    def test_exact_spec_type_nonempty_source_and_incompatible_minion_spec_are_rejected(self):
        class Alias(str,Enum):
            RULE=RULE
        for value in ('',None,True,Alias.RULE):
            with self.subTest(rule=value),self.assertRaises(TypeError):FirstStaggerWoundSpec(value)
        for value in ('rule',{},True):
            with self.subTest(spec=value),self.assertRaises(TypeError):replace(request(),first_stagger_wound=value)
        with self.assertRaises(ValueError):
            replace(request(),minion_stagger_defeat=MinionStaggerDefeatSpec('other:rule'))

    def test_cached_equal_alias_is_readmitted_before_attack_rng(self):
        class Alias(str,Enum):
            RULE=RULE
        source=deepcopy(request())
        object.__setattr__(source.first_stagger_wound,'rule_id',Alias.RULE)
        self.assertEqual(source,request())
        rng=Mock()
        with self.assertRaises(TypeError):resolve_kernel_attack(source,rng)
        rng.randint.assert_not_called()
        source=deepcopy(request())
        object.__setattr__(source.target_state,'wounds',False)
        self.assertEqual(source,request())
        with self.assertRaises(TypeError):resolve_kernel_attack(source,rng)
        rng.randint.assert_not_called()

    def test_ordinary_repeated_stagger_remains_a_real_selected_wound_price(self):
        source=request(selected=False,conditions=(Condition.STAGGERED,))
        decisions=Mock();decisions.choose_repeated_stagger.return_value=StaggerChoice.SUFFER_WOUND
        rng=ScriptedD10([1,10]);result=resolve_kernel_attack(source,rng,decisions=decisions)
        rng.assert_exhausted();decisions.choose_repeated_stagger.assert_called_once()
        self.assertEqual(result.stagger.selected_choice,StaggerChoice.SUFFER_WOUND)
        self.assertEqual(result.applied_secondary_rule_ids,())

    def test_existing_secondary_conditions_and_additional_wounds_are_applied_once(self):
        source=request()
        source=replace(source,additional_profile_wounds=(AdditionalProfileWound('extra:wound'),),
            attack=replace(source.attack,secondary_effects=(
                ConditionOnHitSpec(Condition.DRAINED,'on:hit'),
                ConditionOnGiveGroundOrWoundSpec(Condition.BROKEN,'on:wound'))))
        result=execute(source,[1,10])
        self.assertEqual((result.target_state.wounds,result.target_state.defeated),(2,True))
        self.assertEqual(result.target_state.conditions.conditions,frozenset({Condition.DRAINED,Condition.BROKEN}))
        self.assertEqual(len(result.condition_applications),2)
        self.assertEqual(result.applied_secondary_rule_ids.count(RULE),1)
        self.assertEqual(result.follow_ups,(result.profile_wound.state_change,))

    def test_other_primary_impact_family_cannot_silently_carry_damage_replacement(self):
        source=request()
        condition=replace(source.attack,impact_spec=ConditionImpactSpec(Condition.STAGGERED,'condition:source'))
        with self.assertRaises(ValueError):replace(source,attack=condition)
