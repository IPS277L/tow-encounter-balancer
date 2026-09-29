from __future__ import annotations

from collections.abc import Callable
from random import Random

from towr.domain.npc_mixed_scenario_result_models import NpcMixedScenarioResult
from towr.engine.npc_mixed_scenario_runner import run_npc_mixed_scenario
from towr.rules.dice import RandomSource
from towr.simulation.npc_mixed_models import (
    NpcMixedSimulationRequest, NpcMixedSimulationResult, NpcMixedTrialSummary,
)


def run_npc_mixed_trial(
    request: NpcMixedSimulationRequest, trial_index: int, *, rng_factory: Callable[[int], RandomSource] = Random,
) -> NpcMixedTrialSummary:
    """Run one indexed trial from the same immutable initial scenario with a fresh RNG."""
    if not isinstance(request, NpcMixedSimulationRequest):
        raise TypeError("trial requires a typed simulation request")
    seed = request.seed_for(trial_index)
    result = run_npc_mixed_scenario(request.scenario, rng_factory(seed))
    if not isinstance(result, NpcMixedScenarioResult):
        raise TypeError("scenario runner must return a typed result")
    if result.source_scenario != request.scenario:
        raise ValueError("scenario result belongs to a different simulation input")
    # The last runner call may still report pending defeat. The scenario outcome
    # includes its terminal acknowledgement, without an extra Attack or round.
    return NpcMixedTrialSummary(trial_index, seed, result.outcome,
                                result.runner_report.executed_attack_count, result.runner_report.visited_round_count)


def run_npc_mixed_simulation(
    request: NpcMixedSimulationRequest, *, rng_factory: Callable[[int], RandomSource] = Random,
) -> NpcMixedSimulationResult:
    """Sequential batch. Failures propagate; no partial batch is reported as complete.

    A custom factory must return a new independent RNG for every call. Full
    battle journals are discarded after projection, keeping only trial summaries.
    """
    if not isinstance(request, NpcMixedSimulationRequest):
        raise TypeError("simulation requires a typed request")
    return NpcMixedSimulationResult(request, tuple(
        run_npc_mixed_trial(request, index, rng_factory=rng_factory) for index in range(request.trials)
    ))
