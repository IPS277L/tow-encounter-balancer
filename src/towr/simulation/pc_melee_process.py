"""Reusable spawn execution for independent trials of one PC encounter."""
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import replace
from multiprocessing import get_context
import pickle
from random import Random

from towr.rules.dice import RandomSource
from towr.simulation.pc_melee_models import (
    PcMeleeSimulationRequest,PcMeleeSimulationResult,PcMeleeTrialRecord,
)
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


class PcMeleeSimulationCancelled(Exception):
    """Explicit cancellation, never an incomplete successful simulation."""


# Each spawned process owns its signal reference, installed before any task.
# Rules still receive an explicit seeded RandomSource; no global RNG is used.
_worker_cancel_signal = None


def _initialize_worker(signal):
    global _worker_cancel_signal
    _worker_cancel_signal = signal


def _worker_checkpoint():
    if _worker_cancel_signal is not None and _worker_cancel_signal.is_set():
        raise PcMeleeSimulationCancelled('PC simulation cancelled')


class _InterruptibleSource:
    def __init__(self, source: RandomSource):
        self.source = source

    def randint(self, start: int, end: int) -> int:
        _worker_checkpoint()
        return self.source.randint(start,end)


def _run_process_batch(request: PcMeleeSimulationRequest,indices: range,
        rng_factory: Callable[[int],RandomSource]) -> tuple[PcMeleeTrialRecord,...]:
    records=[]
    for index in indices:
        _worker_checkpoint()
        try:
            record=run_pc_melee_trial(request,index,
                rng_factory=lambda seed:_InterruptibleSource(rng_factory(seed)))
            _worker_checkpoint()
            records.append(record)
        except Exception as error:
            error.add_note(f'PC trial index={index}, seed={request.seed_for(index)}')
            raise
    return tuple(records)


class PcMeleeProcessSession:
    """One pool per search; only one candidate can run through it at a time.

    Up to 2*workers batches are submitted. Parent callbacks receive validated
    completed records in arrival order; the final result sorts trial indices.
    All worker resources are released on cancellation/failure before raising.
    """
    def __init__(self,*,workers: int,batch_size: int=1,cancel_requested=None):
        for name,value in (('workers',workers),('batch_size',batch_size)):
            if type(value) is not int:
                raise TypeError(f'{name} must be an integer')
            if value<1:
                raise ValueError(f'{name} must be positive')
        if cancel_requested is not None and not callable(cancel_requested):
            raise TypeError('cancel_requested must be callable')
        self.workers=workers
        self.batch_size=batch_size
        self.cancel_requested=cancel_requested
        self._context=get_context('spawn')
        self._signal=None
        self._pool=None
        self._closed=False
        self._running=False

    def __enter__(self):
        if self._closed:
            raise RuntimeError('process session is closed')
        return self

    def __exit__(self,kind,error,traceback):
        if kind is not None:
            self._cancel_workers()
        try:
            self.close()
        except BaseException as cleanup:
            if error is None:
                raise
            error.add_note(f'Process cleanup error: {type(cleanup).__name__}: {cleanup}')
        return False

    def _checkpoint(self):
        if self.cancel_requested is not None and self.cancel_requested():
            self._cancel_workers()
            raise PcMeleeSimulationCancelled('PC simulation cancelled')

    def _cancel_workers(self):
        if self._signal is not None:
            self._signal.set()

    def close(self):
        if self._closed:
            return
        self._closed=True
        pool,self._pool=self._pool,None
        try:
            if pool is not None:
                pool.shutdown(wait=True,cancel_futures=True)
        finally:
            self._signal=None

    def _ensure_pool(self):
        if self._pool is None:
            self._signal=self._context.Event()
            self._pool=ProcessPoolExecutor(max_workers=self.workers,mp_context=self._context,
                initializer=_initialize_worker,initargs=(self._signal,))
        return self._pool

    def run(self,request: PcMeleeSimulationRequest,*,
            rng_factory: Callable[[int],RandomSource]=Random,on_trial_complete=None) -> PcMeleeSimulationResult:
        if self._closed or self._running:
            raise RuntimeError('process session is closed or already running')
        if not isinstance(request,PcMeleeSimulationRequest):
            raise TypeError('parallel simulation requires a PcMeleeSimulationRequest')
        replace(request)
        if not callable(rng_factory):
            raise TypeError('rng_factory must be callable')
        if on_trial_complete is not None and not callable(on_trial_complete):
            raise TypeError('on_trial_complete must be callable')
        self._running=True
        pending={}
        records=[]
        starts=iter(range(0,request.trials,self.batch_size))
        try:
            self._checkpoint()
            pickle.dumps((request,rng_factory))
            pool=self._ensure_pool()
            def submit():
                start=next(starts,None)
                if start is None:
                    return False
                self._checkpoint()
                indices=range(start,min(start+self.batch_size,request.trials))
                pending[pool.submit(_run_process_batch,request,indices,rng_factory)]=indices
                return True
            for _ in range(min(2*self.workers,(request.trials+self.batch_size-1)//self.batch_size)):
                submit()
            while pending:
                self._checkpoint()
                done,_=wait(pending,timeout=.05,return_when=FIRST_COMPLETED)
                self._checkpoint()
                for future in done:
                    indices=pending.pop(future)
                    batch=future.result()
                    if type(batch) is not tuple or len(batch)!=len(indices):
                        raise ValueError('worker batch does not cover its assigned trials')
                    for index,record in zip(indices,batch):
                        if type(record) is not PcMeleeTrialRecord:
                            raise TypeError('worker must return typed PC trial records')
                        replace(record)
                        if (record.trial_index!=index or record.seed!=request.seed_for(index)
                                or record.source_scenario!=request.scenario):
                            raise ValueError('worker record has a foreign source, seed or index')
                    for record in batch:
                        self._checkpoint()
                        records.append(record)
                        if on_trial_complete is not None:
                            on_trial_complete(record)
                        self._checkpoint()
                for _ in done:
                    if not submit():
                        break
            self._checkpoint()
            return PcMeleeSimulationResult(request,tuple(records))
        except BaseException as error:
            self._cancel_workers()
            for future in pending:
                future.cancel()
            try:
                self.close()
            except BaseException as cleanup:
                error.add_note(f'Process cleanup error: {type(cleanup).__name__}: {cleanup}')
            raise
        finally:
            self._running=False
