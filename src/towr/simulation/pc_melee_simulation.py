"""Independent PC encounters; retain observations, discard the battle journal."""
from collections.abc import Callable
from dataclasses import replace
from random import Random

from towr.domain.fate_models import FateSpendKind
from towr.domain.pc_melee_models import validate_pc_melee_scenario_admission
from towr.domain.pc_melee_result_models import PcMeleeScenarioResult, PcHelpProof, PcRecoverProof, PcNpcHelpProof, PcAttackProof
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.rules.dice import RandomSource
from towr.simulation.pc_melee_models import (
    PcMeleeSimulationRequest, PcMeleeSimulationResult, PcMeleeTrialRecord, PcNearMissBurnCount, PcGloriousSpendCount,
    PcAimCount, PcAimCounts, pc_has_aim_capability,
    PcHelpActionCount, PcAllyRecoverActionCount, PcNpcExitCount, PcNpcHelpActionCount, PcNpcExtraAttackCount, PcNpcRecoverActionCount, PcNpcWarpedFormCount,
)


def run_pc_melee_trial(request: PcMeleeSimulationRequest, trial_index: int, *,
                       rng_factory: Callable[[int], RandomSource] = Random) -> PcMeleeTrialRecord:
    if not isinstance(request, PcMeleeSimulationRequest):
        raise TypeError('trial requires a PcMeleeSimulationRequest')
    replace(request)
    if not callable(rng_factory):
        raise TypeError('rng_factory must be callable')
    seed = request.seed_for(trial_index)
    result = run_pc_melee_scenario(request.scenario, rng_factory(seed))
    if type(result) is not PcMeleeScenarioResult:
        raise TypeError('PC encounter runner must return a typed result')
    # Admit the actual journal before turning mutable cached state into counters.
    # Projection verifies proofs without executing tests or consuming RNG again.
    replace(result)
    validate_pc_melee_scenario_admission(result.source)
    if result.source != request.scenario:
        raise ValueError('PC encounter result belongs to another source')
    from towr.domain.pc_flagellant_models import PcNpcRecoverProof
    from towr.domain.pc_warped_form_models import PcWarpedFormActivationProof
    aim = None
    if pc_has_aim_capability(request.scenario):
        from towr.domain.pc_aim_models import PcAimProof
        aim = PcAimCounts(tuple(PcAimCount(member.actor_id,
            sum(type(step.proof) is PcAimProof and step.proof.request.actor_id==member.actor_id
                for step in result.steps)) for member in request.scenario.party),
            tuple(PcAimCount(member.actor_id,
                sum(spend.kind is FateSpendKind.SECOND_ACTION for spend in result.state.participant(member.actor_id).fate.spends)
                -sum(spend.kind is FateSpendKind.SECOND_ACTION for spend in member.fate.spends))
                for member in request.scenario.party))
    return PcMeleeTrialRecord(request.scenario, trial_index, seed, result.outcome,
        result.executed_actions, result.started_rounds, result.completed_rounds, result.defeated_pc_ids,
        tuple(PcNearMissBurnCount(member.actor_id,
            len(result.state.participant(member.actor_id).fate.burns)-len(member.fate.burns))
            for member in request.scenario.party),
        tuple(PcGloriousSpendCount(member.actor_id,
            sum(spend.kind is FateSpendKind.GLORIOUS_TEST for spend in result.state.participant(member.actor_id).fate.spends)
            -sum(spend.kind is FateSpendKind.GLORIOUS_TEST for spend in member.fate.spends))
            for member in request.scenario.party),
        tuple(PcHelpActionCount(member.actor_id,
            sum(isinstance(step.proof,PcHelpProof) and step.proof.request.actor_id==member.actor_id
                for step in result.steps)) for member in request.scenario.party),
        tuple(PcAllyRecoverActionCount(member.actor_id,
            sum(isinstance(step.proof,PcRecoverProof)
                and step.proof.result.source_request.actor_id==member.actor_id
                and any(change.entity_id!=member.actor_id
                    for change in step.proof.result.resolution.condition_changes)
                for step in result.steps)) for member in request.scenario.party),
        tuple(PcNpcExitCount(enemy.state.actor_id,int(enemy.state.actor_id in result.exited_npc_ids))
            for enemy in request.scenario.enemies),
        tuple(PcNpcHelpActionCount(enemy.state.actor_id,
            sum(isinstance(step.proof,PcNpcHelpProof) and step.proof.request.actor_id==enemy.state.actor_id
                for step in result.steps)) for enemy in request.scenario.enemies),
        tuple(PcNpcExtraAttackCount(enemy.state.actor_id,
            sum(isinstance(step.proof,PcAttackProof) and step.proof.execution.slot_index==2
                and step.proof.request.actor_id==enemy.state.actor_id for step in result.steps))
            for enemy in request.scenario.enemies),
        tuple(PcNpcRecoverActionCount(enemy.state.actor_id,
            sum(type(step.proof) is PcNpcRecoverProof and step.proof.actor_id==enemy.state.actor_id
                for step in result.steps)) for enemy in request.scenario.enemies),
        tuple(PcNpcWarpedFormCount(enemy.state.actor_id,
            sum(type(step.proof) is PcWarpedFormActivationProof and step.proof.actor_id==enemy.state.actor_id
                for step in result.steps)) for enemy in request.scenario.enemies), aim=aim)


def run_pc_melee_simulation(request: PcMeleeSimulationRequest, *,
                            rng_factory: Callable[[int], RandomSource] = Random) -> PcMeleeSimulationResult:
    if not isinstance(request, PcMeleeSimulationRequest):
        raise TypeError('simulation requires a PcMeleeSimulationRequest')
    replace(request)
    if not callable(rng_factory):
        raise TypeError('rng_factory must be callable')
    return PcMeleeSimulationResult(request, tuple(
        run_pc_melee_trial(request, index, rng_factory=rng_factory) for index in range(request.trials)))
