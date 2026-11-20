"""Shared Talent ownership and acquisition facts, PG1.4 III73–81/138–139.

These immutable facts validate acquisition, not combat admission or activation.
The caller supplies original prerequisite facts rather than temporary battle
modifiers. No XP is spent, action selected, or runtime resource refreshed here.
"""
from dataclasses import dataclass, replace
from enum import Enum

from towr.domain.talent_catalog import (
    FamiliarEffect, TalentEquipmentRequirement, TalentId, TalentLoreRequirement,
    TalentOrigin, TalentProgression, TalentSelection, TalentStatusTier,
    talent_definition,
)


class TalentAcquisitionPhase(str, Enum):
    CREATION = 'creation'
    ADVANCEMENT = 'advancement'


class TalentFunding(str, Enum):
    FREE = 'free'
    XP = 'xp'


class DeityId(str, Enum):
    ULRIC = 'ulric'
    TAAL = 'taal'
    RHYA = 'rhya'
    SIGMAR = 'sigmar'
    MANANN = 'manann'
    MORR = 'morr'
    RANALD = 'ranald'
    VERENA = 'verena'
    MYRMIDIA = 'myrmidia'
    SHALLYA = 'shallya'


def _identifier(value, label):
    if type(value) is not str or not value.strip():
        raise TypeError(label + ' requires a nonempty exact identifier')


@dataclass(frozen=True, slots=True)
class DeityChoice:
    deity: DeityId

    def __post_init__(self):
        if type(self.deity) is not DeityId:
            raise TypeError('Faith requires a typed deity')


@dataclass(frozen=True, slots=True)
class FamiliarEffectChoice:
    effect: FamiliarEffect

    def __post_init__(self):
        if type(self.effect) is not FamiliarEffect:
            raise TypeError('Familiar requires a typed additional effect')


@dataclass(frozen=True, slots=True)
class HatredGroupChoice:
    group_id: str

    def __post_init__(self):
        _identifier(self.group_id, 'Hatred group')


@dataclass(frozen=True, slots=True)
class OathChoice:
    oath_id: str

    def __post_init__(self):
        _identifier(self.oath_id, 'Honour Bound oath')


@dataclass(frozen=True, slots=True)
class BloodlineChoice:
    bloodline_id: str

    def __post_init__(self):
        _identifier(self.bloodline_id, 'Secret Bloodline')


@dataclass(frozen=True, slots=True)
class MagicLoreChoice:
    lore_id: str

    def __post_init__(self):
        _identifier(self.lore_id, 'Touched by the Winds Magic Lore')


TalentChoice = (DeityChoice | FamiliarEffectChoice | HatredGroupChoice |
    OathChoice | BloodlineChoice | MagicLoreChoice)
_CHOICE_TYPES = {
    TalentSelection.DEITY: DeityChoice,
    TalentSelection.FAMILIAR_EFFECT: FamiliarEffectChoice,
    TalentSelection.HATED_GROUP: HatredGroupChoice,
    TalentSelection.OATH: OathChoice,
    TalentSelection.SECRET_BLOODLINE: BloodlineChoice,
    TalentSelection.MAGIC_LORE: MagicLoreChoice,
}


@dataclass(frozen=True, slots=True)
class TalentAcquisition:
    phase: TalentAcquisitionPhase
    funding: TalentFunding
    choice: TalentChoice | None = None
    devotion_confirmed: bool | None = None

    def __post_init__(self):
        if type(self.phase) is not TalentAcquisitionPhase or type(self.funding) is not TalentFunding:
            raise TypeError('Talent acquisition requires its typed phase and funding')
        if self.funding is TalentFunding.FREE and self.phase is not TalentAcquisitionPhase.CREATION:
            raise ValueError('only free Character Creation waives Talent Requirements')
        if self.choice is not None:
            if type(self.choice) not in _CHOICE_TYPES.values():
                raise TypeError('Talent acquisition requires its exact typed choice')
            replace(self.choice)
        if self.devotion_confirmed is not None and type(self.devotion_confirmed) is not bool:
            raise TypeError('Faith devotion confirmation requires an exact bool or None')


@dataclass(frozen=True, slots=True)
class AcquiredTalent:
    id: TalentId
    acquisitions: tuple[TalentAcquisition, ...]

    def __post_init__(self):
        if type(self.id) is not TalentId:
            raise TypeError('acquired Talent requires its typed catalog identifier')
        if (type(self.acquisitions) is not tuple or not self.acquisitions
                or any(type(value) is not TalentAcquisition for value in self.acquisitions)):
            raise TypeError('acquired Talent requires a nonempty tuple of exact acquisitions')
        definition = talent_definition(self.id)
        maximum = definition.maximum_purchases
        if maximum is not None and len(self.acquisitions) > maximum:
            raise ValueError('Talent acquisitions exceed its printed purchase limit')
        advanced = False
        effects = set()
        for index, acquisition in enumerate(self.acquisitions):
            replace(acquisition)
            if definition.creation_only and acquisition.phase is not TalentAcquisitionPhase.CREATION:
                raise ValueError('this Talent can only be acquired during Character Creation')
            if acquisition.phase is TalentAcquisitionPhase.ADVANCEMENT:
                advanced = True
            elif advanced:
                raise ValueError('ordered Talent acquisitions cannot return to Character Creation')
            expected_choice = (_CHOICE_TYPES.get(definition.selection)
                if index == 0 or definition.progression is TalentProgression.FAMILIAR_EFFECTS else None)
            if expected_choice is None:
                if acquisition.choice is not None:
                    raise ValueError('this acquisition has no additional Talent choice')
            elif type(acquisition.choice) is not expected_choice:
                raise TypeError('Talent acquisition is missing its exact required choice')
            if definition.progression is TalentProgression.FAMILIAR_EFFECTS:
                if acquisition.choice.effect in effects:
                    raise ValueError('each Familiar acquisition must add a distinct effect')
                effects.add(acquisition.choice.effect)
            if self.id is TalentId.FAITH:
                if (acquisition.phase is TalentAcquisitionPhase.ADVANCEMENT
                        and acquisition.devotion_confirmed is not True):
                    raise ValueError('each Faith advancement acquisition needs a devotion trial')
            elif acquisition.devotion_confirmed is not None:
                raise ValueError('devotion confirmation belongs only to Faith acquisitions')


@dataclass(frozen=True, slots=True)
class TalentLoreFact:
    id: str
    magic: bool = False

    def __post_init__(self):
        _identifier(self.id, 'Talent Lore fact')
        if type(self.magic) is not bool:
            raise TypeError('Magic Lore classification requires an exact bool')


_CHARACTERISTICS = ('weapon_skill', 'ballistic_skill', 'strength', 'toughness',
    'initiative', 'agility', 'reason', 'fellowship')


@dataclass(frozen=True, slots=True)
class TalentOwnerFacts:
    weapon_skill: int | None = None
    ballistic_skill: int | None = None
    strength: int | None = None
    toughness: int | None = None
    initiative: int | None = None
    agility: int | None = None
    reason: int | None = None
    fellowship: int | None = None
    origin: TalentOrigin | None = None
    lores: tuple[TalentLoreFact, ...] = ()
    status: TalentStatusTier | None = None
    equipment: tuple[TalentEquipmentRequirement, ...] = ()
    grail_quest_completed: bool = False
    can_cast_spells: bool = False

    def __post_init__(self):
        for name in _CHARACTERISTICS:
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 1):
                raise TypeError('Talent prerequisite Characteristics require positive exact integers or None')
        if self.origin is not None and type(self.origin) is not TalentOrigin:
            raise TypeError('Talent Origin fact requires its typed Origin or None')
        if (type(self.lores) is not tuple
                or any(type(lore) is not TalentLoreFact for lore in self.lores)):
            raise TypeError('Talent Lores require a tuple of exact Lore facts')
        for lore in self.lores:
            replace(lore)
        if len({lore.id for lore in self.lores}) != len(self.lores):
            raise ValueError('a Talent Lore fact cannot have duplicate or conflicting identities')
        if self.status is not None and type(self.status) is not TalentStatusTier:
            raise TypeError('Talent Status fact requires its typed tier or None')
        if (type(self.equipment) is not tuple
                or any(type(value) is not TalentEquipmentRequirement for value in self.equipment)):
            raise TypeError('Talent equipment facts require a tuple of typed requirements')
        if len(set(self.equipment)) != len(self.equipment):
            raise ValueError('Talent prerequisite equipment facts must be unique')
        if type(self.grail_quest_completed) is not bool or type(self.can_cast_spells) is not bool:
            raise TypeError('operative Talent confirmations require exact bools')


def _ownership(talents):
    if type(talents) is not tuple or any(type(value) is not AcquiredTalent for value in talents):
        raise TypeError('Talent ownership requires a tuple of exact acquired Talents')
    for value in talents:
        replace(value)
    if len({value.id for value in talents}) != len(talents):
        raise ValueError('each Talent identity must have one complete acquisition source')
    return frozenset(value.id for value in talents)


def _requirements_met(requirements, owned, facts):
    for name in _CHARACTERISTICS:
        minimum = getattr(requirements, name)
        actual = getattr(facts, name)
        if minimum and (actual is None or actual < minimum):
            return False
    if requirements.origins and facts.origin not in requirements.origins:
        return False
    if requirements.excluded_origins and (facts.origin is None or facts.origin in requirements.excluded_origins):
        return False
    for lore in requirements.lores:
        if lore is TalentLoreRequirement.ANY_MAGIC:
            if not any(value.magic for value in facts.lores):
                return False
        elif not any(value.id == lore.value for value in facts.lores):
            return False
    if any(talent not in owned for talent in requirements.talents):
        return False
    if any(item not in facts.equipment for item in requirements.equipment):
        return False
    if requirements.minimum_status is not None:
        tiers = (TalentStatusTier.BRASS, TalentStatusTier.SILVER, TalentStatusTier.GOLD)
        if facts.status is None or tiers.index(facts.status) < tiers.index(requirements.minimum_status):
            return False
    return True


def validate_acquired_talents(talents: tuple[AcquiredTalent, ...], facts: TalentOwnerFacts) -> None:
    """Validate the complete owned set against original acquisition facts.

    Prerequisite Talent identities are checked over the whole set. This does
    not invent a cross-Talent chronology or validate XP affordability.
    """
    owned = _ownership(talents)
    if type(facts) is not TalentOwnerFacts:
        raise TypeError('Talent acquisition requires its exact owner facts')
    replace(facts)
    for acquired in talents:
        requirements = talent_definition(acquired.id).requirements
        for acquisition in acquired.acquisitions:
            if acquisition.funding is TalentFunding.FREE:
                continue
            if not _requirements_met(requirements, owned, facts):
                raise ValueError('paid Talent acquisition does not meet its printed Requirements')
    if TalentId.FAITH in owned and (facts.can_cast_spells
            or owned & {TalentId.WIZARD, TalentId.TOUCHED_BY_THE_WINDS}):
        raise ValueError('Faith cannot coexist with Touched by the Winds or spellcasting')
    if TalentId.GRAIL_VOW in owned and not facts.grail_quest_completed:
        raise ValueError('The Grail Vow requires a completed Grail Quest even when acquired free')


def talent_purchases(talents: tuple[AcquiredTalent, ...], id: TalentId) -> int:
    if type(id) is not TalentId:
        raise TypeError('Talent query requires its exact typed identifier')
    _ownership(talents)
    return next((len(value.acquisitions) for value in talents if value.id is id), 0)


def has_talent(talents: tuple[AcquiredTalent, ...], id: TalentId) -> bool:
    return talent_purchases(talents, id) > 0
