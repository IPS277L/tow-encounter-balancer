"""Finite ADR-0030 transport probe; not the proposed process simulation backend.

Explicit tiny partitions only: no lazy scheduling/refill/cancellation API here.
Run as an importable script with PYTHONPATH=src, including from another cwd.
"""
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from dataclasses import fields
from functools import partial
from multiprocessing import active_children, get_context
import os
import pickle
from random import Random, getstate

from mixed_scenario import ScriptedDice, build_scenario
from towr.simulation.npc_mixed_models import (
    SEED_SCHEME, NpcMixedOutcomeCounts, NpcMixedSimulationRequest,
    NpcMixedSimulationResult, NpcMixedTrialSummary,
)
from towr.simulation.npc_mixed_simulation import run_npc_mixed_simulation, run_npc_mixed_trial
from towr.simulation.npc_mixed_summary import summarize_npc_mixed_simulation as summarize


def child_rng(seed, *, parent_pid):
    assert os.getpid() != parent_pid, "trial must run in child even with workers=1"
    return Random(seed)


def exact_rng(seed, *, seeds):
    wound, miss = (1, 2, 10, 10, 10, 10), (10,) * 6
    # Same 2x2/B=2 request; actual runner paths, no controller substitution.
    scripts = (miss + wound + miss + wound, miss * 2 + wound * 2, miss * 8, wound)
    return ScriptedDice(scripts[seeds.index(seed)])


def failing_rng(seed, *, fail_seed):
    if seed == fail_seed:
        raise ValueError("probe child factory failure")
    return Random(seed)


def probe_batch(request, indices, factory):
    before, global_rng = deepcopy(request), getstate()
    records = []
    for index in indices:
        try:
            records.append(run_npc_mixed_trial(request, index, rng_factory=factory))
        except Exception as error:
            error.add_note(f"M7 trial index={index}, seed={request.seed_for(index)}")
            raise
    assert request == before and getstate() == global_rng
    assert all(isinstance(record, NpcMixedTrialSummary) for record in records)
    # PID is diagnostic probe metadata, not part of the proposed batch result.
    return os.getpid(), tuple(records)


def collect_fixed_batches(request, partitions, workers, factory):
    """Illustrate trusted pickle transport for a fixed finite plan, not a scheduler."""
    assert len(partitions) <= 2 * workers
    pickle.dumps((request, factory))
    before = {child.pid for child in active_children()}
    records = []
    with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as pool:
        futures = tuple(pool.submit(probe_batch, request, indices, factory) for indices in partitions)
        # Deliberately collect opposite to submission, regardless of finish order.
        for future in reversed(futures):
            pid, batch = future.result()
            assert pid != os.getpid()
            records.extend(batch)
    assert {child.pid for child in active_children()} == before
    return NpcMixedSimulationResult(request, tuple(records))


def main():
    original_rng = getstate()
    original_children = {child.pid for child in active_children()}
    print(f"ADR-0030 finite mixed process contract probe; seed_scheme={SEED_SCHEME}")
    print("Existing mixed trial/result/summary; explicit spawn; this is not the production parallel API")
    plans = ((1, (range(0, 3), range(3, 5))),
             (2, (range(0, 2), range(2, 4), range(4, 5))),
             (2, (range(0, 5),)))
    for two_archers in (False, True):
        request = NpcMixedSimulationRequest(build_scenario(two_archers=two_archers), 42, 5)
        before = deepcopy(request)
        assert pickle.loads(pickle.dumps(request)) == request
        expected = run_npc_mixed_simulation(request)
        for workers, partitions in plans:
            result = collect_fixed_batches(request, partitions, workers,
                partial(child_rng, parent_pid=os.getpid()))
            assert result == expected and summarize(result) == summarize(expected)
            assert result.source_request is request and summarize(result).source_request is request
            assert tuple(t.trial_index for t in result.trials) == tuple(range(5))
            assert request == before
            print(f"seeded {'2x2' if two_archers else '3x2'}: workers={workers}; "
                  f"batch_lengths={tuple(len(p) for p in partitions)}; full result/summary equal")
    request = NpcMixedSimulationRequest(build_scenario(two_archers=True), 42, 4)
    factory = partial(exact_rng, seeds=tuple(request.seed_for(i) for i in range(4)))
    expected = run_npc_mixed_simulation(request, rng_factory=factory)
    actual = collect_fixed_batches(request, (range(0, 3), range(3, 4)), 2, factory)
    assert actual == expected and summarize(actual) == summarize(expected)
    assert actual.outcome_counts == NpcMixedOutcomeCounts(1, 1, 1, 1)
    assert (actual.total_attack_count, actual.total_visited_round_count) == (17, 6)
    assert {f.name for f in fields(actual.trials[0])} == {
        "trial_index", "seed", "outcome", "executed_attack_count", "visited_round_count"}
    print("scripted 2x2: achieved/defeated/limit/unsupported=1/1/1/1; attacks=17; visited=6")
    print("Real no-Close-target stop retained; denominator=4; no extra Attack/round for terminal suffix")
    try:
        pickle.dumps((request, lambda seed: Random(seed)))
    except (AttributeError, TypeError, pickle.PicklingError):
        print("Local lambda rejected by parent pickle; no pool created for this check")
    else:
        raise AssertionError("local lambda unexpectedly serialized")
    failure_source = deepcopy(request)
    try:
        collect_fixed_batches(request, (range(0, 3),), 1,
                              partial(failing_rng, fail_seed=request.seed_for(1)))
    except ValueError as error:
        assert str(error) == "probe child factory failure"
        assert f"M7 trial index=1, seed={request.seed_for(1)}" in error.__notes__
        print("Child factory error at index=1 keeps type/message/seed note; no partial result")
    else:
        raise AssertionError("child failure did not propagate")
    assert request == failure_source
    assert getstate() == original_rng
    assert {child.pid for child in active_children()} == original_children
    print("49 completed trials + one failed factory call; inputs/global RNG unchanged; children closed")
    print("Not verified here: public preflight, lazy refill/bounded scheduling, cancel/submission/wait failures")
    print("No throughput claim, process API, auto backend, balance, JSON/CLI or new game rules")


if __name__ == "__main__":
    main()
