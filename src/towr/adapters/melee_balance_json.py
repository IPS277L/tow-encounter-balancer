"""Pure balance v1 adapters. Parsing never generates or executes candidates."""
from dataclasses import asdict
from fractions import Fraction
from functools import partial
import json
import platform

from towr import __version__
from towr.adapters._json_common import build_value, parse_seed, read_request
from towr.adapters._melee_scenario_json import facts_document, parse_facts, parse_scenario, scenario_document
from towr.adapters.melee_json_errors import MeleeBalanceInputError
from towr.adapters.melee_json_schema import validate_melee_balance_document
from towr.application.melee_balance_models import MeleeBalanceCommand, MeleeBalanceResult
from towr.application.melee_balance_errors import MeleeBalanceGenerationError, MeleeBalanceExecutionError
from towr.application.melee_candidate_generation import _count_vectors
from towr.application.melee_candidate_generation_models import MeleeCandidateGenerationRequest, MeleeCompositionGroup
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.balance.melee_staged_evaluation import melee_continuation_candidate_ids
from towr.balance.melee_staged_evaluation_models import MeleeBalanceStage


def encode_melee_balance_error(
    error: MeleeBalanceInputError | MeleeBalanceGenerationError | MeleeBalanceExecutionError,
) -> str:
    """Encode this boundary's typed failures, without causes or partial reports."""
    path = candidate_id = counts = stage_index = None
    if isinstance(error, MeleeBalanceInputError):
        code, path, message = error.code.value, error.path, str(error)
    elif isinstance(error, MeleeBalanceGenerationError):
        code, candidate_id = "generation_failed", error.candidate_id
        counts = list(error.counts) if error.counts is not None else None
        message = "Balance candidate generation failed"
    elif isinstance(error, MeleeBalanceExecutionError):
        code, candidate_id, stage_index = "execution_failed", error.candidate_id, error.stage_index
        message = "Balance evaluation failed"
    else:
        raise TypeError("balance error encoding requires a typed melee input, generation or execution error")
    document = {
        "schema_version": "1", "kind": "melee_balance_error", "request_id": error.request_id,
        "error": {"code": code, "path": path, "message": message, "candidate_id": candidate_id,
                  "counts": counts, "stage_index": stage_index},
    }
    validate_melee_balance_document(document, "error")
    # Malformed-input messages may contain unpaired Unicode surrogates.
    return json.dumps(document, indent=2, ensure_ascii=True, allow_nan=False) + "\n"


def parse_melee_balance_request(text: str | bytes) -> MeleeBalanceCommand:
    """Read strict JSON, validate the reserve and preflight the complete budget."""
    document = read_request(text, MeleeBalanceInputError, validate_melee_balance_document)
    try:
        return _parse_document(document)
    except MeleeBalanceInputError as error:
        error.request_id = document["request_id"]
        raise


def _parse_document(document: dict) -> MeleeBalanceCommand:
    build = partial(build_value, MeleeBalanceInputError)
    reserve, generation, evaluation = document["reserve"], document["generation"], document["evaluation"]
    scenario, definition_order = parse_scenario(
        reserve["scenario"], reserve["initial_request_id"], reserve["round_budget"],
        path_prefix="/reserve/scenario", error_type=MeleeBalanceInputError,
    )
    groups = tuple(build(f"/generation/groups/{i}", MeleeCompositionGroup, **g)
                   for i, g in enumerate(generation["groups"]))
    facts = build("/generation/facts", parse_facts, generation["facts"])
    stages = tuple(build(f"/evaluation/stages/{i}", MeleeBalanceStage, **s)
                   for i, s in enumerate(evaluation["stages"]))
    seed = parse_seed(evaluation["master_seed"], MeleeBalanceInputError, "/evaluation/master_seed")
    window = build("/evaluation/window", ObjectiveRateWindow, **{
        name: Fraction(value["numerator"], value["denominator"])
        for name, value in evaluation["window"].items()
    })
    # Cross-group/stage/budget failures may concern both generation and evaluation.
    request = build("", MeleeCandidateGenerationRequest, scenario, groups, facts,
        generation["candidate_id_prefix"], generation["max_candidates"], seed, stages,
        evaluation["max_total_trials"], window)
    execution = document["execution"]
    options = build("/execution", SimulationExecutionOptions, SimulationExecutionMode(execution["mode"]),
                    execution.get("workers"), execution.get("batch_size"))
    return build("", MeleeBalanceCommand, document["request_id"], request, options, definition_order)


def _fraction_document(value: Fraction) -> dict:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _request_document(command: MeleeBalanceCommand) -> dict:
    source = command.generation_request
    scenario = source.template_scenario
    execution = {"mode": command.execution.mode.value}
    if command.execution.mode is SimulationExecutionMode.PROCESS:
        execution.update(workers=command.execution.workers, batch_size=command.execution.batch_size)
    return {
        "schema_version": "1", "kind": "npc_melee_balance", "ruleset": "towr-pg1.4-gmg1.1",
        "request_id": command.request_id,
        "reserve": {"initial_request_id": scenario.initial.current.id, "round_budget": scenario.initial.max_rounds,
                    "scenario": scenario_document(scenario, command.definition_order)},
        "generation": {"groups": [asdict(group) for group in source.groups], "facts": facts_document(source.facts),
                       "candidate_id_prefix": source.candidate_id_prefix, "max_candidates": source.max_candidates},
        "evaluation": {"master_seed": str(source.master_seed), "stages": [asdict(stage) for stage in source.stages],
                       "max_total_trials": source.max_total_trials,
                       "window": {name: _fraction_document(getattr(source.window, name))
                                  for name in ("minimum", "target", "maximum")}},
        "execution": execution,
    }


def encode_melee_balance_result(command: MeleeBalanceCommand, result: MeleeBalanceResult) -> str:
    """Encode a complete typed source chain, retaining aggregates only."""
    if not isinstance(command, MeleeBalanceCommand) or not isinstance(result, MeleeBalanceResult):
        raise TypeError("balance encoding requires a typed command and result")
    source = command.generation_request
    if result.generation_result.source_request != source:
        raise ValueError("balance result belongs to a different generation request")
    request_document = _request_document(command)
    if parse_melee_balance_request(json.dumps(request_document)) != command:
        raise ValueError("balance command cannot be represented losslessly by JSON v1")
    evaluation = result.evaluation_result
    catalog = [{"candidate_id": candidate.candidate_id, "counts": list(counts)}
               for candidate, counts in zip(result.generation_result.evaluation_request.candidates,
                                            _count_vectors(source), strict=True)]
    reports = []
    for index, report in enumerate(evaluation.stage_reports):
        candidates = []
        for candidate in report.candidates:
            assessment = candidate.assessment
            summary = assessment.summary
            candidates.append({
                "candidate_id": candidate.candidate_id,
                "summary": {"trials": summary.trials, "outcome_counts": asdict(summary.outcome_counts),
                            "total_attack_count": summary.total_attack_count,
                            "total_visited_round_count": summary.total_visited_round_count,
                            "mean_attack_count": summary.mean_attack_count,
                            "mean_visited_round_count": summary.mean_visited_round_count},
                "rates": {name: _fraction_document(getattr(assessment, name + "_rate"))
                          for name in ("objective_achieved", "side_defeated", "round_limit", "unsupported_path")},
                "status": assessment.status.value, "window_match": assessment.window_match,
            })
        reports.append({
            "stage_index": index, "trials_per_candidate": report.source_request.trials_per_candidate,
            "keep": report.source_request.top_k, "total_trials": report.total_trials, "candidates": candidates,
            "selected_candidate_ids": list(report.selected_candidate_ids),
            "continuation_candidate_ids": (list(melee_continuation_candidate_ids(report))
                                           if index + 1 < len(source.stages) else []),
        })
    document = {
        "schema_version": "1", "kind": "npc_melee_balance_result", "request": request_document,
        "seed_scheme": evaluation.seed_scheme,
        "runtime": {"package_version": __version__, "python_implementation": platform.python_implementation(),
                    "python_version": platform.python_version(), "rng": "random.Random"},
        "candidate_count": source.candidate_count, "planned_trials": evaluation.planned_trials,
        "total_trials": evaluation.total_trials, "candidates": catalog, "stage_reports": reports,
        "status": evaluation.status.value, "selected_candidate_ids": list(evaluation.selected_candidate_ids),
    }
    # asdict preserves tuple fields; normalize them to wire arrays before schema validation.
    encoded = json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    validate_melee_balance_document(json.loads(encoded), "result")
    return encoded
