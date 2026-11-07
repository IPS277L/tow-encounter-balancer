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
            if type(proof) is PcAttackProof and proof.execution.resolution.minion_stagger_defeat is not None:
                defeat=proof.execution.resolution.minion_stagger_defeat
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
        if enemy.state.injury.defeat_cause!=(defeat.cause if defeat is not None else None):
            raise ValueError('NPC non-Wound defeat lacks its actual source Attack')
        if defeat is not None and enemy.state.injury!=defeat.state:
            raise ValueError('fleeing NPC injury changed after its actual defeat')
        expected=old.state
        if old.definition.id=='pc-book-npc:night_goblin_net_spear':
            from towr.domain.pc_net_models import expected_pc_npc_net_equipment
            expected=expected_pc_npc_net_equipment(state,target)
        if target in acknowledged:
            expected=replace(expected,wields_weapon=False,available_attack_ids=())
        if replace(enemy.state,injury=old.state.injury)!=expected:
            raise ValueError('PC owner changed NPC equipment outside the actual fleeing weapon drop')
