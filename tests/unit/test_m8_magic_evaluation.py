"""ADR-0040 finite magic-list models and exact ranking, without execution."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from fractions import Fraction as F
import pickle
import unittest
from unittest.mock import patch

from tests.unit.test_m8_npc_magic_scenario import scenario, OPPOSITION
from towr.balance.magic_assessment import assess_magic_candidate
from towr.balance.magic_assessment_models import ObjectiveRateWindow as Window
from towr.balance.magic_evaluation_models import (
    MagicBalanceCandidate as Candidate, MagicBalanceCandidateResult as CandidateResult,
    MagicBalanceEvaluationRequest as Request, MagicBalanceEvaluationResult as Result,
)
from towr.balance.ranged_assessment_models import ObjectiveRateWindow as SharedWindow
from towr.domain.npc_magic_scenario_result_models import NpcMagicScenarioResult
from towr.domain.test_models import InlineProfile
from towr.simulation.npc_magic_models import (
    SEED_SCHEME, NpcMagicOutcomeCounts as Counts, NpcMagicSimulationResult, NpcMagicTrialRecord,
)
from towr.simulation.npc_magic_summary_models import NpcMagicSimulationSummary as Summary


def request(count=3, trials=4):
    source = scenario()
    return Request(tuple(Candidate(f'candidate:{i}', source) for i in range(count)),
                   42, trials, count * trials, Window(F(1, 4), F(1, 2), F(3, 4)), 2)


def candidate_result(source, index, achieved, unsupported=0):
    simulation = source.simulation_requests[index]
    n = simulation.trials
    summary = Summary(simulation, Counts(achieved, n - achieved - unsupported, 0, unsupported),
                      n - unsupported, n, 0)
    return CandidateResult(source.candidates[index].candidate_id,
                           assess_magic_candidate(simulation, summary, source.window))


class MagicEvaluationModelTests(unittest.TestCase):
    def test_request_copies_list_preserves_sources_and_rebuilds_derived_requests(self):
        source = request()
        mutable = list(source.candidates)
        actual = replace(source, candidates=mutable)
        mutable.clear()
        self.assertEqual(actual, source)
        self.assertEqual(actual.planned_trials, 12)
        self.assertIsInstance(actual.candidates, tuple)
        for candidate, simulation in zip(actual.candidates, actual.simulation_requests):
            self.assertIs(simulation.scenario, candidate.scenario)
            self.assertEqual((simulation.master_seed, simulation.trials), (42, 4))
        self.assertEqual(len({s.seed_for(2) for s in actual.simulation_requests}), 1)
        changed = replace(actual, master_seed=43, trials_per_candidate=2, candidates=actual.candidates[::-1])
        self.assertEqual(changed.planned_trials, 6)
        self.assertEqual(tuple(s.scenario for s in changed.simulation_requests),
                         tuple(c.scenario for c in changed.candidates))
        self.assertTrue(all((s.master_seed, s.trials) == (43, 2) for s in changed.simulation_requests))
        self.assertTrue(all(new is not old for new, old in zip(changed.simulation_requests, actual.simulation_requests)))
        self.assertNotEqual(changed.simulation_requests[0].seed_for(0), actual.simulation_requests[0].seed_for(0))
        derived = next(f for f in fields(actual) if f.name == 'simulation_requests')
        self.assertFalse(derived.init or derived.repr or derived.compare)
        with self.assertRaises((TypeError, ValueError)):
            replace(actual, simulation_requests=())

    def test_ids_have_strict_types_exact_uniqueness_and_no_normalization(self):
        source = request()
        for wrong in (None, 1, True, F(1), object()):
            with self.subTest(wrong=wrong):
                with self.assertRaises(TypeError): Candidate(wrong, source.candidates[0].scenario)
                with self.assertRaises(TypeError): CandidateResult(wrong, candidate_result(source, 0, 1).assessment)
        for empty in ('', ' ', '\t\n'):
            with self.subTest(empty=empty):
                with self.assertRaises(ValueError): Candidate(empty, source.candidates[0].scenario)
                with self.assertRaises(ValueError): CandidateResult(empty, candidate_result(source, 0, 1).assessment)
        for candidates in ((), (source.candidates[0], source.candidates[0])):
            with self.subTest(candidates=candidates), self.assertRaises(ValueError):
                replace(source, candidates=candidates)
        spaced = Candidate(' candidate:0 ', source.candidates[0].scenario)
        actual = replace(source, candidates=(spaced, source.candidates[0]))
        self.assertEqual(tuple(c.candidate_id for c in actual.candidates), (' candidate:0 ', 'candidate:0'))
        self.assertIs(actual.candidates[0].scenario, actual.candidates[1].scenario)
        self.assertEqual(actual.candidates[0].scenario.id, actual.candidates[1].scenario.id)

    def test_ordered_sequences_reject_wrong_containers_without_consuming_generators(self):
        source = request()
        rows = tuple(candidate_result(source, i, 2) for i in range(3))
        for wrong in (None, {}, set(), 'candidates', 1):
            with self.subTest(wrong=wrong):
                with self.assertRaises(TypeError): replace(source, candidates=wrong)
                with self.assertRaises(TypeError): Result(source, wrong)
        consumed = []
        def candidates():
            consumed.append('candidate')
            yield source.candidates[0]
        def results():
            consumed.append('row')
            yield rows[0]
        with self.assertRaises(TypeError): replace(source, candidates=candidates())
        with self.assertRaises(TypeError): Result(source, results())
        self.assertEqual(consumed, [])
        with self.assertRaises(TypeError): replace(source, candidates=(None,))
        with self.assertRaises(TypeError): Result(source, (None,))
        with self.assertRaises(TypeError): Candidate('id', None)
        with self.assertRaises(TypeError): CandidateResult('id', None)
        with self.assertRaises(TypeError): Result(None, rows)
        with self.assertRaises(TypeError): replace(source, window=(F(0), F(1, 2), F(1)))

    def test_preflight_requires_strict_numbers_full_budget_and_does_not_execute(self):
        source = request()
        with ExitStack() as stack:
            for target in ('random.Random', 'towr.simulation.npc_magic_simulation.run_npc_magic_simulation',
                           'towr.simulation.npc_magic_parallel.run_npc_magic_simulation_parallel',
                           'concurrent.futures.ProcessPoolExecutor'):
                stack.enter_context(patch(target, side_effect=AssertionError('models must not execute')))
            for name in ('master_seed', 'trials_per_candidate', 'max_total_trials', 'top_k'):
                for wrong in (True, False, 1.5, '4', None):
                    with self.subTest(name=name, wrong=wrong), self.assertRaises(TypeError):
                        replace(source, **{name: wrong})
                with self.subTest(name=name), self.assertRaises(ValueError):
                    replace(source, **{name: -1})
            for name in ('trials_per_candidate', 'max_total_trials', 'top_k'):
                with self.subTest(name=name), self.assertRaises(ValueError): replace(source, **{name: 0})
            for name in ('master_seed', 'trials_per_candidate'):
                with self.subTest(name=name), self.assertRaises(ValueError): replace(source, **{name: 2**64})
            with self.assertRaises(ValueError): replace(source, max_total_trials=source.planned_trials - 1)
            self.assertEqual(replace(source, max_total_trials=source.planned_trials).planned_trials, 12)
            self.assertEqual(replace(source, master_seed=0).master_seed, 0)
            self.assertEqual(replace(source, top_k=100).top_k, 100)

    def test_total_budget_can_exceed_uint64_without_enumerating_trials(self):
        n = 2**64 - 1
        source = request(count=3, trials=n)
        self.assertEqual(source.planned_trials, 3 * n)
        self.assertGreater(source.planned_trials, 2**64)
        self.assertEqual(len(source.simulation_requests), 3)
        self.assertTrue(all(s.trials == n for s in source.simulation_requests))
        with self.assertRaises(ValueError): replace(source, max_total_trials=3 * n - 1)

    def test_candidates_share_perspective_and_scenario_max_rounds(self):
        source = request()
        different = (replace(source.candidates[0].scenario, max_rounds=4), scenario(perspective=OPPOSITION))
        for changed in different:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                replace(source, candidates=(*source.candidates[:-1], Candidate('last', changed)))

    def test_selection_keeps_full_report_filters_unsupported_and_preserves_tie_order(self):
        source = request(count=5)
        rows = (candidate_result(source, 0, 1), candidate_result(source, 1, 3),
                candidate_result(source, 2, 2), candidate_result(source, 3, 4), candidate_result(source, 4, 2, 1))
        result = Result(source, rows)
        self.assertEqual(result.selected_candidate_ids, ('candidate:2', 'candidate:0'))
        self.assertEqual(result.candidates, rows)
        self.assertIsNone(result.candidates[4].assessment.window_match)
        self.assertEqual(result.total_trials, source.planned_trials)
        self.assertEqual(result.seed_scheme, SEED_SCHEME)
        self.assertEqual(Result(replace(source, top_k=100), rows).selected_candidate_ids,
                         ('candidate:2', 'candidate:0', 'candidate:1'))
        order = (1, 0, 2, 3, 4)
        reordered = replace(source, candidates=tuple(source.candidates[i] for i in order))
        self.assertEqual(Result(reordered, tuple(rows[i] for i in order)).selected_candidate_ids,
                         ('candidate:2', 'candidate:1'))

    def test_empty_selection_never_falls_back_to_outside_or_unsupported(self):
        source = request(count=2)
        rows = (candidate_result(source, 0, 0), candidate_result(source, 1, 2, 1))
        result = Result(source, rows)
        self.assertEqual(result.selected_candidate_ids, ())
        self.assertEqual(result.candidates, rows)
        self.assertEqual(result.total_trials, 8)

    def test_ranking_preserves_exact_fraction_distances_when_floats_tie(self):
        n = 2**60 + 1
        source = replace(request(count=2, trials=n), top_k=1)
        rows = (candidate_result(source, 0, n // 2 - 1), candidate_result(source, 1, n // 2))
        self.assertEqual(float(rows[0].assessment.objective_achieved_rate), float(rows[1].assessment.objective_achieved_rate))
        self.assertGreater(abs(rows[0].assessment.objective_achieved_rate - source.window.target),
                           abs(rows[1].assessment.objective_achieved_rate - source.window.target))
        self.assertEqual(Result(source, rows).selected_candidate_ids, ('candidate:1',))

    def test_result_rejects_partial_reordered_duplicate_or_foreign_id_and_window(self):
        source = request()
        rows = tuple(candidate_result(source, i, i + 1) for i in range(3))
        for invalid in ((), rows[:-1], rows[::-1], (rows[0], rows[0], rows[2]),
                        (replace(rows[0], candidate_id='foreign'), *rows[1:])):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError): Result(source, invalid)
        with self.assertRaises(ValueError): Result(replace(source, window=Window(F(0), F(1, 2), F(1))), rows)
        equal_copy = deepcopy(source)
        result = Result(equal_copy, rows)
        self.assertIs(result.source_request, equal_copy)
        self.assertEqual(result.candidates, rows)
        self.assertIs(result.candidates[0], rows[0])

    def test_report_checks_full_seed_n_and_same_id_magic_scenario_not_only_labels(self):
        source = request()
        rows = tuple(candidate_result(source, i, 2) for i in range(3))
        first = source.candidates[0].scenario
        changed_level = replace(first, initial=replace(first.initial, wizard=replace(first.initial.wizard,
            caster=replace(first.initial.wizard.caster, wizard_level=3))))
        changed_profile = replace(first, actors=tuple(replace(a, willpower_profile=InlineProfile(2, 3))
            if a.actor_id == 'enemy' else a for a in first.actors))
        changed_priority = replace(first, actors=tuple(replace(a, zone_priorities=a.zone_priorities[::-1])
            if a.actor_id == 'wizard' else a for a in first.actors))
        changed_order = replace(first, activation_order=first.activation_order[::-1])
        changed_requests = (replace(source, master_seed=43),
                            replace(source, trials_per_candidate=5, max_total_trials=15),
                            *(replace(source, candidates=(replace(source.candidates[0], scenario=s), *source.candidates[1:]))
                              for s in (changed_level, changed_profile, changed_priority, changed_order)))
        for changed in changed_requests:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                Result(source, (candidate_result(changed, 0, 2), *rows[1:]))

    def test_magic_alternatives_and_candidate_rename_preserve_full_inputs_and_seed_scheme(self):
        source = request(count=2)
        alternatives = (scenario(blocker=True), scenario(enemy_zone='middle'))
        source = replace(source, candidates=tuple(Candidate(f'magic:{i}', s) for i, s in enumerate(alternatives)))
        for c, s in zip(source.candidates, source.simulation_requests):
            self.assertIs(s.scenario, c.scenario)
            self.assertIs(s.scenario.scene_frames, c.scenario.scene_frames)
            self.assertIs(s.scenario.actors, c.scenario.actors)
        renamed = replace(source, candidates=tuple(replace(c, candidate_id=f'renamed:{i}')
                                                   for i, c in enumerate(source.candidates)))
        self.assertEqual(renamed.simulation_requests, source.simulation_requests)
        self.assertEqual(tuple(s.seed_for(1) for s in renamed.simulation_requests),
                         tuple(s.seed_for(1) for s in source.simulation_requests))
        rows = tuple(candidate_result(renamed, i, 2) for i in range(2))
        self.assertEqual(Result(renamed, rows).selected_candidate_ids, ('renamed:0', 'renamed:1'))

    def test_other_families_scenarios_candidates_requests_rows_and_assessments_are_rejected(self):
        from tests.unit.test_m5_ranged_evaluation import request as ranged_request, candidate_result as ranged_row
        from tests.unit.test_m6_melee_evaluation import request as melee_request, candidate_result as melee_row
        from tests.unit.test_m7_mixed_evaluation import request as mixed_request, candidate_result as mixed_row
        source = request()
        for make, make_row in ((ranged_request, ranged_row), (melee_request, melee_row), (mixed_request, mixed_row)):
            foreign = make()
            row = make_row(foreign, 0, 1)
            builds = (lambda: Candidate('one', foreign.candidates[0].scenario),
                      lambda: replace(source, candidates=foreign.candidates),
                      lambda: CandidateResult('one', row.assessment),
                      lambda: Result(foreign, ()),
                      lambda: Result(source, (row,) * len(source.candidates)))
            for build in builds:
                with self.subTest(family=type(foreign).__name__, build=build), self.assertRaises(TypeError): build()

    def test_immutable_pickle_ownership_and_derived_values_reject_overrides(self):
        source = request()
        before = deepcopy(source)
        rows = [candidate_result(source, i, 2) for i in range(3)]
        result = Result(source, rows)
        rows.clear()
        self.assertEqual(len(result.candidates), 3)
        self.assertIs(result.source_request, source)
        self.assertEqual(source, before)
        for item, name, wrong in ((source, 'top_k', 1), (source.candidates[0], 'candidate_id', 'new'),
                                  (result, 'candidates', ()), (result.candidates[0], 'assessment', None)):
            self.assertFalse(hasattr(item, '__dict__'))
            with self.subTest(item=type(item)), self.assertRaises(FrozenInstanceError): setattr(item, name, wrong)
        with self.assertRaises(TypeError): replace(source, planned_trials=1)
        for name in ('selected_candidate_ids', 'total_trials', 'seed_scheme'):
            with self.subTest(name=name), self.assertRaises(TypeError): replace(result, **{name: None})
        restored = pickle.loads(pickle.dumps(result))
        self.assertEqual(restored, result)
        self.assertIs(type(restored.source_request.window), SharedWindow)
        self.assertEqual(restored.selected_candidate_ids, result.selected_candidate_ids)

    def test_models_and_selection_are_pure_and_retain_no_full_results_records_or_journals(self):
        with ExitStack() as stack:
            for target in ('random.Random', 'towr.simulation.npc_magic_simulation.run_npc_magic_simulation',
                           'towr.simulation.npc_magic_parallel.run_npc_magic_simulation_parallel',
                           'towr.engine.npc_magic_scenario_runner.run_npc_magic_scenario',
                           'concurrent.futures.ProcessPoolExecutor', 'json.loads'):
                stack.enter_context(patch(target, side_effect=AssertionError('models must remain pure')))
            source = request()
            result = Result(source, tuple(candidate_result(source, i, 2) for i in range(3)))
            self.assertEqual(result.selected_candidate_ids, ('candidate:0', 'candidate:1'))
            self.assertEqual(result.total_trials, 12)
        pending, seen = [result], set()
        while pending:
            item = pending.pop()
            if id(item) in seen: continue
            seen.add(id(item))
            self.assertNotIsInstance(item, (NpcMagicSimulationResult, NpcMagicTrialRecord, NpcMagicScenarioResult))
            if is_dataclass(item): pending.extend(getattr(item, f.name) for f in fields(item))
            elif isinstance(item, (tuple, list)): pending.extend(item)
