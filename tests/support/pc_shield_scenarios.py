"""Independent authored one-handed weapon and shield sources for M53."""
from dataclasses import replace

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.domain.pc_melee_models import (
    PcMeleeWeapon, PcShieldHandConflictPolicy, PcShieldLoadout,
    PcShieldRecoveryPolicy, PcWeaponHand,
)


def shield_loadout(hand: PcWeaponHand = PcWeaponHand.LEFT) -> PcShieldLoadout:
    return PcShieldLoadout(hand, PcShieldHandConflictPolicy.WEAPON_FIRST,
        PcShieldRecoveryPolicy.RESTORE_BEFORE_ATTACK)


def make_pc_shield_scenario(*, weapon: PcMeleeWeapon = PcMeleeWeapon.SWORD,
        weapon_hand: PcWeaponHand = PcWeaponHand.RIGHT, armour_bonus: int = 0,
        enemy_count: int = 1, max_rounds: int = 2):
    source = make_pc_melee_scenario(weapon=weapon, enemy_count=enemy_count, max_rounds=max_rounds)
    member = source.party[0]
    hand = PcWeaponHand.LEFT if weapon_hand is PcWeaponHand.RIGHT else PcWeaponHand.RIGHT
    return replace(source, party=(replace(member, pc=replace(member.pc, armour_bonus=armour_bonus),
        initial_weapon_hand=weapon_hand, shield=shield_loadout(hand)),))
