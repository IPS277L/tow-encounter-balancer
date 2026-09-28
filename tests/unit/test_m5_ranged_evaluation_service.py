from dataclasses import replace
import unittest
from unittest.mock import call, patch

from tests.unit.test_m3_npc_ranged_simulation import observations
from tests.unit.test_m5_ranged_evaluation import request
from towr.application import ranged_evaluation_service as service
from towr.application.ranged_evaluation_errors import RangedBalanceEvaluationError
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.domain.npc_ranged_scenario_result_models import NpcRangedScenarioOutcome as Outcome
from towr.simulation.npc_ranged_models import NpcRangedSimulationResult


def result_for(source):
    records = tuple(replace(item, visited_round_count=source.scenario.initial.max_rounds)
                    if item.outcome is Outcome.ROUND_LIMIT else item for item in observations(source))
    return NpcRangedSimulationResult(source, records)


class M5RangedEvaluationServiceTests(unittest.TestCase):
    def test_explicit_backend_options_and_order_are_preserved_once_per_candidate(self):
        source = request()
        for execution in (Options(Mode.SEQUENTIAL), Options(Mode.PROCESS, 2, 3)):
            with self.subTest(execution=execution), \
                    patch.object(service, "run_npc_ranged_simulation", side_effect=result_for) as seq, \
                    patch.object(service, "run_npc_ranged_simulation_parallel", side_effect=lambda s, **kw: result_for(s)) as proc:
                result = service.evaluate_ranged_candidates(source, execution)
                if execution.mode is Mode.SEQUENTIAL:
                    self.assertEqual(seq.call_args_list, [call(s) for s in source.simulation_requests])
                    proc.assert_not_called()
                else:
                    self.assertEqual(proc.call_args_list, [call(s, workers=2, batch_size=3) for s in source.simulation_requests])
                    seq.assert_not_called()
                self.assertEqual(tuple(r.candidate_id for r in result.candidates), tuple(c.candidate_id for c in source.candidates))
                self.assertEqual(result.total_trials, source.planned_trials)
                self.assertEqual(result.selected_candidate_ids, ())  # unsupported observations are retained, not retried

    def test_failure_after_one_candidate_preserves_id_cause_notes_and_stops(self):
        source = request()
        for mode in Mode:
            cause = OSError("runner failed")
            cause.add_note("worker trial index=2")
            execution = Options(mode) if mode is Mode.SEQUENTIAL else Options(mode, 2, 1)
            responses = [result_for(source.simulation_requests[0]), cause]
            with self.subTest(mode=mode), \
                    patch.object(service, "run_npc_ranged_simulation", side_effect=responses) as seq, \
                    patch.object(service, "run_npc_ranged_simulation_parallel", side_effect=responses) as proc:
                with self.assertRaises(RangedBalanceEvaluationError) as caught:
                    service.evaluate_ranged_candidates(source, execution)
                self.assertEqual(caught.exception.candidate_id, "candidate:1")
                self.assertIs(caught.exception.__cause__, cause)
                self.assertEqual(caught.exception.__cause__.__notes__, ["worker trial index=2"])
                self.assertEqual((seq.call_count, proc.call_count), (2, 0) if mode is Mode.SEQUENTIAL else (0, 2))
                self.assertFalse(hasattr(caught.exception, "partial_result"))

    def test_foreign_or_untyped_runner_result_fails_before_projection(self):
        source = request()
        foreign = replace(source.simulation_requests[0], master_seed=43)
        for value, cause in ((None, TypeError), (result_for(foreign), ValueError)):
            with self.subTest(cause=cause), patch.object(service, "run_npc_ranged_simulation", return_value=value), \
                    patch.object(service, "summarize_npc_ranged_simulation") as summarize:
                with self.assertRaises(RangedBalanceEvaluationError) as caught:
                    service.evaluate_ranged_candidates(source, Options(Mode.SEQUENTIAL))
                self.assertEqual(caught.exception.candidate_id, "candidate:0")
                self.assertIsInstance(caught.exception.__cause__, cause)
                summarize.assert_not_called()

    def test_invalid_request_or_execution_never_starts_runner(self):
        with patch.object(service, "run_npc_ranged_simulation") as seq, \
                patch.object(service, "run_npc_ranged_simulation_parallel") as proc:
            for source, execution in ((None, Options(Mode.SEQUENTIAL)), (request(), None), (request(), "process")):
                with self.assertRaises(TypeError):
                    service.evaluate_ranged_candidates(source, execution)
            seq.assert_not_called()
            proc.assert_not_called()

    def test_interrupts_are_not_wrapped_as_candidate_failures(self):
        for interruption in (KeyboardInterrupt(), SystemExit(2)):
            with patch.object(service, "run_npc_ranged_simulation", side_effect=interruption):
                with self.assertRaises(type(interruption)) as caught:
                    service.evaluate_ranged_candidates(request(), Options(Mode.SEQUENTIAL))
                self.assertIs(caught.exception, interruption)
