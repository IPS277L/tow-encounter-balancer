from copy import deepcopy
from dataclasses import replace
from itertools import product
from random import Random
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_m2_npc_ranged_scenario import scenario
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.npc_ranged_scenario_result_models import NpcRangedScenarioOutcome as Outcome
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult
from towr.domain.npc_rounds_models import NpcRoundsResult
from towr.engine import npc_ranged_scenario_runner as runner
from towr.rules import attack_action_execution as attack_executor
from towr.rules.npc_roster_attack_execution import apply_npc_roster_attack_result
from towr.rules.minion_defeat_resolution import apply_minion_defeat_acknowledgement


MISS = [10] * 6
STAGGER = [1, 10, 10, 10, 10, 10]
WOUND = [1, 2, 10, 10, 10, 10]


def attacks(result):
    return tuple(action for call in result.runner_report.source_steps if isinstance(call, NpcRoundsResult)
                 for combat in call.rounds for action in combat.steps if isinstance(action, NpcRosterAttackExecutionResult))


class M2NpcRangedScenarioCycleTests(unittest.TestCase):
    def test_terminal_defeats_switch_targets_and_stop_mid_round_with_full_decisions(self):
        for reverse, disposition in product((False, True), NpcDefeatDisposition):
            with self.subTest(reverse=reverse, disposition=disposition):
                source = scenario(reverse=reverse, disposition=disposition)
                source = replace(source, initial=replace(source.initial, max_rounds=1))
                before = deepcopy(source)
                rng = Mock(wraps=SequenceRandom(WOUND * 2))
                with (
                    patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel,
                    patch.object(runner, "acknowledge_minion_defeat", wraps=runner.acknowledge_minion_defeat) as acknowledge,
                    patch.object(runner, "exclude_defeated_npc", wraps=runner.exclude_defeated_npc) as exclude,
                    patch.object(runner, "advance_npc_round", side_effect=AssertionError("terminal advance")),
                ):
                    result = runner.run_npc_ranged_scenario(source, rng)
                self.assertIs(result.outcome, Outcome.SIDE_DEFEATED if reverse else Outcome.OBJECTIVE_ACHIEVED)
                self.assertEqual((kernel.call_count, acknowledge.call_count, exclude.call_count), (2, 2, 2))
                self.assertEqual(rng.randint.call_count, 12)
                self.assertEqual(result.current.pending_follow_ups, ())
                self.assertEqual(len(result.current.state.consumed_execution_ids), 2)
                self.assertEqual(len(result.current.state.acknowledged_defeat_execution_ids), 2)
                actual = attacks(result)
                self.assertEqual(tuple(a.execution.target_id for a in actual),
                                 source.policy_for(actual[0].execution.actor_id).target_actor_ids)
                self.assertTrue(result.current.round_state.active_turn.action_slots[0].executed)
                self.assertFalse(result.current.round_state.round_complete)
                self.assertEqual(result.runner_report.visited_round_count, 1)
                self.assertEqual(result.runner_report.executed_attack_count, 2)
                self.assertEqual(result.runner_report.newly_completed_round_count, 0)
                self.assertEqual(len(result.runner_report.defeat_acknowledgements), 1)
                self.assertEqual(len(result.defeat_acknowledgements), 2)
                for confirmation in result.defeat_acknowledgements:
                    self.assertIs(confirmation.source_request.decision.disposition, disposition)
                    self.assertTrue(confirmation.source_request.decision.gm_approved)
                    with self.assertRaises(ValueError):
                        apply_minion_defeat_acknowledgement(result.current, confirmation)
                for attack in actual:
                    with self.assertRaises(ValueError):
                        apply_npc_roster_attack_result(result.current.state, attack)
                self.assertEqual(source, before)

    def test_terminal_target_that_already_acted_is_not_excluded(self):
        source = scenario()
        rng = Mock(wraps=SequenceRandom(MISS * 2 + WOUND * 2))
        with patch.object(runner, "exclude_defeated_npc", side_effect=AssertionError("completed target excluded")):
            result = runner.run_npc_ranged_scenario(source, rng)
        self.assertIs(result.outcome, Outcome.SIDE_DEFEATED)
        self.assertIsNone(result.terminal_exclusion)
        self.assertEqual(result.current.round_state.excluded_turn_entity_ids, ())
        self.assertEqual(result.runner_report.executed_attack_count, 4)
        self.assertEqual(rng.randint.call_count, 24)
        self.assertEqual(len(result.defeat_acknowledgements), 2)

    def test_supplied_actor_and_target_priorities_and_mixed_decisions_are_preserved(self):
        source = scenario()
        policies = tuple(replace(policy, target_actor_ids=policy.target_actor_ids[::-1],
            defeat_decisions=tuple(replace(decision, disposition=(NpcDefeatDisposition.KILLED if index == 0
                                  else NpcDefeatDisposition.DISARMED_AND_SURRENDERED))
                                   for index, decision in enumerate(policy.defeat_decisions[::-1])))
            for policy in source.actor_policies)
        source = replace(source, actor_policies=policies,
                         initial=replace(source.initial, current=replace(source.initial.current,
                             actor_order=source.initial.current.actor_order[::-1])))
        result = runner.run_npc_ranged_scenario(source, SequenceRandom(WOUND * 2))
        self.assertEqual(tuple((a.execution.actor_id, a.execution.target_id) for a in attacks(result)),
                         (("actor:0:1", "actor:1:1"), ("actor:0:0", "actor:1:0")))
        self.assertEqual(tuple(a.source_request.decision.disposition for a in result.defeat_acknowledgements),
                         (NpcDefeatDisposition.KILLED, NpcDefeatDisposition.DISARMED_AND_SURRENDERED))
        self.assertIs(result.outcome, Outcome.OBJECTIVE_ACHIEVED)

    def test_terminal_first_shot_does_not_start_remaining_allied_turns(self):
        source = scenario(sizes=(3, 1))
        rng = Mock(wraps=SequenceRandom(WOUND))
        result = runner.run_npc_ranged_scenario(source, rng)
        self.assertIs(result.outcome, Outcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(result.runner_report.executed_attack_count, 1)
        self.assertEqual(result.current.round_state.completed_turn_entity_ids, ())
        self.assertEqual(rng.randint.call_count, 6)

    def test_repeated_stagger_across_rounds_uses_supplied_wound_choice_once(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                source = scenario(sizes=(1, 1), reverse=reverse)
                source = replace(source, initial=replace(source.initial, max_rounds=2))
                rng = Mock(wraps=SequenceRandom(STAGGER + MISS + STAGGER))
                with patch.object(runner, "advance_npc_round", wraps=runner.advance_npc_round) as advance:
                    result = runner.run_npc_ranged_scenario(source, rng)
                self.assertIs(result.outcome, Outcome.SIDE_DEFEATED if reverse else Outcome.OBJECTIVE_ACHIEVED)
                self.assertEqual(advance.call_count, 1)
                self.assertEqual(result.runner_report.visited_round_count, 2)
                self.assertEqual(result.runner_report.newly_completed_round_count, 1)
                actual = attacks(result)
                self.assertTrue(actual[0].execution.resolution.target_state.conditions.has(Condition.STAGGERED))
                self.assertIs(actual[-1].execution.resolution.stagger.selected_choice, StaggerChoice.SUFFER_WOUND)
                self.assertTrue(actual[-1].execution.resolution.target_state.defeated)
                self.assertEqual(rng.randint.call_count, 18)

    def test_global_budget_is_not_reset_after_defeat_resume(self):
        for limit in (1, 2, 3):
            with self.subTest(limit=limit):
                source = scenario()
                source = replace(source, initial=replace(source.initial, max_rounds=limit))
                rng = Mock(wraps=SequenceRandom(WOUND + MISS * (3 * limit - 1)))
                with patch.object(runner, "advance_npc_round", wraps=runner.advance_npc_round) as advance:
                    result = runner.run_npc_ranged_scenario(source, rng)
                self.assertIs(result.outcome, Outcome.ROUND_LIMIT)
                self.assertEqual(advance.call_count, limit - 1)
                self.assertEqual(result.runner_report.visited_round_count, limit)
                self.assertEqual(result.runner_report.newly_completed_round_count, limit)
                self.assertEqual(len(result.runner_report.call_summaries), limit + 1)
                self.assertEqual(result.runner_report.executed_attack_count, 3 * limit)
                self.assertEqual(len(result.defeat_acknowledgements), 1)
                self.assertEqual(rng.randint.call_count, 18 * limit)
                for call in advance.call_args_list:
                    planned = call.args[0]
                    self.assertEqual(len(planned.next_round_participants), 3)
                    self.assertNotIn("actor:1:0", planned.next_actor_order)
                    self.assertEqual(planned.next_actor_order, ("actor:0:0", "actor:0:1", "actor:1:1"))
                    self.assertEqual(planned.current.round_state.side_order, source.initial.current.round_state.side_order)

    def test_all_misses_reach_exact_budget_without_defeat_or_false_draw(self):
        source = scenario()
        result = runner.run_npc_ranged_scenario(source, SequenceRandom(MISS * 12))
        self.assertIs(result.outcome, Outcome.ROUND_LIMIT)
        self.assertEqual(result.defeat_acknowledgements, ())
        self.assertEqual(result.runner_report.executed_attack_count, 12)
        self.assertEqual(result.runner_report.newly_completed_round_count, 3)
        self.assertTrue(all(not p.state.injury.defeated for p in result.current.state.roster.participants))

    def test_seeded_runs_are_reproducible_and_keep_all_executions_within_budget(self):
        source = scenario(sizes=(3, 2))
        for seed in range(20):
            with self.subTest(seed=seed):
                result = runner.run_npc_ranged_scenario(source, Random(seed))
                self.assertEqual(result, runner.run_npc_ranged_scenario(source, Random(seed)))
                self.assertNotEqual(result.outcome, Outcome.UNSUPPORTED_PATH)
                self.assertLessEqual(result.runner_report.executed_attack_count, 5 * source.initial.max_rounds)
                self.assertEqual(len(result.current.state.consumed_execution_ids), result.runner_report.executed_attack_count)
                self.assertEqual(len(result.defeat_acknowledgements),
                                 sum(p.state.injury.defeated for p in result.current.state.roster.participants))
