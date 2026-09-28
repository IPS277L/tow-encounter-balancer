"""Pure v1 wire adapters. No RNG, execution, pool or application file I/O."""
from __future__ import annotations

from dataclasses import asdict
import json
import platform

from towr.adapters._json_common import read_request, build_value, parse_seed
from towr.adapters._melee_scenario_json import parse_scenario, scenario_document
from towr import __version__
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.adapters.melee_json_errors import MeleeSimulationInputError
from towr.adapters.melee_json_schema import validate_melee_document
from towr.application.melee_simulation_models import MeleeSimulationCommand
from towr.application.melee_simulation_errors import MeleeSimulationExecutionError
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.simulation.npc_melee_models import SEED_SCHEME, NpcMeleeSimulationRequest
from towr.simulation.npc_melee_summary_models import NpcMeleeSimulationSummary


def encode_melee_simulation_error(
    error: MeleeSimulationInputError | MeleeSimulationExecutionError,
) -> str:
    """Encode only this boundary's typed failures, without causes or partial output."""
    if isinstance(error, MeleeSimulationInputError):
        code, path, message = error.code.value, error.path, str(error)
    elif isinstance(error, MeleeSimulationExecutionError):
        code, path, message = "execution_failed", None, "Simulation execution failed"
    else:
        raise TypeError("error encoding requires a typed melee input or execution error")
    document = {
        "schema_version": "1", "kind": "melee_simulation_error", "request_id": error.request_id,
        "error": {"code": code, "path": path, "message": message},
    }
    validate_melee_document(document, "error")
    # Diagnostics from malformed input may contain lone Unicode surrogates.
    return json.dumps(document, indent=2, ensure_ascii=True, allow_nan=False) + "\n"


def parse_melee_simulation_request(text: str | bytes) -> MeleeSimulationCommand:
    """Parse strict UTF-8 JSON and perform full existing scenario admission."""
    document = read_request(text, MeleeSimulationInputError, validate_melee_document)
    try:
        return _parse_document(document)
    except MeleeSimulationInputError as error:
        error.request_id = document["request_id"]
        raise
    except (TypeError, ValueError) as error:
        raise MeleeSimulationInputError(Code.INVALID_INPUT, str(error),
            path="/scenario", request_id=document["request_id"]) from error


def _parse_document(document) -> MeleeSimulationCommand:
    options = document["simulation"]
    scenario, definitions = parse_scenario(document["scenario"], document["request_id"], options["round_budget"],
        path_prefix="/scenario", error_type=MeleeSimulationInputError)
    seed = parse_seed(options["master_seed"], MeleeSimulationInputError, "/simulation/master_seed")
    request = build_value(MeleeSimulationInputError, "/simulation", NpcMeleeSimulationRequest,
                          scenario, seed, options["trials"])
    execution = document["execution"]
    return MeleeSimulationCommand(request, SimulationExecutionOptions(SimulationExecutionMode(execution["mode"]),
        execution.get("workers"), execution.get("batch_size")), definitions)


def _request_document(command: MeleeSimulationCommand) -> dict:
    scenario = command.request.scenario
    execution = {"mode": command.execution.mode.value}
    if command.execution.mode is SimulationExecutionMode.PROCESS:
        execution.update(workers=command.execution.workers, batch_size=command.execution.batch_size)
    return {"schema_version": "1", "kind": "npc_melee_simulation", "ruleset": "towr-pg1.4-gmg1.1",
        "request_id": scenario.initial.current.id,
        "simulation": {"master_seed": str(command.request.master_seed), "trials": command.request.trials,
                       "round_budget": scenario.initial.max_rounds}, "execution": execution,
        "scenario": scenario_document(scenario, command.definition_order)}


def encode_melee_simulation_result(command: MeleeSimulationCommand, result: NpcMeleeSimulationSummary) -> str:
    """Encode an already completed, source-bound result; never run a simulation."""
    if not isinstance(command, MeleeSimulationCommand) or not isinstance(result, NpcMeleeSimulationSummary):
        raise TypeError("encoder requires a typed command and simulation result")
    if result.source_request != command.request:
        raise ValueError("result belongs to a different simulation request")
    request_document = _request_document(command)
    if parse_melee_simulation_request(json.dumps(request_document)) != command:
        raise ValueError("command cannot be represented losslessly by JSON v1")
    document = {"schema_version": "1", "kind": "npc_melee_simulation_result", "request": request_document,
        "seed_scheme": SEED_SCHEME,
        "runtime": {"package_version": __version__, "python_implementation": platform.python_implementation(),
                    "python_version": platform.python_version(), "rng": "random.Random"},
        "summary": {"trials": result.trials, "outcome_counts": asdict(result.outcome_counts), "total_attack_count": result.total_attack_count,
                    "total_visited_round_count": result.total_visited_round_count,
                    "mean_attack_count": result.mean_attack_count, "mean_visited_round_count": result.mean_visited_round_count}}
    validate_melee_document(document, "result")
    return json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
