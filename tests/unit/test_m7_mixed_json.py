from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from importlib.resources import files
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator, ValidationError

from tests.unit.test_m4_ranged_json import at, object_paths
from towr.adapters.mixed_json_errors import MixedSimulationInputError
from towr.adapters.mixed_json_schema import validate_mixed_document
from towr.adapters.mixed_simulation_json import (
    parse_mixed_simulation_request as parse, encode_mixed_simulation_result as encode,
)
from towr.adapters.melee_json_errors import MeleeInputError
from towr.adapters.ranged_json_errors import RangedInputError, RangedInputErrorCode as Code
from towr.application.mixed_simulation_models import MixedSimulationCommand
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.ranged_weapon_profiles import RangedWeaponHands
from towr.domain.test_models import Skill
from towr.simulation.npc_mixed_models import NpcMixedOutcomeCounts
from towr.simulation.npc_mixed_summary_models import NpcMixedSimulationSummary


EXAMPLES = Path(__file__).resolve().parents[2] / "docs/examples/m7/json"


def document():
    return json.loads((EXAMPLES / "mixed-simulation-v1.request.json").read_text(encoding="utf-8"))


def summary(command):
    # A valid synthetic aggregate tests the codec without sampling a distribution.
    return NpcMixedSimulationSummary(command.request,
        NpcMixedOutcomeCounts(0, 0, 0, command.request.trials), 0, command.request.trials)


class M7MixedJsonTests(unittest.TestCase):
    def assert_invalid(self, data, code=Code.INVALID_INPUT):
        with self.assertRaises(MixedSimulationInputError) as caught:
            parse(json.dumps(data))
        self.assertEqual(caught.exception.code, code)
        self.assertNotIsInstance(caught.exception, RangedInputError)
        self.assertNotIsInstance(caught.exception, MeleeInputError)
        return caught.exception

    def test_packaged_schemas_and_contract_fixtures(self):
        for kind in ("request", "result", "error"):
            resource = files("towr.adapters.schemas").joinpath(f"mixed-simulation-{kind}-v1.schema.json")
            schema = json.loads(resource.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            self.assertEqual(schema["$id"], f"urn:towr:mixed-simulation:{kind}:1")
        validate_mixed_document(document(), "request")
        result = json.loads((EXAMPLES / "mixed-simulation-v1.result.json").read_text(encoding="utf-8"))
        validate_mixed_document(result, "result")
        error = {"schema_version": "1", "kind": "mixed_simulation_error", "request_id": None,
                 "error": {"code": "invalid_input", "path": "/a~1b/~0", "message": "invalid input"}}
        validate_mixed_document(error, "error")
        for target, kind in ((result, "result"), (error, "error")):
            for path in object_paths(target):
                for key in (None, *at(target, path)):
                    with self.subTest(kind=kind, path=path, key=key):
                        data = deepcopy(target)
                        if key is None:
                            at(data, path)["unexpected"] = True
                        else:
                            del at(data, path)[key]
                        with self.assertRaises(ValidationError):
                            validate_mixed_document(data, kind)
        for path in ("/bad~2", "\n", "/bad~\n", "no-slash"):
            with self.subTest(path=path), self.assertRaises(ValidationError):
                validate_mixed_document(dict(error, error=dict(error["error"], path=path)), "error")
        with self.assertRaises(ValidationError):
            validate_mixed_document(dict(result, trials=[]), "result")
        with self.assertRaises(ValueError):
            validate_mixed_document({}, "balance")

    def test_example_is_fresh_immutable_and_has_explicit_mixed_profiles(self):
        data = document()
        command = parse(json.dumps(data).encode("utf-8"))
        scenario = command.request.scenario
        self.assertEqual(command.request.master_seed, 42)
        self.assertEqual(command.execution, SimulationExecutionOptions(SimulationExecutionMode.SEQUENTIAL))
        self.assertEqual(scenario.initial.current.id, data["request_id"])
        self.assertEqual(scenario.initial.current.state.consumed_execution_ids, ())
        self.assertIsNone(scenario.initial.current.round_state.active_turn)
        self.assertEqual(scenario.initial.current.pending_follow_ups, ())
        participants = scenario.initial.current.state.roster.participants
        self.assertIs(participants[1].definition, participants[2].definition)
        self.assertIsNot(participants[1].state, participants[2].state)
        self.assertTrue(all(p.state.injury.wounds == 0 and not p.state.injury.conditions.conditions for p in participants))
        self.assertEqual(participants[0].definition.attacks[0].skill, Skill.SHOOTING)
        self.assertEqual(participants[0].definition.attacks[0].hands, RangedWeaponHands.TWO_HANDED)
        self.assertEqual(participants[0].definition.protection[0].skill, Skill.ATHLETICS)
        self.assertTrue(all(p.outnumbering_bonus_approved for p in scenario.actor_policies))
        data["scenario"]["actors"].clear()
        self.assertEqual(len(participants), 5)
        with self.assertRaises(FrozenInstanceError):
            command.definition_order = ()
        self.assertFalse(hasattr(command, "__dict__"))

    def test_strict_reader_uses_separate_errors_without_changing_lexical_rules(self):
        cases = [(b'\xff', Code.INVALID_JSON), ('{', Code.INVALID_JSON),
                 ('{"a":1,"a":2}', Code.INVALID_JSON), ('{"a":{"b":1,"b":2}}', Code.INVALID_JSON),
                 ('{"a":NaN}', Code.INVALID_JSON), ('{"a":Infinity}', Code.INVALID_JSON),
                 ('{"a":-Infinity}', Code.INVALID_JSON), ('{"a":1.0}', Code.INVALID_INPUT),
                 ('{"a":1e0}', Code.INVALID_INPUT), ('{"a":1e999}', Code.INVALID_INPUT),
                 ('{} {}', Code.INVALID_JSON), ('\ufeff{}', Code.INVALID_JSON),
                 (json.dumps({"a": chr(0xD800)}), Code.INVALID_JSON),
                 (json.dumps({chr(0xD800): "a"}), Code.INVALID_JSON)]
        for raw, code in cases:
            with self.subTest(raw=raw), self.assertRaises(MixedSimulationInputError) as caught:
                parse(raw)
            self.assertEqual(caught.exception.code, code)
        for data in ([], None, 1, "object"):
            self.assert_invalid(data)
        for raw in (None, {}, bytearray(b"{}")):
            with self.assertRaises(TypeError):
                parse(raw)

    def test_envelope_version_and_family_do_not_fallback(self):
        for field, value in (("schema_version", "2"), ("schema_version", 1),
                             ("kind", "npc_ranged_simulation"), ("kind", "npc_mixed_balance"),
                             ("ruleset", "other")):
            with self.subTest(field=field, value=value):
                data = dict(document(), **{field: value})
                error = self.assert_invalid(data, Code.UNSUPPORTED_VERSION if value == "2" else Code.INVALID_INPUT)
                self.assertEqual(error.request_id, data["request_id"])
                self.assertEqual(error.path, "/" + field)

    def test_unknown_and_missing_fields_at_every_input_object(self):
        source = document()
        for path in object_paths(source):
            for key in (None, *at(source, path)):
                with self.subTest(path=path, key=key):
                    data = deepcopy(source)
                    if key is None:
                        at(data, path)["extra_rule"] = True
                    else:
                        del at(data, path)[key]
                    self.assert_invalid(data)

    def test_uint64_seed_spelling_and_exact_large_counters(self):
        for seed in ("0", str(2**64-1)):
            data = document()
            data["simulation"].update(master_seed=seed, trials=2**64-1)
            command = parse(json.dumps(data))
            self.assertEqual(command.request.master_seed, int(seed))
            encoded = json.loads(encode(command, summary(command)))
            self.assertEqual(encoded["request"], data)
            self.assertEqual(encoded["summary"]["trials"], 2**64-1)
        for value in (0, True, "01", "-1", "+1", " 1", "1\n", "1.0", "1e0", "", str(2**64), "9"*21):
            with self.subTest(seed=value):
                data = document()
                data["simulation"]["master_seed"] = value
                error = self.assert_invalid(data)
                self.assertEqual(error.path, "/simulation/master_seed")

    def test_integer_fields_and_identifiers_reject_coercion(self):
        for path, values in (
            (("simulation", "trials"), (0, 2**64, True, "3", 3.0)),
            (("simulation", "round_budget"), (0, False, "5")),
            (("scenario", "definitions", 0, "attack", "dice"), (0, -1, True, "3")),
            (("scenario", "definitions", 0, "attack", "threshold"), (0, 11)),
            (("scenario", "definitions", 0, "attack", "damage"), (-1, True)),
            (("scenario", "definitions", 0, "resilience", "toughness"), (-1, True)),
            (("scenario", "definitions", 0, "protection", "dice"), (0, True)),
            (("request_id",), ("", " \t", 17)),
        ):
            for value in values:
                with self.subTest(path=path, value=value):
                    data = document()
                    at(data, path[:-1])[path[-1]] = value
                    self.assert_invalid(data)

    def test_process_options_are_explicit_and_reuse_historical_class(self):
        for workers in (1, 61):
            data = document()
            data["execution"] = {"mode": "process", "workers": workers, "batch_size": 2**53+1}
            command = parse(json.dumps(data))
            self.assertIs(type(command.execution), SimulationExecutionOptions)
            self.assertIs(command.execution.mode, SimulationExecutionMode.PROCESS)
            self.assertEqual(json.loads(encode(command, summary(command)))["request"], data)
        for options in ({"mode": "sequential", "workers": 1}, {"mode": "process"},
                        {"mode": "process", "workers": 62, "batch_size": 1},
                        {"mode": "process", "workers": True, "batch_size": 1},
                        {"mode": "process", "workers": 2, "batch_size": 0}, {"mode": "auto"}):
            self.assert_invalid(dict(document(), execution=options))

    def test_all_required_true_facts_and_stagger_choice(self):
        for name in document()["scenario"]["facts"]:
            for value in ((True, 0, "false") if name == "requires_reload_action" else (False, 1, "true")):
                data = document()
                data["scenario"]["facts"][name] = value
                error = self.assert_invalid(data)
                self.assertEqual(error.path, f"/scenario/facts/{name}")
        data = document()
        data["scenario"]["repeated_stagger_choice"] = "give_ground"
        self.assert_invalid(data)

    def test_escape_flags_are_actor_scoped_explicit_and_not_coerced(self):
        data = document()
        policies = data["scenario"]["actor_policies"]
        policies[1]["can_leave_zone"] = True
        command = parse(json.dumps(data))
        self.assertEqual([p.can_leave_zone for p in command.request.scenario.actor_policies],
                         [False, True, False, False, False])
        self.assertEqual(json.loads(encode(command, summary(command)))["request"], data)
        for value in (0, 1, None, "false"):
            policies[1]["can_leave_zone"] = value
            self.assert_invalid(data)
        data = document()
        data["scenario"]["facts"]["can_leave_zone"] = True
        self.assert_invalid(data)

    def test_semantic_references_orders_objective_and_graph(self):
        mutations = [
            lambda s: s["definitions"].append(deepcopy(s["definitions"][0])),
            lambda s: s["definitions"].append(dict(s["definitions"][0], id="unused")),
            lambda s: s["actors"][0].update(definition_id="missing"),
            lambda s: s["actors"][1].update(id=s["actors"][0]["id"]),
            lambda s: s["actors"][0].update(zone_id="missing"),
            lambda s: s["actors"][0].update(zone_id="exit"),
            lambda s: s["battlefield"]["connections"].append({"first_zone_id": "arena", "second_zone_id": "rear"}),
            lambda s: s["battlefield"]["connections"][0].update(second_zone_id="rear"),
            lambda s: s["battlefield"]["connections"][0].update(second_zone_id="unknown"),
            lambda s: s["actor_order"].__setitem__(0, "missing"),
            lambda s: s["side_order"].reverse(),
            lambda s: [a.update(side="players_and_allies") for a in s["actors"]],
            lambda s: s.update(objective_target_ids=["P1"]),
            lambda s: s["objective_target_ids"].pop(),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                data = document()
                mutate(data["scenario"])
                error = self.assert_invalid(data)
                self.assertTrue(error.path.startswith("/scenario"))
                self.assertEqual(error.request_id, data["request_id"])

    def test_definition_errors_have_specific_pointers(self):
        data = document()
        data["scenario"]["definitions"].append(deepcopy(data["scenario"]["definitions"][0]))
        self.assertEqual(self.assert_invalid(data).path, "/scenario/definitions/2/id")
        data = document()
        data["scenario"]["actors"][0]["definition_id"] = "absent"
        self.assertEqual(self.assert_invalid(data).path, "/scenario/actors/0/definition_id")

    def test_policies_require_all_enemies_and_explicit_gm_approval(self):
        for field, value in (("target_id", "P1"), ("target_id", "unknown"),
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
            elif variant == "missing_target": policies[0]["targets"].pop()
            else: policies.pop()
            with self.subTest(variant=variant): self.assert_invalid(data)
        for disposition in NpcDefeatDisposition:
            data = document()
            data["scenario"]["actor_policies"][0]["targets"][0]["disposition"] = disposition.value
            command = parse(json.dumps(data))
            self.assertEqual(json.loads(encode(command, summary(command)))["request"], data)

    def test_false_outnumbering_is_preserved_but_not_coerced(self):
        data = document()
        data["scenario"]["actor_policies"][0]["outnumbering_bonus_approved"] = False
        command = parse(json.dumps(data))
        self.assertFalse(command.request.scenario.actor_policies[0].outnumbering_bonus_approved)
        self.assertEqual(json.loads(encode(command, summary(command)))["request"], data)
        for value in (0, 1, None, "false"):
            data["scenario"]["actor_policies"][0]["outnumbering_bonus_approved"] = value
            self.assert_invalid(data)

    def test_supplied_two_hands_zero_damage_and_toughness(self):
        data = document()
        profile = data["scenario"]["definitions"][1]
        profile["source_rule_id"] = "caller:supplied-numeric-profile"
        profile["attack"].update(hands="2h", damage=0)
        profile["resilience"]["toughness"] = 0
        profile["protection"]["skill"] = "athletics"
        command = parse(json.dumps(data))
        definition = command.request.scenario.initial.current.state.roster.participants[1].definition
        self.assertEqual(definition.attacks[0].hands, RangedWeaponHands.TWO_HANDED)
        self.assertEqual(definition.protection[0].skill, Skill.ATHLETICS)
        self.assertEqual(json.loads(encode(command, summary(command)))["request"], data)
        profile["protection"]["skill"] = "mixed"
        self.assert_invalid(data)
        profile["protection"]["skill"] = "athletics"
        profile["attack"]["hands"] = "automatic"
        self.assert_invalid(data)

    def test_command_type_tuple_copy_and_replace_guards(self):
        command = parse(json.dumps(document()))
        for changes in ({"request": None}, {"execution": None}, {"definition_order": ()},
                        {"definition_order": (*command.definition_order, *command.definition_order)},
                        {"definition_order": ("unknown",)}, {"definition_order": (" ",)}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(command, **changes)
        order = list(command.definition_order)
        copied = MixedSimulationCommand(command.request, command.execution, order)
        order.clear()
        self.assertEqual(copied, command)
        from tests.unit.test_m4_ranged_json import document as ranged_document
        from towr.adapters.ranged_simulation_json import parse_ranged_simulation_request
        ranged = parse_ranged_simulation_request(json.dumps(ranged_document()))
        with self.assertRaises(TypeError):
            replace(command, request=ranged.request)
        with self.assertRaises(TypeError):
            encode(ranged, summary(command))

    def test_array_orders_unicode_ids_and_whitespace_are_lossless(self):
        data = document()
        data["request_id"] = " example:" + chr(0x1F3F9) + " "
        scenario = data["scenario"]
        other = deepcopy(scenario["definitions"][0])
        other["id"] = "other"
        scenario["definitions"].insert(0, other)
        scenario["actors"][0]["definition_id"] = "other"
        del scenario["definitions"][1]
        scenario["actors"].reverse()
        scenario["actor_order"].reverse()
        scenario["actor_policies"].reverse()
        for policy in scenario["actor_policies"]:
            policy["targets"].reverse()
        scenario["objective_target_ids"].reverse()
        scenario["battlefield"]["zone_ids"].insert(0, "empty")
        scenario["battlefield"]["connections"].insert(0, {"first_zone_id": "empty", "second_zone_id": "far"})
        command = parse(json.dumps(data))
        before = deepcopy(command)
        wire = encode(command, summary(command))
        self.assertTrue(wire.endswith("\n"))
        self.assertEqual(json.loads(wire)["request"], data)
        self.assertEqual(parse(json.dumps(json.loads(wire)["request"])), command)
        self.assertEqual(command, before)

    def test_opposition_perspective_is_preserved(self):
        data = document()
        data["scenario"].update(perspective_side="opposition", objective_target_ids=["P2", "P1", "Pbow"])
        command = parse(json.dumps(data))
        self.assertEqual(json.loads(encode(command, summary(command)))["request"], data)

    def test_encoder_requires_exact_summary_source(self):
        command = parse(json.dumps(document()))
        observed = summary(command)
        scenario = command.request.scenario
        for request in (replace(command.request, master_seed=43),
                        replace(command.request, trials=9),
                        replace(command.request, scenario=replace(scenario, initial=replace(scenario.initial, max_rounds=4))),
                        replace(command.request, scenario=replace(scenario, actor_policies=(
                            replace(scenario.actor_policies[0], outnumbering_bonus_approved=False), *scenario.actor_policies[1:])))):
            with self.assertRaisesRegex(ValueError, "different simulation"):
                encode(replace(command, request=request), observed)
        with self.assertRaises(TypeError):
            encode(command, None)

    def test_encoder_rejects_unrepresentable_combat_and_spatial_order(self):
        command = parse(json.dumps(document()))
        scenario = command.request.scenario
        initial = scenario.initial
        for changed in (
            replace(initial, spatial_state=replace(initial.spatial_state, placements=initial.spatial_state.placements[::-1])),
            replace(initial, current=replace(initial.current, round_state=replace(initial.current.round_state,
                participants=initial.current.round_state.participants[::-1]))),
        ):
            altered = replace(command, request=replace(command.request, scenario=replace(scenario, initial=changed)))
            with self.assertRaisesRegex(ValueError, "losslessly"):
                encode(altered, summary(altered))

    def test_aggregate_only_shape_preserves_four_counts_and_exact_totals(self):
        command = parse(json.dumps(document()))
        observed = NpcMixedSimulationSummary(command.request, NpcMixedOutcomeCounts(2, 2, 2, 2), 9, 12)
        result = json.loads(encode(command, observed))
        self.assertNotIn("trials", result)
        self.assertEqual(result["summary"], {
            "trials": 8, "outcome_counts": {"objective_achieved": 2, "side_defeated": 2, "round_limit": 2, "unsupported_path": 2},
            "total_attack_count": 9, "total_visited_round_count": 12,
            "mean_attack_count": 1.125, "mean_visited_round_count": 1.5})

    def test_contract_result_projection_matches_existing_fixture(self):
        command = parse(json.dumps(document()))
        expected = json.loads((EXAMPLES / "mixed-simulation-v1.result.json").read_text(encoding="utf-8"))
        saved = expected["summary"]
        observed = NpcMixedSimulationSummary(command.request, NpcMixedOutcomeCounts(**saved["outcome_counts"]),
            saved["total_attack_count"], saved["total_visited_round_count"])
        actual = json.loads(encode(command, observed))
        expected["runtime"] = actual["runtime"]
        self.assertEqual(actual, expected)

    def test_parser_and_encoder_do_not_run_rng_or_simulation_or_pool(self):
        with patch("random.Random", side_effect=AssertionError("RNG created")), \
                patch("towr.simulation.npc_mixed_simulation.run_npc_mixed_simulation", side_effect=AssertionError("simulation ran")), \
                patch("towr.simulation.npc_mixed_parallel.ProcessPoolExecutor", side_effect=AssertionError("pool created")):
            command = parse(json.dumps(document()))
            self.assertEqual(json.loads(encode(command, summary(command)))["request"], document())
            invalid = document()
            invalid["scenario"]["facts"]["targets_aware"] = False
            self.assert_invalid(invalid)

    def test_pairs_require_every_enemy_once_with_explicit_admitted_range(self):
        mutations = [
            lambda s: s["pair_ranges"].pop(),
            lambda s: s["pair_ranges"].append(deepcopy(s["pair_ranges"][0])),
            lambda s: s["pair_ranges"].append(dict(s["pair_ranges"][0], first_actor_id="E1", second_actor_id="Pbow")),
            lambda s: s["pair_ranges"][0].update(first_actor_id="missing"),
            lambda s: s["pair_ranges"][0].update(second_actor_id="Pbow"),
            lambda s: s["pair_ranges"][0].update(second_actor_id="P1"),
            lambda s: s["pair_ranges"][0].update(target_range="close"),
            lambda s: s["pair_ranges"][2].update(target_range="medium"),
            lambda s: s["pair_ranges"][0].update(target_range="long"),
            lambda s: s["battlefield"]["connections"].clear(),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                data = document()
                mutate(data["scenario"])
                error = self.assert_invalid(data)
                self.assertTrue(error.path.startswith("/scenario"))
                self.assertEqual(error.request_id, data["request_id"])

    def test_pairs_orientation_and_independent_orders_round_trip(self):
        data = document()
        scenario = data["scenario"]
        scenario["pair_ranges"].reverse()
        for pair in scenario["pair_ranges"]:
            pair["first_actor_id"], pair["second_actor_id"] = pair["second_actor_id"], pair["first_actor_id"]
        scenario["definitions"].reverse()
        scenario["actors"].reverse()
        scenario["actor_policies"].reverse()
        command = parse(json.dumps(data))
        self.assertEqual(json.loads(encode(command, summary(command)))["request"], data)

    def test_attack_role_range_hands_and_protection_are_never_inferred(self):
        for index, field, value in ((0, "skill", "melee"), (0, "hands", "1h"),
                                    (0, "range_min", "close"), (0, "range_max", "close"),
                                    (1, "range_min", "medium"), (1, "range_max", "long"),
                                    (1, "skill", "throwing")):
            with self.subTest(index=index, field=field, value=value):
                data = document()
                data["scenario"]["definitions"][index]["attack"][field] = value
                self.assert_invalid(data)
        for skill in ("melee", "defence", "shooting"):
            data = document()
            data["scenario"]["definitions"][0]["protection"]["skill"] = skill
            self.assert_invalid(data)

    def test_both_roles_and_initial_reachable_target_are_required(self):
        data = document()
        scenario = data["scenario"]
        scenario["definitions"][0]["attack"].update(skill="melee", range_min="close", range_max="close")
        scenario["actors"][0]["zone_id"] = "arena"
        for pair in scenario["pair_ranges"]:
            pair["target_range"] = "close"
        self.assert_invalid(data)
        data = document()
        scenario = data["scenario"]
        scenario["actors"][1]["zone_id"] = "far"
        for pair in scenario["pair_ranges"]:
            if pair["first_actor_id"] == "P1":
                pair["target_range"] = "medium"
        self.assert_invalid(data)
        # No Shooting attack is allowed while ANY enemy is at Close.
        data = document()
        scenario = data["scenario"]
        scenario["actors"][0]["zone_id"] = "arena"
        for pair in scenario["pair_ranges"]:
            if pair["first_actor_id"] == "Pbow":
                pair["target_range"] = "close"
        self.assert_invalid(data)

    def test_summary_source_includes_pairs_and_actor_escape_flags(self):
        command = parse(json.dumps(document()))
        observed = summary(command)
        scenario = command.request.scenario
        pair = scenario.pair_ranges[0]
        for altered in (
            replace(scenario, pair_ranges=scenario.pair_ranges[::-1]),
            replace(scenario, pair_ranges=(replace(pair, first_actor_id=pair.second_actor_id,
                                                   second_actor_id=pair.first_actor_id), *scenario.pair_ranges[1:])),
            replace(scenario, actor_policies=(replace(scenario.actor_policies[0], can_leave_zone=True),
                                               *scenario.actor_policies[1:])),
        ):
            changed = replace(command, request=replace(command.request, scenario=altered))
            with self.assertRaisesRegex(ValueError, "different simulation"):
                encode(changed, observed)

    def test_wrong_family_and_unordered_definition_order_are_rejected(self):
        from tests.unit.test_m6_melee_json import document as melee_document
        from towr.adapters.melee_simulation_json import parse_melee_simulation_request
        melee = parse_melee_simulation_request(json.dumps(melee_document()))
        command = parse(json.dumps(document()))
        for order in (None, set(command.definition_order), "ab", iter(command.definition_order)):
            with self.assertRaises(TypeError):
                replace(command, definition_order=order)
        with self.assertRaises(TypeError):
            replace(command, request=melee.request)
        with self.assertRaises(TypeError):
            encode(melee, summary(command))
        data = document()
        data["kind"] = "npc_melee_simulation"
        self.assert_invalid(data)
