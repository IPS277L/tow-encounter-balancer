"""Actual one-handed shield equipment and the fixed M53 fighting policy."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import TYPE_CHECKING

from towr.domain.attack_models import ResilienceProfile
from towr.domain.condition_models import Condition
from towr.domain.pc_heavy_wound_models import injured_hands, usable_hands, usable_weapon_hand
from towr.domain.pc_melee_models import PcShieldLoadout, PcTwoHandedGrip, PcWeaponHand
from towr.domain.test_models import Skill

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcMeleeParticipantState, PcMeleeState


class PcShieldLocation(str, Enum):
    HELD = 'held'
    DROPPED = 'dropped'
    UNAVAILABLE = 'unavailable'


@dataclass(frozen=True, slots=True)
class PcShieldState:
    location: PcShieldLocation
    hand: PcWeaponHand | None

    def __post_init__(self):
        if type(self.location) is not PcShieldLocation:
            raise TypeError('shield location requires its exact typed value')
        if self.location is PcShieldLocation.DROPPED:
            if self.hand is not None:
                raise ValueError('a dropped shield has no held hand')
        elif type(self.hand) is not PcWeaponHand:
            raise TypeError('held/unavailable shield retains its actual typed hand')


@dataclass(frozen=True, slots=True)
class PcShieldReleaseProof:
    actor_id: str
    action_id: str
    hand: PcWeaponHand

    def __post_init__(self):
        if any(type(value) is not str or not value.strip() for value in (self.actor_id,self.action_id)):
            raise TypeError('shield release requires exact nonempty source IDs')
        if type(self.hand) is not PcWeaponHand:
            raise TypeError('shield release requires its actual typed hand')


def initial_pc_shield(loadout: PcShieldLoadout | None) -> PcShieldState | None:
    if loadout is None:
        return None
    if type(loadout) is not PcShieldLoadout:
        raise TypeError('initial shield requires its exact loadout')
    replace(loadout)
    return PcShieldState(PcShieldLocation.HELD,loadout.initial_hand)


def pc_has_working_shield(member: PcMeleeParticipantState) -> bool:
    shield = member.shield
    return (shield is not None and shield.location is PcShieldLocation.HELD
        and shield.hand in usable_hands(member)
        and member.weapon_hand not in (shield.hand,PcTwoHandedGrip.BOTH))


def pc_shield_recover_hand(member: PcMeleeParticipantState) -> PcWeaponHand | None:
    if member.shield is None or member.shield.location is not PcShieldLocation.DROPPED:
        return None
    # Keep the second hand free through the whole Exacting reload cycle,
    # including an incidental object interaction in a necessary Recover.
    if member.pistol is not None and not member.pistol.loaded:
        return None
    if member.injury.dead or member.injury.conditions.has(Condition.DEFENCELESS):
        return None
    if member.weapon_hand is PcTwoHandedGrip.BOTH:
        return None
    return next((side for side in usable_hands(member)
        if side is not member.weapon_hand and side not in injured_hands(member)),None)


def pc_shield_recover_needed(member: PcMeleeParticipantState) -> bool:
    return usable_weapon_hand(member) is not None and pc_shield_recover_hand(member) is not None


def pc_shield_resilience(state: PcMeleeState, actor: str) -> ResilienceProfile:
    pc = state.source.participant(actor).pc
    return ResilienceProfile(pc.toughness,pc.armour_bonus+int(pc_has_working_shield(state.participant(actor))))


def pc_defence_hand(member: PcMeleeParticipantState, attack_skill: Skill) -> PcWeaponHand | PcTwoHandedGrip | None:
    if attack_skill is Skill.THROWING:
        return member.shield.hand if pc_has_working_shield(member) else None
    if attack_skill is Skill.MELEE:
        return usable_weapon_hand(member) or (member.shield.hand if pc_has_working_shield(member) else None)
    return None


def expected_pc_shield_release(state: PcMeleeState) -> PcShieldReleaseProof | None:
    if state.pending or state.pending_wound is not None:
        return None
    turn = state.round_state.active_turn
    if turn is None or turn.actor_id not in state.source.pc_activation_order or turn.action_slots:
        return None
    actor = turn.actor_id
    member = state.participant(actor)
    if (member.injury.dead or member.injury.conditions.has(Condition.DEFENCELESS)
            or not pc_has_working_shield(member)):
        return None
    from towr.domain.pc_backup_weapon_models import pc_preferred_weapon_hand
    from towr.domain.pc_melee_result_models import pc_melee_action_id, _pc_recover_needed
    needs_weapon_hand = pc_preferred_weapon_hand(state,actor) is member.shield.hand
    needs_reload_hands = (member.pistol is not None and not member.pistol.loaded
        and len(usable_hands(member)) == 2 and usable_weapon_hand(member) is not None
        and bool(state.live_enemies) and not _pc_recover_needed(member))
    if not needs_weapon_hand and not needs_reload_hands:
        return None
    return PcShieldReleaseProof(actor,pc_melee_action_id(state,actor)+':shield:release',member.shield.hand)
