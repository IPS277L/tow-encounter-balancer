"""Source-bound repeated-Stagger defeat; original Goblin equipment stays separate."""
from towr.domain.pc_demigryph_models import pc_kernel_attack_types
from dataclasses import replace

from towr.domain.injury_models import (
    MinionStaggerDefeatCause,MinionStaggerDefeatResult,MinionStaggerDefeatOutcome,
    MinionStaggerDefeatSpec,
)
from towr.domain.pc_npc_ability_models import pc_npc_stagger_defeat_spec


def _stagger_defeat_spec(state,target):
    from towr.domain.pc_actor_models import pc_actor_npc_snapshot
    snapshot=pc_actor_npc_snapshot(state,target)
    if target in state.source.enemy_activation_order:
        spec=pc_npc_stagger_defeat_spec(snapshot.definition)
        if spec is None or spec.outcome is not MinionStaggerDefeatOutcome.FLED:
            raise ValueError('fleeing defeat requires the actual original Dirty Coward profile')
        return spec
    from towr.domain.pc_companion_effect_models import companion_profile
    from towr.domain.pc_undead_minion_models import pc_undead_minion_source
    from towr.domain.undead_minion_models import undead_minion_stagger_defeat_spec
    profile=companion_profile(state,target)
    source=pc_undead_minion_source(state,target)
    if not profile.undead or source is None:
        raise ValueError('companion destruction requires its actual canonical Undead Minion source')
    return undead_minion_stagger_defeat_spec(source,target)


def validate_pc_minion_defeat_equipment(state) -> None:
    routed={}
    route_kinds={}
    acknowledged=set()
    from towr.domain.pc_melee_result_models import PcMinionStaggerDefeatProof
    from towr.domain.pc_demigryph_models import pc_kernel_resolution
    from towr.domain.pc_warped_form_models import PcWarpedFormTargetProof,PcWarpedFormMinionDefeatProof
    attack_types=pc_kernel_attack_types()
    for proof in state.history:
        wave=type(proof) is PcWarpedFormTargetProof
        attack=type(proof) in attack_types
        result=proof.result if wave else pc_kernel_resolution(proof) if attack else None
        if result is not None and result.minion_stagger_defeat is not None:
            defeat=result.minion_stagger_defeat
            if type(defeat) is not MinionStaggerDefeatResult:
                raise TypeError('repeated-Stagger defeat requires its exact typed result')
            replace(defeat)
            target=proof.request.target_id
            spec=_stagger_defeat_spec(state,target)
            actual_spec=proof.request.minion_stagger_defeat if wave else proof.request.kernel_request.minion_stagger_defeat
            if type(actual_spec) is not MinionStaggerDefeatSpec:
                raise TypeError('repeated-Stagger defeat requires its actual typed request source')
            replace(actual_spec)
            identifier=proof.request.id if wave else proof.request.kernel_request.id
            expected=MinionStaggerDefeatCause(identifier+':minion-stagger-defeat',target,spec.rule_id,
                outcome=spec.outcome)
            actual_state=result.state if wave else result.target_state
            if (defeat.cause!=expected or target in routed or actual_spec!=spec
                    or actual_state!=defeat.state):
                raise ValueError('repeated-Stagger defeat changed its actual target/source/outcome or repeated a defeat')
            routed[target]=defeat
            route_kinds[target]='wave' if wave else 'attack'
        elif type(proof) is PcWarpedFormMinionDefeatProof:
            replace(proof)
            target=proof.target_id
            if target in acknowledged or target not in routed or route_kinds[target]!='wave':
                raise ValueError('wave defeat acknowledgement lacks its one actual preceding target')
            if routed[target].request_id!=proof.activation_id+':target:'+target+':minion-stagger-defeat':
                raise ValueError('wave defeat acknowledgement changed its activation source')
            acknowledged.add(target)
        elif type(proof) is PcMinionStaggerDefeatProof:
            if type(proof.source) is not MinionStaggerDefeatCause:
                raise TypeError('defeat acknowledgement requires its typed actual cause')
            replace(proof.source)
            target=proof.source.target_id
            if (target in acknowledged or target not in routed or route_kinds[target]!='attack'
                    or routed[target].cause!=proof.source):
                raise ValueError('defeat acknowledgement is detached, duplicated or precedes its actual source')
            acknowledged.add(target)
    for target,defeat in routed.items():
        count=state.pending.count(defeat.cause)
        if count!=int(target not in acknowledged):
            raise ValueError('repeated-Stagger defeat must await or consume exactly one actual acknowledgement')
    for enemy,old in zip(state.enemies,state.source.enemies,strict=True):
        target=enemy.state.actor_id
        defeat=routed.get(target)
        from towr.domain.injury_models import ProfileDecapitationCause
        cause=enemy.state.injury.defeat_cause
        if type(cause) is ProfileDecapitationCause:
            from towr.domain.pc_melee_result_models import PcAttackProof
            from towr.domain.pc_demigryph_models import pc_kernel_resolution
            actual=next((proof for proof in state.history if type(proof) in pc_kernel_attack_types()
                and proof.request.target_id==target
                and proof.request.kernel_request.id+':wound'==cause.source_id),None)
            if (actual is None or actual.request.kernel_request.fixed_character_wound is None
                    or pc_kernel_resolution(actual).profile_wound is None
                    or pc_kernel_resolution(actual).profile_wound.state.defeat_cause!=cause):
                raise ValueError('NPC decapitation lacks its actual fixed-Wound source Attack')
        elif cause!=(defeat.cause if defeat is not None else None):
            raise ValueError('NPC non-Wound defeat lacks its actual source Attack')
        if defeat is not None and enemy.state.injury!=defeat.state:
            raise ValueError('fleeing NPC injury changed after its actual defeat')
        from towr.domain.pc_npc_resilience_models import npc_current_resilience
        expected=replace(old.state,current_resilience=npc_current_resilience(state,target))
        if old.definition.generated_components is not None:
            from towr.domain.pc_npc_shield_models import NpcShieldLocation
            shield=next((item for item in state.npc_shields if item.actor_id==target),None)
            if shield is not None:
                held=shield.location is NpcShieldLocation.HELD
                expected=replace(expected,holds_shield=held)
        if old.definition.generated_components is not None:
            from towr.domain.weapon_inventory_models import WeaponItemLocation
            inventory=enemy.state.weapon_inventory
            held=inventory is not None and any(item.location is WeaponItemLocation.HELD for item in inventory.items)
            from towr.domain.pc_npc_weapon_inventory import npc_inventory_attack_ids
            expected=replace(expected,wields_weapon=held,
                available_attack_ids=npc_inventory_attack_ids(old.definition,inventory))
        if old.definition.id=='pc-book-npc:night_goblin_net_spear':
            from towr.domain.pc_net_models import expected_pc_npc_net_equipment
            expected=expected_pc_npc_net_equipment(state,target)
        if enemy.state.weapon_inventory is None and any(item.owner_id==target and item.ground is not None
                for item in getattr(state,'briarroot_dropped_weapons',())):
            expected=replace(expected,wields_weapon=False,available_attack_ids=())
        if target in acknowledged:
            expected=replace(expected,wields_weapon=False,available_attack_ids=())
        # This owner authenticates the equipment/availability consequences of
        # defeat, Net, Shield and mount receipts. The common inventory has its
        # own source/history validator in PcMeleeState; Reload progress and
        # physical item transitions must not be reclassified as a fleeing drop
        # merely because they add/change this independent runtime field.
        from towr.domain.tool_inventory_models import ToolInventoryState
        equipment=replace(enemy.state,injury=old.state.injury,weapon_inventory=None,tool_inventory=ToolInventoryState())
        if equipment!=replace(expected,weapon_inventory=None,tool_inventory=ToolInventoryState()):
            raise ValueError('PC owner changed NPC equipment outside the actual fleeing weapon drop')
