"""Canonical projections for the finite Warped Form end phase."""
from dataclasses import replace

from towr.domain.pc_warped_form_models import (
    PcWarpedFormActivationProof, PcWarpedFormTargetProof, PcWarpedFormProfileProof,
    PcWarpedFormMinionDefeatProof, PcWarpedFormEndProof, current_warped_form,
    expected_pc_warped_form_activation, next_warped_form_target, canonical_warped_form_impact,
)

WARPED_PROOFS = (PcWarpedFormActivationProof, PcWarpedFormTargetProof, PcWarpedFormProfileProof,
    PcWarpedFormMinionDefeatProof, PcWarpedFormEndProof)


def project_warped_form_step(state, proof):
    from towr.domain.pc_melee_result_models import _enemy_update, _party_update, validate_pc_melee_source_types
    from towr.domain.pc_npc_wound_models import (official_profile_wound_state,
        elf_merchant_profile_wound_state, pc_npc_drained_profile_wound_state, pc_npc_prone_profile_wound_state)
    from towr.domain.pc_npc_distraction_models import wave_distraction_from_profile_wound, ordered_npc_distractions
    from towr.domain.condition_models import Condition

    def same(actual, expected):
        if actual != expected:
            raise ValueError('Warped Form changed its actual phase, target, rule or consequence')
        validate_pc_melee_source_types(actual, expected)

    def finish(**updates):
        pending = updates.get('pending', state.pending)
        wound = updates.get('pending_wound', state.pending_wound)
        if not pending and wound is None:
            updates['pending_actor_id'] = None
        return replace(state, history=(*state.history, proof), **updates)

    replace(proof)
    activation = current_warped_form(state)
    if type(proof) is PcWarpedFormActivationProof:
        expected = expected_pc_warped_form_activation(state)
        if activation is not None or expected is None:
            raise ValueError('no available own end phase permits Warped Form')
        same(proof, expected)
        return finish(enemies=_enemy_update(state, proof.actor_id, proof.injury))
    if activation is None or proof.activation_id != activation.activation_id:
        raise ValueError('wave continuation lacks its actual open activation')
    if type(proof) is PcWarpedFormTargetProof:
        expected = next_warped_form_target(state)
        if expected is None:
            raise ValueError('wave cannot skip pending work or invent another target')
        same(proof.request, expected)
        canonical = canonical_warped_form_impact(expected, proof.result)
        same(proof.result, canonical)
        target = expected.target_id
        changes = dict(pending=canonical.follow_ups, pending_wound=canonical.pending_character_wound,
            pending_actor_id=target if canonical.follow_ups or canonical.pending_character_wound is not None else None)
        if target in state.source.pc_activation_order:
            changes['party'] = _party_update(state, target, injury=canonical.state)
        else:
            changes['enemies'] = _enemy_update(state, target, canonical.state)
        return finish(**changes)
    if type(proof) is PcWarpedFormEndProof:
        if state.pending or state.pending_wound is not None or next_warped_form_target(state) is not None:
            raise ValueError('wave end cannot omit targets or their mandatory continuations')
        return finish()
    # These acknowledgements bind the actual immediately preceding wave target,
    # not the last ordinary PC Attack somewhere earlier in the journal.
    target_proof = next(p for p in reversed(state.history) if type(p) is PcWarpedFormTargetProof)
    same((proof.activation_id, proof.target_id), (target_proof.activation_id, target_proof.request.target_id))
    if state.pending_wound is not None or not state.pending or state.pending_actor_id != proof.target_id:
        raise ValueError('wave NPC ACK lacks its target-scoped pending queue')
    target = proof.target_id
    combat = state.round_state
    if type(proof) is PcWarpedFormMinionDefeatProof:
        defeat = target_proof.result.minion_stagger_defeat
        if defeat is None:
            raise ValueError('wave fleeing ACK lacks its actual Dirty Coward result')
        same(state.pending, (defeat.cause,))
        enemy = state.enemy(target)
        dropped = replace(enemy, state=replace(enemy.state, wields_weapon=False, available_attack_ids=()))
        enemies = tuple(dropped if e.state.actor_id == target else e for e in state.enemies)
        return finish(enemies=enemies, pending=(), round_state=_exclude(combat, target))
    if type(proof) is not PcWarpedFormProfileProof or target_proof.result.profile_wound is None:
        raise ValueError('wave profile ACK lacks its actual Wound')
    same(proof.source, target_proof.result.profile_wound.state_change)
    same(state.pending, (proof.source,))
    same(state.enemy(target).state.injury, target_proof.result.profile_wound.state)
    if proof.source.defeated:
        policy = next(p for p in state.source.npc_warped_form_policies if p.actor_id == activation.actor_id)
        decision = next(d for d in policy.npc_defeat_decisions if d.target_id == target)
        same(proof.decision, decision)
        return finish(pending=(), round_state=_exclude(combat, target))
    if proof.decision is not None:
        raise ValueError('living wave target cannot receive a defeat disposition')
    enemy = state.enemy(target)
    injury = enemy.state.injury
    for apply in (official_profile_wound_state, elf_merchant_profile_wound_state,
            pc_npc_drained_profile_wound_state, pc_npc_prone_profile_wound_state):
        injury = apply(enemy.definition, injury, proof.source)
    cause = wave_distraction_from_profile_wound(state.source, activation, proof)
    distractions = state.npc_distractions
    if cause is not None:
        injury = replace(injury, conditions=injury.conditions.with_condition(Condition.DISTRACTED))
        distractions = ordered_npc_distractions(state.source, (*distractions, cause))
    return finish(pending=(), enemies=_enemy_update(state, target, injury), npc_distractions=distractions)


def _exclude(combat, actor):
    if actor in (*combat.completed_turn_entity_ids, *combat.excluded_turn_entity_ids):
        return combat
    return replace(combat, excluded_turn_entity_ids=(*combat.excluded_turn_entity_ids, actor))
