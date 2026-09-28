"""Pure v1 wire adapters. No RNG, execution, pool or application file I/O."""
from __future__ import annotations

from dataclasses import asdict
import json
import platform

from jsonschema import ValidationError

from towr import __version__
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code, RangedSimulationInputError
from towr.adapters.ranged_json_schema import validate_ranged_document
from towr.application.ranged_simulation_models import (
    RangedSimulationCommand, SimulationExecutionMode, SimulationExecutionOptions,
)
from towr.application.ranged_simulation_errors import RangedSimulationExecutionError
from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.condition_models import StaggerChoice
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_ranged_scenario_models import NpcRangedActorPolicy, NpcRangedScenario, NpcRangedScenarioFacts
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.npc_roster_models import NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile, NpcRoster
from towr.domain.npc_round_request_models import NpcRoundRequest
from towr.domain.npc_rounds_models import NpcRoundsRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponHands as Hands, RangedWeaponRange as Range
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneConnection, ZoneGraph
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatRoundState, CombatSide
from towr.simulation.npc_ranged_models import SEED_SCHEME, NpcRangedSimulationRequest, NpcRangedSimulationResult


def encode_ranged_simulation_error(
    error: RangedSimulationInputError | RangedSimulationExecutionError,
) -> str:
    """Encode known boundary errors only; never infer a category from a raw exception."""
    if isinstance(error, RangedSimulationInputError):
        code, path = error.code.value, error.path
    elif isinstance(error, RangedSimulationExecutionError):
        code, path = "execution_failed", None
    else:
        raise TypeError("error encoding requires a typed input or execution error")
    document = {
        "schema_version": "1", "kind": "simulation_error", "request_id": error.request_id,
        "error": {"code": code, "path": path, "message": str(error)},
    }
    validate_ranged_document(document, "error")
    # Malformed input diagnostics may themselves include lone Unicode surrogates.
    # Escaping keeps even these error envelopes valid UTF-8 text.
    return json.dumps(document, indent=2, ensure_ascii=True, allow_nan=False) + "\n"


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RangedSimulationInputError(Code.INVALID_JSON, f"duplicate object key: {key}")
        result[key] = value
    return result


def _reject_float(token):
    raise RangedSimulationInputError(Code.INVALID_INPUT, "request numbers must use integer tokens")


def _reject_constant(token):
    raise RangedSimulationInputError(Code.INVALID_JSON, f"non-finite JSON number: {token}")


def _pointer(parts) -> str:
    return "".join("/" + str(part).replace("~", "~0").replace("/", "~1") for part in parts)


def _build(path, constructor, *args, **kwargs):
    try:
        return constructor(*args, **kwargs)
    except (TypeError, ValueError) as error:
        raise RangedSimulationInputError(Code.INVALID_INPUT, str(error), path=path) from error


def parse_ranged_simulation_request(text: str | bytes) -> RangedSimulationCommand:
    """Parse strict UTF-8 JSON and perform full existing scenario admission."""
    if not isinstance(text, (str, bytes)):
        raise TypeError("request JSON must be str or UTF-8 bytes")
    try:
        if isinstance(text, bytes):
            text = text.decode("utf-8")
        text.encode("utf-8")
        document = json.loads(text, object_pairs_hook=_object, parse_float=_reject_float, parse_constant=_reject_constant)
        # Escaped lone surrogates parse in stdlib JSON but cannot be emitted as
        # UTF-8 by the encoder. Validate decoded strings, including object keys.
        pending = [document]
        while pending:
            item = pending.pop()
            if isinstance(item, str):
                item.encode("utf-8")
            elif isinstance(item, dict):
                pending.extend(item.keys())
                pending.extend(item.values())
            elif isinstance(item, list):
                pending.extend(item)
    except RangedSimulationInputError:
        raise
    except (ValueError, UnicodeError, RecursionError) as error:
        raise RangedSimulationInputError(Code.INVALID_JSON, str(error)) from error
    request_id = document.get("request_id") if isinstance(document, dict) else None
    if not isinstance(request_id, str) or not request_id.strip():
        request_id = None
    if isinstance(document, dict) and isinstance(document.get("schema_version"), str) and document["schema_version"] != "1":
        raise RangedSimulationInputError(Code.UNSUPPORTED_VERSION, "unsupported schema_version",
                                         path="/schema_version", request_id=request_id)
    try:
        validate_ranged_document(document, "request")
    except ValidationError as error:
        raise RangedSimulationInputError(Code.INVALID_INPUT, error.message,
            path=_pointer(error.absolute_path), request_id=request_id) from error
    try:
        return _parse_document(document)
    except RangedSimulationInputError as error:
        error.request_id = request_id
        raise
    except (TypeError, ValueError) as error:
        # Nested constructor arguments are evaluated before _build is entered.
        raise RangedSimulationInputError(Code.INVALID_INPUT, str(error),
                                         path="/scenario", request_id=request_id) from error


def _parse_document(document) -> RangedSimulationCommand:
    data = document["scenario"]
    definitions = {}
    for index, raw in enumerate(data["definitions"]):
        path = f"/scenario/definitions/{index}"
        if raw["id"] in definitions:
            raise RangedSimulationInputError(Code.INVALID_INPUT, "duplicate definition ID", path=path + "/id")
        attack, protection = raw["attack"], raw["protection"]
        definitions[raw["id"]] = _build(path, NpcDefinition, raw["id"], raw["source_rule_id"],
            TargetInjuryPolicy.MINION, 1, ResilienceProfile(**raw["resilience"]),
            (NpcAttackProfile(attack["id"], attack["source_rule_id"], Skill.SHOOTING,
                InlineProfile(attack["dice"], attack["threshold"]), DamageProfile(attack["damage"]),
                Range.MEDIUM, Range.LONG, Hands.TWO_HANDED),),
            (NpcProtectionProfile(protection["source_rule_id"], Skill.ATHLETICS,
                InlineProfile(protection["dice"], protection["threshold"])),))
    participants = []
    for index, actor in enumerate(data["actors"]):
        if actor["definition_id"] not in definitions:
            raise RangedSimulationInputError(Code.INVALID_INPUT, "unknown definition ID",
                                             path=f"/scenario/actors/{index}/definition_id")
        definition = definitions[actor["definition_id"]]
        participants.append(NpcParticipantSnapshot(definition, NpcParticipantState(
            actor["id"], definition.id, CombatSide(actor["side"]), ProfileInjuryState(0, 1),
            (definition.attacks[0].id,), definition.resilience, True, False)))
    if set(definitions) != {p.definition.id for p in participants}:
        raise RangedSimulationInputError(Code.INVALID_INPUT, "unused definition", path="/scenario/definitions")
    roster = _build("/scenario/actors", NpcRoster, tuple(participants))
    combat = _build("/scenario/side_order", CombatRoundState, 1, roster.turn_participants,
                    tuple(CombatSide(s) for s in data["side_order"]))
    current = _build("/scenario/actor_order", NpcRoundRequest, document["request_id"], NpcRosterAttackState(roster),
                     combat, tuple(data["actor_order"]), ())
    field = data["battlefield"]
    connections = tuple(_build(f"/scenario/battlefield/connections/{i}", ZoneConnection, **c)
                        for i, c in enumerate(field["connections"]))
    graph = _build("/scenario/battlefield", ZoneGraph, tuple(field["zone_ids"]), connections)
    spatial = _build("/scenario/actors", SpatialBattleState, graph,
        tuple(SpatialEntityPlacement(a["id"], a["side"], a["zone_id"]) for a in data["actors"]))
    policies = tuple(_build(f"/scenario/actor_policies/{i}", NpcRangedActorPolicy, p["actor_id"],
        tuple(t["target_id"] for t in p["targets"]),
        tuple(MinionDefeatDecision(p["actor_id"], t["target_id"], NpcDefeatDisposition(t["disposition"]), t["gm_approved"])
              for t in p["targets"])) for i, p in enumerate(data["actor_policies"]))
    options = document["simulation"]
    # Schema constrains the decimal spelling; numeric uint64 bounds belong here.
    seed = int(options["master_seed"])
    if seed >= 2**64:
        raise RangedSimulationInputError(Code.INVALID_INPUT, "master_seed must be less than 2**64",
                                         path="/simulation/master_seed")
    facts = dict(data["facts"], target_range=Range(data["facts"]["target_range"]))
    scenario = _build("/scenario", NpcRangedScenario,
        NpcRoundsRequest(current, spatial, options["round_budget"]), NpcRangedScenarioFacts(**facts), policies,
        StaggerChoice(data["repeated_stagger_choice"]), CombatSide(data["perspective_side"]),
        NpcDefeatObjective(tuple(data["objective_target_ids"])))
    request = _build("/simulation", NpcRangedSimulationRequest, scenario, seed, options["trials"])
    execution = document["execution"]
    return RangedSimulationCommand(request, SimulationExecutionOptions(SimulationExecutionMode(execution["mode"]),
        execution.get("workers"), execution.get("batch_size")), tuple(definitions))


def _request_document(command: RangedSimulationCommand) -> dict:
    scenario = command.request.scenario
    roster = scenario.initial.current.state.roster
    definitions = {p.definition.id: p.definition for p in roster.participants}
    profiles = []
    for identifier in command.definition_order:
        definition = definitions[identifier]
        attack, protection = definition.attacks[0], definition.protection[0]
        profiles.append({"id": identifier, "source_rule_id": definition.source_rule_id,
            "resilience": asdict(definition.resilience),
            "attack": {"id": attack.id, "source_rule_id": attack.source_rule_id, "dice": attack.test_profile.dice,
                       "threshold": attack.test_profile.threshold, "damage": attack.damage.base},
            "protection": {"source_rule_id": protection.source_rule_id, "dice": protection.test_profile.dice,
                           "threshold": protection.test_profile.threshold}})
    spatial = scenario.initial.spatial_state
    execution = {"mode": command.execution.mode.value}
    if command.execution.mode is SimulationExecutionMode.PROCESS:
        execution.update(workers=command.execution.workers, batch_size=command.execution.batch_size)
    facts = asdict(scenario.facts)
    facts["target_range"] = scenario.facts.target_range.value
    return {"schema_version": "1", "kind": "npc_ranged_simulation", "ruleset": "towr-pg1.4-gmg1.1",
        "request_id": scenario.initial.current.id,
        "simulation": {"master_seed": str(command.request.master_seed), "trials": command.request.trials,
                       "round_budget": scenario.initial.max_rounds}, "execution": execution,
        "scenario": {"definitions": profiles,
            "actors": [{"id": p.state.actor_id, "definition_id": p.definition.id, "side": p.state.side.value,
                        "zone_id": spatial.placement_for(p.state.actor_id).zone_id} for p in roster.participants],
            "battlefield": {"zone_ids": list(spatial.graph.zone_ids),
                            "connections": [asdict(c) for c in spatial.graph.connections]},
            "side_order": [s.value for s in scenario.initial.current.round_state.side_order],
            "actor_order": list(scenario.initial.current.actor_order), "perspective_side": scenario.perspective_side.value,
            "objective_target_ids": list(scenario.objective.target_actor_ids), "facts": facts,
            "repeated_stagger_choice": scenario.repeated_stagger_choice.value,
            "actor_policies": [{"actor_id": p.actor_id, "targets": [
                {"target_id": d.target_id, "disposition": d.disposition.value, "gm_approved": d.gm_approved}
                for d in p.defeat_decisions]} for p in scenario.actor_policies]}}


def encode_ranged_simulation_result(command: RangedSimulationCommand, result: NpcRangedSimulationResult) -> str:
    """Encode an already completed, source-bound result; never run a simulation."""
    if not isinstance(command, RangedSimulationCommand) or not isinstance(result, NpcRangedSimulationResult):
        raise TypeError("encoder requires a typed command and simulation result")
    if result.source_request != command.request:
        raise ValueError("result belongs to a different simulation request")
    request_document = _request_document(command)
    if parse_ranged_simulation_request(json.dumps(request_document)) != command:
        raise ValueError("command cannot be represented losslessly by JSON v1")
    document = {"schema_version": "1", "kind": "npc_ranged_simulation_result", "request": request_document,
        "seed_scheme": SEED_SCHEME,
        "runtime": {"package_version": __version__, "python_implementation": platform.python_implementation(),
                    "python_version": platform.python_version(), "rng": "random.Random"},
        "summary": {"outcome_counts": asdict(result.outcome_counts), "total_attack_count": result.total_attack_count,
                    "total_visited_round_count": result.total_visited_round_count,
                    "mean_attack_count": result.mean_attack_count, "mean_visited_round_count": result.mean_visited_round_count},
        "trials": [{"trial_index": t.trial_index, "seed_hex": f"{t.seed:064x}", "outcome": t.outcome.value,
                    "executed_attack_count": t.executed_attack_count, "visited_round_count": t.visited_round_count}
                   for t in result.trials]}
    validate_ranged_document(document, "result")
    return json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
