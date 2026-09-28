from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from importlib.resources import files
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator, ValidationError

from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code, RangedSimulationInputError
from towr.adapters.ranged_json_schema import validate_ranged_document
from towr.adapters.ranged_simulation_json import parse_ranged_simulation_request as parse, encode_ranged_simulation_result as encode
from towr.application.ranged_simulation_models import RangedSimulationCommand, SimulationExecutionMode as Mode, SimulationExecutionOptions
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.simulation.npc_ranged_simulation import run_npc_ranged_simulation


EXAMPLES = Path(__file__).resolve().parents[2] / "docs/examples/m4"


def document():
    return json.loads((EXAMPLES / "ranged-v1.request.json").read_text(encoding="utf-8"))


def at(root, path):
    for part in path:
        root = root[part]
    return root


def object_paths(value, prefix=()):
    if isinstance(value, dict):
        yield prefix
        for key, child in value.items():
            yield from object_paths(child, (*prefix, key))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from object_paths(child, (*prefix, i))


class M4RangedJsonTests(unittest.TestCase):
    def assert_invalid(self, data, code=Code.INVALID_INPUT):
        with self.assertRaises(RangedSimulationInputError) as caught:
            parse(json.dumps(data))
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_packaged_schemas_and_all_three_document_shapes(self):
        for kind in ("request", "result", "error"):
            schema = json.loads(files("towr.adapters.schemas").joinpath(
                f"ranged-simulation-{kind}-v1.schema.json").read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
        validate_ranged_document(document(), "request")
        result = json.loads((EXAMPLES / "ranged-v1.result.json").read_text(encoding="utf-8"))
        validate_ranged_document(result, "result")
        error = {"schema_version": "1", "kind": "simulation_error", "request_id": None,
                 "error": {"code": "invalid_input", "path": "/a~1b/~0", "message": "invalid input"}}
        validate_ranged_document(error, "error")
        for target, kind in ((result, "result"), (error, "error")):
            with self.subTest(kind=kind), self.assertRaises(ValidationError):
                validate_ranged_document(dict(target, unexpected=True), kind)
        with self.assertRaises(ValidationError):
            validate_ranged_document(dict(result, trials=[]), "result")
        with self.assertRaises(ValidationError):
            validate_ranged_document(dict(error, error=dict(error["error"], path="/bad~2")), "error")

    def test_example_maps_to_fresh_immutable_domain_with_explicit_policies(self):
        data = document()
        command = parse(json.dumps(data).encode("utf-8"))
        scenario = command.request.scenario
        self.assertEqual(command.request.master_seed, 20260928)
        self.assertEqual(command.execution.mode, Mode.SEQUENTIAL)
        self.assertEqual(scenario.initial.current.id, data["request_id"])
        self.assertEqual(scenario.initial.current.actor_order, ("archer:a", "archer:b"))
        self.assertEqual(scenario.initial.current.state.consumed_execution_ids, ())
        self.assertIsNone(scenario.initial.current.round_state.active_turn)
        self.assertEqual(scenario.initial.current.pending_follow_ups, ())
        self.assertEqual(scenario.policy_for("archer:a").target_actor_ids, ("archer:b",))
        self.assertEqual(scenario.policy_for("archer:a").defeat_decisions[0].disposition, NpcDefeatDisposition.KNOCKED_OUT)
        participants = scenario.initial.current.state.roster.participants
        self.assertIs(participants[0].definition, participants[1].definition)
        self.assertIsNot(participants[0].state, participants[1].state)
        self.assertTrue(all(p.state.injury.wounds == 0 and not p.state.injury.conditions.conditions for p in participants))
        data["scenario"]["actors"].clear()
        self.assertEqual(len(participants), 2)
        with self.assertRaises(FrozenInstanceError):
            command.definition_order = ()
        with self.assertRaises(FrozenInstanceError):
            command.execution.workers = 2

    def test_strict_json_duplicate_keys_nonfinite_float_tokens_and_utf8(self):
        cases = [('{"request_id":"a","request_id":"b"}', Code.INVALID_JSON),
                 ('{"a":{"x":1,"x":2}}', Code.INVALID_JSON),
                 ('{"a":NaN}', Code.INVALID_JSON), ('{"a":Infinity}', Code.INVALID_JSON),
                 ('{"a":-Infinity}', Code.INVALID_JSON), ('{"a":1e0}', Code.INVALID_INPUT),
                 ('{"a":1.0}', Code.INVALID_INPUT), ('{"a":1e999}', Code.INVALID_INPUT),
                 ('{', Code.INVALID_JSON), (b'\xff', Code.INVALID_JSON),
                 (json.dumps({"a": chr(0xD800)}), Code.INVALID_JSON),
                 (json.dumps({chr(0xD800): "a"}), Code.INVALID_JSON)]
        for raw, code in cases:
            with self.subTest(raw=raw), self.assertRaises(RangedSimulationInputError) as caught:
                parse(raw)
            self.assertEqual(caught.exception.code, code)
        self.assert_invalid([])
        self.assert_invalid(None)
        data = document()
        data["request_id"] = "example:" + chr(0x1F3F9)
        self.assertEqual(parse(json.dumps(data)).request.scenario.initial.current.id, data["request_id"])

    def test_version_kind_and_ruleset_are_explicit(self):
        for field, value in (("schema_version", "2"), ("schema_version", 1),
                             ("kind", "battle"), ("ruleset", "other")):
            data = document()
            data[field] = value
            code = Code.UNSUPPORTED_VERSION if value == "2" else Code.INVALID_INPUT
            error = self.assert_invalid(data, code)
            self.assertEqual(error.request_id, data["request_id"])
        data = document()
        del data["schema_version"]
        self.assert_invalid(data)

    def test_unknown_and_missing_keys_are_rejected_at_every_object_level(self):
        source = document()
        for path in object_paths(source):
            for key in (None, *at(source, path)):
                with self.subTest(path=path, key=key):
                    data = deepcopy(source)
                    target = at(data, path)
                    if key is None:
                        target["unrecognized_rule"] = True
                    else:
                        del target[key]
                    self.assert_invalid(data)

    def test_master_seed_spelling_and_uint64_bounds(self):
        for value in ("0", str(2**64-1)):
            data = document()
            data["simulation"]["master_seed"] = value
            self.assertEqual(parse(json.dumps(data)).request.master_seed, int(value))
        for value in (0, True, "01", "-1", "+1", " 1", "1\n", "1.0", "1e0", "", str(2**64), "9"*21):
            with self.subTest(value=value):
                data = document()
                data["simulation"]["master_seed"] = value
                self.assert_invalid(data)

    def test_numeric_fields_ids_and_process_options_reject_coercion(self):
        for path, values in (
            (("simulation", "trials"), (0, 2**64, True, "3", 3.0)),
            (("simulation", "round_budget"), (0, False, "5")),
            (("scenario", "definitions", 0, "attack", "dice"), (0, -1, True, "3")),
            (("scenario", "definitions", 0, "attack", "threshold"), (0, 11)),
            (("scenario", "definitions", 0, "attack", "damage"), (-1, True)),
            (("request_id",), ("", " \t", 17)),
        ):
            for value in values:
                with self.subTest(path=path, value=value):
                    data = document()
                    at(data, path[:-1])[path[-1]] = value
                    self.assert_invalid(data)
        for workers in (1, 61):
            data = document()
            data["execution"] = {"mode": "process", "workers": workers, "batch_size": 1}
            self.assertEqual(parse(json.dumps(data)).execution.workers, workers)
        for options in ({"mode": "sequential", "workers": 1}, {"mode": "process"},
                        {"mode": "process", "workers": 62, "batch_size": 1},
                        {"mode": "process", "workers": True, "batch_size": 1},
                        {"mode": "process", "workers": 2, "batch_size": 0}, {"mode": "auto"}):
            self.assert_invalid(dict(document(), execution=options))

    def test_all_facts_and_repeated_stagger_are_required_exact_values(self):
        source = document()
        for name, value in source["scenario"]["facts"].items():
            data = deepcopy(source)
            data["scenario"]["facts"][name] = not value if isinstance(value, bool) else "long"
            error = self.assert_invalid(data)
            self.assertEqual(error.path, f"/scenario/facts/{name}")
        data = document()
        data["scenario"]["repeated_stagger_choice"] = "give_ground"
        self.assert_invalid(data)

    def test_actor_definition_zone_and_order_semantic_guards(self):
        def duplicate_definition(s): s["definitions"].append(deepcopy(s["definitions"][0]))
        def unused_definition(s): s["definitions"].append(dict(s["definitions"][0], id="unused"))
        def unknown_definition(s): s["actors"][0]["definition_id"] = "missing"
        def duplicate_actor(s): s["actors"][1]["id"] = s["actors"][0]["id"]
        def unknown_zone(s): s["actors"][0]["zone_id"] = "missing"
        def same_zone(s): s["actors"][1]["zone_id"] = "left"
        def missing_edge(s): s["battlefield"]["connections"].clear()
        def duplicate_edge(s): s["battlefield"]["connections"].append({"first_zone_id":"right", "second_zone_id":"left"})
        def self_edge(s): s["battlefield"]["connections"][0]["second_zone_id"] = "left"
        def foreign_edge(s): s["battlefield"]["connections"][0]["second_zone_id"] = "unknown"
        def actor_order(s): s["actor_order"][0] = "missing"
        def one_side(s): s["actors"][1]["side"] = "players_and_allies"
        def wrong_objective(s): s["objective_target_ids"] = ["archer:a"]
        for mutate in (duplicate_definition, unused_definition, unknown_definition, duplicate_actor, unknown_zone,
                       same_zone, missing_edge, duplicate_edge, self_edge, foreign_edge, actor_order, one_side, wrong_objective):
            with self.subTest(case=mutate.__name__):
                data = document()
                mutate(data["scenario"])
                error = self.assert_invalid(data)
                self.assertIsNotNone(error.path)
                self.assertEqual(error.request_id, data["request_id"])

    def test_gm_policy_missing_foreign_duplicate_targets_and_dispositions(self):
        for field, value in (("target_id", "archer:a"), ("target_id", "unknown"),
                             ("gm_approved", False), ("gm_approved", 1), ("disposition", "dead")):
            data = document()
            data["scenario"]["actor_policies"][0]["targets"][0][field] = value
            self.assert_invalid(data)
        for variant in ("duplicate_actor", "foreign_actor", "duplicate_target", "missing_target", "missing_policy"):
            data = document()
            policies = data["scenario"]["actor_policies"]
            if variant == "duplicate_actor": policies[1] = deepcopy(policies[0])
            elif variant == "foreign_actor": policies[0]["actor_id"] = "unknown"
            elif variant == "duplicate_target": policies[0]["targets"].append(deepcopy(policies[0]["targets"][0]))
            elif variant == "missing_target": policies[0]["targets"].clear()
            else: policies.pop()
            with self.subTest(variant=variant): self.assert_invalid(data)
        for disposition in NpcDefeatDisposition:
            data = document()
            data["scenario"]["actor_policies"][0]["targets"][0]["disposition"] = disposition.value
            self.assertEqual(parse(json.dumps(data)).request.scenario.actor_policies[0].defeat_decisions[0].disposition, disposition)

    def test_typed_command_options_and_definition_order_cannot_be_forged_via_replace(self):
        command = parse(json.dumps(document()))
        for changes in ({"request": None}, {"execution": None}, {"definition_order": ()},
                        {"definition_order": ("brigand:ranged", "brigand:ranged")}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(command, **changes)
        for mode, workers, batch in (("sequential", None, None), (Mode.SEQUENTIAL, 1, None),
                                     (Mode.PROCESS, True, 1), (Mode.PROCESS, 62, 1), (Mode.PROCESS, 1, 0)):
            with self.assertRaises((ValueError, TypeError)):
                SimulationExecutionOptions(mode, workers, batch)
        order = ["brigand:ranged"]
        copied = RangedSimulationCommand(command.request, command.execution, order)
        order.clear()
        self.assertEqual(copied.definition_order, ("brigand:ranged",))

    def test_parsing_and_encoding_do_not_run_rng_or_simulation(self):
        data = document()
        command = parse(json.dumps(data))
        result = run_npc_ranged_simulation(command.request)
        with patch("random.Random", side_effect=AssertionError("RNG created")), patch(
            "towr.simulation.npc_ranged_simulation.run_npc_ranged_simulation", side_effect=AssertionError("simulation ran")
        ), patch("concurrent.futures.ProcessPoolExecutor", side_effect=AssertionError("pool created")):
            parsed = parse(json.dumps(data))
            encoded = json.loads(encode(parsed, result))
        self.assertEqual(encoded["request"], data)

    def test_encoder_rejects_foreign_request_and_preserves_input(self):
        command = parse(json.dumps(document()))
        before = deepcopy(command)
        result = run_npc_ranged_simulation(command.request)
        for changes in ({"master_seed": 42}, {"scenario": replace(command.request.scenario,
                              initial=replace(command.request.scenario.initial, max_rounds=6))}):
            foreign = replace(command, request=replace(command.request, **changes))
            with self.assertRaisesRegex(ValueError, "different simulation"):
                encode(foreign, result)
        with self.assertRaises(TypeError): encode(command, None)
        self.assertEqual(command, before)

    def test_encoder_rejects_unrepresentable_low_level_snapshot_order(self):
        command = parse(json.dumps(document()))
        scenario = command.request.scenario
        spatial = scenario.initial.spatial_state
        scenario = replace(scenario, initial=replace(scenario.initial,
            spatial_state=replace(spatial, placements=spatial.placements[::-1])))
        command = replace(command, request=replace(command.request, scenario=scenario))
        result = run_npc_ranged_simulation(command.request)
        with self.assertRaisesRegex(ValueError, "losslessly"):
            encode(command, result)
