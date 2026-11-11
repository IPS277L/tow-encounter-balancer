"""Fixed fallback from an unusable two-handed grip or unreloadable ranged weapon."""
from __future__ import annotations

from typing import TYPE_CHECKING
from dataclasses import replace

from towr.domain.condition_models import Condition
from towr.domain.pc_heavy_wound_models import preferred_weapon_hand, usable_hands
from towr.domain.pc_melee_models import PC_TWO_HANDED_RANGED_WEAPONS, PcMeleeWeapon, PcWeaponHand, PcTwoHandedGrip

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


def pc_backup_candidate_hand(state: PcMeleeState, actor_id: str) -> PcWeaponHand | None:
    """Own-turn backup intent before a weapon-first shield release, if needed."""
    turn = state.round_state.active_turn
    participant = state.source.participant(actor_id)
    member = state.participant(actor_id)
    policy = participant.backup_weapon_policy
    if (policy is None or member.using_backup_weapon or member.injury.dead
            or member.injury.conditions.has(Condition.DEFENCELESS)
            or state.pending or state.pending_wound is not None
            or turn is None or turn.actor_id != actor_id or turn.action_slots
            or not state.live_enemies or not usable_hands(member)):
        return None
    from towr.domain.pc_melee_models import PC_RANGED_WEAPONS
    from towr.domain.pc_weapon_models import pc_weapon_allows_close_shooting
    if participant.pc.weapon in PC_RANGED_WEAPONS and not pc_weapon_allows_close_shooting(participant.pc.weapon):
        from towr.domain.pc_short_opening_models import pc_has_close_enemy
        if not pc_has_close_enemy(state,actor_id) and (
                participant.pc.weapon not in PC_TWO_HANDED_RANGED_WEAPONS or len(usable_hands(member)) == 2):
            return None
    elif len(usable_hands(member)) != 1:
        return None
    elif participant.pc.ranged is not None:
        if member.ranged is None or member.ranged.loaded:
            return None
    else:
        from towr.domain.pc_weapon_models import pc_weapon_requires_two_hands
        if not pc_weapon_requires_two_hands(participant.pc.weapon):
            return None
    # The carried weapon has no held hand yet: a healthy primary hand must not
    # silently override the caller's explicit backup preference.
    return preferred_weapon_hand(replace(member,weapon_hand=None),policy.preferred_hand)


def pc_backup_draw_hand(state: PcMeleeState, actor_id: str) -> PcWeaponHand | None:
    hand = pc_backup_candidate_hand(state,actor_id)
    if hand is None:
        return None
    member = state.participant(actor_id)
    from towr.domain.pc_shield_models import PcShieldLocation
    if (member.shield is not None and member.shield.location is PcShieldLocation.HELD
            and member.shield.hand is hand):
        return None  # The existing weapon-first shield receipt must happen first.
    return hand
