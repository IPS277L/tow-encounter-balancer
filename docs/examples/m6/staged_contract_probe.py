"""Finite synthetic examples for ADR-0025, not a staged evaluator or simulator."""

from dataclasses import replace
from fractions import Fraction as F

from melee_scenario import build_scenario
from towr.balance.melee_assessment import assess_melee_candidate
from towr.balance.melee_assessment_models import MeleeAssessmentStatus
from towr.balance.melee_evaluation_models import (
    MeleeBalanceCandidate, MeleeBalanceCandidateResult, MeleeBalanceEvaluationRequest,
    MeleeBalanceEvaluationResult,
)
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.simulation.npc_melee_models import NpcMeleeOutcomeCounts
from towr.simulation.npc_melee_summary_models import NpcMeleeSimulationSummary


def main() -> None:
    scenario = build_scenario()
    candidates = tuple(MeleeBalanceCandidate(name, scenario) for name in ("A", "B", "C", "D"))
    window = ObjectiveRateWindow(F(9, 20), F(1, 2), F(11, 20))
    first_input = MeleeBalanceEvaluationRequest(candidates, 42, 10, 40, window, 2)

    def report(source, goals, unsupported):
        rows = []
        for candidate, simulation, goal, unknown in zip(
                source.candidates, source.simulation_requests, goals, unsupported, strict=True):
            n = simulation.trials
            # Structurally valid synthetic aggregates, not observed battles.
            summary = NpcMeleeSimulationSummary(
                simulation, NpcMeleeOutcomeCounts(goal, 0, n - goal - unknown, unknown),
                goal, n * scenario.initial.max_rounds,
            )
            rows.append(MeleeBalanceCandidateResult(
                candidate.candidate_id, assess_melee_candidate(simulation, summary, source.window)))
        return MeleeBalanceEvaluationResult(source, tuple(rows))

    def illustrative_continuation(observation):
        # Finite arithmetic only: production helper/type guards belong to the next slice.
        eligible = (row for row in observation.candidates
                    if row.assessment.status is MeleeAssessmentStatus.ELIGIBLE)
        ranked = sorted(eligible, key=lambda row: abs(
            row.assessment.objective_achieved_rate - observation.source_request.window.target))
        kept = {row.candidate_id for row in ranked[:observation.source_request.top_k]}
        return tuple(row.candidate_id for row in observation.candidates if row.candidate_id in kept)

    first = report(first_input, (4, 7, 5, 6), (0, 0, 1, 0))
    assert first.selected_candidate_ids == ()
    assert illustrative_continuation(first) == ("A", "D")
    last_input = MeleeBalanceEvaluationRequest((candidates[0], candidates[3]), 42, 100, 200, window, 1)
    final = report(last_input, (49, 51), (0, 0))
    assert final.selected_candidate_ids == ("A",)
    assert report(last_input, (45, 55), (0, 0)).selected_candidate_ids == ("A",)
    assert report(last_input, (40, 60), (0, 0)).selected_candidate_ids == ()
    assert first.total_trials + final.total_trials == 240
    assert 4 * 10 + min(4, 2) * 100 == 240 > 239
    assert 4 * 10 + min(4, 2) * (100 - 10) == 220  # Excluded incremental budget.
    assert 4 * 10 + 2 * 100 + min(2, 5) * 1000 == 2240
    assert illustrative_continuation(report(first_input, (4, 7, 5, 5), (0, 0, 1, 0))) == ("A", "D")
    assert illustrative_continuation(report(first_input, (4, 7, 5, 6), (0, 1, 1, 1))) == ("A",)
    single = replace(last_input, candidates=(candidates[0],), max_total_trials=100)
    assert first.total_trials + report(single, (49,), (0,)).total_trials == 140
    exhausted = report(first_input, (4, 7, 5, 6), (1, 1, 1, 1))
    assert illustrative_continuation(exhausted) == () and exhausted.total_trials == 40
    final_unsupported = report(last_input, (49, 51), (1, 1))
    assert illustrative_continuation(final_unsupported) == final_unsupported.selected_candidate_ids == ()
    all_limit = report(first_input, (0, 0, 0, 0), (0, 0, 0, 0))
    assert illustrative_continuation(all_limit) == ("A", "B")
    assert report(replace(first_input, top_k=10), (4, 7, 5, 6), (0, 0, 0, 0)).selected_candidate_ids == ("C",)
    n = 2**60 + 1
    large = replace(last_input, trials_per_candidate=n, max_total_trials=2*n)
    precise = report(large, (n//2-1, n//2), (0, 0))
    assert float(precise.candidates[0].assessment.objective_achieved_rate) == float(
        precise.candidates[1].assessment.objective_achieved_rate)
    assert illustrative_continuation(precise) == ("D",)
    assert first_input.simulation_requests[0].seed_for(0) == last_input.simulation_requests[0].seed_for(0)
    print("Melee staged contract: synthetic continuation/order/ties, windows, budgets 240/140/40/2240 OK")
    print("No staged models/service, battle execution, RNG, or chain/error guards are implemented by this probe")


if __name__ == "__main__":
    main()
