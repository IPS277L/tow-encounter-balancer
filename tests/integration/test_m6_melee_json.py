import json
import unittest

from tests.unit.test_m6_melee_json import document
from towr.adapters.melee_simulation_json import parse_melee_simulation_request as parse, encode_melee_simulation_result as encode
from towr.adapters.melee_json_schema import validate_melee_document
from towr.simulation.npc_melee_simulation import run_npc_melee_simulation
from towr.simulation.npc_melee_parallel import run_npc_melee_simulation_parallel
from towr.simulation.npc_melee_summary import summarize_npc_melee_simulation


class M6MeleeJsonIntegrationTests(unittest.TestCase):
    def test_fixture_through_existing_simulator_and_summary_to_wire(self):
        data = document()
        command = parse(json.dumps(data))
        result = run_npc_melee_simulation(command.request)
        summary = summarize_npc_melee_simulation(result)
        encoded = json.loads(encode(command, summary))
        validate_melee_document(encoded, "result")
        self.assertEqual(encoded["request"], data)
        self.assertEqual(encoded["summary"]["total_attack_count"], result.total_attack_count)
        self.assertEqual(sum(encoded["summary"]["outcome_counts"].values()), command.request.trials)
        self.assertEqual(parse(json.dumps(encoded["request"])), command)
        self.assertNotIn("trials", encoded)

    def test_process_and_sequential_have_identical_results_and_aggregate_wire(self):
        data = document()
        data["scenario"]["actor_policies"][0]["outnumbering_bonus_approved"] = False
        data["scenario"]["actor_order"].reverse()
        command = parse(json.dumps(data))
        sequential = run_npc_melee_simulation(command.request)
        data["execution"] = {"mode": "process", "workers": 2, "batch_size": 3}
        process_command = parse(json.dumps(data))
        process = run_npc_melee_simulation_parallel(process_command.request,
            workers=process_command.execution.workers, batch_size=process_command.execution.batch_size)
        self.assertEqual(process, sequential)
        expected = json.loads(encode(command, summarize_npc_melee_simulation(sequential)))
        actual = json.loads(encode(process_command, summarize_npc_melee_simulation(process)))
        self.assertEqual(actual["summary"], expected["summary"])
        self.assertEqual(actual["request"], data)
        self.assertEqual(parse(json.dumps(actual["request"])), process_command)
