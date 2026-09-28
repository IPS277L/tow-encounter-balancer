from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from fractions import Fraction as F
import unittest
from unittest.mock import patch

from tests.unit.test_m6_melee_evaluation import (
    request as bounded_request, candidate_result, Window, Counts, Summary, CandidateResult, assess_melee_candidate,
)
from towr.balance.melee_evaluation_models import MeleeBalanceEvaluationRequest as BoundedRequest
from towr.balance.melee_evaluation_models import MeleeBalanceEvaluationResult as BoundedResult
from towr.balance.melee_staged_evaluation import melee_continuation_candidate_ids as continuation
from towr.balance.melee_staged_evaluation_models import (
    MeleeBalanceStage as Stage, MeleeStagedEvaluationRequest as Request,
    MeleeStagedEvaluationResult as Result, MeleeStagedEvaluationStatus as Status,
)
from towr.simulation.npc_melee_models import NpcMeleeSimulationResult, NpcMeleeTrialSummary
from towr.domain.npc_objective_models import NpcDefeatObjective


def request():
    base = bounded_request(count=4, trials=10)
    return Request(base.candidates, 42, (Stage(10, 2), Stage(100, 1)), 240,
                   Window(F(9, 20), F(1, 2), F(11, 20)))


def stage_request(source, index=0, candidates=None):
    candidates = source.candidates if candidates is None else candidates
    stage = source.stages[index]
    return BoundedRequest(candidates, source.master_seed, stage.trials_per_candidate,
                          len(candidates) * stage.trials_per_candidate, source.window, stage.keep)


def report(source, achieved, unsupported=None):
    unsupported = unsupported or (0,) * len(achieved)
    return BoundedResult(source, tuple(candidate_result(source, i, count, unsupported[i])
                                      for i, count in enumerate(achieved)))


def reports(source):
    first = report(stage_request(source), (4, 7, 5, 6), (0, 0, 1, 0))
    last = report(stage_request(source, 1, (source.candidates[0], source.candidates[3])), (49, 51))
    return first, last


class M6MeleeStagedModelTests(unittest.TestCase):
    def test_outside_candidates_continue_but_final_selection_uses_only_last_stage(self):
        source = request()
        first, last = reports(source)
        self.assertEqual(first.selected_candidate_ids, ())
        self.assertEqual(continuation(first), ("candidate:0", "candidate:3"))
        result = Result(source, (first, last))
        self.assertEqual(result.status, Status.COMPLETED)
        self.assertEqual(result.selected_candidate_ids, ("candidate:0",))
        self.assertEqual(result.total_trials, 240)
        self.assertEqual(result.planned_trials, 240)
        self.assertEqual(result.seed_scheme, "towr:npc-melee-trial:v1")
        for counts, selected in (((45, 55), ("candidate:0",)), ((40, 60), ())):
            with self.subTest(counts=counts):
                final = report(last.source_request, counts)
                self.assertEqual(Result(source, (first, final)).selected_candidate_ids, selected)

    def test_continuation_restores_original_order_after_ranking_and_resolves_cutoff_ties(self):
        source = request()
        first = report(stage_request(source), (4, 7, 5, 5), (0, 0, 1, 0))
        self.assertEqual(first.selected_candidate_ids, ("candidate:3",))
        self.assertEqual(continuation(first), ("candidate:0", "candidate:3"))
        last = reports(source)[1]
        self.assertEqual(Result(source, (first, last)).selected_candidate_ids, ("candidate:0",))
        tied = report(stage_request(source), (4, 6, 4, 6))
        self.assertEqual(continuation(tied), ("candidate:0", "candidate:1"))

    def test_continuation_uses_exact_fractions_and_rejects_untyped_report(self):
        n = 2**60 + 1
        base = replace(bounded_request(count=2, trials=n), top_k=1)
        first = report(base, (n//2-1, n//2))
        self.assertEqual(float(first.candidates[0].assessment.objective_achieved_rate),
                         float(first.candidates[1].assessment.objective_achieved_rate))
        self.assertEqual(continuation(first), ("candidate:1",))
        with self.assertRaises(TypeError):
            continuation(None)

    def test_actual_budget_shrinks_only_when_fewer_candidates_are_eligible(self):
        source = request()
        first = report(stage_request(source), (4, 7, 5, 6), (0, 1, 1, 1))
        last = report(stage_request(source, 1, source.candidates[:1]), (49,))
        result = Result(source, (first, last))
        self.assertEqual(result.total_trials, 140)
        self.assertEqual(result.planned_trials, 240)
        self.assertEqual(result.selected_candidate_ids, ("candidate:0",))

    def test_no_eligible_candidates_stops_early_but_final_unsupported_is_completed(self):
        source = request()
        first = report(stage_request(source), (4, 7, 5, 6), (1, 1, 1, 1))
        result = Result(source, (first,))
        self.assertEqual(result.status, Status.NO_ELIGIBLE_CANDIDATES)
        self.assertEqual(result.total_trials, 40)
        self.assertEqual(result.selected_candidate_ids, ())
        normal, last = reports(source)
        final = report(last.source_request, (49, 51), (1, 1))
        complete = Result(source, (normal, final))
        self.assertEqual(complete.status, Status.COMPLETED)
        self.assertEqual(complete.selected_candidate_ids, ())

    def test_early_stop_never_returns_previous_stage_matches(self):
        source = replace(request(), stages=(Stage(10, 2), Stage(100, 1), Stage(1000, 1)), max_total_trials=1240)
        first = report(stage_request(source), (5, 5, 5, 5))
        second = report(stage_request(source, 1, source.candidates[:2]), (50, 50), (1, 1))
        self.assertEqual(first.selected_candidate_ids, ("candidate:0", "candidate:1"))
        result = Result(source, (first, second))
        self.assertEqual(result.status, Status.NO_ELIGIBLE_CANDIDATES)
        self.assertEqual(result.selected_candidate_ids, ())
        self.assertEqual(result.total_trials, 240)

    def test_one_stage_and_keep_above_count_follow_bounded_semantics(self):
        source = replace(request(), stages=(Stage(10, 10),), max_total_trials=40)
        first = report(stage_request(source), (5, 5, 7, 4), (0, 1, 0, 0))
        result = Result(source, (first,))
        self.assertEqual(result.status, Status.COMPLETED)
        self.assertEqual(result.selected_candidate_ids, ("candidate:0",))
        self.assertEqual(result.total_trials, 40)
        self.assertEqual(result.planned_trials, 40)
        unsupported = report(stage_request(source), (5, 5, 5, 5), (1, 1, 1, 1))
        self.assertEqual(Result(source, (unsupported,)).status, Status.COMPLETED)
        caps = replace(source, stages=(Stage(10, 1), Stage(100, 10), Stage(1000, 20)), max_total_trials=1140)
        self.assertEqual(caps.planned_trials, 1140)  # No return of eliminated candidates.

    def test_three_completed_stages_do_not_restore_eliminated_candidates_when_keep_grows(self):
        source = replace(request(), stages=(Stage(10, 1), Stage(100, 10), Stage(1000, 20)), max_total_trials=1140)
        first = report(stage_request(source), (5, 7, 3, 6))
        second = report(stage_request(source, 1, source.candidates[:1]), (50,))
        final = report(stage_request(source, 2, source.candidates[:1]), (500,))
        result = Result(source, (first, second, final))
        self.assertEqual(result.status, Status.COMPLETED)
        self.assertEqual(result.total_trials, 1140)
        self.assertEqual(result.selected_candidate_ids, ("candidate:0",))

    def test_round_limit_remains_eligible_with_all_trials_in_denominator(self):
        source = replace(request(), candidates=request().candidates[:1])
        stages = []
        for i in range(2):
            local = stage_request(source, i)
            simulation = local.simulation_requests[0]
            n = simulation.trials
            summary = Summary(simulation, Counts(0, 0, n, 0), 0, n * simulation.scenario.initial.max_rounds)
            assessment = assess_melee_candidate(simulation, summary, source.window)
            stages.append(BoundedResult(local, (CandidateResult("candidate:0", assessment),)))
            self.assertEqual(assessment.round_limit_rate, 1)
            self.assertEqual(assessment.objective_achieved_rate, 0)
            self.assertEqual(continuation(stages[-1]), ("candidate:0",))
        result = Result(source, tuple(stages))
        self.assertEqual(result.total_trials, 110)
        self.assertEqual(result.status, Status.COMPLETED)
        self.assertEqual(result.selected_candidate_ids, ())

    def test_stage_types_and_strictly_increasing_trials_are_validated_before_execution(self):
        source = request()
        with patch("towr.application.melee_evaluation_service.run_npc_melee_simulation") as runner:
            for value in (None, True, 1.5, "10", 0, -1):
                for name in ("keep", "trials_per_candidate"):
                    with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                        replace(Stage(10, 2), **{name: value})
            with self.assertRaises(ValueError):
                Stage(2**64, 1)
            self.assertEqual(Stage(2**64-1, 1).trials_per_candidate, 2**64-1)
            for stages in ((), (Stage(10, 2), Stage(10, 1)), (Stage(10, 2), Stage(9, 1))):
                with self.subTest(stages=stages), self.assertRaises(ValueError):
                    replace(source, stages=stages)
            with self.assertRaises(TypeError):
                replace(source, stages=(source.stages[0], None))
            runner.assert_not_called()

    def test_full_upper_budget_and_common_input_are_preflighted(self):
        source = request()
        for value in (None, True, 1.5, "240", 0, -1, 239):
            with self.subTest(budget=value), self.assertRaises(ValueError):
                replace(source, max_total_trials=value)
        self.assertEqual(replace(source, max_total_trials=240).planned_trials, 240)
        for value in (None, True, -1, 2**64):
            with self.subTest(seed=value), self.assertRaises((TypeError, ValueError)):
                replace(source, master_seed=value)
        for candidates in ((), (source.candidates[0], source.candidates[0]), (None,)):
            with self.subTest(candidates=candidates), self.assertRaises((TypeError, ValueError)):
                replace(source, candidates=candidates)
        with self.assertRaises(TypeError):
            replace(source, window=None)
        scenario = source.candidates[1].scenario
        different = replace(source.candidates[1], scenario=replace(scenario, initial=replace(scenario.initial, max_rounds=4)))
        with self.assertRaises(ValueError):
            replace(source, candidates=(source.candidates[0], different))
        other_side = next(side for side in scenario.initial.current.round_state.side_order
                          if side is not scenario.perspective_side)
        targets = tuple(actor.state.actor_id for actor in scenario.initial.current.state.roster.participants
                        if actor.state.side is scenario.perspective_side)
        different = replace(source.candidates[1], scenario=replace(
            scenario, perspective_side=other_side, objective=NpcDefeatObjective(targets)))
        with self.assertRaises(ValueError):
            replace(source, candidates=(source.candidates[0], different))

    def test_result_rejects_incomplete_extra_reordered_and_wrong_continuation_reports(self):
        source = request()
        first, last = reports(source)
        wrong = report(stage_request(source, 1, source.candidates[:2]), (49, 51))
        reversed_input = report(stage_request(source, 1, last.source_request.candidates[::-1]), (51, 49))
        for chain in ((), (first,), (first, last, last), (last, first), (first, first),
                      (first, wrong), (first, reversed_input)):
            with self.subTest(length=len(chain)), self.assertRaises(ValueError):
                Result(source, chain)
        exhausted = report(stage_request(source), (4, 7, 5, 6), (1, 1, 1, 1))
        with self.assertRaises(ValueError):
            Result(source, (exhausted, last))
        with self.assertRaises(TypeError):
            Result(None, (first,))
        with self.assertRaises(TypeError):
            Result(source, (first, None))

    def test_result_requires_exact_stage_seed_trials_window_budget_keep_and_scenario(self):
        source = request()
        first, last = reports(source)
        changed = tuple(replace(c, scenario=replace(c.scenario, initial=replace(c.scenario.initial, max_rounds=4)))
                        for c in last.source_request.candidates)
        changes = ({"master_seed": 43}, {"trials_per_candidate": 99}, {"max_total_trials": 201},
                   {"top_k": 2}, {"window": Window(F(0), F(1, 2), F(1))},
                   {"candidates": changed})
        for change in changes:
            with self.subTest(change=tuple(change)), self.assertRaises(ValueError):
                foreign = replace(last.source_request, **change)
                Result(source, (first, report(foreign, (49,) * len(foreign.candidates))))

    def test_frozen_normalized_models_and_derived_properties_retain_no_records(self):
        source = request()
        before = deepcopy(source)
        candidates, stages = list(source.candidates), list(source.stages)
        actual = replace(source, candidates=candidates, stages=stages)
        candidates.clear()
        stages.clear()
        mutable = list(reports(source))
        result = Result(actual, mutable)
        mutable.clear()
        self.assertEqual(actual, before)
        self.assertEqual(len(result.stage_reports), 2)
        for obj, name, value in ((source, "master_seed", 43), (source.stages[0], "keep", 3),
                                 (result, "stage_reports", ())):
            with self.assertRaises(FrozenInstanceError):
                setattr(obj, name, value)
        for name in ("status", "selected_candidate_ids", "total_trials", "planned_trials", "seed_scheme"):
            with self.subTest(name=name), self.assertRaises(TypeError):
                replace(result, **{name: None})
        with self.assertRaises(TypeError):
            replace(source, planned_trials=0)
        def inspect(value):
            self.assertNotIsInstance(value, (NpcMeleeSimulationResult, NpcMeleeTrialSummary))
            if is_dataclass(value):
                for field in fields(value):
                    inspect(getattr(value, field.name))
            elif isinstance(value, tuple):
                for item in value:
                    inspect(item)
        inspect(result)

    def test_ranged_stages_candidates_sources_and_reports_are_rejected(self):
        from tests.unit.test_m5_ranged_staged_evaluation import request as ranged_request, reports as ranged_reports
        from towr.balance.ranged_staged_evaluation_models import RangedStagedEvaluationStatus
        source = request()
        ranged = ranged_request()
        foreign = ranged_reports(ranged)
        for build in (
            lambda: replace(source, stages=ranged.stages),
            lambda: replace(source, candidates=ranged.candidates),
            lambda: continuation(foreign[0]),
            lambda: Result(source, foreign),
            lambda: Result(ranged, reports(source)),
        ):
            with self.subTest(build=build), self.assertRaises(TypeError):
                build()
        self.assertIsNot(type(Result(source, reports(source)).status),
                         RangedStagedEvaluationStatus)

    def test_replace_revalidates_budget_and_chain_but_equal_source_copies_are_accepted(self):
        source = request()
        original_reports = reports(source)
        copied = deepcopy(source)
        result = Result(copied, original_reports)
        self.assertIs(result.source_request, copied)
        self.assertEqual(result, Result(source, original_reports))
        updated = replace(source, stages=(Stage(20, 2), Stage(200, 1)), max_total_trials=480)
        self.assertEqual(updated.planned_trials, 480)
        self.assertEqual(source.planned_trials, 240)
        with self.assertRaises(ValueError):
            replace(source, stages=updated.stages)
        with self.assertRaises(ValueError):
            replace(result, source_request=updated)
        for index in (0, 9):
            self.assertEqual(original_reports[0].source_request.simulation_requests[0].seed_for(index),
                             original_reports[1].source_request.simulation_requests[0].seed_for(index))
        self.assertEqual(updated.window, source.window)

    def test_model_construction_selection_and_preflight_execute_no_rng_runner_pool_or_json(self):
        with patch("towr.application.melee_evaluation_service.run_npc_melee_simulation", side_effect=AssertionError), \
                patch("towr.application.melee_evaluation_service.run_npc_melee_simulation_parallel", side_effect=AssertionError), \
                patch("towr.engine.npc_melee_scenario_runner.run_npc_melee_scenario", side_effect=AssertionError), \
                patch("random.Random", side_effect=AssertionError), \
                patch("concurrent.futures.ProcessPoolExecutor", side_effect=AssertionError), \
                patch("json.loads", side_effect=AssertionError):
            source = request()
            first, last = reports(source)
            before = deepcopy((source, first, last))
            result = Result(source, (first, last))
            self.assertEqual(continuation(first), ("candidate:0", "candidate:3"))
            self.assertEqual(result.selected_candidate_ids, ("candidate:0",))
            for invalid in (239, 220):
                with self.subTest(budget=invalid), self.assertRaises(ValueError):
                    replace(source, max_total_trials=invalid)
            with self.assertRaises(TypeError):
                replace(source, stages=(*source.stages, None))
            self.assertEqual((source, first, last), before)
