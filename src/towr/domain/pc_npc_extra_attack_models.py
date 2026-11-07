"""Explicit Bear policy projected from its actual completed first Attack."""
from towr.domain.attack_models import AttackOutcome
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.turn_models import (
    ENDURING_STRENGTH_RULE_ID, ActionSlotGrant, CombatActionDeclaration,
    CombatActionKind, CombatActionSlotRequest, EnduringStrengthGrant,
)


def build_pc_npc_extra_attack_slot(state) -> CombatActionSlotRequest | None:
    """The PC owner replays the full history before accepting this projection."""
    from towr.domain.pc_melee_result_models import PcAttackProof, pc_melee_action_id

    turn = state.round_state.active_turn
    if (turn is None or len(turn.action_slots) != 1 or not turn.action_slots[0].executed
            or turn.action_slots[0].declaration.kind is not CombatActionKind.ATTACK
            or turn.actor_id not in state.source.npc_extra_attack_actor_ids):
        return None
    if state.pending or state.pending_wound is not None:
        raise ValueError('Enduring Strength must wait for all first Attack consequences')
    enemy = state.enemy(turn.actor_id)
    validate_pc_book_npc_definition(enemy.definition)
    if enemy.definition.id=='pc-book-npc:great_stag':
        from towr.domain.pc_crown_models import build_pc_crown_slot
        return build_pc_crown_slot(state)
    if enemy.definition.id not in ('pc-book-npc:bear_sweeping_claws','pc-book-npc:bear_crushing_weight'):
        raise ValueError('Enduring Strength requires its canonical Bear source')
    first = next((proof for proof in reversed(state.history)
        if type(proof) is PcAttackProof
        and proof.execution.slot.execution == turn.action_slots[0].execution), None)
    if first is None:
        raise ValueError('Enduring Strength requires the actual first Attack in this journal')
    if first.execution.resolution.attack.outcome is not AttackOutcome.HIT:
        return None
    target = next((actor for actor in state.source.enemy_target_priority
        if actor != first.request.target_id and not state.participant(actor).injury.dead), None)
    if target is None:
        return None
    receipt = turn.action_slots[0].execution
    if (first.request.actor_id != turn.actor_id or first.execution.slot_index != 1
            or receipt.round_number != state.round_state.round_number):
        raise ValueError('Enduring Strength cannot use a detached first Attack')
    request_id = pc_melee_action_id(state, turn.actor_id) + ':attack2:reserve'
    grant = EnduringStrengthGrant(turn.actor_id, state.round_state.round_number,
        request_id, receipt, first.request.target_id, target)
    return CombatActionSlotRequest(request_id, state.round_state, turn.actor_id,
        CombatActionDeclaration(CombatActionKind.ATTACK), ActionSlotGrant.ABILITY,
        ENDURING_STRENGTH_RULE_ID, enduring_strength=grant)
