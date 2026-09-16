from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.aim_models import (
    AIM_FOLLOW_UP_RULE_ID,
    AimActionExecutionResult,
    AimFollowUpOutcome,
    AimFollowUpRequest,
    AimFollowUpResult,
    _expected_follow_up,
)
from towr.domain.attack_models import (
    DamageImpactSpec,
    DamageModifier,
    DamageProfile,
    NearbyTargetsStaggerSpec,
)
from towr.domain.injury_models import WoundDiceModifier
from towr.domain.ranged_weapon_attack_models import (
    RangedWeaponAttackExecutionRequest,
)
from towr.domain.ranged_weapon_profiles import (
    RANGED_WEAPON_PROFILE_RULE_ID,
    RangedWeaponCombatProfile,
    RangedWeaponDamageKind,
    RangedWeaponRange,
    ranged_weapon_combat_profile,
)
from towr.domain.reload_models import (
    FreeReloadWeaponState,
    RangedWeaponReloadState,
    ReloadableWeaponState,
)
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import DiceModifier, Skill
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind


RANGED_WEAPON_ATTACK_PREPARATION_RULE_ID = (
    "RULE-EQUIPMENT-004:ranged-attack-preparation"
)
CLOSE_ENEMY_RANGED_RESTRICTION_RULE_ID = (
    "RULE-EQUIPMENT-004:close-enemy-restriction"
)
OUTSIDE_OPTIMUM_RANGE_RULE_ID = "RULE-COMBAT-006:outside-optimum-range"
EXTREME_RANGE_AIM_RULE_ID = "RULE-COMBAT-004:extreme-range-aim"
SHORT_RANGE_SHOOTING_BONUS_RULE_ID = (
    "RULE-EQUIPMENT-004:short-range-shooting-bonus"
)
ARMOURED_TARGET_DAMAGE_BONUS_RULE_ID = (
    "RULE-EQUIPMENT-004:armoured-target-damage-bonus"
)
IGNORES_ARMOUR_RULE_ID = "RULE-EQUIPMENT-004:ignores-armour"
WEAPON_REQUIRES_AIM_RULE_ID = "RULE-EQUIPMENT-004:weapon-requires-aim"
BLACKPOWDER_LORE_REQUIREMENT_RULE_ID = (
    "RULE-EQUIPMENT-004:blackpowder-lore-requirement"
)
WOUNDS_TABLE_BONUS_RULE_ID = "RULE-EQUIPMENT-004:wounds-table-bonus"
BLUNDERBUSS_NEARBY_STAGGER_RULE_ID = (
    "RULE-EFFECT-006:blunderbuss-nearby-stagger"
)


_PROFILE_DICE_RULE_IDS = {
    OUTSIDE_OPTIMUM_RANGE_RULE_ID,
    SHORT_RANGE_SHOOTING_BONUS_RULE_ID,
}
_PROFILE_DAMAGE_RULE_IDS = {ARMOURED_TARGET_DAMAGE_BONUS_RULE_ID}
_PROFILE_WOUND_RULE_IDS = {WOUNDS_TABLE_BONUS_RULE_ID}
_PROFILE_SECONDARY_RULE_IDS = {BLUNDERBUSS_NEARBY_STAGGER_RULE_ID}


@dataclass(frozen=True, slots=True)
class RangedWeaponAttackPreparationRequest:
    id: str
    weapon_state: RangedWeaponReloadState
    attack: AttackActionExecutionRequest
    target_range: RangedWeaponRange
    attacker_strength: int
    has_blackpowder_lore: bool
    has_enemy_in_close_range: bool
    next_reload_cycle_id: str | None = None
    uses_optional_reload_bonus: bool = False
    aim: AimActionExecutionResult | None = None
    range_approved_by_gm: bool = False
    rule_id: str = RANGED_WEAPON_ATTACK_PREPARATION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "preparation request id")
        if not isinstance(
            self.weapon_state,
            (FreeReloadWeaponState, ReloadableWeaponState),
        ):
            raise TypeError("weapon_state must be a ranged reload state")
        if not isinstance(self.attack, AttackActionExecutionRequest):
            raise TypeError("attack must be an AttackActionExecutionRequest")
        if not isinstance(self.target_range, RangedWeaponRange):
            raise TypeError("target_range must be a RangedWeaponRange")
        _validate_positive_int(self.attacker_strength, "attacker_strength")
        _validate_bool(self.has_blackpowder_lore, "has_blackpowder_lore")
        _validate_bool(self.has_enemy_in_close_range, "has_enemy_in_close_range")
        if self.next_reload_cycle_id is not None:
            _validate_non_empty_string(
                self.next_reload_cycle_id,
                "next_reload_cycle_id",
            )
        _validate_bool(
            self.uses_optional_reload_bonus,
            "uses_optional_reload_bonus",
        )
        if self.aim is not None and not isinstance(
            self.aim,
            AimActionExecutionResult,
        ):
            raise TypeError("aim must be an AimActionExecutionResult or None")
        _validate_bool(
            self.range_approved_by_gm,
            "range_approved_by_gm",
        )
        _validate_non_empty_string(self.rule_id, "preparation rule_id")
        if self.rule_id != RANGED_WEAPON_ATTACK_PREPARATION_RULE_ID:
            raise ValueError("ranged Attack preparation uses an unknown rule")
        if self.id == self.attack.id:
            raise ValueError("preparation and Attack request IDs must differ")

        profile = ranged_weapon_combat_profile(self.weapon_state.weapon_id)
        _validate_attack_shape(self.attack)
        _validate_profile_preconditions(self, profile)
        _validate_no_profile_effects(self.attack)


@dataclass(frozen=True, slots=True)
class RangedWeaponAttackPreparationResult:
    request_id: str
    rule_id: str
    source_request: RangedWeaponAttackPreparationRequest
    profile: RangedWeaponCombatProfile
    profile_attack: AttackActionExecutionRequest
    aim_follow_up: AimFollowUpResult | None
    execution: RangedWeaponAttackExecutionRequest
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "preparation request_id")
        _validate_non_empty_string(self.rule_id, "preparation result rule_id")
        if not isinstance(
            self.source_request,
            RangedWeaponAttackPreparationRequest,
        ):
            raise TypeError(
                "source_request must be a ranged Attack preparation request"
            )
        if not isinstance(self.profile, RangedWeaponCombatProfile):
            raise TypeError("profile must be a RangedWeaponCombatProfile")
        if not isinstance(self.profile_attack, AttackActionExecutionRequest):
            raise TypeError("profile_attack must be an Attack action request")
        if self.aim_follow_up is not None and not isinstance(
            self.aim_follow_up,
            AimFollowUpResult,
        ):
            raise TypeError("aim_follow_up must be an AimFollowUpResult or None")
        if not isinstance(self.execution, RangedWeaponAttackExecutionRequest):
            raise TypeError("execution must be a ranged weapon Attack request")

        source = self.source_request
        if self.request_id != source.id or self.rule_id != source.rule_id:
            raise ValueError("ranged Attack preparation result is stale")
        expected_profile = ranged_weapon_combat_profile(
            source.weapon_state.weapon_id
        )
        if self.profile != expected_profile:
            raise ValueError("preparation result uses another weapon profile")
        expected_attack = _profile_prepared_attack(source)
        if self.profile_attack != expected_attack:
            raise ValueError("profile-prepared Attack is inconsistent")
        expected_aim = _aim_follow_up_for(source, expected_attack)
        if self.aim_follow_up != expected_aim:
            raise ValueError("prepared Aim follow-up is inconsistent")
        expected_execution = _execution_for(
            source,
            expected_aim.attack if expected_aim is not None else expected_attack,
        )
        if self.execution != expected_execution:
            raise ValueError("prepared ranged execution is inconsistent")

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        if rule_ids != _applied_rule_ids(source, expected_profile, expected_aim):
            raise ValueError("ranged Attack preparation trace is inconsistent")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


def _profile_prepared_attack(
    request: RangedWeaponAttackPreparationRequest,
) -> AttackActionExecutionRequest:
    profile = ranged_weapon_combat_profile(request.weapon_state.weapon_id)
    kernel = request.attack.kernel_request
    attack = kernel.attack
    impact = attack.impact_spec
    assert isinstance(impact, DamageImpactSpec)

    dice_modifiers = list(attack.attacker_test.dice_modifiers)
    if not _within_optimum(profile, request.target_range):
        dice_modifiers.append(DiceModifier(OUTSIDE_OPTIMUM_RANGE_RULE_ID, -1))
    if (
        request.target_range is RangedWeaponRange.SHORT
        and profile.short_range_shooting_bonus_dice
    ):
        dice_modifiers.append(
            DiceModifier(
                SHORT_RANGE_SHOOTING_BONUS_RULE_ID,
                profile.short_range_shooting_bonus_dice,
            )
        )

    damage_base = (
        request.attacker_strength
        if profile.damage_kind is RangedWeaponDamageKind.STRENGTH
        else profile.damage_value
    )
    assert damage_base is not None
    damage_modifiers = list(impact.damage_modifiers)
    if profile.armoured_target_damage_bonus and impact.resilience.is_armoured:
        damage_modifiers.append(
            DamageModifier(
                ARMOURED_TARGET_DAMAGE_BONUS_RULE_ID,
                profile.armoured_target_damage_bonus,
            )
        )
    prepared_impact = replace(
        impact,
        damage=DamageProfile(damage_base),
        ignores_armour=impact.ignores_armour or profile.ignores_armour,
        damage_modifiers=tuple(damage_modifiers),
    )

    secondary_effects = list(attack.secondary_effects)
    if profile.staggers_nearby_targets_on_hit:
        secondary_effects.append(
            NearbyTargetsStaggerSpec(BLUNDERBUSS_NEARBY_STAGGER_RULE_ID)
        )

    wound_modifiers = list(kernel.wound_dice_modifiers)
    if profile.wounds_table_bonus_dice and kernel.target_policy in {
        TargetInjuryPolicy.PLAYER,
        TargetInjuryPolicy.CHAMPION,
    }:
        wound_modifiers.append(
            WoundDiceModifier(
                WOUNDS_TABLE_BONUS_RULE_ID,
                profile.wounds_table_bonus_dice,
            )
        )

    prepared_test = replace(
        attack.attacker_test,
        dice_modifiers=tuple(dice_modifiers),
    )
    prepared_attack = replace(
        attack,
        attacker_test=prepared_test,
        impact_spec=prepared_impact,
        is_close_range=request.target_range is RangedWeaponRange.CLOSE,
        secondary_effects=tuple(secondary_effects),
    )
    return replace(
        request.attack,
        kernel_request=replace(
            kernel,
            attack=prepared_attack,
            wound_dice_modifiers=tuple(wound_modifiers),
        ),
    )


def _aim_follow_up_for(
    request: RangedWeaponAttackPreparationRequest,
    profile_attack: AttackActionExecutionRequest,
) -> AimFollowUpResult | None:
    if request.aim is None:
        return None
    follow_up_request = AimFollowUpRequest(
        id=f"{request.id}:aim-follow-up",
        aim=request.aim,
        actor_id=profile_attack.actor_id,
        next_action_id=profile_attack.id,
        declaration=CombatActionDeclaration(CombatActionKind.ATTACK),
        attack_skill=Skill.SHOOTING,
        attack=profile_attack,
    )
    outcome, attack, modifier = _expected_follow_up(follow_up_request)
    return AimFollowUpResult(
        request_id=follow_up_request.id,
        rule_id=AIM_FOLLOW_UP_RULE_ID,
        source_request=follow_up_request,
        outcome=outcome,
        attack=attack,
        modifier=modifier,
        applied_rule_ids=(AIM_FOLLOW_UP_RULE_ID, request.aim.rule_id),
    )


def _execution_for(
    request: RangedWeaponAttackPreparationRequest,
    attack: AttackActionExecutionRequest,
) -> RangedWeaponAttackExecutionRequest:
    return RangedWeaponAttackExecutionRequest(
        id=f"{request.id}:execution",
        attack_skill=Skill.SHOOTING,
        attack=attack,
        weapon_state=request.weapon_state,
        next_reload_cycle_id=request.next_reload_cycle_id,
        uses_optional_reload_bonus=request.uses_optional_reload_bonus,
    )


def _validate_attack_shape(attack: AttackActionExecutionRequest) -> None:
    if not isinstance(attack.kernel_request.attack.impact_spec, DamageImpactSpec):
        raise TypeError("ranged weapon preparation requires normal Damage")


def _validate_profile_preconditions(
    request: RangedWeaponAttackPreparationRequest,
    profile: RangedWeaponCombatProfile,
) -> None:
    if (
        request.has_enemy_in_close_range
        and profile.optimum_range_min is not RangedWeaponRange.CLOSE
    ):
        raise ValueError(
            "an enemy in Close Range prevents use of this ranged weapon"
        )
    if (
        profile.requires_blackpowder_lore
        and not request.has_blackpowder_lore
    ):
        raise ValueError("this weapon requires Blackpowder Lore")
    if request.aim is not None:
        if (
            request.aim.bonus.actor_id != request.attack.actor_id
            or request.aim.bonus.target_id != request.attack.target_id
        ):
            raise ValueError("Aim belongs to another actor or target")
    if profile.requires_aim_before_attack and request.aim is None:
        raise ValueError("this weapon requires Aim before attacking")

    if request.target_range is RangedWeaponRange.CLOSE and (
        profile.optimum_range_min is not RangedWeaponRange.CLOSE
    ):
        raise ValueError("this ranged weapon cannot attack at Close Range")
    maximum = profile.maximum_range
    if (
        maximum is not None
        and _range_rank(request.target_range) > _range_rank(maximum)
    ):
        raise ValueError("target is beyond the weapon's fixed Maximum Range")
    if request.target_range is RangedWeaponRange.EXTREME:
        if request.aim is None or not request.range_approved_by_gm:
            raise ValueError("Extreme Range requires Aim and GM approval")
    beyond_gm_defined_optimum = (
        profile.has_gm_defined_maximum_range
        and _range_rank(request.target_range)
        > _range_rank(profile.optimum_range_max)
    )
    if beyond_gm_defined_optimum and not request.range_approved_by_gm:
        raise ValueError(
            "range beyond this two-handed Optimum requires GM approval"
        )
    if (
        request.range_approved_by_gm
        and request.target_range is not RangedWeaponRange.EXTREME
        and not beyond_gm_defined_optimum
    ):
        raise ValueError("GM range approval is not required for this attack")


def _validate_no_profile_effects(attack: AttackActionExecutionRequest) -> None:
    kernel = attack.kernel_request
    source_attack = kernel.attack
    impact = source_attack.impact_spec
    assert isinstance(impact, DamageImpactSpec)
    dice_ids = {item.rule_id for item in source_attack.attacker_test.dice_modifiers}
    damage_ids = {item.rule_id for item in impact.damage_modifiers}
    wound_ids = {item.rule_id for item in kernel.wound_dice_modifiers}
    secondary_ids = {item.rule_id for item in source_attack.secondary_effects}
    if dice_ids & _PROFILE_DICE_RULE_IDS:
        raise ValueError("Attack already contains a profile dice modifier")
    if damage_ids & _PROFILE_DAMAGE_RULE_IDS:
        raise ValueError("Attack already contains a profile Damage modifier")
    if wound_ids & _PROFILE_WOUND_RULE_IDS:
        raise ValueError("Attack already contains a profile Wounds modifier")
    if secondary_ids & _PROFILE_SECONDARY_RULE_IDS:
        raise ValueError("Attack already contains a profile secondary effect")


def _within_optimum(
    profile: RangedWeaponCombatProfile,
    target_range: RangedWeaponRange,
) -> bool:
    value = _range_rank(target_range)
    return (
        _range_rank(profile.optimum_range_min)
        <= value
        <= _range_rank(profile.optimum_range_max)
    )


def _range_rank(value: RangedWeaponRange) -> int:
    return tuple(RangedWeaponRange).index(value)


def _applied_rule_ids(
    request: RangedWeaponAttackPreparationRequest,
    profile: RangedWeaponCombatProfile,
    aim: AimFollowUpResult | None,
) -> tuple[str, ...]:
    rules = [
        request.rule_id,
        RANGED_WEAPON_PROFILE_RULE_ID,
        CLOSE_ENEMY_RANGED_RESTRICTION_RULE_ID,
    ]
    if not _within_optimum(profile, request.target_range):
        rules.append(OUTSIDE_OPTIMUM_RANGE_RULE_ID)
    if (
        request.target_range is RangedWeaponRange.SHORT
        and profile.short_range_shooting_bonus_dice
    ):
        rules.append(SHORT_RANGE_SHOOTING_BONUS_RULE_ID)
    impact = request.attack.kernel_request.attack.impact_spec
    assert isinstance(impact, DamageImpactSpec)
    if profile.armoured_target_damage_bonus and impact.resilience.is_armoured:
        rules.append(ARMOURED_TARGET_DAMAGE_BONUS_RULE_ID)
    if profile.ignores_armour:
        rules.append(IGNORES_ARMOUR_RULE_ID)
    if profile.requires_aim_before_attack:
        rules.append(WEAPON_REQUIRES_AIM_RULE_ID)
    if profile.requires_blackpowder_lore:
        rules.append(BLACKPOWDER_LORE_REQUIREMENT_RULE_ID)
    if (
        profile.wounds_table_bonus_dice
        and request.attack.kernel_request.target_policy
        in {TargetInjuryPolicy.PLAYER, TargetInjuryPolicy.CHAMPION}
    ):
        rules.append(WOUNDS_TABLE_BONUS_RULE_ID)
    if profile.staggers_nearby_targets_on_hit:
        rules.append(BLUNDERBUSS_NEARBY_STAGGER_RULE_ID)
    if request.target_range is RangedWeaponRange.EXTREME:
        rules.append(EXTREME_RANGE_AIM_RULE_ID)
    if aim is not None:
        rules.extend(aim.applied_rule_ids)
    return tuple(dict.fromkeys(rules))


def _validate_rule_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    rule_ids = tuple(values)
    if not rule_ids:
        raise ValueError("applied_rule_ids must not be empty")
    for rule_id in rule_ids:
        _validate_non_empty_string(rule_id, "applied Rule ID")
    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError("applied_rule_ids must be unique")
    return rule_ids


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _validate_positive_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if value < 1:
        raise ValueError(f"{name} must be positive")


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")
