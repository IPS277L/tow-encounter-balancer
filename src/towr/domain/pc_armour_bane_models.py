"""Encounter-owned Armour Bane provenance; physical armour stays independent."""
from __future__ import annotations

from dataclasses import replace

from towr.domain.attack_models import AttackOutcome,DamageImpactSpec,ResilienceProfile
from towr.domain.talent_armour_bane_models import ArmourBaneApplication,armour_bane_eligible_sources
from towr.domain.talent_actor_models import actor_acquired_talents
from towr.domain.talent_catalog import TalentId


def build_armour_bane_application(state,request,execution,weapon_use)->ArmourBaneApplication|None:
    """Bind one successful physical Attack after its original Damage comparison."""
    from towr.domain.action_execution_models import AttackActionExecutionRequest,AttackActionExecutionResult
    from towr.domain.pc_immediate_attack_models import PcImmediateStrikeRequest,PcImmediateStrikeExecutionResult
    if (type(request),type(execution)) not in ((AttackActionExecutionRequest,AttackActionExecutionResult),
            (PcImmediateStrikeRequest,PcImmediateStrikeExecutionResult)):
        raise TypeError('Armour Bane requires the exact actual ordinary or immediate Attack source')
    if (execution.request_id,execution.actor_id,execution.target_id,execution.previous_state)!=(
            request.id,request.actor_id,request.target_id,request.state):
        raise ValueError('Armour Bane execution differs from its actual Attack source')
    impact=request.kernel_request.attack.impact_spec
    talent=next((entry for entry in actor_acquired_talents(state,request.actor_id)
        if entry.id is TalentId.ARMOUR_BANE),None)
    if (talent is None or weapon_use is None or type(impact) is not DamageImpactSpec
            or execution.resolution.attack.outcome is not AttackOutcome.HIT):
        return None
    before=impact.resilience
    sources=armour_bane_eligible_sources(weapon_use,before)
    if not sources or (before.bonus==0 and not before.is_armoured):
        return None
    return ArmourBaneApplication(request.id,request.actor_id,request.target_id,talent,
        weapon_use,sources,before)


def armour_bane_attack_updates(state,application,updates):
    """Rebuild NPC protection after all effects of this same physical Attack.

    PC protection is queried from actual equipment and the appended history.
    An NPC stores current Resilience, so compose the new source atomically with
    any simultaneous inventory change before constructing the next state.
    """
    if application is None or application.target_id in state.source.pc_activation_order:
        return updates
    from towr.domain.pc_npc_resilience_models import npc_base_equipment_resilience
    from towr.domain.pc_actor_models import pc_actor_npc_snapshot,pc_companion
    actor=application.target_id
    companion=None if actor in state.source.npc_activation_order else pc_companion(state,actor)
    if companion is not None:
        rows=updates.get('companions',state.companions)
        current=next(row for row in rows if row.rider_id==companion.rider_id)
        actual=pc_actor_npc_snapshot(state,actor)
        from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
        validate_pc_melee_source_types(current.snapshot.definition,actual.definition)
        if (current.snapshot.definition!=actual.definition or current.snapshot.state.actor_id!=actor
                or current.snapshot.state.side is not actual.state.side):
            raise ValueError('Armour Bane cannot replace the actual mount body, identity or side')
        base=npc_base_equipment_resilience(state,actor)
        resilience=armour_bane_resilience_from_sources(base,(*armour_bane_applications(state,actor),application))
        body=replace(current,snapshot=replace(current.snapshot,
            state=replace(current.snapshot.state,current_resilience=resilience)))
        return dict(updates,companions=tuple(body if row.rider_id==body.rider_id else row for row in rows))
    enemies=updates.get('enemies',state.enemies)
    target=next(enemy for enemy in enemies if enemy.state.actor_id==actor)
    shield=(target.state.holds_shield if target.definition.generated_components is not None else None)
    base=npc_base_equipment_resilience(state,actor,shield_held=shield)
    resilience=armour_bane_resilience_from_sources(base,(*armour_bane_applications(state,actor),application))
    return dict(updates,enemies=tuple(replace(enemy,state=replace(enemy.state,current_resilience=resilience))
        if enemy.state.actor_id==actor else enemy for enemy in enemies))


def armour_bane_resilience_from_sources(base:ResilienceProfile,
        sources:tuple[ArmourBaneApplication,...])->ResilienceProfile:
    """Compose actual reductions on present equipment without a negative bonus.

    A zero-point application carries PG73's armoured-at-floor consequence,
    without damaging a future item. Physical weight, Traits and wards remain.
    """
    if type(base) is not ResilienceProfile:
        raise TypeError('Armour Bane composition needs its exact present Resilience')
    replace(base)
    if type(sources) is not tuple or any(type(source) is not ArmourBaneApplication for source in sources):
        raise TypeError('Armour Bane composition needs its exact source tuple')
    if not sources:
        return base
    target=sources[0].target_id
    identifiers=set()
    for source in sources:
        replace(source)
        if source.target_id!=target or source.attack_id in identifiers:
            raise ValueError('Armour Bane composition cannot mix targets or repeat an Attack')
        identifiers.add(source.attack_id)
    bonus=max(0,base.bonus-sum(source.reduction for source in sources))
    return replace(base,bonus=bonus,armoured=False if bonus==0 else base.armoured)


def armour_bane_applications(state,actor_id:str)->tuple[ArmourBaneApplication,...]:
    """Read complete atomic Attack receipts, not free-standing numeric loss."""
    from towr.domain.pc_melee_result_models import PcAttackProof,validate_pc_melee_source_types
    from towr.domain.pc_actor_models import pc_actor_side
    if actor_id not in (*state.source.pc_activation_order,*state.source.npc_activation_order):
        pc_actor_side(state,actor_id)  # Inactive mount bodies still retain their own loss ledger.
    result=[]
    for proof in state.history:
        from towr.domain.pc_immediate_attack_models import PcImmediateStrikeProof
        if type(proof) not in (PcAttackProof,PcImmediateStrikeProof):
            continue
        application=proof.armour_bane
        if application is None:
            continue
        if type(application) is not ArmourBaneApplication:
            raise TypeError('Armour Bane history must preserve its exact application type')
        replace(application)
        if application.target_id!=actor_id:
            continue
        request=proof.request
        impact=request.kernel_request.attack.impact_spec
        if (application.attack_id!=request.id or application.actor_id!=request.actor_id
                or application.target_id!=request.target_id
                or proof.execution.resolution.attack.outcome is not AttackOutcome.HIT
                or type(impact) is not DamageImpactSpec
                or application.before!=impact.resilience
                or application.weapon_use!=proof.weapon_intent.attack_use
                or application.talent not in actor_acquired_talents(state,request.actor_id)):
            raise ValueError('Armour Bane history lost its actual successful Attack, item or owner')
        validate_pc_melee_source_types(application.before,impact.resilience)
        validate_pc_melee_source_types(application.weapon_use,proof.weapon_intent.attack_use)
        result.append(application)
    sources=tuple(result)
    if len({source.attack_id for source in sources})!=len(sources):
        raise ValueError('an Attack cannot lower the same target Resilience twice')
    return sources


def armour_bane_resilience(state,actor_id:str,base:ResilienceProfile)->ResilienceProfile:
    return armour_bane_resilience_from_sources(base,armour_bane_applications(state,actor_id))
