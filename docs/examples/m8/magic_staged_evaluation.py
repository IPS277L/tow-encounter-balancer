"""Authored magic candidates through two evaluation stages; stdout is not a wire format."""

from copy import deepcopy
from multiprocessing import active_children
import random
import sys

from magic_evaluation import build_request as build_candidates, print_report
from towr.application.magic_staged_evaluation_errors import MagicStagedEvaluationError
from towr.application.magic_staged_evaluation_service import evaluate_magic_candidates_staged
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.balance.magic_staged_evaluation import magic_continuation_candidate_ids
from towr.balance.magic_staged_evaluation_models import MagicBalanceStage, MagicStagedEvaluationRequest


def build_request() -> MagicStagedEvaluationRequest:
    # Two authored priority alternatives; all scene facts/policies stay explicit.
    # PG1.4 Rules/Combat p112, Conditions/Broken p122,
    # Magic/Casting/Potency/Miscasts pp156-157, Battle Magic/Curse p162,
    # Wounds Table pp190-191; GM1.1 Allies and Antagonists pp91-92.
    base = build_candidates()
    return MagicStagedEvaluationRequest(
        candidates=base.candidates, master_seed=base.master_seed,
        stages=(MagicBalanceStage(8, 1), MagicBalanceStage(32, 1)),
        max_total_trials=48, window=base.window,
    )


def main() -> None:
    source = build_request()
    before = deepcopy(source)
    rng_before = random.getstate()
    children_before = {child.pid for child in active_children()}
    sequential = evaluate_magic_candidates_staged(
        source, SimulationExecutionOptions(SimulationExecutionMode.SEQUENTIAL))
    process = evaluate_magic_candidates_staged(
        source, SimulationExecutionOptions(SimulationExecutionMode.PROCESS, workers=2, batch_size=3))
    # Compare full reports without requiring a Monte Carlo percentage or winner.
    assert sequential == process
    assert sequential.selected_candidate_ids == process.selected_candidate_ids
    assert sequential.source_request is source and process.source_request is source
    assert sequential.total_trials <= sequential.planned_trials <= source.max_total_trials
    for result in (sequential, process):
        for report in result.stage_reports:
            for row, expected in zip(report.candidates, report.source_request.simulation_requests):
                assert row.assessment.source_request is row.assessment.summary.source_request is expected
                assert row.assessment.window is source.window
    assert source == before and random.getstate() == rng_before
    assert {child.pid for child in active_children()} == children_before
    # Publish only after both evaluations and their consistency checks succeed.
    print("stages (full trials per candidate, keep): " + str(tuple(
        (stage.trials_per_candidate, stage.keep) for stage in source.stages)))
    print(f"staged budget per evaluation: planned={sequential.planned_trials}; "
          f"actual={sequential.total_trials}; max={source.max_total_trials}")
    for index, report in enumerate(sequential.stage_reports):
        print(f"stage index: {index}")
        print_report(report)
        if index < len(source.stages) - 1:
            print(f"continuation IDs (not local selected): {magic_continuation_candidate_ids(report)}")
    print(f"staged status: {sequential.status.value}; final selected: {sequential.selected_candidate_ids}")
    print("sequential/process full stage reports and selected IDs: equal; process workers=2 batch_size=3")
    print(f"demonstration executes two complete evaluations: {sequential.total_trials + process.total_trials} trials")
    print("each stage reruns its full batch from index 0; repeated prefixes are included in the budget")
    print("input/global RNG unchanged; no remaining child processes")
    print("finite seeded observations only; eligibility is not tactical completeness or a difficulty guarantee")


if __name__ == "__main__":
    try:
        main()
    except MagicStagedEvaluationError as error:
        print(f"stage failed: {error.stage_index}; candidate: {error.candidate_id}; "
              f"cause: {type(error.__cause__).__name__}: {error.__cause__}", file=sys.stderr)
        raise  # Preserve the full cause/notes chain and fail without a partial report.
