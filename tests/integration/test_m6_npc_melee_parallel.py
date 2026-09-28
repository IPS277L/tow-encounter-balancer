from copy import deepcopy
from dataclasses import replace
from functools import partial
from multiprocessing import active_children
import os
import random
import unittest

from tests.helpers import SequenceRandom
from tests.unit.test_m6_npc_melee_scenario import scenario
from towr.simulation.npc_melee_models import NpcMeleeSimulationRequest, NpcMeleeOutcomeCounts
from towr.simulation.npc_melee_simulation import run_npc_melee_simulation
from towr.simulation.npc_melee_parallel import run_npc_melee_simulation_parallel
from towr.simulation.npc_melee_summary import summarize_npc_melee_simulation as summarize


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


def terminal_rng(seed):
    # Two kills: the second Attack gains one die from the updated outnumbering.
    return SequenceRandom([1, 2, 10, 10, 10, 10, 1, 2, 10, 10, 10, 10, 10])


def blocked_rng(seed):
    # Test-only, one-shot controller stop. Restore before returning the decision;
    # preserve every candidate so the scenario's source guards still apply.
    from towr.engine import npc_round_coordinator as coordinator
    from towr.domain.npc_attack_selection_models import (
        NpcAttackSelectionResult, NpcAttackSelectionBlock,
        RejectedNpcAttackCandidate, NpcAttackCandidateRejection,
    )
    original = coordinator.select_npc_attack
    def reject_once(context):
        coordinator.select_npc_attack = original
        return NpcAttackSelectionResult(context, None, None, tuple(
            RejectedNpcAttackCandidate(candidate.id, NpcAttackCandidateRejection.ATTACK_CONTEXT, "technical stop")
            for candidate in context.candidates), NpcAttackSelectionBlock.NO_CANDIDATE)
    coordinator.select_npc_attack = reject_once
    return SequenceRandom(())  # A technical stop must not consume any dice.


class M6ParallelIntegrationTests(unittest.TestCase):
    def test_spawn_matches_sequential_for_workers_partitions_and_all_benchmark_sizes(self):
        global_before = random.getstate()
        children_before = {child.pid for child in active_children()}
        for sizes in ((1, 1), (2, 2), (3, 2)):
            source = NpcMeleeSimulationRequest(scenario(sizes=sizes), 20260928, 7)
            before = deepcopy(source)
            sequential = run_npc_melee_simulation(source)
            for workers, batch_size in ((1, 3), (2, 1)):
                with self.subTest(sizes=sizes, workers=workers, batch_size=batch_size):
                    actual = run_npc_melee_simulation_parallel(source, workers=workers, batch_size=batch_size,
                        rng_factory=partial(child_rng, parent_pid=os.getpid()))
                    self.assertEqual(actual, sequential)
                    self.assertIs(actual.source_request, source)
                    self.assertEqual(summarize(actual), summarize(sequential))
            self.assertEqual(source, before)
        self.assertEqual(random.getstate(), global_before)
        self.assertEqual({child.pid for child in active_children()}, children_before)

    def test_injected_rng_preserves_exact_outcomes_and_extended_batch_prefix(self):
        source = NpcMeleeSimulationRequest(scenario(sizes=(1, 1)), 123, 3)
        factory = partial(exact_rng, seeds=tuple(source.seed_for(i) for i in range(3)))
        expected = run_npc_melee_simulation(source, rng_factory=factory)
        actual = run_npc_melee_simulation_parallel(source, workers=2, batch_size=2, rng_factory=factory)
        self.assertEqual(actual, expected)
        self.assertEqual(summarize(actual), summarize(expected))
        self.assertEqual((actual.outcome_counts.objective_achieved, actual.outcome_counts.side_defeated,
                          actual.outcome_counts.round_limit), (1, 1, 1))
        small = run_npc_melee_simulation_parallel(replace(source, trials=1), workers=2, batch_size=8)
        large = run_npc_melee_simulation_parallel(source, workers=1, batch_size=1)
        self.assertEqual(small.trials, large.trials[:1])

    def test_terminal_suffix_and_dynamic_bonus_match_without_extra_rounds(self):
        source = NpcMeleeSimulationRequest(scenario(), 42, 3)
        expected = run_npc_melee_simulation(source, rng_factory=terminal_rng)
        actual = run_npc_melee_simulation_parallel(source, workers=2, batch_size=2, rng_factory=terminal_rng)
        self.assertEqual(actual, expected)
        summary = summarize(actual)
        self.assertEqual(summary, summarize(expected))
        self.assertEqual(summary.outcome_counts, NpcMeleeOutcomeCounts(3, 0, 0, 0))
        self.assertEqual((summary.total_attack_count, summary.total_visited_round_count), (6, 3))

    def test_source_consistent_controller_stop_remains_unsupported_in_child(self):
        from towr.engine import npc_round_coordinator as coordinator
        original = coordinator.select_npc_attack
        source = NpcMeleeSimulationRequest(scenario(sizes=(1, 1)), 42, 3)
        expected = run_npc_melee_simulation(source, rng_factory=blocked_rng)
        self.assertIs(coordinator.select_npc_attack, original)
        children_before = {child.pid for child in active_children()}
        actual = run_npc_melee_simulation_parallel(source, workers=1, batch_size=2, rng_factory=blocked_rng)
        self.assertEqual(actual, expected)
        self.assertEqual(summarize(actual), summarize(expected))
        self.assertEqual(actual.outcome_counts, NpcMeleeOutcomeCounts(0, 0, 0, 3))
        self.assertEqual((actual.total_attack_count, actual.total_visited_round_count), (0, 3))
        self.assertIs(coordinator.select_npc_attack, original)
        self.assertEqual({child.pid for child in active_children()}, children_before)

    def test_child_exception_propagates_with_index_and_pool_is_closed(self):
        source = NpcMeleeSimulationRequest(scenario(sizes=(1, 1)), 42, 4)
        before = deepcopy(source)
        global_before = random.getstate()
        children_before = {child.pid for child in active_children()}
        with self.assertRaisesRegex(RuntimeError, "injected child RNG failure") as caught:
            run_npc_melee_simulation_parallel(source, workers=2, batch_size=2,
                rng_factory=partial(failing_rng, fail_seed=source.seed_for(1)))
        self.assertIn(f"index=1, seed={source.seed_for(1)}", caught.exception.__notes__[0])
        self.assertEqual(source, before)
        self.assertEqual(random.getstate(), global_before)
        self.assertEqual({child.pid for child in active_children()}, children_before)
