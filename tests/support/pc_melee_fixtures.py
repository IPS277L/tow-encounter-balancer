"""Small independent authored PC melee fixtures, without rule execution."""
from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.fate_models import FateSessionState
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.npc_roster_models import (
    NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile,
)
from towr.domain.pc_melee_models import (
    PcFatePolicy, PcMeleeDefinition, PcMeleeFacts, PcMeleePolicy, PcMeleeScenario,
    PcMeleeWeapon, PcRandomHandPolicy, PcWeaponHand,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatSide


def make_pc_melee_scenario(*, weapon: PcMeleeWeapon = PcMeleeWeapon.STAFF,
                           enemy_count: int = 1, max_rounds: int = 3) -> PcMeleeScenario:
    """An authored healthy PC and ordinary numeric Minions, not a bestiary entry."""
    if type(enemy_count) is not int:
        raise TypeError("enemy_count must be an integer")
    if enemy_count < 1:
        raise ValueError("enemy_count must be positive")
    pc = PcMeleeDefinition("pc-profile", 3, 3, 3, 3, 5, 5, 4, 4, weapon, 0)
    enemies = []
    for index in range(enemy_count):
        actor_id = f"minion{index + 1}"
        attack = NpcAttackProfile("club", "authored:minion:club", Skill.MELEE,
            InlineProfile(2, 4), DamageProfile(3), RangedWeaponRange.CLOSE,
            RangedWeaponRange.CLOSE, RangedWeaponHands.ONE_HANDED)
        definition = NpcDefinition("minion-profile", "authored:minion",
            TargetInjuryPolicy.MINION, 1, ResilienceProfile(3), (attack,),
            (NpcProtectionProfile("authored:minion:defence", Skill.DEFENCE, InlineProfile(2, 4)),))
        state = NpcParticipantState(actor_id, definition.id, CombatSide.OPPOSITION,
            ProfileInjuryState(0, 1), (attack.id,), definition.resilience, True, False)
        enemies.append(NpcParticipantSnapshot(definition, state))
    ids = tuple(enemy.state.actor_id for enemy in enemies)
    return PcMeleeScenario("pc-melee", "pc", pc, FateSessionState("session", "pc", 3, 3),
        "day", tuple(enemies), PcMeleeFacts("arena", True, True, True, True, True,
            True, True, True, True, False), PcMeleePolicy.ATTACK_OR_RECOVER_SELF,
        PcFatePolicy.DECLINE_OPTIONAL_FATE, PcRandomHandPolicy.D10_LOW_LEFT_HIGH_RIGHT,
        PcWeaponHand.LEFT, ids, ids,
        tuple(MinionDefeatDecision("pc", target, NpcDefeatDisposition.KNOCKED_OUT, True)
            for target in ids), max_rounds)
