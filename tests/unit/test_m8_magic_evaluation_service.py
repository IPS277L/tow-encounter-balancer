"""ADR-0040 candidate orchestration and failure boundaries."""
from copy import deepcopy
from dataclasses import replace
import gc
import inspect
import unittest
import weakref
from unittest.mock import call, patch

from tests.unit.test_m5_ranged_evaluation import request as ranged_request
from tests.unit.test_m6_melee_evaluation import request as melee_request
from tests.unit.test_m7_mixed_evaluation import request as mixed_request
from tests.unit.test_m8_magic_evaluation import request
from towr.application import magic_evaluation_service as service
from towr.application.magic_evaluation_errors import MagicBalanceEvaluationError
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.domain.npc_magic_scene_models import NpcMagicAttackDeparture
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome
from towr.domain.test_models import InlineProfile
from towr.simulation.npc_magic_models import NpcMagicSimulationResult, NpcMagicTrialRecord


def result_for(source):
    return NpcMagicSimulationResult(source, tuple(
        NpcMagicTrialRecord(source.scenario, index, source.seed_for(index), Outcome.UNSUPPORTED_PATH, 0, 1, 0)
        for index in range(source.trials)))


class MagicEvaluationServiceTests(unittest.TestCase):
    def test_explicit_backend_options_source_order_and_complete_report(self):
        source = request()
        self.assertEqual(tuple(inspect.signature(service.evaluate_magic_candidates).parameters), ('request', 'execution'))
        for execution in (Options(Mode.SEQUENTIAL), Options(Mode.PROCESS, 2, 3)):
            with self.subTest(execution=execution), \
                    patch.object(service, 'run_npc_magic_simulation', side_effect=result_for) as seq, \
                    patch.object(service, 'run_npc_magic_simulation_parallel', side_effect=lambda s, **kw: result_for(s)) as proc:
                result = service.evaluate_magic_candidates(source, execution)
                if execution.mode is Mode.SEQUENTIAL:
                    self.assertEqual(seq.call_args_list, [call(s) for s in source.simulation_requests])
                    proc.assert_not_called()
                else:
                    self.assertEqual(proc.call_args_list, [call(s, workers=2, batch_size=3) for s in source.simulation_requests])
                    seq.assert_not_called()
                self.assertEqual(tuple(row.candidate_id for row in result.candidates), tuple(c.candidate_id for c in source.candidates))
                self.assertEqual(result.total_trials, source.planned_trials)
                self.assertIs(result.source_request, source)
                self.assertEqual(result.selected_candidate_ids, ())
                for row, expected in zip(result.candidates, source.simulation_requests):
                    self.assertIs(row.assessment.source_request, expected)
                    self.assertIs(row.assessment.summary.source_request, expected)
                    self.assertIs(row.assessment.window, source.window)
                    self.assertEqual(row.assessment.summary.outcome_counts.unsupported_path, expected.trials)

    def test_candidate_failure_preserves_original_cause_notes_and_stops_list(self):
        source = request()
        for mode in Mode:
            for failed_index in (0, 1):
                cause = OSError('magic runner failed')
                cause.add_note('M8 trial index=2, seed=123')
                responses = [result_for(s) for s in source.simulation_requests[:failed_index]] + [cause]
                execution = Options(mode) if mode is Mode.SEQUENTIAL else Options(mode, 2, 1)
                with self.subTest(mode=mode, failed_index=failed_index), \
                        patch.object(service, 'run_npc_magic_simulation', side_effect=responses) as seq, \
                        patch.object(service, 'run_npc_magic_simulation_parallel', side_effect=responses) as proc:
                    with self.assertRaises(MagicBalanceEvaluationError) as caught:
                        service.evaluate_magic_candidates(source, execution)
                    self.assertEqual(caught.exception.candidate_id, source.candidates[failed_index].candidate_id)
                    self.assertIs(caught.exception.__cause__, cause)
                    self.assertEqual(caught.exception.__cause__.__notes__, ['M8 trial index=2, seed=123'])
                    self.assertIn(source.candidates[failed_index].candidate_id, str(caught.exception))
                    self.assertEqual((seq.call_count, proc.call_count),
                                     (failed_index + 1, 0) if mode is Mode.SEQUENTIAL else (0, failed_index + 1))
                    self.assertFalse(hasattr(caught.exception, 'partial_result'))

    def test_foreign_or_untyped_result_is_rejected_before_summary_projection(self):
        source = request()
        initial = source.simulation_requests[0]
        scenario = initial.scenario
        wizard = replace(scenario.initial.wizard, caster=replace(scenario.initial.wizard.caster, wizard_level=3))
        changed_level = replace(initial, scenario=replace(scenario, initial=replace(scenario.initial, wizard=wizard)))
        changed_profile = replace(initial, scenario=replace(scenario, actors=tuple(
            replace(actor, willpower_profile=InlineProfile(2, 3)) if actor.actor_id == 'enemy' else actor
            for actor in scenario.actors)))
        changed_departures = replace(initial, scenario=replace(scenario, scene_frames=tuple(
            replace(frame, attack_departures=(NpcMagicAttackDeparture('ally', False),))
            for frame in scenario.scene_frames)))
        self.assertNotEqual(changed_departures, initial)
        from tests.unit.test_m7_mixed_evaluation_service import result_for as mixed_result
        bad = ((None, TypeError), ({}, TypeError),
               (mixed_result(mixed_request().simulation_requests[0]), TypeError),
               *((result_for(foreign), ValueError) for foreign in
                 (replace(initial, master_seed=43), replace(initial, trials=5), changed_level, changed_profile, changed_departures)))
        for value, cause in bad:
            with self.subTest(value=type(value), cause=cause), \
                    patch.object(service, 'run_npc_magic_simulation', return_value=value) as run, \
                    patch.object(service, 'summarize_npc_magic_simulation') as summarize:
                with self.assertRaises(MagicBalanceEvaluationError) as caught:
                    service.evaluate_magic_candidates(source, Options(Mode.SEQUENTIAL))
                self.assertEqual(caught.exception.candidate_id, 'candidate:0')
                self.assertIsInstance(caught.exception.__cause__, cause)
                summarize.assert_not_called()
                run.assert_called_once()

    def test_equal_result_source_copy_is_admitted_without_rebinding_source(self):
        source = request(count=1)
        original = source.simulation_requests[0]
        copied = deepcopy(original)
        with patch.object(service, 'run_npc_magic_simulation', return_value=result_for(copied)):
            actual = service.evaluate_magic_candidates(source, Options(Mode.SEQUENTIAL))
        assessment = actual.candidates[0].assessment
        self.assertIs(actual.source_request, source)
        self.assertIs(assessment.source_request, original)
        self.assertIs(assessment.summary.source_request, copied)
        self.assertEqual(assessment.source_request, assessment.summary.source_request)

    def test_invalid_request_or_execution_never_starts_either_runner(self):
        with patch.object(service, 'run_npc_magic_simulation') as seq, \
                patch.object(service, 'run_npc_magic_simulation_parallel') as proc:
            for source, execution in ((None, Options(Mode.SEQUENTIAL)), (ranged_request(), Options(Mode.SEQUENTIAL)),
                                      (melee_request(), Options(Mode.SEQUENTIAL)), (mixed_request(), Options(Mode.SEQUENTIAL)),
                                      (request(), None), (request(), 'process'), (request(), {'mode': 'process'})):
                with self.subTest(source=type(source), execution=type(execution)), self.assertRaises(TypeError):
                    service.evaluate_magic_candidates(source, execution)
            seq.assert_not_called()
            proc.assert_not_called()

    def test_interrupts_are_propagated_without_candidate_wrapper(self):
        for interruption in (KeyboardInterrupt(), SystemExit(2)):
            with self.subTest(interruption=type(interruption)), \
                    patch.object(service, 'run_npc_magic_simulation', side_effect=interruption) as runner:
                with self.assertRaises(type(interruption)) as caught:
                    service.evaluate_magic_candidates(request(), Options(Mode.SEQUENTIAL))
                self.assertIs(caught.exception, interruption)
                runner.assert_called_once()

    def test_previous_full_result_is_released_before_next_runner_and_after_report(self):
        class ObservableResult(NpcMagicSimulationResult):
            pass
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
            with self.subTest(mode=mode), patch.object(service, 'run_npc_magic_simulation', side_effect=run), \
                    patch.object(service, 'run_npc_magic_simulation_parallel', side_effect=run):
                report = service.evaluate_magic_candidates(request(), execution)
            gc.collect()
            self.assertEqual(len(references), len(report.candidates))
            self.assertTrue(all(reference() is None for reference in references))

    def test_projection_assessment_and_row_failures_keep_candidate_context(self):
        for stage in ('summarize_npc_magic_simulation', 'assess_magic_candidate', 'MagicBalanceCandidateResult'):
            cause = ValueError('invalid magic aggregate')
            with self.subTest(stage=stage), patch.object(service, 'run_npc_magic_simulation', side_effect=result_for) as runner, \
                    patch.object(service, stage, side_effect=cause):
                with self.assertRaises(MagicBalanceEvaluationError) as caught:
                    service.evaluate_magic_candidates(request(), Options(Mode.SEQUENTIAL))
                self.assertEqual(caught.exception.candidate_id, 'candidate:0')
                self.assertIs(caught.exception.__cause__, cause)
                runner.assert_called_once()

    def test_final_report_failure_propagates_without_invented_candidate_id(self):
        cause = ValueError('invalid full magic report')
        source = request()
        with patch.object(service, 'run_npc_magic_simulation', side_effect=result_for) as runner, \
                patch.object(service, 'MagicBalanceEvaluationResult', side_effect=cause):
            with self.assertRaises(ValueError) as caught:
                service.evaluate_magic_candidates(source, Options(Mode.SEQUENTIAL))
            self.assertIs(caught.exception, cause)
            self.assertEqual(runner.call_count, len(source.candidates))
