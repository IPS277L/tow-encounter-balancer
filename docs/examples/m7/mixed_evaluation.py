"""Two authored mixed candidates through public APIs; no generation or wire format."""

from copy import deepcopy
from fractions import Fraction
from multiprocessing import active_children
import random
import sys

from mixed_scenario import build_scenario
from towr.application.mixed_evaluation_errors import MixedBalanceEvaluationError
from towr.application.mixed_evaluation_service import evaluate_mixed_candidates
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.balance.mixed_evaluation_models import (
    MixedBalanceCandidate, MixedBalanceEvaluationRequest, MixedBalanceEvaluationResult,
)
from towr.balance.ranged_assessment_models import ObjectiveRateWindow


def build_request() -> MixedBalanceEvaluationRequest:
    return MixedBalanceEvaluationRequest(
        candidates=(MixedBalanceCandidate("one-bow:3x2", build_scenario()),
                    MixedBalanceCandidate("two-bows:2x2", build_scenario(two_archers=True))),
        master_seed=42, trials_per_candidate=8, max_total_trials=16,
        window=ObjectiveRateWindow(Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)), top_k=1,
    )


def print_report(report: MixedBalanceEvaluationResult) -> None:
    source = report.source_request
    print("profiles: Footpad Dagger / Brigand Warbow; BOOK-GM-GUIDE 1.1 / Allies and Antagonists pp91,93,97")
    print("rules: BOOK-PLAYER-GUIDE 1.4 / Equipment p94; Rules pp112,114,118-119,123")
    print("facts/policies: stationary aware Minions, explicit Close/Medium, fixed weapons and target order; "
          "outnumbering approved; repeated Staggered -> Wound; defeat -> knocked out")
    print("no movement/weapon switching; no available target -> unsupported_path, not defeat")
    print(f"seed: {source.master_seed}; seed_scheme: {report.seed_scheme}; trials_per_candidate: {source.trials_per_candidate}")
    print(f"window: min={source.window.minimum}, target={source.window.target}, max={source.window.maximum}; top_k: {source.top_k}")
    print(f"budget per evaluation: planned={source.planned_trials}; actual={report.total_trials}; max={source.max_total_trials}")
    for row in report.candidates:
        assessment = row.assessment
        scenario = assessment.source_request.scenario
        counts = assessment.summary.outcome_counts
        print(f"candidate: {row.candidate_id}; round_budget: {scenario.initial.max_rounds}; "
              f"perspective: {scenario.perspective_side.value}; objective: {','.join(scenario.objective.target_actor_ids)}")
        print(f"  counts goal/defeated/limit/unsupported: {counts.objective_achieved}/"
              f"{counts.side_defeated}/{counts.round_limit}/{counts.unsupported_path}")
        print(f"  rates goal/defeated/limit/unsupported: {assessment.objective_achieved_rate}, "
              f"{assessment.side_defeated_rate}, {assessment.round_limit_rate}, {assessment.unsupported_path_rate}")
        print(f"  attacks: {assessment.summary.total_attack_count}; visited_rounds: "
              f"{assessment.summary.total_visited_round_count}; status: {assessment.status.value}; "
              f"window_match: {assessment.window_match}")
    print(f"selected: {report.selected_candidate_ids}")


def main() -> None:
    source = build_request()
    before = deepcopy(source)
    rng_before = random.getstate()
    children_before = {child.pid for child in active_children()}
    sequential = evaluate_mixed_candidates(source, SimulationExecutionOptions(SimulationExecutionMode.SEQUENTIAL))
    process = evaluate_mixed_candidates(
        source, SimulationExecutionOptions(SimulationExecutionMode.PROCESS, workers=2, batch_size=3))
    # Full report equality, with no hard-coded Monte Carlo percentage or winner.
    assert sequential == process
    assert sequential.selected_candidate_ids == process.selected_candidate_ids
    assert sequential.source_request is source and process.source_request is source
    assert sequential.total_trials == process.total_trials == source.planned_trials
    assert source == before and random.getstate() == rng_before
    assert {child.pid for child in active_children()} == children_before
    # Publish only after both complete evaluations and all consistency checks.
    print_report(sequential)
    print("sequential/process reports and selected IDs: equal; process workers=2 batch_size=3")
    print(f"demonstration runs two complete evaluations: {2 * source.planned_trials} total trials")
    print("input/global RNG unchanged; no remaining child processes")


if __name__ == "__main__":
    try:
        main()
    except MixedBalanceEvaluationError as error:
        print(f"candidate failed: {error.candidate_id}; cause: {type(error.__cause__).__name__}: {error.__cause__}",
              file=sys.stderr)
        raise  # Preserve cause/notes and fail without a partial stdout report.
