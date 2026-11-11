"""Explicit, book-backed NPC protection choices against Close Shooting."""
from dataclasses import dataclass

from towr.domain.npc_roster_models import NpcDefinition, NpcProtectionProfile
from towr.domain.test_models import InlineProfile, Skill


@dataclass(frozen=True, slots=True)
class PcNpcCloseShootingProtectionPolicy:
    actor_id: str
    skill: Skill

    def __post_init__(self) -> None:
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('Close Shooting protection requires an exact nonempty NPC actor ID')
        if type(self.skill) is not Skill:
            raise TypeError('Close Shooting protection requires its exact Skill')
        if self.skill not in (Skill.MELEE, Skill.ATHLETICS):
            raise ValueError('Close Shooting protection policy supports Melee or Athletics only')


def pc_close_shooting_protection_profile(
    definition: NpcDefinition, skill: Skill,
) -> NpcProtectionProfile:
    """Return the verified Skill profile without changing ordinary Protection.

    PG94 permits Melee opposition; GM100/101/104/105/116/144/157/158/159 supply the full WS/Skill
    values below. They are not inferred from an arbitrary Attack profile.
    """
    from towr.domain.pc_npc_catalog import (
        PcBookNpcProfile, get_pc_book_npc_entry, validate_pc_book_npc_definition,
    )
    if type(definition) is not NpcDefinition:
        raise TypeError('Close Shooting protection requires its full exact NPC definition')
    if type(skill) is not Skill:
        raise TypeError('Close Shooting protection requires its exact Skill')
    if skill not in (Skill.MELEE, Skill.ATHLETICS):
        raise ValueError('Close Shooting protection supports Melee or Athletics only')
    validate_pc_book_npc_definition(definition)
    profiles = {
        'pc-book-npc:empire_state_trooper_halberd': (
            PcBookNpcProfile.EMPIRE_STATE_TROOPER_HALBERD, InlineProfile(3, 3)),
        'pc-book-npc:empire_state_trooper_spear': (
            PcBookNpcProfile.EMPIRE_STATE_TROOPER_SPEAR, InlineProfile(3, 3)),
        'pc-book-npc:empire_knight_lance': (
            PcBookNpcProfile.EMPIRE_KNIGHT_LANCE, InlineProfile(4, 4)),
        'pc-book-npc:knight_white_wolf_hammer': (
            PcBookNpcProfile.KNIGHT_WHITE_WOLF_HAMMER, InlineProfile(4, 4)),
        'pc-book-npc:orc_boy_choppas': (
            PcBookNpcProfile.ORC_BOY_CHOPPAS, InlineProfile(3, 4)),
        'pc-book-npc:orc_boy_spear': (
            PcBookNpcProfile.ORC_BOY_SPEAR, InlineProfile(3, 4)),
        'pc-book-npc:big_un_choppas': (
            PcBookNpcProfile.BIG_UN_CHOPPAS, InlineProfile(3, 4)),
        'pc-book-npc:big_un_spear': (
            PcBookNpcProfile.BIG_UN_SPEAR, InlineProfile(3, 4)),
        'pc-book-npc:nasty_skulker': (
            PcBookNpcProfile.NASTY_SKULKER, InlineProfile(4, 4)),
        'pc-book-npc:dwarf_brewguard_warhammer': (
            PcBookNpcProfile.DWARF_BREWGUARD_WARHAMMER, InlineProfile(4, 3)),
        'pc-book-npc:dwarf_miner_pickaxe': (
            PcBookNpcProfile.DWARF_MINER_PICKAXE, InlineProfile(4, 3)),
        'pc-book-npc:bestigor_massive_axe': (
            PcBookNpcProfile.BESTIGOR_MASSIVE_AXE, InlineProfile(4, 4)),
    }
    if definition.id not in profiles:
        raise ValueError('Close Shooting protection requires an admitted canonical loadout')
    profile_id, melee = profiles[definition.id]
    if skill is Skill.MELEE:
        return NpcProtectionProfile(definition.source_rule_id+':close-shooting:melee',
            skill, melee)
    entry = get_pc_book_npc_entry(profile_id)
    return next(profile for profile in entry.unselected_protection
        if profile.skill is Skill.ATHLETICS)
