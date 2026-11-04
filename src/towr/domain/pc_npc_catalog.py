"""Book-backed combat loadouts; this is not a catalogue of complete NPC cards."""
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum

from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.npc_roster_models import (
    NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatSide


class PcBookNpcProfile(str, Enum):
    FOOTPAD = 'footpad'
    EMPIRE_TOWNSFOLK = 'empire_townsfolk'
    BRIGAND_AXE = 'brigand_axe'
    EMPIRE_OFFICIAL_DAGGER = 'empire_official_dagger'
    EMPIRE_STATE_TROOPER_HALBERD = 'empire_state_trooper_halberd'


# Immutable identity strings only; canonical definition graphs are always freshly built.
_CATALOG_IDENTITIES = (
    (PcBookNpcProfile.FOOTPAD,'pc-book-npc:footpad',
        ('BOOK-GM-GUIDE:1.1:p97:footpad','BOOK-GM-GUIDE:1.1:p97:footpad:dagger',
         'BOOK-GM-GUIDE:1.1:p97:footpad:athletics')),
    (PcBookNpcProfile.EMPIRE_TOWNSFOLK,'pc-book-npc:empire_townsfolk',
        ('BOOK-GM-GUIDE:1.1:p96:empire_townsfolk','BOOK-GM-GUIDE:1.1:p96:empire_townsfolk:dagger',
         'BOOK-GM-GUIDE:1.1:p96:empire_townsfolk:athletics')),
    (PcBookNpcProfile.BRIGAND_AXE,'pc-book-npc:brigand_axe',
        ('BOOK-GM-GUIDE:1.1:p97:brigand_axe','BOOK-GM-GUIDE:1.1:p97:brigand_axe:axe',
         'BOOK-GM-GUIDE:1.1:p97:brigand_axe:athletics')),
    (PcBookNpcProfile.EMPIRE_OFFICIAL_DAGGER,'pc-book-npc:empire_official_dagger',
        ('BOOK-GM-GUIDE:1.1:p98:empire_official_dagger',
         'BOOK-GM-GUIDE:1.1:p98:empire_official_dagger:dagger',
         'BOOK-GM-GUIDE:1.1:p98:empire_official_dagger:athletics')),
    (PcBookNpcProfile.EMPIRE_STATE_TROOPER_HALBERD,'pc-book-npc:empire_state_trooper_halberd',
        ('BOOK-GM-GUIDE:1.1:p100:empire_state_trooper_halberd',
         'BOOK-GM-GUIDE:1.1:p100:empire_state_trooper_halberd:halberd',
         'BOOK-GM-GUIDE:1.1:p100:empire_state_trooper_halberd:defence',
         'BOOK-GM-GUIDE:1.1:p100:empire_state_trooper_halberd:athletics')),
)


@dataclass(frozen=True, slots=True)
class PcBookNpcAbility:
    name: str
    scope: str
    effect: str


@dataclass(frozen=True, slots=True)
class PcBookNpcWoundBand:
    """Descriptive card metadata; battle effects use explicit rule implementations."""
    wounds: int
    effect: str


@dataclass(frozen=True, slots=True)
class PcBookNpcEntry:
    profile_id: PcBookNpcProfile
    book_id: str
    version: str
    chapter: str
    page: int
    name: str
    definition: NpcDefinition
    inactive_abilities: tuple[PcBookNpcAbility, ...]
    active_abilities: tuple[PcBookNpcAbility, ...]
    unselected_attack_names: tuple[str, ...]
    wound_bands: tuple[PcBookNpcWoundBand, ...]
    unselected_protection: tuple[NpcProtectionProfile, ...]


def _definition(profile_id: PcBookNpcProfile) -> NpcDefinition:
    if type(profile_id) is not PcBookNpcProfile:
        raise TypeError('book NPC profile must be its exact PcBookNpcProfile enum')
    injury_policy,wound_limit = TargetInjuryPolicy.MINION,1
    if profile_id is PcBookNpcProfile.FOOTPAD:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 97,3,3,2,'dagger',0,3
    elif profile_id is PcBookNpcProfile.EMPIRE_TOWNSFOLK:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 96,2,2,2,'dagger',0,2
    elif profile_id is PcBookNpcProfile.BRIGAND_AXE:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 97,3,3,3,'axe',1,2
    elif profile_id is PcBookNpcProfile.EMPIRE_OFFICIAL_DAGGER:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 98,2,3,2,'dagger',0,3
        injury_policy,wound_limit = TargetInjuryPolicy.BRUTE,2
    else:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 100,3,3,5,'halberd',1,4
    source = f'BOOK-GM-GUIDE:1.1:p{page}:{profile_id.value}'
    attack = NpcAttackProfile(attack_name,source+':'+attack_name,Skill.MELEE,
        InlineProfile(dice,threshold),DamageProfile(damage),RangedWeaponRange.CLOSE,
        RangedWeaponRange.CLOSE,(RangedWeaponHands.TWO_HANDED
            if profile_id is PcBookNpcProfile.EMPIRE_STATE_TROOPER_HALBERD else RangedWeaponHands.ONE_HANDED))
    protection_dice = 3 if profile_id is PcBookNpcProfile.EMPIRE_OFFICIAL_DAGGER else dice
    protection_skill = (Skill.DEFENCE if profile_id is PcBookNpcProfile.EMPIRE_STATE_TROOPER_HALBERD
        else Skill.ATHLETICS)
    protection = NpcProtectionProfile(source+':'+protection_skill.value,protection_skill,
        InlineProfile(protection_dice,protection_threshold))
    return NpcDefinition('pc-book-npc:'+profile_id.value,source,injury_policy,wound_limit,
        ResilienceProfile(3,armour),(attack,),(protection,))


def get_pc_book_npc_entry(profile_id: PcBookNpcProfile) -> PcBookNpcEntry:
    definition = _definition(profile_id)
    if profile_id is PcBookNpcProfile.FOOTPAD:
        page,name = 97,'Footpad'
        ability = PcBookNpcAbility('Lurker','Awareness spotting a lurking Footpad outside battle',
            'Grim Awareness Test')
    elif profile_id is PcBookNpcProfile.EMPIRE_TOWNSFOLK:
        page,name = 96,'Empire Townsfolk'
        ability = PcBookNpcAbility('Streetwise','Awareness opposing pickpocket attempts','+1d Awareness')
    elif profile_id is PcBookNpcProfile.BRIGAND_AXE:
        ability = PcBookNpcAbility('Craven Opportunist',
            'Melee attacks against an enemy the Brigand actually outnumbers','+2d instead of +1d')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            97,'Brigand (Axe)',definition,(),(ability,),('Warbow',),(),())
    elif profile_id is PcBookNpcProfile.EMPIRE_OFFICIAL_DAGGER:
        ability = PcBookNpcAbility('Heard It All Before',
            'Persuade or Distract attempts against the Official unless they include a bribe',
            'Grim Persuade or Distract Test')
        bands = (PcBookNpcWoundBand(0,'No effect'),PcBookNpcWoundBand(1,'Broken'),
            PcBookNpcWoundBand(2,'Defeated'))
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            98,'Empire Official (Dagger)',definition,(ability,),(),('Pistol',),bands,())
    else:
        ability = PcBookNpcAbility('Supporting Action',
            'An enemy moves into Close Range; an allied State Trooper or Free Company Militia '
            'in an adjacent Zone is not in Close Range of an enemy',
            'One eligible ally may immediately Charge or make a ranged attack')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            100,'Empire State Trooper (Halberd, Defence)',definition,(ability,),(),
            ('Spear','Crossbow','Handgun'),(),(NpcProtectionProfile(
                definition.source_rule_id+':athletics',Skill.ATHLETICS,InlineProfile(3,3)),))
    return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
        page,name,definition,(ability,),(),(),(),())


def create_pc_book_npc(profile_id: PcBookNpcProfile, actor_id: str) -> NpcParticipantSnapshot:
    if type(actor_id) is not str:
        raise TypeError('book NPC actor ID must be an exact string')
    definition = _definition(profile_id)
    state = NpcParticipantState(actor_id,definition.id,CombatSide.OPPOSITION,
        ProfileInjuryState(0,definition.wound_limit),
        tuple(attack.id for attack in definition.attacks),
        ResilienceProfile(definition.resilience.toughness,definition.resilience.bonus),True,False)
    return NpcParticipantSnapshot(definition,state)


def _require_canonical_types(actual, expected) -> None:
    """Reject equal bools, string enums and subclasses throughout this fixed definition."""
    if type(actual) is not type(expected):
        raise TypeError('book NPC definition must retain every canonical nested value type')
    if is_dataclass(expected):
        for item in fields(expected):
            _require_canonical_types(getattr(actual,item.name),getattr(expected,item.name))
    elif type(expected) is tuple:
        if len(actual) != len(expected):
            raise ValueError('book NPC definition cannot alter its attacks or Protection options')
        for value,canonical in zip(actual,expected):
            _require_canonical_types(value,canonical)


def validate_pc_book_npc_definition(definition: NpcDefinition) -> None:
    """Reserve catalog identities while leaving unrelated authored numeric profiles unchanged."""
    if not isinstance(definition,NpcDefinition):
        raise TypeError('book NPC definition validator requires an NpcDefinition')
    if not isinstance(definition.id,str) or not isinstance(definition.source_rule_id,str):
        raise TypeError('NPC definition identities must be strings')
    sources = (definition.source_rule_id,*(attack.source_rule_id for attack in definition.attacks),
        *(protection.source_rule_id for protection in definition.protection))
    for profile_id,definition_id,book_sources in _CATALOG_IDENTITIES:
        if definition.id==definition_id or any(source in book_sources for source in sources):
            expected = _definition(profile_id)
            _require_canonical_types(definition,expected)
            if definition != expected:
                raise ValueError('book NPC definition differs from its canonical printed combat profile')
            return
    if definition.id.startswith('pc-book-npc:'):
        raise ValueError('unknown reserved book NPC definition ID')
