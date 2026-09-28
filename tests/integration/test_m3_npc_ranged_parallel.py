from copy import deepcopy
from dataclasses import replace
from functools import partial
from multiprocessing import active_children
import os
import random
import unittest

from tests.helpers import SequenceRandom
from tests.unit.test_m2_npc_ranged_scenario import scenario
from towr.simulation.npc_ranged_models import NpcRangedSimulationRequest
from towr.simulation.npc_ranged_simulation import run_npc_ranged_simulation
from towr.simulation.npc_ranged_parallel import run_npc_ranged_simulation_parallel


def child_rng(seed, *, parent_pid):
    if os.getpid() == parent_pid:
        raise AssertionError("trial executed in parent")
    return random.Random(seed)


def failing_rng(seed, *, fail_seed):
    if seed == fail_seed:
        raise RuntimeError("injected child RNG failure")
    return random.Random(seed)


def exact_rng(seed, *, seeds):
    wound, miss = [1, 2, 10, 10, 10, 10], [10] * 6
    return SequenceRandom((wound, miss + wound, miss * 6)[seeds.index(seed)])


class M3ParallelIntegrationTests(unittest.TestCase):
    def test_spawn_matches_sequential_for_workers_partitions_and_all_benchmark_sizes(self):
        global_before = random.getstate()
        children_before = {child.pid for child in active_children()}
        for sizes in ((1, 1), (2, 2), (3, 2)):
            source = NpcRangedSimulationRequest(scenario(sizes=sizes), 20260928, 7)
            before = deepcopy(source)
            sequential = run_npc_ranged_simulation(source)
            for workers, batch_size in ((1, 3), (2, 1)):
                with self.subTest(sizes=sizes, workers=workers, batch_size=batch_size):
                    actual = run_npc_ranged_simulation_parallel(source, workers=workers, batch_size=batch_size,
                        rng_factory=partial(child_rng, parent_pid=os.getpid()))
                    self.assertEqual(actual, sequential)
                    self.assertIs(actual.source_request, source)
            self.assertEqual(source, before)
        self.assertEqual(random.getstate(), global_before)
        self.assertEqual({child.pid for child in active_children()}, children_before)

    def test_injected_rng_preserves_exact_outcomes_and_extended_batch_prefix(self):
        source = NpcRangedSimulationRequest(scenario(sizes=(1, 1)), 123, 3)
        factory = partial(exact_rng, seeds=tuple(source.seed_for(i) for i in range(3)))
        expected = run_npc_ranged_simulation(source, rng_factory=factory)
        actual = run_npc_ranged_simulation_parallel(source, workers=2, batch_size=2, rng_factory=factory)
        self.assertEqual(actual, expected)
        self.assertEqual((actual.outcome_counts.objective_achieved, actual.outcome_counts.side_defeated,
                          actual.outcome_counts.round_limit), (1, 1, 1))
        small = run_npc_ranged_simulation_parallel(replace(source, trials=1), workers=2, batch_size=8)
        large = run_npc_ranged_simulation_parallel(source, workers=1, batch_size=1)
        self.assertEqual(small.trials, large.trials[:1])

    def test_child_exception_propagates_with_index_and_pool_is_closed(self):
        source = NpcRangedSimulationRequest(scenario(sizes=(1, 1)), 42, 4)
        before = deepcopy(source)
        children_before = {child.pid for child in active_children()}
        with self.assertRaisesRegex(RuntimeError, "injected child RNG failure") as caught:
            run_npc_ranged_simulation_parallel(source, workers=2, batch_size=2,
                rng_factory=partial(failing_rng, fail_seed=source.seed_for(1)))
        self.assertIn(f"index=1, seed={source.seed_for(1)}", caught.exception.__notes__[0])
        self.assertEqual(source, before)
        self.assertEqual({child.pid for child in active_children()}, children_before)
