"""Book-backed combat loadouts; this is not a catalogue of complete NPC cards."""
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum

from towr.domain.attack_models import ConditionImpactSpec, ConditionOnHitSpec, DamageProfile, ResilienceProfile, ProneBeforeGiveGroundSpec
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
    GOBLIN_WARRIOR_SPEAR = 'goblin_warrior_spear'
    NASTY_SKULKER = 'nasty_skulker'
    NIGHT_GOBLIN_SPEAR = 'night_goblin_spear'
    NIGHT_GOBLIN_NET_SPEAR = 'night_goblin_net_spear'
    EMPIRE_PEASANT = 'empire_peasant'
    TOWN_WATCH_POLEARM = 'town_watch_polearm'
    FREE_COMPANY_MILITIA_BLADES = 'free_company_militia_blades'
    SIGMARITE_CULTIST_WARHAMMER = 'sigmarite_cultist_warhammer'
    ELF_MILITIA_SPEAR = 'elf_militia_spear'
    UNGOR_SPEAR = 'ungor_spear'
    EMPIRE_STATE_TROOPER_SPEAR = 'empire_state_trooper_spear'
    ORC_BOY_SPEAR_SHIELD = 'orc_boy_spear_shield'
    BIG_UN_SPEAR_SHIELD = 'big_un_spear_shield'
    RAZORGOR = 'razorgor'
    MINOTAUR_AXE = 'minotaur_axe'
    MINOTAUR_DUAL_AXES = 'minotaur_dual_axes'
    MINOTAUR_GREATAXE = 'minotaur_greataxe'
    BEAR_SWEEPING_CLAWS = 'bear_sweeping_claws'
    DEMIGRYPH = 'demigryph'
    CENTIGOR_SPEAR = 'centigor_spear'
    WHITE_WOLF_RENDING_CLAWS = 'white_wolf_rending_claws'
    GOR_AXE_SHIELD = 'gor_axe_shield'
    EMPIRE_KNIGHT_LANCE_SHIELD = 'empire_knight_lance_shield'
    DWARF_BREWGUARD_WARHAMMER = 'dwarf_brewguard_warhammer'
    DWARF_MINER_PICKAXE = 'dwarf_miner_pickaxe'
    HALFLING_THIEF_DAGGER = 'halfling_thief_dagger'
    HOCHLAND_SHARPSHOOTER_AXE = 'hochland_sharpshooter_axe'
    GOR_AXE = 'gor_axe'
    ORC_BOY_SPEAR = 'orc_boy_spear'
    BIG_UN_SPEAR = 'big_un_spear'
    BESTIGOR_MASSIVE_AXE = 'bestigor_massive_axe'
    FLAGELLANT_FLAILS = 'flagellant_flails'
    FLAGELLANT_HOOKS_CHAINS = 'flagellant_hooks_chains'
    SKIN_WOLF = 'skin_wolf'
    IMPERIAL_OGRE_GREATHAMMER = 'imperial_ogre_greathammer'
    PEGASUS_GROUNDED = 'pegasus_grounded'
    BEAR_CRUSHING_WEIGHT = 'bear_crushing_weight'
    GREAT_STAG = 'great_stag'


# Immutable identity strings only; canonical definition graphs are always freshly built.
_CATALOG_IDENTITIES = (
    (PcBookNpcProfile.NIGHT_GOBLIN_NET_SPEAR,'pc-book-npc:night_goblin_net_spear',
        ('BOOK-GM-GUIDE:1.1:p157:night_goblin_net_spear',
         'BOOK-GM-GUIDE:1.1:p157:night_goblin_net_spear:jagged_spear',
         'BOOK-GM-GUIDE:1.1:p157:night_goblin_net_spear:weighted_net',
         'BOOK-GM-GUIDE:1.1:p157:night_goblin_net_spear:athletics')),
    (PcBookNpcProfile.GREAT_STAG,'pc-book-npc:great_stag',
        ('BOOK-GM-GUIDE:1.1:p176:great_stag',
         'BOOK-GM-GUIDE:1.1:p176:great_stag:mighty_antlers',
         'BOOK-GM-GUIDE:1.1:p176:great_stag:trample',
         'BOOK-GM-GUIDE:1.1:p176:great_stag:athletics')),
    (PcBookNpcProfile.BEAR_CRUSHING_WEIGHT,'pc-book-npc:bear_crushing_weight',
        ('BOOK-GM-GUIDE:1.1:p138:bear_crushing_weight',
         'BOOK-GM-GUIDE:1.1:p138:bear_crushing_weight:crushing_weight',
         'BOOK-GM-GUIDE:1.1:p138:bear_crushing_weight:athletics')),
    (PcBookNpcProfile.IMPERIAL_OGRE_GREATHAMMER,'pc-book-npc:imperial_ogre_greathammer',
        ('BOOK-GM-GUIDE:1.1:p103:imperial_ogre_greathammer',
         'BOOK-GM-GUIDE:1.1:p103:imperial_ogre_greathammer:greathammer',
         'BOOK-GM-GUIDE:1.1:p103:imperial_ogre_greathammer:athletics')),
    (PcBookNpcProfile.PEGASUS_GROUNDED,'pc-book-npc:pegasus_grounded',
        ('BOOK-GM-GUIDE:1.1:p176:pegasus_grounded',
         'BOOK-GM-GUIDE:1.1:p176:pegasus_grounded:hooves',
         'BOOK-GM-GUIDE:1.1:p176:pegasus_grounded:athletics')),
    (PcBookNpcProfile.SKIN_WOLF,'pc-book-npc:skin_wolf',
        ('BOOK-GM-GUIDE:1.1:p187:skin_wolf',
         'BOOK-GM-GUIDE:1.1:p187:skin_wolf:claws_and_fangs',
         'BOOK-GM-GUIDE:1.1:p187:skin_wolf:athletics')),
    (PcBookNpcProfile.FLAGELLANT_FLAILS,'pc-book-npc:flagellant_flails',
        ('BOOK-GM-GUIDE:1.1:p122:flagellant_flails',
         'BOOK-GM-GUIDE:1.1:p122:flagellant_flails:flails',
         'BOOK-GM-GUIDE:1.1:p122:flagellant_flails:athletics')),
    (PcBookNpcProfile.FLAGELLANT_HOOKS_CHAINS,'pc-book-npc:flagellant_hooks_chains',
        ('BOOK-GM-GUIDE:1.1:p122:flagellant_hooks_chains',
         'BOOK-GM-GUIDE:1.1:p122:flagellant_hooks_chains:hooks_and_chains',
         'BOOK-GM-GUIDE:1.1:p122:flagellant_hooks_chains:athletics')),

    (PcBookNpcProfile.BESTIGOR_MASSIVE_AXE,'pc-book-npc:bestigor_massive_axe',
        ('BOOK-GM-GUIDE:1.1:p144:bestigor_massive_axe',
         'BOOK-GM-GUIDE:1.1:p144:bestigor_massive_axe:massive_axe',
         'BOOK-GM-GUIDE:1.1:p144:bestigor_massive_axe:defence',
         'BOOK-GM-GUIDE:1.1:p144:bestigor_massive_axe:athletics')),
    (PcBookNpcProfile.HOCHLAND_SHARPSHOOTER_AXE,'pc-book-npc:hochland_sharpshooter_axe',
        ('BOOK-GM-GUIDE:1.1:p114:hochland_sharpshooter_axe', 'BOOK-GM-GUIDE:1.1:p114:hochland_sharpshooter_axe:axe', 'BOOK-GM-GUIDE:1.1:p114:hochland_sharpshooter_axe:athletics')),
    (PcBookNpcProfile.GOR_AXE,'pc-book-npc:gor_axe',
        ('BOOK-GM-GUIDE:1.1:p143:gor_axe', 'BOOK-GM-GUIDE:1.1:p143:gor_axe:crude_axes', 'BOOK-GM-GUIDE:1.1:p143:gor_axe:athletics')),
    (PcBookNpcProfile.ORC_BOY_SPEAR,'pc-book-npc:orc_boy_spear',
        ('BOOK-GM-GUIDE:1.1:p158:orc_boy_spear', 'BOOK-GM-GUIDE:1.1:p158:orc_boy_spear:jagged_spear', 'BOOK-GM-GUIDE:1.1:p158:orc_boy_spear:defence', 'BOOK-GM-GUIDE:1.1:p158:orc_boy_spear:athletics')),
    (PcBookNpcProfile.BIG_UN_SPEAR,'pc-book-npc:big_un_spear',
        ('BOOK-GM-GUIDE:1.1:p159:big_un_spear', 'BOOK-GM-GUIDE:1.1:p159:big_un_spear:jagged_spear', 'BOOK-GM-GUIDE:1.1:p159:big_un_spear:defence', 'BOOK-GM-GUIDE:1.1:p159:big_un_spear:athletics')),
    (PcBookNpcProfile.HALFLING_THIEF_DAGGER,'pc-book-npc:halfling_thief_dagger',
        ('BOOK-GM-GUIDE:1.1:p103:halfling_thief_dagger',
         'BOOK-GM-GUIDE:1.1:p103:halfling_thief_dagger:dagger',
         'BOOK-GM-GUIDE:1.1:p103:halfling_thief_dagger:stealth')),
    (PcBookNpcProfile.DWARF_MINER_PICKAXE,'pc-book-npc:dwarf_miner_pickaxe',
        ('BOOK-GM-GUIDE:1.1:p105:dwarf_miner_pickaxe',
         'BOOK-GM-GUIDE:1.1:p105:dwarf_miner_pickaxe:mining_pickaxe',
         'BOOK-GM-GUIDE:1.1:p105:dwarf_miner_pickaxe:defence',
         'BOOK-GM-GUIDE:1.1:p105:dwarf_miner_pickaxe:athletics')),
    (PcBookNpcProfile.DWARF_BREWGUARD_WARHAMMER,'pc-book-npc:dwarf_brewguard_warhammer',
        ('BOOK-GM-GUIDE:1.1:p104:dwarf_brewguard_warhammer',
         'BOOK-GM-GUIDE:1.1:p104:dwarf_brewguard_warhammer:warhammer',
         'BOOK-GM-GUIDE:1.1:p104:dwarf_brewguard_warhammer:defence',
         'BOOK-GM-GUIDE:1.1:p104:dwarf_brewguard_warhammer:athletics')),
    (PcBookNpcProfile.GOR_AXE_SHIELD,'pc-book-npc:gor_axe_shield',
        ('BOOK-GM-GUIDE:1.1:p143:gor_axe_shield','BOOK-GM-GUIDE:1.1:p143:gor_axe_shield:crude_axes',
         'BOOK-GM-GUIDE:1.1:p143:gor_axe_shield:athletics')),
    (PcBookNpcProfile.EMPIRE_KNIGHT_LANCE_SHIELD,'pc-book-npc:empire_knight_lance_shield',
        ('BOOK-GM-GUIDE:1.1:p101:empire_knight_lance_shield',
         'BOOK-GM-GUIDE:1.1:p101:empire_knight_lance_shield:lance',
         'BOOK-GM-GUIDE:1.1:p101:empire_knight_lance_shield:defence',
         'BOOK-GM-GUIDE:1.1:p101:empire_knight_lance_shield:athletics')),
    (PcBookNpcProfile.DEMIGRYPH,'pc-book-npc:demigryph',
        ('BOOK-GM-GUIDE:1.1:p175:demigryph','BOOK-GM-GUIDE:1.1:p175:demigryph:wicked_claws',
         'BOOK-GM-GUIDE:1.1:p175:demigryph:athletics')),
    (PcBookNpcProfile.CENTIGOR_SPEAR,'pc-book-npc:centigor_spear',
        ('BOOK-GM-GUIDE:1.1:p149:centigor_spear','BOOK-GM-GUIDE:1.1:p149:centigor_spear:jagged_spear',
         'BOOK-GM-GUIDE:1.1:p149:centigor_spear:athletics')),
    (PcBookNpcProfile.WHITE_WOLF_RENDING_CLAWS,'pc-book-npc:white_wolf_rending_claws',
        ('BOOK-GM-GUIDE:1.1:p136:white_wolf_rending_claws',
         'BOOK-GM-GUIDE:1.1:p136:white_wolf_rending_claws:rending_claws',
         'BOOK-GM-GUIDE:1.1:p136:white_wolf_rending_claws:athletics')),
    (PcBookNpcProfile.BEAR_SWEEPING_CLAWS,'pc-book-npc:bear_sweeping_claws',
        ('BOOK-GM-GUIDE:1.1:p138:bear_sweeping_claws',
         'BOOK-GM-GUIDE:1.1:p138:bear_sweeping_claws:sweeping_claws',
         'BOOK-GM-GUIDE:1.1:p138:bear_sweeping_claws:athletics')),
    (PcBookNpcProfile.MINOTAUR_GREATAXE,'pc-book-npc:minotaur_greataxe',
        ('BOOK-GM-GUIDE:1.1:p147:minotaur_greataxe',
         'BOOK-GM-GUIDE:1.1:p147:minotaur_greataxe:greataxe',
         'BOOK-GM-GUIDE:1.1:p147:minotaur_greataxe:athletics')),
    (PcBookNpcProfile.RAZORGOR,'pc-book-npc:razorgor',
        ('BOOK-GM-GUIDE:1.1:p138:razorgor','BOOK-GM-GUIDE:1.1:p138:razorgor:razor_tusks',
         'BOOK-GM-GUIDE:1.1:p138:razorgor:athletics')),
    (PcBookNpcProfile.MINOTAUR_AXE,'pc-book-npc:minotaur_axe',
        ('BOOK-GM-GUIDE:1.1:p147:minotaur_axe','BOOK-GM-GUIDE:1.1:p147:minotaur_axe:axe',
         'BOOK-GM-GUIDE:1.1:p147:minotaur_axe:athletics')),
    (PcBookNpcProfile.MINOTAUR_DUAL_AXES,'pc-book-npc:minotaur_dual_axes',
        ('BOOK-GM-GUIDE:1.1:p147:minotaur_dual_axes','BOOK-GM-GUIDE:1.1:p147:minotaur_dual_axes:axe',
         'BOOK-GM-GUIDE:1.1:p147:minotaur_dual_axes:athletics')),
    (PcBookNpcProfile.EMPIRE_STATE_TROOPER_SPEAR,'pc-book-npc:empire_state_trooper_spear',
        ('BOOK-GM-GUIDE:1.1:p100:empire_state_trooper_spear',
         'BOOK-GM-GUIDE:1.1:p100:empire_state_trooper_spear:spear',
         'BOOK-GM-GUIDE:1.1:p100:empire_state_trooper_spear:defence',
         'BOOK-GM-GUIDE:1.1:p100:empire_state_trooper_spear:athletics')),
    (PcBookNpcProfile.ORC_BOY_SPEAR_SHIELD,'pc-book-npc:orc_boy_spear_shield',
        ('BOOK-GM-GUIDE:1.1:p158:orc_boy_spear_shield',
         'BOOK-GM-GUIDE:1.1:p158:orc_boy_spear_shield:jagged_spear',
         'BOOK-GM-GUIDE:1.1:p158:orc_boy_spear_shield:defence',
         'BOOK-GM-GUIDE:1.1:p158:orc_boy_spear_shield:athletics')),
    (PcBookNpcProfile.BIG_UN_SPEAR_SHIELD,'pc-book-npc:big_un_spear_shield',
        ('BOOK-GM-GUIDE:1.1:p159:big_un_spear_shield',
         'BOOK-GM-GUIDE:1.1:p159:big_un_spear_shield:jagged_spear',
         'BOOK-GM-GUIDE:1.1:p159:big_un_spear_shield:defence',
         'BOOK-GM-GUIDE:1.1:p159:big_un_spear_shield:athletics')),
    (PcBookNpcProfile.SIGMARITE_CULTIST_WARHAMMER,'pc-book-npc:sigmarite_cultist_warhammer',
        ('BOOK-GM-GUIDE:1.1:p121:sigmarite_cultist_warhammer',
         'BOOK-GM-GUIDE:1.1:p121:sigmarite_cultist_warhammer:warhammer',
         'BOOK-GM-GUIDE:1.1:p121:sigmarite_cultist_warhammer:athletics')),
    (PcBookNpcProfile.ELF_MILITIA_SPEAR,'pc-book-npc:elf_militia_spear',
        ('BOOK-GM-GUIDE:1.1:p107:elf_militia_spear','BOOK-GM-GUIDE:1.1:p107:elf_militia_spear:spear',
         'BOOK-GM-GUIDE:1.1:p107:elf_militia_spear:athletics')),
    (PcBookNpcProfile.UNGOR_SPEAR,'pc-book-npc:ungor_spear',
        ('BOOK-GM-GUIDE:1.1:p143:ungor_spear','BOOK-GM-GUIDE:1.1:p143:ungor_spear:crude_spear',
         'BOOK-GM-GUIDE:1.1:p143:ungor_spear:athletics')),
    (PcBookNpcProfile.EMPIRE_PEASANT,'pc-book-npc:empire_peasant',
        ('BOOK-GM-GUIDE:1.1:p96:empire_peasant','BOOK-GM-GUIDE:1.1:p96:empire_peasant:make_shift_weapons',
         'BOOK-GM-GUIDE:1.1:p96:empire_peasant:athletics')),
    (PcBookNpcProfile.TOWN_WATCH_POLEARM,'pc-book-npc:town_watch_polearm',
        ('BOOK-GM-GUIDE:1.1:p97:town_watch_polearm','BOOK-GM-GUIDE:1.1:p97:town_watch_polearm:polearm',
         'BOOK-GM-GUIDE:1.1:p97:town_watch_polearm:athletics')),
    (PcBookNpcProfile.FREE_COMPANY_MILITIA_BLADES,'pc-book-npc:free_company_militia_blades',
        ('BOOK-GM-GUIDE:1.1:p113:free_company_militia_blades',
         'BOOK-GM-GUIDE:1.1:p113:free_company_militia_blades:improvised_blades',
         'BOOK-GM-GUIDE:1.1:p113:free_company_militia_blades:athletics')),
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
    (PcBookNpcProfile.GOBLIN_WARRIOR_SPEAR,'pc-book-npc:goblin_warrior_spear',
        ('BOOK-GM-GUIDE:1.1:p156:goblin_warrior_spear',
         'BOOK-GM-GUIDE:1.1:p156:goblin_warrior_spear:jagged_spear',
         'BOOK-GM-GUIDE:1.1:p156:goblin_warrior_spear:athletics')),
    (PcBookNpcProfile.NASTY_SKULKER,'pc-book-npc:nasty_skulker',
        ('BOOK-GM-GUIDE:1.1:p157:nasty_skulker','BOOK-GM-GUIDE:1.1:p157:nasty_skulker:long_knives',
         'BOOK-GM-GUIDE:1.1:p157:nasty_skulker:defence',
         'BOOK-GM-GUIDE:1.1:p157:nasty_skulker:athletics')),
    (PcBookNpcProfile.NIGHT_GOBLIN_SPEAR,'pc-book-npc:night_goblin_spear',
        ('BOOK-GM-GUIDE:1.1:p157:night_goblin_spear',
         'BOOK-GM-GUIDE:1.1:p157:night_goblin_spear:jagged_spear',
         'BOOK-GM-GUIDE:1.1:p157:night_goblin_spear:athletics')),
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
    if profile_id is PcBookNpcProfile.NIGHT_GOBLIN_NET_SPEAR:
        source = 'BOOK-GM-GUIDE:1.1:p157:night_goblin_net_spear'
        spear = NpcAttackProfile('jagged_spear',source+':jagged_spear',Skill.MELEE,
            InlineProfile(2,3),DamageProfile(3),RangedWeaponRange.CLOSE,
            RangedWeaponRange.SHORT,RangedWeaponHands.ONE_HANDED)
        net = NpcAttackProfile('weighted_net',source+':weighted_net',Skill.THROWING,
            InlineProfile(2,3,6),None,RangedWeaponRange.CLOSE,
            RangedWeaponRange.SHORT,RangedWeaponHands.TWO_HANDED,
            condition_impact=ConditionImpactSpec(Condition.BURDENED,
                'RULE-EQUIPMENT-005:weighted-net-burdened',EffectClassification.UNCLASSIFIED))
        protection = NpcProtectionProfile(source+':athletics',Skill.ATHLETICS,InlineProfile(3,2))
        return NpcDefinition('pc-book-npc:night_goblin_net_spear',source,
            TargetInjuryPolicy.MINION,1,ResilienceProfile(3,armoured=True),(spear,net),(protection,))
    if profile_id is PcBookNpcProfile.GREAT_STAG:
        source = 'BOOK-GM-GUIDE:1.1:p176:great_stag'
        attacks = (
            NpcAttackProfile('mighty_antlers',source+':mighty_antlers',Skill.MELEE,
                InlineProfile(4,3),DamageProfile(6),RangedWeaponRange.CLOSE,RangedWeaponRange.CLOSE,None),
            NpcAttackProfile('trample',source+':trample',Skill.BRAWN,
                InlineProfile(5,3),DamageProfile(5),RangedWeaponRange.CLOSE,RangedWeaponRange.CLOSE,None),
        )
        protection = NpcProtectionProfile(source+':athletics',Skill.ATHLETICS,InlineProfile(5,4))
        return NpcDefinition('pc-book-npc:great_stag',source,TargetInjuryPolicy.BRUTE,3,
            ResilienceProfile(5),attacks,(protection,))
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
    elif profile_id is PcBookNpcProfile.GOBLIN_WARRIOR_SPEAR:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 156,2,3,3,'jagged_spear',2,2
        # The aggregate resilience bonus already includes the carried shield (GM93/156).
    elif profile_id is PcBookNpcProfile.NASTY_SKULKER:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 157,4,4,3,'long_knives',1,4
    elif profile_id is PcBookNpcProfile.NIGHT_GOBLIN_SPEAR:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 157,2,3,3,'jagged_spear',1,2
        # GM157 explicitly replaces total resilience with 4; its shield is retained, not added again.
    elif profile_id is PcBookNpcProfile.EMPIRE_PEASANT:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 96,2,2,2,'make_shift_weapons',0,2
    elif profile_id is PcBookNpcProfile.TOWN_WATCH_POLEARM:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 97,3,3,5,'polearm',1,3
    elif profile_id is PcBookNpcProfile.FREE_COMPANY_MILITIA_BLADES:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 113,3,3,3,'improvised_blades',0,3
    elif profile_id is PcBookNpcProfile.SIGMARITE_CULTIST_WARHAMMER:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 121,3,3,3,'warhammer',0,2
    elif profile_id is PcBookNpcProfile.ELF_MILITIA_SPEAR:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 107,4,3,4,'spear',1,3
    elif profile_id is PcBookNpcProfile.UNGOR_SPEAR:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 143,3,3,3,'crude_spear',1,2
        # Printed Resilience4 already includes the shield; no body armour is inferred.
    elif profile_id is PcBookNpcProfile.EMPIRE_STATE_TROOPER_SPEAR:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 100,3,3,3,'spear',1,4
    elif profile_id is PcBookNpcProfile.ORC_BOY_SPEAR_SHIELD:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 158,3,4,3,'jagged_spear',2,4
        toughness = 4  # Printed Resilience6 includes the shield that this loadout retains.
    elif profile_id is PcBookNpcProfile.BIG_UN_SPEAR_SHIELD:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 159,3,4,4,'jagged_spear',2,4
        injury_policy,wound_limit,toughness = TargetInjuryPolicy.BRUTE,2,4
    elif profile_id is PcBookNpcProfile.RAZORGOR:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 138,3,4,5,'razor_tusks',1,3
        injury_policy,wound_limit,toughness = TargetInjuryPolicy.BRUTE,3,5
    elif profile_id in (PcBookNpcProfile.MINOTAUR_AXE,PcBookNpcProfile.MINOTAUR_DUAL_AXES):
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 147,4,5,5,'axe',1,4
        injury_policy,wound_limit,toughness = TargetInjuryPolicy.BRUTE,3,5
    elif profile_id is PcBookNpcProfile.MINOTAUR_GREATAXE:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 147,3,5,8,'greataxe',1,4
        injury_policy,wound_limit,toughness = TargetInjuryPolicy.BRUTE,3,5
    elif profile_id is PcBookNpcProfile.BEAR_CRUSHING_WEIGHT:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 138,3,3,7,'crushing_weight',1,3
        injury_policy,wound_limit,toughness = TargetInjuryPolicy.BRUTE,3,5
    elif profile_id is PcBookNpcProfile.BEAR_SWEEPING_CLAWS:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 138,4,3,5,'sweeping_claws',1,3
        injury_policy,wound_limit,toughness = TargetInjuryPolicy.BRUTE,3,5
    elif profile_id is PcBookNpcProfile.DEMIGRYPH:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 175,4,4,5,'wicked_claws',0,3
        injury_policy,wound_limit,toughness = TargetInjuryPolicy.BRUTE,3,4
    elif profile_id is PcBookNpcProfile.CENTIGOR_SPEAR:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 149,4,4,4,'jagged_spear',1,3
        injury_policy,wound_limit,toughness = TargetInjuryPolicy.BRUTE,2,4
    elif profile_id is PcBookNpcProfile.WHITE_WOLF_RENDING_CLAWS:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 136,3,4,6,'rending_claws',0,4
        injury_policy,wound_limit,toughness = TargetInjuryPolicy.BRUTE,2,5
    elif profile_id is PcBookNpcProfile.GOR_AXE_SHIELD:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 143,4,3,3,'crude_axes',1,3
        toughness = 4  # This single-axe loadout retains the shield included in printed Resilience5.
    elif profile_id is PcBookNpcProfile.EMPIRE_KNIGHT_LANCE_SHIELD:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 101,4,4,4,'lance',3,4
        injury_policy,wound_limit = TargetInjuryPolicy.BRUTE,2
    elif profile_id is PcBookNpcProfile.DWARF_BREWGUARD_WARHAMMER:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 104,4,3,3,'warhammer',1,3
        injury_policy,wound_limit,toughness = TargetInjuryPolicy.BRUTE,2,4
    elif profile_id is PcBookNpcProfile.IMPERIAL_OGRE_GREATHAMMER:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 103,2,4,8,'greathammer',1,3
        injury_policy,wound_limit,toughness = TargetInjuryPolicy.BRUTE,3,5
    elif profile_id is PcBookNpcProfile.PEGASUS_GROUNDED:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 176,3,3,3,'hooves',0,4
        injury_policy,wound_limit = TargetInjuryPolicy.BRUTE,2
    elif profile_id is PcBookNpcProfile.SKIN_WOLF:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 187,5,3,5,'claws_and_fangs',1,3
        injury_policy,wound_limit,toughness = TargetInjuryPolicy.BRUTE,3,4
    elif profile_id in (PcBookNpcProfile.FLAGELLANT_FLAILS,PcBookNpcProfile.FLAGELLANT_HOOKS_CHAINS):
        flails = profile_id is PcBookNpcProfile.FLAGELLANT_FLAILS
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 122,3,4,(6 if flails else 3),('flails' if flails else 'hooks_and_chains'),0,3
        injury_policy,wound_limit = TargetInjuryPolicy.BRUTE,2
    elif profile_id is PcBookNpcProfile.BESTIGOR_MASSIVE_AXE:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 144,3,4,7,'massive_axe',2,3
        injury_policy,wound_limit,toughness = TargetInjuryPolicy.BRUTE,2,4
    elif profile_id is PcBookNpcProfile.HOCHLAND_SHARPSHOOTER_AXE:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 114,3,3,3,'axe',1,4
        injury_policy,wound_limit,toughness = TargetInjuryPolicy.BRUTE,2,4
    elif profile_id is PcBookNpcProfile.GOR_AXE:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 143,4,3,3,'crude_axes',0,3
        toughness = 4  # GM93: printed Resilience5 minus the omitted shield; only one Axe is selected.
    elif profile_id in (PcBookNpcProfile.ORC_BOY_SPEAR,PcBookNpcProfile.BIG_UN_SPEAR):
        big_un = profile_id is PcBookNpcProfile.BIG_UN_SPEAR
        page,dice,threshold,damage,attack_name,armour,protection_threshold = (159 if big_un else 158),3,4,(4 if big_un else 3),'jagged_spear',1,4
        toughness = 4  # GM93: printed Resilience6 minus the omitted shield.
        if big_un:
            injury_policy,wound_limit = TargetInjuryPolicy.BRUTE,2
    elif profile_id is PcBookNpcProfile.HALFLING_THIEF_DAGGER:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 103,2,3,1,'dagger',0,5
        toughness = 2
    elif profile_id is PcBookNpcProfile.DWARF_MINER_PICKAXE:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 105,4,3,4,'mining_pickaxe',2,3
        toughness = 4
    else:
        page,dice,threshold,damage,attack_name,armour,protection_threshold = 136,3,4,5,'clamping_jaws',0,4
        injury_policy,wound_limit,toughness = TargetInjuryPolicy.BRUTE,2,5
    source = f'BOOK-GM-GUIDE:1.1:p{page}:{profile_id.value}'
    natural = profile_id in (PcBookNpcProfile.HORSE,PcBookNpcProfile.GIANT_WOLF,
        PcBookNpcProfile.GIANT_BOAR,PcBookNpcProfile.CHAOS_WARHOUND,
        PcBookNpcProfile.GIANT_SPIDER,PcBookNpcProfile.WHITE_WOLF_CLAMPING_JAWS,
        PcBookNpcProfile.RAZORGOR,PcBookNpcProfile.BEAR_SWEEPING_CLAWS,PcBookNpcProfile.BEAR_CRUSHING_WEIGHT,
        PcBookNpcProfile.DEMIGRYPH,PcBookNpcProfile.WHITE_WOLF_RENDING_CLAWS,PcBookNpcProfile.SKIN_WOLF,
        PcBookNpcProfile.PEGASUS_GROUNDED)
    secondary_effects = ((ConditionOnHitSpec(Condition.DRAINED,
        'RULE-PROFILE-CREATURE-007:poisonous-fangs-drained',EffectClassification.UNCLASSIFIED),)
        if profile_id is PcBookNpcProfile.GIANT_SPIDER else
        (ProneBeforeGiveGroundSpec('RULE-PROFILE-CREATURE-010:crushing-weight-prone',True),)
        if profile_id is PcBookNpcProfile.BEAR_CRUSHING_WEIGHT else ())
    attack_test_profile = (InlineProfile(dice,threshold,8)
        if profile_id in (PcBookNpcProfile.MINOTAUR_GREATAXE,PcBookNpcProfile.BESTIGOR_MASSIVE_AXE,
            PcBookNpcProfile.BEAR_CRUSHING_WEIGHT)
        else InlineProfile(dice,threshold,6) if profile_id is PcBookNpcProfile.IMPERIAL_OGRE_GREATHAMMER
        else InlineProfile(dice,threshold))
    attack = NpcAttackProfile(attack_name,source+':'+attack_name,Skill.MELEE,
        attack_test_profile,DamageProfile(damage),RangedWeaponRange.CLOSE,
        (RangedWeaponRange.SHORT if profile_id in (PcBookNpcProfile.GOBLIN_WARRIOR_SPEAR,
            PcBookNpcProfile.NIGHT_GOBLIN_SPEAR,PcBookNpcProfile.TOWN_WATCH_POLEARM,
            PcBookNpcProfile.ELF_MILITIA_SPEAR,PcBookNpcProfile.UNGOR_SPEAR,
            PcBookNpcProfile.EMPIRE_STATE_TROOPER_SPEAR,PcBookNpcProfile.ORC_BOY_SPEAR_SHIELD,
            PcBookNpcProfile.BIG_UN_SPEAR_SHIELD,PcBookNpcProfile.CENTIGOR_SPEAR,
            PcBookNpcProfile.ORC_BOY_SPEAR,PcBookNpcProfile.BIG_UN_SPEAR) else RangedWeaponRange.CLOSE),
        (None if natural else RangedWeaponHands.TWO_HANDED
            if profile_id in (PcBookNpcProfile.EMPIRE_STATE_TROOPER_HALBERD,PcBookNpcProfile.ORC_BOY_CHOPPAS,
                PcBookNpcProfile.KNIGHT_WHITE_WOLF_HAMMER,PcBookNpcProfile.BIG_UN_CHOPPAS,
                PcBookNpcProfile.TOWN_WATCH_POLEARM,PcBookNpcProfile.ELF_MILITIA_SPEAR,
                PcBookNpcProfile.MINOTAUR_GREATAXE,PcBookNpcProfile.DWARF_MINER_PICKAXE,
                PcBookNpcProfile.BESTIGOR_MASSIVE_AXE,PcBookNpcProfile.FLAGELLANT_FLAILS,
                PcBookNpcProfile.IMPERIAL_OGRE_GREATHAMMER)
            else RangedWeaponHands.ONE_HANDED),secondary_effects=secondary_effects)
    protection_dice = (3 if profile_id is PcBookNpcProfile.HALFLING_THIEF_DAGGER else 4 if profile_id in (PcBookNpcProfile.HORSE,PcBookNpcProfile.GIANT_WOLF,
        PcBookNpcProfile.CHAOS_WARHOUND,PcBookNpcProfile.GIANT_SPIDER,
        PcBookNpcProfile.WHITE_WOLF_CLAMPING_JAWS,PcBookNpcProfile.UNGOR_SPEAR,
        PcBookNpcProfile.MINOTAUR_GREATAXE,PcBookNpcProfile.WHITE_WOLF_RENDING_CLAWS,
        PcBookNpcProfile.HOCHLAND_SHARPSHOOTER_AXE,PcBookNpcProfile.BESTIGOR_MASSIVE_AXE,PcBookNpcProfile.SKIN_WOLF,
        PcBookNpcProfile.PEGASUS_GROUNDED)
        else 3 if profile_id in (PcBookNpcProfile.EMPIRE_OFFICIAL_DAGGER,PcBookNpcProfile.ARTISAN,
            PcBookNpcProfile.GOBLIN_WARRIOR_SPEAR,PcBookNpcProfile.NIGHT_GOBLIN_SPEAR,
            PcBookNpcProfile.EMPIRE_PEASANT,PcBookNpcProfile.BEAR_SWEEPING_CLAWS,
            PcBookNpcProfile.IMPERIAL_OGRE_GREATHAMMER) else dice)
    protection_skill = (Skill.STEALTH if profile_id is PcBookNpcProfile.HALFLING_THIEF_DAGGER else Skill.DEFENCE if profile_id in (
        PcBookNpcProfile.EMPIRE_STATE_TROOPER_HALBERD,PcBookNpcProfile.ORC_BOY_CHOPPAS,
        PcBookNpcProfile.EMPIRE_KNIGHT_LANCE,PcBookNpcProfile.KNIGHT_WHITE_WOLF_HAMMER,
        PcBookNpcProfile.BIG_UN_CHOPPAS,PcBookNpcProfile.NASTY_SKULKER,
        PcBookNpcProfile.EMPIRE_STATE_TROOPER_SPEAR,PcBookNpcProfile.ORC_BOY_SPEAR_SHIELD,
        PcBookNpcProfile.BIG_UN_SPEAR_SHIELD,PcBookNpcProfile.EMPIRE_KNIGHT_LANCE_SHIELD,
        PcBookNpcProfile.DWARF_BREWGUARD_WARHAMMER,PcBookNpcProfile.DWARF_MINER_PICKAXE,
        PcBookNpcProfile.ORC_BOY_SPEAR,PcBookNpcProfile.BIG_UN_SPEAR,PcBookNpcProfile.BESTIGOR_MASSIVE_AXE)
        else Skill.ATHLETICS)
    protection = NpcProtectionProfile(source+':'+protection_skill.value,protection_skill,
        InlineProfile(protection_dice,protection_threshold))
    return NpcDefinition('pc-book-npc:'+profile_id.value,source,injury_policy,wound_limit,
        ResilienceProfile(toughness,armour),(attack,),(protection,))


def get_pc_book_npc_entry(profile_id: PcBookNpcProfile) -> PcBookNpcEntry:
    definition = _definition(profile_id)
    if profile_id is PcBookNpcProfile.GREAT_STAG:
        charge = PcBookNpcAbility('Mighty Antlers on Charge','A successful Mighty Antlers attack as part of a Charge',
            'Inflict Prone before the target can Give Ground; ordinary Antlers attacks do not receive this effect')
        fear = PcBookNpcAbility('Fearsome','An enemy Gives Ground from a Great Stag attack',
            'That enemy suffers Broken')
        destination = PcBookNpcAbility('Crown of Antlers (Give Ground)',
            'A Great Stag attack makes an enemy Give Ground','The Great Stag chooses where that enemy moves')
        rider = PcBookNpcAbility('Great Stag Knights','A Human or Elf mounted on a Great Stag',
            '+2 Resilience; Fast Speed; Fearsome and Crown of Antlers; a successful Charge inflicts Prone before Give Ground')
        crown = PcBookNpcAbility('Crown of Antlers (Trample)',
            'The first Antlers Attack and its completed Wound/Endurance consequences newly make its target Prone',
            'May take one second action to Trample that same living Prone target; '
            'chosen ADR-0096 interpretation, no retargeting or third Attack')
        trample = PcBookNpcAbility('Trample','The selected Trample Attack against a Prone enemy only',
            'Printed5d/3 Damage5; chosen Brawn/Strength5 cap10; PC opposes with Endurance, or cannot oppose if Defenceless')
        bands = (PcBookNpcWoundBand(0,'No effect'),PcBookNpcWoundBand(1,'No effect'),
            PcBookNpcWoundBand(2,'Drained'),PcBookNpcWoundBand(3,'Defeated'))
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            176,'Great Stag (Mighty Antlers and Trample)',definition,(charge,fear,destination,rider),
            (crown,trample),(),bands,(),())
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
    elif profile_id in (PcBookNpcProfile.GOR_AXE_SHIELD,PcBookNpcProfile.GOR_AXE):
        forest = PcBookNpcAbility('Child of the Forest','Movement through woodland Difficult Terrain',
            'Ignore the effects of woodland Difficult Terrain')
        rage = PcBookNpcAbility('Primal Rage','Melee attacks whilst the Gor itself is Staggered','+1d Melee')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            143,'Gor (single Crude Axe, '+('shield' if profile_id is PcBookNpcProfile.GOR_AXE_SHIELD else 'no shield')+')',
            definition,(forest,),(rage,),(),(),(),('Dual Crude Axes (no shield)',)
            if profile_id is PcBookNpcProfile.GOR_AXE_SHIELD else ('Single Crude Axe with shield','Dual Crude Axes (no shield)'))
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
            158,'Orc Boy (Couple of Choppas, Defence, no shield)',definition,(charge,),(help_ability,),
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
                definition.source_rule_id+':athletics',Skill.ATHLETICS,InlineProfile(2,3,6)),),variants)
    elif profile_id is PcBookNpcProfile.BIG_UN_CHOPPAS:
        charge = PcBookNpcAbility('Choppas on Charge','An attack as part of a Charge','+1 Damage')
        help_ability = PcBookNpcAbility('Power of the Waaagh!',
            'A Big \'Un Helps an ally make a Melee attack',
            'Do not Test; the ally gains 1 free success on that Attack Test')
        bands = (PcBookNpcWoundBand(0,'No effect'),PcBookNpcWoundBand(1,'Drained'),
            PcBookNpcWoundBand(2,'Defeated'))
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            159,'Big \'Un (Couple of Choppas, Defence, no shield)',definition,(charge,),(help_ability,),
            ('Jagged Spear','Warbow'),bands,(NpcProtectionProfile(
                definition.source_rule_id+':athletics',Skill.ATHLETICS,InlineProfile(3,3)),),
            ('Mounted on Giant Boar','Shield'))
    elif profile_id is PcBookNpcProfile.EMPIRE_PEASANT:
        help_ability = PcBookNpcAbility('Torches and Pitchforks','A Peasant Helps an ally make a Melee attack',
            'Do not Test; the ally gains +1d on the Attack Test, which may exceed the usual bonus dice cap')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            96,'Empire Peasant (Make-Shift Weapons)',definition,(),(help_ability,),('Hunting Bow',),(),(),())
    elif profile_id is PcBookNpcProfile.TOWN_WATCH_POLEARM:
        whistle = PcBookNpcAbility('Whistleblower','The Town Watch chooses to signal for aid as part of a Recover action',
            'More Town Watch arrive next turn; Athletics Tests to Retreat from them are Grim')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            97,'Town Watch (Polearm)',definition,(whistle,),(),(),(),(),())
    elif profile_id is PcBookNpcProfile.FREE_COMPANY_MILITIA_BLADES:
        numbers = PcBookNpcAbility('Strength in Numbers',
            'Free Company Militia Help an ally in Medium Range make an attack',
            'Do not Test; the ally gains +1d on the Attack Test, which may exceed the usual bonus dice cap')
        detachment = PcBookNpcAbility('Detachment',
            'An enemy moves into Close Range of a State Trooper; a Free Company Militia or State Trooper '
            'in an adjacent Zone is not in Close Range of an enemy',
            'One nominated eligible ally immediately Charges or makes a ranged attack')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            113,'Free Company Militia (Improvised Blades)',definition,(detachment,),(numbers,),
            ('Assorted Projectiles',),(),(),())
    elif profile_id is PcBookNpcProfile.IMPERIAL_OGRE_GREATHAMMER:
        charge = PcBookNpcAbility('Ogre Charge',
            'A successful Rough Shove attack as part of a separately selected Charge',
            'May take a second action to Attack with another weapon')
        fear = PcBookNpcAbility('Fearsome','An enemy Gives Ground from an Ogre Melee attack',
            'That enemy suffers Broken; current strategy chooses SUFFER_WOUND instead')
        throw = PcBookNpcAbility('Mighty Throw','A successful Rough Shove against an already Staggered enemy',
            'Toss that enemy to a location within Long Range; inflict a Wound and Prone')
        bands = (PcBookNpcWoundBand(0,'Fast Speed'),PcBookNpcWoundBand(1,'Speed reduced to Normal'),
            PcBookNpcWoundBand(2,'Speed reduced to Normal'),PcBookNpcWoundBand(3,'Defeated'))
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            103,'Imperial Ogre (Greathammer, Athletics)',definition,(charge,fear,throw),(),
            ('Rough Shove','Ogre Pistol'),bands,(),())
    elif profile_id is PcBookNpcProfile.PEGASUS_GROUNDED:
        fly = PcBookNpcAbility('Fly','A separately selected movement through vertical Zones',
            'Ignore ground-based obstacles below; cannot move or Give Ground into midair when '
            'starting in Close Range of a ground-based enemy; this encounter starts grounded and has no movement')
        rider = PcBookNpcAbility('Pegasus Knights','A Human or Elf mounted on a Pegasus',
            '+1 Resilience; Fast Speed; Fly; any successful Charge attack inflicts Prone before Give Ground')
        bands = (PcBookNpcWoundBand(0,'No effect'),
            PcBookNpcWoundBand(1,'Cannot fly; must land on next turn (already grounded in this encounter)'),
            PcBookNpcWoundBand(2,'Defeated'))
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            176,'Pegasus (grounded, unmounted Hooves)',definition,(fly,rider),(),(),bands,(),())
    elif profile_id is PcBookNpcProfile.SKIN_WOLF:
        rage = PcBookNpcAbility('Blood Rage','When the Skin Wolf makes an attack',
            'May choose to gain Staggered if not already Staggered; Staggered Skin Wolves gain +1d Melee')
        warped = PcBookNpcAbility('Warped Form','At the end of its own turn, when Wounded and not Staggered',
            'May gain Staggered to heal one non-fire Wound, then inflict Staggered on all other creatures in Close Range')
        bands = (PcBookNpcWoundBand(0,'No effect'),PcBookNpcWoundBand(1,'Warped Form'),
            PcBookNpcWoundBand(2,'Warped Form'),PcBookNpcWoundBand(3,'Defeated'))
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            187,'Skin Wolf',definition,(),(rage,warped),(),bands,(),())
    elif profile_id in (PcBookNpcProfile.FLAGELLANT_FLAILS,PcBookNpcProfile.FLAGELLANT_HOOKS_CHAINS):
        flails = profile_id is PcBookNpcProfile.FLAGELLANT_FLAILS
        unbreakable = PcBookNpcAbility('Unbreakable','Any source that would inflict Broken',
            'Immune to the Broken condition itself, independently of the source psychological classification')
        pain = PcBookNpcAbility('Feel No Pain','When Staggered; when a Wounded Flagellant takes the Recover action',
            'May choose to be Wounded instead of Staggered; a Wounded Flagellant automatically heals one Wound when taking Recover')
        penalty = PcBookNpcAbility('Flails','Melee attacks with Flails whilst the Flagellant is Staggered',
            '-2d Melee while Staggered; no penalty to Protection or Hooks and Chains')
        bands = (PcBookNpcWoundBand(0,'May be Wounded instead of Staggered'),
            PcBookNpcWoundBand(1,'Remove Wound with Recover action'),PcBookNpcWoundBand(2,'Defeated'))
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            122,'Flagellant (Flails)' if flails else 'Flagellant (Hooks and Chains)',definition,(),
            (unbreakable,pain,penalty) if flails else (unbreakable,pain),
            ('Hooks and Chains',) if flails else ('Flails',),bands,(),())
    elif profile_id is PcBookNpcProfile.BESTIGOR_MASSIVE_AXE:
        forest = PcBookNpcAbility('Child of the Forest','Movement through woodland Difficult Terrain',
            'Ignore the effects of woodland Difficult Terrain')
        rage = PcBookNpcAbility('Blood Rage','When the Bestigor makes an attack',
            'May choose to gain Staggered if not already Staggered; Staggered Bestigors gain +1d Melee')
        bands = (PcBookNpcWoundBand(0,'Cannot choose to Give Ground or fall Prone'),
            PcBookNpcWoundBand(1,"Bestigor's next attack is Glorious"),PcBookNpcWoundBand(2,'Defeated'))
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            144,'Bestigor (Massive Axe, Defence)',definition,(forest,),(rage,),(),bands,
            (NpcProtectionProfile(definition.source_rule_id+':athletics',Skill.ATHLETICS,InlineProfile(3,3)),),())
    elif profile_id is PcBookNpcProfile.HOCHLAND_SHARPSHOOTER_AXE:
        reload = PcBookNpcAbility('Rapid Reload',
            'A successful Dexterity Test to reload a weapon, while not Staggered and without moving this turn',
            'May immediately Aim or Attack with that weapon as a second action')
        terrain = PcBookNpcAbility("Sniper's Nest",'Movement through woodland Difficult Terrain',
            'Ignore Difficult Terrain in woodland areas')
        bands = (PcBookNpcWoundBand(0,'No effect'),PcBookNpcWoundBand(1,'Cancel Aim'),
            PcBookNpcWoundBand(2,'Defeated'))
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            114,'Hochland Sharpshooter (Axe, Athletics)',definition,(reload,terrain),(),
            ('Hochland Long Rifle',),bands,(),())
    elif profile_id is PcBookNpcProfile.HALFLING_THIEF_DAGGER:
        protection = PcBookNpcAbility('Now You See Me','Opposing an attack the Halfling Thief is aware of',
            'May use Stealth to Oppose that attack; unaware and Defenceless cannot Oppose')
        theft = PcBookNpcAbility('Thieving Blighter','Stealth to disappear; a separately chosen Move Quietly action',
            'May disappear from view without cover or concealment; when Moving Quietly, may also attempt '
            'to steal a trapping, Asset, or Coin in Close Range that is not in a character\'s hands, '
            'with Dexterity opposed by the owner\'s Awareness')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            103,'Halfling Thief (Dagger, Stealth)',definition,(theft,),(protection,),
            ('Throwing Knives',),(),(),())
    elif profile_id is PcBookNpcProfile.DWARF_MINER_PICKAXE:
        grudges = PcBookNpcAbility('Grudges to Settle',
            'Encountering an enemy against whom the Miner bears a known grudge',
            'Suffer Distracted focused on that enemy; gain +1d Melee only when fighting that enemy; '
            'the relationship is explicitly configured, never inferred from ancestry')
        higher_ground = PcBookNpcAbility('Down in the Dark (higher ground)',
            'An enemy attacks the Miner from higher ground',
            'That enemy does not gain bonus dice for attacking from higher ground')
        terrain = PcBookNpcAbility('Down in the Dark (underground terrain)',
            'Movement through underground obstacles that are Difficult Terrain',
            'Ignore Difficult Terrain from underground obstacles')
        blasting = PcBookNpcAbility('Unselected Blasting Charge',
            'A separately selected ranged attack: Short to Medium Range, 3d/3',
            'All creatures in the target Zone suffer Hazard (3) resisted with Endurance; '
            'a failed attack explodes in the Miner\'s Zone instead')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            105,'Dwarf Miner (Mining Pickaxe, Defence)',definition,(terrain,blasting),
            (grudges,higher_ground),('Blasting Charge',),(),
            (NpcProtectionProfile(definition.source_rule_id+':athletics',Skill.ATHLETICS,InlineProfile(1,3)),),())
    elif profile_id is PcBookNpcProfile.DWARF_BREWGUARD_WARHAMMER:
        cooler = PcBookNpcAbility('Cooler Heads Prevail','A separately chosen action: Leadership Test',
            'For every success, choose one character within Medium Range and remove its Distracted condition')
        distracted = PcBookNpcAbility('First-Wound Distracted','A living Brewguard suffers its first Wound',
            'Accepted ADR-0088 interpretation: the actual first-Wound attacker is the focus; '
            'ordinary one-shot Distracted, not an ongoing Wound cause; '
            'focus death clears it, Defenceless alone does not')
        bands = (PcBookNpcWoundBand(0,'No effect'),
            PcBookNpcWoundBand(1,'Attacker inflicts Distracted condition'),PcBookNpcWoundBand(2,'Defeated'))
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            104,'Dwarf Brewguard (Warhammer, Defence)',definition,(cooler,),(distracted,),('Bare Hands',),bands,
            (NpcProtectionProfile(definition.source_rule_id+':athletics',Skill.ATHLETICS,InlineProfile(2,3)),),())
    elif profile_id is PcBookNpcProfile.DEMIGRYPH:
        fear = PcBookNpcAbility('Fearsome','An enemy Gives Ground from a Demigryph attack',
            'That enemy suffers Broken')
        rider = PcBookNpcAbility('Demigryph Knights','A Human mounted on a Demigryph',
            '+2 Resilience; Fast Speed; Fearsome; ignore Agility penalties from heavy or full plate armour; '
            'when the rider takes the Attack action, may make one rider attack and a second attack '
            'using Wicked Claws, with one of those attacks chosen to be Grim')
        bands = (PcBookNpcWoundBand(0,'No effect'),PcBookNpcWoundBand(1,'Drained'),
            PcBookNpcWoundBand(2,'Drained'),PcBookNpcWoundBand(3,'Defeated'))
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            175,'Demigryph (unmounted Wicked Claws)',definition,(fear,rider),(),(),bands,(),())
    elif profile_id is PcBookNpcProfile.CENTIGOR_SPEAR:
        forest = PcBookNpcAbility('Child of the Forest','Movement through woodland Difficult Terrain',
            'Ignore the effects of woodland Difficult Terrain')
        charge = PcBookNpcAbility('Jagged Spear on Charge','An attack as part of a Charge','+1d Melee')
        rampage = PcBookNpcAbility('Drunken Rampage','A Centigor Charges, before making its attack',
            'Every creature in Close Range suffers Staggered unless it is already Staggered')
        bands = (PcBookNpcWoundBand(0,'No effect'),PcBookNpcWoundBand(1,'Prone'),
            PcBookNpcWoundBand(2,'Defeated'))
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            149,'Centigor (Jagged Spear, shield)',definition,(forest,charge,rampage),(),('Javelin',),bands,(),())
    elif profile_id is PcBookNpcProfile.WHITE_WOLF_RENDING_CLAWS:
        charge = PcBookNpcAbility('Pin and Tear','A successful Clamping Jaws attack as part of a Charge',
            'May take a second action to attack the same target with Rending Claws')
        fear = PcBookNpcAbility('Fearsome','An enemy Gives Ground from a White Wolf attack',
            'The enemy suffers Broken')
        bands = (PcBookNpcWoundBand(0,'No effect'),PcBookNpcWoundBand(1,'Drained'),
            PcBookNpcWoundBand(2,'Defeated'))
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            136,'White Wolf (Rending Claws)',definition,(charge,fear),(),('Clamping Jaws',),bands,(),())
    elif profile_id is PcBookNpcProfile.BEAR_CRUSHING_WEIGHT:
        enduring = PcBookNpcAbility('Enduring Strength',
            'A successful Attack action, while a second action remains available this turn',
            'May take a second action to Attack a different enemy in Close Range')
        fear = PcBookNpcAbility('Fearsome','An enemy Gives Ground from a Bear attack',
            'That enemy suffers Broken')
        prone = PcBookNpcAbility('Crushing Weight','A successful hit with Crushing Weight',
            'Inflict Prone before the target can Give Ground; the condition is removable by ordinary Recover')
        bands = (PcBookNpcWoundBand(0,'No effect'),PcBookNpcWoundBand(1,'Drained'),
            PcBookNpcWoundBand(2,'Drained'),PcBookNpcWoundBand(3,'Defeated'))
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            138,'Bear (Crushing Weight)',definition,(fear,),(enduring,prone),('Sweeping Claws',),bands,(),())
    elif profile_id is PcBookNpcProfile.BEAR_SWEEPING_CLAWS:
        enduring = PcBookNpcAbility('Enduring Strength',
            'A successful Attack action, while a second action remains available this turn',
            'May take a second action to Attack a different enemy in Close Range')
        fear = PcBookNpcAbility('Fearsome','An enemy Gives Ground from a Bear attack',
            'That enemy suffers Broken')
        bands = (PcBookNpcWoundBand(0,'No effect'),PcBookNpcWoundBand(1,'Drained'),
            PcBookNpcWoundBand(2,'Drained'),PcBookNpcWoundBand(3,'Defeated'))
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            138,'Bear (Sweeping Claws)',definition,(fear,),(enduring,),('Crushing Weight',),bands,(),())
    elif profile_id in (PcBookNpcProfile.RAZORGOR,PcBookNpcProfile.MINOTAUR_AXE,
            PcBookNpcProfile.MINOTAUR_DUAL_AXES,PcBookNpcProfile.MINOTAUR_GREATAXE):
        rage = PcBookNpcAbility('Wounded Melee','Melee attacks whilst at 1 or 2 Wounds',
            '+1d Melee per Wound')
        devour = PcBookNpcAbility('Devour the Fallen',
            'Attacking an enemy who is already Staggered, Prone, or Wounded before the attack',
            '+1d on the Wounds Table once, even if several of those conditions apply')
        fear = PcBookNpcAbility('Fearsome','An enemy Gives Ground from this creature\'s attacks',
            'That enemy suffers Broken')
        bands = (PcBookNpcWoundBand(0,'No effect'),PcBookNpcWoundBand(1,'+1d Melee'),
            PcBookNpcWoundBand(2,'+2d Melee'),PcBookNpcWoundBand(3,'Defeated'))
        if profile_id is PcBookNpcProfile.RAZORGOR:
            charge = PcBookNpcAbility('Razor Tusks on Charge','An attack as part of a Charge',
                '+1d Melee and +1 Damage')
            return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
                138,'Razorgor (Razor Tusks)',definition,(charge,fear),(rage,devour),(),bands,(),())
        bull = PcBookNpcAbility('Charging Bull',
            'A separately chosen action targeting a Zone within Medium Range',
            'Brawn Test Opposed by the enemy in that Zone best able to defy it with Defence or Endurance; '
            'success Staggers every creature in the Zone except the Minotaur; '
            'failure Staggers the Minotaur itself')
        dual = profile_id is PcBookNpcProfile.MINOTAUR_DUAL_AXES
        greataxe = profile_id is PcBookNpcProfile.MINOTAUR_GREATAXE
        active = (rage,devour)
        if dual:
            axes = PcBookNpcAbility('Dual-wielded Axes',
                'The fixed two-axe loadout occupies both hands; the shield is not carried','+1 Damage')
            active = (*active,axes)
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            147,'Minotaur ('+('Greataxe' if greataxe else 'dual Axes' if dual else 'single Axe')
                +', Athletics, no shield)',
            definition,(fear,bull),active,('Axe',) if greataxe else ('Greataxe',),bands,(),
            ('Single Axe','Dual Axes') if greataxe else ('Single Axe',) if dual else ('Dual Axes',))
    elif profile_id is PcBookNpcProfile.EMPIRE_KNIGHT_LANCE_SHIELD:
        steed = PcBookNpcAbility('Noble Steed','The Knight is mounted on a Horse',
            '+1 Resilience; Fast Speed; successful Charge against a non-Monstrosity '
            'inflicts Prone before Give Ground')
        charge = PcBookNpcAbility('Lance on Charge','A Charge attack whilst mounted',
            '+1d Melee and +1 Damage; Lance cannot dual wield')
        order = PcBookNpcAbility('For the Order','Attack Tests as part of a Charge whilst not Staggered',
            'Those Attack Tests are Glorious')
        bands = (PcBookNpcWoundBand(0,'No effect'),PcBookNpcWoundBand(1,'Drained'),
            PcBookNpcWoundBand(2,'Defeated'))
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            101,'Empire Knight (unmounted Lance, Defence, shield)',definition,(steed,charge,order),(),(),bands,
            (NpcProtectionProfile(definition.source_rule_id+':athletics',Skill.ATHLETICS,InlineProfile(2,3)),),
            ('Mounted on Horse',))
    elif profile_id is PcBookNpcProfile.EMPIRE_STATE_TROOPER_SPEAR:
        support = PcBookNpcAbility('Supporting Action',
            'An enemy moves into Close Range of a State Trooper; an allied State Trooper '
            'or Free Company Militia in an adjacent Zone is not in Close Range of an enemy',
            'One eligible ally may immediately Charge or make a ranged attack')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            100,'Empire State Trooper (Spear, Defence)',definition,(support,),(),
            ('Halberd','Crossbow','Handgun'),(),(NpcProtectionProfile(
                definition.source_rule_id+':athletics',Skill.ATHLETICS,InlineProfile(3,3)),),())
    elif profile_id in (PcBookNpcProfile.ORC_BOY_SPEAR_SHIELD,PcBookNpcProfile.BIG_UN_SPEAR_SHIELD,
            PcBookNpcProfile.ORC_BOY_SPEAR,PcBookNpcProfile.BIG_UN_SPEAR):
        charge = PcBookNpcAbility('Jagged Spear on Charge','An attack as part of a Charge','+1 Damage')
        big_un = profile_id in (PcBookNpcProfile.BIG_UN_SPEAR_SHIELD,PcBookNpcProfile.BIG_UN_SPEAR)
        shield = profile_id in (PcBookNpcProfile.ORC_BOY_SPEAR_SHIELD,PcBookNpcProfile.BIG_UN_SPEAR_SHIELD)
        help_ability = PcBookNpcAbility('Power of the Waaagh!',
            ('A Big \'Un' if big_un else 'An Orc Boy')+' Helps an ally make a Melee attack',
            'Do not Test; the ally gains 1 free success on that Attack Test')
        bands = ((PcBookNpcWoundBand(0,'No effect'),PcBookNpcWoundBand(1,'Drained'),
            PcBookNpcWoundBand(2,'Defeated')) if big_un else ())
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            159 if big_un else 158,('Big \'Un' if big_un else 'Orc Boy')+' (Jagged Spear, Defence, '+('shield' if shield else 'no shield')+')',
            definition,(charge,),(help_ability,),('Couple of Choppas','Warbow'),bands,
            (NpcProtectionProfile(definition.source_rule_id+':athletics',Skill.ATHLETICS,InlineProfile(3,3)),),
            ('Mounted on Giant Boar',))
    elif profile_id is PcBookNpcProfile.SIGMARITE_CULTIST_WARHAMMER:
        help_ability = PcBookNpcAbility('Torches and Pitchforks',
            'A Sigmarite Cultist Helps an ally make a Melee attack',
            'Do not Test; the ally gains +1d on the Attack Test, which may exceed the usual bonus dice cap')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            121,'Sigmarite Cultist (Warhammer)',definition,(),(help_ability,),(),(),(),())
    elif profile_id is PcBookNpcProfile.ELF_MILITIA_SPEAR:
        prowess = PcBookNpcAbility('Martial Prowess',
            'Opposing a Melee attack whilst another Elf Militia in the same Zone '
            'is not in Close Range of an enemy',
            '+1d on that opposition Test')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            107,'Elf Militia (Spear)',definition,(prowess,),(),('Longbow',),(),(),())
    elif profile_id is PcBookNpcProfile.UNGOR_SPEAR:
        forest = PcBookNpcAbility('Child of the Forest','Difficult Terrain in woodland',
            'Ignore the effects of that Difficult Terrain')
        spite = PcBookNpcAbility('Primal Spite','Attacks against an enemy who is Staggered',
            '+1d on those Attack Tests')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            143,'Ungor (Crude Spear, shield)',definition,(forest,),(spite,),('Shortbow',),(),(),())
    elif profile_id in (PcBookNpcProfile.GOBLIN_WARRIOR_SPEAR,PcBookNpcProfile.NIGHT_GOBLIN_SPEAR,
            PcBookNpcProfile.NIGHT_GOBLIN_NET_SPEAR):
        horde = PcBookNpcAbility('Horde','A Goblin Helps an ally make an attack',
            'Do not Test; the ally gains +1d on the Attack Test, which may exceed the usual bonus dice cap')
        coward = PcBookNpcAbility('Dirty Coward','An already Staggered Goblin receives Staggered again',
            'Automatically defeated without a Wound; drops its weapon and flees combat as fast as possible')
        if profile_id is PcBookNpcProfile.GOBLIN_WARRIOR_SPEAR:
            page,name,unused = 156,'Goblin Warrior (Jagged Spear, shield)',('Shortbow',)
        elif profile_id is PcBookNpcProfile.NIGHT_GOBLIN_NET_SPEAR:
            page,name,unused = 157,'Night Goblin (Weighted Net and carried Jagged Spear)',('Shortbow',)
        else:
            page,name,unused = 157,'Night Goblin (Jagged Spear, shield)',('Weighted Net','Shortbow')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            page,name,definition,(),(coward,horde),unused,(),(),())
    elif profile_id is PcBookNpcProfile.NASTY_SKULKER:
        menace = PcBookNpcAbility('Skulking Menace','Stealth whilst in a Zone with at least 5 other Goblins',
            'May disappear from view even without cover or concealment')
        backstab = PcBookNpcAbility('Backstabba','A genuinely unopposed Melee attack',
            '+1 additional Damage per success; +2 Damage per success in total')
        return PcBookNpcEntry(profile_id,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',
            157,'Nasty Skulker (Long knives, Defence)',definition,(menace,),(backstab,),(),(),
            (NpcProtectionProfile(definition.source_rule_id+':athletics',Skill.ATHLETICS,InlineProfile(3,3)),),())
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
        ResilienceProfile(definition.resilience.toughness,definition.resilience.bonus,
            armoured=definition.resilience.armoured),
        definition.attacks[0].hands is not None,profile_id in (
            PcBookNpcProfile.GOBLIN_WARRIOR_SPEAR,PcBookNpcProfile.NIGHT_GOBLIN_SPEAR,
            PcBookNpcProfile.UNGOR_SPEAR,PcBookNpcProfile.ORC_BOY_SPEAR_SHIELD,
            PcBookNpcProfile.BIG_UN_SPEAR_SHIELD,PcBookNpcProfile.CENTIGOR_SPEAR,
            PcBookNpcProfile.GOR_AXE_SHIELD,PcBookNpcProfile.EMPIRE_KNIGHT_LANCE_SHIELD))
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
