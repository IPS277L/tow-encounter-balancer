"""Finite arithmetic examples prepared for ADR-0024; not an assessor."""

from dataclasses import replace
from fractions import Fraction as F

from melee_scenario import build_scenario
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.simulation.npc_melee_models import NpcMeleeOutcomeCounts, NpcMeleeSimulationRequest
from towr.simulation.npc_melee_summary_models import NpcMeleeSimulationSummary


def main() -> None:
    scenario = build_scenario()
    source = NpcMeleeSimulationRequest(scenario, master_seed=42, trials=4)
    window = ObjectiveRateWindow(F(1, 4), F(1, 2), F(3, 4))

    def observation(counts: NpcMeleeOutcomeCounts) -> NpcMeleeSimulationSummary:
        n = counts.objective_achieved + counts.side_defeated + counts.round_limit + counts.unsupported_path
        terminal = counts.objective_achieved + counts.side_defeated
        rounds = counts.round_limit * scenario.initial.max_rounds + n - counts.round_limit
        return NpcMeleeSimulationSummary(replace(source, trials=n), counts, terminal, rounds)

    # Deliberately synthetic, structurally valid counts, not simulated victories.
    summaries = tuple(observation(NpcMeleeOutcomeCounts(*counts)) for counts in (
        (1, 3, 0, 0), (3, 1, 0, 0), (2, 2, 0, 0), (4, 0, 0, 0), (2, 1, 0, 1)))
    rates = tuple(F(item.outcome_counts.objective_achieved, item.trials) for item in summaries)
    matches = tuple(None if item.outcome_counts.unsupported_path else window.minimum <= rate <= window.maximum
                    for item, rate in zip(summaries, rates))
    assert rates == (F(1, 4), F(3, 4), F(1, 2), F(1), F(1, 2))
    assert matches == (True, True, True, False, None)
    assert all(item.source_request == source for item in summaries)
    planned = sum(item.trials for item in summaries)
    assert planned == 20 and planned <= 20 and not planned <= 19
    for order, expected in (((0, 1, 2, 3, 4), (2, 0)), ((1, 0, 2, 3, 4), (2, 1))):
        selected = sorted((i for i in order if matches[i] is True), key=lambda i: abs(rates[i] - window.target))[:2]
        assert tuple(selected) == expected

    four = observation(NpcMeleeOutcomeCounts(1, 1, 1, 1))
    assert tuple(F(count, four.trials) for count in (1, 1, 1, 1)) == (F(1, 4),) * 4
    assert four.total_visited_round_count == scenario.initial.max_rounds + 3
    all_limit = observation(NpcMeleeOutcomeCounts(0, 0, 4, 0))
    point_zero = ObjectiveRateWindow(F(0), F(0), F(0))
    assert not all_limit.outcome_counts.unsupported_path
    assert point_zero.minimum <= F(all_limit.outcome_counts.objective_achieved, all_limit.trials) <= point_zero.maximum
    all_unsupported = observation(NpcMeleeOutcomeCounts(0, 0, 0, 4))
    assert F(all_unsupported.outcome_counts.unsupported_path, all_unsupported.trials) == 1
    unsupported_match = (None if all_unsupported.outcome_counts.unsupported_path else
                         point_zero.minimum <= F(0) <= point_zero.maximum)
    assert unsupported_match is None

    n = 2**60 + 1
    large = observation(NpcMeleeOutcomeCounts(n // 2, n - n // 2, 0, 0))
    exact = F(large.outcome_counts.objective_achieved, large.trials)
    assert exact < F(1, 2) and float(exact) == 0.5
    assert replace(source, master_seed=43) != summaries[0].source_request
    print("Melee assessment contract: exact shares/windows, unsupported, stable ties, budget 20 OK")


if __name__ == "__main__":
    main()
