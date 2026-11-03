"""PC owner/source invariants: canonical K1 evidence and selected Fate policy."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10, blind_expiry_script, first_wound_script, run_first_wound
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcMeleeOutcome, PcMeleeStep,
    PcRecoverProof, PcWoundCompletionProof,
)
from towr.domain.recover_models import RecoverConditionChange
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario
from towr.rules.wound_lifecycle_resolution import roll_character_wound_lifecycle


def win_result():
    rng = ScriptedD10([1,1,1,10,10])
    result = run_pc_melee_scenario(make_pc_melee_scenario(),rng)
    rng.assert_exhausted()
    return result


def mixed_prone_drained_recover():
    source = make_pc_melee_scenario(max_rounds=3)
    values = first_wound_script(10)
    # Next PC Attack is Grim, then Wound5 from two Wounds dice and failed Endurance.
    values += [1,10,10,1,1,10, 1,1,10,10,10,2,3,10,10,10]
    # Next standard action is Recover (no dice); enemy then misses.
    values += [10,10,1,1,1]
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


class PcMeleeExecutionTests(unittest.TestCase):
    def test_complete_prefix_is_required_and_steps_are_applied_once(self):
        result = win_result()
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        step = result.steps[0]
        self.assertEqual(apply_pc_melee_step(step.source,step),step.state)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(step.state,step)
        for steps in (result.steps[1:],result.steps[:2]+result.steps[3:],tuple(reversed(result.steps))):
            with self.assertRaises(ValueError):
                replace(result,steps=steps)
        stale = replace(step.source,weapon_hand=None)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(stale,step)

    def test_forged_equal_bool_and_enum_test_trace_fields_are_refused(self):
        source = win_result()
        for name,value in (('success_delta',False),('quality','normal'),('minimum_die_rule_applied',0)):
            forged = deepcopy(source)
            proof = next(step.proof for step in forged.steps if isinstance(step.proof,PcAttackProof))
            object.__setattr__(proof.execution.resolution.attack.attacker_test.trace,name,value)
            with self.subTest(field=name), self.assertRaises(TypeError):
                replace(forged)

    def test_forged_attack_enum_and_owner_death_flag_are_refused(self):
        result = win_result()
        forged = deepcopy(result)
        attack = next(step.proof.execution.resolution.attack for step in forged.steps if isinstance(step.proof,PcAttackProof))
        object.__setattr__(attack,'outcome','hit')
        with self.assertRaises(TypeError):
            replace(forged)

    def test_equal_raw_weapon_hand_and_separate_damage_spec_leaf_are_refused(self):
        result = win_result()
        forged = deepcopy(result)
        object.__setattr__(forged.steps[-1].state,'weapon_hand','left')
        with self.assertRaises(TypeError):
            replace(forged)
        step = next(s for s in result.steps if isinstance(s.proof,PcAttackProof))
        proof = deepcopy(step.proof)
        attack = proof.execution.resolution.attack
        spec = deepcopy(attack.impact_spec)
        object.__setattr__(spec.resilience,'bonus',False)
        object.__setattr__(attack,'impact_spec',spec)
        with self.assertRaises(TypeError):
            PcMeleeStep(step.source,proof)

    def test_grim_reroll_indices_and_original_values_require_exact_integer_types(self):
        rng = ScriptedD10(blind_expiry_script())
        result = run_pc_melee_scenario(make_pc_melee_scenario(max_rounds=2),rng)
        rng.assert_exhausted()
        step = next(s for s in result.steps if isinstance(s.proof,PcAttackProof)
            and s.proof.execution.resolution.attack.attacker_test.trace.rerolls)
        for index,field in ((1,'index'),(0,'original')):
            proof = deepcopy(step.proof)
            reroll = proof.execution.resolution.attack.attacker_test.trace.rerolls[index]
            object.__setattr__(reroll,field,True)
            with self.subTest(field=field), self.assertRaises(TypeError):
                PcMeleeStep(step.source,proof)
        forged = deepcopy(result)
        object.__setattr__(forged.steps[-1].state.pc_injury,'dead',0)
        with self.assertRaises(TypeError):
            replace(forged)

    def test_forged_pending_wound_pool_is_rejected_even_if_the_roll_is_self_consistent(self):
        result = run_first_wound(1)
        step = next(s for s in result.steps if isinstance(s.proof,PcAttackProof)
            and s.proof.execution.resolution.pending_character_wound is not None)
        proof = step.proof
        original = proof.execution.resolution.pending_character_wound
        request = replace(original.source_request,wound=replace(original.source_request.wound,base_dice=3))
        forged_roll = roll_character_wound_lifecycle(request,ScriptedD10([10,10,10]))
        self.assertTrue(forged_roll.wound_result.state.dead)
        raw = replace(proof.execution.resolution,pending_character_wound=forged_roll,
            character_wound=forged_roll.wound_result,target_state=forged_roll.wound_result.state)
        forged = replace(proof,execution=replace(proof.execution,resolution=raw))
        with self.assertRaises(ValueError):
            PcMeleeStep(step.source,forged)

    def test_foreign_player_lifecycle_is_rejected_on_a_real_minion_hit(self):
        wound = run_first_wound(1)
        foreign = next(s.proof.execution.resolution.pending_character_wound for s in wound.steps
            if isinstance(s.proof,PcAttackProof) and s.proof.execution.resolution.pending_character_wound is not None)
        hit = next(s for s in win_result().steps if isinstance(s.proof,PcAttackProof))
        proof = replace(hit.proof,execution=replace(hit.proof.execution,
            resolution=replace(hit.proof.execution.resolution,pending_character_wound=foreign)))
        with self.assertRaises(ValueError):
            PcMeleeStep(hit.source,proof)

    def test_wrong_resolution_branch_is_refused(self):
        step = next(s for s in win_result().steps if isinstance(s.proof,PcAttackProof))
        raw = step.proof.execution.resolution
        for field in ('character_wound_completion','replacement_impact','monstrosity_impact'):
            forged = replace(step.proof,execution=replace(step.proof.execution,resolution=replace(raw,**{field:object()})))
            with self.subTest(field=field), self.assertRaises(ValueError):
                PcMeleeStep(step.source,forged)

    def test_nested_daily_registration_cannot_drop_its_actual_receipt(self):
        result = run_first_wound(1)
        step = next(s for s in result.steps if isinstance(s.proof,PcWoundCompletionProof))
        proof = deepcopy(step.proof)
        old_daily = step.source.daily_wounds
        object.__setattr__(proof.completion.daily_registration,'state',old_daily)
        object.__setattr__(proof.completion,'daily_wounds',old_daily)
        # The outer K1 object alone accepts these equal nested fields.
        replace(proof.completion)
        with self.assertRaises(ValueError):
            PcMeleeStep(step.source,proof)

    def test_nested_recover_cannot_remove_ongoing_crushed_rib_drained(self):
        result = mixed_prone_drained_recover()
        step = next(s for s in result.steps if isinstance(s.proof,PcRecoverProof))
        self.assertTrue(step.source.pc_injury.conditions.has(Condition.PRONE))
        self.assertTrue(step.source.pc_injury.conditions.has(Condition.DRAINED))
        self.assertFalse(step.state.pc_injury.conditions.has(Condition.PRONE))
        self.assertTrue(step.state.pc_injury.conditions.has(Condition.DRAINED))
        proof = deepcopy(step.proof)
        before = step.source.pc_injury.conditions
        removal = RecoverConditionChange('pc',before,
            before.without_condition(Condition.PRONE).without_condition(Condition.DRAINED),
            (Condition.PRONE,Condition.DRAINED))
        object.__setattr__(proof.result.resolution,'condition_changes',(removal,))
        replace(proof.result)
        with self.assertRaises(ValueError):
            PcMeleeStep(step.source,proof)

    def test_changed_fate_window_or_daily_source_is_refused(self):
        result = run_first_wound(1)
        step = next(s for s in result.steps if isinstance(s.proof,PcWoundCompletionProof))
        with self.assertRaises(ValueError):
            PcMeleeStep(step.source,replace(step.proof,fate_decline=replace(step.proof.fate_decline,source_id='foreign')))
        forged = deepcopy(result)
        object.__setattr__(forged.steps[-1].state.fate,'rating',True)
        with self.assertRaises((TypeError,ValueError)):
            replace(forged)

    def test_natural_one_die_uses_its_skill_and_sword_bonus_obeys_pc_cap(self):
        source = make_pc_melee_scenario(weapon=PcMeleeWeapon.SWORD,max_rounds=1)
        source = replace(source,pc=replace(source.pc,weapon_skill=1,strength=1,toughness=10))
        rng = ScriptedD10([5,1,10, 1,1,5,5])
        result = run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        attacks = [s.proof for s in result.steps if isinstance(s.proof,PcAttackProof)]
        own = attacks[0].execution.resolution.attack.attacker_test.trace
        protection = attacks[1].execution.resolution.attack.defender_test.trace
        self.assertEqual((own.rolled_dice,own.threshold,own.initial_values,own.successes),(1,5,(5,),1))
        self.assertFalse(own.minimum_die_rule_applied)
        self.assertEqual((protection.rolled_dice,protection.pool_cap),(2,2))
        self.assertEqual(protection.regular_dice_delta,1)


if __name__=='__main__':
    unittest.main()
