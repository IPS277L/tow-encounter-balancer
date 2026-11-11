"""Literal firearm volleys and source-bound focused Reload3/5 checks."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_handgun_scenarios import handgun_profile, make_pc_handgun_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.attack_models import AttackOutcome, MissConsequence
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_models import (
    PC_TWO_HANDED_RANGED_WEAPONS, PcFatePolicy, PcGloriousPolicy,
    PcMeleeWeapon, PcRepeaterBonusPolicy, PcTwoHandedGrip,
)
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcBackupWeaponDrawProof, PcMeleeOutcome, PcMeleeStep,
    build_pc_melee_attack, pc_melee_round_participants,
)
from towr.domain.pc_ranged_models import (
    PcRangedReloadProof, build_pc_ranged_reload, complete_pc_ranged_shot,
    prepare_pc_ranged_shot, ranged_reload_declaration,
)
from towr.domain.pc_short_opening_models import PcNpcApproachProof, PcRangedCloseUnsupported
from towr.domain.ranged_weapon_attack_preparation_models import OUTSIDE_OPTIMUM_RANGE_RULE_ID
from towr.domain.ranged_weapon_profiles import REPEATER_SHOOTING_BONUS_RULE_ID
from towr.domain.test_models import Skill, TestProfile, TestQuality
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionSlotRequest, CombatRoundAdvanceRequest, CombatTurnStartRequest,
)
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.reload_resolution import execute_reload_action
from towr.rules.turn_resolution import advance_combat_round, reserve_combat_action_slot, start_combat_turn


HANDGUN = PcMeleeWeapon.HANDGUN
REPEATER = PcMeleeWeapon.REPEATER_HANDGUN
WHEN = PcRepeaterBonusPolicy.WHEN_AVAILABLE
NEVER = PcRepeaterBonusPolicy.NEVER
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
    return tuple(step for step in steps(result, PcAttackProof) if step.proof.ranged_shot is not None)


def raw(step):
    return step.proof.execution.resolution.attack


def shot_values(weapon=HANDGUN, mode=None, *, hit=False):
    if weapon is HANDGUN:
        return [1,1,10,10] if hit else [10,10,1,1]
    if mode is WHEN:
        return [1,1,1,1,1,1,10,10] if hit else [10,10,10,10,10,10,1,1]
    return [1,1,1,10,10] if hit else [10,10,10,1,1]


def focused_next_pc_turn(result):
    """Alternative own action after a real volley, not fresh automatic tactics."""
    state = result.state
    advanced = advance_combat_round(CombatRoundAdvanceRequest('focused:advance',
        state.round_state, pc_melee_round_participants(state))).state
    started = start_combat_turn(CombatTurnStartRequest('focused:pc1:start', advanced, 'pc1')).state
    return replace(state, round_state=started)


class PcHandgunTests(unittest.TestCase):
    def test_hit_or_miss_spends_exact_three_or_five_cycle_only_when_selected(self):
        self.assertIn(HANDGUN, PC_TWO_HANDED_RANGED_WEAPONS)
        self.assertIn(REPEATER, PC_TWO_HANDED_RANGED_WEAPONS)
        for weapon, mode, target in ((HANDGUN,None,3),(REPEATER,WHEN,5),(REPEATER,NEVER,None)):
            for hit in (False, True):
                with self.subTest(weapon=weapon, mode=mode, hit=hit):
                    source = make_pc_handgun_scenario(weapon=weapon, repeater_bonus_policy=mode,
                        max_rounds=1, npc_toughness=20)
                    result = execute(source, shot_values(weapon,mode,hit=hit)+NPC_MISS)
                    shot, = shots(result)
                    self.assertIs(raw(shot).outcome, AttackOutcome.HIT if hit else AttackOutcome.MISS)
                    self.assertIs(raw(shot).miss_consequence, MissConsequence.NONE)
                    owner = shot.state.participant('pc1').ranged
                    preparation = shot.proof.ranged_shot.preparation.source_request
                    self.assertEqual(preparation.uses_optional_reload_bonus, mode is WHEN)
                    self.assertTrue(preparation.has_blackpowder_lore)
                    self.assertEqual(owner.loaded, target is None)
                    if target is None:
                        self.assertEqual(owner, shot.source.participant('pc1').ranged)
                        self.assertEqual(owner.reload_cycle_ids, ())
                        self.assertIsNone(owner.exacting)
                        self.assertIsNone(preparation.next_reload_cycle_id)
                    else:
                        self.assertEqual(owner.required_successes, target)
                        self.assertEqual(owner.reload_cycle_ids, (preparation.next_reload_cycle_id,))
                        self.assertEqual(owner.exacting.accumulated_successes, 0)
                    self.assertEqual(steps(result, PcRangedReloadProof), ())
                    self.assertEqual(result.executed_actions, 2)

    def test_short_range_penalty_and_damage_five_ignore_armour_without_crossbow_trait(self):
        for weapon, mode, dice in ((HANDGUN,None,2),(REPEATER,WHEN,6),(REPEATER,NEVER,3)):
            with self.subTest(weapon=weapon, mode=mode):
                source = make_pc_handgun_scenario(weapon=weapon, repeater_bonus_policy=mode,
                    max_rounds=1, npc_toughness=20, npc_armour_bonus=3, npc_armoured=True)
                result = execute(source, [1]+[10]*(dice-1)+[10,10]+NPC_MISS)
                shot, = shots(result)
                attack = raw(shot)
                self.assertEqual(attack.attacker_test.trace.rolled_dice, dice)
                penalty = tuple(modifier.amount for modifier in shot.proof.request.kernel_request.attack.attacker_test.dice_modifiers
                    if modifier.rule_id == OUTSIDE_OPTIMUM_RANGE_RULE_ID)
                self.assertEqual(penalty, (-1,) if weapon is HANDGUN else ())
                self.assertEqual(attack.impact_spec.damage.base, 5)
                self.assertTrue(attack.impact_spec.ignores_armour)
                self.assertEqual(attack.effective_resilience, 20)
                self.assertEqual(attack.impact_spec.damage_modifiers, ())
                self.assertEqual(attack.damage, 6)

    def test_minimum_pool_requires_exact_one_after_handgun_short_penalty(self):
        for value, outcome in ((1,AttackOutcome.HIT),(2,AttackOutcome.MISS)):
            source = make_pc_handgun_scenario(ballistic_skill=1, max_rounds=1, npc_toughness=20)
            result = execute(source, [value,10,10]+NPC_MISS)
            shot, = shots(result)
            trace = raw(shot).attacker_test.trace
            self.assertEqual((trace.base_dice,trace.regular_dice_delta,trace.rolled_dice), (1,-1,1))
            self.assertIs(raw(shot).outcome, outcome)
            self.assertEqual(shot.state.party[0].ranged.required_successes, 3)

    def test_drained_retains_handgun_penalty_and_declines_repeater_bonus_and_cycle(self):
        for weapon, mode, values in ((HANDGUN,None,[1,1,10,10]),(REPEATER,WHEN,[1,1,1,10,10])):
            source = make_pc_handgun_scenario(weapon=weapon, repeater_bonus_policy=mode,
                max_rounds=1, npc_toughness=20, npc_armour_bonus=3, npc_armoured=True)
            result = execute(source, shot_values(weapon,mode)+NPC_MISS)
            state = shots(result)[0].source
            member = state.party[0]
            state = replace(state, party=(replace(member, injury=replace(member.injury,
                conditions=member.injury.conditions.with_condition(Condition.DRAINED))),))
            request, _ = build_pc_melee_attack(state)
            test = request.kernel_request.attack.attacker_test
            self.assertFalse(any(modifier.amount > 0 for modifier in test.dice_modifiers))
            penalty = tuple(modifier.amount for modifier in test.dice_modifiers
                if modifier.rule_id == OUTSIDE_OPTIMUM_RANGE_RULE_ID)
            self.assertEqual(penalty, (-1,) if weapon is HANDGUN else ())
            rng = ScriptedD10(values)
            execution = execute_attack_action(request, rng)
            rng.assert_exhausted()
            proof = complete_pc_ranged_shot(state, request, request, execution)
            self.assertFalse(proof.preparation.source_request.uses_optional_reload_bonus)
            self.assertTrue(request.kernel_request.attack.impact_spec.ignores_armour)
            self.assertEqual(request.kernel_request.attack.impact_spec.damage_modifiers, ())
            if weapon is HANDGUN:
                self.assertFalse(proof.execution.weapon_state.loaded)
                self.assertEqual(proof.execution.weapon_state.required_successes, 3)
            else:
                self.assertTrue(proof.execution.weapon_state.loaded)
                self.assertEqual(proof.execution.weapon_state.reload_cycle_ids, ())
                self.assertIsNone(proof.preparation.source_request.next_reload_cycle_id)

    def test_clipped_plus_three_choice_precedes_glorious_and_still_spends_five(self):
        source = make_pc_handgun_scenario(weapon=REPEATER, repeater_bonus_policy=WHEN,
            ballistic_skill=1, max_rounds=1, npc_toughness=20)
        source = replace(source, party=(replace(source.party[0], fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.SHOOTING,),0,0)),))
        result = execute(source, [10,10,1,1,10,10]+NPC_MISS)
        shot, = shots(result)
        trace = raw(shot).attacker_test.trace
        self.assertEqual((trace.base_dice,trace.regular_dice_delta,trace.pool_cap,trace.rolled_dice), (1,3,2,2))
        self.assertIs(trace.quality, TestQuality.GLORIOUS)
        self.assertEqual((trace.initial_values,trace.final_values), ((10,10),(1,1)))
        modifier, = tuple(modifier for modifier in shot.proof.request.kernel_request.attack.attacker_test.dice_modifiers
            if modifier.rule_id == REPEATER_SHOOTING_BONUS_RULE_ID)
        self.assertEqual(modifier.amount, 3)
        self.assertFalse(modifier.bypasses_pool_cap)
        self.assertTrue(shot.proof.ranged_shot.preparation.source_request.uses_optional_reload_bonus)
        self.assertEqual(result.state.party[0].ranged.required_successes, 5)

    def test_real_approach_draw_keeps_charge_history_and_melee_has_no_firearm_traits(self):
        for weapon, mode, loaded in ((HANDGUN,None,False),(REPEATER,WHEN,False),(REPEATER,NEVER,True)):
            source = make_pc_handgun_scenario(weapon=weapon, repeater_bonus_policy=mode,
                max_rounds=2, npc_armoured=True)
            result = execute(source, shot_values(weapon,mode)+NPC_MISS+SWORD_HIT)
            draw, = steps(result, PcBackupWeaponDrawProof)
            self.assertEqual(draw.source.round_state.active_turn.actor_id, 'pc1')
            self.assertEqual(draw.source.round_state.round_number, 2)
            self.assertIs(draw.source.party[0].weapon_hand, PcTwoHandedGrip.BOTH)
            owner = draw.source.party[0].ranged
            self.assertEqual(owner.loaded, loaded)
            self.assertEqual(owner, draw.state.party[0].ranged)
            self.assertEqual(owner, result.state.party[0].ranged)
            self.assertEqual(steps(result, PcRangedReloadProof), ())
            self.assertEqual(len(steps(result, PcNpcApproachProof)), 1)
            melee = steps(result, PcAttackProof)[-1]
            self.assertIsNone(melee.proof.ranged_shot)
            self.assertEqual(raw(melee).impact_spec.damage.base, 3)
            self.assertFalse(raw(melee).impact_spec.ignores_armour)
            self.assertEqual(raw(melee).impact_spec.damage_modifiers, ())
            self.assertFalse(any(modifier.rule_id == REPEATER_SHOOTING_BONUS_RULE_ID
                for modifier in melee.proof.request.kernel_request.attack.attacker_test.dice_modifiers))
            self.assertIs(result.outcome, PcMeleeOutcome.OBJECTIVE_ACHIEVED)
            self.assertEqual(result.executed_actions, 3)

    def test_no_backup_stop_is_neutral_close_boundary_with_no_fake_wound(self):
        for weapon, mode in ((HANDGUN,None),(REPEATER,WHEN),(REPEATER,NEVER)):
            source = make_pc_handgun_scenario(weapon=weapon, repeater_bonus_policy=mode,
                backup=False, max_rounds=3)
            result = execute(source, shot_values(weapon,mode)+NPC_MISS)
            self.assertIs(result.outcome, PcMeleeOutcome.UNSUPPORTED_PATH)
            self.assertIs(type(result.unsupported), PcRangedCloseUnsupported)
            self.assertEqual(result.unsupported.reason, 'ranged_close_enemy')
            self.assertTrue(result.unsupported.source_id.endswith(':ranged:close'))
            self.assertEqual(result.unsupported.actor_id, 'pc1')
            self.assertEqual(result.unsupported.round_number, 2)
            self.assertEqual(result.unsupported.close_enemy_ids, ('minion1',))
            for change in ({'reason':'bow_close_enemy'}, {'reason':None},
                    {'close_enemy_ids':()}, {'round_number':True}, {'actor_id':None}):
                with self.assertRaises((TypeError,ValueError)):
                    replace(result.unsupported, **change)
            self.assertEqual(result.executed_actions, 2)
            self.assertEqual(result.state.round_state.round_number, 2)
            self.assertEqual(result.state.round_state.active_turn.action_slots, ())
            self.assertEqual(result.state.party[0].injury.wounds, ())
            self.assertFalse(hasattr(result.unsupported, 'wound_sequence'))
            self.assertEqual(steps(result, PcRangedReloadProof), ())

    def test_exact_preparation_identity_replay_and_profile_modifiers_are_bound(self):
        for weapon, mode in ((HANDGUN,None),(REPEATER,WHEN)):
            source = make_pc_handgun_scenario(weapon=weapon, repeater_bonus_policy=mode,
                max_rounds=1, npc_toughness=20)
            result = execute(source, shot_values(weapon,mode)+NPC_MISS)
            shot, = shots(result)
            self.assertEqual(apply_pc_melee_step(shot.source, shot), shot.state)
            with self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(shot.source, replace(shot.proof, ranged_shot=None))
            with self.assertRaises((TypeError,ValueError)):
                apply_pc_melee_step(shot.state, shot)
            proof = deepcopy(shot.proof)
            object.__setattr__(proof.ranged_shot.preparation.source_request.weapon_state,
                'weapon_instance_id', 'foreign:weapon')
            with self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(shot.source, proof)
            request = shot.proof.request
            kernel = request.kernel_request
            test = kernel.attack.attacker_test
            bad_modifiers = test.dice_modifiers*2
            with self.assertRaises((TypeError,ValueError)):
                prepare_pc_ranged_shot(shot.source, replace(request,
                    kernel_request=replace(kernel, attack=replace(kernel.attack,
                        attacker_test=replace(test, dice_modifiers=bad_modifiers)))))

    def test_focused_reload_binds_actual_three_or_five_and_explicit_dexterity(self):
        for weapon, mode, target, values in ((HANDGUN,None,3,[1,1,1,10]),
                (REPEATER,WHEN,5,[1,1,1,1])):
            source = make_pc_handgun_scenario(weapon=weapon, repeater_bonus_policy=mode,
                max_rounds=1, initiative=4, dexterity=5)
            result = execute(source, shot_values(weapon,mode)+NPC_MISS)
            state = focused_next_pc_turn(result)
            declaration = ranged_reload_declaration(state,'pc1')
            clock = reserve_combat_action_slot(CombatActionSlotRequest('focused:reserve',
                state.round_state,'pc1',declaration,ActionSlotGrant.STANDARD)).state
            state = replace(state, round_state=clock)
            request = build_pc_ranged_reload(state)
            self.assertIs(request.weapon_state, state.party[0].ranged)
            self.assertEqual(request.weapon_state.required_successes, target)
            self.assertEqual(request.dexterity_test.profile, TestProfile(4,5))
            rng = ScriptedD10(values)
            reloaded = execute_reload_action(request, rng)
            rng.assert_exhausted()
            self.assertEqual(reloaded.completed, weapon is HANDGUN)
            self.assertEqual(reloaded.state.loaded, weapon is HANDGUN)
            self.assertEqual(reloaded.state.exacting.accumulated_successes,
                3 if weapon is HANDGUN else 4)
            self.assertEqual(reloaded.state.reload_cycle_id, state.party[0].ranged.reload_cycle_id)
            self.assertEqual(reloaded.state.reload_cycle_ids, state.party[0].ranged.reload_cycle_ids)
            self.assertTrue(reloaded.slot.executed)
            with self.assertRaises((TypeError,ValueError)):
                replace(request.weapon_state, required_successes=5 if target == 3 else 3)

    def test_two_actors_own_distinct_regular_empty_and_repeater_loaded_states(self):
        source = make_pc_handgun_scenario(pc_count=2, enemy_count=2, max_rounds=1)
        first, second = source.party
        second = replace(second, pc=replace(second.pc, weapon=REPEATER,
            ranged=handgun_profile(weapon=REPEATER, repeater_bonus_policy=NEVER)))
        source = replace(source, party=(first,second))
        result = execute(source, shot_values()+shot_values(REPEATER,NEVER)+NPC_MISS*2)
        a, b = (member.ranged for member in result.state.party)
        self.assertNotEqual(a.weapon_instance_id, b.weapon_instance_id)
        self.assertIsNot(a,b)
        self.assertFalse(a.loaded)
        self.assertEqual(a.required_successes, 3)
        self.assertEqual(len(a.reload_cycle_ids), 1)
        self.assertTrue(b.loaded)
        self.assertEqual(b.reload_cycle_ids, ())


if __name__ == '__main__':
    unittest.main()
