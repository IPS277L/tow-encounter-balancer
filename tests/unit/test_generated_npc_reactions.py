"""Literal Wild Attack/Defensive Stance receipts and source-bound reactions."""
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.armour_fixtures import light_loadout
from dataclasses import replace
import unittest

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_tactics_fixtures import automatic_source
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon,GeneratedTalent
from towr.domain.pc_generated_talents import (
    PcWildAttackProof,PcDefensiveStanceProof,expected_wild_attack,pending_wild_attack,
    expected_defensive_stance,WILD_ATTACK_RULE_ID,
)
from towr.domain.pc_melee_models import PcMeleePolicy,PcMeleeWeapon,PcFatePolicy
from towr.domain.pc_melee_result_models import (
    PcAttackProof,PcAttackerStaggerProof,PcMeleeStep,initial_pc_melee_state,
)
from towr.domain.pc_weapon_models import MORNING_STAR_STAGGERED_RULE_ID
from towr.domain.test_models import TestQuality,Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step


def scenario(*,weapon=GeneratedWeapon.STAFF,talents=(GeneratedTalent.WILD_ATTACK,),
        rounds=1,defence=6,agility=1,athletics=2):
    source=automatic_source(pc_count=1,enemy_count=1,rounds=rounds)
    member=source.party[0]
    member=replace(member,policy=PcMeleePolicy.ATTACK_OR_RECOVER_SELF,
        fate_policy=PcFatePolicy.DECLINE_OPTIONAL_FATE,near_miss_policy=None,glorious_policy=None,
        pc=replace(member.pc,weapon_skill=1,melee=1,defence=1,agility=1,athletics=1,
            strength=1,toughness=20,weapon=PcMeleeWeapon.STAFF))
    npc=GeneratedNpc(3,4,20,agility,2,athletics,initial_generated_weapons(weapon),light_loadout(light=False, shield=False),
        defence=defence,talents=talents)
    return replace(source,party=(member,),enemies=(npc.participant('minion1'),))


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def steps(result,kind):
    return tuple(step for step in result.steps if type(step.proof) is kind)


def attacks(result,actor):
    return tuple(step.proof for step in steps(result,PcAttackProof)
        if step.proof.request.actor_id==actor)


def changed_enemy_conditions(state,*conditions):
    """Preparation-only condition snapshot, never asserted as a real journal."""
    enemy=state.enemy('minion1')
    return replace(state,enemies=(replace(enemy,state=replace(enemy.state,
        injury=replace(enemy.state.injury,conditions=ConditionState(frozenset(conditions))))),))


def stance_result(*,second_pc=(10,1,1,1)):
    source=scenario(talents=(GeneratedTalent.DEFENSIVE_STANCE,),rounds=2)
    result=execute(source,[1,10,10,10]+[10]*4+list(second_pc)+[10]*4)
    return source,result


class GeneratedNpcReactionTests(unittest.TestCase):
    def test_wild_price_precedes_real_test_rerolls_all_failures_without_fate_or_extra_action(self):
        source=scenario()
        result=execute(source,[10]*11)
        price,=steps(result,PcWildAttackProof)
        self.assertFalse(price.source.enemy('minion1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(price.state.enemy('minion1').state.injury.conditions.has(Condition.STAGGERED))
        npc_attack,=attacks(result,'minion1')
        test=npc_attack.execution.resolution.attack.attacker_test
        self.assertIs(test.trace.quality,TestQuality.GLORIOUS)
        self.assertEqual((test.trace.rolled_dice,len(test.trace.rerolls)),(3,3))
        self.assertTrue(npc_attack.request.kernel_request.attack.attacker_is_staggered)
        self.assertEqual([quality.rule_id for quality in
            npc_attack.request.kernel_request.attack.attacker_test.quality_modifiers],[WILD_ATTACK_RULE_ID])
        self.assertEqual(result.executed_actions,2)
        self.assertEqual(result.state.party[0].fate,source.party[0].fate)
        self.assertIsNone(pending_wild_attack(result.state))

    def test_wild_price_applies_morning_star_penalty_before_the_glorious_roll(self):
        result=execute(scenario(weapon=GeneratedWeapon.MORNING_STAR),[10]*9)
        npc_attack,=attacks(result,'minion1')
        request=npc_attack.request.kernel_request.attack.attacker_test
        self.assertEqual([(m.rule_id,m.amount) for m in request.dice_modifiers],
            [(MORNING_STAR_STAGGERED_RULE_ID,-1)])
        trace=npc_attack.execution.resolution.attack.attacker_test.trace
        self.assertEqual((trace.base_dice,trace.rolled_dice,len(trace.rerolls)),(3,2,2))
        self.assertEqual(npc_attack.execution.resolution.attack.impact_spec.damage.base,5)

    def test_wild_paid_sword_loses_defence_bonus_and_cannot_pay_or_gain_glorious_again_while_staggered(self):
        result=execute(scenario(weapon=GeneratedWeapon.SWORD,rounds=2),[10]*20)
        pc_attacks=attacks(result,'pc1')
        self.assertEqual(tuple(a.execution.resolution.attack.defender_test.trace.rolled_dice
            for a in pc_attacks),(4,3))
        npc_attacks=attacks(result,'minion1')
        self.assertEqual(tuple(a.execution.resolution.attack.attacker_test.trace.quality
            for a in npc_attacks),(TestQuality.GLORIOUS,TestQuality.NORMAL))
        self.assertEqual(len(steps(result,PcWildAttackProof)),1)

    def test_wild_rejects_wrong_actor_repeated_price_and_skipping_paid_attack(self):
        result=execute(scenario(),[10]*11)
        price,=steps(result,PcWildAttackProof)
        with self.assertRaises(ValueError):
            PcMeleeStep(price.source,replace(price.proof,actor_id='pc1'))
        with self.assertRaises(ValueError):
            PcMeleeStep(price.source,replace(price.proof,action_id='another-action'))
        with self.assertRaises(ValueError):
            PcMeleeStep(price.state,price.proof)
        with self.assertRaisesRegex(ValueError,'paid Wild Attack'):
            PcMeleeStep(price.state,result.steps[-1].proof)
        state=initial_pc_melee_state(result.source)
        for step in result.steps:
            state=apply_pc_melee_step(state,step)
        self.assertEqual(state,result.state)

    def test_drained_or_already_staggered_snapshot_cannot_pay_wild_price(self):
        result=execute(scenario(),[10]*11)
        before=steps(result,PcWildAttackProof)[0].source
        for conditions in ((Condition.DRAINED,),(Condition.STAGGERED,),
                (Condition.DRAINED,Condition.STAGGERED)):
            snapshot=changed_enemy_conditions(before,*conditions)
            with self.subTest(conditions=conditions):
                self.assertIsNone(expected_wild_attack(snapshot))
                self.assertIsNone(pending_wild_attack(snapshot))

    def test_successful_defence_trades_actual_new_miss_stagger_for_self_removal(self):
        source,result=stance_result()
        stance,=steps(result,PcDefensiveStanceProof)
        self.assertIs(stance.source.pending[0],stance.proof.source)
        self.assertTrue(stance.source.enemy('minion1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(stance.state.enemy('minion1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(stance.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(stance.state.pending)
        attack=attacks(result,'pc1')[1]
        self.assertEqual((attack.execution.resolution.attack.attacker_test.successes,
            attack.execution.resolution.attack.defender_test.successes),(0,3))
        self.assertIs(attack.protection.source_request.selected_skill,Skill.DEFENCE)
        self.assertEqual(result.executed_actions,4)
        self.assertEqual(result.state.party[0].fate,source.party[0].fate)

    def test_defensive_stance_does_not_activate_for_zero_against_zero(self):
        _,result=stance_result(second_pc=[10]*4)
        self.assertFalse(steps(result,PcDefensiveStanceProof))
        self.assertTrue(result.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))

    def test_defensive_stance_preserves_normal_counter_stagger_when_self_is_fresh(self):
        result=execute(scenario(talents=(GeneratedTalent.DEFENSIVE_STANCE,)),[10,1,1,1]+[10]*4)
        self.assertFalse(steps(result,PcDefensiveStanceProof))
        self.assertTrue(result.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))

    def test_defensive_stance_cannot_heal_by_foregoing_nothing_against_already_staggered_attacker(self):
        source=scenario(talents=(GeneratedTalent.DEFENSIVE_STANCE,),rounds=2)
        result=execute(source,[10]*8+[10,1,1,1]+[10]*4)
        self.assertFalse(steps(result,PcDefensiveStanceProof))
        self.assertTrue(result.state.enemy('minion1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(attacks(result,'pc1')[1].request.kernel_request.attack.attacker_is_staggered)

    def test_athletics_opposition_cannot_activate_defensive_stance(self):
        source=scenario(talents=(GeneratedTalent.DEFENSIVE_STANCE,),rounds=2,
            defence=2,agility=6,athletics=6)
        result=execute(source,[1]+[10]*6+[10]*4+[10]+[1]*6+[10]*4)
        self.assertFalse(steps(result,PcDefensiveStanceProof))
        self.assertIs(attacks(result,'pc1')[1].protection.source_request.selected_skill,Skill.ATHLETICS)
        self.assertTrue(result.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))

    def test_drained_snapshot_keeps_passive_defensive_stance(self):
        _,result=stance_result()
        stance,=steps(result,PcDefensiveStanceProof)
        snapshot=changed_enemy_conditions(stance.source,Condition.STAGGERED,Condition.DRAINED)
        self.assertEqual(expected_defensive_stance(snapshot),stance.proof)

    def test_stance_removal_makes_the_following_own_wild_attack_available(self):
        source=scenario(talents=(GeneratedTalent.DEFENSIVE_STANCE,GeneratedTalent.WILD_ATTACK),rounds=2)
        result=execute(source,[1,10,10,10]+[10]*4+[10,1,1,1]+[10]*7)
        stance,=steps(result,PcDefensiveStanceProof)
        price,=steps(result,PcWildAttackProof)
        self.assertLess(result.steps.index(stance),result.steps.index(price))
        self.assertFalse(price.source.enemy('minion1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(price.state.enemy('minion1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(tuple(a.execution.resolution.attack.attacker_test.trace.quality
            for a in attacks(result,'minion1')),(TestQuality.NORMAL,TestQuality.GLORIOUS))
        self.assertEqual(result.executed_actions,4)

    def test_stance_replay_rejects_wrong_source_actors_repeat_and_default_miss_stagger(self):
        _,result=stance_result()
        stance,=steps(result,PcDefensiveStanceProof)
        for altered in (replace(stance.proof,actor_id='another'),
                replace(stance.proof,attacker_id='another'),
                replace(stance.proof,source=replace(stance.proof.source,attack_id='another'))):
            with self.subTest(altered=altered),self.assertRaises(ValueError):
                PcMeleeStep(stance.source,altered)
        with self.assertRaises(ValueError):
            PcMeleeStep(stance.state,stance.proof)
        with self.assertRaisesRegex(ValueError,'selected Defensive Stance'):
            PcMeleeStep(stance.source,PcAttackerStaggerProof(stance.proof.source))
        state=initial_pc_melee_state(result.source)
        for step in result.steps:
            state=apply_pc_melee_step(state,step)
        self.assertEqual(state,result.state)


if __name__=='__main__':
    unittest.main()
