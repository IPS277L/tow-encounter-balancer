"""Actual finite Net throws, retained equipment, and source-bound Burdened."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.attack_models import AttackOutcome, ConditionImpactSpec, MissConsequence
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcAttackerStaggerProof, PcMinionStaggerDefeatProof,
    PcMeleeOutcome, PcMeleeStep, PcNpcHelpProof, PcRecoverProof, PcTurnEndProof,
    PcWoundCompletionProof,
)
from towr.domain.pc_net_models import PcNpcNetDrawProof, net_stock_and_held
from towr.domain.pc_npc_help_models import HORDE_HELP_RULE_ID, PcNpcHelpPolicy
from towr.domain.pc_npc_net_policy_models import PcNpcNetMode, PcNpcNetPolicy, NET_RULE_ID
from towr.domain.test_models import Skill
from towr.domain.turn_models import CombatTurnEndRequest
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario
from towr.rules.turn_resolution import end_combat_turn


ACTOR = 'net_goblin1'
PC_MISS = [10]*3+[1]*3
NET_HIT = [1]*2+[10]*3
NET_MISS = [10]*2+[1]*3
SPEAR_MISS = [10]*2+[1]*3


def scene(*, pcs=1, rounds=1, mode=PcNpcNetMode.THROW_ONCE_THEN_SPEAR, **counts):
    source = book_pc_scenario(net_goblins=counts.pop('net_goblins', 1),
        footpads=counts.pop('footpads', 0), townsfolk=0,
        pc_count=pcs, max_rounds=rounds, **counts)
    return replace(source, facts=replace(source.facts, outnumbering_bonus_approved=False),
        npc_net_policies=tuple(PcNpcNetPolicy(p.actor_id, 1, mode)
            for p in source.npc_net_policies))


def execute(source, values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source, rng)
    rng.assert_exhausted()
    return result


def steps(result, kind):
    return tuple(step for step in result.steps if type(step.proof) is kind)


def incoming(result, actor=ACTOR):
    return tuple(step for step in steps(result, PcAttackProof)
        if step.proof.request.actor_id == actor)


class PcNetExecutionTests(unittest.TestCase):
    def test_hit_is_primary_burdened_without_damage_stagger_or_wound(self):
        result = execute(scene(), PC_MISS+NET_HIT)
        attack, = incoming(result)
        raw = attack.proof.execution.resolution.attack
        self.assertIs(raw.outcome, AttackOutcome.HIT)
        self.assertIs(type(raw.impact_spec), ConditionImpactSpec)
        self.assertIs(raw.impact_spec.condition, Condition.BURDENED)
        self.assertEqual(raw.impact_spec.rule_id, NET_RULE_ID)
        self.assertIsNone(raw.damage)
        self.assertIsNone(raw.effective_resilience)
        self.assertIsNone(raw.impact)
        self.assertIsNone(attack.proof.execution.resolution.stagger)
        self.assertIsNone(attack.proof.execution.resolution.pending_character_wound)
        before = attack.source.participant('pc1')
        after = attack.state.participant('pc1')
        self.assertEqual(after.injury.wounds, before.injury.wounds)
        self.assertEqual(after.injury.conditions.conditions,
            before.injury.conditions.conditions | {Condition.BURDENED})
        cause, = after.net_condition_sources
        self.assertEqual((cause.attacker_id, cause.target_id, cause.rule_id),
            (ACTOR, 'pc1', NET_RULE_ID))
        self.assertEqual(cause.attack_id, attack.proof.request.id)
        self.assertEqual(result.executed_actions, 2)
        self.assertEqual(len(steps(result, PcWoundCompletionProof)), 0)

    def test_throwing_uses_printed_two_dice_cap_six_and_athletics(self):
        result = execute(scene(), PC_MISS+NET_HIT)
        attack, = incoming(result)
        trace = attack.proof.execution.resolution.attack.attacker_test.trace
        self.assertEqual((trace.base_dice, trace.threshold, trace.pool_cap,
            trace.rolled_dice), (2, 3, 6, 2))
        protection = attack.proof.protection.source_request
        self.assertIs(protection.attack_skill, Skill.THROWING)
        self.assertIs(protection.selected_skill, Skill.ATHLETICS)

    def test_throwing_does_not_inherit_melee_outnumbering_or_prone_higher_ground(self):
        source = scene(footpads=1)
        source = replace(source, facts=replace(source.facts, outnumbering_bonus_approved=True),
            enemy_activation_order=('footpad1', ACTOR))
        result = execute(source, PC_MISS+[1]*4+[10]*3+[9]+NET_HIT)
        attack, = incoming(result)
        self.assertTrue(attack.source.participant('pc1').injury.conditions.has(Condition.PRONE))
        trace = attack.proof.execution.resolution.attack.attacker_test.trace
        self.assertEqual((trace.base_dice, trace.regular_dice_delta, trace.rolled_dice), (2, 0, 2))
        self.assertEqual(attack.proof.request.kernel_request.attack.attacker_test.dice_modifiers, ())

    def test_miss_spends_net_then_finishes_own_close_stagger_before_free_draw(self):
        result = execute(scene(), PC_MISS+NET_MISS)
        attack, = incoming(result)
        self.assertIs(attack.proof.execution.resolution.attack.outcome, AttackOutcome.MISS)
        self.assertIs(attack.proof.execution.resolution.attack.miss_consequence,
            MissConsequence.STAGGER_ATTACKER)
        self.assertFalse(attack.state.participant('pc1').injury.conditions.has(Condition.BURDENED))
        self.assertEqual(attack.state.participant('pc1').net_condition_sources, ())
        stagger, = tuple(step for step in steps(result, PcAttackerStaggerProof)
            if step.source.round_state.active_turn.actor_id == ACTOR)
        draw, = steps(result, PcNpcNetDrawProof)
        self.assertLess(result.steps.index(attack), result.steps.index(stagger))
        self.assertLess(result.steps.index(stagger), result.steps.index(draw))
        self.assertTrue(draw.state.enemy(ACTOR).state.injury.conditions.has(Condition.STAGGERED))
        self.assertFalse(draw.state.enemy(ACTOR).state.injury.defeated)

    def test_both_outcomes_require_draw_spear_and_cannot_skip_end_transition(self):
        for rolls in (NET_HIT, NET_MISS):
            with self.subTest(rolls=rolls):
                result = execute(scene(), PC_MISS+rolls)
                attack, = incoming(result)
                spent = attack.state.enemy(ACTOR).state
                self.assertEqual(spent.available_attack_ids, ('jagged_spear',))
                self.assertFalse(spent.wields_weapon)
                self.assertEqual(net_stock_and_held(attack.state, ACTOR), (0, None))
                draw, = steps(result, PcNpcNetDrawProof)
                self.assertEqual((draw.proof.actor_id, draw.proof.attack_id), (ACTOR, 'jagged_spear'))
                self.assertTrue(draw.state.enemy(ACTOR).state.wields_weapon)
                self.assertEqual(net_stock_and_held(draw.state, ACTOR), (0, 'jagged_spear'))
                self.assertEqual(draw.state.enemy(ACTOR).state.available_attack_ids, ('jagged_spear',))
                clock = draw.source.round_state
                end = end_combat_turn(CombatTurnEndRequest('pc-melee:r1:net_goblin1:end', clock, ACTOR))
                with self.assertRaises((TypeError, ValueError)):
                    PcMeleeStep(draw.source, PcTurnEndProof(end, None))

    def test_net_stays_spent_across_rounds_and_burdened_does_not_change_pc_attack(self):
        result = execute(scene(rounds=3), PC_MISS+NET_HIT+(PC_MISS+SPEAR_MISS)*2)
        attacks = incoming(result)
        self.assertEqual(tuple(s.proof.protection.source_request.attack_skill for s in attacks),
            (Skill.THROWING, Skill.MELEE, Skill.MELEE))
        self.assertEqual(len(steps(result, PcNpcNetDrawProof)), 1)
        self.assertEqual(steps(result, PcRecoverProof), ())
        pc_attacks = tuple(s for s in steps(result, PcAttackProof)
            if s.proof.request.actor_id == 'pc1')
        self.assertEqual(tuple(s.proof.execution.resolution.attack.attacker_test.trace.rolled_dice
            for s in pc_attacks), (3, 3, 3))
        self.assertTrue(pc_attacks[-1].source.participant('pc1').injury.conditions.has(Condition.BURDENED))
        self.assertEqual(result.state.enemy(ACTOR).state.available_attack_ids, ('jagged_spear',))

    def test_explicit_spear_only_draws_before_attack_and_preserves_unused_net(self):
        result = execute(scene(mode=PcNpcNetMode.SPEAR_ONLY), PC_MISS+SPEAR_MISS)
        draw, = steps(result, PcNpcNetDrawProof)
        attack, = incoming(result)
        self.assertLess(result.steps.index(draw), result.steps.index(attack))
        self.assertEqual(draw.proof.attack_id, 'jagged_spear')
        self.assertIs(attack.proof.protection.source_request.attack_skill, Skill.MELEE)
        self.assertIn('weighted_net', result.state.enemy(ACTOR).state.available_attack_ids)
        self.assertEqual(net_stock_and_held(result.state, ACTOR), (1, 'jagged_spear'))
        self.assertEqual(result.state.participant('pc1').net_condition_sources, ())

    def test_already_burdened_target_selects_spear_and_retains_second_net(self):
        result = execute(scene(net_goblins=2), PC_MISS+NET_HIT+SPEAR_MISS)
        first, = incoming(result)
        second, = incoming(result, 'net_goblin2')
        self.assertIs(first.proof.protection.source_request.attack_skill, Skill.THROWING)
        self.assertTrue(second.source.participant('pc1').injury.conditions.has(Condition.BURDENED))
        self.assertIs(second.proof.protection.source_request.attack_skill, Skill.MELEE)
        self.assertIn('weighted_net', result.state.enemy('net_goblin2').state.available_attack_ids)
        self.assertEqual(len(result.state.participant('pc1').net_condition_sources), 1)

    def test_actual_defenceless_target_uses_spear_and_preserves_unthrown_net(self):
        source = replace(scene(pcs=2, footpads=1, minotaurs=2),
            enemy_activation_order=('footpad1', 'minotaur1', 'minotaur2', ACTOR))
        # The actual Wound queue removes both arms before this Goblin acts.
        prefix = (PC_MISS*2+[1]*3+[10]*3+[1]
            +[1]*4+[10]*3+[10, 9, 1]+[1]
            +[1]*4+[10, 8, 1, 1])
        result = execute(source, prefix+[10]*2)
        attack, = incoming(result)
        self.assertTrue(attack.source.participant('pc1').injury.conditions.has(Condition.DEFENCELESS))
        self.assertFalse(attack.source.participant('pc1').injury.dead)
        self.assertIs(attack.proof.protection.source_request.attack_skill, Skill.MELEE)
        self.assertIsNone(attack.proof.protection.source_request.selected_skill)
        self.assertIsNone(attack.proof.execution.resolution.attack.defender_test)
        self.assertEqual(net_stock_and_held(result.state, ACTOR), (1, 'jagged_spear'))
        self.assertEqual(result.state.participant('pc1').net_condition_sources, ())

    def test_retained_net_can_be_redrawn_for_next_live_unburdened_priority_target(self):
        source = replace(scene(pcs=2, rounds=2, net_goblins=2, footpads=3),
            enemy_activation_order=(ACTOR, 'net_goblin2', 'footpad1', 'footpad2', 'footpad3'))
        # Goblin2 preserves its Net against Burdened pc1. Three later Wounds
        # kill pc1, so the next round's live priority target is unburdened pc2.
        result = execute(source, PC_MISS*2+NET_HIT+SPEAR_MISS
            +[1]*3+[10]*3+[1]+[1]*3+[10]*3+[1, 1]
            +[1]*3+[10]*3+[10]*3
            +PC_MISS+SPEAR_MISS+NET_HIT+([10]*3+[1]*3)*3)
        first, second = incoming(result, 'net_goblin2')
        self.assertEqual((first.proof.request.target_id, second.proof.request.target_id), ('pc1', 'pc2'))
        self.assertIs(first.proof.protection.source_request.attack_skill, Skill.MELEE)
        self.assertIs(second.proof.protection.source_request.attack_skill, Skill.THROWING)
        self.assertTrue(second.source.participant('pc1').injury.dead)
        self.assertFalse(second.source.participant('pc2').injury.conditions.has(Condition.BURDENED))
        draws = tuple(step.proof.attack_id for step in steps(result, PcNpcNetDrawProof)
            if step.proof.actor_id == 'net_goblin2')
        self.assertEqual(draws, ('jagged_spear', 'weighted_net', 'jagged_spear'))
        self.assertEqual(net_stock_and_held(result.state, 'net_goblin2'), (0, 'jagged_spear'))
        self.assertTrue(result.state.participant('pc2').injury.conditions.has(Condition.BURDENED))

    def test_standard_recover_removes_real_hit_prone_but_keeps_net_cause(self):
        result = execute(scene(rounds=2, footpads=1), PC_MISS+NET_HIT
            +[1]*3+[10]*3+[9]+SPEAR_MISS+[10]*3+[1]*3)
        recover, = steps(result, PcRecoverProof)
        before = recover.source.participant('pc1')
        after = recover.state.participant('pc1')
        self.assertTrue(before.injury.conditions.has(Condition.PRONE))
        self.assertFalse(after.injury.conditions.has(Condition.PRONE))
        self.assertTrue(after.injury.conditions.has(Condition.BURDENED))
        self.assertEqual(after.net_condition_sources, before.net_condition_sources)
        self.assertEqual(len(after.net_condition_sources), 1)

    def test_later_wound_and_timed_expiry_keep_net_cause(self):
        source = scene(rounds=2, footpads=1)
        # Net HIT, then Gash Brow7 and failed Endurance. The independent
        # Blinded effect expires at the PC's next turn end.
        result = execute(source, PC_MISS+NET_HIT
            +[1]*3+[10]*3+[7]+[10]*3+PC_MISS+SPEAR_MISS+[10]*3+[1]*3)
        net, = tuple(step for step in incoming(result)
            if step.proof.protection.source_request.attack_skill is Skill.THROWING)
        cause = net.state.participant('pc1').net_condition_sources
        wound, = steps(result, PcWoundCompletionProof)
        self.assertEqual(wound.state.participant('pc1').net_condition_sources, cause)
        pc_attack = tuple(step for step in steps(result, PcAttackProof)
            if step.proof.request.actor_id == 'pc1')[-1]
        self.assertTrue(pc_attack.source.participant('pc1').injury.conditions.has(Condition.BLINDED))
        self.assertEqual(pc_attack.state.participant('pc1').net_condition_sources, cause)
        member = result.state.participant('pc1')
        self.assertFalse(member.injury.conditions.has(Condition.BLINDED))
        self.assertTrue(member.injury.conditions.has(Condition.BURDENED))
        self.assertEqual(member.net_condition_sources, cause)
        self.assertEqual(member.timed_wounds, ())

    def test_replay_changed_actor_and_equal_string_aliases_cannot_spend_or_draw(self):
        result = execute(scene(), PC_MISS+NET_HIT)
        attack, = incoming(result)
        draw, = steps(result, PcNpcNetDrawProof)
        for step in (attack, draw):
            with self.subTest(proof=type(step.proof).__name__), self.assertRaises((TypeError, ValueError)):
                apply_pc_melee_step(step.state, step)
        for changes in ({'actor_id':'another-npc'}, {'attack_id':'weighted_net'}, {'action_id':'another-action'}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                PcMeleeStep(draw.source, replace(draw.proof, **changes))
        class IdAlias(str):
            pass
        forged = deepcopy(attack.proof)
        object.__setattr__(forged.request, 'actor_id', IdAlias(ACTOR))
        with self.assertRaises((TypeError, ValueError)):
            PcMeleeStep(attack.source, forged)
        forged = deepcopy(draw.proof)
        object.__setattr__(forged, 'actor_id', IdAlias(ACTOR))
        with self.assertRaises((TypeError, ValueError)):
            PcMeleeStep(draw.source, forged)

    def test_fresh_equipment_or_erased_receipt_cannot_restore_spent_stock(self):
        result = execute(scene(), PC_MISS+NET_HIT)
        attack, = incoming(result)
        fresh = scene().enemy(ACTOR)
        with self.assertRaises((TypeError, ValueError)):
            replace(attack.state, enemies=(fresh,))
        with self.assertRaises((TypeError, ValueError)):
            replace(attack.state, history=())

    def test_cause_cannot_be_removed_reassigned_duplicated_or_replaced_by_alias(self):
        result = execute(scene(), PC_MISS+NET_HIT)
        attack, = incoming(result)
        member = attack.state.participant('pc1')
        cause, = member.net_condition_sources
        for sources in ((), (cause, cause), (replace(cause, attack_id='another-attack'),)):
            with self.subTest(sources=sources), self.assertRaises((TypeError, ValueError)):
                replace(attack.state, party=(replace(member, net_condition_sources=sources),))
        with self.assertRaises((TypeError, ValueError)):
            replace(member, injury=replace(member.injury,
                conditions=member.injury.conditions.without_condition(Condition.BURDENED)))
        class IdAlias(str):
            pass
        forged = deepcopy(result)
        object.__setattr__(forged.state.participant('pc1').net_condition_sources[0],
            'attack_id', IdAlias(cause.attack_id))
        with self.assertRaises((TypeError, ValueError)):
            replace(forged)

    def test_dirty_coward_still_defeats_repeated_incoming_stagger_before_net_throw(self):
        source = scene(pcs=2)
        source = replace(source, party=tuple(replace(member,
            pc=replace(member.pc, strength=2)) for member in source.party))
        result = execute(source, ([1, 10, 10]+[10]*3)*2)
        defeat, = steps(result, PcMinionStaggerDefeatProof)
        self.assertEqual(defeat.proof.source.target_id, ACTOR)
        self.assertEqual(result.state.enemy(ACTOR).state.injury.wounds, 0)
        self.assertTrue(result.state.enemy(ACTOR).state.injury.defeated)
        self.assertEqual(incoming(result), ())
        self.assertEqual(steps(result, PcNpcNetDrawProof), ())

    def test_net_holder_horde_help_has_priority_and_does_not_spend_net(self):
        source = replace(scene(goblins=1), enemy_activation_order=(ACTOR, 'goblin1'),
            npc_help_policies=(PcNpcHelpPolicy(ACTOR, 'goblin1'),))
        result = execute(source, PC_MISS+[10]*3+[1]*3)
        help_step, = steps(result, PcNpcHelpProof)
        self.assertEqual(help_step.proof.request.actor_id, ACTOR)
        self.assertEqual(help_step.proof.request.source_rule_id, HORDE_HELP_RULE_ID)
        self.assertEqual(incoming(result), ())
        self.assertEqual(steps(result, PcNpcNetDrawProof), ())
        self.assertIn('weighted_net', result.state.enemy(ACTOR).state.available_attack_ids)
        beneficiary, = incoming(result, 'goblin1')
        self.assertEqual(len(beneficiary.proof.npc_help_applications), 1)

    def test_horde_helper_attacks_instead_of_binding_melee_help_to_throwing(self):
        source = replace(scene(goblins=1), enemy_activation_order=('goblin1', ACTOR),
            npc_help_policies=(PcNpcHelpPolicy('goblin1', ACTOR),))
        result = execute(source, PC_MISS+SPEAR_MISS+NET_HIT)
        self.assertEqual(steps(result, PcNpcHelpProof), ())
        attack, = incoming(result)
        self.assertEqual(attack.proof.npc_help_applications, ())
        self.assertEqual(attack.proof.execution.resolution.attack.attacker_test.trace.rolled_dice, 2)

    def test_spear_selection_allows_exact_future_melee_horde_binding(self):
        source = replace(scene(goblins=1, mode=PcNpcNetMode.SPEAR_ONLY),
            enemy_activation_order=('goblin1', ACTOR),
            npc_help_policies=(PcNpcHelpPolicy('goblin1', ACTOR),))
        result = execute(source, PC_MISS+[10]*3+[1]*3)
        help_step, = steps(result, PcNpcHelpProof)
        attack, = incoming(result)
        self.assertEqual(help_step.proof.request.beneficiary_id, ACTOR)
        self.assertEqual(len(attack.proof.npc_help_applications), 1)
        self.assertEqual(attack.proof.execution.resolution.attack.attacker_test.trace.rolled_dice, 3)
        self.assertIn('weighted_net', result.state.enemy(ACTOR).state.available_attack_ids)

    def test_unsupported_later_anatomy_keeps_actual_net_prefix_and_spent_stock(self):
        source = replace(scene(pcs=2, footpads=1, minotaurs=3),
            enemy_activation_order=(ACTOR, 'footpad1', 'minotaur1', 'minotaur2', 'minotaur3'))
        values = (PC_MISS*2+NET_HIT+[1]*3+[10]*3+[1]
            +[1]*4+[10]*3+[10, 9, 1]+[1]
            +[1]*4+[10, 8, 1, 1]+[1]*4+[3, 3, 2, 2, 2])
        result = execute(source, values)
        self.assertIs(result.outcome, PcMeleeOutcome.UNSUPPORTED_PATH)
        self.assertEqual((result.unsupported.actor_id, result.unsupported.reason),
            ('pc1', 'unavailable_anatomical_target'))
        self.assertTrue(result.state.pending)
        self.assertTrue(result.state.participant('pc1').injury.conditions.has(Condition.BURDENED))
        self.assertEqual(len(result.state.participant('pc1').net_condition_sources), 1)
        self.assertEqual(len(incoming(result)), 1)
        self.assertEqual(net_stock_and_held(result.state, ACTOR), (0, 'jagged_spear'))


if __name__ == '__main__':
    unittest.main()
