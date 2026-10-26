"""Public ADR-0039 example; keep magic_simulation.py/magic_scenario.py beside it.

Authored numeric inputs retain the single-run scope. This is finite correctness
evidence, not a process throughput measurement or a difficulty estimate.
"""
from copy import deepcopy
from dataclasses import dataclass, replace
from functools import partial
from multiprocessing import active_children
import os
from random import Random, getstate

from magic_scenario import ScriptedDice
from magic_simulation import authored_simulation_scenario
from towr.simulation.npc_magic_models import NpcMagicOutcomeCounts, NpcMagicSimulationRequest
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation as summarize


def child_rng(seed, *, parent_pid):
    if os.getpid() == parent_pid:
        raise AssertionError('trial must execute in a spawned child, even with workers=1')
    return Random(seed)


@dataclass(frozen=True, slots=True)
class ScriptFactory:
    seeds: tuple[int, ...]
    scripts: tuple[tuple[int, ...], ...]

    def __call__(self, seed):
        return ScriptedDice(self.scripts[self.seeds.index(seed)])


def check_equal(request, actual, expected):
    assert actual == expected and summarize(actual) == summarize(expected)
    assert actual.source_request is request and summarize(actual).source_request is request
    assert all(record.source_scenario is request.scenario for record in actual.trials)


def main() -> None:
    source = authored_simulation_scenario()
    before, global_rng = deepcopy(source), getstate()
    children = {child.pid for child in active_children()}
    request = NpcMagicSimulationRequest(source, 42, 5)
    expected = run_npc_magic_simulation(request)
    print('ADR-0039 public magic process API; explicit spawn; unchanged indexed seeds and single-run scope')
    for workers, batch_size in ((1, 2), (2, 2), (2, 32)):
        actual = run_npc_magic_simulation_parallel(request, workers=workers, batch_size=batch_size,
            rng_factory=partial(child_rng, parent_pid=os.getpid()))
        check_equal(request, actual, expected)
        print(f'seeded N=5: workers={workers}; batch_size={batch_size}; full result/summary equal; parent input shared')

    scripted = replace(request, trials=4)
    wait, miss, hit = (10,) * 3, (10,) * 6, (1, 2, 3, 10, 10, 10)
    scripts = (wait + hit,
        wait + miss + hit + wait + hit + (1,) + wait + hit + (1, 1) + wait + hit + (10, 10, 5),
        (10,) * 60, (9, 9, 9))
    factory = ScriptFactory(tuple(scripted.seed_for(i) for i in range(4)), scripts)
    expected = run_npc_magic_simulation(scripted, rng_factory=factory)
    for workers in (1, 2):
        actual = run_npc_magic_simulation_parallel(scripted, workers=workers, batch_size=3, rng_factory=factory)
        check_equal(scripted, actual, expected)
        assert actual.outcome_counts == NpcMagicOutcomeCounts(1, 1, 1, 1)
        assert (actual.total_action_count, actual.total_started_round_count,
                actual.total_completed_round_count) == (24, 10, 9)
        print(f'scripted N=4: workers={workers}; outcomes=1/1/1/1; actions=24; started=10; completed=9; 120 d10')

    zero_source = replace(source, activation_order=('ally', 'wizard', 'enemy'),
        scene_frames=(replace(source.initial_frame, attack_departures=()),))
    zero_request = NpcMagicSimulationRequest(zero_source, 42, 1)
    zero_factory = ScriptFactory((zero_request.seed_for(0),), ((),))
    actual = run_npc_magic_simulation_parallel(zero_request, workers=1, rng_factory=zero_factory)
    check_equal(zero_request, actual, run_npc_magic_simulation(zero_request, rng_factory=zero_factory))
    assert actual.outcome_counts == NpcMagicOutcomeCounts(0, 0, 0, 1)
    assert (actual.total_action_count, actual.total_started_round_count,
            actual.total_completed_round_count) == (0, 1, 0)
    print('zero-action stop: unsupported retained; rounds=1/0; 0 draws')
    assert source == before and getstate() == global_rng
    assert {child.pid for child in active_children()} == children
    print('24 spawned trials in six public API calls; inputs/global RNG preserved; child processes closed')
    print('No throughput claim, automatic backend selection, balance metric, JSON/CLI or new game rules')


if __name__ == '__main__':
    main()
