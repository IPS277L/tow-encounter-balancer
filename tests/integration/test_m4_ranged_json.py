from copy import deepcopy
import json
import unittest

from tests.unit.test_m4_ranged_json import document, EXAMPLES
from towr.adapters.ranged_simulation_json import parse_ranged_simulation_request as parse, encode_ranged_simulation_result as encode
from towr.adapters.ranged_json_schema import validate_ranged_document
from towr.simulation.npc_ranged_parallel import run_npc_ranged_simulation_parallel
from towr.simulation.npc_ranged_simulation import run_npc_ranged_simulation


class M4RangedJsonIntegrationTests(unittest.TestCase):
    def test_example_through_real_execution_matches_documented_records_and_output(self):
        command = parse((EXAMPLES / "ranged-v1.request.json").read_bytes())
        sequential = run_npc_ranged_simulation(command.request)
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
        result = run_npc_ranged_simulation(command.request)
        sequential = json.loads(encode(command, result))
        self.assertEqual(sequential["request"], data)
        data["execution"] = {"mode":"process", "workers":2, "batch_size":1}
        process_command = parse(json.dumps(data))
        process = run_npc_ranged_simulation_parallel(process_command.request,
            workers=process_command.execution.workers, batch_size=process_command.execution.batch_size)
        encoded = json.loads(encode(process_command, process))
        validate_ranged_document(encoded, "result")
        self.assertEqual(encoded["request"], data)
        self.assertEqual(encoded["trials"], sequential["trials"])
        self.assertEqual(encoded["summary"], sequential["summary"])
        self.assertEqual(parse(json.dumps(encoded["request"])), process_command)
