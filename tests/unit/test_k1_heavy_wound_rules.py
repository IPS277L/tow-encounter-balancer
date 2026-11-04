"""PG123/190 heavy-Wound rules with actual Tests and bounded RNG traces."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.attack_models import (
    AttackOutcome, AttackRequest, ConditionImpactSpec, DamageImpactSpec,
    DamageProfile, ImpactOutcome, ResilienceProfile,
)
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.critical_injury_models import CriticalInjuryTestRequest
from towr.domain.fate_models import FATE_NEAR_MISS_RULE_ID, FateNearMissBurnRequest, FateSessionState
from towr.domain.infection_models import DailyWoundState
from towr.domain.injury_models import (
    CharacterInjuryState, CharacterWoundRequest, FixedCharacterWoundRequest,
    ProfileInjuryState, WoundConditionEffect, WoundEffectDuration, WoundEntryId,
    WoundRecord, WoundRestriction, WoundRestrictionEffect,
)
from towr.domain.resolution_models import (
    ConsumeWoundNegationRequest, KernelAttackRequest, TargetInjuryPolicy,
    condition_forces_wound,
)
from towr.domain.test_models import InlineProfile, TestRequest
from towr.domain.wound_lifecycle_models import (
    CharacterWoundLifecycleCompletionRequest, CharacterWoundLifecycleOutcome,
    CharacterWoundLifecycleRollRequest,
)
from towr.rules.attack_resolution import resolve_attack
from towr.rules.critical_injury_resolution import resolve_critical_injury_test
from towr.rules.injury_resolution import resolve_character_wound, resolve_fixed_character_wound
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.test_resolution import resolve_test
from towr.rules.wound_lifecycle_resolution import (
    complete_character_wound_lifecycle, roll_character_wound_lifecycle,
)


class NoRepeatedChoice:
    def choose_repeated_stagger(self, **kwargs):
        raise AssertionError('forced Wound cannot offer repeated Staggered choices')


def request(state, *, policy=TargetInjuryPolicy.PLAYER, physical=False):
    attack = AttackRequest('attack',TestRequest('attack:test',InlineProfile(1,5)),None,
        DamageImpactSpec(DamageProfile(0),ResilienceProfile(100)),True,False)
    return KernelAttackRequest('kernel','pc',attack,policy,state,False,False,
                               physical_attack=physical)


def staggered_wound(entry=WoundEntryId.SCARRING_STRIKE):
    total = 15 if entry is WoundEntryId.SCARRING_STRIKE else 19
    values = (7,8) if total == 15 else (9,10)
    wound = WoundRecord(1,entry,total,values,effect_resolved=True)
    effect = WoundConditionEffect(1,Condition.STAGGERED,WoundEffectDuration.UNTIL_HEALED)
    return CharacterInjuryState((wound,),ConditionState(frozenset({Condition.STAGGERED})),(effect,))


def endurance(test_id='critical:test', value=10):
    return resolve_test(TestRequest(test_id,InlineProfile(1,5)),ScriptedD10([value]))


class HeavyWoundRuleTests(unittest.TestCase):
    def test_defenceless_low_damage_hit_opens_real_lifecycle_without_rewriting_attack(self):
        state = CharacterInjuryState(conditions=ConditionState(
            frozenset({Condition.DEFENCELESS,Condition.STAGGERED})))
        source = request(state)
        rng = ScriptedD10([1,3])
        result = resolve_kernel_attack(source,rng,decisions=NoRepeatedChoice())
        rng.assert_exhausted()
        self.assertIs(result.attack.outcome,AttackOutcome.HIT)
        self.assertIs(result.attack.impact,ImpactOutcome.STAGGERED)
        self.assertEqual((result.attack.damage,result.attack.effective_resilience),(1,100))
        self.assertEqual(result.attack.impact_spec,source.attack.impact_spec)
        self.assertTrue(condition_forces_wound(source,result.attack))
        self.assertIsNotNone(result.pending_character_wound)
        self.assertIsNone(result.stagger)
        self.assertEqual(result.character_wound.table_roll.values,(3,))
        self.assertFalse(result.character_wound.state.wounds[0].effect_resolved)
        self.assertEqual(result.pending_character_wound.source_request.wound.state,state)

    def test_defenceless_profile_npc_uses_its_real_limit_without_table_roll(self):
        state = ProfileInjuryState(0,2,conditions=ConditionState(frozenset({Condition.DEFENCELESS})))
        rng = ScriptedD10([1])
        result = resolve_kernel_attack(request(state,policy=TargetInjuryPolicy.BRUTE),rng)
        rng.assert_exhausted()
        self.assertEqual(result.target_state.wounds,1)
        self.assertFalse(result.target_state.defeated)
        self.assertEqual(result.target_state.wound_limit,2)
        self.assertIsNone(result.pending_character_wound)
        self.assertEqual(result.profile_wound.wounds_inflicted,1)

    def test_defenceless_miss_cannot_force_a_wound(self):
        source = request(CharacterInjuryState(conditions=ConditionState(frozenset({Condition.DEFENCELESS}))))
        rng = ScriptedD10([10])
        result = resolve_kernel_attack(source,rng)
        rng.assert_exhausted()
        self.assertFalse(condition_forces_wound(source,result.attack))
        self.assertIsNone(result.pending_character_wound)
        self.assertEqual(result.target_state,source.target_state)

    def test_ruptured_organs_requires_confirmed_physical_damage_attack(self):
        wound = WoundRecord(1,WoundEntryId.RUPTURED_ORGANS,22,(10,10,2),
            treated=True,effect_resolved=True)
        restriction = WoundRestrictionEffect(1,WoundRestriction.PHYSICAL_STAGGER_BECOMES_WOUND,
            WoundEffectDuration.PERMANENT)
        state = CharacterInjuryState((wound,),active_wound_effects=(restriction,))
        for physical in (False,True):
            source = request(state,physical=physical)
            rng = ScriptedD10([1,3] if physical else [1])
            result = resolve_kernel_attack(source,rng)
            rng.assert_exhausted()
            with self.subTest(physical=physical):
                self.assertEqual(condition_forces_wound(source,result.attack),physical)
                self.assertEqual(result.pending_character_wound is not None,physical)
                self.assertIs(result.attack.impact,ImpactOutcome.STAGGERED)
                self.assertEqual((result.attack.damage,result.attack.effective_resilience),(1,100))
        with self.assertRaises(TypeError):
            replace(source,physical_attack=1)
        detached = replace(result.attack,request_id='another-attack')
        with self.assertRaises(ValueError):
            condition_forces_wound(source,detached)

    def test_non_damage_impact_is_not_reinterpreted_by_the_bounded_damage_rule(self):
        source = request(CharacterInjuryState(conditions=ConditionState(frozenset({Condition.DEFENCELESS}))))
        source = replace(source,attack=replace(source.attack,
            impact_spec=ConditionImpactSpec(Condition.BROKEN,'authored:fear')))
        actual = resolve_attack(source.attack,ScriptedD10([1]))
        self.assertFalse(condition_forces_wound(source,actual))

    def test_new_rolled_and_fixed_wounds_retain_ongoing_staggered_sources(self):
        for entry in (WoundEntryId.SCARRING_STRIKE,WoundEntryId.BLACKING_OUT):
            source = staggered_wound(entry)
            rolled = resolve_character_wound(CharacterWoundRequest('new',source),ScriptedD10([1,1]))
            fixed = resolve_fixed_character_wound(FixedCharacterWoundRequest(
                'fixed',source,WoundEntryId.SUPERFICIAL_INJURY,3,'authored:fixed'))
            for result in (rolled,fixed):
                with self.subTest(entry=entry,result=type(result).__name__):
                    self.assertTrue(result.state.conditions.has(Condition.STAGGERED))
                    self.assertEqual(result.state.active_wound_effects,source.active_wound_effects)
                    self.assertEqual(len(result.state.wounds),2)
        ordinary = CharacterInjuryState(conditions=ConditionState(frozenset({Condition.STAGGERED})))
        result = resolve_character_wound(CharacterWoundRequest('ordinary',ordinary),ScriptedD10([1]))
        self.assertFalse(result.state.conditions.has(Condition.STAGGERED))

    def test_near_miss_restores_exact_prior_staggered_and_ongoing_effects(self):
        source = staggered_wound()
        request = CharacterWoundLifecycleRollRequest('roll','pc',CharacterWoundRequest('wound',source))
        rolled = roll_character_wound_lifecycle(request,ScriptedD10([1,1]))
        burn = FateNearMissBurnRequest('burn',FateSessionState('session','pc',1,1),
            ConsumeWoundNegationRequest('wound',FATE_NEAR_MISS_RULE_ID))
        result = complete_character_wound_lifecycle(CharacterWoundLifecycleCompletionRequest(
            'complete',rolled,rolled.wound_result.state,DailyWoundState('day','pc'),near_miss=burn))
        self.assertIs(result.outcome,CharacterWoundLifecycleOutcome.NEAR_MISS)
        self.assertEqual(result.state,source)
        self.assertEqual(result.daily_wounds.wound_count,0)

    def test_critical_endurance_success_preserves_state_including_defenceless(self):
        for defenceless in (False,True):
            conditions = {Condition.CRITICALLY_INJURED}
            if defenceless:
                conditions.add(Condition.DEFENCELESS)
            source = CharacterInjuryState(conditions=ConditionState(frozenset(conditions)))
            result = resolve_critical_injury_test(CriticalInjuryTestRequest(
                'critical','pc',source,'critical:test'),endurance(value=1))
            self.assertIs(result.state,source)
            self.assertFalse(result.state.dead)

    def test_critical_failures_add_defenceless_then_kill_without_another_wound(self):
        source = CharacterInjuryState(conditions=ConditionState(frozenset({Condition.CRITICALLY_INJURED})))
        first = resolve_critical_injury_test(CriticalInjuryTestRequest(
            'critical:1','pc',source,'critical:test'),endurance())
        self.assertTrue(first.state.conditions.has(Condition.DEFENCELESS))
        self.assertFalse(first.state.dead)
        second = resolve_critical_injury_test(CriticalInjuryTestRequest(
            'critical:2','pc',first.state,'critical:test:2'),endurance('critical:test:2'))
        self.assertTrue(second.state.dead)
        self.assertEqual(second.state.wounds,source.wounds)
        self.assertEqual(second.state.active_wound_effects,source.active_wound_effects)
        self.assertTrue(second.state.conditions.has(Condition.CRITICALLY_INJURED))

    def test_critical_source_test_id_state_and_equal_but_wrong_types_are_rejected(self):
        source = CharacterInjuryState(conditions=ConditionState(frozenset({Condition.CRITICALLY_INJURED})))
        request = CriticalInjuryTestRequest('critical','pc',source,'critical:test')
        good = resolve_critical_injury_test(request,endurance())
        with self.assertRaises(ValueError):
            resolve_critical_injury_test(request,endurance('foreign'))
        for state in (CharacterInjuryState(),replace(source,dead=True)):
            with self.subTest(state=state),self.assertRaises(ValueError):
                replace(request,state=state)
        forged = deepcopy(good.test)
        object.__setattr__(forged.trace,'successes',False)
        with self.assertRaises(TypeError):
            resolve_critical_injury_test(request,forged)
        with self.assertRaises(ValueError):
            replace(good,state=source)
        forged_state = deepcopy(good.state)
        object.__setattr__(forged_state,'dead',0)
        with self.assertRaises(TypeError):
            replace(good,state=forged_state)


if __name__ == '__main__':
    unittest.main()
