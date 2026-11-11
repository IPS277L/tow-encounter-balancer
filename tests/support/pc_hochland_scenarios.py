"""Independent Hochland sources with explicit Aim and Second Action choices."""
from dataclasses import replace

from tests.support.pc_bow_scenarios import make_pc_bow_scenario
from towr.domain.attack_models import ResilienceProfile
from towr.domain.pc_melee_models import (
    PcAimSecondActionPolicy, PcFatePolicy, PcMeleeWeapon, PcRangedProfile,
    PcRangedReloadHandPolicy,
)


def hochland_profile(*, ballistic_skill: int = 3, shooting: int = 4,
        initiative: int = 3, dexterity: int = 4, awareness: int = 4):
    return PcRangedProfile(ballistic_skill=ballistic_skill, shooting=shooting,
        initiative=initiative, dexterity=dexterity, awareness=awareness,
        has_blackpowder_lore=True, has_blackpowder_kit=True,
        ammunition_supply_confirmed=True, initially_loaded=True,
        reload_hand_policy=PcRangedReloadHandPolicy.TWO_AVAILABLE_HANDS)


def make_pc_hochland_scenario(*, pc_count: int = 1, enemy_count: int = 1,
        max_rounds: int = 3, backup: bool = True,
        ballistic_skill: int = 3, shooting: int = 4,
        initiative: int = 3, dexterity: int = 4, awareness: int = 4,
        fate_rating: int = 1, reserve: int = 0, use_second_action: bool = True,
        has_lucky: bool = False, npc_toughness: int = 3,
        npc_armour_bonus: int = 0, npc_armoured: bool | None = None):
    source = make_pc_bow_scenario(pc_count=pc_count, enemy_count=enemy_count,
        max_rounds=max_rounds, backup=backup)
    party = tuple(replace(member, pc=replace(member.pc,
        weapon=PcMeleeWeapon.HOCHLAND_LONG_RIFLE,
        ranged=hochland_profile(ballistic_skill=ballistic_skill, shooting=shooting,
            initiative=initiative, dexterity=dexterity, awareness=awareness)),
        fate=replace(member.fate, rating=fate_rating, session_spend_limit=fate_rating,
            has_lucky=has_lucky),
        fate_policy=PcFatePolicy.CONFIGURED if use_second_action else PcFatePolicy.DECLINE_OPTIONAL_FATE,
        aim_second_action_policy=PcAimSecondActionPolicy(reserve) if use_second_action else None)
        for member in source.party)
    resilience = ResilienceProfile(npc_toughness, npc_armour_bonus, armoured=npc_armoured)
    enemies = tuple(replace(enemy, definition=replace(enemy.definition, resilience=resilience),
        state=replace(enemy.state, current_resilience=resilience)) for enemy in source.enemies)
    return replace(source, id='pc-hochland-short-opening', party=party, enemies=enemies)
