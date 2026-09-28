import json
import unittest
from unittest.mock import patch

from tests.unit.test_m5_ranged_balance_json import document
from towr.adapters.ranged_balance_json import parse_ranged_balance_request, encode_ranged_balance_error
from towr.application import ranged_balance_service as service, ranged_candidate_generation as generation
from towr.application.ranged_balance_errors import RangedBalanceGenerationError, RangedBalanceExecutionError
from towr.simulation import npc_ranged_simulation as simulation


class M5BalanceServiceIntegrationTests(unittest.TestCase):
    def test_second_composition_failure_preserves_counts_cause_and_stops_before_evaluation(self):
        command = parse_ranged_balance_request(json.dumps(document()))
        constructor = generation.NpcRangedScenario
        calls = []
        cause = ValueError('private projection failure')
        cause.add_note('private source note')

        def fail_second(*args, **kwargs):
            calls.append(args[0].current.id)
            if len(calls) == 2:
                raise cause
            return constructor(*args, **kwargs)

        with patch.object(generation, 'NpcRangedScenario', side_effect=fail_second), \
                patch.object(service, 'evaluate_ranged_candidates_staged') as evaluate:
            with self.assertRaises(RangedBalanceGenerationError) as caught:
                service.execute_ranged_balance(command)
        evaluate.assert_not_called()
        self.assertEqual(calls, ['example:counts:0,1:initial', 'example:counts:1,0:initial'])
        error = caught.exception
        self.assertEqual(error.candidate_id, 'example:counts:1,0')
        self.assertEqual(error.counts, (1, 0))
        self.assertIs(error.__cause__.__cause__, cause)
        self.assertEqual(cause.__notes__, ['private source note'])
        encoded = json.loads(encode_ranged_balance_error(error))
        self.assertEqual(encoded['error']['counts'], [1, 0])
        self.assertEqual(set(encoded), {'schema_version', 'kind', 'request_id', 'error'})

    def test_late_trial_failure_discards_completed_stage_and_partial_second_stage(self):
        data = document()
        data['generation']['groups'][0].update(minimum_count=0, maximum_count=0)
        data['generation']['groups'][1].update(minimum_count=1, maximum_count=1)
        data['evaluation']['stages'] = [dict(trials_per_candidate=n, keep=1) for n in (1, 2, 3)]
        data['evaluation']['max_total_trials'] = 6
        command = parse_ranged_balance_request(json.dumps(data))
        run_trial = simulation.run_npc_ranged_trial
        calls = []
        cause = RuntimeError('private trial failure')
        cause.add_note('trial diagnosis')

        def fail_late(request, index, **kwargs):
            calls.append((request.trials, index))
            if request.trials == 2 and index == 1:
                raise cause
            return run_trial(request, index, **kwargs)

        with patch.object(simulation, 'run_npc_ranged_trial', side_effect=fail_late):
            with self.assertRaises(RangedBalanceExecutionError) as caught:
                service.execute_ranged_balance(command)
        self.assertEqual(calls, [(1, 0), (2, 0), (2, 1)])
        error = caught.exception
        self.assertEqual((error.request_id, error.stage_index, error.candidate_id),
                         (command.request_id, 1, 'example:counts:0,1'))
        deepest = error
        while deepest.__cause__ is not None:
            deepest = deepest.__cause__
        self.assertIs(deepest, cause)
        self.assertEqual(cause.__notes__, ['trial diagnosis'])
        text = encode_ranged_balance_error(error)
        actual = json.loads(text)
        self.assertEqual(set(actual), {'schema_version', 'kind', 'request_id', 'error'})
        self.assertNotIn('private', text)
        self.assertIsNone(actual['error']['counts'])
