"""Independent authored Pistol PCs and lawful Shooting opposition for M54."""
from dataclasses import replace

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
from towr.domain.pc_melee_models import (
    PcMeleeScenario, PcMeleeWeapon, PcPistolProfile, PcPistolReloadHandPolicy,
)
from towr.domain.test_models import Skill


def pistol_profile(*, ballistic_skill: int = 3, shooting: int = 4,
        initiative: int = 3, dexterity: int = 4) -> PcPistolProfile:
    return PcPistolProfile(ballistic_skill, shooting, initiative, dexterity,
        True, True, True, True, PcPistolReloadHandPolicy.TWO_AVAILABLE_HANDS)


def make_pc_pistol_scenario(*, pc_count: int = 1, enemy_count: int = 1,
        max_rounds: int = 5, ballistic_skill: int = 3, shooting: int = 4,
        initiative: int = 3, dexterity: int = 4,
        profile: PcPistolProfile | None = None) -> PcMeleeScenario:
    """Fresh loaded, no-shield Pistol PCs against explicitly authored Athletics."""
    source = make_pc_melee_party_scenario(pc_count=pc_count,
        enemy_count=enemy_count, max_rounds=max_rounds)
    profile = (pistol_profile(ballistic_skill=ballistic_skill, shooting=shooting,
        initiative=initiative, dexterity=dexterity) if profile is None else profile)
    party = tuple(replace(member, pc=replace(member.pc,
        weapon=PcMeleeWeapon.PISTOL, pistol=profile)) for member in source.party)
    enemies = tuple(replace(enemy, definition=replace(enemy.definition,
        protection=(replace(enemy.definition.protection[0], skill=Skill.ATHLETICS),)))
        for enemy in source.enemies)
    return replace(source, id='pc-pistol', party=party, enemies=enemies)
