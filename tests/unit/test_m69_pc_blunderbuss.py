"""Literal Blunderbuss hits and complete ordered nearby consequences."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_blunderbuss_scenarios import make_pc_blunderbuss_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.attack_models import AttackOutcome, NearbyTargetsStaggerSpec
from towr.domain.condition_models import Condition
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.pc_blunderbuss_models import PcBlunderbussNearbyProof
from towr.domain.pc_melee_models import PcFatePolicy, PcGloriousPolicy, PcMeleeWeapon
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcBackupWeaponDrawProof, PcMeleeOutcome, PcMeleeStep,
    PcProfileWoundProof, build_pc_melee_attack,
)
from towr.domain.pc_ranged_models import (
    PcRangedReloadProof, complete_pc_ranged_shot, prepare_pc_ranged_shot,
)
from towr.domain.pc_short_opening_models import (
    PcNpcApproachProof, PcRangedCloseUnsupported, pc_enemy_range,
)
from towr.domain.ranged_weapon_attack_preparation_models import BLUNDERBUSS_NEARBY_STAGGER_RULE_ID
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.resolution_models import NearbyTargetsStaggerRequest
from towr.domain.test_models import Skill, TestQuality
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario
from towr.rules.attack_action_execution import execute_attack_action


HIT = [1,10,10,10,10,10,10]
MISS = [10,10,10,10,10,1,1]
NPC_MISS = [10,10,1,1,1]
SWORD_HIT = [1,1,1,10,10]


def execute(source, values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source, rng)
    rng.assert_exhausted()
    return result


def steps(result, kind):
    return tuple(step for step in result.steps if type(step.proof) is kind)


def shots(result):
    return tuple(step for step in steps(result,PcAttackProof) if step.proof.ranged_shot is not None)


def raw(step):
    return step.proof.execution.resolution.attack


class PcBlunderbussTests(unittest.TestCase):
    def test_hit_without_primary_wound_staggers_every_other_target_in_explicit_order(self):
        source = make_pc_blunderbuss_scenario(enemy_count=3,max_rounds=1,npc_toughness=20,
            target_priority=('minion3','minion1','minion2'))
        result = execute(source,HIT+NPC_MISS*3)
        shot, = shots(result)
        wave, = steps(result,PcBlunderbussNearbyProof)
        self.assertIs(raw(shot).outcome,AttackOutcome.HIT)
        self.assertIsNone(shot.proof.execution.resolution.profile_wound)
        self.assertEqual(tuple(target.target_id for target in wave.proof.request.targets),('minion3','minion2'))
        self.assertEqual(tuple(target.target_id for target in wave.proof.result.targets),('minion3','minion2'))
        self.assertEqual(wave.proof.defeat_decisions,())
        self.assertEqual(tuple(enemy.state.injury.wounds for enemy in wave.state.enemies),(0,0,0))
        self.assertTrue(all(enemy.state.injury.conditions.has(Condition.STAGGERED) for enemy in wave.state.enemies))
        self.assertEqual(result.executed_actions,4)
        self.assertEqual(len(steps(result,PcNpcApproachProof)),3)
        self.assertEqual(len(steps(result,PcRangedReloadProof)),0)
        self.assertEqual(wave.proof.request.source.resolution_id,shot.proof.request.kernel_request.id)
        self.assertEqual(wave.proof.request.primary_target_id,'minion1')
        self.assertEqual(wave.proof.request.source.rule_id,BLUNDERBUSS_NEARBY_STAGGER_RULE_ID)
        self.assertTrue(all(not member.injury.conditions.has(Condition.STAGGERED) for member in wave.state.party))
        first_approach, *_ = steps(result,PcNpcApproachProof)
        self.assertLess(result.steps.index(wave),result.steps.index(first_approach))

    def test_primary_wound_ack_precedes_wave_and_dead_primary_does_not_cancel_it(self):
        source = make_pc_blunderbuss_scenario(enemy_count=3,max_rounds=1,npc_toughness=3)
        result = execute(source,HIT+NPC_MISS*2)
        shot, = shots(result)
        primary_ack, = steps(result,PcProfileWoundProof)
        wave, = steps(result,PcBlunderbussNearbyProof)
        self.assertTrue(shot.state.enemy('minion1').state.injury.defeated)
        self.assertEqual(tuple(target.target_id for target in wave.proof.request.targets),('minion2','minion3'))
        self.assertLess(result.steps.index(primary_ack),result.steps.index(wave))
        self.assertEqual(result.executed_actions,3)
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(shot.state,wave.proof)

    def test_hit_and_miss_both_spend_three_but_only_hit_has_nearby_source(self):
        for hit, values in ((False,MISS),(True,HIT)):
            source = make_pc_blunderbuss_scenario(enemy_count=2,max_rounds=1,npc_toughness=20)
            with self.subTest(hit=hit):
                result = execute(source,values+NPC_MISS*2)
                shot, = shots(result)
                weapon = shot.state.party[0].ranged
                self.assertFalse(weapon.loaded)
                self.assertEqual(weapon.required_successes,3)
                self.assertEqual(len(weapon.reload_cycle_ids),1)
                triggers = tuple(item for item in shot.proof.execution.resolution.follow_ups
                    if type(item) is NearbyTargetsStaggerRequest)
                self.assertEqual(len(triggers),1 if hit else 0)
                self.assertEqual(len(steps(result,PcBlunderbussNearbyProof)),1 if hit else 0)
                self.assertEqual(result.executed_actions,3)
                if not hit:
                    self.assertTrue(all(not enemy.state.injury.conditions.has(Condition.STAGGERED)
                        for enemy in shot.state.enemies))

    def test_damage_four_short_plus_two_keeps_full_armour_and_single_trait(self):
        source = make_pc_blunderbuss_scenario(max_rounds=1,npc_toughness=20,
            npc_armour_bonus=3,npc_armoured=True)
        result = execute(source,HIT+NPC_MISS)
        shot, = shots(result)
        attack = raw(shot)
        self.assertEqual(attack.attacker_test.trace.rolled_dice,5)
        self.assertEqual(attack.attacker_test.trace.regular_dice_delta,2)
        self.assertEqual(attack.impact_spec.damage.base,4)
        self.assertFalse(attack.impact_spec.ignores_armour)
        self.assertEqual(attack.impact_spec.damage_modifiers,())
        self.assertEqual((attack.damage,attack.effective_resilience),(5,23))
        effects = shot.proof.request.kernel_request.attack.secondary_effects
        self.assertEqual(effects,(NearbyTargetsStaggerSpec(BLUNDERBUSS_NEARBY_STAGGER_RULE_ID),))
        prepared = shot.proof.ranged_shot.preparation.profile_attack.kernel_request.attack
        self.assertEqual(prepared.secondary_effects,effects)

    def test_drained_declines_positive_short_dice_but_retains_hit_trait_and_charge(self):
        result = execute(make_pc_blunderbuss_scenario(max_rounds=1,npc_toughness=20),MISS+NPC_MISS)
        state = shots(result)[0].source
        member = state.party[0]
        state = replace(state,party=(replace(member,injury=replace(member.injury,
            conditions=member.injury.conditions.with_condition(Condition.DRAINED))),))
        request, _ = build_pc_melee_attack(state)
        self.assertFalse(any(modifier.amount>0 for modifier in request.kernel_request.attack.attacker_test.dice_modifiers))
        rng = ScriptedD10([1,10,10,10,10])
        attack = execute_attack_action(request,rng)
        rng.assert_exhausted()
        self.assertEqual(attack.resolution.attack.attacker_test.trace.rolled_dice,3)
        self.assertIs(attack.resolution.attack.outcome,AttackOutcome.HIT)
        self.assertEqual(sum(type(item) is NearbyTargetsStaggerRequest for item in attack.resolution.follow_ups),1)
        proof = complete_pc_ranged_shot(state,request,request,attack)
        self.assertFalse(proof.execution.weapon_state.loaded)
        self.assertEqual(proof.execution.weapon_state.required_successes,3)

    def test_low_bs_cap_glorious_and_drained_single_die_keep_the_same_weapon_price(self):
        source = make_pc_blunderbuss_scenario(ballistic_skill=1,max_rounds=1,npc_toughness=20)
        source = replace(source,party=(replace(source.party[0],fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.SHOOTING,),0,0)),))
        result = execute(source,[10,10,1,1,10,10]+NPC_MISS)
        shot, = shots(result)
        trace = raw(shot).attacker_test.trace
        self.assertEqual((trace.base_dice,trace.regular_dice_delta,trace.pool_cap,trace.rolled_dice),(1,2,2,2))
        self.assertIs(trace.quality,TestQuality.GLORIOUS)
        self.assertEqual((trace.initial_values,trace.final_values),((10,10),(1,1)))
        self.assertEqual(len(steps(result,PcBlunderbussNearbyProof)),1)
        self.assertEqual(result.state.party[0].ranged.required_successes,3)
        # One unpenalised BS die still uses Shooting4: Drained removes +2d,
        # but does not reduce the pool below one to invoke the minimum exception.
        for value, outcome in ((1,AttackOutcome.HIT),(5,AttackOutcome.MISS)):
            state = shot.source
            member = state.party[0]
            state = replace(state,party=(replace(member,injury=replace(member.injury,
                conditions=member.injury.conditions.with_condition(Condition.DRAINED))),))
            request, _ = build_pc_melee_attack(state)
            rng = ScriptedD10([value,10,10])
            attack = execute_attack_action(request,rng)
            rng.assert_exhausted()
            self.assertEqual(attack.resolution.attack.attacker_test.trace.rolled_dice,1)
            self.assertIs(attack.resolution.attack.outcome,outcome)

    def test_second_pc_wave_uses_updated_staggered_targets_and_actual_defeat_decisions(self):
        source = make_pc_blunderbuss_scenario(pc_count=2,enemy_count=3,max_rounds=2,npc_toughness=20,
            target_priority=('minion3','minion2','minion1'))
        second = source.party[1]
        dispositions = (NpcDefeatDisposition.KILLED,NpcDefeatDisposition.KNOCKED_OUT,
            NpcDefeatDisposition.DISARMED_AND_SURRENDERED)
        decisions = tuple(replace(decision,disposition=disposition)
            for decision,disposition in zip(second.defeat_decisions,dispositions,strict=True))
        source = replace(source,party=(source.party[0],replace(second,defeat_decisions=decisions)))
        result = execute(source,HIT+HIT)
        first, second_wave = steps(result,PcBlunderbussNearbyProof)
        self.assertEqual(first.proof.defeat_decisions,())
        self.assertEqual(tuple(item.target_id for item in second_wave.proof.request.targets),('minion3','minion2'))
        self.assertTrue(all(target.impact.target_state.conditions.has(Condition.STAGGERED)
            for target in second_wave.proof.request.targets))
        self.assertEqual(second_wave.proof.defeat_decisions,(decisions[2],decisions[1]))
        self.assertTrue(all(enemy.state.injury.defeated for enemy in result.state.enemies))
        self.assertEqual(tuple(enemy.state.injury.wounds for enemy in result.state.enemies),(1,1,1))
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(result.executed_actions,2)
        self.assertEqual(steps(result,PcNpcApproachProof),())
        self.assertEqual(steps(result,PcRangedReloadProof),())
        owners = tuple(member.ranged for member in result.state.party)
        self.assertEqual(tuple(owner.weapon_instance_id for owner in owners),('pc1:weapon','pc2:weapon'))
        self.assertNotEqual(owners[0].reload_cycle_id,owners[1].reload_cycle_id)
        self.assertTrue(all(owner.required_successes==3 and not owner.loaded for owner in owners))

    def test_later_wave_excludes_already_defeated_secondary_but_finishes_the_last_one(self):
        result = execute(make_pc_blunderbuss_scenario(pc_count=2,enemy_count=3,max_rounds=2),HIT+HIT)
        first, second = steps(result,PcBlunderbussNearbyProof)
        self.assertEqual(tuple(item.target_id for item in first.proof.request.targets),('minion2','minion3'))
        self.assertEqual(tuple(item.target_id for item in second.proof.request.targets),('minion3',))
        self.assertEqual(second.proof.request.primary_target_id,'minion2')
        self.assertEqual(tuple(item.target_id for item in second.proof.defeat_decisions),('minion3',))
        self.assertTrue(second.source.enemy('minion1').state.injury.defeated)
        self.assertTrue(all(enemy.state.injury.defeated for enemy in result.state.enemies))
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(result.executed_actions,2)

    def test_empty_wave_is_completed_before_terminal_objective(self):
        result = execute(make_pc_blunderbuss_scenario(max_rounds=3),HIT)
        shot, = shots(result)
        ack, = steps(result,PcProfileWoundProof)
        wave, = steps(result,PcBlunderbussNearbyProof)
        self.assertEqual(wave.proof.request.targets,())
        self.assertEqual(wave.proof.result.targets,())
        self.assertEqual(wave.proof.defeat_decisions,())
        self.assertLess(result.steps.index(ack),result.steps.index(wave))
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(result.executed_actions,1)
        self.assertEqual(result.state.pending,())
        self.assertEqual(steps(result,PcNpcApproachProof),())
        self.assertFalse(shot.state.party[0].ranged.loaded)

    def test_real_approach_backup_retains_spent_primary_without_secondary_or_bonus_on_sword(self):
        result = execute(make_pc_blunderbuss_scenario(max_rounds=2,npc_toughness=20),HIT+NPC_MISS+SWORD_HIT)
        shot, = shots(result)
        wave, = steps(result,PcBlunderbussNearbyProof)
        approach, = steps(result,PcNpcApproachProof)
        draw, = steps(result,PcBackupWeaponDrawProof)
        self.assertLess(result.steps.index(wave),result.steps.index(approach))
        self.assertEqual(draw.source.party[0].ranged,shot.state.party[0].ranged)
        self.assertEqual(result.state.party[0].ranged,shot.state.party[0].ranged)
        melee = steps(result,PcAttackProof)[-1]
        self.assertIsNone(melee.proof.ranged_shot)
        self.assertEqual(melee.proof.request.kernel_request.attack.secondary_effects,())
        self.assertEqual(raw(melee).attacker_test.trace.regular_dice_delta,0)
        self.assertEqual(steps(result,PcRangedReloadProof),())
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(result.executed_actions,3)

    def test_no_backup_and_actual_close_block_shooting_even_at_other_short_target(self):
        source = make_pc_blunderbuss_scenario(enemy_count=3,max_rounds=3,npc_toughness=20,backup=False)
        result = execute(source,HIT+NPC_MISS*3)
        shot, = shots(result)
        self.assertIs(result.outcome,PcMeleeOutcome.UNSUPPORTED_PATH)
        self.assertIs(type(result.unsupported),PcRangedCloseUnsupported)
        self.assertEqual(result.unsupported.round_number,2)
        approach = steps(result,PcNpcApproachProof)[0]
        self.assertIs(pc_enemy_range(approach.state,'pc1','minion2'),RangedWeaponRange.SHORT)
        with self.assertRaises((TypeError,ValueError)):
            prepare_pc_ranged_shot(approach.state,replace(shot.proof.request,target_id='minion2'))
        self.assertEqual(len(steps(result,PcBlunderbussNearbyProof)),1)
        self.assertEqual(result.executed_actions,4)

    def test_wave_source_order_states_primary_exclusion_and_replay_are_bound(self):
        source = make_pc_blunderbuss_scenario(enemy_count=3,max_rounds=1,npc_toughness=20)
        result = execute(source,HIT+NPC_MISS*3)
        wave, = steps(result,PcBlunderbussNearbyProof)
        self.assertEqual(apply_pc_melee_step(wave.source,wave),wave.state)
        with self.assertRaises((TypeError,ValueError)):
            apply_pc_melee_step(wave.state,wave)
        for request in (replace(wave.proof.request,id='foreign:nearby'),
                replace(wave.proof.request,targets=tuple(reversed(wave.proof.request.targets))),
                replace(wave.proof.request,targets=wave.proof.request.targets[:1]),
                replace(wave.proof.request,source=replace(wave.proof.request.source,resolution_id='foreign:kernel'))):
            with self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(wave.source,replace(wave.proof,request=request))
        proof = deepcopy(wave.proof)
        target = proof.request.targets[0].impact
        object.__setattr__(target,'target_state',replace(target.target_state,
            conditions=target.target_state.conditions.with_condition(Condition.STAGGERED)))
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(wave.source,proof)
        for field,value in (('primary_target_id','pc1'),('source',replace(wave.proof.request.source,
                rule_id='RULE-FOREIGN'))):
            with self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(wave.source,replace(wave.proof,request=replace(wave.proof.request,**{field:value})))
        approach = steps(result,PcNpcApproachProof)[0]
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(wave.source,approach.proof)

    def test_wave_defeat_ack_cannot_be_missing_or_belong_to_another_attacker(self):
        result = execute(make_pc_blunderbuss_scenario(pc_count=2,enemy_count=3,max_rounds=1,npc_toughness=20),HIT+HIT)
        wave = steps(result,PcBlunderbussNearbyProof)[1]
        self.assertEqual(len(wave.proof.defeat_decisions),2)
        wrong = replace(wave.proof.defeat_decisions[0],attacker_id='pc1')
        for decisions in ((),wave.proof.defeat_decisions[:1],
                (wrong,*wave.proof.defeat_decisions[1:]),tuple(reversed(wave.proof.defeat_decisions))):
            with self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(wave.source,replace(wave.proof,defeat_decisions=decisions))

    def test_hit_commits_cluster_and_target_snapshot_before_primary_ack_or_wave(self):
        source = make_pc_blunderbuss_scenario(enemy_count=3,max_rounds=1)
        result = execute(source,HIT+NPC_MISS*2)
        shot, = shots(result)
        wave, = steps(result,PcBlunderbussNearbyProof)
        snapshot = shot.proof.nearby_snapshot
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.cluster,source.blunderbuss_nearby)
        self.assertEqual(snapshot.request,wave.proof.request)
        other_cluster = replace(source.blunderbuss_nearby,
            target_priority=('minion3','minion2','minion1'))
        other_source = replace(source,blunderbuss_nearby=other_cluster)
        # This is a separately valid fresh source. It cannot replace the
        # committed encounter facts after a Hit, even before primary Wound ACK.
        for state in (shot.state,wave.source,wave.state):
            with self.subTest(history_length=len(state.history)),self.assertRaises((TypeError,ValueError)):
                replace(state,source=other_source)
        alterations = (lambda:None,
            lambda:replace(snapshot,cluster=other_cluster),
            lambda:replace(snapshot,request=replace(snapshot.request,
                targets=tuple(reversed(snapshot.request.targets)))),
            lambda:replace(snapshot,request=replace(snapshot.request,
                source=replace(snapshot.request.source,resolution_id='other:shot'))))
        for index, alter in enumerate(alterations):
            with self.subTest(index=index),self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(shot.source,replace(shot.proof,nearby_snapshot=alter()))

    def test_miss_cannot_invent_a_committed_nearby_snapshot(self):
        source = make_pc_blunderbuss_scenario(enemy_count=3,max_rounds=1,npc_toughness=20)
        hit = execute(source,HIT+NPC_MISS*3)
        miss = execute(source,MISS+NPC_MISS*3)
        hit_shot, = shots(hit)
        miss_shot, = shots(miss)
        self.assertIsNone(miss_shot.proof.nearby_snapshot)
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(miss_shot.source,replace(miss_shot.proof,
                nearby_snapshot=hit_shot.proof.nearby_snapshot))


if __name__ == '__main__':
    unittest.main()
