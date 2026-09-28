from copy import deepcopy
from dataclasses import replace
import random
import unittest
from unittest.mock import Mock

from tests.helpers import SequenceRandom
from tests.unit.test_m6_npc_melee_scenario import scenario
from towr.simulation.npc_melee_models import NpcMeleeSimulationRequest, NpcMeleeSimulationResult, NpcMeleeOutcomeCounts
from towr.simulation.npc_melee_simulation import run_npc_melee_simulation, run_npc_melee_trial
from towr.simulation.npc_melee_summary import summarize_npc_melee_simulation as summarize


class M6NpcMeleeSimulationIntegrationTests(unittest.TestCase):
    def test_real_trials_have_exact_aggregates_and_distinct_injected_rng(self):
        source = scenario(sizes=(1, 1))
        source = replace(source, initial=replace(source.initial, max_rounds=2))
        request = NpcMeleeSimulationRequest(source, 17, 3)
        before = deepcopy(request)
        wound, miss = [1, 2, 10, 10, 10, 10], [10] * 6
        values = {request.seed_for(0): wound, request.seed_for(1): miss + wound, request.seed_for(2): miss * 4}
        created = []
        def make_rng(seed):
            rng = Mock(wraps=SequenceRandom(values[seed]))
            created.append(rng)
            return rng
        factory = Mock(side_effect=make_rng)
        result = run_npc_melee_simulation(request, rng_factory=factory)
        self.assertEqual(result.outcome_counts, NpcMeleeOutcomeCounts(1, 1, 1, 0))
        self.assertEqual(result.total_attack_count, 7)
        self.assertEqual(result.total_visited_round_count, 4)
        self.assertEqual([r.randint.call_count for r in created], [6, 12, 24])
        self.assertEqual([call.args[0] for call in factory.call_args_list], [request.seed_for(i) for i in range(3)])
        self.assertEqual(len({id(rng) for rng in created}), 3)
        self.assertEqual(request, before)
        summary = summarize(result)
        self.assertIs(summary.source_request, request)
        self.assertEqual(summary.outcome_counts, NpcMeleeOutcomeCounts(1, 1, 1, 0))
        self.assertEqual((summary.total_attack_count, summary.total_visited_round_count), (7, 4))

    def test_default_rng_replay_reverse_order_and_larger_batch_preserve_each_index(self):
        request = NpcMeleeSimulationRequest(scenario(), 12345, 6)
        global_before = random.getstate()
        result = run_npc_melee_simulation(request)
        self.assertEqual(result, run_npc_melee_simulation(request))
        reversed_trials = tuple(run_npc_melee_trial(request, index) for index in reversed(range(request.trials)))
        self.assertEqual(result, NpcMeleeSimulationResult(request, reversed_trials))
        larger = run_npc_melee_simulation(replace(request, trials=9))
        self.assertEqual(result.trials, larger.trials[:6])
        self.assertEqual(global_before, random.getstate())
        self.assertEqual(sum((result.outcome_counts.objective_achieved, result.outcome_counts.side_defeated,
                              result.outcome_counts.round_limit, result.outcome_counts.unsupported_path)), 6)

    def test_more_draws_in_one_trial_do_not_shift_the_next_trial_rng(self):
        request = NpcMeleeSimulationRequest(scenario(sizes=(1, 1)), 7, 2)
        wound, miss = [1, 2, 10, 10, 10, 10], [10] * 6
        def factory(extra):
            return lambda seed: SequenceRandom((miss * 2 * extra + wound) if seed == request.seed_for(0) else wound)
        short = run_npc_melee_simulation(request, rng_factory=factory(0))
        longer = run_npc_melee_simulation(request, rng_factory=factory(1))
        self.assertNotEqual(short.trials[0].executed_attack_count, longer.trials[0].executed_attack_count)
        self.assertEqual(short.trials[1], longer.trials[1])

    def test_terminal_suffix_and_dynamic_bonus_are_projected_without_extra_attacks(self):
        from unittest.mock import patch
        from towr.simulation import npc_melee_simulation as simulation
        from towr.domain.npc_rounds_models import NpcRoundsOutcome
        request = NpcMeleeSimulationRequest(scenario(), 42, 2)
        created = []
        def factory(seed):
            rng = Mock(wraps=SequenceRandom([1, 2, 10, 10, 10, 10, 1, 2, 10, 10, 10, 10, 10]))
            created.append(rng)
            return rng
        full_results = []
        runner = simulation.run_npc_melee_scenario
        def observe(source, rng):
            result = runner(source, rng)
            full_results.append(result)
            return result
        with patch.object(simulation, "run_npc_melee_scenario", side_effect=observe):
            result = run_npc_melee_simulation(request, rng_factory=factory)
        self.assertEqual([rng.randint.call_count for rng in created], [13, 13])
        for full in full_results:
            self.assertIs(full.runner_report.outcome, NpcRoundsOutcome.PENDING_FOLLOW_UPS)
            self.assertIsNotNone(full.terminal_acknowledgement)
            self.assertEqual(len(full.defeat_acknowledgements), 2)
            self.assertEqual(full.runner_report.newly_completed_round_count, 0)
            self.assertEqual(full.current.pending_follow_ups, ())
        summary = summarize(result)
        self.assertEqual(summary.outcome_counts, NpcMeleeOutcomeCounts(2, 0, 0, 0))
        self.assertEqual((summary.total_attack_count, summary.total_visited_round_count), (4, 2))
        self.assertEqual((summary.mean_attack_count, summary.mean_visited_round_count), (2, 1))
