from dataclasses import replace
import unittest
from unittest.mock import call, patch

from tests.unit.test_m5_ranged_staged_evaluation import request, stage_request, report, reports, Stage, Status
from towr.application import ranged_staged_evaluation_service as service
from towr.application import ranged_evaluation_service as bounded_service
from towr.application.ranged_evaluation_errors import RangedBalanceEvaluationError
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.application.ranged_staged_evaluation_errors import RangedStagedEvaluationError
from towr.domain.npc_ranged_scenario_result_models import NpcRangedScenarioOutcome as Outcome
from towr.simulation.npc_ranged_models import NpcRangedSimulationResult, NpcRangedTrialSummary


def all_objectives(source):
    return NpcRangedSimulationResult(source, tuple(
        NpcRangedTrialSummary(i, source.seed_for(i), Outcome.OBJECTIVE_ACHIEVED, 1, 1)
        for i in range(source.trials)))


class M5RangedStagedServiceTests(unittest.TestCase):
    def test_exact_stage_requests_options_and_outside_continuation(self):
        source = request()
        first, last = reports(source)
        for options in (Options(Mode.SEQUENTIAL), Options(Mode.PROCESS, 2, 3)):
            with self.subTest(options=options), \
                    patch.object(service, "evaluate_ranged_candidates", side_effect=(first, last)) as evaluate:
                result = service.evaluate_ranged_candidates_staged(source, options)
                self.assertEqual(evaluate.call_args_list, [call(first.source_request, options), call(last.source_request, options)])
                self.assertEqual(result.stage_reports, (first, last))
                self.assertEqual(result.status, Status.COMPLETED)
                self.assertEqual(result.selected_candidate_ids, ("candidate:0",))
                self.assertEqual(result.total_trials, 240)

    def test_unsupported_early_stop_and_reduced_candidate_budget(self):
        source = request()
        options = Options(Mode.SEQUENTIAL)
        exhausted = report(stage_request(source), (4, 7, 5, 6), (1, 1, 1, 1))
        with patch.object(service, "evaluate_ranged_candidates", return_value=exhausted) as evaluate:
            result = service.evaluate_ranged_candidates_staged(source, options)
            evaluate.assert_called_once_with(exhausted.source_request, options)
            self.assertEqual(result.status, Status.NO_ELIGIBLE_CANDIDATES)
            self.assertEqual(result.total_trials, 40)
        first = report(stage_request(source), (4, 7, 5, 6), (0, 1, 1, 1))
        last = report(stage_request(source, 1, source.candidates[:1]), (49,))
        with patch.object(service, "evaluate_ranged_candidates", side_effect=(first, last)) as evaluate:
            result = service.evaluate_ranged_candidates_staged(source, options)
            self.assertEqual(evaluate.call_args_list[-1], call(last.source_request, options))
            self.assertEqual(result.total_trials, 140)

    def test_full_batches_rerun_from_index_zero_with_same_seed_in_both_modes(self):
        source = request()
        for options in (Options(Mode.SEQUENTIAL), Options(Mode.PROCESS, 2, 3)):
            with self.subTest(options=options), \
                    patch.object(bounded_service, "run_npc_ranged_simulation", side_effect=all_objectives) as seq, \
                    patch.object(bounded_service, "run_npc_ranged_simulation_parallel",
                                 side_effect=lambda s, **kw: all_objectives(s)) as proc:
                result = service.evaluate_ranged_candidates_staged(source, options)
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
        source = request()
        cause = OSError("worker failed")
        cause.add_note("trial index=7")
        inputs = []
        def run(simulation):
            inputs.append(simulation)
            if len(inputs) == 6:
                raise cause
            return all_objectives(simulation)
        with patch.object(bounded_service, "run_npc_ranged_simulation", side_effect=run), \
                patch.object(bounded_service, "run_npc_ranged_simulation_parallel") as proc:
            with self.assertRaises(RangedStagedEvaluationError) as caught:
                service.evaluate_ranged_candidates_staged(source, Options(Mode.SEQUENTIAL))
            error = caught.exception
            self.assertEqual(error.stage_index, 1)
            self.assertEqual(error.candidate_id, "candidate:1")
            self.assertIsInstance(error.__cause__, RangedBalanceEvaluationError)
            self.assertIs(error.__cause__.__cause__, cause)
            self.assertEqual(cause.__notes__, ["trial index=7"])
            self.assertFalse(hasattr(error, "partial_result"))
            self.assertEqual(len(inputs), 6)
            proc.assert_not_called()

    def test_invalid_second_stage_report_stops_before_third_without_inventing_candidate(self):
        source = replace(request(), stages=(Stage(10, 2), Stage(100, 1), Stage(1000, 1)), max_total_trials=1240)
        first, last = reports(source)
        foreign = report(replace(last.source_request, master_seed=43), (49, 51))
        for bad, expected_cause in ((None, TypeError), (foreign, ValueError), (RuntimeError("stage failed"), RuntimeError)):
            with self.subTest(cause=expected_cause), \
                    patch.object(service, "evaluate_ranged_candidates", side_effect=(first, bad)) as evaluate:
                with self.assertRaises(RangedStagedEvaluationError) as caught:
                    service.evaluate_ranged_candidates_staged(source, Options(Mode.SEQUENTIAL))
                self.assertEqual(evaluate.call_count, 2)
                self.assertEqual(caught.exception.stage_index, 1)
                self.assertIsNone(caught.exception.candidate_id)
                self.assertIsInstance(caught.exception.__cause__, expected_cause)

    def test_invalid_request_options_and_late_stage_spec_fail_before_evaluation(self):
        with patch.object(service, "evaluate_ranged_candidates") as evaluate:
            for source, options in ((None, Options(Mode.SEQUENTIAL)), (request(), None), (request(), "process")):
                with self.assertRaises(TypeError):
                    service.evaluate_ranged_candidates_staged(source, options)
            for changes in ({"max_total_trials": 239}, {"stages": (Stage(10, 2), Stage(10, 1))},
                            {"stages": (Stage(10, 2), None)}):
                with self.assertRaises((ValueError, TypeError)):
                    service.evaluate_ranged_candidates_staged(replace(request(), **changes), Options(Mode.SEQUENTIAL))
            evaluate.assert_not_called()

    def test_interrupts_are_not_wrapped_as_stage_errors(self):
        for interruption in (KeyboardInterrupt(), SystemExit(2)):
            with patch.object(service, "evaluate_ranged_candidates", side_effect=interruption) as evaluate:
                with self.assertRaises(type(interruption)) as caught:
                    service.evaluate_ranged_candidates_staged(request(), Options(Mode.SEQUENTIAL))
                self.assertIs(caught.exception, interruption)
                self.assertEqual(evaluate.call_count, 1)
