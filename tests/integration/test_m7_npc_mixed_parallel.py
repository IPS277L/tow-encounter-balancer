from copy import deepcopy
from dataclasses import replace
from functools import partial
from multiprocessing import active_children
import os
import random
import unittest

from tests.helpers import SequenceRandom
from tests.unit.test_m7_npc_mixed_scenario import scenario
from tests.integration.test_m7_npc_mixed_simulation import four_outcome_request, WOUND, MISS
from towr.simulation.npc_mixed_models import NpcMixedSimulationRequest, NpcMixedOutcomeCounts
from towr.simulation.npc_mixed_simulation import run_npc_mixed_simulation
from towr.simulation.npc_mixed_parallel import run_npc_mixed_simulation_parallel
from towr.simulation.npc_mixed_summary import summarize_npc_mixed_simulation as summarize


def child_rng(seed, *, parent_pid):
    if os.getpid() == parent_pid:
        raise AssertionError("trial executed in parent")
    return random.Random(seed)


def exact_rng(seed, *, seeds):
    scripts = (MISS + WOUND + MISS + WOUND, MISS * 2 + WOUND * 2, MISS * 8, WOUND)
    return SequenceRandom(scripts[seeds.index(seed)])


def terminal_rng(seed, *, approved):
    return SequenceRandom(WOUND + WOUND + ([10] if approved else []))


def shifted_rng(seed, *, shifted_seed, draws):
    rng = random.Random(seed)
    if seed == shifted_seed:
        for _ in range(draws):
            rng.randint(1, 10)
    return rng


def failing_rng(seed, *, fail_seed):
    if seed == fail_seed:
        error = RuntimeError("injected mixed child failure")
        error.add_note("original factory context")
        raise error
    return random.Random(seed)


class M7ParallelIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.global_before = random.getstate()
        self.children_before = {child.pid for child in active_children()}

    def tearDown(self):
        self.assertEqual(random.getstate(), self.global_before)
        self.assertEqual({child.pid for child in active_children()}, self.children_before)

    def test_spawn_matches_sequential_across_workers_partitions_and_mixed_sizes(self):
        for sizes in ((2, 1), (3, 2), (2, 2)):
            source = NpcMixedSimulationRequest(scenario(sizes=sizes, enemy_bow=sizes == (2, 2)), 20260929, 7)
            before = deepcopy(source)
            expected = run_npc_mixed_simulation(source)
            for workers, batch_size in ((1, 3), (2, 1)):
                with self.subTest(sizes=sizes, workers=workers, batch_size=batch_size):
                    actual = run_npc_mixed_simulation_parallel(source, workers=workers, batch_size=batch_size,
                        rng_factory=partial(child_rng, parent_pid=os.getpid()))
                    self.assertEqual(actual, expected)
                    self.assertIs(actual.source_request, source)
                    self.assertEqual(summarize(actual), summarize(expected))
                    self.assertIs(summarize(actual).source_request, source)
            self.assertEqual(source, before)

    def test_four_real_scripted_outcomes_keep_terminal_suffix_and_unsupported(self):
        source = four_outcome_request()
        before = deepcopy(source)
        factory = partial(exact_rng, seeds=tuple(source.seed_for(i) for i in range(4)))
        expected = run_npc_mixed_simulation(source, rng_factory=factory)
        actual = run_npc_mixed_simulation_parallel(source, workers=2, batch_size=3, rng_factory=factory)
        self.assertEqual(actual, expected)
        self.assertEqual(summarize(actual), summarize(expected))
        self.assertEqual(actual.outcome_counts, NpcMixedOutcomeCounts(1, 1, 1, 1))
        self.assertEqual(tuple((t.executed_attack_count, t.visited_round_count) for t in actual.trials),
                         ((4, 2), (4, 1), (8, 2), (1, 1)))
        self.assertEqual((actual.total_attack_count, actual.total_visited_round_count), (17, 6))
        self.assertEqual(summarize(actual).trials, 4)
        self.assertEqual(source, before)

    def test_repeat_expanded_prefix_and_workers_exceeding_batches_preserve_records(self):
        source = four_outcome_request()
        small = run_npc_mixed_simulation_parallel(replace(source, trials=1), workers=2, batch_size=32,
            rng_factory=partial(child_rng, parent_pid=os.getpid()))
        first = run_npc_mixed_simulation_parallel(source, workers=1, batch_size=2)
        repeated = run_npc_mixed_simulation_parallel(source, workers=2, batch_size=8)
        expanded = run_npc_mixed_simulation_parallel(replace(source, trials=7), workers=2, batch_size=3)
        self.assertEqual(first, repeated)
        self.assertEqual(first, run_npc_mixed_simulation(source))
        self.assertEqual(small.trials, first.trials[:1])
        self.assertEqual(first.trials, expanded.trials[:4])

    def test_dynamic_outnumbering_and_gm_withholding_preserve_exact_terminal_counts(self):
        for approved in (True, False):
            with self.subTest(approved=approved):
                source = NpcMixedSimulationRequest(scenario(approved=approved), 7, 2)
                before = deepcopy(source)
                factory = partial(terminal_rng, approved=approved)
                expected = run_npc_mixed_simulation(source, rng_factory=factory)
                actual = run_npc_mixed_simulation_parallel(source, workers=2, batch_size=1, rng_factory=factory)
                self.assertEqual(actual, expected)
                self.assertEqual(summarize(actual), summarize(expected))
                self.assertEqual(actual.outcome_counts, NpcMixedOutcomeCounts(2, 0, 0, 0))
                self.assertEqual((actual.total_attack_count, actual.total_visited_round_count), (4, 2))
                self.assertEqual(source, before)

    def test_extra_draws_in_one_trial_do_not_shift_other_streams_in_workers(self):
        source = four_outcome_request()
        normal = run_npc_mixed_simulation(source)
        factory = partial(shifted_rng, shifted_seed=source.seed_for(0), draws=17)
        expected = run_npc_mixed_simulation(source, rng_factory=factory)
        actual = run_npc_mixed_simulation_parallel(source, workers=2, batch_size=3, rng_factory=factory)
        self.assertEqual(actual, expected)
        self.assertEqual(actual.trials[1:], normal.trials[1:])
        self.assertEqual(summarize(actual), summarize(expected))

    def test_child_failure_keeps_original_note_and_trial_context_without_partial_result(self):
        source = four_outcome_request()
        before = deepcopy(source)
        with self.assertRaisesRegex(RuntimeError, "injected mixed child failure") as caught:
            run_npc_mixed_simulation_parallel(source, workers=2, batch_size=2,
                rng_factory=partial(failing_rng, fail_seed=source.seed_for(1)))
        self.assertIn("original factory context", caught.exception.__notes__)
        self.assertIn(f"M7 trial index=1, seed={source.seed_for(1)}", caught.exception.__notes__)
        self.assertEqual(source, before)
