"""Authoritative Talent acquisition metadata, PG1.4 III73–81.

This inventory is not combat admission. An entry does not enable its effects in
the simulator. Runtime owners and their complete source must be connected before
a Talent can be admitted by the character or generated-NPC compilers.
"""
from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType


class TalentId(str, Enum):
    ACCELERATED_RECOVERY = 'accelerated_recovery'
    ACROBATIC = 'acrobatic'
    ALLIES_IN_ARMS = 'allies_in_arms'
    ARMOUR_BANE = 'armour_bane'
    BASH_ATTACK = 'bash_attack'
    BACK_IN_THE_SADDLE = 'back_in_the_saddle'
    BATTLEFIELD_MUSICIAN = 'battlefield_musician'
    BLESSINGS_OF_THE_LADY = 'blessings_of_the_lady'
    CAREFUL_AIM = 'careful_aim'
    CLEAVING_BLOW = 'cleaving_blow'
    COMBAT_SURGEON = 'combat_surgeon'
    DEEP_FORMATION = 'deep_formation'
    DEFENSIVE_STANCE = 'defensive_stance'
    DISPELLER = 'dispeller'
    EXCEPTIONAL_HEARING = 'exceptional_hearing'
    FAITH = 'faith'
    FAMILIAR = 'familiar'
    FEIGNED_FLIGHT = 'feigned_flight'
    FIGHT_AS_ONE = 'fight_as_one'
    FRIGHTENING = 'frightening'
    GOLDEN_VOICE = 'golden_voice'
    GRAIL_VOW = 'grail_vow'
    HARDY = 'hardy'
    HATRED = 'hatred'
    HOLD_THE_LINE = 'hold_the_line'
    HONOUR_BOUND = 'honour_bound'
    INTENSE_SCRUTINY = 'intense_scrutiny'
    INTERCEPTOR = 'interceptor'
    IRON_GUT = 'iron_gut'
    KEEN_EYED = 'keen_eyed'
    LIGHTNING_REFLEXES = 'lightning_reflexes'
    LONGBEARD = 'longbeard'
    LUCKY = 'lucky'
    MAGIC_RESISTANCE = 'magic_resistance'
    MIGHTY_BLOW = 'mighty_blow'
    NIGHT_DWELLER = 'night_dweller'
    POLYMATH = 'polymath'
    QUESTING_VOW = 'questing_vow'
    QUICK_CHANGE = 'quick_change'
    QUICK_THROW = 'quick_throw'
    RAPID_RELOAD = 'rapid_reload'
    RESISTANCE_TO_CORRUPTION = 'resistance_to_corruption'
    RESOLUTE = 'resolute'
    RIPOSTE = 'riposte'
    SECRET_BLOODLINE = 'secret_bloodline'
    SHORT_SIZE = 'short_size'
    SNAKE_CHARMER = 'snake_charmer'
    SPITESEER = 'spiteseer'
    STAND_AND_SHOOT = 'stand_and_shoot'
    STEER_CLEAR = 'steer_clear'
    TAUNTER = 'taunter'
    THIRST_FOR_KNOWLEDGE = 'thirst_for_knowledge'
    TOUCHED_BY_THE_WINDS = 'touched_by_the_winds'
    UNBREAKABLE = 'unbreakable'
    VALOUR_OF_AGES = 'valour_of_ages'
    VANGUARD = 'vanguard'
    VOUCH_FOR_THEM = 'vouch_for_them'
    WILD_ATTACK = 'wild_attack'
    WIZARD = 'wizard'


class TalentOrigin(str, Enum):
    # Actor facts also cover NPCs and the existing wider Casting source.
    # A generic Human is not proof of either specific Human culture.
    HUMAN = 'human'
    OGRE = 'ogre'
    EMPIRE_HUMAN = 'empire_human'
    BRETONNIAN_HUMAN = 'bretonnian_human'
    DWARF = 'dwarf'
    HIGH_ELF = 'high_elf'
    WOOD_ELF = 'wood_elf'
    HALFLING = 'halfling'


class TalentLoreRequirement(str, Enum):
    ANATOMY = 'anatomy'
    HIGH_SOCIETY = 'high_society'
    ANY_MAGIC = 'any_magic_lore'


class TalentEquipmentRequirement(str, Enum):
    MUSICIANS_GEAR = 'musicians_gear'
    GROOMING_KIT = 'grooming_kit'


class TalentStatusTier(str, Enum):
    BRASS = 'brass'
    SILVER = 'silver'
    GOLD = 'gold'


class TalentProgression(str, Enum):
    SINGLE = 'single'
    FAITH = 'faith'
    FAMILIAR_EFFECTS = 'familiar_effects'
    WIZARD_LEVELS = 'wizard_levels'


class TalentSelection(str, Enum):
    DEITY = 'deity'
    FAMILIAR_EFFECT = 'familiar_effect'
    HATED_GROUP = 'hated_group'
    OATH = 'oath'
    SECRET_BLOODLINE = 'secret_bloodline'
    MAGIC_LORE = 'magic_lore'


class FamiliarEffect(str, Enum):
    ARMOURED = 'armoured'
    BABBLER = 'babbler'
    BOOKREST = 'bookrest'
    CHAOS_SINK = 'chaos_sink'
    COMBATANT = 'combatant'
    FLIGHT = 'flight'
    LINKED = 'linked'
    POISON_TONGUE = 'poison_tongue'
    SKULKER = 'skulker'


def _typed_choices(values, kind, label):
    if (type(values) is not tuple or any(type(value) is not kind for value in values)
            or len(set(values)) != len(values)):
        raise TypeError(label + ' requires unique typed facts in a tuple')


@dataclass(frozen=True, slots=True)
class TalentRequirements:
    """Only the printed Requirements row; operative restrictions are separate.

    A zero minimum means that the printed row has no such prerequisite. These
    facts describe acquisition, not temporary battle modifiers or a rules DSL.
    """
    weapon_skill: int = 0
    ballistic_skill: int = 0
    strength: int = 0
    toughness: int = 0
    initiative: int = 0
    agility: int = 0
    reason: int = 0
    fellowship: int = 0
    origins: tuple[TalentOrigin, ...] = ()
    excluded_origins: tuple[TalentOrigin, ...] = ()
    lores: tuple[TalentLoreRequirement, ...] = ()
    talents: tuple[TalentId, ...] = ()
    equipment: tuple[TalentEquipmentRequirement, ...] = ()
    minimum_status: TalentStatusTier | None = None

    def __post_init__(self):
        for name in ('weapon_skill', 'ballistic_skill', 'strength', 'toughness',
                'initiative', 'agility', 'reason', 'fellowship'):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise TypeError('Talent characteristic minima require exact nonnegative integers')
        _typed_choices(self.origins, TalentOrigin, 'Required Origins')
        _typed_choices(self.excluded_origins, TalentOrigin, 'Excluded Origins')
        if set(self.origins) & set(self.excluded_origins):
            raise ValueError('a Talent cannot require and exclude the same Origin')
        _typed_choices(self.lores, TalentLoreRequirement, 'Required Lores')
        _typed_choices(self.talents, TalentId, 'Required Talents')
        _typed_choices(self.equipment, TalentEquipmentRequirement, 'Required equipment')
        if self.minimum_status is not None and type(self.minimum_status) is not TalentStatusTier:
            raise TypeError('Talent Status prerequisite requires a typed tier')


@dataclass(frozen=True, slots=True)
class TalentDefinition:
    id: TalentId
    name: str
    page: int
    xp_cost: int
    requirements: TalentRequirements = field(default_factory=TalentRequirements)
    progression: TalentProgression = TalentProgression.SINGLE
    selection: TalentSelection | None = None
    creation_only: bool = False
    # Text outside Requirements cannot silently be waived by creation_free.
    operative_source_pages: tuple[int, ...] = ()

    def __post_init__(self):
        if type(self.id) is not TalentId or type(self.name) is not str or not self.name.strip():
            raise TypeError('Talent definition requires its typed ID and printed name')
        if type(self.page) is not int or not 73 <= self.page <= 81:
            raise ValueError('the general Talent catalog comes from PG1.4 III73–81')
        if type(self.xp_cost) is not int or self.xp_cost < 1:
            raise ValueError('Talent cost requires a positive exact XP amount')
        if type(self.requirements) is not TalentRequirements:
            raise TypeError('Talent definition requires its complete typed prerequisites')
        replace(self.requirements)
        if type(self.progression) is not TalentProgression:
            raise TypeError('Talent definition requires its typed acquisition progression')
        if self.selection is not None and type(self.selection) is not TalentSelection:
            raise TypeError('Talent choice requires its typed category')
        if type(self.creation_only) is not bool:
            raise TypeError('Character Creation restriction requires an exact bool')
        if (type(self.operative_source_pages) is not tuple
                or any(type(page) is not int or not 1 <= page <= 192
                    for page in self.operative_source_pages)
                or len(set(self.operative_source_pages)) != len(self.operative_source_pages)):
            raise TypeError('operative restrictions require unique PG source pages')

    @property
    def maximum_purchases(self) -> int | None:
        if self.progression is TalentProgression.SINGLE:
            return 1
        if self.progression is TalentProgression.WIZARD_LEVELS:
            return 4
        # Faith has no purchase cap. Familiar has distinct additional effects,
        # not a printed numeric level cap; its choices must be validated too.
        return None


TALENT_DEFINITIONS = (
    TalentDefinition(TalentId.ACCELERATED_RECOVERY, 'Accelerated Recovery', 73, 4,
        TalentRequirements(toughness=5)),
    TalentDefinition(TalentId.ACROBATIC, 'Acrobatic', 73, 3, TalentRequirements(agility=4)),
    TalentDefinition(TalentId.ALLIES_IN_ARMS, 'Allies in Arms', 73, 3,
        TalentRequirements(fellowship=4)),
    TalentDefinition(TalentId.ARMOUR_BANE, 'Armour Bane', 73, 3),
    TalentDefinition(TalentId.BASH_ATTACK, 'Bash Attack', 73, 4, TalentRequirements(strength=5)),
    TalentDefinition(TalentId.BACK_IN_THE_SADDLE, 'Back in the Saddle', 73, 2,
        TalentRequirements(agility=4)),
    TalentDefinition(TalentId.BATTLEFIELD_MUSICIAN, 'Battlefield Musician', 73, 3,
        TalentRequirements(equipment=(TalentEquipmentRequirement.MUSICIANS_GEAR,))),
    TalentDefinition(TalentId.BLESSINGS_OF_THE_LADY, 'Blessings of the Lady', 74, 3,
        TalentRequirements(origins=(TalentOrigin.BRETONNIAN_HUMAN,),
            lores=(TalentLoreRequirement.HIGH_SOCIETY,), talents=(TalentId.HONOUR_BOUND,))),
    TalentDefinition(TalentId.CAREFUL_AIM, 'Careful Aim', 74, 3, TalentRequirements(reason=4)),
    TalentDefinition(TalentId.CLEAVING_BLOW, 'Cleaving Blow', 74, 4, TalentRequirements(strength=5)),
    TalentDefinition(TalentId.COMBAT_SURGEON, 'Combat Surgeon', 74, 3,
        TalentRequirements(lores=(TalentLoreRequirement.ANATOMY,))),
    TalentDefinition(TalentId.DEEP_FORMATION, 'Deep Formation', 74, 2),
    TalentDefinition(TalentId.DEFENSIVE_STANCE, 'Defensive Stance', 74, 2,
        TalentRequirements(weapon_skill=3)),
    TalentDefinition(TalentId.DISPELLER, 'Dispeller', 74, 3,
        TalentRequirements(talents=(TalentId.WIZARD,))),
    TalentDefinition(TalentId.EXCEPTIONAL_HEARING, 'Exceptional Hearing', 75, 2,
        TalentRequirements(initiative=4)),
    TalentDefinition(TalentId.FAITH, 'Faith', 75, 4,
        TalentRequirements(origins=(TalentOrigin.EMPIRE_HUMAN,)),
        TalentProgression.FAITH, TalentSelection.DEITY, operative_source_pages=(75, 138, 139)),
    TalentDefinition(TalentId.FAMILIAR, 'Familiar', 75, 3,
        TalentRequirements(talents=(TalentId.WIZARD,)),
        TalentProgression.FAMILIAR_EFFECTS, TalentSelection.FAMILIAR_EFFECT),
    TalentDefinition(TalentId.FEIGNED_FLIGHT, 'Feigned Flight', 76, 2),
    TalentDefinition(TalentId.FIGHT_AS_ONE, 'Fight As One', 76, 3),
    TalentDefinition(TalentId.FRIGHTENING, 'Frightening', 76, 4),
    TalentDefinition(TalentId.GOLDEN_VOICE, 'Golden Voice', 76, 2,
        TalentRequirements(fellowship=4)),
    TalentDefinition(TalentId.GRAIL_VOW, 'The Grail Vow', 76, 4,
        TalentRequirements(talents=(TalentId.QUESTING_VOW,)), operative_source_pages=(76,)),
    TalentDefinition(TalentId.HARDY, 'Hardy', 76, 3, TalentRequirements(toughness=4)),
    TalentDefinition(TalentId.HATRED, 'Hatred', 76, 3, selection=TalentSelection.HATED_GROUP),
    TalentDefinition(TalentId.HOLD_THE_LINE, 'Hold the Line', 76, 3,
        TalentRequirements(fellowship=4)),
    TalentDefinition(TalentId.HONOUR_BOUND, 'Honour Bound', 77, 3, selection=TalentSelection.OATH),
    TalentDefinition(TalentId.INTENSE_SCRUTINY, 'Intense Scrutiny', 77, 3,
        TalentRequirements(initiative=4)),
    TalentDefinition(TalentId.INTERCEPTOR, 'Interceptor', 77, 4, TalentRequirements(agility=5)),
    TalentDefinition(TalentId.IRON_GUT, 'Iron Gut', 77, 2,
        TalentRequirements(excluded_origins=(TalentOrigin.HIGH_ELF, TalentOrigin.WOOD_ELF))),
    TalentDefinition(TalentId.KEEN_EYED, 'Keen Eyed', 78, 2, TalentRequirements(initiative=4)),
    TalentDefinition(TalentId.LIGHTNING_REFLEXES, 'Lightning Reflexes', 78, 3,
        TalentRequirements(initiative=5)),
    TalentDefinition(TalentId.LONGBEARD, 'Longbeard', 78, 3,
        TalentRequirements(origins=(TalentOrigin.DWARF,)), creation_only=True),
    TalentDefinition(TalentId.LUCKY, 'Lucky', 78, 4),
    TalentDefinition(TalentId.MAGIC_RESISTANCE, 'Magic Resistance', 78, 3),
    TalentDefinition(TalentId.MIGHTY_BLOW, 'Mighty Blow', 79, 3, TalentRequirements(strength=4)),
    TalentDefinition(TalentId.NIGHT_DWELLER, 'Night Dweller', 79, 2),
    TalentDefinition(TalentId.POLYMATH, 'Polymath', 79, 2, TalentRequirements(reason=4)),
    TalentDefinition(TalentId.QUESTING_VOW, 'The Questing Vow', 79, 3,
        TalentRequirements(talents=(TalentId.BLESSINGS_OF_THE_LADY,))),
    TalentDefinition(TalentId.QUICK_CHANGE, 'Quick Change', 79, 3,
        TalentRequirements(equipment=(TalentEquipmentRequirement.GROOMING_KIT,))),
    TalentDefinition(TalentId.QUICK_THROW, 'Quick Throw', 79, 4,
        TalentRequirements(weapon_skill=4, ballistic_skill=4)),
    TalentDefinition(TalentId.RAPID_RELOAD, 'Rapid Reload', 79, 3,
        TalentRequirements(ballistic_skill=4)),
    TalentDefinition(TalentId.RESISTANCE_TO_CORRUPTION, 'Resistance to Corruption', 79, 4),
    TalentDefinition(TalentId.RESOLUTE, 'Resolute', 79, 3, TalentRequirements(reason=4)),
    TalentDefinition(TalentId.RIPOSTE, 'Riposte', 79, 4, TalentRequirements(weapon_skill=5)),
    TalentDefinition(TalentId.SECRET_BLOODLINE, 'Secret Bloodline', 80, 3,
        creation_only=True, selection=TalentSelection.SECRET_BLOODLINE),
    TalentDefinition(TalentId.SHORT_SIZE, 'Short Size', 80, 2, creation_only=True),
    TalentDefinition(TalentId.SNAKE_CHARMER, 'Snake Charmer', 80, 3),
    TalentDefinition(TalentId.SPITESEER, 'Spiteseer', 80, 3,
        TalentRequirements(origins=(TalentOrigin.WOOD_ELF,))),
    TalentDefinition(TalentId.STAND_AND_SHOOT, 'Stand and Shoot', 80, 3,
        TalentRequirements(initiative=4)),
    TalentDefinition(TalentId.STEER_CLEAR, 'Steer Clear', 80, 3),
    TalentDefinition(TalentId.TAUNTER, 'Taunter', 80, 4),
    TalentDefinition(TalentId.THIRST_FOR_KNOWLEDGE, 'Thirst for Knowledge', 81, 2,
        TalentRequirements(reason=4)),
    TalentDefinition(TalentId.TOUCHED_BY_THE_WINDS, 'Touched by the Winds', 81, 2,
        TalentRequirements(excluded_origins=(TalentOrigin.DWARF, TalentOrigin.HALFLING)),
        selection=TalentSelection.MAGIC_LORE),
    TalentDefinition(TalentId.UNBREAKABLE, 'Unbreakable', 81, 3,
        TalentRequirements(talents=(TalentId.RESOLUTE,))),
    TalentDefinition(TalentId.VALOUR_OF_AGES, 'Valour of Ages', 81, 3,
        TalentRequirements(origins=(TalentOrigin.HIGH_ELF,))),
    TalentDefinition(TalentId.VANGUARD, 'Vanguard', 81, 3, TalentRequirements(agility=4)),
    TalentDefinition(TalentId.VOUCH_FOR_THEM, 'Vouch For Them', 81, 3,
        TalentRequirements(fellowship=4, minimum_status=TalentStatusTier.SILVER)),
    TalentDefinition(TalentId.WILD_ATTACK, 'Wild Attack', 81, 3, TalentRequirements(strength=4)),
    TalentDefinition(TalentId.WIZARD, 'Wizard', 81, 4,
        TalentRequirements(excluded_origins=(TalentOrigin.DWARF, TalentOrigin.HALFLING),
            lores=(TalentLoreRequirement.ANY_MAGIC,)), TalentProgression.WIZARD_LEVELS),
)

_TALENT_INDEX = MappingProxyType({entry.id: entry for entry in TALENT_DEFINITIONS})
if len(_TALENT_INDEX) != len(TALENT_DEFINITIONS) or set(_TALENT_INDEX) != set(TalentId):
    raise RuntimeError('the general Talent catalog must contain each of the 59 entries exactly once')


def talent_definition(talent: TalentId) -> TalentDefinition:
    if type(talent) is not TalentId:
        raise TypeError('Talent lookup requires its exact typed identifier')
    return _TALENT_INDEX[talent]
