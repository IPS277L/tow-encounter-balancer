"""Immutable authored input for the first PC melee encounter (ADR-0065)."""
from dataclasses import dataclass, replace
from enum import Enum

from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.condition_models import ConditionState
from towr.domain.fate_models import (
    FateBurnRecord, FateRefreshRecord, FateSessionState, FateSpendRecord,
)
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.minion_defeat_models import MinionDefeatDecision, NpcDefeatDisposition
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.npc_roster_models import (
    NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill, TestProfile
from towr.domain.turn_models import CombatSide


class PcMeleeWeapon(str, Enum):
    STAFF = "staff"
    SWORD = "sword"


class PcMeleePolicy(str, Enum):
    ATTACK_OR_RECOVER_SELF = "attack_or_recover_self"


class PcFatePolicy(str, Enum):
    DECLINE_OPTIONAL_FATE = "decline_optional_fate"


class PcRandomHandPolicy(str, Enum):
    D10_LOW_LEFT_HIGH_RIGHT = "d10_low_left_high_right"


class PcWeaponHand(str, Enum):
    LEFT = "left"
    RIGHT = "right"


@dataclass(frozen=True, slots=True)
class PcMeleeDefinition:
    id: str
    weapon_skill: int
    strength: int
    toughness: int
    agility: int
    melee: int
    defence: int
    athletics: int
    endurance: int
    weapon: PcMeleeWeapon
    armour_bonus: int

    def __post_init__(self) -> None:
        _identifier(self.id, "PC definition")
        for name in ("weapon_skill", "strength", "toughness", "agility"):
            _integer(getattr(self, name), name, minimum=1)
        for characteristic, skill in (
            (self.weapon_skill, self.melee), (self.weapon_skill, self.defence),
            (self.agility, self.athletics), (self.toughness, self.endurance),
        ):
            TestProfile(characteristic, skill)
        _typed(self.weapon, PcMeleeWeapon, "PC weapon")
        _integer(self.armour_bonus, "PC armour bonus", minimum=0)

    @property
    def melee_profile(self) -> TestProfile:
        return TestProfile(self.weapon_skill, self.melee)

    @property
    def defence_profile(self) -> TestProfile:
        return TestProfile(self.weapon_skill, self.defence)

    @property
    def athletics_profile(self) -> TestProfile:
        return TestProfile(self.agility, self.athletics)

    @property
    def endurance_profile(self) -> TestProfile:
        return TestProfile(self.toughness, self.endurance)

    @property
    def resilience(self) -> ResilienceProfile:
        return ResilienceProfile(self.toughness, self.armour_bonus)


@dataclass(frozen=True, slots=True)
class PcMeleeFacts:
    zone_id: str
    all_opponents_close: bool
    targets_aware: bool
    all_combatants_included: bool
    unmounted: bool
    no_external_effects: bool
    no_terrain_modifiers: bool
    no_additional_abilities: bool
    no_ambush: bool
    outnumbering_bonus_approved: bool
    can_leave_zone: bool

    def __post_init__(self) -> None:
        _identifier(self.zone_id, "PC melee Zone")
        for name in (
            "all_opponents_close", "targets_aware", "all_combatants_included",
            "unmounted", "no_external_effects", "no_terrain_modifiers",
            "no_additional_abilities", "no_ambush", "outnumbering_bonus_approved",
            "can_leave_zone",
        ):
            value = getattr(self, name)
            _typed(value, bool, name)
            if name not in ("outnumbering_bonus_approved", "can_leave_zone") and not value:
                raise ValueError(f"unsupported PC melee fact: {name}")


@dataclass(frozen=True, slots=True)
class PcMeleeParticipant:
    actor_id: str
    pc: PcMeleeDefinition
    fate: FateSessionState
    policy: PcMeleePolicy
    fate_policy: PcFatePolicy
    random_hand_policy: PcRandomHandPolicy
    initial_weapon_hand: PcWeaponHand
    target_priority: tuple[str, ...]
    defeat_decisions: tuple[MinionDefeatDecision, ...]

    def __post_init__(self) -> None:
        _identifier(self.actor_id, "PC actor")
        _typed(self.pc, PcMeleeDefinition, "PC definition")
        replace(self.pc)
        _readmit_fate(self.fate, self.actor_id)
        for name, cls in (("policy", PcMeleePolicy), ("fate_policy", PcFatePolicy),
                          ("random_hand_policy", PcRandomHandPolicy), ("initial_weapon_hand", PcWeaponHand)):
            _typed(getattr(self, name), cls, name)
        targets = _ordered(self.target_priority, "PC target priority")
        for target in targets:
            _identifier(target, "PC target")
        if not targets or len(set(targets)) != len(targets):
            raise ValueError("PC target priority must be nonempty and unique")
        decisions = _ordered(self.defeat_decisions, "defeat decisions")
        for decision in decisions:
            _typed(decision, MinionDefeatDecision, "defeat decision")
            _identifier(decision.attacker_id, "defeat attacker")
            _identifier(decision.target_id, "defeat target")
            _typed(decision.disposition, NpcDefeatDisposition, "defeat disposition")
            _typed(decision.gm_approved, bool, "defeat approval")
            replace(decision)
            if decision.attacker_id != self.actor_id or not decision.gm_approved:
                raise ValueError("defeat decisions require their PC and explicit GM approval")
        if tuple(item.target_id for item in decisions) != targets:
            raise ValueError("defeat decisions must follow the full PC target priority")
        object.__setattr__(self, "target_priority", targets)
        object.__setattr__(self, "defeat_decisions", decisions)

    def defeat_decision(self, target_id: str) -> MinionDefeatDecision:
        _identifier(target_id, "defeat target")
        for decision in self.defeat_decisions:
            if decision.target_id == target_id:
                return decision
        raise ValueError("unknown PC melee defeat target")


@dataclass(frozen=True, slots=True)
class PcMeleeScenario:
    id: str
    party: tuple[PcMeleeParticipant, ...]
    day_id: str
    enemies: tuple[NpcParticipantSnapshot, ...]
    facts: PcMeleeFacts
    pc_activation_order: tuple[str, ...]
    enemy_activation_order: tuple[str, ...]
    enemy_target_priority: tuple[str, ...]
    max_rounds: int

    def __post_init__(self) -> None:
        for name in ("id", "day_id"):
            _identifier(getattr(self, name), name)
        _typed(self.facts, PcMeleeFacts, "PC melee facts")
        replace(self.facts)
        _integer(self.max_rounds, "max rounds", minimum=1)
        party = _ordered(self.party, "party")
        enemies = _ordered(self.enemies, "enemies")
        if not party or not enemies:
            raise ValueError("PC melee requires a nonempty party and Minions")
        pc_definitions = {}
        for member in party:
            _typed(member, PcMeleeParticipant, "PC participant")
            _canonical_tuple(member.target_priority, "PC target priority")
            _canonical_tuple(member.defeat_decisions, "PC defeat decisions")
            replace(member)
            if member.pc.id in pc_definitions and pc_definitions[member.pc.id] != member.pc:
                raise ValueError("conflicting PC definitions with the same ID")
            pc_definitions[member.pc.id] = member.pc
        definitions = {}
        for enemy in enemies:
            _readmit_profile_enemy(enemy)
            definition = enemy.definition
            if definition.id in definitions and definitions[definition.id] != definition:
                raise ValueError("conflicting Minion definitions with the same ID")
            definitions[definition.id] = definition
        pc_ids = tuple(member.actor_id for member in party)
        enemy_ids = tuple(enemy.state.actor_id for enemy in enemies)
        all_ids = (*pc_ids, *enemy_ids)
        if len(set(all_ids)) != len(all_ids):
            raise ValueError("PC and Minion actor IDs must be distinct")
        for name, ids in (("pc_activation_order", pc_ids),
                          ("enemy_activation_order", enemy_ids), ("enemy_target_priority", pc_ids)):
            ordered = _ordered(getattr(self, name), name)
            for actor_id in ordered:
                _identifier(actor_id, name)
            if len(set(ordered)) != len(ordered) or set(ordered) != set(ids):
                raise ValueError(f"{name} must contain every member of its side exactly once")
            object.__setattr__(self, name, ordered)
        for member in party:
            if set(member.target_priority) != set(enemy_ids):
                raise ValueError("each PC target priority must include every Minion exactly once")
        object.__setattr__(self, "party", party)
        object.__setattr__(self, "enemies", enemies)

    def participant(self, actor_id: str) -> PcMeleeParticipant:
        _identifier(actor_id, "PC actor")
        for member in self.party:
            if member.actor_id == actor_id:
                return member
        raise ValueError("unknown PC melee participant")

    def enemy(self, actor_id: str) -> NpcParticipantSnapshot:
        _identifier(actor_id, "enemy actor")
        for enemy in self.enemies:
            if enemy.state.actor_id == actor_id:
                return enemy
        raise ValueError("unknown PC melee enemy")


def validate_pc_melee_scenario_admission(scenario: PcMeleeScenario) -> None:
    """Re-admit canonical full input before execution, including nested values."""
    _typed(scenario, PcMeleeScenario, "PC melee scenario")
    for name in ("party", "enemies", "pc_activation_order", "enemy_activation_order", "enemy_target_priority"):
        _canonical_tuple(getattr(scenario, name), name)
    replace(scenario)


def _readmit_fate(fate: FateSessionState, actor_id: str) -> None:
    _typed(fate, FateSessionState, "PC Fate state")
    _typed(fate.has_lucky, bool, "Lucky fact")
    for name, cls in (("spends", FateSpendRecord), ("refreshes", FateRefreshRecord),
                      ("burns", FateBurnRecord)):
        for item in _canonical_tuple(getattr(fate, name), f"Fate {name}"):
            _typed(item, cls, f"Fate {name} record")
            replace(item)
    _canonical_tuple(fate.resource_event_ids, "Fate resource event order")
    replace(fate)
    if fate.actor_id != actor_id:
        raise ValueError("Fate belongs to another PC")
    if fate.has_lucky:
        raise ValueError("Lucky is outside the first PC melee scenario")


def _readmit_profile_enemy(enemy: NpcParticipantSnapshot) -> None:
    _typed(enemy, NpcParticipantSnapshot, "Minion snapshot")
    definition, state = enemy.definition, enemy.state
    _typed(definition, NpcDefinition, "Minion definition")
    _typed(state, NpcParticipantState, "Minion state")
    for value, name in ((definition.id, "Minion definition ID"),
                        (definition.source_rule_id, "Minion source rule"),
                        (state.actor_id, "Minion actor ID"),
                        (state.definition_id, "Minion state definition ID")):
        _identifier(value, name)
    _typed(definition.injury_policy, TargetInjuryPolicy, "Minion injury policy")
    _typed(state.side, CombatSide, "Minion side")
    if definition.injury_policy not in (TargetInjuryPolicy.MINION, TargetInjuryPolicy.BRUTE) or state.side is not CombatSide.OPPOSITION:
        raise ValueError("PC melee enemies must be opposition Minions or Brutes")
    _integer(definition.wound_limit, "NPC profile wound limit", minimum=1)
    _readmit_resilience(definition.resilience)
    _readmit_resilience(state.current_resilience)
    attacks = _canonical_tuple(definition.attacks, "Minion attacks")
    protection = _canonical_tuple(definition.protection, "Minion protection")
    if len(attacks) != 1 or len(protection) != 1:
        raise ValueError("Minion requires one Melee attack and one Defence profile")
    attack, defence = attacks[0], protection[0]
    _typed(attack, NpcAttackProfile, "Minion attack")
    _typed(defence, NpcProtectionProfile, "Minion Defence")
    for value, name in ((attack.id, "Minion attack ID"),
                        (attack.source_rule_id, "Minion attack source"),
                        (defence.source_rule_id, "Minion Defence source")):
        _identifier(value, name)
    _typed(attack.skill, Skill, "Minion attack Skill")
    _typed(defence.skill, Skill, "Minion Protection Skill")
    _typed(attack.range_min, RangedWeaponRange, "Minion minimum Range")
    _typed(attack.range_max, RangedWeaponRange, "Minion maximum Range")
    _readmit_inline(attack.test_profile)
    _readmit_inline(defence.test_profile)
    _typed(attack.damage, DamageProfile, "Minion Damage")
    replace(attack.damage)
    _canonical_tuple(attack.secondary_effects, "Minion secondary effects")
    replace(attack)
    replace(defence)
    _typed(attack.ignores_armour, bool, "Minion ignores armour")
    _typed(attack.hands, RangedWeaponHands, "Minion weapon hands")
    if (attack.skill is not Skill.MELEE
            or attack.range_min is not RangedWeaponRange.CLOSE
            or attack.range_max is not RangedWeaponRange.CLOSE
            or attack.damage.success_multiplier != 1 or attack.ignores_armour
            or attack.secondary_effects or defence.skill is not Skill.DEFENCE):
        raise ValueError("unsupported Minion attack or Protection profile")
    injury = state.injury
    _typed(injury, ProfileInjuryState, "Minion injury")
    _typed(injury.conditions, ConditionState, "Minion Conditions")
    _typed(injury.conditions.conditions, frozenset, "Minion Condition set")
    replace(injury.conditions)
    replace(injury)
    _integer(injury.wounds, "NPC Wounds", minimum=0)
    _integer(injury.wound_limit, "NPC state wound limit", minimum=1)
    _typed(injury.defeated, bool, "NPC defeated flag")
    _typed(state.wields_weapon, bool, "NPC weapon eligibility")
    _typed(state.holds_shield, bool, "NPC shield eligibility")
    _canonical_tuple(state.available_attack_ids, "Minion available attacks")
    for attack_id in state.available_attack_ids:
        _identifier(attack_id, "available Minion attack ID")
    replace(state)
    replace(definition)
    replace(enemy)
    if (injury.wounds or injury.defeated or injury.conditions.conditions
            or not state.wields_weapon or state.holds_shield
            or state.current_resilience != definition.resilience
            or state.available_attack_ids != (attack.id,)):
        raise ValueError("PC melee requires fresh armed healthy Minions without shields")


def _readmit_inline(profile: InlineProfile) -> None:
    _typed(profile, InlineProfile, "Minion numeric profile")
    replace(profile)
    if profile.pool_cap is not None:
        raise ValueError("Minion profile must be unmodified")


def _readmit_resilience(value: ResilienceProfile) -> None:
    _typed(value, ResilienceProfile, "Minion Resilience")
    replace(value)


def _typed(value, cls, name: str) -> None:
    if type(value) is not cls:
        raise TypeError(f"{name} must be {cls.__name__}")


def _identifier(value: str, name: str) -> None:
    _typed(value, str, name)
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _integer(value: int, name: str, *, minimum: int) -> None:
    _typed(value, int, name)
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")


def _ordered(value, name: str) -> tuple:
    if type(value) not in (tuple, list):
        raise TypeError(f"{name} must be an ordered list or tuple")
    return tuple(value)


def _canonical_tuple(value, name: str) -> tuple:
    _typed(value, tuple, name)
    return value
