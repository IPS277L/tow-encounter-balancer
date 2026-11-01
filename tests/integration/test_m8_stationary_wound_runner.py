"""ADR-0050 native stationary policy survives trial, sequential and spawn paths."""
from copy import deepcopy
from fractions import Fraction
from functools import partial
from multiprocessing import active_children
import os
from random import Random, getstate
import unittest

from tests.unit.test_m8_npc_magic_scenario_runner import Dice
from tests.unit.test_m8_stationary_wound_runner import FULL_CHAIN, HIT, scenario
from towr.balance.magic_assessment import assess_magic_candidate
from towr.balance.magic_assessment_models import MagicAssessmentStatus, ObjectiveRateWindow
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome
from towr.simulation.npc_magic_models import NpcMagicOutcomeCounts, NpcMagicSimulationRequest
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation, run_npc_magic_trial
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation as summarize


SCRIPTS = (FULL_CHAIN, (*HIT, 10))


def scripted_rng(seed, *, seeds, parent_pid=None):
    if parent_pid is not None and os.getpid() == parent_pid:
        raise AssertionError('spawn trial must run in a child')
    return Dice(SCRIPTS[seeds.index(seed)])


def child_random(seed, *, parent_pid):
    if os.getpid() == parent_pid:
        raise AssertionError('seeded trial must run in a child')
    return Random(seed)


class StationaryWoundPropagationTests(unittest.TestCase):
    def setUp(self):
        self.rng_before = getstate()
        self.children_before = {p.pid for p in active_children()}

    def tearDown(self):
        self.assertEqual(getstate(), self.rng_before)
        self.assertEqual({p.pid for p in active_children()}, self.children_before)

    def test_actual_scripted_trial_counts_actions_not_stand_or_expiry_phases(self):
        request = NpcMagicSimulationRequest(scenario(), 42, 1)
        before = deepcopy(request)
        dice = Dice(FULL_CHAIN)
        record = run_npc_magic_trial(request, 0, rng_factory=lambda seed: dice)
        dice.exhausted()
        self.assertEqual((record.outcome, record.executed_action_count,
                          record.started_round_count, record.completed_round_count),
                         (Outcome.ROUND_LIMIT_REACHED, 9, 3, 3))
        self.assertIs(record.source_scenario, request.scenario)
        self.assertIs(record.source_scenario.stationary_wound_continuation,
                      request.scenario.stationary_wound_continuation)
        self.assertEqual(request, before)

    def test_scripted_sequential_spawn_and_assessment_preserve_source_and_unsupported_denominator(self):
        request = NpcMagicSimulationRequest(scenario(), 42, 2)
        before = deepcopy(request)
        seeds = tuple(request.seed_for(i) for i in range(2))
        sequential = run_npc_magic_simulation(request, rng_factory=partial(scripted_rng, seeds=seeds))
        spawned = run_npc_magic_simulation_parallel(request, workers=1, batch_size=1,
            rng_factory=partial(scripted_rng, seeds=seeds, parent_pid=os.getpid()))
        self.assertEqual(sequential, spawned)
        self.assertEqual(summarize(sequential), summarize(spawned))
        for result in (sequential, spawned):
            self.assertIs(result.source_request, request)
            self.assertEqual(result.outcome_counts, NpcMagicOutcomeCounts(0, 0, 1, 1))
            self.assertEqual(tuple(r.seed for r in result.trials), seeds)
            self.assertTrue(all(r.source_scenario is request.scenario for r in result.trials))
            summary = summarize(result)
            self.assertEqual(summary.trials, 2)
            assessment = assess_magic_candidate(request, summary,
                ObjectiveRateWindow(Fraction(0), Fraction(1, 2), Fraction(1)))
            self.assertEqual(assessment.unsupported_path_rate, Fraction(1, 2))
            self.assertEqual(assessment.round_limit_rate, Fraction(1, 2))
            self.assertIs(assessment.status, MagicAssessmentStatus.UNSUPPORTED_OBSERVATIONS)
            self.assertIsNone(assessment.window_match)
        self.assertEqual(request, before)

    def test_default_seeded_sequential_and_spawn_keep_full_native_records(self):
        request = NpcMagicSimulationRequest(scenario(miscast=True), 613, 3)
        before = deepcopy(request)
        sequential = run_npc_magic_simulation(request)
        spawned = run_npc_magic_simulation_parallel(request, workers=1, batch_size=2,
            rng_factory=partial(child_random, parent_pid=os.getpid()))
        self.assertEqual(spawned, sequential)
        self.assertEqual(summarize(spawned), summarize(sequential))
        self.assertIs(spawned.source_request, request)
        self.assertTrue(all(r.source_scenario is request.scenario for r in spawned.trials))
        self.assertEqual(request, before)


if __name__ == '__main__':
    unittest.main()
