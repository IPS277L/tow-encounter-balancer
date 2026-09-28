"""Pure v1 wire adapters. No RNG, execution, pool or application file I/O."""
from __future__ import annotations

from dataclasses import asdict
import json
import platform

from towr.adapters._ranged_json_common import read_request, build_value, parse_seed
from towr.adapters._ranged_scenario_json import parse_scenario, scenario_document
from towr import __version__
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code, RangedSimulationInputError
from towr.adapters.ranged_json_schema import validate_ranged_document
from towr.application.ranged_simulation_models import (
    RangedSimulationCommand, SimulationExecutionMode, SimulationExecutionOptions,
)
from towr.application.ranged_simulation_errors import RangedSimulationExecutionError
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


def parse_ranged_simulation_request(text: str | bytes) -> RangedSimulationCommand:
    """Parse strict UTF-8 JSON and perform full existing scenario admission."""
    document = read_request(text, RangedSimulationInputError, validate_ranged_document)
    try:
        return _parse_document(document)
    except RangedSimulationInputError as error:
        error.request_id = document["request_id"]
        raise
    except (TypeError, ValueError) as error:
        raise RangedSimulationInputError(Code.INVALID_INPUT, str(error),
            path="/scenario", request_id=document["request_id"]) from error


def _parse_document(document) -> RangedSimulationCommand:
    options = document["simulation"]
    scenario, definitions = parse_scenario(document["scenario"], document["request_id"], options["round_budget"],
        path_prefix="/scenario", error_type=RangedSimulationInputError)
    seed = parse_seed(options["master_seed"], RangedSimulationInputError, "/simulation/master_seed")
    request = build_value(RangedSimulationInputError, "/simulation", NpcRangedSimulationRequest,
                          scenario, seed, options["trials"])
    execution = document["execution"]
    return RangedSimulationCommand(request, SimulationExecutionOptions(SimulationExecutionMode(execution["mode"]),
        execution.get("workers"), execution.get("batch_size")), definitions)


def _request_document(command: RangedSimulationCommand) -> dict:
    scenario = command.request.scenario
    execution = {"mode": command.execution.mode.value}
    if command.execution.mode is SimulationExecutionMode.PROCESS:
        execution.update(workers=command.execution.workers, batch_size=command.execution.batch_size)
    return {"schema_version": "1", "kind": "npc_ranged_simulation", "ruleset": "towr-pg1.4-gmg1.1",
        "request_id": scenario.initial.current.id,
        "simulation": {"master_seed": str(command.request.master_seed), "trials": command.request.trials,
                       "round_budget": scenario.initial.max_rounds}, "execution": execution,
        "scenario": scenario_document(scenario, command.definition_order)}


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
