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
)


@dataclass(frozen=True, slots=True)
class PcBookNpcAbility:
    name: str
    scope: str
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


def _definition(profile_id: PcBookNpcProfile) -> NpcDefinition:
    if type(profile_id) is not PcBookNpcProfile:
        raise TypeError('book NPC profile must be its exact PcBookNpcProfile enum')
    if profile_id is PcBookNpcProfile.FOOTPAD:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 97,3,3,2,'dagger',0,3
    elif profile_id is PcBookNpcProfile.EMPIRE_TOWNSFOLK:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 96,2,2,2,'dagger',0,2
    else:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 97,3,3,3,'axe',1,2
    source = f'BOOK-GM-GUIDE:1.1:p{page}:{profile_id.value}'
    attack = NpcAttackProfile(attack_name,source+':'+attack_name,Skill.MELEE,
        InlineProfile(dice,threshold),DamageProfile(damage),RangedWeaponRange.CLOSE,
        RangedWeaponRange.CLOSE,RangedWeaponHands.ONE_HANDED)
    protection = NpcProtectionProfile(source+':athletics',Skill.ATHLETICS,InlineProfile(dice,protection_threshold))
    return NpcDefinition('pc-book-npc:'+profile_id.value,source,TargetInjuryPolicy.MINION,1,
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
    else:
        ability = PcBookNpcAbility('Craven Opportunist',
            'Melee attacks against an enemy the Brigand actually outnumbers','+2d instead of +1d')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            97,'Brigand (Axe)',definition,(),(ability,),('Warbow',))
    return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
        page,name,definition,(ability,),(),())


def create_pc_book_npc(profile_id: PcBookNpcProfile, actor_id: str) -> NpcParticipantSnapshot:
    if type(actor_id) is not str:
        raise TypeError('book NPC actor ID must be an exact string')
    definition = _definition(profile_id)
    state = NpcParticipantState(actor_id,definition.id,CombatSide.OPPOSITION,ProfileInjuryState(0,1),
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
