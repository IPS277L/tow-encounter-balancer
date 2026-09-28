from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from multiprocessing import get_context
import pickle
from random import Random

from towr.rules.dice import RandomSource
from towr.simulation.npc_melee_models import (
    NpcMeleeSimulationRequest, NpcMeleeSimulationResult, NpcMeleeTrialSummary,
)
from towr.simulation.npc_melee_simulation import run_npc_melee_trial


def _run_batch(
    request: NpcMeleeSimulationRequest, indices: range, rng_factory: Callable[[int], RandomSource],
) -> tuple[NpcMeleeTrialSummary, ...]:
    records = []
    for index in indices:
        try:
            records.append(run_npc_melee_trial(request, index, rng_factory=rng_factory))
        except Exception as error:
            error.add_note(f"M6 trial index={index}, seed={request.seed_for(index)}")
            raise
    return tuple(records)


def run_npc_melee_simulation_parallel(
    request: NpcMeleeSimulationRequest, *, workers: int, batch_size: int = 32,
    rng_factory: Callable[[int], RandomSource] = Random,
) -> NpcMeleeSimulationResult:
    """Run indexed trials in a fresh spawn pool; return the sequential result contract.

    The caller needs an importable main module and an ``if __name__ == '__main__'``
    entry-point guard. Custom RNG factories must be importable/picklable and create
    a fresh RNG from each supplied seed, independent of worker or invocation order.
    At most 2 * workers batches are in flight. Shutdown waits for running work;
    pending work is cancelled on failure, which never yields a partial result.
    """
    if not isinstance(request, NpcMeleeSimulationRequest):
        raise TypeError("parallel simulation requires a typed request")
    for name, value in (("workers", workers), ("batch_size", batch_size)):
        if type(value) is not int:
            raise TypeError(f"{name} must be an integer")
        if value < 1:
            raise ValueError(f"{name} must be positive")
    if not callable(rng_factory):
        raise TypeError("rng_factory must be callable")
    # Catch local functions/lambdas and non-serializable inputs before any spawn.
    # Child import errors can still occur and propagate through the pool.
    pickle.dumps((request, rng_factory))
    starts = iter(range(0, request.trials, batch_size))
    batch_count = (request.trials + batch_size - 1) // batch_size
    records = []
    with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as pool:
        pending = set()
        try:
            for _ in range(min(2 * workers, batch_count)):
                start = next(starts)
                pending.add(pool.submit(_run_batch, request,
                    range(start, min(start + batch_size, request.trials)), rng_factory))
            while pending:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    records.extend(future.result())
                for _ in done:
                    start = next(starts, None)
                    if start is None:
                        break
                    pending.add(pool.submit(_run_batch, request,
                        range(start, min(start + batch_size, request.trials)), rng_factory))
        finally:
            for future in pending:
                future.cancel()
    # The existing constructor sorts indices and checks completeness/seeds/budgets.
    return NpcMeleeSimulationResult(request, tuple(records))
