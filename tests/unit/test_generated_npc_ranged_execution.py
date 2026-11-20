"""Literal native generated Shooting journals and explicit local preparation tests.

Prepared Condition snapshots exercise request boundaries, not invented legal
complete battle histories. Full runs retain actual prices, cycles and receipts.
"""
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.armour_fixtures import light_loadout
from tests.support.talent_sources import paid_talent
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_shield_scenarios import shield_loadout
from tests.support.pc_tactics_fixtures import automatic_source
from towr.domain.attack_models import AttackOutcome, MissConsequence
from towr.domain.condition_models import Condition
from towr.domain.talent_catalog import TalentId
from towr.domain.generated_npc_models import (
    GeneratedNpc, GeneratedRangedFacts, GeneratedWeapon,
    GENERATED_RANGED_WEAPONS,
)
from towr.domain.pc_generated_talents import PcWildAttackProof, PcDefensiveStanceProof
from towr.domain.pc_melee_models import PcFatePolicy, PcMeleePolicy, PcMeleeWeapon, PcWeaponHand
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcMeleeStep, initial_pc_melee_state, build_pc_melee_attack,
)
from towr.domain.pc_npc_ranged_models import PcNpcRangedReloadProof, pc_npc_ranged_weapon
from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
from towr.domain.ranged_weapon_profiles import REPEATER_SHOOTING_BONUS_RULE_ID
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario
from towr.rules.test_resolution import resolve_test


def component(weapon=GeneratedWeapon.PISTOL, *, bs=2, shooting=2, initiative=2,
        dexterity=3, ws=1, strength=1, talents=()):
    blackpowder=weapon is not GeneratedWeapon.REPEATER_HANDBOW
    ranged=(GeneratedRangedFacts(bs,shooting,initiative,dexterity,True,
        True if blackpowder else None,True if blackpowder else None)
        if weapon in GENERATED_RANGED_WEAPONS else None)
    return GeneratedNpc(ws,strength,20,1,2,2,initial_generated_weapons(weapon),light_loadout(light=False, shield=False),
        defence=2,talents=talents,ranged=ranged)


def scene(*, weapons=(GeneratedWeapon.PISTOL,), rounds=1, automatic=False,
        npc_changes=None, pc_changes=None, shield=False, outnumber=False, pc_talents=()):
    source=automatic_source(pc_count=1,enemy_count=len(weapons),rounds=rounds)
    member=source.party[0]
    pc=dict(weapon_skill=1,melee=1,defence=1,agility=1,athletics=1,strength=1,
        toughness=20,weapon=PcMeleeWeapon.STAFF)
    pc.update(pc_changes or {})
    member=replace(member,pc=replace(member.pc,**pc),
        policy=PcMeleePolicy.AUTOMATIC_COMBAT if automatic else PcMeleePolicy.ATTACK_OR_RECOVER_SELF,
        fate_policy=PcFatePolicy.DECLINE_OPTIONAL_FATE,near_miss_policy=None,glorious_policy=None,
        initial_weapon_hand=PcWeaponHand.RIGHT if shield else PcWeaponHand.LEFT,
        shield=shield_loadout() if shield else None,talents=pc_talents)
    components=tuple(component(weapon,**(npc_changes or {})) for weapon in weapons)
    actors=source.enemy_activation_order
    return replace(source,party=(member,),
        enemies=tuple(npc.participant(actor) for npc,actor in zip(components,actors)),
        npc_ranged_policies=tuple(pc_npc_ranged_policy_for_generated(npc,actor)
            for npc,actor in zip(components,actors) if npc.ranged is not None),
        facts=replace(source.facts,outnumbering_bonus_approved=outnumber))


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def steps(result,kind):
    return tuple(step for step in result.steps if type(step.proof) is kind)


def shots(result):
    return tuple(step for step in steps(result,PcAttackProof) if step.proof.npc_ranged_shot is not None)


def attack(step):
    return step.proof.execution.resolution.attack


class GeneratedRangedExecutionTests(unittest.TestCase):
    def assert_replays(self,result):
        state=initial_pc_melee_state(result.source)
        for step in result.steps:
            state=apply_pc_melee_step(state,step)
        self.assertEqual(state,result.state)

    def test_pistol_zero_partial_reload_and_second_shot_are_real_distinct_actions(self):
        result=execute(scene(rounds=6),[10]*5+[10]*4+[10]*2+[1,10]+[10]*2+[1,1]+[10]*5+[10]*4)
        reloads=steps(result,PcNpcRangedReloadProof)
        self.assertEqual([step.proof.result.state.exacting.accumulated_successes for step in reloads],
            [0,1,3,0])
        self.assertEqual([step.proof.result.state.loaded for step in reloads],[False,False,True,False])
        self.assertEqual([step.source.round_state.round_number for step in shots(result)],[1,5])
        self.assertEqual(result.executed_actions,12)
        for step in reloads:
            self.assertEqual(step.proof.result.exacting.test_result.trace.rolled_dice,2)
            self.assertEqual(step.proof.result.exacting.test_result.trace.threshold,3)
        weapon=pc_npc_ranged_weapon(result.state,'minion1')
        self.assertEqual(len(weapon.reload_cycle_ids),2)
        self.assertNotEqual(*weapon.reload_cycle_ids)
        self.assertIs(attack(shots(result)[0]).miss_consequence,MissConsequence.STAGGER_ATTACKER)
        self.assertIs(attack(shots(result)[1]).miss_consequence,MissConsequence.NONE)
        self.assert_replays(result)

    def test_repeaters_save_reload_cost_then_use_bonus_at_final_turn(self):
        for weapon,bonus in ((GeneratedWeapon.REPEATER_PISTOL,2),(GeneratedWeapon.REPEATER_HANDBOW,1)):
            with self.subTest(weapon=weapon):
                result=execute(scene(weapons=(weapon,),rounds=3),[10]*(15+bonus))
                observed=shots(result)
                self.assertEqual(len(observed),3)
                self.assertEqual([step.proof.npc_ranged_shot.preparation.source_request.uses_optional_reload_bonus
                    for step in observed],[False,False,True])
                self.assertTrue(pc_npc_ranged_weapon(observed[0].state,'minion1').loaded)
                self.assertTrue(pc_npc_ranged_weapon(observed[1].state,'minion1').loaded)
                self.assertFalse(pc_npc_ranged_weapon(observed[2].state,'minion1').loaded)
                self.assertEqual(steps(result,PcNpcRangedReloadProof),())
                self.assertEqual(attack(observed[-1]).attacker_test.trace.rolled_dice,2+bonus)
                self.assert_replays(result)

    def test_automatic_pc_chooses_actual_melee_shield_defence_and_athletics(self):
        cases=[(dict(weapon_skill=3,melee=6),False,Skill.MELEE,9),
            (dict(weapon_skill=3,defence=6),True,Skill.DEFENCE,9),
            (dict(agility=3,athletics=6),False,Skill.ATHLETICS,7)]
        for changes,shield,skill,count in cases:
            with self.subTest(skill=skill):
                result=execute(scene(automatic=True,pc_changes=changes,shield=shield),[10]*count)
                shot,=shots(result)
                self.assertIs(shot.proof.protection.source_request.selected_skill,skill)
                self.assertEqual(attack(shot).defender_test.trace.rolled_dice,3)
                self.assert_replays(result)

    def test_both_repeaters_really_reload_after_chosen_early_bonus_and_shoot_again(self):
        # Strong actual Shield Defence makes the larger burst worthwhile even
        # with an intervening Reload. High I/Dex gives that cost a low forecast.
        for weapon,bonus in ((GeneratedWeapon.REPEATER_PISTOL,2),(GeneratedWeapon.REPEATER_HANDBOW,1)):
            with self.subTest(weapon=weapon):
                source=scene(weapons=(weapon,),rounds=3,shield=True,
                    pc_changes=dict(weapon_skill=10,defence=6),
                    npc_changes=dict(initiative=10,dexterity=6))
                result=execute(source,[10]*(23+bonus)+[10]*11+[1]*10+[10]*(23+bonus))
                first,second=shots(result)
                reload,=steps(result,PcNpcRangedReloadProof)
                self.assertEqual([first.source.round_state.round_number,
                    reload.source.round_state.round_number,second.source.round_state.round_number],[1,2,3])
                self.assertTrue(first.proof.npc_ranged_shot.preparation.source_request.uses_optional_reload_bonus)
                self.assertTrue(second.proof.npc_ranged_shot.preparation.source_request.uses_optional_reload_bonus)
                self.assertEqual(reload.proof.result.state.exacting.accumulated_successes,10)
                self.assertTrue(reload.proof.result.state.loaded)
                self.assertEqual(result.executed_actions,6)
                self.assert_replays(result)

    def test_shooting_does_not_activate_wild_or_trade_stagger_through_shield_defence(self):
        source=scene(automatic=True,shield=True,pc_changes=dict(weapon_skill=3,defence=6),
            npc_changes=dict(ws=3,strength=4,talents=(paid_talent(TalentId.WILD_ATTACK),)),
            pc_talents=(paid_talent(TalentId.DEFENSIVE_STANCE),))
        result=execute(source,[10]*3+[1]*3+[10]*2+[1]*3)
        shot,=shots(result)
        self.assertEqual(attack(shot).defender_test.successes,3)
        self.assertIs(shot.proof.protection.source_request.selected_skill,Skill.DEFENCE)
        self.assertEqual(steps(result,PcWildAttackProof),())
        self.assertEqual(steps(result,PcDefensiveStanceProof),())
        self.assertTrue(result.state.party[0].injury.conditions.has(Condition.STAGGERED))
        self.assert_replays(result)

    def test_mixed_component_roster_has_melee_outnumber_bonus_but_not_shooting_bonus(self):
        result=execute(scene(weapons=(GeneratedWeapon.STAFF,GeneratedWeapon.PISTOL),
            outnumber=True),[10]*8)
        attacks=steps(result,PcAttackProof)
        melee=next(step for step in attacks if step.proof.request.actor_id=='minion1')
        shot,=shots(result)
        self.assertEqual(attack(melee).attacker_test.trace.regular_dice_delta,1)
        self.assertEqual(attack(shot).attacker_test.trace.regular_dice_delta,0)
        self.assertEqual(result.executed_actions,3)
        self.assertEqual(sum(pc_npc_ranged_weapon(result.state,enemy.state.actor_id) is not None
            for enemy in result.state.enemies),1)
        self.assert_replays(result)

    def test_actual_firearm_ignores_body_and_shield_armour_but_handbow_does_not(self):
        for weapon,count,expected in ((GeneratedWeapon.PISTOL,6,True),
                (GeneratedWeapon.REPEATER_HANDBOW,6,False)):
            with self.subTest(weapon=weapon):
                values=[1,10]+[1]*(2 if expected else 3)+[10]+([1] if expected else [])
                self.assertEqual(len(values),count)
                result=execute(scene(weapons=(weapon,),shield=True,
                    pc_changes=dict(toughness=3,armour_bonus=9)),values)
                shot,=shots(result)
                self.assertIs(attack(shot).impact_spec.ignores_armour,expected)
                self.assertEqual(attack(shot).effective_resilience,3 if expected else 13)
                self.assertEqual(len(result.state.party[0].injury.wounds),int(expected))
                self.assert_replays(result)

    def test_prepared_prone_penalty_minimum_die_and_drained_mode_boundary(self):
        # Preparation-only states: no fabricated Condition event is claimed as
        # part of these otherwise genuine native shot prefixes.
        result=execute(scene(npc_changes=dict(bs=1,shooting=6)),[10]*4)
        before=shots(result)[0].source
        member=before.party[0]
        prone=replace(member,injury=replace(member.injury,
            conditions=member.injury.conditions.with_condition(Condition.PRONE)))
        prepared=replace(before,party=(prone,))
        request,_=build_pc_melee_attack(prepared)
        rng=ScriptedD10([2])
        rolled=resolve_test(request.kernel_request.attack.attacker_test,rng)
        rng.assert_exhausted()
        self.assertEqual((rolled.trace.regular_dice_delta,rolled.trace.rolled_dice,rolled.trace.threshold),(-1,1,1))
        self.assertTrue(rolled.trace.minimum_die_rule_applied)
        self.assertEqual(rolled.successes,0)
        boosted=execute(scene(weapons=(GeneratedWeapon.REPEATER_PISTOL,)),[10]*7)
        before=shots(boosted)[0].source
        enemy=before.enemies[0]
        enemy=replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
            conditions=enemy.state.injury.conditions.with_condition(Condition.DRAINED))))
        prepared=replace(before,enemies=(enemy,))
        request,_=build_pc_melee_attack(prepared)
        self.assertFalse(any(m.rule_id==REPEATER_SHOOTING_BONUS_RULE_ID
            for m in request.kernel_request.attack.attacker_test.dice_modifiers))

    def test_shot_reload_and_bank_proofs_reject_missing_repeat_and_foreign_cycle(self):
        result=execute(scene(rounds=2),[10]*7+[1,1])
        shot,=shots(result)
        reload,=steps(result,PcNpcRangedReloadProof)
        for step in (shot,reload):
            with self.subTest(proof=type(step.proof)),self.assertRaises((TypeError,ValueError)):
                apply_pc_melee_step(step.state,step)
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(shot.source,replace(shot.proof,npc_ranged_shot=None))
        forged=deepcopy(reload.proof)
        object.__setattr__(forged.request.weapon_state,'weapon_instance_id','foreign:weapon')
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(reload.source,forged)
        forged=deepcopy(shot.state.enemies)
        object.__setattr__(forged[0].state.weapon_inventory.active.reload,'reload_cycle_id','foreign:cycle')
        with self.assertRaises((TypeError,ValueError)):
            replace(shot.state,enemies=forged)
        enemy=shot.state.enemies[0]
        for inventory in (None,replace(enemy.state.weapon_inventory,items=(),active_item_id=None)):
            with self.subTest(erased_inventory=inventory),self.assertRaises((TypeError,ValueError)):
                replace(shot.state,enemies=(replace(enemy,state=replace(enemy.state,weapon_inventory=inventory)),))
        self.assert_replays(result)

    def test_missing_policy_and_forged_ranged_component_fail_before_rng(self):
        source=scene()
        with self.assertRaises(ValueError):
            replace(source,npc_ranged_policies=())
        forged=deepcopy(source)
        object.__setattr__(forged.enemies[0].definition.generated_components.ranged,'ballistic_skill',True)
        rng=ScriptedD10(())
        with self.assertRaises((TypeError,ValueError)):
            run_pc_melee_scenario(forged,rng)
        rng.assert_exhausted()

    def test_trial_and_summary_counters_preserve_actual_shot_reload_action_budget(self):
        from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
        from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
        from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation

        generators=[]
        def rng_factory(seed):
            rng=ScriptedD10([10]*7+[1,1]+[10]*2+[1,10])
            generators.append(rng)
            return rng
        request=PcMeleeSimulationRequest(scene(rounds=3),42,2)
        result=run_pc_melee_simulation(request,rng_factory=rng_factory)
        self.assertIsNot(generators[0],generators[1])
        for rng,record in zip(generators,result.records):
            rng.assert_exhausted()
            row,=record.npc_ranged_counts
            self.assertEqual((row.actor_id,row.shots,row.bonus_shots,row.reload_actions),('minion1',1,0,2))
            self.assertEqual(record.executed_actions,6)
            for counts in (None,(),(replace(row,bonus_shots=1),),(replace(row,shots=2),)):
                with self.subTest(counts=counts),self.assertRaises(ValueError):
                    replace(record,npc_ranged_counts=counts)
        row,=summarize_pc_melee_simulation(result).npc_ranged_counts
        self.assertEqual((row.shots,row.bonus_shots,row.reload_actions),(2,0,4))

    def test_prepared_next_test_magic_penalty_is_consumed_by_actual_reload_only(self):
        from towr.domain.pc_magic_models import PcMagicModifier,PcMagicTaskKind
        from towr.domain.pc_npc_ranged_models import build_pc_npc_ranged_reload,npc_ranged_reload_test
        from towr.domain.reload_models import _complete_reload_action_after_test
        from towr.rules.test_resolution import resolve_test
        result=execute(scene(rounds=2),[10]*7+[1,1])
        actual_reload,=steps(result,PcNpcRangedReloadProof)
        penalty=PcMagicModifier('prepared:next-test','minion1',PcMagicTaskKind.NEXT_TEST_PENALTY)
        other=PcMagicModifier('prepared:other-test','pc1',PcMagicTaskKind.NEXT_TEST_PENALTY)
        # Local prepared modifier boundary, not a fabricated complete Casting
        # history. The actual reload slot/progress comes from the literal run.
        prepared=replace(actual_reload.source,magic_modifiers=(penalty,other))
        request=build_pc_npc_ranged_reload(prepared)
        rng=ScriptedD10([1])
        test=resolve_test(request.dexterity_test,rng)
        rng.assert_exhausted()
        self.assertEqual(test.trace.rolled_dice,1)
        proof=PcNpcRangedReloadProof(request,_complete_reload_action_after_test(request,test))
        after=PcMeleeStep(prepared,proof).state
        self.assertEqual(after.magic_modifiers,(other,))
        self.assertEqual(pc_npc_ranged_weapon(after,'minion1').exacting.accumulated_successes,1)
        later=npc_ranged_reload_test(after,'minion1','prepared:later')
        self.assertFalse(any(m.rule_id==penalty.source_id for m in later.dice_modifiers))


if __name__=='__main__':
    unittest.main()
