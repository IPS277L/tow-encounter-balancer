"""Literal NPC firearm journals: Shoot/Reload, PC consequences and replay bounds."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_pistol_scenarios import make_pc_pistol_scenario
from tests.support.pc_shield_scenarios import shield_loadout
from tests.unit.test_m61_npc_pistol_source import scenario, OFFICIAL, OGRE
from towr.domain.attack_models import AttackOutcome, MissConsequence
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_models import (
    PcAdjacentNpcExitPolicy, PcFatePolicy, PcGloriousPolicy, PcMeleeWeapon,
    PcNearMissPolicy, PcWeaponHand,
)
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcHandDropProof, PcMeleeOutcome, PcMeleeStep, PcWoundCompletionProof,
    PcNpcRecoverProof, PcNpcHelpProof, PcTurnEndProof,
)
from towr.domain.pc_npc_exit_models import PcNpcExitProof
from towr.domain.pc_npc_pistol_models import PcNpcPistolReloadProof, pc_npc_pistol_weapon
from towr.domain.pc_ranged_models import PcRangedReloadProof
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.test_models import Skill, TestQuality
from towr.domain.turn_models import CombatActionKind, ImproviseKind
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario


PC_MISS = [10]*3+[1]*3
OFFICIAL_MISS = [10]*2+[1]*3
OGRE_MISS = [10]*3+[1]*3


def scene(*,profiles=(OFFICIAL,),rounds=1):
    source = scenario(profiles)
    return replace(source,max_rounds=rounds,
        facts=replace(source.facts,outnumbering_bonus_approved=False))


def execute(source,values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def steps(result,kind):
    return tuple(step for step in result.steps if type(step.proof) is kind)


def shots(result):
    return tuple(step for step in steps(result,PcAttackProof) if step.proof.npc_pistol_shot is not None)


def raw(step):
    return step.proof.execution.resolution.attack


class NpcPistolExecutionTests(unittest.TestCase):
    def test_close_miss_consumes_ammunition_and_staggers_only_its_actual_actor(self):
        result = execute(scene(),PC_MISS+OFFICIAL_MISS)
        shot, = shots(result)
        self.assertIs(raw(shot).outcome,AttackOutcome.MISS)
        self.assertIs(raw(shot).miss_consequence,MissConsequence.STAGGER_ATTACKER)
        before = pc_npc_pistol_weapon(shot.source,'minion1')
        after = pc_npc_pistol_weapon(shot.state,'minion1')
        self.assertTrue(before.loaded)
        self.assertFalse(after.loaded)
        self.assertEqual(after.weapon_instance_id,'minion1:weapon')
        self.assertEqual(after.exacting.accumulated_successes,0)
        self.assertTrue(result.state.enemy('minion1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertIs(shot.proof.npc_pistol_shot.execution.source_request.attack_skill,Skill.SHOOTING)
        self.assertIs(shot.proof.protection.source_request.selected_skill,Skill.ATHLETICS)
        self.assertEqual(result.executed_actions,2)

    def test_zero_partial_failure_completion_and_next_shot_are_distinct_actual_actions(self):
        result = execute(scene(rounds=6),PC_MISS+OFFICIAL_MISS
            +PC_MISS+[10]*3+PC_MISS+[1,1,10]+PC_MISS+[10]*3
            +PC_MISS+[1,10,10]+PC_MISS+OFFICIAL_MISS)
        reloads = steps(result,PcNpcPistolReloadProof)
        first,second = shots(result)
        self.assertEqual(tuple(step.proof.result.state.exacting.accumulated_successes for step in reloads),
            (0,2,2,3))
        self.assertEqual(tuple(step.proof.result.state.loaded for step in reloads),(False,False,False,True))
        self.assertEqual((first.source.round_state.round_number,second.source.round_state.round_number),(1,6))
        for count,step in enumerate(reloads,1):
            self.assertEqual(len(step.proof.result.state.exacting.contributions),count)
            self.assertIs(step.proof.result.slot.declaration.kind,CombatActionKind.IMPROVISE)
            self.assertIs(step.proof.result.slot.declaration.improvise_kind,ImproviseKind.SKILL)
            self.assertTrue(step.proof.result.slot.executed)
            self.assertEqual(step.proof.result.exacting.test_result.trace.rolled_dice,3)
            self.assertEqual(step.proof.result.exacting.test_result.trace.threshold,3)
        weapon = pc_npc_pistol_weapon(result.state,'minion1')
        self.assertEqual(len(weapon.reload_cycle_ids),2)
        self.assertNotEqual(*weapon.reload_cycle_ids)
        self.assertEqual(weapon.exacting.contributions,())
        self.assertFalse(weapon.loaded)
        self.assertEqual(result.executed_actions,12)
        self.assertEqual(steps(result,PcNpcRecoverProof),())
        self.assertEqual(steps(result,PcNpcHelpProof),())

    def test_ogre_reload_overshoot_retains_four_real_successes_without_free_shot(self):
        result = execute(scene(profiles=(OGRE,),rounds=3),
            PC_MISS+OGRE_MISS+PC_MISS+[1,1]+PC_MISS+[1,1])
        first,second = steps(result,PcNpcPistolReloadProof)
        self.assertEqual(first.proof.result.state.exacting.accumulated_successes,2)
        self.assertEqual(second.proof.result.state.exacting.accumulated_successes,4)
        self.assertTrue(second.proof.result.state.loaded)
        self.assertEqual(len(shots(result)),1)
        self.assertEqual(result.executed_actions,6)

    def test_multiple_npc_and_pc_firearms_keep_independent_instances_and_reload_dice(self):
        source = scene(profiles=(OFFICIAL,OGRE),rounds=4)
        pc = make_pc_pistol_scenario().party[0].pc
        source = replace(source,party=(replace(source.party[0],pc=pc,initial_weapon_hand=PcWeaponHand.LEFT),))
        result = execute(source,PC_MISS+OFFICIAL_MISS+OGRE_MISS
            +[1]*3+[1]*3+[1,1]
            +PC_MISS+OFFICIAL_MISS+[1,10]
            +[10]*3+[10]*3+OGRE_MISS)
        self.assertEqual(result.executed_actions,12)
        self.assertEqual(len(steps(result,PcRangedReloadProof)),2)
        bank = result.state.npc_pistols
        self.assertEqual(tuple(entry.actor_id for entry in bank),('minion1','minion2'))
        self.assertEqual(tuple(entry.weapon_state.weapon_id for entry in bank),
            (RangedWeaponId.PISTOL,RangedWeaponId.OGRE_PISTOL))
        self.assertEqual(tuple(entry.weapon_state.exacting.accumulated_successes for entry in bank),(0,0))
        self.assertTrue(all(not entry.weapon_state.loaded for entry in bank))
        instances = {entry.weapon_state.weapon_instance_id for entry in bank}
        instances.add(result.state.participant('pc').ranged.weapon_instance_id)
        self.assertEqual(len(instances),3)
        reloads = steps(result,PcNpcPistolReloadProof)
        self.assertEqual(tuple((s.proof.request.actor_id,s.proof.result.exacting.test_result.trace.rolled_dice)
            for s in reloads),(('minion1',3),('minion2',2),('minion2',2),('minion1',3)))
        ogre_complete = next(s for s in reloads if s.proof.request.actor_id=='minion2'
            and s.proof.result.state.loaded)
        self.assertEqual(ogre_complete.proof.result.state.exacting.accumulated_successes,3)

    def test_shield_defence_and_armour_ignore_retain_actual_source_and_wound(self):
        source = scene()
        member = source.party[0]
        source = replace(source,party=(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.SWORD,
            armour_bonus=9),initial_weapon_hand=PcWeaponHand.RIGHT,shield=shield_loadout()),))
        result = execute(source,PC_MISS+[1,1]+[10]*3+[1])
        shot, = shots(result)
        self.assertIs(shot.proof.protection.source_request.selected_skill,Skill.DEFENCE)
        self.assertEqual(raw(shot).defender_test.trace.regular_dice_delta,0)
        self.assertTrue(raw(shot).impact_spec.ignores_armour)
        self.assertEqual(raw(shot).impact_spec.resilience.total,13)
        self.assertEqual(raw(shot).effective_resilience,3)
        self.assertIs(raw(shot).outcome,AttackOutcome.HIT)
        self.assertEqual(len(steps(result,PcWoundCompletionProof)),1)
        self.assertEqual(len(result.state.participant('pc').injury.wounds),1)
        self.assertEqual(result.source.party[0].pc.armour_bonus,9)

    def test_protection_glorious_and_near_miss_use_actual_pc_fate(self):
        source = scene()
        member = source.party[0]
        configured = replace(source,party=(replace(member,fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.ATHLETICS,),0,0)),))
        result = execute(configured,PC_MISS+[1,1]+[10]*3+[1]*3)
        shot, = shots(result)
        self.assertIs(raw(shot).defender_test.trace.quality,TestQuality.GLORIOUS)
        self.assertEqual(raw(shot).defender_test.trace.initial_values,(10,10,10))
        self.assertEqual(raw(shot).defender_test.trace.final_values,(1,1,1))
        self.assertEqual(len(result.state.participant('pc').fate.spends),1)
        self.assertIsNotNone(shot.proof.glorious)
        near_source = replace(source,party=(replace(member,fate_policy=PcFatePolicy.CONFIGURED,
            near_miss_policy=PcNearMissPolicy(8,0)),))
        near = execute(near_source,PC_MISS+[1,1]+[10]*3+[8])
        self.assertEqual(near.state.participant('pc').injury.wounds,())
        self.assertEqual(near.state.participant('pc').fate.rating,2)
        self.assertEqual(steps(near,PcHandDropProof),())
        self.assertFalse(pc_npc_pistol_weapon(near.state,'minion1').loaded)

    def test_prone_target_takes_shooting_penalty_without_outnumber_or_higher_ground_bonus(self):
        source = scene(profiles=(OGRE,OGRE))
        source = replace(source,facts=replace(source.facts,outnumbering_bonus_approved=True))
        result = execute(source,PC_MISS+[1]*3+[10]*3+[9]+[10]*2+[1]*3)
        first,second = shots(result)
        self.assertEqual(raw(first).attacker_test.trace.rolled_dice,3)
        self.assertEqual(raw(first).attacker_test.trace.regular_dice_delta,0)
        self.assertTrue(second.source.participant('pc').injury.conditions.has(Condition.PRONE))
        self.assertEqual(raw(second).attacker_test.trace.rolled_dice,2)
        self.assertEqual(raw(second).attacker_test.trace.regular_dice_delta,-1)

    def test_wound_ten_consumes_grim_on_next_actual_protection_only_once(self):
        result = execute(scene(profiles=(OFFICIAL,OFFICIAL,OFFICIAL)),PC_MISS
            +[1,1]+[10]*3+[10]
            +[10]*2+[1]*3+[10]*3
            +[10]*2+[1]*3)
        _,second,third = shots(result)
        self.assertTrue(second.source.participant('pc').injury.conditions.has(Condition.DRAINED))
        self.assertIs(raw(second).defender_test.trace.quality,TestQuality.GRIM)
        self.assertIs(raw(third).defender_test.trace.quality,TestQuality.NORMAL)
        self.assertEqual(raw(second).defender_test.trace.rolled_dice,3)

    def test_broken_official_stops_or_exits_before_empty_weapon_reload(self):
        source = scene(rounds=2)
        values = PC_MISS+OFFICIAL_MISS+[1]*3+[10]*3
        stopped = execute(source,values)
        self.assertIs(stopped.outcome,PcMeleeOutcome.UNSUPPORTED_PATH)
        self.assertEqual(stopped.unsupported.reason,'npc_broken_turn')
        self.assertTrue(stopped.state.enemy('minion1').state.injury.conditions.has(Condition.BROKEN))
        self.assertFalse(pc_npc_pistol_weapon(stopped.state,'minion1').loaded)
        self.assertEqual(steps(stopped,PcNpcPistolReloadProof),())
        source = replace(source,facts=replace(source.facts,can_leave_zone=True),
            npc_broken_exit_policy=PcAdjacentNpcExitPolicy('outside',True,True))
        exited = execute(source,values)
        self.assertIs(exited.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(exited.exited_npc_ids,('minion1',))
        self.assertEqual(len(steps(exited,PcNpcExitProof)),1)
        self.assertEqual(steps(exited,PcNpcPistolReloadProof),())
        self.assertEqual(exited.executed_actions,3)
        self.assertEqual(pc_npc_pistol_weapon(exited.state,'minion1').exacting.accumulated_successes,0)

    def test_real_heavy_wounds_preserve_defenceless_protection_and_critical_end_phase(self):
        source = scene(profiles=(OFFICIAL,)*4)
        member = source.party[0]
        source = replace(source,party=(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.SWORD),
            initial_weapon_hand=PcWeaponHand.RIGHT,shield=shield_loadout()),))
        first_hit = [1]*2+[10]*3
        # The first Wound clears Staggered, restoring the held Sword's
        # printed Defence bonus for the second and third incoming shots.
        later_hit = [1]*2+[10]*4
        result = execute(source,PC_MISS+first_hit+[1]+later_hit+[1,1]
            +later_hit+[10,9,1]+[1]+[10]*2)
        last = shots(result)[-1]
        self.assertTrue(last.source.participant('pc').injury.conditions.has(Condition.DEFENCELESS))
        self.assertIsNone(raw(last).defender_test)
        self.assertIsNone(last.proof.fate_decline)
        self.assertFalse(pc_npc_pistol_weapon(last.state,'minion4').loaded)

        source = scene(profiles=(OFFICIAL,)*3,rounds=2)
        member = source.party[0]
        source = replace(source,party=(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.SWORD),
            initial_weapon_hand=PcWeaponHand.RIGHT),))
        result = execute(source,PC_MISS+first_hit+[1]+first_hit+[1,1]
            +first_hit+[10,5,1]+[1]+PC_MISS+[10]*3+[10]*9)
        critical, = tuple(step for step in steps(result,PcTurnEndProof) if step.proof.critical is not None)
        self.assertTrue(critical.source.participant('pc').injury.conditions.has(Condition.CRITICALLY_INJURED))
        self.assertTrue(critical.state.participant('pc').injury.conditions.has(Condition.DEFENCELESS))
        self.assertEqual(len(steps(result,PcNpcPistolReloadProof)),3)
        self.assertEqual(result.executed_actions,8)

    def test_shot_reload_and_weapon_bank_reject_replay_forgery_and_foreign_instances(self):
        result = execute(scene(rounds=2),PC_MISS+OFFICIAL_MISS+PC_MISS+[1]*3)
        shot, = shots(result)
        reload, = steps(result,PcNpcPistolReloadProof)
        for step in (shot,reload):
            self.assertEqual(apply_pc_melee_step(step.source,step),step.state)
            with self.assertRaises((TypeError,ValueError)):
                apply_pc_melee_step(step.state,step)
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(shot.source,replace(shot.proof,npc_pistol_shot=None))
        class IdAlias(str):
            pass
        for value in ('other:weapon',IdAlias('minion1:weapon')):
            forged = deepcopy(reload.proof)
            object.__setattr__(forged.request.weapon_state,'weapon_instance_id',value)
            with self.subTest(value=value),self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(reload.source,forged)
        for value in (True,1):
            bank = deepcopy(shot.state.npc_pistols)
            object.__setattr__(bank[0].weapon_state,'loaded',value)
            with self.subTest(value=value),self.assertRaises((TypeError,ValueError)):
                replace(shot.state,npc_pistols=bank)
        forged = deepcopy(shot.proof)
        object.__setattr__(forged.npc_pistol_shot.execution.weapon_state,'reload_cycle_id','foreign-cycle')
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(shot.source,forged)
        self.assertTrue(pc_npc_pistol_weapon(shot.source,'minion1').loaded)


if __name__ == '__main__':
    unittest.main()
