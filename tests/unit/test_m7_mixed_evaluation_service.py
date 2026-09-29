from dataclasses import replace
import gc
import unittest
import weakref
from unittest.mock import call, patch

from tests.unit.test_m7_npc_mixed_simulation import observations
from tests.unit.test_m7_mixed_evaluation import request
from tests.unit.test_m5_ranged_evaluation import request as ranged_request
from tests.unit.test_m6_melee_evaluation import request as melee_request
from towr.application import mixed_evaluation_service as service
from towr.application.mixed_evaluation_errors import MixedBalanceEvaluationError
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.domain.npc_mixed_scenario_result_models import NpcMixedScenarioOutcome as Outcome
from towr.simulation.npc_mixed_models import NpcMixedSimulationResult


def result_for(source):
    records = tuple(replace(item, visited_round_count=source.scenario.initial.max_rounds)
                    if item.outcome is Outcome.ROUND_LIMIT else item for item in observations(source))
    return NpcMixedSimulationResult(source, records)


class M7MixedEvaluationServiceTests(unittest.TestCase):
    def test_explicit_backend_options_and_order_are_preserved_once_per_candidate(self):
        source = request()
        for execution in (Options(Mode.SEQUENTIAL), Options(Mode.PROCESS, 2, 3)):
            with self.subTest(execution=execution), \
                    patch.object(service, "run_npc_mixed_simulation", side_effect=result_for) as seq, \
                    patch.object(service, "run_npc_mixed_simulation_parallel", side_effect=lambda s, **kw: result_for(s)) as proc:
                result = service.evaluate_mixed_candidates(source, execution)
                if execution.mode is Mode.SEQUENTIAL:
                    self.assertEqual(seq.call_args_list, [call(s) for s in source.simulation_requests])
                    proc.assert_not_called()
                else:
                    self.assertEqual(proc.call_args_list, [call(s, workers=2, batch_size=3) for s in source.simulation_requests])
                    seq.assert_not_called()
                self.assertEqual(tuple(r.candidate_id for r in result.candidates), tuple(c.candidate_id for c in source.candidates))
                self.assertEqual(result.total_trials, source.planned_trials)
                self.assertIs(result.source_request, source)
                self.assertEqual(result.selected_candidate_ids, ())  # unsupported observations are retained, not retried

    def test_failure_after_one_candidate_preserves_id_cause_notes_and_stops(self):
        source = request()
        for mode in Mode:
            cause = OSError("runner failed")
            cause.add_note("worker trial index=2")
            execution = Options(mode) if mode is Mode.SEQUENTIAL else Options(mode, 2, 1)
            responses = [result_for(source.simulation_requests[0]), cause]
            with self.subTest(mode=mode), \
                    patch.object(service, "run_npc_mixed_simulation", side_effect=responses) as seq, \
                    patch.object(service, "run_npc_mixed_simulation_parallel", side_effect=responses) as proc:
                with self.assertRaises(MixedBalanceEvaluationError) as caught:
                    service.evaluate_mixed_candidates(source, execution)
                self.assertEqual(caught.exception.candidate_id, "candidate:1")
                self.assertIs(caught.exception.__cause__, cause)
                self.assertEqual(caught.exception.__cause__.__notes__, ["worker trial index=2"])
                self.assertEqual((seq.call_count, proc.call_count), (2, 0) if mode is Mode.SEQUENTIAL else (0, 2))
                self.assertFalse(hasattr(caught.exception, "partial_result"))

    def test_foreign_or_untyped_runner_result_fails_before_projection(self):
        source = request()
        foreign = replace(source.simulation_requests[0], master_seed=43)
        initial = source.simulation_requests[0]
        other_facts = replace(initial, scenario=replace(initial.scenario, actor_policies=tuple(
            replace(p, outnumbering_bonus_approved=False) for p in initial.scenario.actor_policies)))
        other_pairs = replace(initial, scenario=replace(initial.scenario, pair_ranges=initial.scenario.pair_ranges[::-1]))
        from tests.unit.test_m6_melee_evaluation_service import result_for as melee_result
        for value, cause in ((None, TypeError), (melee_result(melee_request().simulation_requests[0]), TypeError),
                             (result_for(foreign), ValueError), (result_for(other_facts), ValueError),
                             (result_for(other_pairs), ValueError)):
            with self.subTest(cause=cause), patch.object(service, "run_npc_mixed_simulation", return_value=value), \
                    patch.object(service, "summarize_npc_mixed_simulation") as summarize:
                with self.assertRaises(MixedBalanceEvaluationError) as caught:
                    service.evaluate_mixed_candidates(source, Options(Mode.SEQUENTIAL))
                self.assertEqual(caught.exception.candidate_id, "candidate:0")
                self.assertIsInstance(caught.exception.__cause__, cause)
                summarize.assert_not_called()

    def test_invalid_request_or_execution_never_starts_runner(self):
        with patch.object(service, "run_npc_mixed_simulation") as seq, \
                patch.object(service, "run_npc_mixed_simulation_parallel") as proc:
            for source, execution in ((None, Options(Mode.SEQUENTIAL)), (ranged_request(), Options(Mode.SEQUENTIAL)),
                                      (melee_request(), Options(Mode.SEQUENTIAL)),
                                      (request(), None), (request(), "process")):
                with self.assertRaises(TypeError):
                    service.evaluate_mixed_candidates(source, execution)
            seq.assert_not_called()
            proc.assert_not_called()

    def test_interrupts_are_not_wrapped_as_candidate_failures(self):
        for interruption in (KeyboardInterrupt(), SystemExit(2)):
            with patch.object(service, "run_npc_mixed_simulation", side_effect=interruption):
                with self.assertRaises(type(interruption)) as caught:
                    service.evaluate_mixed_candidates(request(), Options(Mode.SEQUENTIAL))
                self.assertIs(caught.exception, interruption)

    def test_previous_full_result_is_released_before_next_runner(self):
        class ObservableResult(NpcMixedSimulationResult):
            pass  # A weak-referenceable result, without altering production slots.

        references = []

        def run(source, **options):
            gc.collect()
            self.assertTrue(all(reference() is None for reference in references))
            result = ObservableResult(source, result_for(source).trials)
            references.append(weakref.ref(result))
            return result

        for mode in Mode:
            references.clear()
            execution = Options(mode) if mode is Mode.SEQUENTIAL else Options(mode, 2, 1)
            with self.subTest(mode=mode), patch.object(service, "run_npc_mixed_simulation", side_effect=run), \
                    patch.object(service, "run_npc_mixed_simulation_parallel", side_effect=run):
                report = service.evaluate_mixed_candidates(request(), execution)
                gc.collect()
                self.assertEqual(len(references), len(report.candidates))
                self.assertTrue(all(reference() is None for reference in references))

    def test_projection_assessment_and_row_failures_keep_candidate_context(self):
        for stage in ("summarize_npc_mixed_simulation", "assess_mixed_candidate", "MixedBalanceCandidateResult"):
            cause = ValueError("invalid candidate aggregate")
            with self.subTest(stage=stage), \
                    patch.object(service, "run_npc_mixed_simulation", side_effect=result_for) as runner, \
                    patch.object(service, stage, side_effect=cause):
                with self.assertRaises(MixedBalanceEvaluationError) as caught:
                    service.evaluate_mixed_candidates(request(), Options(Mode.SEQUENTIAL))
                self.assertEqual(caught.exception.candidate_id, "candidate:0")
                self.assertIs(caught.exception.__cause__, cause)
                runner.assert_called_once()

    def test_final_report_failure_has_no_invented_candidate_context(self):
        cause = ValueError("invalid full report")
        source = request()
        with patch.object(service, "run_npc_mixed_simulation", side_effect=result_for) as runner, \
                patch.object(service, "MixedBalanceEvaluationResult", side_effect=cause):
            with self.assertRaises(ValueError) as caught:
                service.evaluate_mixed_candidates(source, Options(Mode.SEQUENTIAL))
            self.assertIs(caught.exception, cause)
            self.assertEqual(runner.call_count, len(source.candidates))
