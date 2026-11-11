"""Independent Sling sources for the existing single-Zone Short opening."""
from dataclasses import replace

from tests.support.pc_bow_scenarios import make_pc_bow_scenario
from tests.support.pc_shield_scenarios import shield_loadout
from towr.domain.attack_models import ResilienceProfile
from towr.domain.pc_melee_models import (
    PcBackupWeaponPolicy, PcMeleeWeapon, PcRangedProfile, PcWeaponHand,
)


def sling_profile(*, ballistic_skill: int = 3, shooting: int = 4) -> PcRangedProfile:
    return PcRangedProfile(ballistic_skill=ballistic_skill, shooting=shooting,
        ammunition_supply_confirmed=True)


def make_pc_sling_scenario(*, pc_count: int = 1, enemy_count: int = 1,
        max_rounds: int = 3, backup: bool = True, strength: int = 3,
        ballistic_skill: int = 3, shooting: int = 4, shield: bool = False,
        initial_hand: PcWeaponHand = PcWeaponHand.RIGHT,
        backup_hand: PcWeaponHand = PcWeaponHand.RIGHT,
        npc_toughness: int = 3, npc_armour_bonus: int = 0,
        npc_armoured: bool | None = None):
    source = make_pc_bow_scenario(pc_count=pc_count, enemy_count=enemy_count,
        max_rounds=max_rounds, backup=backup)
    shield_hand = PcWeaponHand.LEFT if initial_hand is PcWeaponHand.RIGHT else PcWeaponHand.RIGHT
    party = tuple(replace(member, pc=replace(member.pc, weapon=PcMeleeWeapon.SLING,
        strength=strength, ranged=sling_profile(ballistic_skill=ballistic_skill, shooting=shooting)),
        initial_weapon_hand=initial_hand,
        backup_weapon_policy=PcBackupWeaponPolicy(PcMeleeWeapon.SWORD, backup_hand) if backup else None,
        shield=shield_loadout(shield_hand) if shield else None) for member in source.party)
    resilience = ResilienceProfile(npc_toughness, npc_armour_bonus, armoured=npc_armoured)
    enemies = tuple(replace(enemy, definition=replace(enemy.definition, resilience=resilience),
        state=replace(enemy.state, current_resilience=resilience)) for enemy in source.enemies)
    return replace(source, id='pc-sling-short-opening', party=party, enemies=enemies)
