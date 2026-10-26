"""Optional spawn execution over the unchanged magic trial contract (ADR-0039)."""
from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from dataclasses import replace
from multiprocessing import get_context
import pickle
from random import Random

from towr.domain.npc_magic_scenario_models import NpcMagicScenario
from towr.rules.dice import RandomSource
from towr.simulation.npc_magic_models import (
    NpcMagicSimulationRequest, NpcMagicSimulationResult, NpcMagicTrialRecord,
)
from towr.simulation.npc_magic_simulation import run_npc_magic_trial


def _run_batch(
    request: NpcMagicSimulationRequest, indices: range, rng_factory: Callable[[int], RandomSource],
) -> tuple[NpcMagicTrialRecord, ...]:
    records = []
    for index in indices:
        try:
            records.append(run_npc_magic_trial(request, index, rng_factory=rng_factory))
        except Exception as error:
            error.add_note(f"M8 trial index={index}, seed={request.seed_for(index)}")
            raise
    return tuple(records)


def _normalize_batch(
    request: NpcMagicSimulationRequest, indices: range, payload: object,
) -> tuple[NpcMagicTrialRecord, ...]:
    """Check the transported source before replacing it with the parent's input."""
    if type(payload) is not tuple:
        raise TypeError("magic worker payload must be a tuple of records")
    if len(payload) != indices.stop - indices.start:
        raise ValueError("magic worker must return its entire assigned batch")
    normalized = []
    for index, record in zip(indices, payload):
        if not isinstance(record, NpcMagicTrialRecord):
            raise TypeError("magic worker returned a foreign record type")
        if not isinstance(record.source_scenario, NpcMagicScenario):
            raise TypeError("magic worker record requires its typed source scenario")
        if record.source_scenario != request.scenario:
            raise ValueError("magic worker record belongs to a different full scenario")
        # Unpickling does not call __post_init__. Reconstruct only after the full
        # source check, enforcing scalar/Enum/bool/counter guards before equality.
        canonical = replace(record, source_scenario=request.scenario)
        if canonical.trial_index != index:
            raise ValueError("magic worker record does not match its assigned index/order")
        if canonical.seed != request.seed_for(index):
            raise ValueError("magic worker record seed does not match the parent request")
        normalized.append(canonical)
    return tuple(normalized)


def run_npc_magic_simulation_parallel(
    request: NpcMagicSimulationRequest, *, workers: int, batch_size: int = 32,
    rng_factory: Callable[[int], RandomSource] = Random,
) -> NpcMagicSimulationResult:
    """Run indexed trials in a fresh spawn pool, retaining the sequential result.

    Call from an importable main module with an ``if __name__ == '__main__'``
    guard. Factories must be picklable/importable and create a fresh RNG per seed.
    At most 2*workers batches are outstanding. Shutdown waits for running work;
    failure never returns a partial result or retries with another backend.
    """
    if not isinstance(request, NpcMagicSimulationRequest):
        raise TypeError("parallel magic simulation requires a typed request")
    for name, value in (("workers", workers), ("batch_size", batch_size)):
        if type(value) is not int:
            raise TypeError(f"{name} must be an integer")
        if value < 1:
            raise ValueError(f"{name} must be positive")
    if not callable(rng_factory):
        raise TypeError("rng_factory must be callable")
    pickle.dumps((request, rng_factory))

    starts = iter(range(0, request.trials, batch_size))
    batch_count = (request.trials + batch_size - 1) // batch_size
    records = []
    with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as pool:
        pending: dict[Future[tuple[NpcMagicTrialRecord, ...]], range] = {}
        try:
            for _ in range(min(2 * workers, batch_count)):
                start = next(starts)
                indices = range(start, min(start + batch_size, request.trials))
                pending[pool.submit(_run_batch, request, indices, rng_factory)] = indices
            while pending:
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                completed_count = len(done)
                for future in done:
                    indices = pending.pop(future)
                    records.extend(_normalize_batch(request, indices, future.result()))
                # A completed Future retains its raw pickle payload. Release the
                # whole done group before refill; only canonical records survive.
                del future, done
                for _ in range(completed_count):
                    start = next(starts, None)
                    if start is None:
                        break
                    indices = range(start, min(start + batch_size, request.trials))
                    pending[pool.submit(_run_batch, request, indices, rng_factory)] = indices
        finally:
            cancellation_error = None
            for future in pending:
                try:
                    future.cancel()
                except Exception as error:
                    if cancellation_error is None:
                        cancellation_error = error
                    else:
                        cancellation_error.add_note(f"Additional cancellation error: {type(error).__name__}: {error}")
            if cancellation_error is not None:
                # Standard exception chaining preserves an active execution error.
                # The pool context still performs shutdown, including on failure.
                raise cancellation_error
    return NpcMagicSimulationResult(request, tuple(records))
