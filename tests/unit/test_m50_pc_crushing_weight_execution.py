"""Literal native histories prove early Prone, removable lifetime and real slot2."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_m28_pc_beast_orc_modifiers import pure_active
from towr.domain.attack_models import AttackOutcome, ImpactOutcome
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.injury_models import WoundConditionEffect, WoundEffectDuration
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.pc_melee_models import PcAllyRecoverPolicy, PcFatePolicy, PcMeleePolicy, PcMeleeWeapon, PcNearMissPolicy
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcEnduranceProof, PcMeleeOutcome, PcMeleeStep, PcRecoverProof,
    PcTurnEndProof, PcWoundCompletionProof, build_pc_melee_attack,
)
from towr.domain.pc_npc_extra_attack_models import build_pc_npc_extra_attack_slot
from towr.domain.pc_warped_form_models import PcWarpedFormProfileProof
from towr.domain.pc_warped_form_policy_models import PcWarpedFormPolicy
from towr.domain.test_models import DiceModifier
from towr.domain.turn_models import CombatActionSlotResult, CombatTurnEndRequest
from towr.engine.pc_melee_runner import run_pc_melee_scenario, apply_pc_melee_step
from towr.rules.test_resolution import resolve_test
from towr.rules.turn_resolution import end_combat_turn


ACTOR = 'crushing_bear1'
RULE = 'RULE-PROFILE-CREATURE-010:crushing-weight-prone'
PC_MISS = [10]*3 + [1]*3
PC_WEAK = [1, 10, 10] + [10]*3
BEAR_MISS = [10]*3 + [1]*3
BEAR_HIT = [1]*3 + [10]*3 + [1]


def scene(*, pcs=1, rounds=1, enabled=True, **counts):
    source = book_pc_scenario(crushing_bears=1, footpads=counts.pop('footpads', 0), townsfolk=0,
        pc_count=pcs, max_rounds=rounds, **counts)
    return replace(source, facts=replace(source.facts, outnumbering_bonus_approved=False),
        npc_extra_attack_actor_ids=(ACTOR,) if enabled else ())


def execute(source, values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source, rng)
    rng.assert_exhausted()
    return result


def steps(result, kind):
    return tuple(step for step in result.steps if type(step.proof) is kind)


def incoming(result):
    return tuple(step for step in steps(result, PcAttackProof) if step.proof.request.actor_id == ACTOR)


class PcCrushingWeightExecutionTests(unittest.TestCase):
    def test_miss_and_zero_zero_apply_no_prone_or_secondary_rule(self):
        for values in (BEAR_MISS, [10]*6):
            result = execute(scene(pcs=2), PC_MISS*2+values)
            attack, = incoming(result)
            self.assertIs(attack.proof.execution.resolution.attack.outcome, AttackOutcome.MISS)
            self.assertFalse(result.state.participant('pc1').injury.conditions.has(Condition.PRONE))
            self.assertEqual(attack.proof.execution.resolution.applied_secondary_rule_ids, ())

    def test_weak_positive_tie_applies_prone_before_first_stagger_without_wound_or_test_bonus(self):
        source = scene()
        source = replace(source, party=tuple(replace(m, pc=replace(m.pc, toughness=10)) for m in source.party))
        result = execute(source, PC_WEAK+[1, 10, 10]+[1, 10, 10])
        attack, = incoming(result)
        raw = attack.proof.execution.resolution
        self.assertTrue(raw.attack.tie_break_applied)
        self.assertIs(raw.attack.impact, ImpactOutcome.STAGGERED)
        self.assertTrue(raw.stagger.state.has(Condition.PRONE))
        self.assertTrue(raw.stagger.state.has(Condition.STAGGERED))
        self.assertIsNone(raw.character_wound)
        self.assertEqual(raw.applied_secondary_rule_ids, (RULE,))
        self.assertEqual(raw.attack.attacker_test.trace.rolled_dice, 3)
        self.assertFalse(attack.proof.request.kernel_request.target_state.conditions.has(Condition.PRONE))
        self.assertEqual(raw.condition_applications, ())
        self.assertEqual(result.state.participant('pc1').hit_condition_sources, ())

    def test_direct_wound_lifecycle_source_already_contains_hit_prone(self):
        result = execute(scene(), PC_MISS+BEAR_HIT)
        attack, = incoming(result)
        raw = attack.proof.execution.resolution
        self.assertTrue(raw.pending_character_wound.source_request.wound.state.conditions.has(Condition.PRONE))
        self.assertFalse(attack.proof.request.kernel_request.target_state.conditions.has(Condition.PRONE))
        self.assertTrue(raw.target_state.conditions.has(Condition.PRONE))
        self.assertEqual(raw.applied_secondary_rule_ids, (RULE,))
        self.assertEqual(result.state.participant('pc1').hit_condition_sources, ())

    def test_repeated_stagger_options_observe_prone_before_the_wound_choice(self):
        source = scene()
        source = replace(source, facts=replace(source.facts, can_leave_zone=True),
            party=tuple(replace(m, pc=replace(m.pc, toughness=10)) for m in source.party))
        result = execute(source, PC_MISS+[1, 10, 10]+[1, 10, 10]+[1])
        attack, = incoming(result)
        raw = attack.proof.execution.resolution
        self.assertEqual(raw.stagger.allowed_choices, (StaggerChoice.SUFFER_WOUND,))
        self.assertIs(raw.stagger.selected_choice, StaggerChoice.SUFFER_WOUND)
        self.assertTrue(raw.stagger.state.has(Condition.PRONE))
        self.assertEqual(len(result.state.participant('pc1').injury.wounds), 1)

    def test_near_miss_removes_only_wound_and_keeps_early_hit_prone(self):
        source = scene()
        source = replace(source, party=(replace(source.party[0], fate_policy=PcFatePolicy.CONFIGURED,
            near_miss_policy=PcNearMissPolicy(1, 0)),))
        result = execute(source, PC_MISS+[1]*3+[10]*3+[6])
        member = result.state.participant('pc1')
        self.assertEqual(member.injury.wounds, ())
        self.assertEqual(member.daily_wounds.wound_count, 0)
        self.assertTrue(member.injury.conditions.has(Condition.PRONE))
        self.assertEqual(member.hit_condition_sources, ())
        self.assertEqual(member.fate.rating, 2)
        completion, = steps(result, PcWoundCompletionProof)
        self.assertTrue(completion.proof.completion.source_request.roll.source_request.wound.state.conditions.has(Condition.PRONE))

    def test_standard_self_recover_removes_hit_prone_without_permanent_retention(self):
        result = execute(scene(rounds=2), PC_MISS+BEAR_HIT+BEAR_MISS)
        recover, = steps(result, PcRecoverProof)
        self.assertTrue(recover.source.participant('pc1').injury.conditions.has(Condition.PRONE))
        self.assertFalse(recover.state.participant('pc1').injury.conditions.has(Condition.PRONE))
        self.assertFalse(result.state.participant('pc1').injury.conditions.has(Condition.PRONE))
        self.assertEqual(result.state.participant('pc1').hit_condition_sources, ())

    def test_later_hit_can_apply_prone_again_after_legitimate_self_recover(self):
        result = execute(scene(rounds=2), PC_MISS+BEAR_HIT+[1]*3+[10]*3+[1, 1])
        first, second = incoming(result)
        self.assertTrue(first.state.participant('pc1').injury.conditions.has(Condition.PRONE))
        self.assertFalse(second.source.participant('pc1').injury.conditions.has(Condition.PRONE))
        self.assertTrue(second.state.participant('pc1').injury.conditions.has(Condition.PRONE))
        self.assertEqual(second.proof.execution.resolution.attack.attacker_test.trace.rolled_dice, 3)

    def test_standard_ally_recover_clears_hit_prone_before_the_ally_next_action(self):
        source = scene(pcs=2, rounds=2, enabled=False)
        source = replace(source, pc_activation_order=('pc2', 'pc1'), party=(source.party[0],
            replace(source.party[1], policy=PcMeleePolicy.RECOVER_ALLY_OR_ATTACK_OR_RECOVER_SELF,
                ally_recover_policy=PcAllyRecoverPolicy('pc1'))))
        result = execute(source, PC_MISS*2+BEAR_HIT+PC_MISS+BEAR_MISS)
        recover, = steps(result, PcRecoverProof)
        self.assertEqual(recover.proof.result.source_request.actor_id, 'pc2')
        self.assertEqual(recover.proof.result.source_request.choice.prone_target.entity_id, 'pc1')
        self.assertFalse(recover.state.participant('pc1').injury.conditions.has(Condition.PRONE))
        self.assertEqual(result.state.participant('pc1').hit_condition_sources, ())

    def test_ongoing_wound_prone_is_not_treated_as_removable_hit_prone(self):
        # W2 total17 is an ongoing Shattered Knee. R3 attacks, rather than
        # fabricating a Recover that removes the wound's untreated Prone cause.
        values = (PC_MISS+BEAR_HIT+[1]*3+[10]*3+[10, 7]
            +PC_MISS+[1]*3+[10]*4+[1]*3)
        result = execute(scene(rounds=3), values)
        self.assertEqual(len(steps(result, PcRecoverProof)), 1)
        member = result.state.participant('pc1')
        self.assertTrue(member.injury.conditions.has(Condition.PRONE))
        self.assertTrue(any(type(effect) is WoundConditionEffect and effect.condition is Condition.PRONE
            and effect.duration is WoundEffectDuration.UNTIL_TREATED for effect in member.injury.active_wound_effects))

    def test_two_real_attacks_finish_wound_queues_then_end_one_turn(self):
        result = execute(scene(pcs=2), PC_MISS*2+BEAR_HIT*2)
        first, second = incoming(result)
        self.assertEqual((first.proof.request.target_id, second.proof.request.target_id), ('pc1', 'pc2'))
        self.assertEqual((first.proof.execution.slot_index, second.proof.execution.slot_index), (1, 2))
        self.assertNotEqual(first.proof.request.id, second.proof.request.id)
        self.assertFalse(second.source.pending)
        self.assertIsNone(second.source.pending_wound)
        self.assertEqual(len(second.source.participant('pc1').injury.wounds), 1)
        self.assertTrue(all(result.state.participant(actor).injury.conditions.has(Condition.PRONE)
            for actor in ('pc1', 'pc2')))
        self.assertEqual(result.executed_actions, 4)
        self.assertEqual(sum(p.proof.result.completed_turn.actor_id == ACTOR for p in steps(result, PcTurnEndProof)), 1)

    def test_wound_endurance_finishes_before_second_attack_and_observes_early_prone(self):
        result = execute(scene(pcs=2), PC_MISS*2+[1]*3+[10]*3+[5]+[10]*3+BEAR_HIT)
        first, second = incoming(result)
        endurance, = steps(result, PcEnduranceProof)
        self.assertTrue(endurance.source.participant('pc1').injury.conditions.has(Condition.PRONE))
        self.assertLess(result.steps.index(first), result.steps.index(endurance))
        self.assertLess(result.steps.index(endurance), result.steps.index(second))
        self.assertFalse(second.source.pending)

    def test_empty_policy_or_single_live_pc_skips_extra_attack_but_keeps_prone(self):
        for source, pcs in ((scene(pcs=2, enabled=False), 2), (scene(), 1)):
            result = execute(source, PC_MISS*pcs+BEAR_HIT)
            self.assertEqual(len(incoming(result)), 1)
            self.assertTrue(result.state.participant('pc1').injury.conditions.has(Condition.PRONE))

    def test_current_priority_still_picks_a_different_secondary_pc(self):
        source = replace(scene(pcs=3), enemy_target_priority=('pc3', 'pc2', 'pc1'))
        result = execute(source, PC_MISS*3+BEAR_HIT*2)
        self.assertEqual(tuple(p.proof.request.target_id for p in incoming(result)), ('pc3', 'pc2'))

    def test_primary_death_keeps_actual_first_target_and_attacks_the_other_live_pc(self):
        source = scene(pcs=2, rounds=3)
        hit2 = [1]*3+[10]*3+[1, 1]
        values = PC_MISS*2+BEAR_HIT*2+hit2*2+[1]*3+[10]*3+[10]*3+[1]*3+[10]*3+[1]*3
        result = execute(source, values)
        second = incoming(result)[-1]
        self.assertTrue(second.source.participant('pc1').injury.dead)
        self.assertFalse(second.source.participant('pc2').injury.dead)
        self.assertEqual(second.proof.request.target_id, 'pc2')
        self.assertEqual(second.proof.request.state.active_turn.action_slots[-1].enduring_strength.first_target_id, 'pc1')
        self.assertTrue(second.state.participant('pc2').injury.conditions.has(Condition.PRONE))

    def test_pending_or_replayed_steps_cannot_skip_or_duplicate_prone_and_slot2(self):
        result = execute(scene(pcs=2), PC_MISS*2+BEAR_HIT*2)
        first, second = incoming(result)
        with self.assertRaises(ValueError):
            build_pc_npc_extra_attack_slot(first.state)
        with self.assertRaises((TypeError, ValueError)):
            apply_pc_melee_step(first.state, first)
        forged = deepcopy(first.proof)
        object.__setattr__(forged.execution.resolution.pending_character_wound.source_request.wound,
            'state', first.proof.request.kernel_request.target_state)
        with self.assertRaises((TypeError, ValueError)):
            PcMeleeStep(first.source, forged)
        slot = next(p for p in result.steps if type(p.proof) is CombatActionSlotResult and p.proof.slot.index == 2)
        clock = slot.source.round_state
        end = end_combat_turn(CombatTurnEndRequest('pc-melee:r1:crushing_bear1:end', clock, ACTOR))
        with self.assertRaises(ValueError):
            PcMeleeStep(slot.source, PcTurnEndProof(end, None))
        forged = deepcopy(second.proof)
        object.__setattr__(forged.request.kernel_request.attack.secondary_effects[0], 'affects_monstrosities', 1)
        with self.assertRaises((TypeError, ValueError)):
            PcMeleeStep(second.source, forged)

    def test_drained_from_first_wound_does_not_suppress_damage_effect_or_second_attack(self):
        source = scene(pcs=2)
        source = replace(source, party=(replace(source.party[0], pc=replace(source.party[0].pc, strength=6)),
            source.party[1]))
        result = execute(source, [1]*3+[10]*3+PC_MISS+BEAR_HIT*2)
        first, second = incoming(result)
        self.assertTrue(first.source.enemy(ACTOR).state.injury.conditions.has(Condition.DRAINED))
        self.assertEqual(first.proof.execution.resolution.attack.attacker_test.trace.rolled_dice, 3)
        self.assertEqual(second.proof.execution.resolution.attack.attacker_test.trace.rolled_dice, 3)
        self.assertEqual(second.proof.execution.resolution.applied_secondary_rule_ids, (RULE,))

    def test_real_wave_w1_applies_bear_drained_through_the_actual_npc_ack(self):
        source = scene(skin_wolves=1)
        target_order = ('skin_wolf1', ACTOR)
        source = replace(source, enemy_activation_order=(ACTOR, 'skin_wolf1'),
            party=tuple(replace(m, pc=replace(m.pc, weapon=PcMeleeWeapon.AXE), target_priority=target_order,
                defeat_decisions=tuple(m.defeat_decision(actor) for actor in target_order)) for m in source.party),
            npc_warped_form_policies=(PcWarpedFormPolicy('skin_wolf1', ('pc1', ACTOR),
                (MinionDefeatDecision('skin_wolf1', ACTOR, NpcDefeatDisposition.KILLED, True),)),))
        # Wolf W1; Bear misses and gains Staggered; Wolf hits then heals/waves.
        result = execute(source, [1]*3+[10]*4+BEAR_MISS+[1]*5+[10]*3+[1])
        ack, = steps(result, PcWarpedFormProfileProof)
        self.assertEqual(ack.proof.target_id, ACTOR)
        self.assertTrue(ack.state.enemy(ACTOR).state.injury.conditions.has(Condition.DRAINED))
        self.assertEqual(ack.proof.source.current_wounds, 1)

    def test_unsupported_anatomy_retains_first_attack_prefix_without_second_action(self):
        source = scene(pcs=2, footpads=1, minotaurs=2)
        source = replace(source, enemy_activation_order=('footpad1', 'minotaur1', 'minotaur2', ACTOR))
        values = (PC_MISS*2+[1]*3+[10]*3+[1]
            +[1]*4+[10]*3+[10, 9, 1]+[1]
            +[1]*4+[10, 8, 1, 1]
            +[1]*3+[3]*4)
        result = execute(source, values)
        self.assertIs(result.outcome, PcMeleeOutcome.UNSUPPORTED_PATH)
        self.assertEqual(result.unsupported.actor_id, 'pc1')
        self.assertEqual(result.unsupported.reason, 'unavailable_anatomical_target')
        self.assertEqual(len(incoming(result)), 1)
        self.assertTrue(result.state.pending)
        self.assertTrue(result.state.participant('pc1').injury.conditions.has(Condition.PRONE))
        self.assertFalse(result.state.participant('pc2').injury.conditions.has(Condition.PRONE))


if __name__ == '__main__':
    unittest.main()
