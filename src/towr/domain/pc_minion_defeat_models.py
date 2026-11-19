"""Source-bound Goblin fleeing defeat and its one mandatory weapon drop."""
from dataclasses import replace

from towr.domain.injury_models import MinionStaggerDefeatCause,MinionStaggerDefeatResult
from towr.domain.pc_npc_ability_models import pc_npc_stagger_defeat_spec


def validate_pc_minion_defeat_equipment(state) -> None:
    # Old scenes retain the existing fixed-equipment path without a history scan.
    routed={}
    acknowledged=set()
    if any(enemy.definition.id in ('pc-book-npc:goblin_warrior_spear',
            'pc-book-npc:night_goblin_spear','pc-book-npc:night_goblin_net_spear') for enemy in state.source.enemies):
        from towr.domain.pc_melee_result_models import PcAttackProof,PcMinionStaggerDefeatProof
        from towr.domain.pc_demigryph_models import PcDemigryphStrikeProof,pc_kernel_resolution
        from towr.domain.pc_warped_form_models import PcWarpedFormTargetProof,PcWarpedFormMinionDefeatProof
        for proof in state.history:
            if type(proof) is PcWarpedFormTargetProof and proof.result.minion_stagger_defeat is not None:
                defeat=proof.result.minion_stagger_defeat
                target=proof.request.target_id
                spec=pc_npc_stagger_defeat_spec(state.source.enemy(target).definition)
                expected=MinionStaggerDefeatCause(proof.request.id+':minion-stagger-defeat',target,spec.rule_id)
                if defeat.cause!=expected or target in routed or proof.request.minion_stagger_defeat!=spec:
                    raise ValueError('fleeing defeat changed its actual wave target or rule')
                routed[target]=defeat
            elif type(proof) is PcWarpedFormMinionDefeatProof:
                target=proof.target_id
                if target in acknowledged or target not in routed:
                    raise ValueError('wave fleeing drop lacks its actual defeat')
                if routed[target].request_id!=proof.activation_id+':target:'+target+':minion-stagger-defeat':
                    raise ValueError('wave fleeing drop changed its activation source')
                acknowledged.add(target)
            if type(proof) in (PcAttackProof,PcDemigryphStrikeProof) and pc_kernel_resolution(proof).minion_stagger_defeat is not None:
                defeat=pc_kernel_resolution(proof).minion_stagger_defeat
                if type(defeat) is not MinionStaggerDefeatResult:
                    raise TypeError('fleeing defeat requires its exact result')
                replace(defeat)
                target=proof.request.target_id
                if target not in state.source.enemy_activation_order:
                    raise ValueError('fleeing defeat requires an actual NPC target')
                spec=pc_npc_stagger_defeat_spec(state.source.enemy(target).definition)
                if spec is None:
                    raise ValueError('fleeing defeat requires the actual Dirty Coward profile')
                expected=MinionStaggerDefeatCause(proof.request.kernel_request.id+':minion-stagger-defeat',
                    target,spec.rule_id)
                if (defeat.cause!=expected or target in routed
                        or proof.request.kernel_request.minion_stagger_defeat!=spec):
                    raise ValueError('fleeing defeat changed its actual Attack/target/rule or repeated an existing defeat')
                routed[target]=defeat
            elif type(proof) is PcMinionStaggerDefeatProof:
                if type(proof.source) is not MinionStaggerDefeatCause:
                    raise TypeError('weapon-drop acknowledgement requires its typed fleeing cause')
                replace(proof.source)
                target=proof.source.target_id
                if target in acknowledged or target not in routed or routed[target].cause!=proof.source:
                    raise ValueError('fleeing weapon drop is detached, duplicated or precedes its actual defeat')
                acknowledged.add(target)
    for enemy,old in zip(state.enemies,state.source.enemies,strict=True):
        target=enemy.state.actor_id
        defeat=routed.get(target)
        from towr.domain.injury_models import ProfileDecapitationCause
        cause=enemy.state.injury.defeat_cause
        if type(cause) is ProfileDecapitationCause:
            from towr.domain.pc_melee_result_models import PcAttackProof
            from towr.domain.pc_demigryph_models import pc_kernel_resolution
            actual=next((proof for proof in state.history if type(proof) is PcAttackProof
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
        expected=old.state
        if (old.definition.generated_components is not None
                and old.definition.generated_components.mount is not None):
            from towr.domain.pc_mount_models import pc_is_mounted,mount_source_resilience_bonus
            if not pc_is_mounted(state,target):
                components=old.definition.generated_components
                expected=replace(expected,current_resilience=replace(expected.current_resilience,
                    bonus=expected.current_resilience.bonus-mount_source_resilience_bonus(components.mount)
                        -int(components.armour.barding)))
        if old.definition.generated_components is not None:
            from towr.domain.pc_npc_shield_models import NpcShieldLocation
            shield=next((item for item in state.npc_shields if item.actor_id==target),None)
            if shield is not None:
                held=shield.location is NpcShieldLocation.HELD
                expected=replace(expected,holds_shield=held,current_resilience=replace(
                    expected.current_resilience,bonus=expected.current_resilience.bonus
                        -int(old.state.holds_shield)+int(held)))
            from towr.domain.armour_models import armour_is_worn
            expected=replace(expected,current_resilience=replace(expected.current_resilience,
                armoured=True if expected.current_resilience.bonus==0
                    and armour_is_worn(old.definition.generated_components.armour) else None))
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
        equipment=replace(enemy.state,injury=old.state.injury,weapon_inventory=None)
        if equipment!=replace(expected,weapon_inventory=None):
            raise ValueError('PC owner changed NPC equipment outside the actual fleeing weapon drop')
