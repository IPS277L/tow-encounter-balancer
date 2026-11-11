"""Literal Sling journals preserve free reload, Close permission and real hands."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_sling_scenarios import make_pc_sling_scenario
from towr.domain.attack_models import AttackOutcome, MissConsequence
from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundEntryId, WoundRecord, WoundRecordOrigin
from towr.domain.pc_backup_weapon_models import pc_backup_draw_hand
from towr.domain.pc_heavy_wound_models import PcBodyFact, PcBodyFactKind
from towr.domain.pc_melee_models import PcFatePolicy, PcGloriousPolicy, PcWeaponHand
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcBackupWeaponDrawProof, PcHandDropProof, PcMeleeOutcome,
    PcMeleeStep, PcRecoverProof, build_pc_melee_attack, initial_pc_melee_state,
    pc_melee_round_participants, pc_attack_skill,
)
from towr.domain.pc_ranged_models import (
    PcRangedReloadProof, complete_pc_ranged_shot, prepare_pc_ranged_shot, pc_ranged_unsupported,
)
from towr.domain.pc_shield_models import PcShieldLocation, PcShieldReleaseProof
from towr.domain.pc_short_opening_models import (
    PcNpcApproachProof, PcRangedCloseUnsupported, pc_enemy_range,
)
from towr.domain.ranged_weapon_attack_preparation_models import OUTSIDE_OPTIMUM_RANGE_RULE_ID
from towr.domain.ranged_weapon_profiles import RangedWeaponId, RangedWeaponRange
from towr.domain.reload_models import FreeReloadWeaponState
from towr.domain.test_models import Skill, TestQuality
from towr.domain.turn_models import CombatRoundAdvanceRequest, CombatTurnStartRequest
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.turn_resolution import advance_combat_round, start_combat_turn


SLING_MISS = [10,10,1,1]
SLING_HIT = [1,1,10,10]
NPC_MISS = [10,10,1,1,1]
NPC_HIT = [1,1,10,10,10]
SWORD_HIT = [1,1,1,10,10]


def execute(source, values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source, rng)
    rng.assert_exhausted()
    return result


def steps(result, kind):
    return tuple(step for step in result.steps if type(step.proof) is kind)


def shots(result):
    return tuple(step for step in steps(result, PcAttackProof) if step.proof.ranged_shot is not None)


def raw(step):
    return step.proof.execution.resolution.attack


def own_next_turn(result):
    state = result.state
    advanced = advance_combat_round(CombatRoundAdvanceRequest('focused:advance',
        state.round_state, pc_melee_round_participants(state))).state
    started = start_combat_turn(CombatTurnStartRequest('focused:pc:start',advanced,'pc1')).state
    return replace(state, round_state=started)


def object_id(step):
    interaction = step.proof.result.source_request.choice.object_interaction
    return None if interaction is None else interaction.object_id


class PcSlingTests(unittest.TestCase):
    def test_strength_damage_and_short_shooting_use_separate_characteristics_and_full_armour(self):
        for strength in (1,3,5):
            for hit in (False,True):
                source = make_pc_sling_scenario(strength=strength,backup=False,
                    max_rounds=1,npc_toughness=20,npc_armour_bonus=3,npc_armoured=True)
                result = execute(source,([1,10,10,10] if hit else SLING_MISS)+NPC_MISS)
                shot, = shots(result)
                attack = raw(shot)
                with self.subTest(strength=strength,hit=hit):
                    self.assertIs(attack.outcome,AttackOutcome.HIT if hit else AttackOutcome.MISS)
                    self.assertEqual(attack.impact_spec.damage.base,strength)
                    self.assertFalse(attack.impact_spec.ignores_armour)
                    self.assertEqual(attack.effective_resilience,23 if hit else None)
                    self.assertEqual(attack.impact_spec.damage_modifiers,())
                    self.assertEqual((attack.attacker_test.trace.base_dice,
                        attack.attacker_test.trace.regular_dice_delta,
                        attack.attacker_test.trace.rolled_dice),(3,-1,2))
                    penalty, = shot.proof.request.kernel_request.attack.attacker_test.dice_modifiers
                    self.assertEqual((penalty.rule_id,penalty.amount),(OUTSIDE_OPTIMUM_RANGE_RULE_ID,-1))
                    if hit:
                        self.assertEqual(attack.damage,strength+1)
                    self.assertIs(attack.miss_consequence,MissConsequence.NONE)
                    self.assertEqual(shot.source.party[0].ranged,shot.state.party[0].ranged)
                    owner = shot.state.party[0].ranged
                    self.assertIs(type(owner),FreeReloadWeaponState)
                    self.assertIs(owner.weapon_id,RangedWeaponId.SLING)
                    self.assertFalse(hasattr(owner,'loaded'))
                    self.assertFalse(hasattr(owner,'reload_cycle_id'))
                    self.assertIsNone(shot.proof.ranged_shot.preparation.source_request.next_reload_cycle_id)
                    self.assertEqual(steps(result,PcRangedReloadProof),())

    def test_minimum_pool_and_glorious_retain_free_profile(self):
        for value,outcome in ((1,AttackOutcome.HIT),(2,AttackOutcome.MISS)):
            source = make_pc_sling_scenario(ballistic_skill=1,max_rounds=1,npc_toughness=20)
            result = execute(source,[value,10,10]+NPC_MISS)
            shot, = shots(result)
            self.assertEqual(raw(shot).attacker_test.trace.rolled_dice,1)
            self.assertIs(raw(shot).outcome,outcome)
        source = make_pc_sling_scenario(max_rounds=1,npc_toughness=20)
        source = replace(source,party=(replace(source.party[0],fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.SHOOTING,),0,0)),))
        result = execute(source,[10,10,1,1,10,10]+NPC_MISS)
        shot, = shots(result)
        trace = raw(shot).attacker_test.trace
        self.assertIs(trace.quality,TestQuality.GLORIOUS)
        self.assertEqual((trace.initial_values,trace.final_values),((10,10),(1,1)))
        self.assertEqual(shot.source.party[0].ranged,shot.state.party[0].ranged)

    def test_drained_focused_attack_keeps_negative_range_and_free_state(self):
        # Focused preparation follows a real typed shot context, not a fresh
        # encounter claiming an initially injured or Drained participant.
        result = execute(make_pc_sling_scenario(max_rounds=1,npc_toughness=20),SLING_MISS+NPC_MISS)
        state = shots(result)[0].source
        member = state.party[0]
        member = replace(member,injury=replace(member.injury,
            conditions=member.injury.conditions.with_condition(Condition.DRAINED)))
        state = replace(state,party=(member,))
        request,_ = build_pc_melee_attack(state)
        self.assertEqual(tuple(m.amount for m in request.kernel_request.attack.attacker_test.dice_modifiers),(-1,))
        rng = ScriptedD10(SLING_HIT)
        execution = execute_attack_action(request,rng)
        rng.assert_exhausted()
        proof = complete_pc_ranged_shot(state,request,request,execution)
        self.assertEqual(proof.execution.weapon_state,state.party[0].ranged)
        self.assertEqual(proof.preparation.profile_attack.kernel_request.attack.impact_spec.damage.base,3)

    def test_real_close_triggers_backup_with_free_sling_retained_and_no_early_draw(self):
        source = make_pc_sling_scenario(max_rounds=2)
        initial = initial_pc_melee_state(source)
        clock = start_combat_turn(CombatTurnStartRequest('focused:first',initial.round_state,'pc1')).state
        self.assertIsNone(pc_backup_draw_hand(replace(initial,round_state=clock),'pc1'))
        result = execute(source,SLING_MISS+NPC_MISS+SWORD_HIT)
        draw, = steps(result,PcBackupWeaponDrawProof)
        self.assertEqual(draw.source.round_state.round_number,2)
        self.assertEqual(draw.proof.actor_id,'pc1')
        self.assertIs(draw.proof.hand,PcWeaponHand.RIGHT)
        self.assertEqual(draw.source.party[0].ranged,draw.state.party[0].ranged)
        self.assertEqual(draw.state.party[0].ranged,result.state.party[0].ranged)
        self.assertEqual(len(steps(result,PcNpcApproachProof)),1)
        self.assertEqual(steps(result,PcRangedReloadProof),())
        melee = steps(result,PcAttackProof)[-1]
        self.assertIsNone(melee.proof.ranged_shot)
        self.assertIs(pc_attack_skill(melee.source,'pc1'),Skill.MELEE)
        self.assertEqual(melee.proof.request.kernel_request.attack.attacker_test.dice_modifiers,())
        self.assertEqual(raw(melee).impact_spec.damage.base,3)
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)

    def test_no_backup_stops_at_real_own_close_turn_and_other_short_target_does_not_help(self):
        result = execute(make_pc_sling_scenario(backup=False,max_rounds=3),SLING_MISS+NPC_MISS)
        self.assertIs(result.outcome,PcMeleeOutcome.UNSUPPORTED_PATH)
        self.assertIs(type(result.unsupported),PcRangedCloseUnsupported)
        self.assertEqual(result.unsupported.reason,'ranged_close_enemy')
        self.assertEqual(result.unsupported.round_number,2)
        self.assertEqual(result.unsupported.close_enemy_ids,('minion1',))
        self.assertTrue(result.unsupported.source_id.endswith(':ranged:close'))
        self.assertEqual(result.state.party[0].injury.wounds,())
        self.assertEqual(result.executed_actions,2)
        result = execute(make_pc_sling_scenario(enemy_count=2,max_rounds=1),SLING_MISS+NPC_MISS*2)
        approach = steps(result,PcNpcApproachProof)[0]
        self.assertIs(pc_enemy_range(approach.state,'pc1','minion2'),RangedWeaponRange.SHORT)
        # The real pre-approach shot cannot be prepared against even its Short
        # target once any other live enemy is Close.
        with self.assertRaises((TypeError,ValueError)):
            prepare_pc_ranged_shot(approach.state,shots(result)[0].proof.request)

    def test_one_usable_hand_still_shoots_before_close_and_can_choose_healthy_backup_after(self):
        source = make_pc_sling_scenario(initial_hand=PcWeaponHand.LEFT,max_rounds=1,npc_toughness=20)
        result = execute(source,SLING_MISS+NPC_MISS)
        shot, = shots(result)
        wound = WoundRecord(1,WoundEntryId.SLASHED_FOREARMS,16,(),effect_resolved=True,
            origin=WoundRecordOrigin.FIXED_ENTRY)
        def one_arm(state):
            member = state.party[0]
            member = replace(member,injury=replace(member.injury,wounds=(wound,)),
                body_facts=(PcBodyFact(PcBodyFactKind.UNUSABLE_ARM,1,PcWeaponHand.RIGHT),))
            return replace(state,party=(member,))
        short = one_arm(shot.source)
        request,_ = build_pc_melee_attack(short)
        proof = prepare_pc_ranged_shot(short,request)
        self.assertEqual(proof.source_request.weapon_state,short.party[0].ranged)
        self.assertEqual(proof.source_request.attacker_strength,3)
        close = one_arm(own_next_turn(result))
        self.assertIs(pc_backup_draw_hand(close,'pc1'),PcWeaponHand.LEFT)
        self.assertIsNone(pc_ranged_unsupported(close))

    def test_shield_conflict_releases_before_preferred_backup_draw_then_recovers_in_free_hand(self):
        source = make_pc_sling_scenario(shield=True,initial_hand=PcWeaponHand.LEFT,
            backup_hand=PcWeaponHand.RIGHT,max_rounds=3)
        result = execute(source,SLING_MISS+NPC_MISS+[10,10,1,1,1,1]+SWORD_HIT)
        release, = steps(result,PcShieldReleaseProof)
        draw, = steps(result,PcBackupWeaponDrawProof)
        recover, = steps(result,PcRecoverProof)
        self.assertIs(release.proof.hand,PcWeaponHand.RIGHT)
        self.assertIs(draw.proof.hand,PcWeaponHand.RIGHT)
        self.assertLess(result.steps.index(release),result.steps.index(draw))
        self.assertLess(result.steps.index(draw),result.steps.index(recover))
        self.assertEqual(tuple(step.source.round_state.round_number for step in (release,draw,recover)),(2,2,2))
        self.assertEqual(object_id(recover),'pc1:shield')
        self.assertIs(recover.state.party[0].weapon_hand,PcWeaponHand.RIGHT)
        self.assertIs(recover.state.party[0].shield.hand,PcWeaponHand.LEFT)
        self.assertIs(recover.state.party[0].shield.location,PcShieldLocation.HELD)
        self.assertEqual(len(shots(result)),1)
        self.assertEqual(steps(result,PcRangedReloadProof),())
        self.assertEqual(tuple(raw(s).impact_spec.resilience.total for s in steps(result,PcAttackProof)
            if s.proof.request.actor_id=='minion1'),(4,4))
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        for step in (release,draw,recover):
            self.assertEqual(apply_pc_melee_step(step.source,step),step.state)
            with self.assertRaises((TypeError,ValueError)):
                apply_pc_melee_step(step.state,step)

    def test_actual_light_drop_keeps_free_state_and_draw_uses_backup_without_false_reload(self):
        for side,shield_dropped in ((1,True),(10,False)):
            source = make_pc_sling_scenario(shield=True,max_rounds=2)
            values = SLING_MISS+NPC_HIT+[8,side]
            values += [10,10,1,1,1,1] if shield_dropped else SWORD_HIT
            result = execute(source,values)
            self.assertEqual(len(steps(result,PcHandDropProof)),1)
            self.assertEqual(len(steps(result,PcBackupWeaponDrawProof)),1)
            recovers = steps(result,PcRecoverProof)
            self.assertEqual(tuple(object_id(s) for s in recovers),('pc1:shield',) if shield_dropped else ())
            self.assertEqual(steps(result,PcRangedReloadProof),())
            self.assertEqual(shots(result)[0].state.party[0].ranged,result.state.party[0].ranged)

    def test_real_heavy_hand_and_clutch_paths_keep_only_usable_equipment(self):
        for total in (12,16,18):
            source = make_pc_sling_scenario(shield=True,enemy_count=3,max_rounds=2)
            # Three real Wounds; the third selects injured shield hand12,
            # unusable weapon arm16, or clutch stomach18.
            ending = [1,1,10,1,1,10,10] if total==12 else ([10,1,5,10] if total==16 else [10,1,7])
            first = SLING_MISS+NPC_HIT+[1]+NPC_HIT+[1,1]+NPC_HIT+ending
            values = first+SWORD_HIT+([1,1,1] if total in (16,18) else [])
            values += NPC_MISS*2 if total==18 else [10,10,1,1,1,1]*2
            with self.subTest(total=total):
                result = execute(source,values)
                draw, = steps(result,PcBackupWeaponDrawProof)
                self.assertIs(draw.proof.hand,PcWeaponHand.LEFT if total==16 else PcWeaponHand.RIGHT)
                self.assertEqual(draw.source.party[0].injury.wounds[-1].table_total,total)
                self.assertIs(result.state.party[0].shield.location,PcShieldLocation.DROPPED)
                self.assertEqual(steps(result,PcRecoverProof),())
                self.assertEqual(steps(result,PcRangedReloadProof),())
                self.assertEqual(len(steps(result,PcShieldReleaseProof)),1 if total==16 else 0)
                self.assertEqual(shots(result)[0].state.party[0].ranged,result.state.party[0].ranged)

    def test_recover_and_defenceless_or_terminal_boundaries_precede_close_stop(self):
        result = execute(make_pc_sling_scenario(backup=False,max_rounds=4),
            SLING_MISS+NPC_HIT+[8,10]+NPC_MISS)
        recover, = steps(result,PcRecoverProof)
        self.assertEqual(recover.source.round_state.round_number,2)
        self.assertEqual(object_id(recover),'pc1:weapon')
        self.assertIsNone(recover.source.party[0].weapon_hand)
        self.assertIs(recover.state.party[0].weapon_hand,PcWeaponHand.RIGHT)
        self.assertIs(result.outcome,PcMeleeOutcome.UNSUPPORTED_PATH)
        self.assertEqual(result.unsupported.round_number,3)
        self.assertEqual(result.executed_actions,4)
        self.assertEqual(recover.source.party[0].ranged,recover.state.party[0].ranged)
        # Focused exact stop guard; this does not claim a fresh Defenceless PC.
        blocked = result.state
        member = blocked.party[0]
        member = replace(member,injury=replace(member.injury,
            conditions=member.injury.conditions.with_condition(Condition.DEFENCELESS)))
        blocked = replace(blocked,party=(member,))
        self.assertIsNone(pc_ranged_unsupported(blocked))
        self.assertIsNone(pc_backup_draw_hand(blocked,'pc1'))
        terminal = execute(make_pc_sling_scenario(max_rounds=3),SLING_HIT)
        self.assertIs(terminal.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(terminal.executed_actions,1)
        self.assertEqual(steps(terminal,PcNpcApproachProof),())
        self.assertEqual(steps(terminal,PcBackupWeaponDrawProof),())
        self.assertIsNone(pc_ranged_unsupported(terminal.state))

    def test_proof_source_strength_instance_and_replay_are_exact(self):
        result = execute(make_pc_sling_scenario(max_rounds=1,npc_toughness=20),SLING_MISS+NPC_MISS)
        shot, = shots(result)
        self.assertEqual(apply_pc_melee_step(shot.source,shot),shot.state)
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(shot.source,replace(shot.proof,ranged_shot=None))
        for field,value in (('attacker_strength',4),('next_reload_cycle_id','invented'),
                ('has_enemy_in_close_range',True)):
            proof = deepcopy(shot.proof)
            object.__setattr__(proof.ranged_shot.preparation.source_request,field,value)
            with self.subTest(field=field),self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(shot.source,proof)
        proof = deepcopy(shot.proof)
        object.__setattr__(proof.ranged_shot.preparation.source_request.weapon_state,
            'weapon_instance_id','other:weapon')
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(shot.source,proof)

    def test_two_actors_keep_independent_free_states_and_both_draw(self):
        result = execute(make_pc_sling_scenario(pc_count=2,enemy_count=2,max_rounds=2),
            SLING_MISS*2+NPC_MISS*2+SWORD_HIT*2)
        self.assertEqual(tuple(s.proof.actor_id for s in steps(result,PcBackupWeaponDrawProof)),('pc1','pc2'))
        a,b = (m.ranged for m in result.state.party)
        self.assertIsNot(a,b)
        self.assertNotEqual(a.weapon_instance_id,b.weapon_instance_id)
        self.assertIs(type(a),FreeReloadWeaponState)
        self.assertIs(type(b),FreeReloadWeaponState)
        self.assertEqual(result.executed_actions,6)
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)


if __name__=='__main__':
    unittest.main()
