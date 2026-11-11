"""Literal Hochland Aim, paid second actions and one-use Aim lifecycles."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_hochland_scenarios import make_pc_hochland_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.aim_models import AimFollowUpOutcome
from towr.domain.attack_models import AttackOutcome
from towr.domain.condition_models import Condition
from towr.domain.fate_models import FateSpendFunding, FateSpendKind, FateSecondActionSpendRequest
from towr.domain.pc_aim_models import PcAimProof, PcAimSecondActionProof, PcAimConsumptionProof, build_pc_aim
from towr.domain.pc_melee_models import PcGloriousPolicy
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcBackupWeaponDrawProof, PcMeleeOutcome, PcMeleeStep,
    PcRecoverProof, PcTurnEndProof, PcFateDecline, build_pc_melee_attack, pc_melee_action_id,
)
from towr.domain.pc_ranged_models import PcRangedReloadProof, complete_pc_ranged_shot
from towr.domain.pc_short_opening_models import PcNpcApproachProof, PcRangedCloseUnsupported
from towr.domain.ranged_weapon_attack_preparation_models import OUTSIDE_OPTIMUM_RANGE_RULE_ID
from towr.domain.test_models import Skill, TestProfile, TestQuality
from towr.domain.turn_models import ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest, CombatTurnEndRequest
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.fate_resolution import spend_fate_for_second_action
from towr.rules.turn_resolution import reserve_combat_action_slot, end_combat_turn


AIM_ZERO = [10,10,10]
AIM_TWO = [1,1,10]
SHOT_MISS = [10,10,1,1]
SHOT_HIT = [1,1,10,10]
AIMED_ONE_HIT = [1,10,10,10,10,10]
NPC_MISS = [10,10,1,1,1]
NPC_HIT = [1,1,10,10,10]
SWORD_HIT = [1,1,1,10,10]


def execute(source, values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def steps(result, kind):
    return tuple(step for step in result.steps if type(step.proof) is kind)


def shots(result):
    return tuple(step for step in steps(result,PcAttackProof) if step.proof.ranged_shot is not None)


def raw(step):
    return step.proof.execution.resolution.attack


class PcHochlandTests(unittest.TestCase):
    def test_actual_aim_spend_and_slot_two_shot_are_one_owned_turn(self):
        result = execute(make_pc_hochland_scenario(max_rounds=1,npc_toughness=20),
            AIM_ZERO+SHOT_MISS+NPC_MISS)
        aim, = steps(result,PcAimProof)
        spend, = steps(result,PcAimSecondActionProof)
        shot, = shots(result)
        consumed, = steps(result,PcAimConsumptionProof)
        self.assertLess(result.steps.index(aim),result.steps.index(spend))
        self.assertLess(result.steps.index(spend),result.steps.index(shot))
        self.assertLess(result.steps.index(shot),result.steps.index(consumed))
        for step in (aim,spend,shot,consumed):
            self.assertEqual(step.source.round_state.round_number,1)
            self.assertEqual(step.source.round_state.active_turn.actor_id,'pc1')
            self.assertEqual(apply_pc_melee_step(step.source,step),step.state)
        self.assertEqual(aim.proof.result.awareness_test_result.successes,0)
        self.assertEqual(shot.proof.request.slot_index,2)
        slot = spend.state.round_state.active_turn.action_slots[-1]
        self.assertIs(slot.grant,ActionSlotGrant.FATE)
        self.assertIs(slot.declaration.kind,CombatActionKind.ATTACK)
        self.assertIsNone(slot.execution)
        self.assertIs(spend.proof.result.spend.kind,FateSpendKind.SECOND_ACTION)
        self.assertEqual(spend.proof.result.spend.session_cost,1)
        self.assertEqual(result.state.party[0].fate.remaining_spends,0)
        self.assertIs(consumed.proof.follow_up.outcome,AimFollowUpOutcome.APPLIED_TO_RANGED_ATTACK)
        self.assertEqual(result.executed_actions,3)
        self.assertEqual(steps(result,PcRangedReloadProof),())
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)

    def test_zero_and_two_aim_successes_use_actual_shooting_pool_and_charge_four(self):
        for aim_values,shot_values,dice,delta in ((AIM_ZERO,SHOT_HIT,2,-1),
                (AIM_TWO,AIMED_ONE_HIT,4,1)):
            source = make_pc_hochland_scenario(max_rounds=1,npc_toughness=20,
                npc_armour_bonus=5,npc_armoured=True)
            with self.subTest(aim_values=aim_values):
                result = execute(source,aim_values+shot_values+NPC_MISS)
                aim, = steps(result,PcAimProof)
                shot, = shots(result)
                attack = raw(shot)
                self.assertIs(attack.outcome,AttackOutcome.HIT)
                self.assertEqual(attack.attacker_test.trace.rolled_dice,dice)
                self.assertEqual(attack.attacker_test.trace.regular_dice_delta,delta)
                self.assertEqual(attack.impact_spec.damage.base,6)
                self.assertTrue(attack.impact_spec.ignores_armour)
                self.assertEqual(attack.effective_resilience,20)
                self.assertEqual(attack.impact_spec.damage_modifiers,())
                self.assertEqual(shot.proof.request.kernel_request.wound_dice_modifiers,())
                proof = shot.proof.ranged_shot
                self.assertEqual(proof.preparation.source_request.aim,aim.proof.result)
                self.assertIs(proof.preparation.aim_follow_up.outcome,AimFollowUpOutcome.APPLIED_TO_RANGED_ATTACK)
                self.assertFalse(proof.execution.weapon_state.loaded)
                self.assertEqual(proof.execution.weapon_state.required_successes,4)
                self.assertEqual(len(proof.execution.weapon_state.reload_cycle_ids),1)
                self.assertEqual(result.state.party[0].ranged,proof.execution.weapon_state)

    def test_initiative_awareness_and_ballistic_shooting_are_not_substituted(self):
        source = make_pc_hochland_scenario(max_rounds=1,npc_toughness=20,
            initiative=2,awareness=5,ballistic_skill=4,shooting=3)
        result = execute(source,[1,5]+[1,10,10,10,10,10,10]+NPC_MISS)
        aim, = steps(result,PcAimProof)
        shot, = shots(result)
        self.assertEqual(aim.proof.request.awareness_test.profile,TestProfile(2,5))
        self.assertEqual(aim.proof.result.awareness_test_result.successes,2)
        self.assertEqual(shot.proof.request.kernel_request.attack.attacker_test.profile,TestProfile(4,3))
        self.assertEqual((raw(shot).attacker_test.trace.base_dice,
            raw(shot).attacker_test.trace.regular_dice_delta,
            raw(shot).attacker_test.trace.rolled_dice),(4,1,5))

    def test_aim_bonus_obeys_cap_and_glorious_is_funded_after_second_action(self):
        source = make_pc_hochland_scenario(max_rounds=1,npc_toughness=20,ballistic_skill=1)
        result = execute(source,[1,1,1]+[10,10,1,1]+NPC_MISS)
        shot, = shots(result)
        self.assertEqual((raw(shot).attacker_test.trace.base_dice,
            raw(shot).attacker_test.trace.regular_dice_delta,
            raw(shot).attacker_test.trace.pool_cap,raw(shot).attacker_test.trace.rolled_dice),(1,2,2,2))
        for funding,shot_values,quality in ((1,SHOT_MISS,TestQuality.NORMAL),
                (2,[10,10,1,1,10,10],TestQuality.GLORIOUS)):
            source = make_pc_hochland_scenario(max_rounds=1,npc_toughness=20,fate_rating=funding)
            source = replace(source,party=(replace(source.party[0],
                glorious_policy=PcGloriousPolicy((Skill.SHOOTING,),0,0)),))
            with self.subTest(funding=funding):
                result = execute(source,AIM_ZERO+shot_values+NPC_MISS)
                shot, = shots(result)
                self.assertIs(raw(shot).attacker_test.trace.quality,quality)
                self.assertEqual(tuple(spend.kind for spend in result.state.party[0].fate.spends),
                    (FateSpendKind.SECOND_ACTION,) if funding==1 else
                    (FateSpendKind.SECOND_ACTION,FateSpendKind.GLORIOUS_TEST))
                self.assertEqual(result.state.party[0].fate.remaining_spends,0)

    def test_zero_aim_short_minimum_pool_requires_exact_one(self):
        for value,outcome in ((1,AttackOutcome.HIT),(2,AttackOutcome.MISS)):
            source = make_pc_hochland_scenario(max_rounds=1,npc_toughness=20,ballistic_skill=1)
            with self.subTest(value=value):
                result = execute(source,AIM_ZERO+[value,10,10]+NPC_MISS)
                shot, = shots(result)
                trace = raw(shot).attacker_test.trace
                self.assertEqual((trace.base_dice,trace.regular_dice_delta,trace.rolled_dice),(1,-1,1))
                self.assertIs(raw(shot).outcome,outcome)
                self.assertEqual(shot.state.party[0].ranged.required_successes,4)

    def test_drained_focused_shot_keeps_aim_prerequisite_but_loses_positive_bonus(self):
        # A real paid slot and owned Aim supply the context; injecting Conditions
        # here is a focused unit boundary, not a fresh externally affected trial.
        source = make_pc_hochland_scenario(max_rounds=1,npc_toughness=20)
        result = execute(source,AIM_TWO+AIMED_ONE_HIT+NPC_MISS)
        state = shots(result)[0].source
        member = state.party[0]
        state = replace(state,party=(replace(member,injury=replace(member.injury,
            conditions=member.injury.conditions.with_condition(Condition.DRAINED))),))
        request,_ = build_pc_melee_attack(state)
        test = request.kernel_request.attack.attacker_test
        self.assertFalse(any(modifier.amount>0 for modifier in test.dice_modifiers))
        self.assertEqual(tuple(modifier.amount for modifier in test.dice_modifiers
            if modifier.rule_id==OUTSIDE_OPTIMUM_RANGE_RULE_ID),(-1,))
        rng = ScriptedD10(SHOT_HIT)
        execution = execute_attack_action(request,rng)
        rng.assert_exhausted()
        proof = complete_pc_ranged_shot(state,request,request,execution)
        self.assertEqual(proof.preparation.source_request.aim.bonus.bonus_dice,2)
        self.assertIs(proof.preparation.aim_follow_up.outcome,AimFollowUpOutcome.APPLIED_TO_RANGED_ATTACK)
        self.assertFalse(proof.execution.weapon_state.loaded)
        self.assertEqual(proof.execution.weapon_state.required_successes,4)

    def test_absent_exhausted_or_reserved_fate_never_creates_a_free_shot(self):
        for options in ({'use_second_action':False},{'fate_rating':0},{'fate_rating':1,'reserve':1}):
            with self.subTest(options=options):
                result = execute(make_pc_hochland_scenario(max_rounds=2,**options),
                    AIM_ZERO+NPC_MISS+SWORD_HIT)
                self.assertEqual(len(steps(result,PcAimProof)),1)
                self.assertEqual(steps(result,PcAimSecondActionProof),())
                self.assertEqual(shots(result),())
                self.assertEqual(len(steps(result,PcBackupWeaponDrawProof)),1)
                consumed, = steps(result,PcAimConsumptionProof)
                self.assertIs(consumed.proof.follow_up.outcome,AimFollowUpOutcome.LOST)
                self.assertIs(consumed.proof.action.declaration.kind,CombatActionKind.ATTACK)
                self.assertEqual(result.executed_actions,3)
                self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
                self.assertTrue(result.state.party[0].ranged.loaded)

    def test_lucky_free_and_paid_funding_preserve_explicit_reserve(self):
        for rating,reserve,lucky,funding,left in ((0,0,True,FateSpendFunding.LUCKY_FREE,0),
                (1,1,True,FateSpendFunding.LUCKY_FREE,1),(2,1,False,FateSpendFunding.SESSION_POOL,1)):
            source = make_pc_hochland_scenario(max_rounds=1,npc_toughness=20,
                fate_rating=rating,reserve=reserve,has_lucky=lucky)
            with self.subTest(rating=rating,reserve=reserve,lucky=lucky):
                result = execute(source,AIM_ZERO+SHOT_MISS+NPC_MISS)
                spend, = steps(result,PcAimSecondActionProof)
                self.assertIs(spend.proof.result.spend.funding,funding)
                self.assertEqual(result.state.party[0].fate.remaining_spends,left)
                self.assertEqual(len(shots(result)),1)

    def test_aim_and_paid_grant_full_source_and_replay_are_bound(self):
        result = execute(make_pc_hochland_scenario(max_rounds=1,npc_toughness=20),
            AIM_ZERO+SHOT_MISS+NPC_MISS)
        aim, = steps(result,PcAimProof)
        spend, = steps(result,PcAimSecondActionProof)
        consumed, = steps(result,PcAimConsumptionProof)
        for step in (aim,spend,consumed):
            self.assertEqual(apply_pc_melee_step(step.source,step),step.state)
            with self.assertRaises((TypeError,ValueError)):
                apply_pc_melee_step(step.state,step)
        for field,value in (('actor_id','other'),('target_id','other'),('id','foreign:aim')):
            proof = deepcopy(aim.proof)
            object.__setattr__(proof.request,field,value)
            with self.subTest(field=field),self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(aim.source,proof)
        for field,value in (('actor_id','other'),('session_id','foreign'),('slot_index',1)):
            proof = deepcopy(spend.proof)
            object.__setattr__(proof.result.proof,field,value)
            with self.subTest(field=field),self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(spend.source,proof)
        proof = deepcopy(consumed.proof)
        object.__setattr__(proof.follow_up.source_request,'actor_id','other')
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(consumed.source,proof)

    def test_funded_selected_second_action_cannot_be_skipped_by_a_forged_turn_end(self):
        result = execute(make_pc_hochland_scenario(max_rounds=1,npc_toughness=20),
            AIM_ZERO+SHOT_MISS+NPC_MISS)
        aim, = steps(result,PcAimProof)
        state = aim.state
        actor = state.round_state.active_turn.actor_id
        action = pc_melee_action_id(state,actor)
        # The generic clock permits ending a one-action turn. This caller chose
        # a funded Aim->Shoot policy, so PC projection must require its grant.
        clock = end_combat_turn(CombatTurnEndRequest(action+':end',state.round_state,actor))
        forged = PcTurnEndProof(clock,PcFateDecline(actor,action+':end','action',
            state.source.participant(actor).fate_policy))
        self.assertEqual(state.participant(actor).fate.remaining_spends,1)
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(state,forged)

    def test_bare_fate_grant_and_third_action_cannot_bypass_the_spend(self):
        result = execute(make_pc_hochland_scenario(max_rounds=1,npc_toughness=20,fate_rating=3),
            AIM_ZERO+SHOT_MISS+NPC_MISS)
        spend, = steps(result,PcAimSecondActionProof)
        slot_request = spend.proof.result.source_request.slot_request
        with self.assertRaises((TypeError,ValueError)):
            reserve_combat_action_slot(slot_request)
        shot, = shots(result)
        third = CombatActionSlotRequest('foreign:third',shot.state.round_state,'pc1',
            CombatActionDeclaration(CombatActionKind.ATTACK),ActionSlotGrant.FATE)
        with self.assertRaises((TypeError,ValueError)):
            spend_fate_for_second_action(FateSecondActionSpendRequest('foreign:third:spend',
                shot.state.party[0].fate,third))

    def test_terminal_shot_consumes_aim_before_objective_and_never_approaches(self):
        result = execute(make_pc_hochland_scenario(max_rounds=3),AIM_ZERO+SHOT_HIT)
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(result.executed_actions,2)
        self.assertEqual(len(steps(result,PcAimConsumptionProof)),1)
        self.assertEqual(steps(result,PcNpcApproachProof),())
        self.assertFalse(result.state.party[0].ranged.loaded)

    def test_real_wound_drop_recover_loses_aim_before_close_stop(self):
        result = execute(make_pc_hochland_scenario(use_second_action=False,backup=False,max_rounds=4),
            AIM_ZERO+NPC_HIT+[8,1]+NPC_MISS)
        recover, = steps(result,PcRecoverProof)
        consumed, = steps(result,PcAimConsumptionProof)
        self.assertIs(consumed.proof.follow_up.outcome,AimFollowUpOutcome.LOST)
        self.assertIs(consumed.proof.action.declaration.kind,CombatActionKind.RECOVER)
        self.assertLess(result.steps.index(recover),result.steps.index(consumed))
        self.assertIs(result.outcome,PcMeleeOutcome.UNSUPPORTED_PATH)
        self.assertIs(type(result.unsupported),PcRangedCloseUnsupported)
        self.assertEqual(result.unsupported.round_number,3)
        self.assertEqual(result.executed_actions,4)
        self.assertEqual(shots(result),())

    def test_actual_shaking_grip_restriction_blocks_a_focused_new_aim(self):
        wound = execute(make_pc_hochland_scenario(use_second_action=False,backup=False,max_rounds=4),
            AIM_ZERO+NPC_HIT+[8,1]+NPC_MISS)
        recovered, = steps(wound,PcRecoverProof)
        healthy = execute(make_pc_hochland_scenario(max_rounds=1,npc_toughness=20),
            AIM_ZERO+SHOT_MISS+NPC_MISS)
        aim, = steps(healthy,PcAimProof)
        state = aim.source
        member = state.party[0]
        actual = recovered.state.party[0]
        # The actual W8 effect is carried into a focused clear-range action
        # context. This does not claim a fresh wounded encounter source.
        state = replace(state,party=(replace(member,injury=actual.injury,
            daily_wounds=actual.daily_wounds,body_facts=actual.body_facts,
            timed_wounds=actual.timed_wounds),))
        self.assertEqual(state.party[0].injury.wounds[-1].table_total,8)
        with self.assertRaises((TypeError,ValueError)):
            build_pc_aim(state)

    def test_focused_critical_phase_cannot_be_omitted_after_two_actions(self):
        result = execute(make_pc_hochland_scenario(max_rounds=1,npc_toughness=20),
            AIM_ZERO+SHOT_MISS+NPC_MISS)
        end = next(step for step in steps(result,PcTurnEndProof)
            if step.source.round_state.active_turn.actor_id=='pc1')
        state = end.source
        member = state.party[0]
        state = replace(state,party=(replace(member,injury=replace(member.injury,
            conditions=member.injury.conditions.with_condition(Condition.CRITICALLY_INJURED))),))
        self.assertEqual(len(state.round_state.active_turn.action_slots),2)
        self.assertTrue(all(slot.executed for slot in state.round_state.active_turn.action_slots))
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(state,end.proof)

    def test_two_pc_aims_fate_ledgers_and_weapon_instances_stay_independent(self):
        source = make_pc_hochland_scenario(pc_count=2,enemy_count=2,max_rounds=1,npc_toughness=20)
        result = execute(source,(AIM_ZERO+SHOT_MISS)*2+NPC_MISS*2)
        self.assertEqual(tuple(step.proof.request.actor_id for step in steps(result,PcAimProof)),('pc1','pc2'))
        self.assertEqual(tuple(step.proof.result.state.actor_id for step in steps(result,PcAimSecondActionProof)),('pc1','pc2'))
        self.assertEqual(tuple(member.fate.remaining_spends for member in result.state.party),(0,0))
        self.assertEqual(tuple(member.ranged.weapon_instance_id for member in result.state.party),('pc1:weapon','pc2:weapon'))
        self.assertEqual(tuple(member.ranged.required_successes for member in result.state.party),(4,4))
        self.assertEqual(len(steps(result,PcAimConsumptionProof)),2)
        self.assertEqual(result.executed_actions,6)


if __name__ == '__main__':
    unittest.main()
