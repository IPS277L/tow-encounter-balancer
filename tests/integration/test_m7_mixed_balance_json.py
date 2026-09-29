from copy import deepcopy
import json
import unittest

from tests.unit.test_m7_mixed_balance_json import document
from towr.adapters.mixed_balance_json import parse_mixed_balance_request as parse, encode_mixed_balance_result as encode
from towr.adapters.mixed_json_schema import validate_mixed_balance_document
from towr.application.mixed_balance_models import MixedBalanceResult
from towr.application.mixed_candidate_generation import generate_mixed_candidates
from towr.application.mixed_staged_evaluation_service import evaluate_mixed_candidates_staged


class M7MixedBalanceJsonIntegrationTests(unittest.TestCase):
    def compare_backends(self, data):
        outputs = []
        for execution in ({"mode": "sequential"}, {"mode": "process", "workers": 2, "batch_size": 4}):
            data = dict(data, execution=execution)
            command = parse(json.dumps(data).encode("utf-8"))
            before = deepcopy(command)
            generated = generate_mixed_candidates(command.generation_request)
            result = MixedBalanceResult(generated, evaluate_mixed_candidates_staged(generated.evaluation_request, command.execution))
            evaluated = result.evaluation_result
            encoded = json.loads(encode(command, result))
            validate_mixed_balance_document(encoded, "result")
            self.assertEqual(encoded["request"], data)
            self.assertEqual(parse(json.dumps(encoded["request"])), command)
            self.assertEqual(command, before)
            self.assertEqual(encoded["total_trials"], evaluated.total_trials)
            self.assertLessEqual(encoded["total_trials"], command.generation_request.planned_trials)
            # Backend choice differs in the echoed request; no fixed Monte Carlo oracle.
            encoded["request"].pop("execution")
            outputs.append((evaluated, encoded))
        self.assertEqual(outputs[0], outputs[1])

    def test_documented_reserve_round_trip_through_real_sequential_and_spawn(self):
        self.compare_backends(document())

    def test_distinct_definitions_and_independent_orders_are_preserved(self):
        data = document()
        scenario = data["reserve"]["scenario"]
        alternate = deepcopy(scenario["definitions"][0])
        alternate["id"] = "other:bow"
        alternate["attack"]["damage"] = 4
        scenario["definitions"].insert(0, alternate)
        scenario["actors"][-1]["definition_id"] = alternate["id"]
        scenario["actor_order"].reverse()
        scenario["objective_target_ids"].reverse()
        scenario["actor_policies"].reverse()
        for policy in scenario["actor_policies"]:
            policy["targets"].reverse()
            policy["targets"][0]["disposition"] = "disarmed_and_surrendered"
        data["generation"]["groups"][0]["actor_ids"].reverse()
        data["generation"]["groups"].reverse()
        data["evaluation"]["stages"] = [dict(trials_per_candidate=2, keep=1), dict(trials_per_candidate=3, keep=1)]
        scenario["pair_ranges"].reverse()
        for pair in scenario["pair_ranges"]:
            pair["first_actor_id"], pair["second_actor_id"] = pair["second_actor_id"], pair["first_actor_id"]
        data["generation"]["pair_ranges"] = deepcopy(scenario["pair_ranges"])
        data["evaluation"]["max_total_trials"] = 11
        self.compare_backends(data)
