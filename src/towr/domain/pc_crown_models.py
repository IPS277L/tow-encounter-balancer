"""Crown of Antlers is bound to its first Attack's completed new-Prone cause."""
from towr.domain.attack_models import AttackOutcome
from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundEnduranceFailure
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.turn_models import ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest
from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleOutcome

GREAT_STAG_DEFINITION_ID = 'pc-book-npc:great_stag'


def build_pc_crown_slot(state):
    from towr.domain.pc_melee_result_models import (
        PcAttackProof, PcWoundCompletionProof, PcEnduranceProof, pc_melee_action_id, pc_melee_unsupported,
    )
    from towr.domain.turn_models import CrownOfAntlersGrant, CROWN_OF_ANTLERS_RULE_ID

    turn = state.round_state.active_turn
    if (turn is None or len(turn.action_slots)!=1 or not turn.action_slots[0].executed
            or turn.action_slots[0].declaration.kind is not CombatActionKind.ATTACK
            or turn.actor_id not in state.source.npc_extra_attack_actor_ids):
        return None
    if state.pending or state.pending_wound is not None:
        raise ValueError('Crown must wait for the complete first Attack consequences')
    if pc_melee_unsupported(state) is not None:
        return None
    enemy = state.enemy(turn.actor_id)
    validate_pc_book_npc_definition(enemy.definition)
    if enemy.definition.id!=GREAT_STAG_DEFINITION_ID:
        raise ValueError('Crown requires its canonical Great Stag')
    receipt = turn.action_slots[0].execution
    indexed = next(((index,proof) for index,proof in reversed(tuple(enumerate(state.history)))
        if type(proof) is PcAttackProof and proof.execution.slot.execution==receipt),None)
    if indexed is None:
        raise ValueError('Crown lacks the actual executed first Attack in this journal')
    index,first = indexed
    if (first.request.actor_id!=turn.actor_id or first.execution.slot_index!=1
            or receipt.round_number!=state.round_state.round_number):
        raise ValueError('Crown first Attack is detached from the active actor/round')
    target = first.request.target_id
    before = first.request.kernel_request.target_state
    if first.execution.resolution.attack.outcome is not AttackOutcome.HIT or before.conditions.has(Condition.PRONE):
        return None
    current = state.participant(target)
    if current.injury.dead or not current.injury.conditions.has(Condition.PRONE):
        return None
    pending = first.execution.resolution.pending_character_wound
    if pending is None:
        return None  # Ordinary Antlers has no direct Prone effect without Charge.
    completion = None
    completed_at = None
    for offset,proof in enumerate(state.history[index+1:],index+1):
        if (type(proof) is PcWoundCompletionProof
                and proof.completion.source_request.roll==pending):
            completion = proof.completion
            completed_at = offset
            break
    if completion is None or completion.outcome is not CharacterWoundLifecycleOutcome.ACCEPTED:
        return None
    effect = completion.wound_effect
    if effect is None:
        return None
    caused = effect.state.conditions.has(Condition.PRONE)
    if not caused:
        caused = any(type(proof) is PcEnduranceProof and proof.request in effect.follow_ups
            and proof.request.failure is WoundEnduranceFailure.FALL_PRONE
            and proof.result.request==proof.request and not proof.result.succeeded
            and proof.result.state.conditions.has(Condition.PRONE)
            for proof in state.history[completed_at+1:])
    if not caused:
        return None
    request_id = pc_melee_action_id(state,turn.actor_id)+':attack2:reserve'
    grant = CrownOfAntlersGrant(turn.actor_id,state.round_state.round_number,request_id,
        receipt,target,target,'trample')
    return CombatActionSlotRequest(request_id,state.round_state,turn.actor_id,
        CombatActionDeclaration(CombatActionKind.ATTACK),ActionSlotGrant.ABILITY,
        CROWN_OF_ANTLERS_RULE_ID,crown_of_antlers=grant)
