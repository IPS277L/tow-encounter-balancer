"""Duellist Blades' two-Attack plan, from real item and first action (GM83).

This owner never rolls, grants Fate, changes equipment or asks the tactical
selector again. The first ordinary Attack declares Grim; only its completed
receipt can grant one further Attack with that same physical unit.
"""
from towr.domain.injury_models import injury_is_defeated
from dataclasses import replace

from towr.domain.condition_models import Condition
from towr.domain.turn_models import (
    DUELLIST_BLADES_RULE_ID, ActionSlotGrant, CombatActionDeclaration,
    CombatActionKind, CombatActionSlotRequest, DuellistBladesGrant,
)
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_quality_preparation import DUELLIST_GRIM_RULE_ID
from towr.domain.weapon_use_models import WeaponUse


def _current_use(state, actor):
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_weapon_inventory import pc_attack_weapon_use
        return pc_attack_weapon_use(state, actor)
    from towr.domain.pc_npc_weapon_inventory import npc_attack_weapon_use
    return npc_attack_weapon_use(state, actor)


def _ready_actor(state, actor):
    if actor in state.source.pc_activation_order:
        injury = state.participant(actor).injury
        return not injury.dead and not injury.conditions.has(Condition.DEFENCELESS)
    enemy = state.enemy(actor)
    return (not injury_is_defeated(enemy.state.injury) and actor not in state.exited_npc_ids
        and not enemy.state.injury.conditions.has(Condition.DEFENCELESS))


def duellist_action_index(state, use: WeaponUse | None) -> int | None:
    """Fixed Grim→Glorious plan before each genuinely selected Attack Test.

    An as-yet-unreserved first Attack is also preparable by tactical advice.
    After the first is executed, only the actual distinct grant authorizes two.
    """
    if use is None:
        return None
    if type(use) is not WeaponUse:
        raise TypeError('Duellist quality requires its exact actual WeaponUse')
    replace(use)
    if use.kind is not WeaponKind.DUELLIST_BLADES:
        return None
    turn = state.round_state.active_turn
    if turn is None or turn.actor_id != use.actor_id:
        return None
    if not turn.action_slots:
        return 1
    if (len(turn.action_slots) == 1 and not turn.action_slots[0].executed
            and turn.action_slots[0].grant is ActionSlotGrant.STANDARD
            and turn.action_slots[0].declaration.kind is CombatActionKind.ATTACK):
        return 1
    if len(turn.action_slots) != 2 or turn.action_slots[1].executed:
        return None
    grant = turn.action_slots[1].duellist_blades
    if grant is None:
        return None
    replace(grant)
    if (use.primary_item_id != grant.weapon_use.primary_item_id
            or use.primary.source != grant.weapon_use.primary.source):
        raise ValueError('the second Duellist Attack cannot change its physical unit')
    return 2


def build_pc_duellist_second_action(state) -> CombatActionSlotRequest | None:
    """Project slot2 after all first-Attack consequences, with no third action."""
    from towr.domain.pc_melee_result_models import PcAttackProof, pc_melee_action_id
    from towr.domain.pc_battlefield_movement_models import pc_battlefield_attack_available

    turn = state.round_state.active_turn
    if (turn is None or len(turn.action_slots) != 1
            or not turn.action_slots[0].executed
            or turn.action_slots[0].declaration.kind is not CombatActionKind.ATTACK):
        return None
    if state.pending or state.pending_wound is not None or state.magic_pending is not None:
        return None
    actor = turn.actor_id
    if not _ready_actor(state, actor):
        return None
    receipt = turn.action_slots[0].execution
    first = next((proof for proof in reversed(state.history)
        if type(proof) is PcAttackProof and proof.execution.slot.execution == receipt), None)
    if first is None:
        # Other executors may legitimately have used slot1, but a forged
        # journal cannot supply Duellist authority merely through its clock.
        return None
    intent = first.weapon_intent
    use = None if intent is None else intent.attack_use
    if use is None or use.kind is not WeaponKind.DUELLIST_BLADES:
        return None
    replace(use)
    if (first.request.actor_id != actor or first.execution.slot_index != 1
            or receipt.round_number != state.round_state.round_number):
        raise ValueError('Duellist first Attack is detached from its actual actor or round')
    if not any(modifier.rule_id == DUELLIST_GRIM_RULE_ID
            for modifier in first.request.kernel_request.attack.attacker_test.quality_modifiers):
        raise ValueError('Duellist second Attack lacks its declared first-Grim plan')
    current = _current_use(state, actor)
    if (current is None or current.kind is not WeaponKind.DUELLIST_BLADES
            or current.primary_item_id != use.primary_item_id
            or current.primary.source != use.primary.source):
        return None
    from towr.domain.pc_battlefield_movement_models import _enemies
    targets = _enemies(state,actor)
    # Defenceless is a legitimate Attack target; it only prevents the source
    # actor from taking this optional action, not being attacked by its enemy.
    target = next((target for target in targets
        if (not state.participant(target).injury.dead
            if target in state.source.pc_activation_order else
            not injury_is_defeated(state.enemy(target).state.injury) and target not in state.exited_npc_ids)
        and pc_battlefield_attack_available(state, actor, target)), None)
    if target is None:
        return None
    identifier = pc_melee_action_id(state, actor) + ':attack2:reserve'
    grant = DuellistBladesGrant(actor, state.round_state.round_number,
        identifier, receipt, use, target)
    return CombatActionSlotRequest(identifier, state.round_state, actor,
        CombatActionDeclaration(CombatActionKind.ATTACK), ActionSlotGrant.ABILITY,
        DUELLIST_BLADES_RULE_ID, duellist_blades=grant)
