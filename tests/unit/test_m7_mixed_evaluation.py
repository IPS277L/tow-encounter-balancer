from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from fractions import Fraction as F
import unittest
from unittest.mock import patch

from tests.unit.test_m7_npc_mixed_scenario import scenario
from towr.balance.mixed_assessment import assess_mixed_candidate
from towr.balance.mixed_assessment_models import ObjectiveRateWindow as Window
from towr.balance.mixed_evaluation_models import (
    MixedBalanceCandidate as Candidate, MixedBalanceCandidateResult as CandidateResult,
    MixedBalanceEvaluationRequest as Request, MixedBalanceEvaluationResult as Result,
)
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_mixed_scenario_result_models import NpcMixedScenarioResult
from towr.domain.npc_rounds_chain_summary_models import NpcRoundsChainSummary
from towr.simulation.npc_mixed_models import NpcMixedOutcomeCounts as Counts, NpcMixedSimulationResult, NpcMixedTrialSummary
from towr.simulation.npc_mixed_summary_models import NpcMixedSimulationSummary as Summary


def request(count=3, trials=4):
    source = scenario(sizes=(2, 1))
    return Request(tuple(Candidate(f"candidate:{i}", source) for i in range(count)),
                   42, trials, count * trials, Window(F(1, 4), F(1, 2), F(3, 4)), 2)


def candidate_result(source, index, achieved, unsupported=0):
    simulation = source.simulation_requests[index]
    n = simulation.trials
    summary = Summary(simulation, Counts(achieved, n-achieved-unsupported, 0, unsupported), n-unsupported, n)
    assessment = assess_mixed_candidate(simulation, summary, source.window)
    return CandidateResult(source.candidates[index].candidate_id, assessment)


class M7MixedEvaluationModelTests(unittest.TestCase):
    def test_request_freezes_candidates_and_derives_same_trial_seeds(self):
        source = request()
        mutable = list(source.candidates)
        actual = replace(source, candidates=mutable)
        mutable.clear()
        self.assertEqual(actual, source)
        self.assertEqual(actual.planned_trials, 12)
        self.assertEqual({item.seed_for(2) for item in actual.simulation_requests}, {source.simulation_requests[0].seed_for(2)})
        with self.assertRaises(FrozenInstanceError):
            actual.top_k = 1
        # dataclasses.replace reports init=False overrides differently by runtime.
        with self.assertRaises((TypeError, ValueError)):
            replace(actual, simulation_requests=())
        changed = replace(actual, master_seed=43)
        self.assertTrue(all(item.master_seed == 43 for item in changed.simulation_requests))
        self.assertNotEqual(changed.simulation_requests[0].seed_for(0), actual.simulation_requests[0].seed_for(0))
        rebuilt = replace(actual, trials_per_candidate=2, candidates=actual.candidates[::-1])
        self.assertEqual(rebuilt.planned_trials, 6)
        self.assertEqual(tuple(item.trials for item in rebuilt.simulation_requests), (2, 2, 2))
        self.assertEqual(tuple(item.scenario for item in rebuilt.simulation_requests),
                         tuple(item.scenario for item in rebuilt.candidates))
        self.assertTrue(all(new is not old for new, old in zip(rebuilt.simulation_requests, actual.simulation_requests)))

    def test_candidate_ids_and_typed_inputs_are_required(self):
        source = request()
        for value in (None, "", " ", 1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Candidate(value, source.candidates[0].scenario)
        with self.assertRaises(TypeError):
            Candidate("one", None)
        with self.assertRaises(TypeError):
            replace(source, candidates=(None,))
        for candidates in ((), (source.candidates[0], source.candidates[0])):
            with self.subTest(candidates=candidates), self.assertRaises(ValueError):
                replace(source, candidates=candidates)
        with self.assertRaises(TypeError):
            replace(source, window=None)
        spaced = Candidate(" candidate:0 ", source.candidates[0].scenario)
        self.assertEqual(replace(source, candidates=(spaced, source.candidates[0])).candidates[0].candidate_id,
                         " candidate:0 ")  # IDs remain exact; they are not stripped or generated.
        with self.assertRaises(FrozenInstanceError):
            spaced.candidate_id = "new"
        for candidate_id, assessment, error_type in (("", None, ValueError), ("x", None, TypeError)):
            with self.assertRaises(error_type):
                CandidateResult(candidate_id, assessment)

    def test_full_preflight_rejects_budget_and_numeric_coercion_before_runners(self):
        source = request()
        with patch("towr.simulation.npc_mixed_simulation.run_npc_mixed_simulation") as seq, \
                patch("towr.simulation.npc_mixed_parallel.run_npc_mixed_simulation_parallel") as proc, \
                patch("random.Random", side_effect=AssertionError), \
                patch("concurrent.futures.ProcessPoolExecutor", side_effect=AssertionError):
            for name in ("master_seed", "trials_per_candidate", "max_total_trials", "top_k"):
                for value in (True, False, 1.5, "4", None, -1):
                    with self.subTest(name=name, value=value), self.assertRaises((TypeError, ValueError)):
                        replace(source, **{name: value})
            for name in ("trials_per_candidate", "max_total_trials", "top_k"):
                with self.assertRaises(ValueError):
                    replace(source, **{name: 0})
            for name in ("master_seed", "trials_per_candidate"):
                with self.assertRaises(ValueError):
                    replace(source, **{name: 2**64})
            with self.assertRaises(ValueError):
                replace(source, max_total_trials=source.planned_trials-1)
            self.assertEqual(replace(source, max_total_trials=source.planned_trials).planned_trials, 12)
            self.assertEqual(replace(source, top_k=100).top_k, 100)
            seq.assert_not_called()
            proc.assert_not_called()

    def test_all_candidates_must_share_perspective_and_round_budget(self):
        source = request()
        first = source.candidates[0].scenario
        other_side = next(side for side in first.initial.current.round_state.side_order if side is not first.perspective_side)
        targets = tuple(p.state.actor_id for p in first.initial.current.state.roster.participants
                        if p.state.side is first.perspective_side)
        different = (replace(first, initial=replace(first.initial, max_rounds=4)),
                     replace(first, perspective_side=other_side, objective=NpcDefeatObjective(targets)))
        for scenario_input in different:
            with self.subTest(scenario=scenario_input), self.assertRaises(ValueError):
                replace(source, candidates=(*source.candidates[:-1], Candidate("last", scenario_input)))

    def test_ranking_filters_and_preserves_exact_ties_input_order_and_full_report(self):
        source = request(count=5)
        rows = (candidate_result(source, 0, 1), candidate_result(source, 1, 3),
                candidate_result(source, 2, 2), candidate_result(source, 3, 4), candidate_result(source, 4, 2, 1))
        result = Result(source, rows)
        self.assertEqual(result.selected_candidate_ids, ("candidate:2", "candidate:0"))
        self.assertEqual(result.candidates, rows)
        self.assertIsNone(result.candidates[4].assessment.window_match)
        self.assertEqual(result.total_trials, 20)
        self.assertEqual(result.seed_scheme, "towr:npc-mixed-trial:v1")
        larger = replace(source, top_k=100)
        self.assertEqual(Result(larger, rows).selected_candidate_ids, ("candidate:2", "candidate:0", "candidate:1"))
        order = (1, 0, 2, 3, 4)
        reversed_tie = replace(source, candidates=tuple(source.candidates[i] for i in order))
        self.assertEqual(Result(reversed_tie, tuple(rows[i] for i in order)).selected_candidate_ids,
                         ("candidate:2", "candidate:1"))

    def test_no_matching_candidates_returns_empty_selection_without_nearest_fallback(self):
        source = request(count=2)
        rows = (candidate_result(source, 0, 0), candidate_result(source, 1, 2, 1))
        result = Result(source, rows)
        self.assertEqual(result.selected_candidate_ids, ())
        self.assertEqual(len(result.candidates), 2)

    def test_ranking_uses_fraction_distances_instead_of_float(self):
        n = 2**60 + 1
        source = replace(request(count=2, trials=n), top_k=1)
        result = Result(source, (candidate_result(source, 0, n//2-1), candidate_result(source, 1, n//2)))
        self.assertEqual(float(result.candidates[0].assessment.objective_achieved_rate),
                         float(result.candidates[1].assessment.objective_achieved_rate))
        self.assertEqual(result.selected_candidate_ids, ("candidate:1",))

    def test_result_rejects_partial_reordered_duplicate_foreign_window_or_source(self):
        source = request()
        rows = tuple(candidate_result(source, i, i+1) for i in range(3))
        for invalid in (rows[:-1], rows[::-1], (rows[0], rows[0], rows[2])):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                Result(source, invalid)
        foreign = replace(source, master_seed=43)
        with self.assertRaises(ValueError):
            Result(source, (candidate_result(foreign, 0, 1), *rows[1:]))
        with self.assertRaises(ValueError):
            Result(replace(source, window=Window(F(0), F(1, 2), F(1))), rows)
        different_scenario = replace(source.candidates[0].scenario, actor_policies=tuple(
            replace(p, can_leave_zone=not p.can_leave_zone)
            for p in source.candidates[0].scenario.actor_policies))
        different = replace(source, candidates=(replace(source.candidates[0], scenario=different_scenario),
                                                *source.candidates[1:]))
        with self.assertRaises(ValueError):
            Result(source, (candidate_result(different, 0, 1), *rows[1:]))
        with self.assertRaises(ValueError):
            Result(source, (replace(rows[0], candidate_id="foreign"), *rows[1:]))
        copied = deepcopy(source)
        self.assertEqual(Result(copied, rows).candidates, rows)
        with self.assertRaises(TypeError):
            Result(None, rows)
        with self.assertRaises(TypeError):
            Result(source, (None,))

    def test_result_freezes_rows_and_retains_no_full_results_or_records(self):
        source = request()
        before = deepcopy(source)
        rows = [candidate_result(source, i, i+1) for i in range(3)]
        result = Result(source, rows)
        rows.clear()
        self.assertEqual(len(result.candidates), 3)
        self.assertEqual(source, before)
        self.assertIs(result.source_request, source)
        for item in (source, source.candidates[0], result, result.candidates[0]):
            self.assertFalse(hasattr(item, '__dict__'))
        with self.assertRaises(FrozenInstanceError):
            result.candidates = ()
        with self.assertRaises(FrozenInstanceError):
            result.candidates[0].assessment = None
        for field in ("selected_candidate_ids", "total_trials", "seed_scheme"):
            with self.assertRaises(TypeError):
                replace(result, **{field: None})
        pending, seen = [result], set()
        while pending:
            item = pending.pop()
            if id(item) in seen:
                continue
            seen.add(id(item))
            self.assertNotIsInstance(item, (NpcMixedSimulationResult, NpcMixedTrialSummary,
                                           NpcMixedScenarioResult, NpcRoundsChainSummary))
            if is_dataclass(item):
                pending.extend(getattr(item, field.name) for field in fields(item))
            elif isinstance(item, (tuple, list)):
                pending.extend(item)

    def test_ranged_and_melee_candidates_requests_rows_and_assessments_are_rejected(self):
        from tests.unit.test_m5_ranged_evaluation import request as ranged_request, candidate_result as ranged_row
        from tests.unit.test_m6_melee_evaluation import request as melee_request, candidate_result as melee_row
        source = request()
        for make, make_row in ((ranged_request, ranged_row), (melee_request, melee_row)):
            foreign = make()
            row = make_row(foreign, 0, 1)
            for build in (
                lambda: Candidate("one", foreign.candidates[0].scenario),
                lambda: replace(source, candidates=foreign.candidates),
                lambda: CandidateResult("one", row.assessment),
                lambda: Result(foreign, ()),
                lambda: Result(source, (row,) * len(source.candidates)),
            ):
                with self.subTest(family=type(foreign).__name__, build=build), self.assertRaises(TypeError):
                    build()

    def test_mixed_alternatives_preserve_pairs_policies_and_sources_through_rename(self):
        source = request()
        scenarios = (scenario(sizes=(3, 2)), scenario(sizes=(2, 2), enemy_bow=True))
        source = replace(source, candidates=tuple(Candidate(f"mixed:{i}", s) for i, s in enumerate(scenarios)))
        for candidate, simulation in zip(source.candidates, source.simulation_requests):
            self.assertIs(simulation.scenario, candidate.scenario)
            self.assertEqual(simulation.scenario.pair_ranges, candidate.scenario.pair_ranges)
            self.assertEqual(simulation.scenario.actor_policies, candidate.scenario.actor_policies)
        rows = tuple(candidate_result(source, i, 2) for i in range(2))
        renamed = replace(source, candidates=tuple(replace(c, candidate_id=f"renamed:{i}")
                                                   for i, c in enumerate(source.candidates)))
        self.assertEqual(renamed.simulation_requests, source.simulation_requests)
        self.assertEqual(Result(renamed, tuple(replace(r, candidate_id=c.candidate_id)
                                              for r, c in zip(rows, renamed.candidates))).selected_candidate_ids,
                         ("renamed:0", "renamed:1"))
        first = scenarios[0]
        for changed in (replace(first, pair_ranges=first.pair_ranges[::-1]),
                        replace(first, actor_policies=tuple(replace(p, outnumbering_bonus_approved=False)
                                                           for p in first.actor_policies))):
            changed_source = replace(source, candidates=(replace(source.candidates[0], scenario=changed),
                                                         source.candidates[1]))
            with self.assertRaises(ValueError):
                Result(source, (candidate_result(changed_source, 0, 2), rows[1]))
