"""Independent PC encounters; retain observations, discard the battle journal."""
from collections.abc import Callable
from dataclasses import replace
from random import Random

from towr.domain.pc_melee_models import validate_pc_melee_scenario_admission
from towr.domain.pc_melee_result_models import PcMeleeScenarioResult
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.rules.dice import RandomSource
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest, PcMeleeSimulationResult, PcMeleeTrialRecord


def run_pc_melee_trial(request: PcMeleeSimulationRequest, trial_index: int, *,
                       rng_factory: Callable[[int], RandomSource] = Random) -> PcMeleeTrialRecord:
    if not isinstance(request, PcMeleeSimulationRequest):
        raise TypeError('trial requires a PcMeleeSimulationRequest')
    replace(request)
    if not callable(rng_factory):
        raise TypeError('rng_factory must be callable')
    seed = request.seed_for(trial_index)
    result = run_pc_melee_scenario(request.scenario, rng_factory(seed))
    if not isinstance(result, PcMeleeScenarioResult):
        raise TypeError('PC encounter runner must return a typed result')
    validate_pc_melee_scenario_admission(result.source)
    if result.source != request.scenario:
        raise ValueError('PC encounter result belongs to another source')
    return PcMeleeTrialRecord(request.scenario, trial_index, seed, result.outcome,
        result.executed_actions, result.started_rounds, result.completed_rounds)


def run_pc_melee_simulation(request: PcMeleeSimulationRequest, *,
                            rng_factory: Callable[[int], RandomSource] = Random) -> PcMeleeSimulationResult:
    if not isinstance(request, PcMeleeSimulationRequest):
        raise TypeError('simulation requires a PcMeleeSimulationRequest')
    replace(request)
    if not callable(rng_factory):
        raise TypeError('rng_factory must be callable')
    return PcMeleeSimulationResult(request, tuple(
        run_pc_melee_trial(request, index, rng_factory=rng_factory) for index in range(request.trials)))
