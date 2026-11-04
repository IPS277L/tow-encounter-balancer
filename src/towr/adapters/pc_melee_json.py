"""Pure PC JSON1: canonical seed/fraction spellings permit exact source echo.

Input fractions must be reduced, including 0/1. No simulation or process startup.
"""
from dataclasses import asdict, replace
from fractions import Fraction
import json
import platform

from towr import __version__
from towr.adapters._json_common import build_value, parse_seed, read_request
from towr.adapters._pc_melee_scenario_json import (
    facts_document, parse_facts, parse_scenario, scenario_document,
)
from towr.adapters.pc_melee_json_errors import (
    PcMeleeBalanceInputError, PcMeleeInputError, PcMeleeSimulationInputError,
)
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document, validate_pc_melee_simulation_document,
)
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.application.pc_melee_balance_models import (
    PcMeleeBalanceRequest, PcMeleeBalanceResult, PcMeleeCompositionGroup,
    validate_pc_melee_balance_result,
)
from towr.application.pc_melee_commands import (
    PcMeleeBalanceCommand, PcMeleeCommandExecutionError, PcMeleeSimulationCommand,
)
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.simulation.pc_melee_models import SEED_SCHEME, PcMeleeSimulationRequest
from towr.simulation.pc_melee_summary_models import PcMeleeSimulationSummary


def _execution(data: dict) -> SimulationExecutionOptions:
    return SimulationExecutionOptions(SimulationExecutionMode(data["mode"]),
        data.get("workers"), data.get("batch_size"))


def _execution_document(execution: SimulationExecutionOptions) -> dict:
    result = {"mode": execution.mode.value}
    if execution.mode is SimulationExecutionMode.PROCESS:
        result.update(workers=execution.workers, batch_size=execution.batch_size)
    return result


def parse_pc_melee_simulation_request(text: str | bytes) -> PcMeleeSimulationCommand:
    document = read_request(text, PcMeleeSimulationInputError, validate_pc_melee_simulation_document)
    try:
        scenario = parse_scenario(document["scenario"], path_prefix="/scenario",
                                  error_type=PcMeleeSimulationInputError)
        options = document["simulation"]
        request = build_value(PcMeleeSimulationInputError, "/simulation", PcMeleeSimulationRequest,
            scenario, parse_seed(options["master_seed"], PcMeleeSimulationInputError,
                                 "/simulation/master_seed"), options["trials"])
        return PcMeleeSimulationCommand(document["request_id"], request, _execution(document["execution"]))
    except PcMeleeInputError as error:
        error.request_id = document["request_id"]
        raise
    except (TypeError, ValueError) as error:
        raise PcMeleeSimulationInputError(Code.INVALID_INPUT, str(error),
            path="/scenario", request_id=document["request_id"]) from error


def parse_pc_melee_balance_request(text: str | bytes) -> PcMeleeBalanceCommand:
    document = read_request(text, PcMeleeBalanceInputError, validate_pc_melee_balance_document)
    try:
        scenario = parse_scenario(document["template"], path_prefix="/template",
                                  error_type=PcMeleeBalanceInputError)
        generation, evaluation = document["generation"], document["evaluation"]
        groups = tuple(build_value(PcMeleeBalanceInputError, f"/generation/groups/{index}",
            PcMeleeCompositionGroup, **group) for index, group in enumerate(generation["groups"]))
        facts = build_value(PcMeleeBalanceInputError, "/generation/facts", parse_facts, generation["facts"])
        if facts != scenario.facts:
            raise PcMeleeBalanceInputError(Code.INVALID_INPUT,
                "generation facts must equal the complete template facts", path="/generation/facts")
        fractions = {}
        for name, value in evaluation["window"].items():
            fraction = Fraction(**value)
            if (fraction.numerator, fraction.denominator) != (value["numerator"], value["denominator"]):
                raise PcMeleeBalanceInputError(Code.INVALID_INPUT,
                    "window fractions must use reduced numerator/denominator", path=f"/evaluation/window/{name}")
            fractions[name] = fraction
        window = build_value(PcMeleeBalanceInputError, "/evaluation/window", ObjectiveRateWindow, **fractions)
        request = build_value(PcMeleeBalanceInputError, "/generation", PcMeleeBalanceRequest,
            scenario, groups, facts, parse_seed(evaluation["master_seed"], PcMeleeBalanceInputError,
                "/evaluation/master_seed"), evaluation["trials_per_candidate"], generation["max_candidates"],
            evaluation["max_total_trials"], window, evaluation["top_k"])
        return PcMeleeBalanceCommand(document["request_id"], request, _execution(document["execution"]))
    except PcMeleeInputError as error:
        error.request_id = document["request_id"]
        raise
    except (TypeError, ValueError) as error:
        raise PcMeleeBalanceInputError(Code.INVALID_INPUT, str(error),
            path="/generation", request_id=document["request_id"]) from error


def _fraction(value: Fraction) -> dict:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _window(window: ObjectiveRateWindow) -> dict:
    return {name: _fraction(getattr(window, name)) for name in ("minimum", "target", "maximum")}


def _simulation_request_document(command: PcMeleeSimulationCommand) -> dict:
    return {"schema_version": "1", "kind": "pc_melee_simulation", "request_id": command.request_id,
        "ruleset": "towr-pg1.4-gmg1.1", "scenario": scenario_document(command.request.scenario),
        "simulation": {"master_seed": str(command.request.master_seed), "trials": command.request.trials},
        "execution": _execution_document(command.execution)}


def _balance_request_document(command: PcMeleeBalanceCommand) -> dict:
    request = command.request
    return {"schema_version": "1", "kind": "pc_melee_balance", "request_id": command.request_id,
        "ruleset": "towr-pg1.4-gmg1.1", "template": scenario_document(request.template),
        "generation": {"groups": [{"group_id": group.group_id, "actor_ids": list(group.actor_ids),
            "minimum_count": group.minimum_count, "maximum_count": group.maximum_count}
            for group in request.groups], "facts": facts_document(request.facts),
            "max_candidates": request.max_candidates},
        "evaluation": {"master_seed": str(request.master_seed),
            "trials_per_candidate": request.trials_per_candidate, "max_total_trials": request.max_total_trials,
            "window": _window(request.window), "top_k": request.top_k},
        "execution": _execution_document(command.execution)}


def _runtime() -> dict:
    return {"package_version": __version__, "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(), "rng": "random.Random"}


def _summary(summary: PcMeleeSimulationSummary) -> dict:
    return {"trials": summary.trials, "outcome_counts": asdict(summary.outcome_counts),
        "total_action_count": summary.total_action_count,
        "total_started_round_count": summary.total_started_round_count,
        "total_completed_round_count": summary.total_completed_round_count,
        "any_pc_defeated_count": summary.any_pc_defeated_count,
        "pc_defeat_counts": [asdict(count) for count in summary.pc_defeat_counts]}


def encode_pc_melee_simulation_result(command: PcMeleeSimulationCommand,
                                      summary: PcMeleeSimulationSummary) -> str:
    if type(command) is not PcMeleeSimulationCommand or type(summary) is not PcMeleeSimulationSummary:
        raise TypeError("simulation encoding requires a PC command and aggregate summary")
    replace(command)
    replace(summary)
    if summary.source_request != command.request:
        raise ValueError("summary belongs to another complete simulation request")
    source = _simulation_request_document(command)
    if parse_pc_melee_simulation_request(json.dumps(source)) != command:
        raise ValueError("simulation source is not representable losslessly")
    document = {"schema_version": "1", "kind": "pc_melee_simulation_result", "request": source,
        "seed_scheme": SEED_SCHEME, "runtime": _runtime(), "summary": _summary(summary)}
    validate_pc_melee_simulation_document(document, "result")
    return json.dumps(document, ensure_ascii=False, allow_nan=False, indent=2) + "\n"


def encode_pc_melee_balance_result(command: PcMeleeBalanceCommand, result: PcMeleeBalanceResult) -> str:
    if type(command) is not PcMeleeBalanceCommand or type(result) is not PcMeleeBalanceResult:
        raise TypeError("balance encoding requires a PC command and complete balance result")
    replace(command)
    validate_pc_melee_balance_result(result)
    if result.source_request != command.request:
        raise ValueError("balance result belongs to another complete request")
    source = _balance_request_document(command)
    if parse_pc_melee_balance_request(json.dumps(source)) != command:
        raise ValueError("balance source is not representable losslessly")
    candidates = []
    for candidate in result.candidates:
        assessment = candidate.assessment
        candidates.append({"candidate_id": candidate.candidate_id, "counts": list(candidate.counts),
            "request": {"master_seed": str(candidate.source_request.master_seed),
                "trials": candidate.source_request.trials,
                "scenario": scenario_document(candidate.source_request.scenario)},
            "summary": _summary(candidate.summary),
            "assessment": {"status": assessment.status.value, "window": _window(assessment.window),
                **{name: _fraction(getattr(assessment, name)) for name in (
                    "objective_achieved_rate", "party_defeated_rate", "round_limit_rate", "unsupported_path_rate")},
                "window_match": assessment.window_match}})
    document = {"schema_version": "1", "kind": "pc_melee_balance_result", "request": source,
        "seed_scheme": SEED_SCHEME, "runtime": _runtime(), "candidate_count": result.candidate_count,
        "planned_trials": result.planned_trials, "total_trials": result.total_trials,
        "candidates": candidates, "selected_candidate_ids": list(result.selected_candidate_ids)}
    validate_pc_melee_balance_document(document, "result")
    return json.dumps(document, ensure_ascii=False, allow_nan=False, indent=2) + "\n"


def _encode_error(error, family: str) -> str:
    input_type = PcMeleeSimulationInputError if family == "simulation" else PcMeleeBalanceInputError
    if isinstance(error, input_type):
        code, phase, path, message = error.code.value, "input", error.path, str(error)
        candidate_id = candidate_index = None
    elif type(error) is PcMeleeCommandExecutionError:
        checked = PcMeleeCommandExecutionError(error.request_id, error.family, error.phase,
            candidate_id=error.candidate_id, candidate_index=error.candidate_index)
        if checked.family != family:
            raise TypeError("execution error belongs to another PC command family")
        code, phase, path = checked.code, checked.phase, "/" + checked.phase
        message = f"PC melee {family} {phase} failed"
        candidate_id, candidate_index = checked.candidate_id, checked.candidate_index
    else:
        raise TypeError("encoding requires this PC family's typed input or execution error")
    if error.schema_version != "1" or type(error.schema_version) is not str:
        raise ValueError("unsupported PC melee error version")
    document = {"schema_version": "1", "kind": f"pc_melee_{family}_error", "request_id": error.request_id,
        "error": {"code": code, "path": path, "message": message, "phase": phase,
                  "candidate_id": candidate_id, "candidate_index": candidate_index}}
    validator = validate_pc_melee_simulation_document if family == "simulation" else validate_pc_melee_balance_document
    validator(document, "error")
    return json.dumps(document, ensure_ascii=True, allow_nan=False, indent=2) + "\n"


def encode_pc_melee_simulation_error(error) -> str:
    return _encode_error(error, "simulation")


def encode_pc_melee_balance_error(error) -> str:
    return _encode_error(error, "balance")
