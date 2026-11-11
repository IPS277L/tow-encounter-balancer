"""Literal PC repeater choices, ordinary shots, Reload and retained equipment."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import with_pc_melee_brute
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_ranged_scenarios import make_pc_ranged_scenario, ranged_profile
from tests.support.pc_shield_scenarios import shield_loadout
from towr.domain.attack_models import AttackOutcome, ResilienceProfile
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_models import (
    PcBackupWeaponPolicy, PcFatePolicy, PcGloriousPolicy, PcMeleeWeapon,
    PcRepeaterBonusPolicy, PcWeaponHand,
)
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcBackupWeaponDrawProof, PcHandSwapProof, PcMeleeOutcome,
    PcMeleeStep, PcRecoverProof,
)
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc
from towr.domain.pc_npc_pistol_source_models import PcNpcPistolPolicy, PcNpcPistolReloadHandPolicy
from towr.domain.pc_ranged_models import PcRangedReloadProof
from towr.domain.pc_shield_models import PcShieldLocation, PcShieldReleaseProof
from towr.domain.ranged_weapon_profiles import REPEATER_SHOOTING_BONUS_RULE_ID, RangedWeaponId
from towr.domain.test_models import Skill, TestQuality
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario


HANDBOW = PcMeleeWeapon.REPEATER_HANDBOW
PISTOL = PcMeleeWeapon.REPEATER_PISTOL
WHEN = PcRepeaterBonusPolicy.WHEN_AVAILABLE
NEVER = PcRepeaterBonusPolicy.NEVER
NPC_MISS = [10,10,1,1,1]
NPC_HIT = [1,1,10,10,10]
ORDINARY_HIT = [1,1,1,10,10]


def scene(*,weapon=HANDBOW,bonus=WHEN,rounds=1,enemies=1,shield=False,**kwargs):
    source = make_pc_ranged_scenario(weapon=weapon,repeater_bonus_policy=bonus,
        max_rounds=rounds,enemy_count=enemies,**kwargs)
    if shield:
        source = replace(source,party=tuple(replace(member,shield=shield_loadout()) for member in source.party))
    for actor in source.enemy_activation_order:
        source = with_pc_melee_brute(source,actor,wound_limit=20)
    return source


def execute(source,values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def steps(result,kind):
    return tuple(step for step in result.steps if type(step.proof) is kind)


def shots(result):
    return tuple(step for step in steps(result,PcAttackProof) if step.proof.ranged_shot is not None)


def raw(step):
    return step.proof.execution.resolution.attack


def bonus_hit(weapon):
    return [1]*(4 if weapon is HANDBOW else 5)+[10,10]


def heavy_hits(total=16):
    return NPC_HIT+[1]+NPC_HIT+[1,1]+NPC_HIT+[10,1,total-11]+[10]


class PcRangedExecutionTests(unittest.TestCase):
    def test_never_ordinary_shots_keep_loaded_state_without_creating_reload_cycles(self):
        for weapon in (HANDBOW,PISTOL):
            with self.subTest(weapon=weapon):
                result = execute(scene(weapon=weapon,bonus=NEVER,rounds=2),
                    ORDINARY_HIT+NPC_MISS+ORDINARY_HIT+NPC_MISS)
                first,second = shots(result)
                for shot in (first,second):
                    self.assertEqual(shot.source.participant('pc1').ranged,shot.state.participant('pc1').ranged)
                    preparation = shot.proof.ranged_shot.preparation.source_request
                    self.assertFalse(preparation.uses_optional_reload_bonus)
                    self.assertIsNone(preparation.next_reload_cycle_id)
                    self.assertEqual(raw(shot).attacker_test.trace.rolled_dice,3)
                self.assertNotEqual(first.proof.request.id,second.proof.request.id)
                weapon_state = result.state.participant('pc1').ranged
                self.assertTrue(weapon_state.loaded)
                self.assertEqual(weapon_state.reload_cycle_ids,())
                self.assertIsNone(weapon_state.exacting)
                self.assertEqual(steps(result,PcRangedReloadProof),())
                self.assertEqual(result.executed_actions,4)

    def test_bonus_hit_and_miss_choose_exact_modifier_once_and_open_one_cycle(self):
        for weapon,extra in ((HANDBOW,1),(PISTOL,2)):
            for hit in (True,False):
                with self.subTest(weapon=weapon,hit=hit):
                    count = 3+extra
                    values = ([1]*count+[10]*2 if hit else [10]*count+[1]*2)+NPC_MISS
                    result = execute(scene(weapon=weapon),values)
                    shot, = shots(result)
                    self.assertIs(raw(shot).outcome,AttackOutcome.HIT if hit else AttackOutcome.MISS)
                    test = shot.proof.request.kernel_request.attack.attacker_test
                    modifiers = tuple(m for m in test.dice_modifiers if m.rule_id==REPEATER_SHOOTING_BONUS_RULE_ID)
                    self.assertEqual(tuple(m.amount for m in modifiers),(extra,))
                    self.assertFalse(modifiers[0].bypasses_pool_cap)
                    self.assertEqual(raw(shot).attacker_test.trace.rolled_dice,count)
                    preparation = shot.proof.ranged_shot.preparation.source_request
                    self.assertTrue(preparation.uses_optional_reload_bonus)
                    state = result.state.participant('pc1').ranged
                    self.assertFalse(state.loaded)
                    self.assertEqual(state.reload_cycle_ids,(preparation.next_reload_cycle_id,))
                    self.assertEqual(state.exacting.accumulated_successes,0)
                    self.assertEqual(state.required_successes,3)

    def test_partial_failed_overshoot_reload_cost_actions_and_next_shot_opens_new_cycle(self):
        for weapon in (HANDBOW,PISTOL):
            with self.subTest(weapon=weapon):
                result = execute(scene(weapon=weapon,rounds=5,initiative=4),bonus_hit(weapon)+NPC_MISS
                    +[1,1,10,10]+NPC_MISS+[10]*4+NPC_MISS+[1]*4+NPC_MISS
                    +bonus_hit(weapon)+NPC_MISS)
                first,second = shots(result)
                reloads = steps(result,PcRangedReloadProof)
                self.assertEqual(tuple(s.proof.result.state.exacting.accumulated_successes for s in reloads),(2,2,6))
                self.assertEqual(tuple(s.proof.result.state.loaded for s in reloads),(False,False,True))
                self.assertEqual((first.source.round_state.round_number,second.source.round_state.round_number),(1,5))
                self.assertTrue(all(s.proof.result.exacting.test_result.trace.rolled_dice==4 for s in reloads))
                state = result.state.participant('pc1').ranged
                self.assertFalse(state.loaded)
                self.assertEqual(len(state.reload_cycle_ids),2)
                self.assertNotEqual(*state.reload_cycle_ids)
                self.assertEqual(state.exacting.contributions,())
                self.assertEqual(result.executed_actions,10)

    def test_optional_bonus_uses_normal_cap_and_choice_precedes_fate_rerolls(self):
        source = scene(weapon=PISTOL,ballistic_skill=1)
        source = replace(source,party=(replace(source.party[0],fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.SHOOTING,),0,0)),))
        result = execute(source,[10,10,1,1,10,10]+NPC_MISS)
        shot, = shots(result)
        trace = raw(shot).attacker_test.trace
        self.assertEqual((trace.base_dice,trace.regular_dice_delta,trace.pool_cap,trace.rolled_dice),(1,2,2,2))
        self.assertIs(trace.quality,TestQuality.GLORIOUS)
        self.assertEqual(trace.initial_values,(10,10))
        self.assertEqual(trace.final_values,(1,1))
        self.assertTrue(shot.proof.ranged_shot.preparation.source_request.uses_optional_reload_bonus)
        self.assertFalse(result.state.participant('pc1').ranged.loaded)
        self.assertEqual(len(result.state.participant('pc1').fate.spends),1)

    def test_drained_must_finish_existing_cycle_then_fires_ordinary_without_new_cycle(self):
        for weapon in (HANDBOW,PISTOL):
            with self.subTest(weapon=weapon):
                result = execute(scene(weapon=weapon,rounds=5),bonus_hit(weapon)+NPC_HIT+[10]
                    +[1,10,10,10]+NPC_MISS+[1]*3+NPC_MISS
                    +ORDINARY_HIT+NPC_MISS+ORDINARY_HIT+NPC_MISS)
                first,second,third = shots(result)
                reloads = steps(result,PcRangedReloadProof)
                self.assertEqual(tuple(s.proof.result.state.exacting.accumulated_successes for s in reloads),(0,3))
                self.assertIs(reloads[0].proof.result.exacting.test_result.trace.quality,TestQuality.GRIM)
                self.assertTrue(second.source.participant('pc1').injury.conditions.has(Condition.DRAINED))
                for shot in (second,third):
                    self.assertFalse(shot.proof.ranged_shot.preparation.source_request.uses_optional_reload_bonus)
                    self.assertIsNone(shot.proof.ranged_shot.preparation.source_request.next_reload_cycle_id)
                    self.assertEqual(raw(shot).attacker_test.trace.rolled_dice,3)
                    self.assertEqual(shot.source.participant('pc1').ranged,shot.state.participant('pc1').ranged)
                self.assertEqual(len(result.state.participant('pc1').ranged.reload_cycle_ids),1)
                self.assertEqual(first.source.round_state.round_number,1)
                self.assertEqual(second.source.round_state.round_number,4)

    def test_handbow_retains_armour_while_repeater_pistol_uses_toughness(self):
        for weapon,effective,has_wound in ((HANDBOW,12,False),(PISTOL,3,True)):
            source = scene(weapon=weapon,bonus=NEVER)
            enemy = source.enemies[0]
            resilience = ResilienceProfile(3,9)
            source = replace(source,enemies=(replace(enemy,definition=replace(enemy.definition,resilience=resilience),
                state=replace(enemy.state,current_resilience=resilience)),))
            with self.subTest(weapon=weapon):
                result = execute(source,ORDINARY_HIT+NPC_MISS)
                shot, = shots(result)
                self.assertEqual(raw(shot).impact_spec.damage.base,4 if weapon is HANDBOW else 5)
                self.assertEqual(raw(shot).effective_resilience,effective)
                self.assertIs(raw(shot).impact_spec.ignores_armour,weapon is PISTOL)
                self.assertEqual(raw(shot).impact_spec.resilience,resilience)
                self.assertEqual(result.state.enemy('minion1').state.injury.wounds,1 if has_wound else 0)

    def test_shield_is_released_only_for_real_reload_and_restored_before_next_shot(self):
        for weapon in (HANDBOW,PISTOL):
            with self.subTest(weapon=weapon):
                result = execute(scene(weapon=weapon,shield=True,rounds=4),bonus_hit(weapon)+NPC_MISS
                    +[1]*3+NPC_MISS+NPC_MISS+bonus_hit(weapon)+NPC_MISS)
                first,second = shots(result)
                release, = steps(result,PcShieldReleaseProof)
                reload, = steps(result,PcRangedReloadProof)
                recover, = steps(result,PcRecoverProof)
                self.assertEqual(tuple(s.source.round_state.round_number for s in (first,release,reload,recover,second)),
                    (1,2,2,3,4))
                self.assertIs(reload.source.participant('pc1').shield.location,PcShieldLocation.DROPPED)
                self.assertTrue(reload.state.participant('pc1').ranged.loaded)
                self.assertIs(second.source.participant('pc1').shield.location,PcShieldLocation.HELD)
                ordinary = execute(scene(weapon=weapon,bonus=NEVER,shield=True,rounds=2),
                    ORDINARY_HIT+NPC_MISS+ORDINARY_HIT+NPC_MISS)
                self.assertEqual(steps(ordinary,PcShieldReleaseProof),())
                self.assertEqual(steps(ordinary,PcRangedReloadProof),())
                self.assertEqual(steps(ordinary,PcRecoverProof),())
                self.assertIs(ordinary.state.participant('pc1').shield.location,PcShieldLocation.HELD)

    def test_one_hand_loaded_shot_precedes_backup_but_empty_weapon_draws_without_refill(self):
        for weapon in (HANDBOW,PISTOL):
            with self.subTest(weapon=weapon):
                source = scene(weapon=weapon,bonus=NEVER,rounds=2,enemies=3)
                source = replace(source,party=(replace(source.party[0],
                    backup_weapon_policy=PcBackupWeaponPolicy(PcMeleeWeapon.SWORD,PcWeaponHand.LEFT)),))
                loaded = execute(source,ORDINARY_HIT+heavy_hits()
                    +ORDINARY_HIT+[1]*3+NPC_MISS*3)
                self.assertEqual(steps(loaded,PcBackupWeaponDrawProof),())
                self.assertEqual(len(shots(loaded)),2)
                self.assertEqual(len(steps(loaded,PcHandSwapProof)),1)
                self.assertTrue(loaded.state.participant('pc1').ranged.loaded)
                self.assertEqual(loaded.state.participant('pc1').ranged.reload_cycle_ids,())
                source = scene(weapon=weapon,rounds=2,enemies=3)
                source = replace(source,party=(replace(source.party[0],
                    backup_weapon_policy=PcBackupWeaponPolicy(PcMeleeWeapon.SWORD,PcWeaponHand.LEFT)),))
                empty = execute(source,bonus_hit(weapon)+heavy_hits()
                    +ORDINARY_HIT+[1]*3+[10,10,1,1,1,1]*3)
                draw, = steps(empty,PcBackupWeaponDrawProof)
                self.assertEqual(draw.source.round_state.round_number,2)
                self.assertEqual(len(shots(empty)),1)
                self.assertTrue(empty.state.participant('pc1').using_backup_weapon)
                self.assertFalse(empty.state.participant('pc1').ranged.loaded)
                self.assertEqual(steps(empty,PcRangedReloadProof),())
                own = next(s for s in steps(empty,PcAttackProof) if s.proof.request.actor_id=='pc1'
                    and s.source.round_state.round_number==2)
                self.assertEqual(raw(own).impact_spec.damage.base,3)
                self.assertFalse(raw(own).impact_spec.ignores_armour)
                self.assertEqual(own.proof.ranged_shot,None)
                stopped = execute(scene(weapon=weapon,rounds=2,enemies=3),bonus_hit(weapon)+heavy_hits())
                self.assertIs(stopped.outcome,PcMeleeOutcome.UNSUPPORTED_PATH)
                self.assertFalse(stopped.state.participant('pc1').ranged.loaded)
                self.assertEqual(steps(stopped,PcRangedReloadProof),())
                self.assertEqual(stopped.executed_actions,4)

    def test_unchanged_ordinary_weapon_state_does_not_admit_missing_replayed_or_forged_proofs(self):
        result = execute(scene(bonus=NEVER,rounds=2),ORDINARY_HIT+NPC_MISS+ORDINARY_HIT+NPC_MISS)
        first,second = shots(result)
        for shot in (first,second):
            self.assertEqual(apply_pc_melee_step(shot.source,shot),shot.state)
            with self.assertRaises((TypeError,ValueError)):
                apply_pc_melee_step(shot.state,shot)
            with self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(shot.source,replace(shot.proof,ranged_shot=None))
        with self.assertRaises((TypeError,ValueError)):
            apply_pc_melee_step(second.source,first)
        for field,value in (('uses_optional_reload_bonus',True),('next_reload_cycle_id','foreign-cycle')):
            forged = deepcopy(first.proof)
            object.__setattr__(forged.ranged_shot.preparation.source_request,field,value)
            with self.subTest(field=field),self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(first.source,forged)
        class Alias(str):
            pass
        forged = deepcopy(first.proof)
        object.__setattr__(forged.ranged_shot.execution.previous_weapon_state,'weapon_instance_id',Alias('pc1:weapon'))
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(first.source,forged)

    def test_two_pc_weapons_keep_distinct_conditional_and_ordinary_progress(self):
        source = scene(pc_count=2,rounds=2)
        first,second = source.party
        source = replace(source,party=(first,replace(second,pc=replace(second.pc,weapon=PISTOL,
            ranged=ranged_profile(weapon=PISTOL,repeater_bonus_policy=NEVER)))))
        result = execute(source,bonus_hit(HANDBOW)+ORDINARY_HIT+NPC_MISS
            +[1]*3+ORDINARY_HIT+NPC_MISS)
        a,b = (result.state.participant(actor).ranged for actor in ('pc1','pc2'))
        self.assertNotEqual(a.weapon_instance_id,b.weapon_instance_id)
        self.assertIs(a.weapon_id,RangedWeaponId.REPEATER_HANDBOW)
        self.assertIs(b.weapon_id,RangedWeaponId.REPEATER_PISTOL)
        self.assertTrue(a.loaded)
        self.assertTrue(b.loaded)
        self.assertEqual(len(a.reload_cycle_ids),1)
        self.assertEqual(b.reload_cycle_ids,())
        self.assertEqual(len(steps(result,PcRangedReloadProof)),1)
        self.assertEqual(result.executed_actions,6)

    def test_melee_opposition_does_not_activate_repeater_bonus_or_consume_owned_state(self):
        source = scene(weapon=PISTOL)
        enemy = create_pc_book_npc(PcBookNpcProfile.IMPERIAL_OGRE_PISTOL,'minion1')
        npc_policy = PcNpcPistolPolicy('minion1',True,True,True,True,
            PcNpcPistolReloadHandPolicy.TWO_AVAILABLE_HANDS)
        source = replace(source,enemies=(enemy,),npc_pistol_policies=(npc_policy,),
            party=(replace(source.party[0],close_shooting_protection_skill=Skill.MELEE),))
        result = execute(source,[10]*5+[1]*3+[10]*3+[1]*3)
        incoming = next(s for s in steps(result,PcAttackProof) if s.proof.request.actor_id=='minion1')
        self.assertIs(incoming.proof.protection.source_request.selected_skill,Skill.MELEE)
        self.assertEqual(raw(incoming).defender_test.trace.regular_dice_delta,0)
        self.assertEqual(raw(incoming).defender_test.trace.rolled_dice,3)
        self.assertEqual(incoming.source.participant('pc1').ranged,incoming.state.participant('pc1').ranged)
        self.assertEqual(result.executed_actions,2)


if __name__ == '__main__':
    unittest.main()
