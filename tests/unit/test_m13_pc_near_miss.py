"""Literal PC Fate strategies at the actual post-table Wound decision window."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario, make_pc_melee_party_scenario
from tests.support.pc_melee_scripted import ScriptedD10, first_wound_script
from towr.domain.condition_models import Condition
from towr.domain.fate_models import (
    FateSessionState, FateNearMissBurnRequest, FateSpendRecord, FateSpendKind,
    FATE_NEAR_MISS_RULE_ID, FATE_GLORIOUS_RULE_ID,
)
from towr.domain.pc_melee_models import PcFatePolicy, PcNearMissPolicy
from towr.domain.pc_melee_result_models import (
    PcWoundCompletionProof, PcMeleeOutcome, PcMeleeStep, PcFateDecline, PcAttackProof,
    build_pc_wound_completion,
)
from towr.domain.resolution_models import ConsumeWoundNegationRequest
from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleOutcome
from towr.domain.injury_models import WoundRestriction, WoundRestrictionEffect
from towr.domain.test_models import TestQuality
from towr.engine.pc_melee_runner import run_pc_melee_scenario, apply_pc_melee_step
from towr.rules.fate_resolution import burn_fate
from towr.rules.wound_lifecycle_resolution import complete_character_wound_lifecycle


def active(source, threshold=1, reserve=0):
    return replace(source,party=tuple(replace(member,
        fate_policy=PcFatePolicy.CONFIGURED,
        near_miss_policy=PcNearMissPolicy(threshold,reserve)) for member in source.party))


def execute(source, values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def completions(result):
    return tuple(s for s in result.steps if isinstance(s.proof,PcWoundCompletionProof))


def third_wound(total):
    # First two Wounds are1 and2. The actual third table roll has three dice.
    dice = [10,1,total-11] if total <= 21 else [10,10,total-20]
    return ([10,10,10,1,1]
        + [1,1,1,10,10,10,1]
        + [1,1,1,10,10,10,1,1]
        + [1,1,1,10,10,10] + dice)


class PcNearMissTests(unittest.TestCase):
    def test_explicit_strategy_validation(self):
        member = make_pc_melee_scenario().party[0]
        for threshold,reserve in ((True,0),(1,False),(0,0),(1,-1)):
            with self.subTest(threshold=threshold,reserve=reserve), self.assertRaises((TypeError,ValueError)):
                PcNearMissPolicy(threshold,reserve)
        with self.assertRaises(ValueError):
            replace(member,near_miss_policy=PcNearMissPolicy(1,0))
        with self.assertRaises((TypeError,ValueError)):
            replace(member,fate_policy=PcFatePolicy.CONFIGURED)

    def test_inclusive_threshold_negates_wound_and_preserves_staggered_without_follow_up_rng(self):
        source = active(make_pc_melee_scenario(max_rounds=1),8)
        result = execute(source,first_wound_script(8)[:-1])
        member = result.state.party[0]
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
        self.assertEqual(member.fate.rating,2)
        self.assertEqual(member.fate.session_spend_limit,2)
        self.assertEqual(source.party[0].fate.rating,3)
        self.assertEqual(member.injury.wounds,())
        self.assertTrue(member.injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(member.injury.active_wound_effects)
        self.assertEqual(member.daily_wounds.wound_count,0)
        step, = completions(result)
        self.assertIsNone(step.proof.fate_decline)
        self.assertIs(step.proof.completion.outcome,CharacterWoundLifecycleOutcome.NEAR_MISS)
        self.assertIsNone(step.proof.completion.wound_effect)

    def test_below_threshold_keeps_actual_wound_and_fate(self):
        source = active(make_pc_melee_scenario(max_rounds=1),9)
        result = execute(source,first_wound_script(8))
        member = result.state.party[0]
        self.assertEqual(member.fate,source.party[0].fate)
        self.assertEqual(member.injury.wounds[0].table_total,8)
        self.assertIs(completions(result)[0].proof.fate_decline.policy,PcFatePolicy.CONFIGURED)

    def test_reserve_and_zero_rating_accept_wound(self):
        for rating,reserve in ((3,3),(3,4),(0,0)):
            with self.subTest(rating=rating,reserve=reserve):
                source = active(make_pc_melee_scenario(max_rounds=1),1,reserve)
                source = replace(source,party=(replace(source.party[0],
                    fate=FateSessionState('session',source.party[0].actor_id,rating,rating)),))
                result = execute(source,first_wound_script(1))
                self.assertEqual(result.state.party[0].fate,source.party[0].fate)
                self.assertEqual(len(result.state.party[0].injury.wounds),1)

    def test_exhausted_spending_does_not_prevent_burning_and_retains_history(self):
        source = active(make_pc_melee_scenario(max_rounds=1))
        member = source.party[0]
        spend = FateSpendRecord('old-spend','session',member.actor_id,
            FateSpendKind.GLORIOUS_TEST,'old-test',FATE_GLORIOUS_RULE_ID)
        initial = FateSessionState('session',member.actor_id,2,2,(spend,))
        old = burn_fate(FateNearMissBurnRequest('old-burn',initial,
            ConsumeWoundNegationRequest('old-wound',FATE_NEAR_MISS_RULE_ID))).state
        source = replace(source,party=(replace(member,fate=old),))
        result = execute(source,first_wound_script(1))
        state = result.state.party[0].fate
        self.assertEqual(state.rating,0)
        self.assertEqual(state.session_spend_limit,1)
        self.assertEqual(state.spends,old.spends)
        self.assertEqual(state.burns[:-1],old.burns)
        self.assertEqual(state.resource_event_ids[:-1],old.resource_event_ids)
        self.assertFalse(state.burns[-1].current_session_allowance_reduced)

    def test_lethal_or_anatomical_wound_is_negated_before_death_or_body_work(self):
        for total in (20,24,27):
            with self.subTest(total=total):
                result = execute(active(make_pc_melee_scenario(enemy_count=3,max_rounds=1),20),third_wound(total))
                member = result.state.party[0]
                self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
                self.assertEqual([w.table_total for w in member.injury.wounds],[1,2])
                self.assertFalse(member.injury.dead)
                self.assertFalse(member.body_facts)
                self.assertEqual(member.daily_wounds.wound_count,2)
                self.assertEqual(member.fate.rating,2)

    def test_consecutive_burns_preserve_wound_dice_and_stop_at_reserve(self):
        source = active(make_pc_melee_scenario(enemy_count=3,max_rounds=1),1,1)
        # Two burned Wounds do not raise the next table pool above a single die.
        result = execute(source,[10,10,10,1,1] + [1,1,1,10,10,10,1]*3)
        member = result.state.party[0]
        self.assertEqual(member.fate.rating,1)
        self.assertEqual(len(member.fate.burns),2)
        self.assertEqual([w.table_total for w in member.injury.wounds],[1])
        self.assertEqual(member.daily_wounds.wound_count,1)
        first,second,third = completions(result)
        self.assertEqual(second.proof.completion.source_request.consumed_near_miss_effect_ids,
            first.proof.completion.consumed_near_miss_effect_ids)
        self.assertEqual(third.proof.completion.source_request.consumed_near_miss_effect_ids,
            second.proof.completion.consumed_near_miss_effect_ids)

    def test_party_resources_remain_independent(self):
        for priority in (('pc1','pc2'),('pc2','pc1')):
            with self.subTest(priority=priority):
                source = active(make_pc_melee_party_scenario(pc_count=2,enemy_count=2,max_rounds=1))
                source = replace(source,enemy_target_priority=priority)
                result = execute(source,[10,10,10,1,1]*2 + [1,1,10,10,10,1]*2)
                hit,spared = (result.state.participant(actor) for actor in priority)
                self.assertEqual(hit.fate.rating,1)
                self.assertEqual(spared.fate,source.participant(spared.actor_id).fate)
                self.assertEqual(spared.injury.wounds,())

    def test_near_miss_does_not_restore_grim_consumed_by_actual_protection_test(self):
        source = active(make_pc_melee_scenario(enemy_count=2,max_rounds=1),20)
        result = execute(source,[10,10,10,1,1]
            + [1,1,1,10,10,10,10]
            + [1,1,1,10,10,10,10,10])
        member = result.state.party[0]
        self.assertEqual([w.table_total for w in member.injury.wounds],[10])
        self.assertTrue(member.injury.conditions.has(Condition.DRAINED))
        self.assertFalse(any(isinstance(e,WoundRestrictionEffect)
            and e.restriction is WoundRestriction.NEXT_TEST_IS_GRIM for e in member.injury.active_wound_effects))
        second_attack = next(s.proof for s in result.steps
            if isinstance(s.proof,PcAttackProof) and s.proof.request.actor_id == 'minion2')
        self.assertIs(second_attack.execution.resolution.attack.defender_test.trace.quality,TestQuality.GRIM)

    def test_replay_or_mutated_owner_is_rejected(self):
        result = execute(active(make_pc_melee_scenario(max_rounds=1)),first_wound_script(1))
        step, = completions(result)
        self.assertEqual(apply_pc_melee_step(step.source,step),step.state)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(step.state,step)
        with self.assertRaises(ValueError):
            replace(step.state,party=(replace(step.state.party[0],fate=step.source.party[0].fate),))
        forged = deepcopy(step.proof)
        object.__setattr__(forged.completion.fate_burn.burn,'current_session_allowance_reduced',1)
        self.assertEqual(forged,step.proof)
        with self.assertRaises((ValueError,TypeError)):
            PcMeleeStep(step.source,forged)

    def test_policy_cannot_decline_selected_burn_or_burn_below_threshold(self):
        result = execute(active(make_pc_melee_scenario(max_rounds=1)),first_wound_script(1))
        step, = completions(result)
        request = build_pc_wound_completion(step.source)
        declined = replace(request,near_miss=None,daily_registration_id=request.id+':forged-daily')
        forged = PcWoundCompletionProof(complete_character_wound_lifecycle(declined),
            PcFateDecline('pc',request.roll.request_id,'wound',PcFatePolicy.CONFIGURED))
        with self.assertRaises(ValueError):
            PcMeleeStep(step.source,forged)
        with self.assertRaises(ValueError):
            PcMeleeStep(step.source,replace(step.proof,fate_decline=forged.fate_decline))
        declined_result = execute(active(make_pc_melee_scenario(max_rounds=1),2),first_wound_script(1))
        declined_step, = completions(declined_result)
        request = build_pc_wound_completion(declined_step.source)
        forced_burn = FateNearMissBurnRequest(request.roll.request_id+':near-miss-burn',
            declined_step.source.party[0].fate,
            ConsumeWoundNegationRequest(request.roll.source_request.wound.id,FATE_NEAR_MISS_RULE_ID))
        request = replace(request,near_miss=forced_burn,daily_registration_id=None)
        with self.assertRaises((ValueError,TypeError)):
            PcMeleeStep(declined_step.source,PcWoundCompletionProof(complete_character_wound_lifecycle(request),None))

    def test_burn_cannot_replace_current_resource_snapshot(self):
        result = execute(active(make_pc_melee_scenario(max_rounds=1)),first_wound_script(1))
        step, = completions(result)
        request = build_pc_wound_completion(step.source)
        foreign = replace(request.near_miss,state=FateSessionState('foreign-session','pc',3,3))
        completion = complete_character_wound_lifecycle(replace(request,near_miss=foreign))
        with self.assertRaises(ValueError):
            PcMeleeStep(step.source,PcWoundCompletionProof(completion,None))

    def test_supplied_resource_id_collision_allocates_fresh_deterministic_id(self):
        source = active(make_pc_melee_scenario(max_rounds=1))
        baseline = execute(source,first_wound_script(1))
        step, = completions(baseline)
        base_id = step.proof.completion.fate_burn.request_id
        member = source.party[0]
        old = burn_fate(FateNearMissBurnRequest(base_id,
            replace(member.fate,rating=4,session_spend_limit=4),
            ConsumeWoundNegationRequest('old-unrelated-wound',FATE_NEAR_MISS_RULE_ID))).state
        source = replace(source,party=(replace(member,fate=old),))
        result = execute(source,first_wound_script(1))
        self.assertEqual(result.state.party[0].fate.burns[:-1],old.burns)
        self.assertEqual(result.state.party[0].fate.burns[-1].id,base_id+':1')
        self.assertEqual(result.state.party[0].fate.rating,2)

    def test_cancelled_wound_receipt_rejects_equal_noncanonical_nested_types(self):
        result = execute(active(make_pc_melee_scenario(max_rounds=1)),first_wound_script(1))
        step, = completions(result)
        proof = deepcopy(step.proof)
        application = proof.completion.near_miss_application
        changed = replace(application.cancelled_wound,roll_values=(True,))
        object.__setattr__(application,'cancelled_wound',changed)
        self.assertEqual(proof,step.proof)
        with self.assertRaises(TypeError):
            PcMeleeStep(step.source,proof)

    def test_near_miss_provenance_headers_reject_equal_string_enums(self):
        result = execute(active(make_pc_melee_scenario(max_rounds=1)),first_wound_script(1))
        step, = completions(result)
        for branch,headers in (
                ('near_miss_application',('request_id','rule_id','session_id','target_id','applied_rule_ids')),
                ('fate_burn',('request_id','rule_id','applied_rule_ids')),
                (None,('request_id','rule_id','applied_rule_ids','consumed_roll_ids','consumed_near_miss_effect_ids'))):
            for header in headers:
                with self.subTest(branch=branch,header=header):
                    proof = deepcopy(step.proof)
                    target = getattr(proof.completion,branch) if branch else proof.completion
                    value = getattr(target,header)
                    text = value[0] if type(value) is tuple else value
                    alias = Enum('ForeignString',{'VALUE':text},type=str).VALUE
                    changed = (alias,*value[1:]) if type(value) is tuple else alias
                    object.__setattr__(target,header,changed)
                    self.assertEqual(proof,step.proof)
                    with self.assertRaises(TypeError):
                        PcMeleeStep(step.source,proof)


if __name__ == '__main__':
    unittest.main()
