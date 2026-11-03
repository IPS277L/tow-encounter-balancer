"""Bounded spawn batches for PC encounters; same records as sequential execution."""
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import replace
from multiprocessing import get_context
import pickle
from random import Random

from towr.rules.dice import RandomSource
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest, PcMeleeSimulationResult, PcMeleeTrialRecord
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


def _run_batch(request: PcMeleeSimulationRequest, indices: range,
               rng_factory: Callable[[int], RandomSource]) -> tuple[PcMeleeTrialRecord, ...]:
    records = []
    for index in indices:
        try:
            records.append(run_pc_melee_trial(request, index, rng_factory=rng_factory))
        except Exception as error:
            error.add_note(f'M9 trial index={index}, seed={request.seed_for(index)}')
            raise
    return tuple(records)


def run_pc_melee_simulation_parallel(request: PcMeleeSimulationRequest, *, workers: int,
        batch_size: int = 32, rng_factory: Callable[[int], RandomSource] = Random) -> PcMeleeSimulationResult:
    """No fallback, retry, or partial result; at most 2*workers batches in flight."""
    if not isinstance(request, PcMeleeSimulationRequest):
        raise TypeError('parallel simulation requires a PcMeleeSimulationRequest')
    replace(request)
    for name, value in (('workers', workers), ('batch_size', batch_size)):
        if type(value) is not int:
            raise TypeError(f'{name} must be an integer')
        if value < 1:
            raise ValueError(f'{name} must be positive')
    if not callable(rng_factory):
        raise TypeError('rng_factory must be callable')
    pickle.dumps((request, rng_factory))
    starts = iter(range(0, request.trials, batch_size))
    records = []
    with ProcessPoolExecutor(max_workers=workers, mp_context=get_context('spawn')) as pool:
        pending = set()
        try:
            for _ in range(min(2*workers, (request.trials+batch_size-1)//batch_size)):
                start = next(starts)
                pending.add(pool.submit(_run_batch, request,
                    range(start, min(start+batch_size, request.trials)), rng_factory))
            while pending:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    records.extend(future.result())
                for _ in done:
                    start = next(starts, None)
                    if start is None:
                        break
                    pending.add(pool.submit(_run_batch, request,
                        range(start, min(start+batch_size, request.trials)), rng_factory))
        finally:
            for future in pending:
                future.cancel()
    return PcMeleeSimulationResult(request, tuple(records))
