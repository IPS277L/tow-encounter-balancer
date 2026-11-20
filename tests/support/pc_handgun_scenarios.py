"""Independent firearm sources for the existing Short-opening scenario."""
from dataclasses import replace

from tests.support.pc_bow_scenarios import make_pc_bow_scenario
from tests.support.pc_weapon_sources import initial_weapon_items
from towr.domain.attack_models import ResilienceProfile
from towr.domain.pc_melee_models import (
    PcMeleeWeapon, PcRangedProfile, PcRangedReloadHandPolicy, PcRepeaterBonusPolicy,
)


def handgun_profile(*, weapon: PcMeleeWeapon=PcMeleeWeapon.HANDGUN, ballistic_skill: int=3, shooting: int=4, repeater_bonus_policy: PcRepeaterBonusPolicy | None=None):
    """Callers supply Repeater policy explicitly; facts do not infer strategy."""
    return PcRangedProfile(ballistic_skill=ballistic_skill, shooting=shooting,  has_blackpowder_lore=True, has_blackpowder_kit=True, ammunition_supply_confirmed=True, reload_hand_policy=PcRangedReloadHandPolicy.TWO_AVAILABLE_HANDS, repeater_bonus_policy=repeater_bonus_policy)


def make_pc_handgun_scenario(*, weapon: PcMeleeWeapon = PcMeleeWeapon.HANDGUN,
        pc_count: int = 1, enemy_count: int = 1, max_rounds: int = 3,
        backup: bool = True, ballistic_skill: int = 3, shooting: int = 4,
        initiative: int = 3, dexterity: int = 4,
        repeater_bonus_policy: PcRepeaterBonusPolicy | None = None,
        npc_toughness: int = 3, npc_armour_bonus: int = 0,
        npc_armoured: bool | None = None):
    source = make_pc_bow_scenario(pc_count=pc_count, enemy_count=enemy_count,
        max_rounds=max_rounds, backup=backup)
    party = tuple(replace(member, pc=replace(member.pc, weapon=weapon,
        ranged=handgun_profile(weapon=weapon, ballistic_skill=ballistic_skill, shooting=shooting, repeater_bonus_policy=repeater_bonus_policy), initiative=initiative, dexterity=dexterity),combat_equipment=initial_weapon_items(
                weapon,member.initial_weapon_hand,member.backup_weapon_policy,initially_loaded=True)) for member in source.party)
    resilience = ResilienceProfile(npc_toughness, npc_armour_bonus, armoured=npc_armoured)
    enemies = tuple(replace(enemy, definition=replace(enemy.definition, resilience=resilience),
        state=replace(enemy.state, current_resilience=resilience)) for enemy in source.enemies)
    return replace(source, id='pc-handguns-short-opening', party=party, enemies=enemies)
