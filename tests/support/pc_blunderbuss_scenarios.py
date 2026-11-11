"""Independent Blunderbuss sources with an explicit initial NPC cluster."""
from dataclasses import replace

from tests.support.pc_bow_scenarios import make_pc_bow_scenario
from towr.domain.attack_models import ResilienceProfile
from towr.domain.pc_melee_models import (
    PcBlunderbussNearby, PcMeleeWeapon, PcRangedProfile, PcRangedReloadHandPolicy,
)


def blunderbuss_profile(*, ballistic_skill: int = 3, shooting: int = 4,
        initiative: int = 3, dexterity: int = 4) -> PcRangedProfile:
    return PcRangedProfile(ballistic_skill=ballistic_skill, shooting=shooting,
        initiative=initiative, dexterity=dexterity, has_blackpowder_lore=True,
        has_blackpowder_kit=True, ammunition_supply_confirmed=True,
        initially_loaded=True, reload_hand_policy=PcRangedReloadHandPolicy.TWO_AVAILABLE_HANDS)


def make_pc_blunderbuss_scenario(*, pc_count: int = 1, enemy_count: int = 1,
        max_rounds: int = 3, backup: bool = True, ballistic_skill: int = 3,
        shooting: int = 4, initiative: int = 3, dexterity: int = 4,
        npc_toughness: int = 3, npc_armour_bonus: int = 0,
        npc_armoured: bool | None = None, target_priority: tuple[str, ...] | None = None):
    source = make_pc_bow_scenario(pc_count=pc_count, enemy_count=enemy_count,
        max_rounds=max_rounds, backup=backup)
    party = tuple(replace(member, pc=replace(member.pc, weapon=PcMeleeWeapon.BLUNDERBUSS,
        ranged=blunderbuss_profile(ballistic_skill=ballistic_skill, shooting=shooting,
            initiative=initiative, dexterity=dexterity))) for member in source.party)
    resilience = ResilienceProfile(npc_toughness, npc_armour_bonus, armoured=npc_armoured)
    enemies = tuple(replace(enemy, definition=replace(enemy.definition, resilience=resilience),
        state=replace(enemy.state, current_resilience=resilience)) for enemy in source.enemies)
    order = source.enemy_activation_order if target_priority is None else target_priority
    return replace(source, id='pc-blunderbuss-short-opening', party=party, enemies=enemies,
        blunderbuss_nearby=PcBlunderbussNearby(True, order))
