from copy import deepcopy
from dataclasses import replace
from itertools import product
from random import Random
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_m7_npc_mixed_scenario import scenario
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.npc_attack_selection_models import NpcAttackSelectionBlock
from towr.domain.npc_mixed_scenario_result_models import NpcMixedScenarioOutcome as Outcome
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult
from towr.domain.npc_rounds_models import NpcRoundsResult
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.turn_models import CombatSide
from towr.engine import npc_mixed_scenario_runner as runner
from towr.rules import attack_action_execution as attack_executor
from towr.rules.minion_defeat_resolution import apply_minion_defeat_acknowledgement
from towr.rules.npc_roster_attack_execution import apply_npc_roster_attack_result


MISS = [10] * 6
WOUND = [1, 2, 10, 10, 10, 10]
BONUS_WOUND = [1, 2, 10, 10, 10, 10, 10]
BONUS_MISS = [10] * 7
LOW_BOW = [1, 10, 10, 1, 10, 10]


def attacks(result):
    return tuple(action for call in result.runner_report.source_steps if isinstance(call, NpcRoundsResult)
                 for combat in call.rounds for action in combat.steps if isinstance(action, NpcRosterAttackExecutionResult))


class M7NpcMixedScenarioCycleTests(unittest.TestCase):
    def test_shot_then_melee_recounts_bonus_and_stops_once_with_all_dispositions(self):
        for opposition, disposition in product((False, True), NpcDefeatDisposition):
            with self.subTest(opposition=opposition, disposition=disposition):
                source = scenario(disposition=disposition)
                if opposition:
                    source = replace(source, perspective_side=CombatSide.OPPOSITION,
                                     objective=NpcDefeatObjective(('0:0', '0:1', '0:2')))
                before = deepcopy(source)
                rng = Mock(wraps=SequenceRandom(WOUND + BONUS_WOUND))
                with (
                    patch.object(attack_executor, 'resolve_kernel_attack', wraps=attack_executor.resolve_kernel_attack) as kernel,
                    patch.object(runner, 'acknowledge_minion_defeat', wraps=runner.acknowledge_minion_defeat) as ack,
                    patch.object(runner, 'exclude_defeated_npc', wraps=runner.exclude_defeated_npc) as exclude,
                    patch.object(runner, 'advance_npc_round', side_effect=AssertionError('terminal advance')),
                ):
                    result = runner.run_npc_mixed_scenario(source, rng)
                self.assertIs(result.outcome, Outcome.SIDE_DEFEATED if opposition else Outcome.OBJECTIVE_ACHIEVED)
                self.assertEqual((kernel.call_count, ack.call_count, exclude.call_count), (2, 2, 2))
                self.assertEqual(rng.randint.call_count, 13)
                actual = attacks(result)
                self.assertEqual(tuple(a.execution.actor_id for a in actual), ('0:0', '0:1'))
                self.assertEqual(tuple(a.execution.target_id for a in actual), ('1:0', '1:1'))
                self.assertEqual(tuple(a.source_request.preparation.npc_attack.source_request.target_range for a in actual),
                                 (Range.MEDIUM, Range.CLOSE))
                self.assertEqual(tuple(len(a.execution.resolution.attack.attacker_test.trace.initial_values) for a in actual), (3, 4))
                self.assertEqual(result.current.pending_follow_ups, ())
                self.assertEqual(len(result.current.state.consumed_execution_ids), 2)
                self.assertEqual(len(result.runner_report.defeat_acknowledgements), 1)
                self.assertEqual(len(result.defeat_acknowledgements), 2)
                self.assertEqual(result.runner_report.visited_round_count, 1)
                self.assertEqual(result.runner_report.newly_completed_round_count, 0)
                for confirmation in result.defeat_acknowledgements:
                    self.assertIs(confirmation.source_request.decision.disposition, disposition)
                    with self.assertRaises(ValueError):
                        apply_minion_defeat_acknowledgement(result.current, confirmation)
                for action in actual:
                    with self.assertRaises(ValueError):
                        apply_npc_roster_attack_result(result.current.state, action)
                self.assertEqual(source, before)

    def test_exhausted_melee_targets_stop_without_wait_move_or_extra_rng(self):
        source = scenario(sizes=(2, 2), enemy_bow=True)
        bow = source.policy_for('0:0')
        source = replace(source, actor_policies=(replace(bow, target_actor_ids=bow.target_actor_ids[::-1],
                         defeat_decisions=bow.defeat_decisions[::-1]), *source.actor_policies[1:]))
        rng = Mock(wraps=SequenceRandom(WOUND))
        with patch.object(runner, 'advance_npc_round', side_effect=AssertionError('blocked advance')):
            result = runner.run_npc_mixed_scenario(source, rng)
        self.assertIs(result.outcome, Outcome.UNSUPPORTED_PATH)
        self.assertIs(result.runner_report.blocked_reason, NpcAttackSelectionBlock.NO_CANDIDATE)
        self.assertEqual(result.runner_report.executed_attack_count, 1)
        self.assertEqual(rng.randint.call_count, 6)
        self.assertEqual(len(result.defeat_acknowledgements), 1)
        self.assertIsNone(result.terminal_acknowledgement)
        self.assertIsNone(result.terminal_exclusion)
        turn = result.current.round_state.active_turn
        self.assertEqual(turn.actor_id, '0:1')
        self.assertFalse(turn.action_slots[0].executed)
        self.assertFalse(result.current.round_state.round_complete)
        self.assertEqual(result.current.pending_follow_ups, ())
        self.assertEqual(result.runner_report.spatial_state.placements, source.initial.spatial_state.placements)

    def test_melee_skips_remote_first_target_then_bow_finishes_remaining_enemy(self):
        source = scenario(sizes=(2, 2), enemy_bow=True)
        source = replace(source, initial=replace(source.initial, current=replace(source.initial.current,
                         actor_order=('0:1', '0:0', '1:0', '1:1'))))
        rng = Mock(wraps=SequenceRandom(WOUND * 2))
        result = runner.run_npc_mixed_scenario(source, rng)
        self.assertIs(result.outcome, Outcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(tuple((a.execution.actor_id, a.execution.target_id) for a in attacks(result)),
                         (('0:1', '1:1'), ('0:0', '1:0')))
        self.assertEqual(rng.randint.call_count, 12)

    def test_completed_targets_are_not_excluded_on_real_side_defeat(self):
        source = scenario(sizes=(2, 2), enemy_bow=True)
        rng = Mock(wraps=SequenceRandom(MISS * 2 + WOUND * 2))
        with patch.object(runner, 'exclude_defeated_npc', side_effect=AssertionError('completed target excluded')):
            result = runner.run_npc_mixed_scenario(source, rng)
        self.assertIs(result.outcome, Outcome.SIDE_DEFEATED)
        self.assertIsNone(result.terminal_exclusion)
        self.assertEqual(result.current.round_state.excluded_turn_entity_ids, ())
        self.assertEqual(rng.randint.call_count, 24)
        self.assertEqual(tuple(a.execution.target_id for a in attacks(result)[-2:]), ('0:0', '0:1'))

    def test_repeated_stagger_across_rounds_and_close_miss_do_not_double_apply(self):
        source = scenario(sizes=(2, 1))
        source = replace(source, initial=replace(source.initial, max_rounds=2))
        rng = Mock(wraps=SequenceRandom(LOW_BOW + MISS * 2 + LOW_BOW))
        with patch.object(runner, 'advance_npc_round', wraps=runner.advance_npc_round) as advance:
            result = runner.run_npc_mixed_scenario(source, rng)
        self.assertIs(result.outcome, Outcome.OBJECTIVE_ACHIEVED)
        actual = attacks(result)
        self.assertTrue(actual[0].execution.resolution.target_state.conditions.has(Condition.STAGGERED))
        self.assertFalse(actual[2].execution.resolution.target_state.defeated)
        self.assertIs(actual[-1].execution.resolution.stagger.selected_choice, StaggerChoice.SUFFER_WOUND)
        self.assertEqual(advance.call_count, 1)
        self.assertEqual(result.runner_report.executed_attack_count, 4)
        self.assertEqual(rng.randint.call_count, 24)
        self.assertFalse(result.current.state.roster.participant('0:0').state.injury.conditions.has(Condition.STAGGERED))

    def test_resume_preserves_whole_budget_and_surviving_order(self):
        for budget in (1, 2, 3):
            with self.subTest(budget=budget):
                source = scenario()
                source = replace(source, initial=replace(source.initial, max_rounds=budget))
                values = WOUND + BONUS_MISS * 2 + MISS + (MISS + BONUS_MISS * 2 + MISS) * (budget - 1)
                rng = Mock(wraps=SequenceRandom(values))
                with patch.object(runner, 'advance_npc_round', wraps=runner.advance_npc_round) as advance:
                    result = runner.run_npc_mixed_scenario(source, rng)
                self.assertIs(result.outcome, Outcome.ROUND_LIMIT)
                self.assertEqual(advance.call_count, budget - 1)
                self.assertEqual(result.runner_report.visited_round_count, budget)
                self.assertEqual(result.runner_report.newly_completed_round_count, budget)
                self.assertEqual(result.runner_report.executed_attack_count, 4 * budget)
                self.assertEqual(len(result.runner_report.call_summaries), budget + 1)
                self.assertEqual(rng.randint.call_count, 26 * budget)
                for call in advance.call_args_list:
                    self.assertEqual(call.args[0].next_actor_order, ('0:0', '0:1', '0:2', '1:1'))

    def test_all_misses_stagger_only_close_attackers_without_escalation(self):
        source = scenario()
        rng = Mock(wraps=SequenceRandom(MISS * 15))
        result = runner.run_npc_mixed_scenario(source, rng)
        self.assertIs(result.outcome, Outcome.ROUND_LIMIT)
        self.assertEqual(result.defeat_acknowledgements, ())
        self.assertEqual(result.runner_report.executed_attack_count, 15)
        self.assertEqual(rng.randint.call_count, 90)
        for participant in result.current.state.roster.participants:
            self.assertEqual(participant.state.injury.wounds, 0)
            self.assertEqual(participant.state.injury.conditions.has(Condition.STAGGERED), participant.state.actor_id != '0:0')

    def test_gm_withholding_survives_real_defeat_resume(self):
        source = scenario(approved=False)
        rng = Mock(wraps=SequenceRandom(WOUND * 2))
        result = runner.run_npc_mixed_scenario(source, rng)
        self.assertIs(result.outcome, Outcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(rng.randint.call_count, 12)
        self.assertTrue(all(a.source_request.preparation.npc_attack.source_request.dice_modifiers == () for a in attacks(result)))

    def test_seeded_results_are_repeatable_bounded_and_keep_unsupported_distinct(self):
        source = scenario(sizes=(2, 2), enemy_bow=True)
        for seed in range(10):
            with self.subTest(seed=seed):
                result = runner.run_npc_mixed_scenario(source, Random(seed))
                self.assertEqual(result, runner.run_npc_mixed_scenario(source, Random(seed)))
                self.assertLessEqual(result.runner_report.executed_attack_count, 4 * source.initial.max_rounds)
                self.assertIn(result.outcome, tuple(Outcome))
