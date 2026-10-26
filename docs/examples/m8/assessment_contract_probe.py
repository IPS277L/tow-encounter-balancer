"""Finite ADR-0040 arithmetic and existing simulation evidence, not an assessor.

Keep magic_simulation.py and magic_scenario.py beside this file. Synthetic
summaries are illustrative inputs; real trials below use supplied scripted dice.
"""
from copy import deepcopy
from dataclasses import dataclass, replace
from fractions import Fraction as F
from multiprocessing import active_children
import pickle
from random import getstate

from magic_scenario import ScriptedDice
from magic_simulation import authored_simulation_scenario
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.simulation.npc_magic_models import NpcMagicOutcomeCounts, NpcMagicSimulationRequest
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation as summarize
from towr.simulation.npc_magic_summary_models import NpcMagicSimulationSummary


@dataclass(frozen=True, slots=True)
class ScriptFactory:
    seeds: tuple[int, ...]
    scripts: tuple[tuple[int, ...], ...]

    def __call__(self, seed: int) -> ScriptedDice:
        return ScriptedDice(self.scripts[self.seeds.index(seed)])


def main() -> None:
    original_rng = getstate()
    original_children = {child.pid for child in active_children()}
    scenario = authored_simulation_scenario()
    source = NpcMagicSimulationRequest(scenario, master_seed=42, trials=4)
    before = deepcopy(source)
    window = ObjectiveRateWindow(F(1, 4), F(1, 2), F(3, 4))

    def observation(counts: NpcMagicOutcomeCounts) -> NpcMagicSimulationSummary:
        n = counts.objective_achieved + counts.perspective_defeated + counts.round_limit_reached + counts.unsupported_path
        terminal = counts.objective_achieved + counts.perspective_defeated
        completed = counts.round_limit_reached * scenario.max_rounds
        started = completed + n - counts.round_limit_reached
        return NpcMagicSimulationSummary(replace(source, trials=n), counts, terminal + completed, started, completed)

    # Structurally valid synthetic observations, not simulated victories.
    summaries = tuple(observation(NpcMagicOutcomeCounts(*counts)) for counts in (
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
    print('Synthetic arithmetic only: shares=1/4,3/4,1/2,1,1/2; matches=True,True,True,False,None')
    print('Synthetic selection: C,A; reordered ties: C,B; planned=20 fits cap=20, exceeds cap=19')

    four = observation(NpcMagicOutcomeCounts(1, 1, 1, 1))
    assert tuple(F(count, four.trials) for count in (1, 1, 1, 1)) == (F(1, 4),) * 4
    assert (four.total_action_count, four.total_started_round_count, four.total_completed_round_count) == (6, 7, 4)
    all_limit = observation(NpcMagicOutcomeCounts(0, 0, 4, 0))
    point_zero = ObjectiveRateWindow(F(0), F(0), F(0))
    assert not all_limit.outcome_counts.unsupported_path
    assert point_zero.minimum <= F(all_limit.outcome_counts.objective_achieved, all_limit.trials) <= point_zero.maximum
    all_unsupported = observation(NpcMagicOutcomeCounts(0, 0, 0, 4))
    assert F(all_unsupported.outcome_counts.unsupported_path, all_unsupported.trials) == 1
    unsupported_match = (None if all_unsupported.outcome_counts.unsupported_path else
                         point_zero.minimum <= F(0) <= point_zero.maximum)
    assert unsupported_match is None
    n = 2**60 + 1
    large = observation(NpcMagicOutcomeCounts(n // 2, n - n // 2, 0, 0))
    exact = F(large.outcome_counts.objective_achieved, large.trials)
    assert exact < F(1, 2) and float(exact) == 0.5
    assert replace(source, master_seed=43) != summaries[0].source_request
    print('Point window zero/all-limit/all-unsupported and large exact Fraction: OK')

    # Shared types keep their existing identities and import/pickle paths.
    assert type(pickle.loads(pickle.dumps(window))) is ObjectiveRateWindow
    sequential_options = SimulationExecutionOptions(SimulationExecutionMode.SEQUENTIAL)
    process_options = SimulationExecutionOptions(SimulationExecutionMode.PROCESS, workers=2, batch_size=3)
    assert sequential_options.workers is None and sequential_options.batch_size is None
    assert type(pickle.loads(pickle.dumps(process_options))) is SimulationExecutionOptions
    assert pickle.loads(pickle.dumps(process_options)) == process_options
    print('Existing ObjectiveRateWindow and SimulationExecutionOptions/pickle paths: OK')

    wait, miss, hit = (10,) * 3, (10,) * 6, (1, 2, 3, 10, 10, 10)
    scripts = (wait + hit,
        wait + miss + hit + wait + hit + (1,) + wait + hit + (1, 1) + wait + hit + (10, 10, 5),
        (10,) * 60, (9, 9, 9))
    factory = ScriptFactory(tuple(source.seed_for(i) for i in range(4)), scripts)
    sequential = run_npc_magic_simulation(source, rng_factory=factory)
    process = run_npc_magic_simulation_parallel(source, workers=process_options.workers,
        batch_size=process_options.batch_size, rng_factory=factory)
    assert sequential == process
    actual = summarize(sequential)
    assert actual == summarize(process)
    assert sequential.source_request is process.source_request is actual.source_request is summarize(process).source_request is source
    assert all(record.source_scenario is scenario for result in (sequential, process) for record in result.trials)
    assert actual.outcome_counts == NpcMagicOutcomeCounts(1, 1, 1, 1)
    assert (actual.total_action_count, actual.total_started_round_count, actual.total_completed_round_count) == (24, 10, 9)
    counts = actual.outcome_counts
    shares = tuple(F(count, actual.trials) for count in (
        counts.objective_achieved, counts.perspective_defeated, counts.round_limit_reached, counts.unsupported_path))
    assert shares == (F(1, 4),) * 4
    assert window.minimum <= shares[0] <= window.maximum
    actual_match = None if counts.unsupported_path else window.minimum <= shares[0] <= window.maximum
    assert actual_match is None
    print('Real N=4 sequential/spawn: full results/summaries equal; outcomes=1/1/1/1; actions=24; started=10; completed=9')
    print('Real goal share=1/4 of ALL trials; unsupported=1/4 -> proposed window_match=None')

    # A separately executed complete N=3 request, never filtering the N=4 result.
    supported_source = replace(source, trials=3)
    supported_factory = ScriptFactory(tuple(supported_source.seed_for(i) for i in range(3)), scripts[:3])
    supported_sequential = run_npc_magic_simulation(supported_source, rng_factory=supported_factory)
    supported_process = run_npc_magic_simulation_parallel(supported_source, workers=process_options.workers,
        batch_size=process_options.batch_size, rng_factory=supported_factory)
    assert supported_sequential == supported_process
    assert supported_sequential.trials == sequential.trials[:3]
    assert supported_sequential.source_request is supported_process.source_request is supported_source
    assert all(record.source_scenario is scenario
               for result in (supported_sequential, supported_process) for record in result.trials)
    supported = summarize(supported_sequential)
    assert supported == summarize(supported_process) and supported.source_request is supported_source
    assert summarize(supported_process).source_request is supported_source
    assert supported.outcome_counts == NpcMagicOutcomeCounts(1, 1, 1, 0)
    assert (supported.total_action_count, supported.total_started_round_count,
            supported.total_completed_round_count) == (23, 9, 9)
    supported_rate = F(supported.outcome_counts.objective_achieved, supported.trials)
    supported_match = (None if supported.outcome_counts.unsupported_path else
                       window.minimum <= supported_rate <= window.maximum)
    assert supported_rate == F(1, 3) and supported_match is True
    print('Independent complete N=3 sequential/spawn: outcomes=1/1/1/0; actions=23; started=9; completed=9')
    print('Independent N=3 goal share=1/3 -> proposed window_match=True; N=4 observations were not filtered')
    assert source == before and supported_source == replace(before, trials=3) and getstate() == original_rng
    assert {child.pid for child in active_children()} == original_children
    print('14 real trials in four calls; original parent inputs/global RNG preserved; child processes closed')
    print('Magic assessment/list/service APIs and their guards are NOT implemented by this probe')


if __name__ == '__main__':
    main()
