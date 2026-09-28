"""Finite spawn compatibility probe for ADR-0023, not the future process backend."""

from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from functools import partial
from multiprocessing import active_children, get_context
import os
import pickle
import random

from melee_scenario import build_scenario
from towr.simulation.npc_melee_models import NpcMeleeSimulationRequest, NpcMeleeSimulationResult
from towr.simulation.npc_melee_simulation import run_npc_melee_simulation, run_npc_melee_trial
from towr.simulation.npc_melee_summary import summarize_npc_melee_simulation


def child_rng(seed: int, *, parent_pid: int, fail_seed: int | None = None) -> random.Random:
    if os.getpid() == parent_pid:
        raise AssertionError("trial must execute in a child")
    if seed == fail_seed:
        raise RuntimeError("contract probe child failure")
    return random.Random(seed)


def main() -> None:
    request = NpcMeleeSimulationRequest(build_scenario(), master_seed=20260928, trials=3)
    before = deepcopy(request)
    global_before = random.getstate()
    children_before = {child.pid for child in active_children()}
    expected = run_npc_melee_simulation(request)
    factory = partial(child_rng, parent_pid=os.getpid())
    copied, _ = pickle.loads(pickle.dumps((request, factory)))
    assert copied == request
    for workers in (1, 2):
        with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as pool:
            # Exactly three trials. This probe has no general scheduler or batch queue.
            futures = [pool.submit(run_npc_melee_trial, request, index, rng_factory=factory)
                       for index in (2, 0, 1)]
            records = tuple(future.result() for future in reversed(futures))
        actual = NpcMeleeSimulationResult(request, records)
        assert actual == expected
        assert actual.source_request is request
        assert summarize_npc_melee_simulation(actual) == summarize_npc_melee_simulation(expected)
    failing = partial(child_rng, parent_pid=os.getpid(), fail_seed=request.seed_for(1))
    with ProcessPoolExecutor(max_workers=1, mp_context=get_context("spawn")) as pool:
        future = pool.submit(run_npc_melee_trial, request, 1, rng_factory=failing)
        try:
            future.result()
        except RuntimeError as error:
            assert str(error) == "contract probe child failure"
        else:
            raise AssertionError("child exception must reach parent")
    assert request == before
    assert random.getstate() == global_before
    assert {child.pid for child in active_children()} == children_before
    print("Melee contract: 3 trials; spawn workers 1/2 == sequential; pickle/source/summary OK; child failure/cleanup OK")


if __name__ == "__main__":
    main()
