"""Fixed optional replacement of an unusable two-handed primary weapon."""
from __future__ import annotations

from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition
from towr.domain.pc_heavy_wound_models import preferred_weapon_hand, usable_hands
from towr.domain.pc_melee_models import PcMeleeWeapon, PcWeaponHand, PcTwoHandedGrip

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcMeleeState


def pc_active_weapon(state: PcMeleeState, actor_id: str) -> PcMeleeWeapon:
    participant = state.source.participant(actor_id)
    return (participant.backup_weapon_policy.weapon if state.participant(actor_id).using_backup_weapon
        else participant.pc.weapon)


def pc_preferred_weapon_hand(state: PcMeleeState, actor_id: str) -> PcWeaponHand | PcTwoHandedGrip | None:
    participant = state.source.participant(actor_id)
    initial = (participant.backup_weapon_policy.preferred_hand if state.participant(actor_id).using_backup_weapon
        else participant.initial_weapon_hand)
    return preferred_weapon_hand(state.participant(actor_id),initial)


def pc_active_weapon_item_id(state: PcMeleeState, actor_id: str) -> str:
    return actor_id + (':backup-weapon' if state.participant(actor_id).using_backup_weapon else ':weapon')


def pc_backup_draw_hand(state: PcMeleeState, actor_id: str) -> PcWeaponHand | None:
    """Select only the actual own unreserved incidental draw, after immediate Wound work."""
    turn = state.round_state.active_turn
    participant = state.source.participant(actor_id)
    member = state.participant(actor_id)
    policy = participant.backup_weapon_policy
    if (policy is None or member.using_backup_weapon or member.injury.dead
            or member.injury.conditions.has(Condition.DEFENCELESS)
            or state.pending or state.pending_wound is not None
            or turn is None or turn.actor_id != actor_id or turn.action_slots
            or len(usable_hands(member)) != 1):
        return None
    return preferred_weapon_hand(member,policy.preferred_hand)
