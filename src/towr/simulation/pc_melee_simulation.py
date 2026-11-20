"""Independent PC encounters; retain observations, discard the battle journal."""
from towr.simulation.pc_npc_ally_statistics import observe_npc_allies
from towr.simulation.pc_ranged_statistics import PcRangedCount,pc_ranged_count_actors
from towr.domain.pc_weapon_inventory import PcWeaponSwapProof
from towr.domain.pc_ranged_models import PcRangedReloadProof

from towr.simulation.pc_npc_ranged_statistics import PcNpcRangedCount
from towr.simulation.pc_extra_attack_statistics import PcExtraAttackCount,pc_extra_attack_actors
from towr.domain.pc_npc_ranged_models import PcNpcRangedReloadProof
from towr.domain.pc_npc_aim_models import PcNpcAimProof
from towr.simulation.pc_rapid_reload_statistics import (
    PcRapidReloadCount, rapid_reload_count_actors, npc_aim_count_actors,
)
from towr.simulation.pc_immediate_attack_statistics import (
    PcImmediateAttackCount, immediate_attack_count_actors,
)
from towr.simulation.pc_companion_statistics import companion_observations
from towr.simulation.pc_musician_statistics import musician_observations
from towr.simulation.pc_oath_statistics import oath_observations

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
    PcAimCount, PcAimCounts, pc_has_aim_capability, PcPotionUseCount, PcMagicCount,
    PcHelpActionCount, PcAllyRecoverActionCount, PcNpcExitCount, PcNpcHelpActionCount, PcNpcExtraAttackCount, PcNpcRecoverActionCount, PcNpcWarpedFormCount,
)


def _rapid_reload_observations(result):
    from towr.domain.pc_aim_models import PcAimProof
    from towr.domain.pc_npc_aim_models import PcNpcAimProof
    actors=rapid_reload_count_actors(result.source)
    if not actors:
        return None
    counts=dict.fromkeys(actors,0)
    seen=set()
    for step in result.steps:
        proof=step.proof
        slot=(proof.execution.slot if type(proof) is PcAttackProof else proof.result.slot
            if type(proof) in (PcAimProof,PcNpcAimProof) else None)
        if slot is None or slot.rapid_reload is None:
            continue
        replace(slot)
        grant=slot.rapid_reload
        if grant.actor_id in tuple(ally.state.actor_id for ally in result.source.npc_allies):continue
        if slot.index!=2 or not slot.executed or grant.actor_id not in counts:
            raise ValueError('Rapid Reload observation lacks its actual executed owned action2')
        key=(grant.actor_id,grant.round_number,grant.slot_request_id)
        if key in seen:
            raise ValueError('one Rapid Reload grant cannot be observed twice')
        seen.add(key)
        counts[grant.actor_id]+=1
    return tuple(PcRapidReloadCount(actor,counts[actor]) for actor in actors)


def _immediate_attack_observations(result):
    """Observe actual free strikes only after the caller validates full replay."""
    from towr.domain.pc_immediate_attack_models import PcImmediateStrikeProof
    actors = immediate_attack_count_actors(result.source)
    counts = dict.fromkeys(actors, 0)
    seen = set()
    for step in result.steps:
        proof = step.proof
        if type(proof) is not PcImmediateStrikeProof:
            continue
        replace(proof)
        request = proof.request
        if request.actor_id in tuple(ally.state.actor_id for ally in result.source.npc_allies):continue
        if request.actor_id not in counts or request.id != request.grant.id:
            raise ValueError('immediate Attack observation requires its actual owner and grant')
        if request.grant.id in seen:
            raise ValueError('one immediate Attack grant cannot be observed twice')
        seen.add(request.grant.id)
        counts[request.actor_id] += 1
    return tuple(PcImmediateAttackCount(actor, counts[actor]) for actor in actors) if actors else None


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
    from towr.domain.pc_npc_champion_models import PcNpcChampionRecoverProof
    from towr.domain.pc_medical_models import PcMedicalTreatmentProof
    from towr.domain.pc_medical_equipment_models import PcMedicalToolRecoverProof
    from towr.domain.pc_extinguish_models import PcExtinguishProof
    from towr.domain.pc_npc_shield_models import PcNpcShieldRecoverProof
    from towr.domain.pc_briarroot_models import PcBriarrootReleaseProof
    from towr.domain.pc_briarroot_weapon_models import PcBriarrootWeaponPickupProof
    from towr.domain.pc_battlefield_movement_models import PcBattlefieldRecoverProof
    from towr.domain.pc_weighted_net_models import PcNetReleaseProof,PcNetPickupProof
    from towr.domain.pc_warped_form_models import PcWarpedFormActivationProof
    from towr.domain.pc_scarab_recover_models import PcScarabHealingProof
    from towr.domain.pc_hammer_recover_models import PcHammerRetrievalProof
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
    potion_counts = None
    if any(member.consumables for member in request.scenario.party):
        from towr.domain.pc_potion_models import PcPotionRecoverProof
        potion_counts = tuple(PcPotionUseCount(member.actor_id, item.id,
            sum(type(step.proof) is PcPotionRecoverProof
                and step.proof.actor_id == member.actor_id and step.proof.item_id == item.id
                for step in result.steps))
            for member in request.scenario.party for item in member.consumables)
    magic_counts = None
    if any(member.wizard is not None for member in request.scenario.party):
        from towr.domain.pc_magic_models import PcCastingProof, PcMiscastRollProof, PcMagicUnsupported
        magic_counts = tuple(PcMagicCount(member.actor_id,
            sum(type(step.proof) is PcCastingProof and step.proof.actor_id==member.actor_id
                for step in result.steps),
            sum(type(step.proof) is PcCastingProof and step.proof.actor_id==member.actor_id
                and step.proof.spell_id is not None for step in result.steps),
            sum(type(step.proof) is PcMiscastRollProof and step.proof.actor_id==member.actor_id
                for step in result.steps),
            int(type(result.unsupported) is PcMagicUnsupported
                and result.unsupported.reason=='pc_magic_miscast_unresolved'
                and result.unsupported.actor_id==member.actor_id))
            for member in request.scenario.party if member.wizard is not None)
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
            sum(isinstance(step.proof,(PcNpcHelpProof,PcHelpProof)) and (step.proof.actor_id if type(step.proof) is PcMedicalToolRecoverProof else step.proof.request.actor_id)==enemy.state.actor_id
                for step in result.steps)) for enemy in request.scenario.enemies),
        tuple(PcNpcExtraAttackCount(enemy.state.actor_id,
            sum(isinstance(step.proof,PcAttackProof) and step.proof.execution.slot_index==2
                and step.proof.execution.slot.rapid_reload is None
                and step.proof.request.actor_id==enemy.state.actor_id for step in result.steps))
            for enemy in request.scenario.enemies),
        tuple(PcNpcRecoverActionCount(enemy.state.actor_id,
            sum(type(step.proof) in (PcMedicalToolRecoverProof,PcNpcChampionRecoverProof,PcMedicalTreatmentProof,PcNpcRecoverProof,PcExtinguishProof,PcBattlefieldRecoverProof,PcNetReleaseProof,PcNetPickupProof,
                PcNpcShieldRecoverProof,PcBriarrootReleaseProof,PcBriarrootWeaponPickupProof,
                PcScarabHealingProof,PcHammerRetrievalProof)
                and (step.proof.actor_id if type(step.proof) is PcMedicalToolRecoverProof else step.proof.request.actor_id)==enemy.state.actor_id
                for step in result.steps)) for enemy in request.scenario.enemies),
        tuple(PcNpcWarpedFormCount(enemy.state.actor_id,
            sum(type(step.proof) is PcWarpedFormActivationProof and step.proof.actor_id==enemy.state.actor_id
                for step in result.steps)) for enemy in request.scenario.enemies), aim=aim,potion_use_counts=potion_counts,
        magic_counts=magic_counts,
        rapid_reload_counts=_rapid_reload_observations(result),
        immediate_attack_counts=_immediate_attack_observations(result),
        companion_counts=companion_observations(result),
        music_counts=musician_observations(result),
        oath_counts=oath_observations(result),
        npc_aim_counts=(tuple(PcAimCount(actor,sum(type(step.proof) is PcNpcAimProof
            and step.proof.request.actor_id==actor for step in result.steps))
            for actor in npc_aim_count_actors(request.scenario))
            if npc_aim_count_actors(request.scenario) else None),
        pc_extra_attack_counts=(tuple(PcExtraAttackCount(member.actor_id,
            sum(type(step.proof) is PcAttackProof and step.proof.request.actor_id==member.actor_id
                and step.proof.execution.slot.duellist_blades is not None for step in result.steps))
            for member in request.scenario.party) if pc_extra_attack_actors(request.scenario) else None),
        pc_ranged_counts=(tuple(PcRangedCount(actor,
            sum(type(step.proof) is PcAttackProof and step.proof.request.actor_id==actor
                and step.proof.ranged_shot is not None for step in result.steps),
            sum(type(step.proof) is PcAttackProof and step.proof.request.actor_id==actor
                and step.proof.ranged_shot is not None
                and step.proof.ranged_shot.execution.source_request.uses_optional_reload_bonus
                for step in result.steps),
            sum(type(step.proof) is PcHelpProof and step.proof.request.actor_id==actor
                and step.proof.ranged_use is not None for step in result.steps),
            sum(type(step.proof) is PcHelpProof and step.proof.request.actor_id==actor
                and step.proof.ranged_use is not None and step.proof.ranged_use.uses_optional_reload_bonus
                for step in result.steps),
            sum(type(step.proof) is PcRangedReloadProof and step.proof.request.actor_id==actor for step in result.steps),
            sum(type(step.proof) is PcWeaponSwapProof and step.proof.actor_id==actor
                or type(step.proof) is PcRecoverProof
                and step.source.participant(actor).weapon_inventory is not None
                and step.source.participant(actor).weapon_inventory.active_item_id
                    !=step.state.participant(actor).weapon_inventory.active_item_id
                for step in result.steps)) for actor in pc_ranged_count_actors(request.scenario))
            if pc_ranged_count_actors(request.scenario) else None),
        npc_ally_counts=observe_npc_allies(result),
        npc_ranged_counts=(tuple(PcNpcRangedCount(policy.actor_id,
            sum(type(step.proof) is PcAttackProof and step.proof.request.actor_id==policy.actor_id
                and step.proof.npc_ranged_shot is not None for step in result.steps),
            sum(type(step.proof) is PcAttackProof and step.proof.request.actor_id==policy.actor_id
                and step.proof.npc_ranged_shot is not None
                and step.proof.npc_ranged_shot.execution.source_request.uses_optional_reload_bonus
                for step in result.steps),
            sum(type(step.proof) is PcNpcRangedReloadProof and step.proof.request.actor_id==policy.actor_id
                for step in result.steps)) for policy in request.scenario.npc_ranged_policies if policy.actor_id in request.scenario.enemy_activation_order)
            if any(p.actor_id in request.scenario.enemy_activation_order for p in request.scenario.npc_ranged_policies) else None))


def run_pc_melee_simulation(request: PcMeleeSimulationRequest, *,
                            rng_factory: Callable[[int], RandomSource] = Random,
                            on_trial_complete: Callable[[PcMeleeTrialRecord], None] | None = None) -> PcMeleeSimulationResult:
    if not isinstance(request, PcMeleeSimulationRequest):
        raise TypeError('simulation requires a PcMeleeSimulationRequest')
    replace(request)
    if not callable(rng_factory):
        raise TypeError('rng_factory must be callable')
    if on_trial_complete is not None and not callable(on_trial_complete):
        raise TypeError('on_trial_complete must be callable')
    records = []
    for index in range(request.trials):
        record = run_pc_melee_trial(request, index, rng_factory=rng_factory)
        records.append(record)
        if on_trial_complete is not None:
            on_trial_complete(record)
    return PcMeleeSimulationResult(request, tuple(records))
