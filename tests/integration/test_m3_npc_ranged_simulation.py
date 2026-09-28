from copy import deepcopy
from dataclasses import replace
import random
import unittest
from unittest.mock import Mock

from tests.helpers import SequenceRandom
from tests.unit.test_m2_npc_ranged_scenario import scenario
from towr.simulation.npc_ranged_models import NpcRangedSimulationRequest, NpcRangedSimulationResult, NpcRangedOutcomeCounts
from towr.simulation.npc_ranged_simulation import run_npc_ranged_simulation, run_npc_ranged_trial


class M3NpcRangedSimulationIntegrationTests(unittest.TestCase):
    def test_real_trials_have_exact_aggregates_and_distinct_injected_rng(self):
        source = scenario(sizes=(1, 1))
        source = replace(source, initial=replace(source.initial, max_rounds=2))
        request = NpcRangedSimulationRequest(source, 17, 3)
        before = deepcopy(request)
        wound, miss = [1, 2, 10, 10, 10, 10], [10] * 6
        values = {request.seed_for(0): wound, request.seed_for(1): miss + wound, request.seed_for(2): miss * 4}
        created = []
        def make_rng(seed):
            rng = Mock(wraps=SequenceRandom(values[seed]))
            created.append(rng)
            return rng
        factory = Mock(side_effect=make_rng)
        result = run_npc_ranged_simulation(request, rng_factory=factory)
        self.assertEqual(result.outcome_counts, NpcRangedOutcomeCounts(1, 1, 1, 0))
        self.assertEqual(result.total_attack_count, 7)
        self.assertEqual(result.total_visited_round_count, 4)
        self.assertEqual([r.randint.call_count for r in created], [6, 12, 24])
        self.assertEqual([call.args[0] for call in factory.call_args_list], [request.seed_for(i) for i in range(3)])
        self.assertEqual(len({id(rng) for rng in created}), 3)
        self.assertEqual(request, before)

    def test_default_rng_replay_reverse_order_and_larger_batch_preserve_each_index(self):
        request = NpcRangedSimulationRequest(scenario(), 12345, 6)
        global_before = random.getstate()
        result = run_npc_ranged_simulation(request)
        self.assertEqual(result, run_npc_ranged_simulation(request))
        reversed_trials = tuple(run_npc_ranged_trial(request, index) for index in reversed(range(request.trials)))
        self.assertEqual(result, NpcRangedSimulationResult(request, reversed_trials))
        larger = run_npc_ranged_simulation(replace(request, trials=9))
        self.assertEqual(result.trials, larger.trials[:6])
        self.assertEqual(global_before, random.getstate())
        self.assertEqual(sum((result.outcome_counts.objective_achieved, result.outcome_counts.side_defeated,
                              result.outcome_counts.round_limit, result.outcome_counts.unsupported_path)), 6)

    def test_more_draws_in_one_trial_do_not_shift_the_next_trial_rng(self):
        request = NpcRangedSimulationRequest(scenario(sizes=(1, 1)), 7, 2)
        wound, miss = [1, 2, 10, 10, 10, 10], [10] * 6
        def factory(extra):
            return lambda seed: SequenceRandom((miss * 2 * extra + wound) if seed == request.seed_for(0) else wound)
        short = run_npc_ranged_simulation(request, rng_factory=factory(0))
        longer = run_npc_ranged_simulation(request, rng_factory=factory(1))
        self.assertNotEqual(short.trials[0].executed_attack_count, longer.trials[0].executed_attack_count)
        self.assertEqual(short.trials[1], longer.trials[1])
