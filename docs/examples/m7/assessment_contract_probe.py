"""Finite arithmetic examples prepared for ADR-0031; not an assessor."""

from copy import deepcopy
from dataclasses import replace
from functools import partial
from multiprocessing import active_children
import pickle
from random import getstate
from fractions import Fraction as F

from mixed_scenario import ScriptedDice, build_scenario
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.simulation.npc_mixed_simulation import run_npc_mixed_simulation
from towr.simulation.npc_mixed_parallel import run_npc_mixed_simulation_parallel
from towr.simulation.npc_mixed_summary import summarize_npc_mixed_simulation as summarize
from towr.simulation.npc_mixed_models import NpcMixedOutcomeCounts, NpcMixedSimulationRequest
from towr.simulation.npc_mixed_summary_models import NpcMixedSimulationSummary


def exact_rng(seed: int, *, seeds: tuple[int, ...]) -> ScriptedDice:
    wound, miss = (1, 2, 10, 10, 10, 10), (10,) * 6
    scripts = (miss + wound + miss + wound, miss * 2 + wound * 2, miss * 8, wound)
    return ScriptedDice(scripts[seeds.index(seed)])


def main() -> None:
    original_rng = getstate()
    original_children = {child.pid for child in active_children()}
    scenario = build_scenario(two_archers=True)
    source = NpcMixedSimulationRequest(scenario, master_seed=42, trials=4)
    window = ObjectiveRateWindow(F(1, 4), F(1, 2), F(3, 4))

    def observation(counts: NpcMixedOutcomeCounts) -> NpcMixedSimulationSummary:
        n = counts.objective_achieved + counts.side_defeated + counts.round_limit + counts.unsupported_path
        terminal = counts.objective_achieved + counts.side_defeated
        rounds = counts.round_limit * scenario.initial.max_rounds + n - counts.round_limit
        return NpcMixedSimulationSummary(replace(source, trials=n), counts, terminal, rounds)

    # Deliberately synthetic, structurally valid counts, not simulated victories.
    summaries = tuple(observation(NpcMixedOutcomeCounts(*counts)) for counts in (
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

    four = observation(NpcMixedOutcomeCounts(1, 1, 1, 1))
    assert tuple(F(count, four.trials) for count in (1, 1, 1, 1)) == (F(1, 4),) * 4
    assert four.total_visited_round_count == scenario.initial.max_rounds + 3
    all_limit = observation(NpcMixedOutcomeCounts(0, 0, 4, 0))
    point_zero = ObjectiveRateWindow(F(0), F(0), F(0))
    assert not all_limit.outcome_counts.unsupported_path
    assert point_zero.minimum <= F(all_limit.outcome_counts.objective_achieved, all_limit.trials) <= point_zero.maximum
    all_unsupported = observation(NpcMixedOutcomeCounts(0, 0, 0, 4))
    assert F(all_unsupported.outcome_counts.unsupported_path, all_unsupported.trials) == 1
    unsupported_match = (None if all_unsupported.outcome_counts.unsupported_path else
                         point_zero.minimum <= F(0) <= point_zero.maximum)
    assert unsupported_match is None

    n = 2**60 + 1
    large = observation(NpcMixedOutcomeCounts(n // 2, n - n // 2, 0, 0))
    exact = F(large.outcome_counts.objective_achieved, large.trials)
    assert exact < F(1, 2) and float(exact) == 0.5
    assert replace(source, master_seed=43) != summaries[0].source_request
    # Shared classes remain at their existing import/pickle paths.
    assert type(pickle.loads(pickle.dumps(window))) is ObjectiveRateWindow
    sequential_options = SimulationExecutionOptions(SimulationExecutionMode.SEQUENTIAL)
    process_options = SimulationExecutionOptions(SimulationExecutionMode.PROCESS, workers=2, batch_size=3)
    assert pickle.loads(pickle.dumps(process_options)) == process_options
    assert sequential_options.workers is None and sequential_options.batch_size is None
    print("Synthetic arithmetic only: shares=1/4,3/4,1/2,1,1/2; matches=True,True,True,False,None")
    print("Synthetic selection: C,A; reordered ties: C,B; planned=20 fits cap=20, exceeds cap=19")
    print("Point window zero/all-limit/all-unsupported and large exact Fraction: OK")
    print("Existing ObjectiveRateWindow and SimulationExecutionOptions/pickle paths: OK")

    before = deepcopy(source)
    factory = partial(exact_rng, seeds=tuple(source.seed_for(i) for i in range(4)))
    sequential = run_npc_mixed_simulation(source, rng_factory=factory)
    process = run_npc_mixed_simulation_parallel(source, workers=process_options.workers,
        batch_size=process_options.batch_size, rng_factory=factory)
    assert sequential == process
    actual = summarize(sequential)
    assert actual == summarize(process)
    assert sequential.source_request is process.source_request is actual.source_request is source
    assert actual.outcome_counts == NpcMixedOutcomeCounts(1, 1, 1, 1)
    assert (actual.total_attack_count, actual.total_visited_round_count) == (17, 6)
    counts = actual.outcome_counts
    shares = tuple(F(count, actual.trials) for count in (
        counts.objective_achieved, counts.side_defeated, counts.round_limit, counts.unsupported_path))
    assert shares == (F(1, 4),) * 4
    # This rate lies on the lower boundary, yet unsupported prevents selection.
    assert window.minimum <= shares[0] <= window.maximum
    actual_match = None if counts.unsupported_path else window.minimum <= shares[0] <= window.maximum
    assert actual_match is None
    assert source == before and getstate() == original_rng
    assert {child.pid for child in active_children()} == original_children
    print("Real scripted sequential/spawn: full results/summaries equal; outcomes=1/1/1/1; attacks=17; visited=6")
    print("Real goal share=1/4 of ALL trials; unsupported=1/4 -> proposed window_match=None")
    print("8 real trials total; source/global RNG unchanged; children closed")
    print("Mixed assessment/list/service APIs and their guards are NOT implemented by this probe")


if __name__ == "__main__":
    main()
