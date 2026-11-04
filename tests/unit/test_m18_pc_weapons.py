"""Literal encounter traces and explicit preparation boundaries for PG 92–93 weapons."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario, make_pc_melee_party_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_m12_pc_heavy_wounds import heavy_prefix
from towr.domain.attack_models import DamageModifier, ImpactOutcome, ResilienceProfile
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.pc_help_models import build_pc_help_action
from towr.domain.pc_melee_models import (PcMeleeWeapon, PcMeleePolicy, PcHelpPolicy, PcHelpTarget,
    PcFatePolicy, PcGloriousPolicy, PcWeaponHand)
from towr.domain.pc_melee_result_models import (PcAttackProof, PcHelpProof, PcRecoverProof,
    PcHandSwapProof, PcMeleeStep, initial_pc_melee_state, build_pc_melee_attack)
from towr.domain.pc_weapon_models import (AXE_ARMOUR_RULE_ID, WARHAMMER_STAGGERED_RULE_ID,
    MORNING_STAR_STAGGERED_RULE_ID)
from towr.domain.test_models import DiceModifier, Skill
from towr.domain.turn_models import CombatTurnStartRequest
from towr.engine.pc_melee_runner import run_pc_melee_scenario, apply_pc_melee_step
from towr.rules.test_resolution import resolve_test
from towr.rules.turn_resolution import start_combat_turn


NEW_WEAPONS = (PcMeleeWeapon.DAGGER, PcMeleeWeapon.AXE,
    PcMeleeWeapon.WARHAMMER, PcMeleeWeapon.MORNING_STAR)


def execute(source, values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source, rng)
    rng.assert_exhausted()
    return result


def armoured(source, bonus=1):
    return replace(source, enemies=tuple(replace(enemy,
        definition=replace(enemy.definition, resilience=ResilienceProfile(3, bonus)),
        state=replace(enemy.state, current_resilience=ResilienceProfile(3, bonus))) for enemy in source.enemies))


def attacks(result, actor='pc'):
    return tuple(step for step in result.steps
        if isinstance(step.proof, PcAttackProof) and step.proof.request.actor_id == actor)


def pure_active(source):
    """An authored preparation boundary; this does not claim a native encounter prefix."""
    state = initial_pc_melee_state(source)
    clock = start_combat_turn(CombatTurnStartRequest('pure:start', state.round_state,
        source.pc_activation_order[0])).state
    return replace(state, round_state=clock)


def pure_conditions(state, conditions):
    member = state.party[0]
    return replace(state, party=(replace(member, injury=replace(member.injury,
        conditions=ConditionState(frozenset(conditions)))), *state.party[1:]))


class PcWeaponTests(unittest.TestCase):
    def test_native_each_weapon_uses_its_strength_damage(self):
        for weapon, base in ((PcMeleeWeapon.DAGGER, 2), (PcMeleeWeapon.AXE, 3),
                (PcMeleeWeapon.WARHAMMER, 3), (PcMeleeWeapon.MORNING_STAR, 4)):
            with self.subTest(weapon=weapon):
                result = execute(make_pc_melee_scenario(weapon=weapon, max_rounds=1), [1]*3+[10]*2)
                attack = attacks(result)[0].proof.execution.resolution.attack
                self.assertEqual((attack.impact_spec.damage.base, attack.damage), (base, base+3))
                self.assertIs(attack.impact, ImpactOutcome.WOUND)

    def test_native_dagger_strength_one_has_zero_base_and_tie_damage_zero(self):
        source = make_pc_melee_scenario(weapon=PcMeleeWeapon.DAGGER, max_rounds=1)
        source = replace(source, party=(replace(source.party[0], pc=replace(source.party[0].pc, strength=1)),))
        result = execute(source, [1,10,10]+[1,10]+[10,10]+[1,10,10])
        attack = attacks(result)[0].proof.execution.resolution.attack
        self.assertEqual((attack.impact_spec.damage.base, attack.damage, attack.success_margin), (0,0,0))
        self.assertTrue(attack.tie_break_applied)
        self.assertIs(attack.impact, ImpactOutcome.STAGGERED)

    def test_native_axe_armour_bonus_crosses_wound_boundary_without_ignoring_armour(self):
        source = armoured(make_pc_melee_scenario(weapon=PcMeleeWeapon.AXE, max_rounds=1))
        result = execute(source, [1,10,10]+[10,10])
        step, = attacks(result)
        attack = step.proof.execution.resolution.attack
        self.assertEqual((attack.damage, attack.effective_resilience), (5,4))
        self.assertEqual(attack.impact_spec.damage_modifiers, (DamageModifier(AXE_ARMOUR_RULE_ID,1),))
        self.assertEqual(attack.applied_rule_ids, (AXE_ARMOUR_RULE_ID,))
        self.assertFalse(attack.impact_spec.ignores_armour)
        # Exact source arithmetic and trait receipt must survive replay validation.
        forged = deepcopy(step.proof)
        object.__setattr__(forged.execution.resolution.attack, 'damage', 4)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(PcMeleeStep(step.source, forged))
        forged = deepcopy(step.proof)
        object.__setattr__(forged.execution.resolution.attack, 'applied_rule_ids', ())
        with self.assertRaises(ValueError):
            apply_pc_melee_step(PcMeleeStep(step.source, forged))
        forged = deepcopy(step.proof)
        object.__setattr__(forged.request.kernel_request.attack.impact_spec,'damage_modifiers',
            (DamageModifier('authored:foreign-damage',1),))
        with self.assertRaises(ValueError):
            PcMeleeStep(step.source,forged)

    def test_native_axe_trait_on_tie_and_absent_from_miss_trace(self):
        source = armoured(make_pc_melee_scenario(weapon=PcMeleeWeapon.AXE, max_rounds=1))
        tied = execute(source, [1,10,10]+[1,10]+[10,10]+[1]*3)
        attack = attacks(tied)[0].proof.execution.resolution.attack
        self.assertEqual((attack.damage, attack.effective_resilience), (4,4))
        self.assertIs(attack.impact, ImpactOutcome.STAGGERED)
        self.assertEqual(attack.applied_rule_ids, (AXE_ARMOUR_RULE_ID,'RULE-COMBAT-006:attack-tie'))
        missed = execute(source, [10]*3+[1]*2+[10]*2+[1]*3)
        attack = attacks(missed)[0].proof.execution.resolution.attack
        self.assertIsNone(attack.damage)
        self.assertEqual(attack.applied_rule_ids, ())
        self.assertEqual(attack.impact_spec.damage_modifiers, (DamageModifier(AXE_ARMOUR_RULE_ID,1),))

    def test_pure_axe_preparation_tracks_actual_current_target_armour(self):
        state = pure_active(armoured(make_pc_melee_scenario(weapon=PcMeleeWeapon.AXE)))
        self.assertTrue(build_pc_melee_attack(state)[0].kernel_request.attack.impact_spec.damage_modifiers)
        enemy = state.enemies[0]
        with self.assertRaises(ValueError):
            replace(state, enemies=(replace(enemy,
                state=replace(enemy.state, current_resilience=ResilienceProfile(3))),))
        # Equipment is immutable within a native owner; independently author the unarmoured target.
        unarmoured = pure_active(armoured(state.source,bonus=0))
        self.assertEqual(build_pc_melee_attack(unarmoured)[0].kernel_request.attack.impact_spec.damage_modifiers, ())

    def test_native_warhammer_bonus_appears_on_next_attack_against_staggered_enemy(self):
        source = make_pc_melee_scenario(weapon=PcMeleeWeapon.WARHAMMER, max_rounds=2)
        source = replace(source, party=(replace(source.party[0], pc=replace(source.party[0].pc, strength=1)),))
        result = execute(source, [1,10,10]+[10,10]+[10,10]+[1]*3+[1]*4+[10,10])
        first, second = attacks(result)
        self.assertEqual(first.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,3)
        request = second.proof.request.kernel_request.attack.attacker_test
        self.assertEqual(request.dice_modifiers,(DiceModifier(WARHAMMER_STAGGERED_RULE_ID,1),))
        self.assertEqual(second.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,4)

    def test_pure_warhammer_target_trait_obeys_cap_drained_and_condition_removal(self):
        state = pure_active(make_pc_melee_scenario(weapon=PcMeleeWeapon.WARHAMMER))
        enemy = state.enemies[0]
        staggered = replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
            conditions=ConditionState(frozenset({Condition.STAGGERED})))) )
        state = replace(state,enemies=(staggered,))
        test = build_pc_melee_attack(state)[0].kernel_request.attack.attacker_test
        capped = replace(test,dice_modifiers=(*test.dice_modifiers,DiceModifier('authored:cap',9)))
        rng = ScriptedD10([1]*6)
        self.assertEqual(resolve_test(capped,rng).trace.rolled_dice,6)
        rng.assert_exhausted()
        drained = build_pc_melee_attack(pure_conditions(state,(Condition.DRAINED,)))[0].kernel_request.attack.attacker_test
        self.assertEqual(drained.dice_modifiers,())
        self.assertEqual(build_pc_melee_attack(replace(state,enemies=(enemy,)))[0].kernel_request.attack.attacker_test.dice_modifiers,())

    def test_native_morning_star_stagger_penalty_applies_without_recovering_stagger(self):
        source = make_pc_melee_scenario(weapon=PcMeleeWeapon.MORNING_STAR,max_rounds=2)
        result = execute(source,[10]*3+[1]*2+[10]*2+[1]*3+[1]*2+[10]*2)
        first, second = attacks(result)
        self.assertEqual(first.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,3)
        self.assertEqual(second.proof.request.kernel_request.attack.attacker_test.dice_modifiers,
            (DiceModifier(MORNING_STAR_STAGGERED_RULE_ID,-1),))
        self.assertEqual(second.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,2)

    def test_native_morning_star_minimum_die_and_glorious_retain_effective_threshold(self):
        source = make_pc_melee_scenario(weapon=PcMeleeWeapon.MORNING_STAR,max_rounds=2)
        member = source.party[0]
        source = replace(source,party=(replace(member,pc=replace(member.pc,weapon_skill=1),
            fate_policy=PcFatePolicy.CONFIGURED,glorious_policy=PcGloriousPolicy((Skill.MELEE,),0,0)),))
        result = execute(source,[10,10]+[1,1]+[10,10]+[1]+[10,1]+[10,10])
        first, second = attacks(result)
        self.assertEqual((first.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,
            first.proof.execution.resolution.attack.attacker_test.trace.threshold),(1,5))
        test = second.proof.execution.resolution.attack.attacker_test
        self.assertEqual((test.trace.rolled_dice,test.trace.threshold),(1,1))
        self.assertEqual((test.trace.initial_values,test.trace.final_values),((10,),(1,)))
        self.assertIsNotNone(second.proof.glorious)

    def test_pure_morning_star_help_penalty_survives_drained_and_removes_with_stagger(self):
        source = make_pc_melee_party_scenario(enemy_count=1)
        member = source.party[0]
        source = replace(source,party=(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.MORNING_STAR),
            policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
            help_policy=PcHelpPolicy('pc2',PcHelpTarget.MELEE_ATTACK,None)),source.party[1]))
        state = pure_active(source)
        for conditions in ((Condition.STAGGERED,),(Condition.STAGGERED,Condition.DRAINED)):
            with self.subTest(conditions=conditions):
                request = build_pc_help_action(pure_conditions(state,conditions))
                self.assertEqual(request.help_test.dice_modifiers,(DiceModifier(MORNING_STAR_STAGGERED_RULE_ID,-1),))
        self.assertEqual(build_pc_help_action(state).help_test.dice_modifiers,())

    def test_native_warhammer_help_has_no_enemy_target_bonus_and_fate_stays_bound(self):
        source = make_pc_melee_party_scenario(enemy_count=1,max_rounds=1)
        helper, beneficiary = source.party
        source = replace(source,party=(replace(helper,pc=replace(helper.pc,weapon=PcMeleeWeapon.WARHAMMER),
            policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
            help_policy=PcHelpPolicy('pc2',PcHelpTarget.MELEE_ATTACK,None),
            fate_policy=PcFatePolicy.CONFIGURED,glorious_policy=PcGloriousPolicy((Skill.MELEE,),0,0)),
            replace(beneficiary,pc=replace(beneficiary.pc,weapon=PcMeleeWeapon.DAGGER))))
        result = execute(source,[10]*3+[1]*3+[1]*6+[10,10])
        helper_step, = (step for step in result.steps if isinstance(step.proof,PcHelpProof))
        self.assertEqual(helper_step.proof.request.help_test.dice_modifiers,())
        self.assertEqual(helper_step.proof.execution.help_test_result.trace.rolled_dice,3)
        self.assertIsNotNone(helper_step.proof.glorious)
        self.assertEqual(len(result.state.participant('pc1').fate.spends),1)
        self.assertEqual(len(result.state.participant('pc2').fate.spends),0)
        self.assertEqual(attacks(result,'pc2')[0].proof.execution.resolution.attack.impact_spec.damage.base,2)
        # Pure boundary: even an enemy already Staggered is not a target of this own Help Test.
        state = helper_step.source
        enemy = state.enemies[0]
        state = replace(state,enemies=(replace(enemy,state=replace(enemy.state,
            injury=replace(enemy.state.injury,conditions=ConditionState(frozenset({Condition.STAGGERED}))))),))
        self.assertEqual(build_pc_help_action(state).help_test.dice_modifiers,())

    def test_native_morning_star_penalises_own_help_after_actual_stagger(self):
        source = make_pc_melee_party_scenario(enemy_count=1,max_rounds=2)
        helper, beneficiary = source.party
        source = replace(source,party=(replace(helper,pc=replace(helper.pc,weapon=PcMeleeWeapon.MORNING_STAR),
            policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
            help_policy=PcHelpPolicy('pc2',PcHelpTarget.MELEE_ATTACK,None)),beneficiary))
        result = execute(source,[10]*3+[10]*4+[1,1]+[1,10]+[1,10,10]
            +[1]*2+[1]*6+[10,10])
        first, second = tuple(step for step in result.steps if isinstance(step.proof,PcHelpProof))
        self.assertEqual(first.proof.request.help_test.dice_modifiers,())
        self.assertTrue(second.source.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(second.proof.request.help_test.dice_modifiers,
            (DiceModifier(MORNING_STAR_STAGGERED_RULE_ID,-1),))
        self.assertEqual(second.proof.execution.help_test_result.trace.rolled_dice,2)

    def test_native_all_new_one_handed_weapons_follow_heavy_hand_swap(self):
        for weapon in NEW_WEAPONS:
            with self.subTest(weapon=weapon):
                source = make_pc_melee_scenario(weapon=weapon,enemy_count=4,max_rounds=2)
                result = execute(source,heavy_prefix(16)+[10,10,10,1,1,1]
                    +[10,10,10,1,1]+[1,1,1]+[10,10,10,1,1,1]*4)
                self.assertEqual(tuple(step.proof for step in result.steps
                    if isinstance(step.proof,PcHandSwapProof)),
                    (PcHandSwapProof(PcWeaponHand.LEFT,PcWeaponHand.RIGHT),))
                self.assertIs(result.state.party[0].weapon_hand,PcWeaponHand.RIGHT)

    def test_native_all_new_weapons_drop_and_recover_in_healthy_hand(self):
        for weapon in NEW_WEAPONS:
            with self.subTest(weapon=weapon):
                source = make_pc_melee_scenario(weapon=weapon,enemy_count=3,max_rounds=2)
                result = execute(source,heavy_prefix(12)+[10,10,10,1,1,1]*3)
                self.assertEqual(sum(isinstance(step.proof,PcRecoverProof) for step in result.steps),1)
                self.assertIs(result.state.party[0].weapon_hand,PcWeaponHand.RIGHT)


if __name__ == '__main__':
    unittest.main()
