"""Literal Short volley, source-bound NPC approach and actual melee continuation."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_bow_scenarios import make_pc_bow_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_ranged_scenarios import ranged_profile
from towr.domain.attack_models import AttackOutcome, MissConsequence
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_models import (
    PC_BOW_WEAPONS, PcFatePolicy, PcGloriousPolicy, PcMeleeWeapon,
    PcNearMissPolicy, PcRepeaterBonusPolicy, PcTwoHandedGrip, PcWeaponHand,
)
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcBackupWeaponDrawProof, PcHandDropProof, PcMeleeOutcome,
    PcMeleeStep, PcRecoverProof, build_pc_melee_attack,
)
from towr.domain.pc_ranged_models import PcRangedReloadProof
from towr.domain.pc_short_opening_models import (
    PcNpcApproachProof, expected_pc_npc_approach, pc_enemy_range, pc_has_close_enemy,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponId, RangedWeaponRange
from towr.domain.reload_models import FreeReloadWeaponState
from towr.domain.test_models import Skill, TestQuality
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario


SHORTBOW = PcMeleeWeapon.SHORTBOW
WARBOW = PcMeleeWeapon.WARBOW
LONGBOW = PcMeleeWeapon.LONGBOW
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
    return tuple(step for step in steps(result, PcAttackProof)
        if step.proof.ranged_shot is not None)


def raw(step):
    return step.proof.execution.resolution.attack


def bow_miss(weapon):
    return [10,10,10,10,1,1] if weapon is SHORTBOW else [10,10,1,1]


class PcBowShortOpeningTests(unittest.TestCase):
    def test_three_optimum_traits_and_short_miss_do_not_invent_close_stagger(self):
        self.assertEqual(PC_BOW_WEAPONS, (SHORTBOW,WARBOW,LONGBOW))
        for weapon, dice, delta in ((SHORTBOW,4,1),(WARBOW,2,-1),(LONGBOW,2,-1)):
            with self.subTest(weapon=weapon):
                result = execute(make_pc_bow_scenario(weapon=weapon,max_rounds=1),
                    bow_miss(weapon)+NPC_MISS)
                shot, = shots(result)
                attack = raw(shot)
                self.assertIs(attack.outcome, AttackOutcome.MISS)
                self.assertIs(attack.miss_consequence,MissConsequence.NONE)
                self.assertEqual((attack.attacker_test.trace.rolled_dice,
                    attack.attacker_test.trace.regular_dice_delta), (dice,delta))
                preparation = shot.proof.ranged_shot.preparation.source_request
                self.assertIs(preparation.target_range, RangedWeaponRange.SHORT)
                self.assertFalse(preparation.has_enemy_in_close_range)
                self.assertIsNone(preparation.next_reload_cycle_id)
                self.assertFalse(preparation.uses_optional_reload_bonus)
                self.assertFalse(shot.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))
                self.assertIs(type(shot.state.participant('pc1').ranged), FreeReloadWeaponState)
                self.assertEqual(shot.source.participant('pc1').ranged, shot.state.participant('pc1').ranged)
                self.assertEqual(steps(result,PcRangedReloadProof), ())
                self.assertEqual(result.executed_actions, 2)

    def test_free_bow_damage_keeps_full_armour_and_never_builds_reload_progress(self):
        for weapon,damage in ((SHORTBOW,3),(WARBOW,3),(LONGBOW,4)):
            with self.subTest(weapon=weapon):
                hit = [1,10,10,10,10,10] if weapon is SHORTBOW else [1,10,10,10]
                result = execute(make_pc_bow_scenario(weapon=weapon,max_rounds=1,
                    npc_toughness=3,npc_armour_bonus=3), hit+NPC_MISS)
                shot, = shots(result)
                attack = raw(shot)
                self.assertIs(attack.outcome, AttackOutcome.HIT)
                self.assertEqual(attack.impact_spec.damage.base, damage)
                self.assertFalse(attack.impact_spec.ignores_armour)
                self.assertEqual(attack.effective_resilience, 6)
                self.assertEqual(result.state.enemy('minion1').state.injury.wounds, 0)
                owner = result.state.participant('pc1').ranged
                self.assertFalse(hasattr(owner,'loaded'))
                self.assertFalse(hasattr(owner,'exacting'))
                self.assertFalse(hasattr(owner,'reload_cycle_ids'))
                self.assertEqual(steps(result,PcRangedReloadProof), ())

    def test_real_approach_precedes_npc_attack_and_own_turn_draw_continues_with_melee(self):
        result = execute(make_pc_bow_scenario(max_rounds=2), bow_miss(SHORTBOW)+NPC_MISS+SWORD_HIT)
        approach, = steps(result,PcNpcApproachProof)
        draw, = steps(result,PcBackupWeaponDrawProof)
        attacks = steps(result,PcAttackProof)
        self.assertEqual(expected_pc_npc_approach(approach.source), approach.proof)
        self.assertEqual(approach.source.round_state.active_turn.actor_id,'minion1')
        self.assertEqual(approach.source.round_state.active_turn.action_slots, ())
        self.assertEqual(approach.source.approached_npc_ids, ())
        self.assertEqual(approach.state.approached_npc_ids, ('minion1',))
        self.assertIs(pc_enemy_range(approach.source,'pc1','minion1'), RangedWeaponRange.SHORT)
        self.assertIs(pc_enemy_range(approach.state,'pc1','minion1'), RangedWeaponRange.CLOSE)
        self.assertFalse(pc_has_close_enemy(approach.source,'pc1'))
        self.assertTrue(pc_has_close_enemy(approach.state,'pc1'))
        self.assertLess(result.steps.index(approach),result.steps.index(attacks[1]))
        self.assertEqual(draw.source.round_state.round_number,2)
        self.assertEqual(draw.source.round_state.active_turn.actor_id,'pc1')
        self.assertIs(draw.source.participant('pc1').weapon_hand,PcTwoHandedGrip.BOTH)
        self.assertIs(draw.state.participant('pc1').weapon_hand,PcWeaponHand.RIGHT)
        self.assertEqual(draw.source.participant('pc1').ranged,draw.state.participant('pc1').ranged)
        self.assertEqual(draw.state.participant('pc1').ranged,result.state.participant('pc1').ranged)
        self.assertIsNone(attacks[-1].proof.ranged_shot)
        self.assertEqual(raw(attacks[-1]).impact_spec.damage.base,3)
        self.assertEqual(result.executed_actions,3)
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(steps(result,PcRecoverProof), ())
        self.assertEqual(steps(result,PcRangedReloadProof), ())

    def test_killed_before_own_turn_never_approaches_or_causes_terminal_draw(self):
        for weapon,hit in ((SHORTBOW,[1,1,1,1,10,10]),
                (WARBOW,[1,1,10,10]),(LONGBOW,[1,1,10,10])):
            with self.subTest(weapon=weapon):
                result = execute(make_pc_bow_scenario(weapon=weapon,max_rounds=3),hit)
                self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
                self.assertEqual(result.executed_actions,1)
                self.assertEqual(steps(result,PcNpcApproachProof), ())
                self.assertEqual(steps(result,PcBackupWeaponDrawProof), ())
                self.assertEqual(result.state.approached_npc_ids, ())
                self.assertFalse(result.state.participant('pc1').using_backup_weapon)

    def test_no_backup_stops_at_real_next_own_turn_without_an_extra_roll_or_action(self):
        result = execute(make_pc_bow_scenario(backup=False,max_rounds=3),bow_miss(SHORTBOW)+NPC_MISS)
        self.assertIs(result.outcome,PcMeleeOutcome.UNSUPPORTED_PATH)
        self.assertEqual(result.executed_actions,2)
        self.assertEqual(len(shots(result)),1)
        self.assertEqual(len(steps(result,PcNpcApproachProof)),1)
        self.assertEqual(steps(result,PcBackupWeaponDrawProof), ())
        self.assertEqual(result.state.round_state.round_number,2)
        self.assertEqual(result.state.round_state.active_turn.actor_id,'pc1')
        self.assertEqual(result.state.round_state.active_turn.action_slots, ())
        self.assertEqual(result.unsupported.actor_id,'pc1')
        recovering = execute(make_pc_bow_scenario(backup=False,max_rounds=4),
            bow_miss(SHORTBOW)+NPC_HIT+[8,1]+NPC_MISS)
        self.assertIs(recovering.outcome,PcMeleeOutcome.UNSUPPORTED_PATH)
        recover, = steps(recovering,PcRecoverProof)
        self.assertEqual(recover.source.round_state.round_number,2)
        self.assertIsNone(recover.source.participant('pc1').weapon_hand)
        self.assertIs(recover.state.participant('pc1').weapon_hand,PcTwoHandedGrip.BOTH)
        self.assertEqual(recovering.executed_actions,4)
        self.assertEqual(recovering.state.round_state.round_number,3)
        self.assertEqual(recovering.state.round_state.active_turn.actor_id,'pc1')
        self.assertEqual(recovering.state.round_state.active_turn.action_slots, ())

    def test_free_state_equality_does_not_admit_missing_replayed_or_foreign_shot_proof(self):
        result = execute(make_pc_bow_scenario(max_rounds=1),bow_miss(SHORTBOW)+NPC_MISS)
        shot, = shots(result)
        self.assertEqual(apply_pc_melee_step(shot.source,shot),shot.state)
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(shot.source,replace(shot.proof,ranged_shot=None))
        with self.assertRaises((TypeError,ValueError)):
            apply_pc_melee_step(shot.state,shot)
        for field,value in (('has_enemy_in_close_range',True),
                ('target_range',RangedWeaponRange.CLOSE),('next_reload_cycle_id','invented-cycle')):
            proof = deepcopy(shot.proof)
            object.__setattr__(proof.ranged_shot.preparation.source_request,field,value)
            with self.subTest(field=field),self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(shot.source,proof)
        proof = deepcopy(shot.proof)
        object.__setattr__(proof.ranged_shot.preparation.source_request.weapon_state,
            'weapon_instance_id','other-pc:weapon')
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(shot.source,proof)

    def test_approach_is_per_actor_and_source_bound_not_automatic_close_for_the_zone(self):
        source = make_pc_bow_scenario(enemy_count=2,max_rounds=1)
        result = execute(source,bow_miss(SHORTBOW)+NPC_MISS*2)
        first,second = steps(result,PcNpcApproachProof)
        self.assertIs(pc_enemy_range(first.state,'pc1','minion1'),RangedWeaponRange.CLOSE)
        self.assertIs(pc_enemy_range(first.state,'pc1','minion2'),RangedWeaponRange.SHORT)
        self.assertTrue(pc_has_close_enemy(first.state,'pc1'))
        self.assertEqual(second.source.approached_npc_ids,('minion1',))
        self.assertEqual(second.state.approached_npc_ids,('minion1','minion2'))
        self.assertEqual(apply_pc_melee_step(first.source,first),first.state)
        with self.assertRaises((TypeError,ValueError)):
            build_pc_melee_attack(first.source)
        with self.assertRaises((TypeError,ValueError)):
            apply_pc_melee_step(first.state,first)
        with self.assertRaises((TypeError,ValueError)):
            apply_pc_melee_step(second.source,first)
        with self.assertRaises((TypeError,ValueError)):
            replace(first.state,approached_npc_ids=('unknown',))
        with self.assertRaises((TypeError,ValueError)):
            replace(second.state,approached_npc_ids=('minion2','minion1'))
        for field,value in (('action_id','foreign:approach'),
                ('previous_approached_npc_ids',()),('party_actor_ids',('other-pc',))):
            with self.subTest(field=field),self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(second.source,replace(second.proof,**{field:value}))

    def test_two_bows_retain_independent_instances_and_both_draw_before_their_melee(self):
        source = make_pc_bow_scenario(pc_count=2,enemy_count=2,max_rounds=2)
        result = execute(source,bow_miss(SHORTBOW)*2+NPC_MISS*2+SWORD_HIT*2)
        a,b = shots(result)
        self.assertEqual((a.proof.request.actor_id,b.proof.request.actor_id),('pc1','pc2'))
        self.assertNotEqual(a.state.participant('pc1').ranged.weapon_instance_id,
            b.state.participant('pc2').ranged.weapon_instance_id)
        self.assertIsNot(result.state.party[0].ranged,result.state.party[1].ranged)
        self.assertEqual(tuple(s.proof.actor_id for s in steps(result,PcBackupWeaponDrawProof)),('pc1','pc2'))
        self.assertTrue(all(member.using_backup_weapon for member in result.state.party))
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(result.executed_actions,6)

    def test_shortbow_bonus_uses_cap_and_glorious_changes_rolls_not_the_chosen_profile(self):
        source = make_pc_bow_scenario(max_rounds=1,ballistic_skill=1,npc_toughness=8)
        source = replace(source,party=(replace(source.party[0],fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.SHOOTING,),0,0)),))
        result = execute(source,[10,10,1,1,10,10]+NPC_MISS)
        shot, = shots(result)
        trace = raw(shot).attacker_test.trace
        self.assertEqual((trace.base_dice,trace.regular_dice_delta,trace.pool_cap,trace.rolled_dice),(1,1,2,2))
        self.assertIs(trace.quality,TestQuality.GLORIOUS)
        self.assertEqual(trace.initial_values,(10,10))
        self.assertEqual(trace.final_values,(1,1))
        self.assertEqual(len(result.state.participant('pc1').fate.spends),1)
        self.assertEqual(shot.source.participant('pc1').ranged,shot.state.participant('pc1').ranged)

    def test_near_miss_cancels_bow_drop_before_actual_close_trigger_backup(self):
        for near_miss in (False,True):
            source = make_pc_bow_scenario(max_rounds=2)
            if near_miss:
                source = replace(source,party=(replace(source.party[0],fate_policy=PcFatePolicy.CONFIGURED,
                    near_miss_policy=PcNearMissPolicy(8,0)),))
            values = bow_miss(SHORTBOW)+NPC_HIT+[8]+([] if near_miss else [1])+SWORD_HIT
            with self.subTest(near_miss=near_miss):
                result = execute(source,values)
                draw, = steps(result,PcBackupWeaponDrawProof)
                self.assertEqual(len(steps(result,PcHandDropProof)),0 if near_miss else 1)
                self.assertIs(draw.source.participant('pc1').weapon_hand,
                    PcTwoHandedGrip.BOTH if near_miss else None)
                self.assertEqual(len(result.state.participant('pc1').fate.burns),1 if near_miss else 0)
                self.assertEqual(steps(result,PcRecoverProof), ())
                self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)

    def test_real_unusable_arm_selects_healthy_backup_hand_and_keeps_free_bow_owned(self):
        source = make_pc_bow_scenario(enemy_count=3,max_rounds=2)
        first_round = (bow_miss(SHORTBOW)+NPC_HIT+[1]+NPC_HIT+[1,1]
            +NPC_HIT+[10,1,5,10])
        result = execute(source,first_round+SWORD_HIT+[1,1,1]+[10,10,1,1,1,1]*2)
        draw, = steps(result,PcBackupWeaponDrawProof)
        self.assertIs(draw.proof.hand,PcWeaponHand.LEFT)
        self.assertEqual(draw.source.participant('pc1').injury.wounds[-1].table_total,16)
        self.assertEqual(len(shots(result)),1)
        self.assertIs(type(result.state.participant('pc1').ranged),FreeReloadWeaponState)
        self.assertIs(result.state.participant('pc1').ranged.weapon_id,RangedWeaponId.SHORTBOW)
        self.assertEqual(draw.state.participant('pc1').ranged,result.state.participant('pc1').ranged)
        self.assertEqual(steps(result,PcRangedReloadProof), ())

    def test_drained_filters_shortbow_positive_trait_in_focused_preparation_only(self):
        # Fresh scenes cannot start Drained, and NPCs approach before the next
        # PC volley. This focused preparation is not claimed as a fresh journal.
        for weapon in PC_BOW_WEAPONS:
            with self.subTest(weapon=weapon):
                result = execute(make_pc_bow_scenario(weapon=weapon,max_rounds=1),
                    bow_miss(weapon)+NPC_MISS)
                shot, = shots(result)
                state = shot.source
                member = state.party[0]
                state = replace(state,party=(replace(member,injury=replace(member.injury,
                    conditions=member.injury.conditions.with_condition(Condition.DRAINED))),))
                request,_ = build_pc_melee_attack(state)
                test = request.kernel_request.attack.attacker_test
                self.assertTrue(all(modifier.amount<=0 for modifier in test.dice_modifiers))
                self.assertEqual(sum(modifier.amount for modifier in test.dice_modifiers),
                    0 if weapon is SHORTBOW else -1)

    def test_existing_guns_keep_shoot_or_reload_after_approach_without_close_trigger_draw(self):
        for weapon,mode,first_shot,reloads in (
                (PcMeleeWeapon.PISTOL,None,[10,10,10,1,1],1),
                (PcMeleeWeapon.REPEATER_HANDBOW,PcRepeaterBonusPolicy.NEVER,[10,10,10,1,1],0),
                (PcMeleeWeapon.REPEATER_PISTOL,PcRepeaterBonusPolicy.WHEN_AVAILABLE,[10,10,10,10,10,1,1],1)):
            source = make_pc_bow_scenario(max_rounds=2,npc_toughness=10)
            member = source.party[0]
            member = replace(member,pc=replace(member.pc,weapon=weapon,
                ranged=ranged_profile(weapon=weapon,repeater_bonus_policy=mode)),
                initial_weapon_hand=PcWeaponHand.RIGHT)
            source = replace(source,party=(member,))
            second = [1,1,1] if reloads else [10,10,10,1,1]
            with self.subTest(weapon=weapon):
                result = execute(source,first_shot+NPC_MISS+second+NPC_MISS)
                shot = shots(result)[0]
                self.assertIs(shot.proof.ranged_shot.preparation.source_request.target_range,
                    RangedWeaponRange.SHORT)
                self.assertFalse(shot.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))
                self.assertEqual(len(steps(result,PcRangedReloadProof)),reloads)
                self.assertEqual(steps(result,PcBackupWeaponDrawProof), ())
                self.assertFalse(result.state.participant('pc1').using_backup_weapon)
                self.assertTrue(result.state.participant('pc1').ranged.loaded)
                self.assertEqual(len(steps(result,PcNpcApproachProof)),1)
                self.assertEqual(result.executed_actions,4)
                if not reloads:
                    self.assertEqual(len(shots(result)),2)
                    second_shot = shots(result)[1]
                    self.assertIs(second_shot.proof.ranged_shot.preparation.source_request.target_range,
                        RangedWeaponRange.CLOSE)
                    self.assertIs(raw(second_shot).miss_consequence,MissConsequence.STAGGER_ATTACKER)
                    self.assertTrue(result.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))


if __name__=='__main__':
    unittest.main()
