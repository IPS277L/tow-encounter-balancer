"""Independent loaded ranged PC sources with explicit current profile facts."""
from dataclasses import replace

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
from towr.domain.pc_melee_models import (
    PcMeleeWeapon, PcRangedProfile, PcRangedReloadHandPolicy, PcRepeaterBonusPolicy,
    PcWeaponHand,
)
from towr.domain.test_models import Skill


def ranged_profile(*,weapon: PcMeleeWeapon = PcMeleeWeapon.REPEATER_HANDBOW,
        ballistic_skill: int = 3,shooting: int = 4,initiative: int = 3,dexterity: int = 4,
        repeater_bonus_policy: PcRepeaterBonusPolicy | None = PcRepeaterBonusPolicy.WHEN_AVAILABLE):
    """Ordinary Pistol callers must explicitly choose bonus policy None."""
    firearm = weapon in (PcMeleeWeapon.PISTOL,PcMeleeWeapon.REPEATER_PISTOL)
    return PcRangedProfile(ballistic_skill=ballistic_skill,shooting=shooting,
        initiative=initiative,dexterity=dexterity,
        has_blackpowder_lore=True if firearm else None,
        has_blackpowder_kit=True if firearm else None,
        ammunition_supply_confirmed=True,initially_loaded=True,
        reload_hand_policy=PcRangedReloadHandPolicy.TWO_AVAILABLE_HANDS,
        repeater_bonus_policy=repeater_bonus_policy)


def make_pc_ranged_scenario(*,weapon: PcMeleeWeapon = PcMeleeWeapon.REPEATER_HANDBOW,
        profile: PcRangedProfile | None = None,
        repeater_bonus_policy: PcRepeaterBonusPolicy | None = PcRepeaterBonusPolicy.WHEN_AVAILABLE,
        pc_count: int = 1,enemy_count: int = 1,max_rounds: int = 3,
        ballistic_skill: int = 3,shooting: int = 4,initiative: int = 3,dexterity: int = 4):
    source = make_pc_melee_party_scenario(pc_count=pc_count,enemy_count=enemy_count,max_rounds=max_rounds)
    selected = (ranged_profile(weapon=weapon,ballistic_skill=ballistic_skill,shooting=shooting,
        initiative=initiative,dexterity=dexterity,repeater_bonus_policy=repeater_bonus_policy)
        if profile is None else profile)
    party = tuple(replace(member,pc=replace(member.pc,weapon=weapon,ranged=selected),
        initial_weapon_hand=PcWeaponHand.RIGHT) for member in source.party)
    enemies = tuple(replace(enemy,definition=replace(enemy.definition,
        protection=(replace(enemy.definition.protection[0],skill=Skill.ATHLETICS),)))
        for enemy in source.enemies)
    return replace(source,id='pc-ranged',party=party,enemies=enemies,
        facts=replace(source.facts,outnumbering_bonus_approved=False))
