"""Sequential independent trials over the unchanged M8 single-run boundary."""
from collections.abc import Callable
from random import Random

from towr.domain.npc_magic_scenario_result_models import NpcMagicScenarioResult
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.dice import RandomSource
from towr.simulation.npc_magic_models import (
    NpcMagicSimulationRequest, NpcMagicSimulationResult, NpcMagicTrialRecord,
)


def run_npc_magic_trial(
    request: NpcMagicSimulationRequest, trial_index: int, *, rng_factory: Callable[[int], RandomSource] = Random,
) -> NpcMagicTrialRecord:
    """Use a fresh caller-supplied RNG and discard the journal after projection."""
    if not isinstance(request, NpcMagicSimulationRequest):
        raise TypeError("magic trial requires a typed simulation request")
    seed = request.seed_for(trial_index)
    result = run_npc_magic_scenario(request.scenario, rng_factory(seed))
    if not isinstance(result, NpcMagicScenarioResult):
        raise TypeError("magic runner must return a typed scenario result")
    if result.source != request.scenario:
        raise ValueError("magic result belongs to a different full scenario")
    return NpcMagicTrialRecord(
        request.scenario, trial_index, seed, result.outcome,
        result.executed_actions, result.started_rounds, result.completed_rounds,
    )


def run_npc_magic_simulation(
    request: NpcMagicSimulationRequest, *, rng_factory: Callable[[int], RandomSource] = Random,
) -> NpcMagicSimulationResult:
    """Return a complete batch; propagate failures without retry or partial success.

    Each factory call must supply a new independent RandomSource. The same full
    immutable input is shared by all compact records, with no state carry-over.
    """
    if not isinstance(request, NpcMagicSimulationRequest):
        raise TypeError("magic simulation requires a typed request")
    return NpcMagicSimulationResult(request, tuple(
        run_npc_magic_trial(request, index, rng_factory=rng_factory) for index in range(request.trials)
    ))
