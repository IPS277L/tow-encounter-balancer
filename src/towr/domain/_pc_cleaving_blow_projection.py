"""Canonical native transitions for the ordered Cleaving Blow wave."""
from dataclasses import replace

from towr.domain.pc_cleaving_blow_models import (
    PcCleavingStartProof,PcCleavingTargetProof,PcCleavingProfileProof,
    PcCleavingMinionDefeatProof,PcCleavingEndProof,current_cleaving_wave,
    expected_cleaving_start,next_cleaving_target,cleaving_pending_npc_target,
    cleaving_profile_decision,cleaving_wave_receipt,
)


def project_cleaving_step(state,proof):
    from towr.domain.pc_melee_result_models import _party_update,validate_pc_melee_source_types
    from towr.domain.pc_actor_models import pc_actor_npc_snapshot,pc_actor_npc_update,pc_companion
    from towr.domain.pc_warped_form_models import canonical_warped_form_impact
    from towr.domain._pc_warped_form_projection import _exclude

    def same(actual,expected):
        if actual != expected:
            raise ValueError('Cleaving Blow changed its actual source, target or result')
        validate_pc_melee_source_types(actual,expected)

    def finish(**updates):
        from towr.domain.pc_weighted_net_models import weighted_nets_after_equipment
        updates=weighted_nets_after_equipment(state,proof,updates)
        if not updates.get('pending',state.pending) and updates.get('pending_wound',state.pending_wound) is None:
            updates['pending_actor_id']=None
        return replace(state,history=(*state.history,proof),**updates)

    replace(proof)
    if type(proof) is PcCleavingStartProof:
        expected=expected_cleaving_start(state)
        if expected is None: raise ValueError('no actual unused weapon Wound permits Cleaving Blow')
        same(proof,expected)
        return finish()
    wave=current_cleaving_wave(state)
    if wave is None or proof.wave_id != wave.wave_id:
        raise ValueError('Cleaving continuation requires its unique actual wave')
    if type(proof) is PcCleavingTargetProof:
        request=next_cleaving_target(state)
        if request is None: raise ValueError('Cleaving cannot skip mandatory work or invent another target')
        same(proof.request,request)
        result=canonical_warped_form_impact(request,proof.result)
        same(proof.result,result)
        actor=request.target_id
        updates=dict(pending=result.follow_ups,pending_wound=result.pending_character_wound,
            pending_actor_id=actor if result.follow_ups or result.pending_character_wound is not None else None)
        if actor in state.source.pc_activation_order:
            updates['party']=_party_update(state,actor,injury=result.state)
        else: updates.update(pc_actor_npc_update(state,actor,injury=result.state))
        return finish(**updates)
    if type(proof) is PcCleavingEndProof:
        if state.pending or state.pending_wound is not None or next_cleaving_target(state) is not None:
            raise ValueError('Cleaving completion cannot omit a target or injury lifecycle')
        return finish()
    target=cleaving_pending_npc_target(state)
    if target is None: raise ValueError('Cleaving NPC acknowledgement has no actual pending target')
    cleaving_wave_receipt(state.history,proof)
    actor=proof.target_id
    if type(proof) is PcCleavingMinionDefeatProof:
        same(state.pending,(proof.source,))
        same(pc_actor_npc_snapshot(state,actor).state.injury,target.result.state)
        enemy=pc_actor_npc_snapshot(state,actor)
        dropped=replace(enemy,state=replace(enemy.state,wields_weapon=False,available_attack_ids=()))
        return finish(**pc_actor_npc_update(state,actor,snapshot=dropped),pending=(),
            round_state=_exclude(state.round_state,actor))
    if type(proof) is not PcCleavingProfileProof or target.result.profile_wound is None:
        raise ValueError('Cleaving profile acknowledgement omitted its real Wound')
    same(proof.decision,cleaving_profile_decision(state,target))
    same(state.pending,(proof.source,))
    same(pc_actor_npc_snapshot(state,actor).state.injury,target.result.profile_wound.state)
    updates=dict(pending=(),round_state=_exclude(state.round_state,actor)
        if proof.source.defeated else state.round_state)
    if pc_companion(state,actor) is not None:
        from towr.domain.pc_companion_effect_models import companion_profile_wound_injury
        updates.update(pc_actor_npc_update(state,actor,
            injury=companion_profile_wound_injury(state,actor,proof.source)))
    elif not proof.source.defeated:
        from towr.domain.pc_npc_wound_models import (official_profile_wound_state,
            elf_merchant_profile_wound_state,pc_npc_drained_profile_wound_state,pc_npc_prone_profile_wound_state)
        enemy=pc_actor_npc_snapshot(state,actor)
        injury=enemy.state.injury
        for apply in (official_profile_wound_state,elf_merchant_profile_wound_state,
                pc_npc_drained_profile_wound_state,pc_npc_prone_profile_wound_state):
            injury=apply(enemy.definition,injury,proof.source)
        from towr.domain.pc_npc_distraction_models import cleaving_distraction_from_profile_wound,ordered_npc_distractions
        from towr.domain.condition_models import Condition
        cause=cleaving_distraction_from_profile_wound(state.source,wave,proof)
        if cause is not None:
            injury=replace(injury,conditions=injury.conditions.with_condition(Condition.DISTRACTED))
            updates['npc_distractions']=ordered_npc_distractions(state.source,(*state.npc_distractions,cause))
        updates.update(pc_actor_npc_update(state,actor,injury=injury))
    return finish(**updates)
