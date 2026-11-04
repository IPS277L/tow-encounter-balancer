"""Closed body facts and deterministic hand choices for the M12 battle owner."""
from dataclasses import dataclass, replace
from enum import Enum

from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundConditionEffect, WoundEffectDuration, WoundRestriction, WoundRestrictionEffect
from towr.domain.pc_melee_models import PcWeaponHand, PcTwoHandedGrip


class PcBodyFactKind(str, Enum):
    INJURED_HAND = 'injured_hand'
    UNUSABLE_ARM = 'unusable_arm'
    LOST_ARM = 'lost_arm'
    LOST_LEG = 'lost_leg'
    LOST_EYE = 'lost_eye'
    LOST_FINGER = 'lost_finger'
    LOST_TEETH = 'lost_teeth'
    CLUTCH_STOMACH = 'clutch_stomach'


@dataclass(frozen=True, slots=True)
class PcBodyFact:
    kind: PcBodyFactKind
    wound_sequence: int
    side: PcWeaponHand | None
    count: int = 1

    def __post_init__(self):
        if type(self.kind) is not PcBodyFactKind or type(self.wound_sequence) is not int or self.wound_sequence < 1:
            raise TypeError('body fact requires its typed kind and positive Wound sequence')
        if type(self.count) is not int or self.count < 1:
            raise TypeError('body fact requires a positive integer count')
        if self.kind is PcBodyFactKind.LOST_TEETH:
            if self.side is not None or self.count > 10:
                raise ValueError('teeth loss retains one actual d10 and no side')
        elif type(self.side) is not PcWeaponHand or self.count != 1:
            raise TypeError('sided anatomical fact requires one actual typed side')


def has_ongoing_condition(injury, condition):
    return any(isinstance(effect,WoundConditionEffect) and effect.condition is condition
        and effect.duration in (WoundEffectDuration.UNTIL_TREATED,WoundEffectDuration.UNTIL_HEALED,WoundEffectDuration.PERMANENT)
        for effect in injury.active_wound_effects)


def restriction_sources(injury, restriction):
    return tuple(effect.wound_sequence for effect in injury.active_wound_effects
        if isinstance(effect,WoundRestrictionEffect) and effect.restriction is restriction)


def available_sides(member, excluded_kinds):
    blocked = {fact.side for fact in member.body_facts if fact.kind in excluded_kinds}
    return tuple(side for side in PcWeaponHand if side not in blocked)


def usable_hands(member):
    return available_sides(member,(PcBodyFactKind.UNUSABLE_ARM,PcBodyFactKind.LOST_ARM,PcBodyFactKind.CLUTCH_STOMACH))


def injured_hands(member):
    active = restriction_sources(member.injury,WoundRestriction.USING_INJURED_HAND_CAUSES_CRITICAL)
    return {fact.side for fact in member.body_facts if fact.kind is PcBodyFactKind.INJURED_HAND and fact.wound_sequence in active}


def preferred_weapon_hand(member, initial_hand):
    usable = usable_hands(member)
    if initial_hand is PcTwoHandedGrip.BOTH:
        return initial_hand if len(usable) == 2 else None
    if member.weapon_hand in usable and member.weapon_hand not in injured_hands(member):
        return member.weapon_hand
    preferred = (initial_hand,*(side for side in PcWeaponHand if side is not initial_hand))
    return next((side for side in preferred if side in usable and side not in injured_hands(member)),
        next((side for side in preferred if side in usable),None))


def usable_weapon_hand(member):
    if member.weapon_hand is PcTwoHandedGrip.BOTH:
        return member.weapon_hand if len(usable_hands(member)) == 2 else None
    return member.weapon_hand if member.weapon_hand in usable_hands(member) else None


def add_critical(injury, sequences):
    effects = list(injury.active_wound_effects)
    for sequence in sequences:
        effect = WoundConditionEffect(sequence,Condition.CRITICALLY_INJURED,WoundEffectDuration.UNTIL_TREATED)
        if effect not in effects:
            effects.append(effect)
    return replace(injury,active_wound_effects=tuple(effects),conditions=(
        injury.conditions.with_condition(Condition.CRITICALLY_INJURED) if sequences else injury.conditions))


def critical_for_hand(member, hand):
    if hand is None:
        return member.injury
    sequences = tuple(fact.wound_sequence for fact in member.body_facts
        if fact.kind is PcBodyFactKind.INJURED_HAND
        and (hand is PcTwoHandedGrip.BOTH or fact.side is hand)
        and fact.wound_sequence in restriction_sources(member.injury,WoundRestriction.USING_INJURED_HAND_CAUSES_CRITICAL))
    return add_critical(member.injury,sequences)


def critical_for_action(member, action, *, removes_prone=False, used_hand=None):
    from towr.domain.turn_models import CombatActionKind
    sequences = list(restriction_sources(member.injury,WoundRestriction.NON_FACE_PROTECTION_ACTION_CAUSES_CRITICAL))
    if action is not CombatActionKind.RECOVER:
        sequences.extend(restriction_sources(member.injury,WoundRestriction.NON_RECOVER_ACTION_CAUSES_CRITICAL))
    if removes_prone:
        sequences.extend(restriction_sources(member.injury,WoundRestriction.REMOVING_PRONE_CAUSES_CRITICAL))
    injury = add_critical(member.injury,sequences)
    return critical_for_hand(replace(member,injury=injury),used_hand)


def critical_for_incidental_hand_use(member, hand):
    """A chosen swap/clutch is a free action, unlike an involuntary drop.

    None marks a confirmed incidental action rather than one of the six
    CombatActionKind values; it is neither Recover nor face protection.
    """
    return critical_for_action(member,None,used_hand=hand)
