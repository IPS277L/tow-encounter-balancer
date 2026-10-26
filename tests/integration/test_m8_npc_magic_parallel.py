"""ADR-0039 real spawn transport over existing magic trials and finite scripts."""
from copy import deepcopy
from dataclasses import replace
from functools import partial
from multiprocessing import active_children
import os
from pathlib import Path
from random import Random, getstate
from tempfile import TemporaryDirectory
import unittest

from tests.integration.test_m8_npc_magic_simulation import simulation_scenario, SCRIPTS
from tests.unit.test_m8_npc_magic_scenario_runner import Dice
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome
from towr.simulation.npc_magic_models import NpcMagicOutcomeCounts, NpcMagicSimulationRequest
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation as summarize


def child_rng(seed, *, parent_pid):
    if os.getpid() == parent_pid:
        raise AssertionError('magic trial executed in parent instead of spawn child')
    return Random(seed)


def scripted_rng(seed, *, seeds, parent_pid=None):
    if parent_pid is not None and os.getpid() == parent_pid:
        raise AssertionError('scripted magic trial executed in parent')
    return Dice(SCRIPTS[seeds.index(seed)])


def empty_rng(seed, *, parent_pid=None):
    if parent_pid is not None and os.getpid() == parent_pid:
        raise AssertionError('zero-action magic trial executed in parent')
    return Dice(())


def shifted_rng(seed, *, shifted_seed, parent_pid=None):
    if parent_pid is not None and os.getpid() == parent_pid:
        raise AssertionError('shifted magic trial executed in parent')
    rng = Random(seed)
    if seed == shifted_seed:
        for _ in range(17):
            rng.randint(1, 10)
    return rng


def failing_rng(seed, *, seeds, marker, parent_pid):
    if os.getpid() == parent_pid:
        raise AssertionError('failing magic trial executed in parent')
    index = seeds.index(seed)
    with Path(marker).open('a', encoding='utf-8') as stream:
        stream.write(f'{index}\n')
    if index == 1:
        error = RuntimeError('injected magic child factory failure')
        error.add_note('original magic factory context')
        raise error
    return Random(seed)


class MagicParallelIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.global_before = getstate()
        self.children_before = {child.pid for child in active_children()}

    def tearDown(self):
        self.assertEqual(getstate(), self.global_before)
        self.assertEqual({child.pid for child in active_children()}, self.children_before)

    def assert_complete_equal(self, source, actual, expected):
        self.assertEqual(actual, expected)
        self.assertIs(actual.source_request, source)
        self.assertEqual(tuple(record.trial_index for record in actual.trials), tuple(range(source.trials)))
        self.assertEqual(tuple(record.seed for record in actual.trials),
                         tuple(source.seed_for(index) for index in range(source.trials)))
        self.assertTrue(all(record.source_scenario is source.scenario for record in actual.trials))
        summary = summarize(actual)
        self.assertEqual(summary, summarize(expected))
        self.assertIs(summary.source_request, source)

    def test_real_spawn_even_one_worker_matches_sequential_with_uneven_and_oversized_batches(self):
        source = NpcMagicSimulationRequest(simulation_scenario(), 20261026, 5)
        before = deepcopy(source)
        expected = run_npc_magic_simulation(source)
        # The last configuration covers both batch>N and workers>batches.
        for workers, batch_size in ((1, 2), (2, 2), (2, 32)):
            with self.subTest(workers=workers, batch_size=batch_size):
                actual = run_npc_magic_simulation_parallel(source, workers=workers, batch_size=batch_size,
                    rng_factory=partial(child_rng, parent_pid=os.getpid()))
                self.assert_complete_equal(source, actual, expected)
                self.assertEqual(source, before)

    def test_four_real_scripted_outcomes_keep_actions_rounds_unsupported_and_parent_identity(self):
        source = NpcMagicSimulationRequest(simulation_scenario(), 42, 4)
        before = deepcopy(source)
        seeds = tuple(source.seed_for(index) for index in range(source.trials))
        expected = run_npc_magic_simulation(source, rng_factory=partial(scripted_rng, seeds=seeds))
        observations = (
            (Outcome.OBJECTIVE_ACHIEVED, 2, 1, 1),
            (Outcome.PERSPECTIVE_DEFEATED, 9, 4, 4),
            (Outcome.ROUND_LIMIT_REACHED, 12, 4, 4),
            (Outcome.UNSUPPORTED_PATH, 1, 1, 0),
        )
        for workers in (1, 2):
            with self.subTest(workers=workers):
                actual = run_npc_magic_simulation_parallel(source, workers=workers, batch_size=3,
                    rng_factory=partial(scripted_rng, seeds=seeds, parent_pid=os.getpid()))
                self.assert_complete_equal(source, actual, expected)
                self.assertEqual(tuple((record.outcome, record.executed_action_count,
                    record.started_round_count, record.completed_round_count) for record in actual.trials), observations)
                self.assertEqual(actual.outcome_counts, NpcMagicOutcomeCounts(1, 1, 1, 1))
                self.assertEqual((actual.total_action_count, actual.total_started_round_count,
                                  actual.total_completed_round_count), (24, 10, 9))
                self.assertEqual(summarize(actual).trials, 4)
                self.assertEqual(source, before)

    def test_zero_action_missing_departure_is_preserved_without_any_rng_draws(self):
        original = simulation_scenario()
        scenario = replace(original, activation_order=('ally', 'wizard', 'enemy'),
            scene_frames=(replace(original.initial_frame, attack_departures=()),))
        source = NpcMagicSimulationRequest(scenario, 42, 3)
        before = deepcopy(source)
        expected = run_npc_magic_simulation(source, rng_factory=empty_rng)
        actual = run_npc_magic_simulation_parallel(source, workers=2, batch_size=2,
            rng_factory=partial(empty_rng, parent_pid=os.getpid()))
        self.assert_complete_equal(source, actual, expected)
        self.assertEqual(actual.outcome_counts, NpcMagicOutcomeCounts(0, 0, 0, 3))
        self.assertEqual(tuple((record.executed_action_count, record.started_round_count,
                               record.completed_round_count) for record in actual.trials), ((0, 1, 0),) * 3)
        self.assertEqual(source, before)

    def test_repeat_expanded_prefix_and_partition_changes_preserve_full_records(self):
        source = NpcMagicSimulationRequest(simulation_scenario(), 42, 4)
        before = deepcopy(source)
        first = run_npc_magic_simulation_parallel(source, workers=1, batch_size=2)
        repeated = run_npc_magic_simulation_parallel(source, workers=2, batch_size=8)
        expanded_source = replace(source, trials=7)
        expanded = run_npc_magic_simulation_parallel(expanded_source, workers=2, batch_size=3)
        self.assert_complete_equal(source, repeated, first)
        self.assert_complete_equal(source, first, run_npc_magic_simulation(source))
        self.assert_complete_equal(expanded_source, expanded, run_npc_magic_simulation(expanded_source))
        self.assertEqual(expanded.trials[:4], first.trials)
        self.assertTrue(all(record.source_scenario is source.scenario for record in expanded.trials))
        self.assertEqual(source, before)

    def test_extra_draws_in_one_trial_do_not_shift_other_worker_streams(self):
        source = NpcMagicSimulationRequest(simulation_scenario(), 42, 4)
        before = deepcopy(source)
        ordinary = run_npc_magic_simulation(source)
        factory = partial(shifted_rng, shifted_seed=source.seed_for(0))
        expected = run_npc_magic_simulation(source, rng_factory=factory)
        actual = run_npc_magic_simulation_parallel(source, workers=2, batch_size=3,
            rng_factory=partial(shifted_rng, shifted_seed=source.seed_for(0), parent_pid=os.getpid()))
        self.assert_complete_equal(source, actual, expected)
        self.assertEqual(actual.trials[1:], ordinary.trials[1:])
        self.assertEqual(source, before)

    def test_child_failure_preserves_type_message_notes_and_stops_next_index_in_same_batch(self):
        source = NpcMagicSimulationRequest(simulation_scenario(), 42, 3)
        before = deepcopy(source)
        with TemporaryDirectory() as directory:
            marker = Path(directory) / 'factory-indices.txt'
            with self.assertRaisesRegex(RuntimeError, 'injected magic child factory failure') as caught:
                run_npc_magic_simulation_parallel(source, workers=1, batch_size=3,
                    rng_factory=partial(failing_rng, seeds=tuple(source.seed_for(index) for index in range(3)),
                                        marker=str(marker), parent_pid=os.getpid()))
            self.assertIs(type(caught.exception), RuntimeError)
            self.assertEqual(str(caught.exception), 'injected magic child factory failure')
            self.assertIn('original magic factory context', caught.exception.__notes__)
            self.assertIn(f'M8 trial index=1, seed={source.seed_for(1)}', caught.exception.__notes__)
            self.assertEqual(marker.read_text(encoding='utf-8').splitlines(), ['0', '1'])
        self.assertEqual(source, before)


if __name__ == '__main__':
    unittest.main()
