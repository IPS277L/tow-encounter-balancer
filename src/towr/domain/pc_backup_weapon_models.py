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
    member=state.participant(actor_id)
    item=member.weapon_inventory.active
    if item is None:
        return PcMeleeWeapon.UNARMED
    return PcMeleeWeapon(item.kind.value)


def pc_preferred_weapon_hand(state: PcMeleeState, actor_id: str) -> PcWeaponHand | PcTwoHandedGrip | None:
    participant = state.source.participant(actor_id)
    initial = (participant.backup_weapon_policy.preferred_hand if state.participant(actor_id).using_backup_weapon
        and participant.backup_weapon_policy is not None else participant.initial_weapon_hand)
    from towr.domain.pc_weapon_models import pc_weapon_supports_variable_grip,pc_weapon_requires_two_hands
    member=state.participant(actor_id)
    if (member.weapon_inventory is not None and member.weapon_inventory.active is not None
            and member.weapon_inventory.active.weapon is PcMeleeWeapon.WEIGHTED_NET
            and member.weapon_inventory.active.location.value == 'deployed'):
        return None
    weapon=pc_active_weapon(state,actor_id)
    if weapon is PcMeleeWeapon.UNARMED:
        return None
    if pc_weapon_supports_variable_grip(weapon):
        return preferred_variable_weapon_hand(member,initial)
    if pc_weapon_requires_two_hands(weapon):
        return preferred_weapon_hand(member,PcTwoHandedGrip.BOTH)
    if initial is PcTwoHandedGrip.BOTH:
        initial=(member.weapon_hand if type(member.weapon_hand) is PcWeaponHand else PcWeaponHand.LEFT)
    return preferred_weapon_hand(member,initial)


def preferred_variable_weapon_hand(member, initial_hand):
    """Use both free healthy hands, otherwise a real usable single hand.

    This is the simulator's grip preference. It never changes equipment or
    body facts; the existing source-bound hand-swap/pickup owner applies it.
    """
    from towr.domain.pc_heavy_wound_models import injured_hands
    from towr.domain.pc_shield_models import PcShieldLocation
    shield=(member.shield.hand if member.shield is not None
        and member.shield.location is PcShieldLocation.HELD else None)
    available=tuple(side for side in usable_hands(member) if side is not shield)
    healthy=tuple(side for side in available if side not in injured_hands(member))
    if len(healthy)==2:
        return PcTwoHandedGrip.BOTH
    preferred=(member.weapon_hand, initial_hand, *PcWeaponHand)
    all_healthy=tuple(side for side in usable_hands(member) if side not in injured_hands(member))
    # A healthy Shield hand may be chosen only when no free healthy hand
    # exists; the existing weapon-first release must then happen before use.
    return next((side for pool in (healthy,all_healthy,available) for side in preferred if side in pool),None)


def pc_active_weapon_item_id(state: PcMeleeState, actor_id: str) -> str:
    return state.participant(actor_id).weapon_inventory.active_item_id


def pc_backup_candidate_hand(state: PcMeleeState, actor_id: str) -> PcWeaponHand | None:
    """Own-turn backup intent before a weapon-first shield release, if needed."""
    turn = state.round_state.active_turn
    participant = state.source.participant(actor_id)
    member = state.participant(actor_id)
    from towr.domain.pc_melee_models import PcMeleePolicy
    if participant.policy is PcMeleePolicy.AUTOMATIC_COMBAT:
        return None
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
    elif participant.pc.weapon in PC_RANGED_WEAPONS:
        if member.ranged is None or member.ranged.loaded:
            return None
    else:
        from towr.domain.pc_weapon_models import pc_weapon_requires_two_hands
        if not pc_weapon_requires_two_hands(participant.pc.weapon):
            return None
    # The carried weapon has no held hand yet: a healthy primary hand must not
    # silently override the caller's explicit backup preference.
    from towr.domain.pc_heavy_wound_models import injured_hands
    order=(policy.preferred_hand,*(side for side in PcWeaponHand if side is not policy.preferred_hand))
    usable=usable_hands(member)
    injured=injured_hands(member)
    return next((side for side in order if side in usable and side not in injured),
        next((side for side in order if side in usable),None))


def pc_backup_draw_hand(state: PcMeleeState, actor_id: str) -> PcWeaponHand | None:
    hand = pc_backup_candidate_hand(state,actor_id)
    if hand is None:
        return None
    from towr.domain.pc_potion_models import selected_pc_potion
    from towr.domain.pc_melee_result_models import pc_melee_selected_action
    from towr.domain.turn_models import CombatActionKind
    if selected_pc_potion(state) is not None or (state.source.participant(actor_id).wizard is not None
            and pc_melee_selected_action(state) is CombatActionKind.IMPROVISE):
        return None
    member = state.participant(actor_id)
    from towr.domain.pc_shield_models import PcShieldLocation
    if (member.shield is not None and member.shield.location is PcShieldLocation.HELD
            and member.shield.hand is hand):
        return None  # The existing weapon-first shield receipt must happen first.
    return hand
