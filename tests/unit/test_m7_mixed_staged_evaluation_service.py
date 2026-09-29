from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import call, patch

from tests.unit.test_m7_mixed_staged_evaluation import request, stage_request, report, reports, Stage, Status
from tests.unit.test_m5_ranged_staged_evaluation import request as ranged_request, reports as ranged_reports
from tests.unit.test_m6_melee_staged_evaluation import request as melee_request, reports as melee_reports
from towr.application import mixed_staged_evaluation_service as service
from towr.application import mixed_evaluation_service as bounded_service
from towr.application.mixed_evaluation_errors import MixedBalanceEvaluationError
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.application.mixed_staged_evaluation_errors import MixedStagedEvaluationError
from towr.domain.npc_mixed_scenario_result_models import NpcMixedScenarioOutcome as Outcome
from towr.simulation.npc_mixed_models import NpcMixedSimulationResult, NpcMixedTrialSummary


def all_objectives(source):
    return NpcMixedSimulationResult(source, tuple(
        NpcMixedTrialSummary(i, source.seed_for(i), Outcome.OBJECTIVE_ACHIEVED, 1, 1)
        for i in range(source.trials)))


class M7MixedStagedServiceTests(unittest.TestCase):
    def test_exact_stage_requests_options_and_outside_continuation(self):
        source = request()
        first, last = reports(source)
        for options in (Options(Mode.SEQUENTIAL), Options(Mode.PROCESS, 2, 3)):
            with self.subTest(options=options), \
                    patch.object(service, "evaluate_mixed_candidates", side_effect=deepcopy((first, last))) as evaluate:
                result = service.evaluate_mixed_candidates_staged(source, options)
                self.assertEqual(evaluate.call_args_list, [call(first.source_request, options), call(last.source_request, options)])
                self.assertEqual(result.stage_reports, (first, last))
                self.assertEqual(result.status, Status.COMPLETED)
                self.assertEqual(result.selected_candidate_ids, ("candidate:0",))
                self.assertEqual(result.total_trials, 240)
                self.assertIs(result.source_request, source)
                self.assertTrue(all(args.args[1] is options for args in evaluate.call_args_list))

    def test_unsupported_early_stop_and_reduced_candidate_budget(self):
        source = request()
        options = Options(Mode.SEQUENTIAL)
        exhausted = report(stage_request(source), (4, 7, 5, 6), (1, 1, 1, 1))
        with patch.object(service, "evaluate_mixed_candidates", return_value=exhausted) as evaluate:
            result = service.evaluate_mixed_candidates_staged(source, options)
            evaluate.assert_called_once_with(exhausted.source_request, options)
            self.assertEqual(result.status, Status.NO_ELIGIBLE_CANDIDATES)
            self.assertEqual(result.total_trials, 40)
        first = report(stage_request(source), (4, 7, 5, 6), (0, 1, 1, 1))
        last = report(stage_request(source, 1, source.candidates[:1]), (49,))
        with patch.object(service, "evaluate_mixed_candidates", side_effect=(first, last)) as evaluate:
            result = service.evaluate_mixed_candidates_staged(source, options)
            self.assertEqual(evaluate.call_args_list[-1], call(last.source_request, options))
            self.assertEqual(result.total_trials, 140)
        first, last = reports(source)
        unsupported_final = report(last.source_request, (49, 51), (1, 1))
        with patch.object(service, "evaluate_mixed_candidates", side_effect=(first, unsupported_final)) as evaluate:
            result = service.evaluate_mixed_candidates_staged(source, options)
            self.assertEqual(result.status, Status.COMPLETED)
            self.assertEqual(result.selected_candidate_ids, ())
            self.assertEqual(evaluate.call_count, 2)

    def test_full_batches_rerun_from_index_zero_with_same_seed_in_both_modes(self):
        source = request()
        for options in (Options(Mode.SEQUENTIAL), Options(Mode.PROCESS, 2, 3)):
            with self.subTest(options=options), \
                    patch.object(bounded_service, "run_npc_mixed_simulation", side_effect=all_objectives) as seq, \
                    patch.object(bounded_service, "run_npc_mixed_simulation_parallel",
                                 side_effect=lambda s, **kw: all_objectives(s)) as proc:
                result = service.evaluate_mixed_candidates_staged(source, options)
                active, idle = (seq, proc) if options.mode is Mode.SEQUENTIAL else (proc, seq)
                idle.assert_not_called()
                inputs = [args.args[0] for args in active.call_args_list]
                self.assertEqual([s.trials for s in inputs], [10, 10, 10, 10, 100, 100])
                self.assertTrue(all(s.master_seed == 42 for s in inputs))
                self.assertEqual([inputs[0].seed_for(i) for i in range(10)],
                                 [inputs[4].seed_for(i) for i in range(10)])
                for args in active.call_args_list:
                    self.assertEqual(args.kwargs, {} if options.mode is Mode.SEQUENTIAL else {"workers": 2, "batch_size": 3})
                self.assertEqual(sum(s.trials for s in inputs), result.total_trials)
                self.assertEqual(result.total_trials, 240)
                self.assertEqual(result.selected_candidate_ids, ())  # All observed rates are outside the window.

    def test_second_stage_runner_failure_retains_stage_candidate_cause_notes_and_stops(self):
        source = replace(request(), stages=(Stage(10, 2), Stage(100, 1), Stage(1000, 1)), max_total_trials=1240)
        for options in (Options(Mode.SEQUENTIAL), Options(Mode.PROCESS, 2, 3)):
            cause = OSError("worker failed")
            cause.add_note("trial index=7")
            inputs = []
            def run(simulation, **kwargs):
                inputs.append(simulation)
                if len(inputs) == 6:
                    raise cause
                return all_objectives(simulation)
            with self.subTest(options=options), \
                    patch.object(bounded_service, "run_npc_mixed_simulation", side_effect=run) as seq, \
                    patch.object(bounded_service, "run_npc_mixed_simulation_parallel", side_effect=run) as proc:
                with self.assertRaises(MixedStagedEvaluationError) as caught:
                    service.evaluate_mixed_candidates_staged(source, options)
                error = caught.exception
                self.assertEqual(error.stage_index, 1)
                self.assertEqual(error.candidate_id, "candidate:1")
                self.assertIsInstance(error.__cause__, MixedBalanceEvaluationError)
                self.assertIs(error.__cause__.__cause__, cause)
                self.assertEqual(cause.__notes__, ["trial index=7"])
                self.assertFalse(hasattr(error, "partial_result"))
                self.assertEqual(len(inputs), 6)
                self.assertEqual((seq.call_count, proc.call_count),
                                 (6, 0) if options.mode is Mode.SEQUENTIAL else (0, 6))

    def test_invalid_second_stage_report_stops_before_third_without_inventing_candidate(self):
        source = replace(request(), stages=(Stage(10, 2), Stage(100, 1), Stage(1000, 1)), max_total_trials=1240)
        first, last = reports(source)
        foreign = report(replace(last.source_request, master_seed=43), (49, 51))
        ranged = ranged_reports(ranged_request())[1]
        melee = melee_reports(melee_request())[1]
        original = last.source_request.candidates[0].scenario
        changed = (
            replace(original, pair_ranges=original.pair_ranges[::-1]),
            replace(original, actor_policies=tuple(replace(p, outnumbering_bonus_approved=False)
                                                   for p in original.actor_policies)),
        )
        foreign_scenarios = tuple(report(replace(last.source_request, candidates=(
            replace(last.source_request.candidates[0], scenario=scenario),
            *last.source_request.candidates[1:])), (49, 51)) for scenario in changed)
        for bad, expected_cause in ((None, TypeError), (ranged, TypeError), (melee, TypeError), (foreign, ValueError),
                                    *((item, ValueError) for item in foreign_scenarios),
                                    (RuntimeError("stage failed"), RuntimeError)):
            with self.subTest(cause=expected_cause), \
                    patch.object(service, "evaluate_mixed_candidates", side_effect=(first, bad)) as evaluate:
                with self.assertRaises(MixedStagedEvaluationError) as caught:
                    service.evaluate_mixed_candidates_staged(source, Options(Mode.SEQUENTIAL))
                self.assertEqual(evaluate.call_count, 2)
                self.assertEqual(caught.exception.stage_index, 1)
                self.assertIsNone(caught.exception.candidate_id)
                self.assertIsInstance(caught.exception.__cause__, expected_cause)

    def test_invalid_request_options_and_late_stage_spec_fail_before_evaluation(self):
        with patch.object(service, "evaluate_mixed_candidates") as evaluate:
            for source, options in ((None, Options(Mode.SEQUENTIAL)), (ranged_request(), Options(Mode.SEQUENTIAL)),
                                    (melee_request(), Options(Mode.SEQUENTIAL)),
                                    (request(), None), (request(), "process")):
                with self.assertRaises(TypeError):
                    service.evaluate_mixed_candidates_staged(source, options)
            for changes in ({"max_total_trials": 239}, {"stages": (Stage(10, 2), Stage(10, 1))},
                            {"stages": (Stage(10, 2), None)}):
                with self.assertRaises((ValueError, TypeError)):
                    service.evaluate_mixed_candidates_staged(replace(request(), **changes), Options(Mode.SEQUENTIAL))
            evaluate.assert_not_called()

    def test_interrupts_are_not_wrapped_as_stage_errors(self):
        for interruption in (KeyboardInterrupt(), SystemExit(2)):
            with patch.object(service, "evaluate_mixed_candidates", side_effect=interruption) as evaluate:
                with self.assertRaises(type(interruption)) as caught:
                    service.evaluate_mixed_candidates_staged(request(), Options(Mode.SEQUENTIAL))
                self.assertIs(caught.exception, interruption)
                self.assertEqual(evaluate.call_count, 1)

    def test_stage_assembly_and_continuation_failures_preserve_cause_without_candidate(self):
        source = request()
        for stage, calls in (("_stage_request", 0), ("mixed_continuation_candidate_ids", 1)):
            cause = ValueError("invalid stage")
            with self.subTest(stage=stage), patch.object(service, stage, side_effect=cause), \
                    patch.object(service, "evaluate_mixed_candidates", return_value=reports(source)[0]) as evaluate:
                with self.assertRaises(MixedStagedEvaluationError) as caught:
                    service.evaluate_mixed_candidates_staged(source, Options(Mode.SEQUENTIAL))
                self.assertEqual(caught.exception.stage_index, 0)
                self.assertIsNone(caught.exception.candidate_id)
                self.assertIs(caught.exception.__cause__, cause)
                self.assertEqual(evaluate.call_count, calls)

    def test_final_result_constructor_failure_has_no_invented_stage_context(self):
        source = request()
        cause = ValueError("invalid report chain")
        with patch.object(service, "evaluate_mixed_candidates", side_effect=reports(source)) as evaluate, \
                patch.object(service, "MixedStagedEvaluationResult", side_effect=cause):
            with self.assertRaises(ValueError) as caught:
                service.evaluate_mixed_candidates_staged(source, Options(Mode.SEQUENTIAL))
            self.assertIs(caught.exception, cause)
            self.assertEqual(evaluate.call_count, 2)
