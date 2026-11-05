"""Book-backed combat loadouts; this is not a catalogue of complete NPC cards."""
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum

from towr.domain.attack_models import ConditionOnHitSpec, DamageProfile, ResilienceProfile
from towr.domain.condition_models import Condition, EffectClassification
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
    ARTISAN = 'artisan'
    BRETONNIAN_SQUIRE_SWORD = 'bretonnian_squire_sword'
    ELF_MERCHANT_JEWELLED_BLADE = 'elf_merchant_jewelled_blade'
    HORSE = 'horse'
    GIANT_WOLF = 'giant_wolf'
    GIANT_BOAR = 'giant_boar'
    GOR_DUAL_AXES = 'gor_dual_axes'
    CHAOS_WARHOUND = 'chaos_warhound'
    ORC_BOY_CHOPPAS = 'orc_boy_choppas'
    GIANT_SPIDER = 'giant_spider'
    WHITE_WOLF_CLAMPING_JAWS = 'white_wolf_clamping_jaws'
    EMPIRE_KNIGHT_LANCE = 'empire_knight_lance'
    KNIGHT_WHITE_WOLF_HAMMER = 'knight_white_wolf_hammer'
    BIG_UN_CHOPPAS = 'big_un_choppas'


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
    (PcBookNpcProfile.ARTISAN,'pc-book-npc:artisan',
        ('BOOK-GM-GUIDE:1.1:p96:artisan','BOOK-GM-GUIDE:1.1:p96:artisan:make_shift_weapons',
         'BOOK-GM-GUIDE:1.1:p96:artisan:athletics')),
    (PcBookNpcProfile.BRETONNIAN_SQUIRE_SWORD,'pc-book-npc:bretonnian_squire_sword',
        ('BOOK-GM-GUIDE:1.1:p109:bretonnian_squire_sword',
         'BOOK-GM-GUIDE:1.1:p109:bretonnian_squire_sword:sword',
         'BOOK-GM-GUIDE:1.1:p109:bretonnian_squire_sword:athletics')),
    (PcBookNpcProfile.ELF_MERCHANT_JEWELLED_BLADE,'pc-book-npc:elf_merchant_jewelled_blade',
        ('BOOK-GM-GUIDE:1.1:p107:elf_merchant_jewelled_blade',
         'BOOK-GM-GUIDE:1.1:p107:elf_merchant_jewelled_blade:jewelled_blade',
         'BOOK-GM-GUIDE:1.1:p107:elf_merchant_jewelled_blade:athletics')),
    (PcBookNpcProfile.HORSE,'pc-book-npc:horse',
        ('BOOK-GM-GUIDE:1.1:p135:horse','BOOK-GM-GUIDE:1.1:p135:horse:hooves',
         'BOOK-GM-GUIDE:1.1:p135:horse:athletics')),
    (PcBookNpcProfile.GIANT_WOLF,'pc-book-npc:giant_wolf',
        ('BOOK-GM-GUIDE:1.1:p136:giant_wolf','BOOK-GM-GUIDE:1.1:p136:giant_wolf:clamping_jaws',
         'BOOK-GM-GUIDE:1.1:p136:giant_wolf:athletics')),
    (PcBookNpcProfile.GIANT_BOAR,'pc-book-npc:giant_boar',
        ('BOOK-GM-GUIDE:1.1:p137:giant_boar','BOOK-GM-GUIDE:1.1:p137:giant_boar:goring_tusks',
         'BOOK-GM-GUIDE:1.1:p137:giant_boar:athletics')),
    (PcBookNpcProfile.GOR_DUAL_AXES,'pc-book-npc:gor_dual_axes',
        ('BOOK-GM-GUIDE:1.1:p143:gor_dual_axes','BOOK-GM-GUIDE:1.1:p143:gor_dual_axes:crude_axes',
         'BOOK-GM-GUIDE:1.1:p143:gor_dual_axes:athletics')),
    (PcBookNpcProfile.CHAOS_WARHOUND,'pc-book-npc:chaos_warhound',
        ('BOOK-GM-GUIDE:1.1:p145:chaos_warhound','BOOK-GM-GUIDE:1.1:p145:chaos_warhound:pinning_claws',
         'BOOK-GM-GUIDE:1.1:p145:chaos_warhound:athletics')),
    (PcBookNpcProfile.ORC_BOY_CHOPPAS,'pc-book-npc:orc_boy_choppas',
        ('BOOK-GM-GUIDE:1.1:p158:orc_boy_choppas','BOOK-GM-GUIDE:1.1:p158:orc_boy_choppas:choppas',
         'BOOK-GM-GUIDE:1.1:p158:orc_boy_choppas:defence',
         'BOOK-GM-GUIDE:1.1:p158:orc_boy_choppas:athletics')),
    (PcBookNpcProfile.GIANT_SPIDER,'pc-book-npc:giant_spider',
        ('BOOK-GM-GUIDE:1.1:p137:giant_spider','BOOK-GM-GUIDE:1.1:p137:giant_spider:poisonous_fangs',
         'BOOK-GM-GUIDE:1.1:p137:giant_spider:athletics')),
    (PcBookNpcProfile.WHITE_WOLF_CLAMPING_JAWS,'pc-book-npc:white_wolf_clamping_jaws',
        ('BOOK-GM-GUIDE:1.1:p136:white_wolf_clamping_jaws',
         'BOOK-GM-GUIDE:1.1:p136:white_wolf_clamping_jaws:clamping_jaws',
         'BOOK-GM-GUIDE:1.1:p136:white_wolf_clamping_jaws:athletics')),
    (PcBookNpcProfile.EMPIRE_KNIGHT_LANCE,'pc-book-npc:empire_knight_lance',
        ('BOOK-GM-GUIDE:1.1:p101:empire_knight_lance',
         'BOOK-GM-GUIDE:1.1:p101:empire_knight_lance:lance',
         'BOOK-GM-GUIDE:1.1:p101:empire_knight_lance:defence',
         'BOOK-GM-GUIDE:1.1:p101:empire_knight_lance:athletics')),
    (PcBookNpcProfile.KNIGHT_WHITE_WOLF_HAMMER,'pc-book-npc:knight_white_wolf_hammer',
        ('BOOK-GM-GUIDE:1.1:p116:knight_white_wolf_hammer',
         'BOOK-GM-GUIDE:1.1:p116:knight_white_wolf_hammer:wolf_hammer',
         'BOOK-GM-GUIDE:1.1:p116:knight_white_wolf_hammer:defence',
         'BOOK-GM-GUIDE:1.1:p116:knight_white_wolf_hammer:athletics')),
    (PcBookNpcProfile.BIG_UN_CHOPPAS,'pc-book-npc:big_un_choppas',
        ('BOOK-GM-GUIDE:1.1:p159:big_un_choppas','BOOK-GM-GUIDE:1.1:p159:big_un_choppas:choppas',
         'BOOK-GM-GUIDE:1.1:p159:big_un_choppas:defence',
         'BOOK-GM-GUIDE:1.1:p159:big_un_choppas:athletics')),
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
    unselected_variant_names: tuple[str, ...]


def _definition(profile_id: PcBookNpcProfile) -> NpcDefinition:
    if type(profile_id) is not PcBookNpcProfile:
        raise TypeError('book NPC profile must be its exact PcBookNpcProfile enum')
    injury_policy,wound_limit,toughness = TargetInjuryPolicy.MINION,1,3
    if profile_id is PcBookNpcProfile.FOOTPAD:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 97,3,3,2,'dagger',0,3
    elif profile_id is PcBookNpcProfile.EMPIRE_TOWNSFOLK:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 96,2,2,2,'dagger',0,2
    elif profile_id is PcBookNpcProfile.BRIGAND_AXE:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 97,3,3,3,'axe',1,2
    elif profile_id is PcBookNpcProfile.EMPIRE_OFFICIAL_DAGGER:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 98,2,3,2,'dagger',0,3
        injury_policy,wound_limit = TargetInjuryPolicy.BRUTE,2
    elif profile_id is PcBookNpcProfile.EMPIRE_STATE_TROOPER_HALBERD:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 100,3,3,5,'halberd',1,4
    elif profile_id is PcBookNpcProfile.ARTISAN:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 96,2,2,2,'make_shift_weapons',0,2
    elif profile_id is PcBookNpcProfile.BRETONNIAN_SQUIRE_SWORD:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 109,3,3,3,'sword',0,4
    elif profile_id is PcBookNpcProfile.ELF_MERCHANT_JEWELLED_BLADE:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 107,4,3,3,'jewelled_blade',1,3
        injury_policy,wound_limit = TargetInjuryPolicy.BRUTE,2
    elif profile_id is PcBookNpcProfile.HORSE:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 135,3,3,3,'hooves',0,4
    elif profile_id is PcBookNpcProfile.GIANT_WOLF:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 136,3,3,3,'clamping_jaws',0,4
    elif profile_id is PcBookNpcProfile.GIANT_BOAR:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 137,3,4,3,'goring_tusks',2,3
    elif profile_id is PcBookNpcProfile.GOR_DUAL_AXES:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 143,4,3,3,'crude_axes',0,3
        toughness = 4  # Printed Resilience5 includes the shield; the fixed dual loadout omits it.
    elif profile_id is PcBookNpcProfile.CHAOS_WARHOUND:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 145,3,3,3,'pinning_claws',0,3
    elif profile_id is PcBookNpcProfile.ORC_BOY_CHOPPAS:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 158,3,4,4,'choppas',1,4
        toughness = 4  # Printed Resilience6 minus the unselected shield; light armour remains.
    elif profile_id is PcBookNpcProfile.GIANT_SPIDER:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 137,3,3,3,'poisonous_fangs',0,3
    elif profile_id is PcBookNpcProfile.EMPIRE_KNIGHT_LANCE:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 101,4,4,4,'lance',2,4
        injury_policy,wound_limit = TargetInjuryPolicy.BRUTE,2  # Resilience6 minus the unselected shield.
    elif profile_id is PcBookNpcProfile.KNIGHT_WHITE_WOLF_HAMMER:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 116,4,4,5,'wolf_hammer',2,3
        injury_policy,wound_limit = TargetInjuryPolicy.BRUTE,2
    elif profile_id is PcBookNpcProfile.BIG_UN_CHOPPAS:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 159,3,4,5,'choppas',1,4
        injury_policy,wound_limit,toughness = TargetInjuryPolicy.BRUTE,2,4  # GM158 plus the GM159 variant.
    else:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 136,3,4,5,'clamping_jaws',0,4
        injury_policy,wound_limit,toughness = TargetInjuryPolicy.BRUTE,2,5
    source = f'BOOK-GM-GUIDE:1.1:p{page}:{profile_id.value}'
    natural = profile_id in (PcBookNpcProfile.HORSE,PcBookNpcProfile.GIANT_WOLF,
        PcBookNpcProfile.GIANT_BOAR,PcBookNpcProfile.CHAOS_WARHOUND,
        PcBookNpcProfile.GIANT_SPIDER,PcBookNpcProfile.WHITE_WOLF_CLAMPING_JAWS)
    secondary_effects = ((ConditionOnHitSpec(Condition.DRAINED,
        'RULE-PROFILE-CREATURE-007:poisonous-fangs-drained',EffectClassification.UNCLASSIFIED),)
        if profile_id is PcBookNpcProfile.GIANT_SPIDER else ())
    attack = NpcAttackProfile(attack_name,source+':'+attack_name,Skill.MELEE,
        InlineProfile(dice,threshold),DamageProfile(damage),RangedWeaponRange.CLOSE,
        RangedWeaponRange.CLOSE,(None if natural else RangedWeaponHands.TWO_HANDED
            if profile_id in (PcBookNpcProfile.EMPIRE_STATE_TROOPER_HALBERD,PcBookNpcProfile.ORC_BOY_CHOPPAS,
                PcBookNpcProfile.KNIGHT_WHITE_WOLF_HAMMER,PcBookNpcProfile.BIG_UN_CHOPPAS)
            else RangedWeaponHands.ONE_HANDED),secondary_effects=secondary_effects)
    protection_dice = (4 if profile_id in (PcBookNpcProfile.HORSE,PcBookNpcProfile.GIANT_WOLF,
        PcBookNpcProfile.CHAOS_WARHOUND,PcBookNpcProfile.GIANT_SPIDER,
        PcBookNpcProfile.WHITE_WOLF_CLAMPING_JAWS)
        else 3 if profile_id in (PcBookNpcProfile.EMPIRE_OFFICIAL_DAGGER,PcBookNpcProfile.ARTISAN) else dice)
    protection_skill = (Skill.DEFENCE if profile_id in (
        PcBookNpcProfile.EMPIRE_STATE_TROOPER_HALBERD,PcBookNpcProfile.ORC_BOY_CHOPPAS,
        PcBookNpcProfile.EMPIRE_KNIGHT_LANCE,PcBookNpcProfile.KNIGHT_WHITE_WOLF_HAMMER,
        PcBookNpcProfile.BIG_UN_CHOPPAS)
        else Skill.ATHLETICS)
    protection = NpcProtectionProfile(source+':'+protection_skill.value,protection_skill,
        InlineProfile(protection_dice,protection_threshold))
    return NpcDefinition('pc-book-npc:'+profile_id.value,source,injury_policy,wound_limit,
        ResilienceProfile(toughness,armour),(attack,),(protection,))


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
            97,'Brigand (Axe)',definition,(),(ability,),('Warbow',),(),(),())
    elif profile_id is PcBookNpcProfile.EMPIRE_OFFICIAL_DAGGER:
        ability = PcBookNpcAbility('Heard It All Before',
            'Persuade or Distract attempts against the Official unless they include a bribe',
            'Grim Persuade or Distract Test')
        bands = (PcBookNpcWoundBand(0,'No effect'),PcBookNpcWoundBand(1,'Broken'),
            PcBookNpcWoundBand(2,'Defeated'))
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            98,'Empire Official (Dagger)',definition,(ability,),(),('Pistol',),bands,(),())
    elif profile_id is PcBookNpcProfile.EMPIRE_STATE_TROOPER_HALBERD:
        ability = PcBookNpcAbility('Supporting Action',
            'An enemy moves into Close Range; an allied State Trooper or Free Company Militia '
            'in an adjacent Zone is not in Close Range of an enemy',
            'One eligible ally may immediately Charge or make a ranged attack')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            100,'Empire State Trooper (Halberd, Defence)',definition,(ability,),(),
            ('Spear','Crossbow','Handgun'),(),(NpcProtectionProfile(
                definition.source_rule_id+':athletics',Skill.ATHLETICS,InlineProfile(3,3)),),())
    elif profile_id is PcBookNpcProfile.ARTISAN:
        page,name = 96,'Artisan'
        ability = PcBookNpcAbility('Professional Pride',
            'Paying an extra Coin when acquiring a trapping directly from an Artisan creator',
            '+1d on the next Test using that trapping')
    elif profile_id is PcBookNpcProfile.BRETONNIAN_SQUIRE_SWORD:
        ability = PcBookNpcAbility('Noble Service',
            'Help Tests assisting the knight the Squire serves','+2d on those Help Tests')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            109,'Bretonnian Squire (Sword)',definition,(ability,),(),('Longbow',),(),(),())
    elif profile_id is PcBookNpcProfile.ELF_MERCHANT_JEWELLED_BLADE:
        ability = PcBookNpcAbility('Hard Bargain','Tests to barter with an Elf Merchant',
            '-1d on those Tests')
        bands = (PcBookNpcWoundBand(0,'No effect'),PcBookNpcWoundBand(1,'Staggered'),
            PcBookNpcWoundBand(2,'Defeated'))
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            107,'Elf Merchant (Jewelled Blade)',definition,(ability,),(),(),bands,(),())
    elif profile_id is PcBookNpcProfile.HORSE:
        ability = PcBookNpcAbility('Noble Steed','A character mounted on this Horse',
            '+1 Resilience; Fast Speed; successful Charge against a non-Monstrosity '
            'inflicts Prone before Give Ground')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            135,'Horse (unmounted)',definition,(ability,),(),(),(),(),
            ('Bretonnian Warhorse','Elven Steed','Skeletal Steed'))
    elif profile_id is PcBookNpcProfile.GIANT_WOLF:
        rider = PcBookNpcAbility('Goblin Wolf Rider','A Goblin mounted on a Giant Wolf',
            '+1 Resilience; Fast Speed; targets hit by the rider\'s Melee attacks cannot Give Ground')
        jaws = PcBookNpcAbility('Clamping Jaws','The Giant Wolf\'s natural Clamping Jaws attack',
            'Target cannot Give Ground')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            136,'Giant Wolf (unmounted)',definition,(rider,),(jaws,),(),(),(),())
    elif profile_id is PcBookNpcProfile.GIANT_BOAR:
        charge = PcBookNpcAbility('Goring Tusks on Charge','An attack as part of a Charge',
            '+1d Melee and +1 Damage')
        rider = PcBookNpcAbility('Orc Boar Boyz','An Orc mounted on a Giant Boar',
            '+2 Resilience; Fast Speed; +1d Melee and +1 Damage on Charge attacks')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            137,'Giant Boar (unmounted)',definition,(charge,rider),(),(),(),(),())
    elif profile_id is PcBookNpcProfile.GOR_DUAL_AXES:
        forest = PcBookNpcAbility('Child of the Forest','Movement through woodland Difficult Terrain',
            'Ignore the effects of woodland Difficult Terrain')
        rage = PcBookNpcAbility('Primal Rage','Melee attacks whilst the Gor itself is Staggered','+1d Melee')
        axes = PcBookNpcAbility('Dual-wielded Crude Axes',
            'The fixed two-axe loadout occupies both hands; the shield is not carried','+1 Damage')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            143,'Gor (dual Crude Axes, no shield)',definition,(forest,),(rage,axes),(),(),(),())
    elif profile_id is PcBookNpcProfile.CHAOS_WARHOUND:
        forest = PcBookNpcAbility('Child of the Forest','Movement through woodland Difficult Terrain',
            'Ignore the effects of woodland Difficult Terrain')
        claws = PcBookNpcAbility('Pinning Claws','The Chaos Warhound\'s natural Pinning Claws attack',
            'Target cannot Give Ground')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            145,'Chaos Warhound',definition,(forest,),(claws,),(),(),(),())
    elif profile_id is PcBookNpcProfile.ORC_BOY_CHOPPAS:
        charge = PcBookNpcAbility('Choppas on Charge','An attack as part of a Charge','+1 Damage')
        help_ability = PcBookNpcAbility('Power of the Waaagh!',
            'An Orc Boy Helps an ally make a Melee attack',
            'Do not Test; the ally gains 1 free success on that Attack Test')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            158,'Orc Boy (Couple of Choppas, Defence, no shield)',definition,(charge,help_ability),(),
            ('Jagged Spear','Warbow'),(),(NpcProtectionProfile(
                definition.source_rule_id+':athletics',Skill.ATHLETICS,InlineProfile(3,3)),),())
    elif profile_id is PcBookNpcProfile.GIANT_SPIDER:
        terrain = PcBookNpcAbility('Scitter-Scatter','Movement through forests, ruins or vertical obstacles',
            'Ignore Difficult Terrain imposed by those features')
        rider = PcBookNpcAbility('Goblin Wolf Rider','A Goblin mounted on a Giant Spider',
            '+1 Resilience; Fast Speed; ignore forest/ruin/vertical Difficult Terrain; '
            'targets successfully attacked by the rider suffer Drained')
        fangs = PcBookNpcAbility('Poisonous Fangs','A successful Poisonous Fangs hit',
            'Inflict Drained independently of Damage or Wound acceptance')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            137,'Giant Spider (unmounted)',definition,(terrain,rider),(fangs,),(),(),(),())
    elif profile_id in (PcBookNpcProfile.EMPIRE_KNIGHT_LANCE,PcBookNpcProfile.KNIGHT_WHITE_WOLF_HAMMER):
        steed = PcBookNpcAbility('Noble Steed','The Knight is mounted on a Horse',
            '+1 Resilience; Fast Speed; successful Charge against a non-Monstrosity '
            'inflicts Prone before Give Ground')
        if profile_id is PcBookNpcProfile.EMPIRE_KNIGHT_LANCE:
            charge = PcBookNpcAbility('Lance on Charge','A Charge attack whilst mounted',
                '+1d Melee and +1 Damage; Lance cannot dual wield')
            order = PcBookNpcAbility('For the Order','Attack Tests as part of a Charge whilst not Staggered',
                'Those Attack Tests are Glorious')
            page,name = 101,'Empire Knight (unmounted Lance, Defence, no shield)'
            inactive = (steed,charge,order)
            variants = ('Mounted on Horse','Shield')
        else:
            charge = PcBookNpcAbility('Wolf Hammer on Charge','An attack as part of a Charge',
                '+1d Melee and +1 Damage')
            fury = PcBookNpcAbility('Furious Charge','A successful attack as part of a Charge',
                'May take a second action to Attack a different enemy in Close Range')
            page,name = 116,'Knight of the White Wolf (unmounted Wolf Hammer, Defence)'
            inactive = (steed,charge,fury)
            variants = ('Mounted on Horse',)
        bands = (PcBookNpcWoundBand(0,'No effect'),PcBookNpcWoundBand(1,'Drained'),
            PcBookNpcWoundBand(2,'Defeated'))
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            page,name,definition,inactive,(),(),bands,(NpcProtectionProfile(
                definition.source_rule_id+':athletics',Skill.ATHLETICS,InlineProfile(2,3)),),variants)
    elif profile_id is PcBookNpcProfile.BIG_UN_CHOPPAS:
        charge = PcBookNpcAbility('Choppas on Charge','An attack as part of a Charge','+1 Damage')
        help_ability = PcBookNpcAbility('Power of the Waaagh!',
            'A Big \'Un Helps an ally make a Melee attack',
            'Do not Test; the ally gains 1 free success on that Attack Test')
        bands = (PcBookNpcWoundBand(0,'No effect'),PcBookNpcWoundBand(1,'Drained'),
            PcBookNpcWoundBand(2,'Defeated'))
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            159,'Big \'Un (Couple of Choppas, Defence, no shield)',definition,(charge,help_ability),(),
            ('Jagged Spear','Warbow'),bands,(NpcProtectionProfile(
                definition.source_rule_id+':athletics',Skill.ATHLETICS,InlineProfile(3,3)),),
            ('Mounted on Giant Boar','Shield'))
    else:
        charge = PcBookNpcAbility('Pin and Tear','A successful Clamping Jaws attack as part of a Charge',
            'May take a second action to attack the same target with Rending Claws')
        fear = PcBookNpcAbility('Fearsome','An enemy Gives Ground from a White Wolf attack',
            'The enemy suffers Broken; unreachable for the selected Clamping Jaws attack')
        jaws = PcBookNpcAbility('Clamping Jaws','The White Wolf\'s natural Clamping Jaws attack',
            'Target cannot Give Ground')
        bands = (PcBookNpcWoundBand(0,'No effect'),PcBookNpcWoundBand(1,'Drained'),
            PcBookNpcWoundBand(2,'Defeated'))
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            136,'White Wolf (Clamping Jaws)',definition,(charge,fear),(jaws,),('Rending Claws',),bands,(),())
    return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
        page,name,definition,(ability,),(),(),(),(),())


def create_pc_book_npc(profile_id: PcBookNpcProfile, actor_id: str) -> NpcParticipantSnapshot:
    if type(actor_id) is not str:
        raise TypeError('book NPC actor ID must be an exact string')
    definition = _definition(profile_id)
    state = NpcParticipantState(actor_id,definition.id,CombatSide.OPPOSITION,
        ProfileInjuryState(0,definition.wound_limit),
        tuple(attack.id for attack in definition.attacks),
        ResilienceProfile(definition.resilience.toughness,definition.resilience.bonus),
        definition.attacks[0].hands is not None,False)
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
