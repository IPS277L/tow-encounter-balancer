from __future__ import annotations

from dataclasses import dataclass

from towr.domain.attack_models import (
    AttackRequest, DamageImpactSpec, DamageProfile, ResilienceProfile, SecondaryEffectSpec,
)
from towr.domain.protection_models import ProtectionPreparationRequest, ProtectionPreparationResult
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.test_models import DiceModifier, InlineProfile, Skill, TestRequest


NPC_ATTACK_PREPARATION_RULE_ID = "RULE-NPC-007:attack-preparation"
NPC_ATTACK_SELECTION_RULE_ID = "RULE-NPC-006:available-attack-selection"
NPC_ATTACK_TRAITS_RULE_ID = "RULE-NPC-010:explicit-attack-traits"
NPC_ATTACK_RANGE_RULE_ID = "RULE-NPC-007:attack-range"
NPC_OUTSIDE_OPTIMUM_RULE_ID = "RULE-NPC-007:outside-optimum"


@dataclass(frozen=True, slots=True)
class NpcAttackProfile:
    id: str
    source_rule_id: str
    skill: Skill
    test_profile: InlineProfile
    damage: DamageProfile
    range_min: RangedWeaponRange
    range_max: RangedWeaponRange
    hands: RangedWeaponHands
    ignores_armour: bool = False
    secondary_effects: tuple[SecondaryEffectSpec, ...] = ()

    def __post_init__(self) -> None:
        _non_empty(self.id, "NPC attack profile id")
        _non_empty(self.source_rule_id, "NPC attack source rule")
        if not isinstance(self.skill, Skill):
            raise TypeError("NPC attack skill must be a Skill")
        if self.skill not in (Skill.MELEE, Skill.SHOOTING):
            raise ValueError("NPC attack preparation currently supports Melee/Shooting")
        if not isinstance(self.test_profile, InlineProfile):
            raise TypeError("NPC attack requires an InlineProfile")
        if not isinstance(self.damage, DamageProfile):
            raise TypeError("NPC attack requires a numeric DamageProfile")
        if not isinstance(self.hands, RangedWeaponHands):
            raise TypeError("NPC attack hands must be explicit")
        if not isinstance(self.ignores_armour, bool):
            raise TypeError("ignores_armour must be a boolean")
        if _rank(self.range_min) > _rank(self.range_max):
            raise ValueError("NPC attack range must be ordered")
        if self.skill is Skill.MELEE and self.range_min is not RangedWeaponRange.CLOSE:
            raise ValueError("Melee profile gives maximum range, starting at Close")
        effects = tuple(self.secondary_effects)
        if not all(isinstance(effect, SecondaryEffectSpec) for effect in effects):
            raise TypeError("NPC secondary effects must be typed effect specs")
        if len({effect.rule_id for effect in effects}) != len(effects):
            raise ValueError("NPC secondary effect rules must be unique")
        object.__setattr__(self, "secondary_effects", effects)


@dataclass(frozen=True, slots=True)
class NpcAttackSelectionSnapshot:
    id: str
    actor_id: str
    profiles: tuple[NpcAttackProfile, ...]
    available_attack_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _non_empty(self.id, "NPC attack snapshot id")
        _non_empty(self.actor_id, "NPC actor id")
        profiles = tuple(self.profiles)
        if not all(isinstance(profile, NpcAttackProfile) for profile in profiles):
            raise TypeError("profiles must contain NpcAttackProfile values")
        profile_ids = {profile.id for profile in profiles}
        if len(profile_ids) != len(profiles):
            raise ValueError("NPC attack profile IDs must be unique")
        available = tuple(self.available_attack_ids)
        for attack_id in available:
            _non_empty(attack_id, "available attack id")
        if len(set(available)) != len(available) or not set(available) <= profile_ids:
            raise ValueError("available attacks must be distinct known profile IDs")
        object.__setattr__(self, "profiles", profiles)
        object.__setattr__(self, "available_attack_ids", available)


@dataclass(frozen=True, slots=True)
class NpcAttackPreparationRequest:
    id: str
    attack_id: str
    attacker_test_id: str
    snapshot: NpcAttackSelectionSnapshot
    selected_attack_id: str
    target_id: str
    target_range: RangedWeaponRange
    target_resilience: ResilienceProfile
    has_enemy_in_close_range: bool
    attacker_is_staggered: bool
    range_approved_by_gm: bool
    dice_modifiers: tuple[DiceModifier, ...] = ()
    rule_id: str = NPC_ATTACK_PREPARATION_RULE_ID

    def __post_init__(self) -> None:
        for value in (self.id, self.attack_id, self.attacker_test_id, self.selected_attack_id, self.target_id):
            _non_empty(value, "NPC attack request ID")
        if not isinstance(self.snapshot, NpcAttackSelectionSnapshot):
            raise TypeError("snapshot must be a NpcAttackSelectionSnapshot")
        if self.target_id == self.snapshot.actor_id:
            raise ValueError("NPC attack target must differ from actor")
        _rank(self.target_range)
        if not isinstance(self.target_resilience, ResilienceProfile):
            raise TypeError("target_resilience must be a ResilienceProfile")
        for value in (self.has_enemy_in_close_range, self.attacker_is_staggered, self.range_approved_by_gm):
            if not isinstance(value, bool):
                raise TypeError("NPC attack context requires explicit booleans")
        modifiers = tuple(self.dice_modifiers)
        if not all(isinstance(modifier, DiceModifier) for modifier in modifiers):
            raise TypeError("NPC attack modifiers must be DiceModifier values")
        if any(modifier.rule_id == NPC_OUTSIDE_OPTIMUM_RULE_ID for modifier in modifiers):
            raise ValueError("NPC range modifier is owned by preparation")
        if self.rule_id != NPC_ATTACK_PREPARATION_RULE_ID:
            raise ValueError("unknown NPC attack preparation rule")
        object.__setattr__(self, "dice_modifiers", modifiers)
        _expected_npc_attack(self)


@dataclass(frozen=True, slots=True)
class NpcAttackPreparationResult:
    request_id: str
    source_request: NpcAttackPreparationRequest
    snapshot: NpcAttackSelectionSnapshot
    target_id: str
    selected_profile: NpcAttackProfile
    attack: AttackRequest
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, NpcAttackPreparationRequest):
            raise TypeError("source_request must be a NpcAttackPreparationRequest")
        expected = _expected_npc_attack(self.source_request)
        if (self.request_id != self.source_request.id
                or self.snapshot != self.source_request.snapshot
                or self.target_id != self.source_request.target_id
                or (self.selected_profile, self.attack, tuple(self.applied_rule_ids)) != expected):
            raise ValueError("NPC attack preparation has stale source/profile/attack/trace")
        object.__setattr__(self, "applied_rule_ids", expected[2])


@dataclass(frozen=True, slots=True)
class NpcProtectedAttackPreparationResult:
    npc_attack: NpcAttackPreparationResult
    protection: ProtectionPreparationResult
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.protection, ProtectionPreparationResult):
            raise TypeError("protection must be a ProtectionPreparationResult")
        _validate_protection_pair(self.npc_attack, self.protection.source_request)
        expected = tuple(dict.fromkeys((*self.npc_attack.applied_rule_ids, *self.protection.applied_rule_ids)))
        if tuple(self.applied_rule_ids) != expected:
            raise ValueError("NPC attack/protection trace is inconsistent")
        object.__setattr__(self, "applied_rule_ids", expected)

    @property
    def attack(self) -> AttackRequest:
        return self.protection.attack


def _validate_protection_pair(npc: NpcAttackPreparationResult, protection: ProtectionPreparationRequest) -> None:
    if not isinstance(npc, NpcAttackPreparationResult):
        raise TypeError("npc_attack must be a NpcAttackPreparationResult")
    if not isinstance(protection, ProtectionPreparationRequest):
        raise TypeError("protection must be a ProtectionPreparationRequest")
    if (protection.attack != npc.attack or protection.attack_skill is not npc.selected_profile.skill
            or protection.defender_id != npc.source_request.target_id):
        raise ValueError("Protection does not match the exact prepared NPC attack/skill/target")


def _expected_npc_attack(request: NpcAttackPreparationRequest) -> tuple[NpcAttackProfile, AttackRequest, tuple[str, ...]]:
    if request.selected_attack_id not in request.snapshot.available_attack_ids:
        raise ValueError("selected NPC attack is unknown or unavailable")
    profile = next(p for p in request.snapshot.profiles if p.id == request.selected_attack_id)
    target = request.target_range
    modifiers = request.dice_modifiers
    rules = (request.rule_id, NPC_ATTACK_SELECTION_RULE_ID, profile.source_rule_id,
             NPC_ATTACK_TRAITS_RULE_ID, NPC_ATTACK_RANGE_RULE_ID)
    if target is RangedWeaponRange.EXTREME:
        raise ValueError("NPC preparation currently excludes Extreme/Aim composition")
    if profile.skill is Skill.MELEE:
        if _rank(target) > _rank(profile.range_max):
            raise ValueError("target exceeds NPC Melee maximum range")
        if request.range_approved_by_gm:
            raise ValueError("GM range approval cannot extend Melee range")
    else:
        if (target is RangedWeaponRange.CLOSE or request.has_enemy_in_close_range) and profile.range_min is not RangedWeaponRange.CLOSE:
            raise ValueError("NPC Shooting requires Close in Optimum when an enemy is Close")
        if profile.hands is RangedWeaponHands.ONE_HANDED and _rank(target) > _rank(RangedWeaponRange.LONG):
            raise ValueError("one-handed Shooting maximum range is Long")
        beyond = _rank(target) > _rank(profile.range_max)
        needs_approval = profile.hands is RangedWeaponHands.TWO_HANDED and beyond
        if needs_approval and not request.range_approved_by_gm:
            raise ValueError("two-handed Shooting beyond Optimum needs explicit GM approval")
        if request.range_approved_by_gm and not needs_approval:
            raise ValueError("GM range approval is not applicable here")
        if not _rank(profile.range_min) <= _rank(target) <= _rank(profile.range_max):
            modifiers = (*modifiers, DiceModifier(NPC_OUTSIDE_OPTIMUM_RULE_ID, -1))
            rules = (*rules, NPC_OUTSIDE_OPTIMUM_RULE_ID)
    attack = AttackRequest(
        request.attack_id, TestRequest(request.attacker_test_id, profile.test_profile, dice_modifiers=modifiers),
        None, DamageImpactSpec(profile.damage, request.target_resilience, ignores_armour=profile.ignores_armour),
        target is RangedWeaponRange.CLOSE, request.attacker_is_staggered,
        secondary_effects=profile.secondary_effects,
    )
    return profile, attack, tuple(dict.fromkeys((*rules, *(m.rule_id for m in request.dice_modifiers),
                                             *(effect.rule_id for effect in profile.secondary_effects))))


def _rank(value: RangedWeaponRange) -> int:
    if not isinstance(value, RangedWeaponRange):
        raise TypeError("range must be a RangedWeaponRange")
    return tuple(RangedWeaponRange).index(value)


def _non_empty(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
