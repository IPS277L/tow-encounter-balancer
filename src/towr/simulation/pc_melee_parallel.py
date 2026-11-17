"""One-shot spawn API over the reusable PC trial process backend."""
from collections.abc import Callable
from dataclasses import replace
from random import Random

from towr.rules.dice import RandomSource
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest,PcMeleeSimulationResult
from towr.simulation.pc_melee_process import PcMeleeProcessSession


def run_pc_melee_simulation_parallel(request: PcMeleeSimulationRequest,*,workers: int,
        batch_size: int=32,rng_factory: Callable[[int],RandomSource]=Random) -> PcMeleeSimulationResult:
    """No fallback/retry/partial result; at most 2*workers batches in flight."""
    if not isinstance(request,PcMeleeSimulationRequest):
        raise TypeError('parallel simulation requires a PcMeleeSimulationRequest')
    replace(request)
    with PcMeleeProcessSession(workers=workers,batch_size=batch_size) as session:
        return session.run(request,rng_factory=rng_factory)
