"""Current Magic JSON contract: deterministic admission and source guards."""
from copy import deepcopy
import json
from unittest.mock import patch
import unittest

from tests.integration.test_m8_magic_json_v6 import invoke_v6
from tests.unit.test_m8_magic_balance_json_v6 import document
from towr.adapters import magic_balance_json as bal
from towr.adapters.magic_json_schema import validate_magic_balance_document
from towr.application import magic_balance_service as service
from towr.application.magic_balance_errors import MagicBalanceGenerationError, MagicBalanceExecutionError
from towr.application.magic_candidate_generation_errors import MagicCandidateGenerationError
from towr.application.magic_staged_evaluation_errors import MagicStagedEvaluationError


def small_document():
    raw = document()
    raw['evaluation']['stages'] = [{'trials_per_candidate': 1, 'keep': 1}, {'trials_per_candidate': 2, 'keep': 1}]
    raw['evaluation']['max_total_trials'] = 6
    return raw


class M8MagicBalanceJsonV6IntegrationTests(unittest.TestCase):
    def test_module_console_sequential_process_preserve_source_and_entire_report(self):
        raw = small_document()
        command = bal.parse_magic_balance_request(json.dumps(raw))
        original = deepcopy(command)
        expected = service.execute_magic_balance(command)
        self.assertEqual(len(expected.evaluation_result.stage_reports), 2)
        profile = command.generation_request.battered_leg_continuation
        self.assertTrue(all(candidate.scenario.battered_leg_continuation == profile
            for candidate in expected.generation_result.evaluation_request.candidates))
        for console in (False, True):
            for mode in ('sequential', 'process'):
                request = deepcopy(raw)
                request['execution'] = {'mode': mode}
                if mode == 'process':
                    request['execution'].update(workers=2, batch_size=1)
                selected = bal.parse_magic_balance_request(json.dumps(request))
                encoded = bal.encode_magic_balance_result(selected, expected)
                completed = invoke_v6('balance-magic', request, console=console)
                with self.subTest(console=console, mode=mode):
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    self.assertEqual(completed.stderr, b'')
                    self.assertEqual(completed.stdout.decode('utf-8'), encoded)
                    output = json.loads(completed.stdout)
                    validate_magic_balance_document(output, 'result', schema_version='6')
                    self.assertEqual(output['request'], request)
                    self.assertEqual(output['request']['generation']['battered_leg_continuation'],
                                     output['request']['reserve']['scenario']['battered_leg_continuation'])
        self.assertEqual(command, original)

    def test_cli_profile_mismatch_is_input_six_before_any_generation(self):
        raw = small_document()
        raw['generation']['battered_leg_continuation']['endurance_profile']['threshold'] = 4
        completed = invoke_v6('balance-magic', raw)
        self.assertEqual(completed.returncode, 2, completed.stderr)
        output = json.loads(completed.stdout)
        validate_magic_balance_document(output, 'error', schema_version='6')
        self.assertEqual((output['schema_version'], output['request_id'], output['error']['path']),
                         ('6', raw['request_id'], '/generation/battered_leg_continuation'))

    def test_generation_and_late_evaluation_failures_retain_v6_phase_context_privately(self):
        command = bal.parse_magic_balance_request(json.dumps(small_document()))
        for error in (RuntimeError('private general generation'), MagicCandidateGenerationError('finite-candidate', (2,))):
            with patch.object(service, 'generate_magic_candidates', side_effect=error),\
                    patch.object(service, 'evaluate_magic_candidates_staged') as evaluator:
                with self.assertRaises(MagicBalanceGenerationError) as caught:
                    service.execute_magic_balance(command)
                evaluator.assert_not_called()
            encoded = bal.encode_magic_balance_error(caught.exception)
            output = json.loads(encoded)
            validate_magic_balance_document(output, 'error', schema_version='6')
            self.assertEqual((output['schema_version'], output['request_id'], output['error']['code']),
                             ('6', command.request_id, 'generation_failed'))
            self.assertNotIn('private', encoded)
            if isinstance(error, MagicCandidateGenerationError):
                self.assertEqual((output['error']['candidate_id'], output['error']['counts']), ('finite-candidate', [2]))
        late = MagicStagedEvaluationError(1, 'finite-candidate')
        late.__cause__ = RuntimeError('private late evaluation')
        with patch.object(service, 'evaluate_magic_candidates_staged', side_effect=late):
            with self.assertRaises(MagicBalanceExecutionError) as caught:
                service.execute_magic_balance(command)
        encoded = bal.encode_magic_balance_error(caught.exception)
        output = json.loads(encoded)
        validate_magic_balance_document(output, 'error', schema_version='6')
        self.assertEqual((output['schema_version'], output['error']['candidate_id'], output['error']['stage_index']),
                         ('6', 'finite-candidate', 1))
        self.assertNotIn('private', encoded)
        self.assertNotIn('stage_reports', output)

    def test_equal_value_corrupt_family_profile_fails_before_generation_or_stage_execution(self):
        raw = small_document()
        raw['reserve']['scenario']['battered_leg_continuation']['endurance_profile']['dice'] = 1
        raw['generation']['battered_leg_continuation']['endurance_profile']['dice'] = 1
        command = bal.parse_magic_balance_request(json.dumps(raw))
        forged = deepcopy(command)
        object.__setattr__(forged.generation_request.battered_leg_continuation.endurance_profile, 'dice', True)
        self.assertEqual(forged, command)
        with patch.object(service, 'generate_magic_candidates') as generator,\
                patch.object(service, 'evaluate_magic_candidates_staged') as evaluator:
            with self.assertRaises(MagicBalanceGenerationError) as caught:
                service.execute_magic_balance(forged)
            self.assertEqual(caught.exception.schema_version, '6')
            self.assertIsInstance(caught.exception.__cause__, TypeError)
            generator.assert_not_called()
            evaluator.assert_not_called()


if __name__ == '__main__':
    unittest.main()
