from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from tests.unit.test_m4_ranged_json import document, EXAMPLES
from towr.adapters.ranged_simulation_json import parse_ranged_simulation_request as parse, encode_ranged_simulation_result as encode
from towr.adapters.ranged_json_schema import validate_ranged_document
from towr.adapters.ranged_json_errors import RangedSimulationInputError
from towr.adapters.ranged_simulation_json import encode_ranged_simulation_error
from towr.application.ranged_simulation_errors import RangedSimulationExecutionError
from towr.application.ranged_simulation_service import execute_ranged_simulation
from towr.simulation import npc_ranged_simulation


class M4RangedJsonIntegrationTests(unittest.TestCase):
    def test_example_through_real_execution_matches_documented_records_and_output(self):
        command = parse((EXAMPLES / "ranged-v1.request.json").read_bytes())
        sequential = execute_ranged_simulation(command)
        actual = json.loads(encode(command, sequential))
        expected = json.loads((EXAMPLES / "ranged-v1.result.json").read_text(encoding="utf-8"))
        # Runtime metadata is descriptive; the sample was generated on Python 3.14.5.
        expected["runtime"] = actual["runtime"]
        self.assertEqual(actual, expected)
        self.assertEqual(parse(json.dumps(actual["request"])), command)
        self.assertEqual(actual["summary"]["outcome_counts"],
                         {"objective_achieved":0, "side_defeated":3, "round_limit":0, "unsupported_path":0})

    def test_process_and_sequential_preserve_arrays_and_results_with_multiple_definitions(self):
        data = document()
        scenario = data["scenario"]
        other = deepcopy(scenario["definitions"][0])
        other["id"] = "other"
        other["attack"]["damage"] = 4
        scenario["definitions"].insert(0, other)  # deliberately not first-actor order
        scenario["actors"][1]["definition_id"] = "other"
        scenario["side_order"].reverse()
        scenario["actor_order"].reverse()
        scenario["actor_policies"].reverse()
        scenario["battlefield"]["zone_ids"].append("unoccupied")
        command = parse(json.dumps(data))
        result = execute_ranged_simulation(command)
        sequential = json.loads(encode(command, result))
        self.assertEqual(sequential["request"], data)
        data["execution"] = {"mode":"process", "workers":2, "batch_size":1}
        process_command = parse(json.dumps(data))
        process = execute_ranged_simulation(process_command)
        encoded = json.loads(encode(process_command, process))
        validate_ranged_document(encoded, "result")
        self.assertEqual(encoded["request"], data)
        self.assertEqual(encoded["trials"], sequential["trials"])
        self.assertEqual(encoded["summary"], sequential["summary"])
        self.assertEqual(parse(json.dumps(encoded["request"])), process_command)

    def test_parse_and_admission_failures_never_enter_execution(self):
        version = dict(document(), schema_version="2")
        invalid = document()
        invalid["scenario"]["facts"]["targets_aware"] = False
        cases = ((b"{", "invalid_json", None),
                 (json.dumps(version), "unsupported_version", version["request_id"]),
                 (json.dumps(invalid), "invalid_input", invalid["request_id"]))
        with patch("towr.application.ranged_simulation_service.run_npc_ranged_simulation") as seq, \
                patch("towr.application.ranged_simulation_service.run_npc_ranged_simulation_parallel") as proc:
            for text, code, request_id in cases:
                with self.subTest(code=code):
                    try:
                        execute_ranged_simulation(parse(text))
                    except RangedSimulationInputError as error:
                        actual = json.loads(encode_ranged_simulation_error(error))
                    else:
                        self.fail("invalid input was accepted")
                    validate_ranged_document(actual, "error")
                    self.assertEqual(actual["error"]["code"], code)
                    self.assertEqual(actual["request_id"], request_id)
            seq.assert_not_called()
            proc.assert_not_called()

    def test_failure_after_completed_trial_has_no_partial_output(self):
        command = parse(json.dumps(document()))
        original = npc_ranged_simulation.run_npc_ranged_trial
        cause = RuntimeError("second trial failed")

        def fail_second(request, index, **kwargs):
            if index == 1:
                raise cause
            return original(request, index, **kwargs)

        with patch.object(npc_ranged_simulation, "run_npc_ranged_trial", side_effect=fail_second) as trial:
            with self.assertRaises(RangedSimulationExecutionError) as caught:
                execute_ranged_simulation(command)
            self.assertEqual(trial.call_count, 2)
        self.assertIs(caught.exception.__cause__, cause)
        actual = json.loads(encode_ranged_simulation_error(caught.exception))
        validate_ranged_document(actual, "error")
        self.assertEqual(actual["error"]["code"], "execution_failed")
        self.assertEqual(actual["request_id"], document()["request_id"])
        self.assertNotIn("trials", actual)
        self.assertNotIn("summary", actual)

    def test_pool_startup_failure_is_encoded_without_sequential_fallback(self):
        data = document()
        data["execution"] = {"mode": "process", "workers": 2, "batch_size": 1}
        command = parse(json.dumps(data))
        cause = OSError("pool startup failed")
        with patch("towr.simulation.npc_ranged_parallel.ProcessPoolExecutor", side_effect=cause) as pool, \
                patch("towr.application.ranged_simulation_service.run_npc_ranged_simulation") as seq:
            with self.assertRaises(RangedSimulationExecutionError) as caught:
                execute_ranged_simulation(command)
            pool.assert_called_once()
            seq.assert_not_called()
        self.assertIs(caught.exception.__cause__, cause)
        actual = json.loads(encode_ranged_simulation_error(caught.exception))
        validate_ranged_document(actual, "error")
        self.assertEqual(actual["error"]["code"], "execution_failed")
        self.assertEqual(actual["request_id"], data["request_id"])
        self.assertNotIn("trials", actual)
        self.assertNotIn("summary", actual)
