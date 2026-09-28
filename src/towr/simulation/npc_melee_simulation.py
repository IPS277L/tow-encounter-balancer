from __future__ import annotations

from collections.abc import Callable
from random import Random

from towr.domain.npc_melee_scenario_result_models import NpcMeleeScenarioResult
from towr.engine.npc_melee_scenario_runner import run_npc_melee_scenario
from towr.rules.dice import RandomSource
from towr.simulation.npc_melee_models import (
    NpcMeleeSimulationRequest, NpcMeleeSimulationResult, NpcMeleeTrialSummary,
)


def run_npc_melee_trial(
    request: NpcMeleeSimulationRequest, trial_index: int, *, rng_factory: Callable[[int], RandomSource] = Random,
) -> NpcMeleeTrialSummary:
    """Run one indexed trial from the same immutable initial scenario with a fresh RNG."""
    if not isinstance(request, NpcMeleeSimulationRequest):
        raise TypeError("trial requires a typed simulation request")
    seed = request.seed_for(trial_index)
    result = run_npc_melee_scenario(request.scenario, rng_factory(seed))
    if not isinstance(result, NpcMeleeScenarioResult):
        raise TypeError("scenario runner must return a typed result")
    if result.source_scenario != request.scenario:
        raise ValueError("scenario result belongs to a different simulation input")
    # The last runner call may still report pending defeat. The scenario outcome
    # includes its terminal acknowledgement, without an extra Attack or round.
    return NpcMeleeTrialSummary(trial_index, seed, result.outcome,
                                result.runner_report.executed_attack_count, result.runner_report.visited_round_count)


def run_npc_melee_simulation(
    request: NpcMeleeSimulationRequest, *, rng_factory: Callable[[int], RandomSource] = Random,
) -> NpcMeleeSimulationResult:
    """Sequential batch. Failures propagate; no partial batch is reported as complete.

    A custom factory must return a new independent RNG for every call. Full
    battle journals are discarded after projection, keeping only trial summaries.
    """
    if not isinstance(request, NpcMeleeSimulationRequest):
        raise TypeError("simulation requires a typed request")
    return NpcMeleeSimulationResult(request, tuple(
        run_npc_melee_trial(request, index, rng_factory=rng_factory) for index in range(request.trials)
    ))
