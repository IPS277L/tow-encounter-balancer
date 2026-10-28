"""Two active phases, exact sources and cause ownership at the balance boundary."""
from copy import deepcopy
from dataclasses import replace
import json
from multiprocessing import active_children
import random
import unittest
from unittest.mock import patch

from tests.unit.test_m8_magic_balance_json import document, generation_failure_document, make_result
from towr.adapters.magic_balance_json import parse_magic_balance_request
from towr.application import magic_balance_service as service
from towr.application.magic_balance_errors import MagicBalanceGenerationError, MagicBalanceExecutionError
from towr.application.magic_candidate_generation_errors import MagicCandidateGenerationError
from towr.application.magic_staged_evaluation_errors import MagicStagedEvaluationError
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options


def command():
    return parse_magic_balance_request(json.dumps(document()))


def foreign_commands():
    for change in (
        lambda d: d['evaluation'].update(master_seed='43'),
        lambda d: d['reserve']['scenario']['wizard'].update(day_id='other-day'),
        lambda d: d['reserve']['scenario']['wizard']['caster'].update(wizard_level=3),
        lambda d: d['reserve']['scenario']['actor_policies'][1]['willpower'].update(dice=4),
        lambda d: d['reserve']['scenario']['definitions'][1]['attacks'][0].update(damage=4),
        lambda d: d['reserve']['scenario']['activation_order'].reverse(),
        lambda d: (d['reserve']['scenario']['scene_frames'][0]['attack_departures'][0].update(can_leave_zone=False),
                   d['generation'].update(scene_frames=deepcopy(d['reserve']['scenario']['scene_frames']))),
    ):
        data = document()
        change(data)
        yield parse_magic_balance_request(json.dumps(data))


class MagicBalanceServiceTests(unittest.TestCase):
    def test_dispatch_passes_exact_sources_options_and_no_extra_rng(self):
        base = command()
        expected = make_result(base)
        for execution in (Options(Mode.SEQUENTIAL), Options(Mode.PROCESS, 2, 7)):
            source = replace(base, execution=execution)
            with self.subTest(mode=execution.mode), \
                    patch.object(service, 'generate_magic_candidates', return_value=expected.generation_result) as generate, \
                    patch.object(service, 'evaluate_magic_candidates_staged', return_value=expected.evaluation_result) as evaluate:
                self.assertEqual(service.execute_magic_balance(source), expected)
            generate.assert_called_once_with(source.generation_request)
            evaluate.assert_called_once_with(expected.generation_result.evaluation_request, execution)

    def test_all_complete_and_early_unsupported_reports_are_success(self):
        source = command()
        for counts in (None, lambda i, p, n: (0, 0, 0, n),
                       lambda i, p, n: (0, 0, 0, n) if i else (n, 0, 0, 0),
                       lambda i, p, n: (0, 0, n, 0), lambda i, p, n: (0, n, 0, 0)):
            result = make_result(source, counts)
            with self.subTest(counts=counts), \
                    patch.object(service, 'generate_magic_candidates', return_value=result.generation_result), \
                    patch.object(service, 'evaluate_magic_candidates_staged', return_value=result.evaluation_result):
                self.assertEqual(service.execute_magic_balance(source), result)

    def test_wrong_root_fails_before_either_phase(self):
        source = command()
        with patch.object(service, 'generate_magic_candidates') as generate, \
                patch.object(service, 'evaluate_magic_candidates_staged') as evaluate:
            for value in (None, {}, 3, source.generation_request):
                with self.subTest(value=type(value)), self.assertRaises(TypeError):
                    service.execute_magic_balance(value)
        generate.assert_not_called()
        evaluate.assert_not_called()

    def test_wrong_generation_type_is_failure_before_evaluation(self):
        source = command()
        for value in (None, source.generation_request, make_result(source)):
            with self.subTest(value=type(value)), \
                    patch.object(service, 'generate_magic_candidates', return_value=value), \
                    patch.object(service, 'evaluate_magic_candidates_staged') as evaluate:
                with self.assertRaises(MagicBalanceGenerationError) as caught:
                    service.execute_magic_balance(source)
                self.assertIsInstance(caught.exception.__cause__, TypeError)
                self.assertEqual(caught.exception.request_id, source.request_id)
                self.assertIsNone(caught.exception.candidate_id)
                evaluate.assert_not_called()

    def test_generation_source_is_full_value_not_scenario_id(self):
        source = command()
        for other in foreign_commands():
            self.assertEqual(other.generation_request.template_scenario.id, source.generation_request.template_scenario.id)
            foreign = make_result(other)
            with self.subTest(source=other.generation_request), \
                    patch.object(service, 'generate_magic_candidates', return_value=foreign.generation_result), \
                    patch.object(service, 'evaluate_magic_candidates_staged') as evaluate:
                with self.assertRaises(MagicBalanceGenerationError) as caught:
                    service.execute_magic_balance(source)
                self.assertIsInstance(caught.exception.__cause__, ValueError)
                self.assertEqual(caught.exception.request_id, source.request_id)
                evaluate.assert_not_called()

    def test_evaluation_type_and_source_are_checked_before_balance_result(self):
        source = command()
        generated = make_result(source).generation_result
        wrong = [None, generated, source.generation_request]
        wrong.extend(make_result(other).evaluation_result for other in foreign_commands())
        for value in wrong:
            with self.subTest(evaluation=type(value)), \
                    patch.object(service, 'generate_magic_candidates', return_value=generated), \
                    patch.object(service, 'evaluate_magic_candidates_staged', return_value=value), \
                    patch.object(service, 'MagicBalanceResult') as build:
                with self.assertRaises(MagicBalanceExecutionError) as caught:
                    service.execute_magic_balance(source)
                self.assertIsInstance(caught.exception.__cause__, (TypeError, ValueError))
                self.assertEqual(caught.exception.request_id, source.request_id)
                self.assertIsNone(caught.exception.stage_index)
                self.assertIsNone(caught.exception.candidate_id)
                build.assert_not_called()

    def test_equal_copied_source_and_separate_external_id_are_accepted(self):
        source = command()
        result = make_result(deepcopy(source))
        renamed = replace(source, request_id='other-external-id')
        with patch.object(service, 'generate_magic_candidates', return_value=result.generation_result), \
                patch.object(service, 'evaluate_magic_candidates_staged', return_value=result.evaluation_result):
            self.assertEqual(service.execute_magic_balance(renamed), result)
        self.assertNotEqual(renamed.request_id, renamed.generation_request.template_scenario.id)

    def test_typed_generation_failure_preserves_context_and_full_cause_chain(self):
        source = command()
        original = ValueError('private admission')
        original.add_note('private admission note')
        cause = MagicCandidateGenerationError('candidate', (1, 0))
        cause.__cause__ = original
        with patch.object(service, 'generate_magic_candidates', side_effect=cause) as generate, \
                patch.object(service, 'evaluate_magic_candidates_staged') as evaluate:
            with self.assertRaises(MagicBalanceGenerationError) as caught:
                service.execute_magic_balance(source)
        error = caught.exception
        self.assertEqual((error.request_id, error.candidate_id, error.counts), (source.request_id, 'candidate', (1, 0)))
        self.assertIs(error.__cause__, cause)
        self.assertIs(cause.__cause__, original)
        self.assertEqual(original.__notes__, ['private admission note'])
        generate.assert_called_once()
        evaluate.assert_not_called()

    def test_typed_evaluation_failure_preserves_stage_candidate_and_notes(self):
        source = command()
        result = make_result(source)
        original = OSError('private worker error')
        original.add_note('private worker note')
        cause = MagicStagedEvaluationError(1, 'candidate')
        cause.__cause__ = original
        with patch.object(service, 'generate_magic_candidates', return_value=result.generation_result), \
                patch.object(service, 'evaluate_magic_candidates_staged', side_effect=cause) as evaluate:
            with self.assertRaises(MagicBalanceExecutionError) as caught:
                service.execute_magic_balance(source)
        error = caught.exception
        self.assertEqual((error.request_id, error.stage_index, error.candidate_id), (source.request_id, 1, 'candidate'))
        self.assertIs(error.__cause__, cause)
        self.assertIs(cause.__cause__, original)
        self.assertEqual(original.__notes__, ['private worker note'])
        evaluate.assert_called_once()

    def test_failure_category_follows_active_phase_not_foreign_exception_type(self):
        source = command()
        generated = make_result(source).generation_result
        cause = MagicStagedEvaluationError(9, 'foreign')
        with patch.object(service, 'generate_magic_candidates', side_effect=cause), \
                patch.object(service, 'evaluate_magic_candidates_staged') as evaluate:
            with self.assertRaises(MagicBalanceGenerationError) as caught:
                service.execute_magic_balance(source)
            evaluate.assert_not_called()
        self.assertIs(caught.exception.__cause__, cause)
        self.assertIsNone(caught.exception.candidate_id)
        self.assertIsNone(caught.exception.counts)
        cause = MagicCandidateGenerationError('foreign', (9,))
        with patch.object(service, 'generate_magic_candidates', return_value=generated), \
                patch.object(service, 'evaluate_magic_candidates_staged', side_effect=cause):
            with self.assertRaises(MagicBalanceExecutionError) as caught:
                service.execute_magic_balance(source)
        self.assertIs(caught.exception.__cause__, cause)
        self.assertIsNone(caught.exception.stage_index)
        self.assertIsNone(caught.exception.candidate_id)

    def test_unknown_errors_and_final_result_failure_have_only_active_phase_context(self):
        source = command()
        result = make_result(source)
        for phase in ('generation', 'evaluation', 'result'):
            cause = OSError('private unknown ' + phase)
            cause.add_note('original note')
            with self.subTest(phase=phase), \
                    patch.object(service, 'generate_magic_candidates', side_effect=cause if phase == 'generation' else None,
                                 return_value=result.generation_result) as generate, \
                    patch.object(service, 'evaluate_magic_candidates_staged', side_effect=cause if phase == 'evaluation' else None,
                                 return_value=result.evaluation_result) as evaluate, \
                    patch.object(service, 'MagicBalanceResult', side_effect=cause):
                error_type = MagicBalanceGenerationError if phase == 'generation' else MagicBalanceExecutionError
                with self.assertRaises(error_type) as caught:
                    service.execute_magic_balance(source)
                self.assertIs(caught.exception.__cause__, cause)
                self.assertEqual(cause.__notes__, ['original note'])
                self.assertEqual(caught.exception.request_id, source.request_id)
                self.assertIsNone(caught.exception.candidate_id)
                self.assertEqual(generate.call_count, 1)
                self.assertEqual(evaluate.call_count, int(phase != 'generation'))

    def test_error_context_counts_copy_and_generic_messages(self):
        counts = [1, 0]
        error = MagicBalanceGenerationError('outer', 'candidate', counts)
        counts.clear()
        self.assertEqual(error.counts, (1, 0))
        self.assertEqual(str(error), 'Magic balance candidate generation failed')
        self.assertEqual(str(MagicBalanceExecutionError('outer')), 'Magic balance evaluation failed')

    def test_base_exceptions_propagate_directly_from_both_phases(self):
        source = command()
        result = make_result(source)
        for phase in ('generation', 'evaluation', 'result'):
            for cause in (KeyboardInterrupt('stop'), SystemExit(7)):
                with self.subTest(phase=phase, error=type(cause)), \
                        patch.object(service, 'generate_magic_candidates', side_effect=cause if phase == 'generation' else None,
                                     return_value=result.generation_result), \
                        patch.object(service, 'evaluate_magic_candidates_staged', side_effect=cause if phase == 'evaluation' else None,
                                     return_value=result.evaluation_result), \
                        patch.object(service, 'MagicBalanceResult', side_effect=cause):
                    with self.assertRaises(type(cause)) as caught:
                        service.execute_magic_balance(source)
                    self.assertIs(caught.exception, cause)

    def test_real_invalid_subset_stops_generation_without_evaluation_and_preserves_inputs(self):
        source = parse_magic_balance_request(json.dumps(generation_failure_document()))
        before, before_rng = deepcopy(source), random.getstate()
        children = {c.pid for c in active_children()}
        with patch.object(service, 'evaluate_magic_candidates_staged') as evaluate:
            with self.assertRaises(MagicBalanceGenerationError) as caught:
                service.execute_magic_balance(source)
            evaluate.assert_not_called()
        self.assertEqual(caught.exception.counts, (1, 0))
        self.assertEqual(caught.exception.request_id, source.request_id)
        self.assertIsInstance(caught.exception.__cause__, MagicCandidateGenerationError)
        self.assertIsNotNone(caught.exception.__cause__.__cause__)
        self.assertEqual(source, before)
        self.assertEqual(random.getstate(), before_rng)
        self.assertEqual({c.pid for c in active_children()}, children)

    def test_late_generation_failure_after_one_real_admission_keeps_context_without_evaluation(self):
        from towr.application import magic_candidate_generation as generation
        source = command()
        before, before_rng = deepcopy(source), random.getstate()
        children = {c.pid for c in active_children()}
        original = generation.NpcMagicScenario
        cause = OSError('private second admission failure')
        cause.add_note('private admission note')
        admitted = []

        def fail_second(*args, **kwargs):
            if admitted:
                raise cause
            scenario = original(*args, **kwargs)
            admitted.append(scenario)
            return scenario

        with patch.object(generation, 'NpcMagicScenario', side_effect=fail_second) as admission, \
                patch.object(service, 'evaluate_magic_candidates_staged') as evaluate:
            with self.assertRaises(MagicBalanceGenerationError) as caught:
                service.execute_magic_balance(source)
            evaluate.assert_not_called()
        self.assertEqual(admission.call_count, 2)
        self.assertEqual(len(admitted), 1)
        error = caught.exception
        self.assertEqual(error.counts, (1, 1))
        self.assertEqual(error.request_id, source.request_id)
        self.assertIs(error.__cause__.__cause__, cause)
        self.assertEqual(cause.__notes__, ['private admission note'])
        self.assertEqual(source, before)
        self.assertEqual(random.getstate(), before_rng)
        self.assertEqual({c.pid for c in active_children()}, children)

    def test_late_evaluation_failure_after_first_real_candidate_keeps_full_chain_without_retry(self):
        from towr.application import magic_evaluation_service as bounded
        from towr.application.magic_evaluation_errors import MagicBalanceEvaluationError
        source = command()
        before, before_rng = deepcopy(source), random.getstate()
        children = {c.pid for c in active_children()}
        original = bounded.run_npc_magic_simulation
        cause = OSError('private second candidate failure')
        cause.add_note('private trial note')
        completed, failed = [], []

        def fail_second(request):
            if completed:
                failed.append(request.scenario.id)
                raise cause
            result = original(request)
            completed.append(result)
            return result

        with patch.object(bounded, 'run_npc_magic_simulation', side_effect=fail_second) as runner, \
                patch.object(bounded, 'run_npc_magic_simulation_parallel') as process:
            with self.assertRaises(MagicBalanceExecutionError) as caught:
                service.execute_magic_balance(source)
            process.assert_not_called()
        self.assertEqual(runner.call_count, 2)
        self.assertEqual(len(completed), 1)
        self.assertEqual(len(completed[0].trials), source.generation_request.stages[0].trials_per_candidate)
        error = caught.exception
        self.assertEqual((error.request_id, error.stage_index, error.candidate_id), (source.request_id, 0, failed[0]))
        self.assertIsInstance(error.__cause__, MagicStagedEvaluationError)
        self.assertIsInstance(error.__cause__.__cause__, MagicBalanceEvaluationError)
        self.assertIs(error.__cause__.__cause__.__cause__, cause)
        self.assertEqual(cause.__notes__, ['private trial note'])
        self.assertEqual(source, before)
        self.assertEqual(random.getstate(), before_rng)
        self.assertEqual({c.pid for c in active_children()}, children)
