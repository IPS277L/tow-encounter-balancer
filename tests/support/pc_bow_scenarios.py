"""Independent authored Short-opening sources, without preparing or rolling rules."""
from dataclasses import replace

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
from towr.domain.attack_models import ResilienceProfile
from towr.domain.pc_melee_models import (
    PcBackupWeaponPolicy, PcMeleeWeapon, PcRangedProfile, PcShortRangeOpening,
    PcTwoHandedGrip, PcWeaponHand,
)
from towr.domain.test_models import Skill


def bow_profile(*, ballistic_skill: int = 3, shooting: int = 4) -> PcRangedProfile:
    return PcRangedProfile(ballistic_skill=ballistic_skill, shooting=shooting,
        ammunition_supply_confirmed=True)


def make_pc_bow_scenario(*, weapon: PcMeleeWeapon = PcMeleeWeapon.SHORTBOW,
        pc_count: int = 1, enemy_count: int = 1, max_rounds: int = 3,
        backup: bool = True, ballistic_skill: int = 3, shooting: int = 4,
        npc_toughness: int = 3, npc_armour_bonus: int = 0):
    source = make_pc_melee_party_scenario(pc_count=pc_count,
        enemy_count=enemy_count, max_rounds=max_rounds)
    party = tuple(replace(member, pc=replace(member.pc, weapon=weapon,
        ranged=bow_profile(ballistic_skill=ballistic_skill, shooting=shooting)),
        initial_weapon_hand=PcTwoHandedGrip.BOTH,
        backup_weapon_policy=PcBackupWeaponPolicy(PcMeleeWeapon.SWORD, PcWeaponHand.RIGHT)
            if backup else None) for member in source.party)
    resilience = ResilienceProfile(npc_toughness, npc_armour_bonus)
    enemies = tuple(replace(enemy, definition=replace(enemy.definition,
        resilience=resilience,
        protection=(replace(enemy.definition.protection[0], skill=Skill.ATHLETICS),)),
        state=replace(enemy.state, current_resilience=resilience)) for enemy in source.enemies)
    return replace(source, id='pc-bows-short-opening', party=party, enemies=enemies,
        facts=replace(source.facts, all_opponents_close=False,
            can_leave_zone=False, outnumbering_bonus_approved=False),
        short_range_opening=PcShortRangeOpening(
            party_clustered_confirmed=True, npc_approach_clear_confirmed=True))
