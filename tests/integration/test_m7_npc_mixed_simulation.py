from copy import deepcopy
from dataclasses import replace
import random
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_m7_npc_mixed_scenario import scenario
from towr.domain.npc_attack_selection_models import NpcAttackSelectionBlock
from towr.domain.npc_mixed_scenario_result_models import NpcMixedScenarioOutcome as Outcome
from towr.domain.npc_rounds_models import NpcRoundsOutcome
from towr.simulation.npc_mixed_models import NpcMixedSimulationRequest, NpcMixedSimulationResult, NpcMixedOutcomeCounts
from towr.simulation import npc_mixed_simulation as simulation
from towr.simulation.npc_mixed_summary import summarize_npc_mixed_simulation as summarize


WOUND = [1, 2, 10, 10, 10, 10]
MISS = [10] * 6


def four_outcome_request():
    source = scenario(sizes=(2, 2), enemy_bow=True)
    bow = source.policy_for('0:0')
    # Shoot the enemy melee first; the ally melee may then lack a Close target.
    source = replace(source, initial=replace(source.initial, max_rounds=2), actor_policies=(
        replace(bow, target_actor_ids=bow.target_actor_ids[::-1], defeat_decisions=bow.defeat_decisions[::-1]),
        *source.actor_policies[1:]))
    return NpcMixedSimulationRequest(source, 42, 4)


class M7NpcMixedSimulationIntegrationTests(unittest.TestCase):
    def test_four_real_outcomes_from_same_initial_have_exact_counters_and_separate_rngs(self):
        request = four_outcome_request()
        before, global_rng = deepcopy(request), random.getstate()
        scripts = (MISS + WOUND + MISS + WOUND, MISS * 2 + WOUND * 2, MISS * 8, WOUND)
        values = {request.seed_for(i): script for i, script in enumerate(scripts)}
        created, full = [], []
        def factory(seed):
            rng = Mock(wraps=SequenceRandom(values[seed]))
            created.append(rng)
            return rng
        actual_runner = simulation.run_npc_mixed_scenario
        def observe(source, rng):
            self.assertIs(source, request.scenario)
            result = actual_runner(source, rng)
            full.append(result)
            return result
        rng_factory = Mock(side_effect=factory)
        with patch.object(simulation, 'run_npc_mixed_scenario', side_effect=observe):
            result = simulation.run_npc_mixed_simulation(request, rng_factory=rng_factory)
        self.assertEqual(tuple(t.outcome for t in result.trials), tuple(Outcome))
        self.assertEqual(tuple((t.executed_attack_count, t.visited_round_count) for t in result.trials),
                         ((4, 2), (4, 1), (8, 2), (1, 1)))
        self.assertEqual([r.randint.call_count for r in created], [24, 24, 48, 6])
        self.assertEqual(len({id(r) for r in created}), 4)
        self.assertEqual([c.args[0] for c in rng_factory.call_args_list], [request.seed_for(i) for i in range(4)])
        summary = summarize(result)
        self.assertIs(summary.source_request, request)
        self.assertEqual(summary.outcome_counts, NpcMixedOutcomeCounts(1, 1, 1, 1))
        self.assertEqual((summary.trials, summary.total_attack_count, summary.total_visited_round_count), (4, 17, 6))
        self.assertEqual((summary.mean_attack_count, summary.mean_visited_round_count), (4.25, 1.5))
        self.assertIs(full[-1].runner_report.blocked_reason, NpcAttackSelectionBlock.NO_CANDIDATE)
        self.assertFalse(full[-1].current.round_state.active_turn.action_slots[0].executed)
        self.assertEqual(full[-1].current.round_state.active_turn.actor_id, '0:1')
        for terminal in full[:2]:
            self.assertIs(terminal.runner_report.outcome, NpcRoundsOutcome.PENDING_FOLLOW_UPS)
            self.assertIsNotNone(terminal.terminal_acknowledgement)
            self.assertEqual(terminal.current.pending_follow_ups, ())
        self.assertGreater(len(full[0].runner_report.call_summaries), result.trials[0].visited_round_count)
        self.assertEqual((request, random.getstate()), (before, global_rng))

    def test_default_rng_replay_reverse_and_expanded_prefix_preserve_indexed_trials(self):
        request = four_outcome_request()
        before, global_rng = deepcopy(request), random.getstate()
        result = simulation.run_npc_mixed_simulation(request)
        self.assertEqual(result, simulation.run_npc_mixed_simulation(request))
        reverse = tuple(simulation.run_npc_mixed_trial(request, i) for i in reversed(range(request.trials)))
        self.assertEqual(result, NpcMixedSimulationResult(request, reverse))
        expanded = simulation.run_npc_mixed_simulation(replace(request, trials=7))
        self.assertEqual(result.trials, expanded.trials[:4])
        self.assertEqual((request, random.getstate()), (before, global_rng))

    def test_more_draws_in_one_trial_do_not_shift_other_streams(self):
        request = four_outcome_request()
        def factory(extra):
            def make(seed):
                rng = random.Random(seed)
                if seed == request.seed_for(0):
                    for _ in range(extra):
                        rng.randint(1, 10)
                return rng
            return make
        first = simulation.run_npc_mixed_simulation(request, rng_factory=factory(0))
        shifted = simulation.run_npc_mixed_simulation(request, rng_factory=factory(17))
        self.assertEqual(first.trials[1:], shifted.trials[1:])

    def test_dynamic_bonus_gm_withholding_and_terminal_suffix_do_not_add_counts(self):
        for approval in (True, False):
            with self.subTest(approval=approval):
                request = NpcMixedSimulationRequest(scenario(approved=approval), 7, 2)
                before = deepcopy(request)
                created, full = [], []
                actual_runner = simulation.run_npc_mixed_scenario
                def observe(source, rng):
                    result = actual_runner(source, rng)
                    full.append(result)
                    return result
                def factory(seed):
                    rng = Mock(wraps=SequenceRandom(WOUND + WOUND + ([10] if approval else [])))
                    created.append(rng)
                    return rng
                with patch.object(simulation, 'run_npc_mixed_scenario', side_effect=observe):
                    result = simulation.run_npc_mixed_simulation(request, rng_factory=factory)
                summary = summarize(result)
                self.assertEqual(summary.outcome_counts, NpcMixedOutcomeCounts(2, 0, 0, 0))
                self.assertEqual((summary.total_attack_count, summary.total_visited_round_count), (4, 2))
                self.assertEqual([r.randint.call_count for r in created], [13 if approval else 12] * 2)
                for played in full:
                    self.assertEqual(played.source_scenario.actor_policies, request.scenario.actor_policies)
                    self.assertEqual(played.source_scenario.pair_ranges, request.scenario.pair_ranges)
                    self.assertIsNotNone(played.terminal_acknowledgement)
                    self.assertEqual(len(played.defeat_acknowledgements), 2)
                    self.assertEqual(played.runner_report.newly_completed_round_count, 0)
                self.assertEqual(request, before)
