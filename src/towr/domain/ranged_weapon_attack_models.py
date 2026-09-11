from __future__ import annotations

from dataclasses import dataclass

from towr.domain.action_execution_models import (
    AttackActionExecutionRequest,
    AttackActionExecutionResult,
)
from towr.domain.exacting_test_models import ExactingTestProgress
from towr.domain.reload_models import (
    RELOAD_RULE_ID,
    FreeReloadWeaponState,
    RangedWeaponReloadState,
    ReloadableWeaponState,
)
from towr.domain.ranged_weapon_profiles import (
    REPEATER_SHOOTING_BONUS_RULE_ID,
    RangedReloadTrigger,
    ranged_weapon_reload_profile,
)
from towr.domain.test_models import Skill


@dataclass(frozen=True, slots=True)
class ReloadableRangedAttackExecutionRequest:
    id: str
    attack_skill: Skill
    attack: AttackActionExecutionRequest
    weapon_state: ReloadableWeaponState
    next_reload_cycle_id: str | None
    uses_optional_reload_bonus: bool = False
    rule_id: str = RELOAD_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "reloadable ranged Attack id")
        if not isinstance(self.attack_skill, Skill):
            raise TypeError("attack_skill must be a Skill")
        if self.attack_skill is not Skill.SHOOTING:
            raise ValueError("reloadable ranged weapons attack with Shooting")
        if not isinstance(self.attack, AttackActionExecutionRequest):
            raise TypeError("attack must be an AttackActionExecutionRequest")
        if not isinstance(self.weapon_state, ReloadableWeaponState):
            raise TypeError("weapon_state must be a ReloadableWeaponState")
        if self.next_reload_cycle_id is not None:
            _validate_non_empty_string(
                self.next_reload_cycle_id,
                "next_reload_cycle_id",
            )
        if not isinstance(self.uses_optional_reload_bonus, bool):
            raise TypeError("uses_optional_reload_bonus must be a boolean")
        _validate_non_empty_string(self.rule_id, "ranged Attack rule_id")
        if self.rule_id != RELOAD_RULE_ID:
            raise ValueError("reloadable ranged Attack uses an unknown rule")
        if self.weapon_state.rule_id != self.rule_id:
            raise ValueError("reloadable ranged Attack uses another weapon rule")
        if not self.weapon_state.loaded:
            raise ValueError("a reloadable ranged weapon must be loaded to fire")
        if self.next_reload_cycle_id in self.weapon_state.reload_cycle_ids:
            raise ValueError("reload cycle ID was already used by this weapon")
        if self.id == self.attack.id:
            raise ValueError("composite and Attack request IDs must differ")
        _validate_reload_trigger(self)


@dataclass(frozen=True, slots=True)
class ReloadableRangedAttackExecutionResult:
    request_id: str
    rule_id: str
    source_request: ReloadableRangedAttackExecutionRequest
    attack: AttackActionExecutionResult
    previous_weapon_state: ReloadableWeaponState
    weapon_state: ReloadableWeaponState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "reloadable ranged Attack result request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "reloadable ranged Attack result rule_id",
        )
        if not isinstance(
            self.source_request,
            ReloadableRangedAttackExecutionRequest,
        ):
            raise TypeError("source_request must be a ranged Attack request")
        if not isinstance(self.attack, AttackActionExecutionResult):
            raise TypeError("attack must be an AttackActionExecutionResult")
        if not isinstance(self.previous_weapon_state, ReloadableWeaponState):
            raise TypeError("previous_weapon_state must be reloadable state")
        if not isinstance(self.weapon_state, ReloadableWeaponState):
            raise TypeError("weapon_state must be reloadable state")

        source = self.source_request
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.previous_weapon_state != source.weapon_state
        ):
            raise ValueError("reloadable ranged Attack result is stale")
        if (
            self.attack.request_id != source.attack.id
            or self.attack.actor_id != source.attack.actor_id
            or self.attack.target_id != source.attack.target_id
            or self.attack.slot_index != source.attack.slot_index
            or self.attack.previous_state != source.attack.state
            or self.attack.resolution.request_id
            != source.attack.kernel_request.id
        ):
            raise ValueError("ranged Attack result belongs to another Attack")
        expected_weapon_state = _spent_weapon_state(source)
        if self.weapon_state != expected_weapon_state:
            raise ValueError("ranged Attack changed unrelated weapon state")

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {self.rule_id, *self.attack.applied_rule_ids}
        if not required <= set(rule_ids):
            raise ValueError("reloadable ranged Attack trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


@dataclass(frozen=True, slots=True)
class RangedWeaponAttackExecutionRequest:
    id: str
    attack_skill: Skill
    attack: AttackActionExecutionRequest
    weapon_state: RangedWeaponReloadState
    next_reload_cycle_id: str | None = None
    uses_optional_reload_bonus: bool = False
    rule_id: str = RELOAD_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "ranged weapon Attack id")
        if not isinstance(self.attack_skill, Skill):
            raise TypeError("attack_skill must be a Skill")
        if self.attack_skill is not Skill.SHOOTING:
            raise ValueError("ranged weapons attack with Shooting")
        if not isinstance(self.attack, AttackActionExecutionRequest):
            raise TypeError("attack must be an AttackActionExecutionRequest")
        if not isinstance(
            self.weapon_state,
            (FreeReloadWeaponState, ReloadableWeaponState),
        ):
            raise TypeError("weapon_state must be a ranged reload state")
        if self.next_reload_cycle_id is not None:
            _validate_non_empty_string(
                self.next_reload_cycle_id,
                "next_reload_cycle_id",
            )
        if not isinstance(self.uses_optional_reload_bonus, bool):
            raise TypeError("uses_optional_reload_bonus must be a boolean")
        _validate_non_empty_string(self.rule_id, "ranged weapon rule_id")
        if self.rule_id != RELOAD_RULE_ID:
            raise ValueError("ranged weapon Attack uses an unknown rule")
        if self.weapon_state.rule_id != self.rule_id:
            raise ValueError("ranged weapon Attack uses another weapon rule")
        if self.id == self.attack.id:
            raise ValueError("composite and Attack request IDs must differ")

        if isinstance(self.weapon_state, ReloadableWeaponState):
            _as_reloadable_request(self)
            return
        if self.next_reload_cycle_id is not None:
            raise ValueError("free reload Attack does not open a reload cycle")
        if self.uses_optional_reload_bonus:
            raise ValueError("free reload weapon has no Repeater bonus")
        if any(
            modifier.rule_id == REPEATER_SHOOTING_BONUS_RULE_ID
            for modifier in (
                self.attack.kernel_request.attack.attacker_test.dice_modifiers
            )
        ):
            raise ValueError("free reload weapon has no Repeater bonus")


@dataclass(frozen=True, slots=True)
class RangedWeaponAttackExecutionResult:
    request_id: str
    rule_id: str
    source_request: RangedWeaponAttackExecutionRequest
    attack: AttackActionExecutionResult
    previous_weapon_state: RangedWeaponReloadState
    weapon_state: RangedWeaponReloadState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "ranged weapon Attack result request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "ranged weapon Attack result rule_id",
        )
        if not isinstance(
            self.source_request,
            RangedWeaponAttackExecutionRequest,
        ):
            raise TypeError("source_request must be a ranged weapon Attack")
        if not isinstance(self.attack, AttackActionExecutionResult):
            raise TypeError("attack must be an AttackActionExecutionResult")
        if not isinstance(
            self.previous_weapon_state,
            (FreeReloadWeaponState, ReloadableWeaponState),
        ):
            raise TypeError("previous_weapon_state must be a ranged state")
        if not isinstance(
            self.weapon_state,
            (FreeReloadWeaponState, ReloadableWeaponState),
        ):
            raise TypeError("weapon_state must be a ranged state")

        source = self.source_request
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.previous_weapon_state != source.weapon_state
        ):
            raise ValueError("ranged weapon Attack result is stale")
        if (
            self.attack.request_id != source.attack.id
            or self.attack.actor_id != source.attack.actor_id
            or self.attack.target_id != source.attack.target_id
            or self.attack.slot_index != source.attack.slot_index
            or self.attack.previous_state != source.attack.state
            or self.attack.resolution.request_id
            != source.attack.kernel_request.id
        ):
            raise ValueError("ranged weapon result belongs to another Attack")

        expected_state: RangedWeaponReloadState
        if isinstance(source.weapon_state, FreeReloadWeaponState):
            expected_state = source.weapon_state
        else:
            expected_state = _spent_weapon_state(_as_reloadable_request(source))
        if self.weapon_state != expected_state:
            raise ValueError("ranged weapon Attack changed unrelated state")

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {self.rule_id, *self.attack.applied_rule_ids}
        if not required <= set(rule_ids):
            raise ValueError("ranged weapon Attack trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


def _as_reloadable_request(
    request: RangedWeaponAttackExecutionRequest,
) -> ReloadableRangedAttackExecutionRequest:
    if not isinstance(request.weapon_state, ReloadableWeaponState):
        raise TypeError("free reload state has no Exacting reload request")
    return ReloadableRangedAttackExecutionRequest(
        id=request.id,
        attack_skill=request.attack_skill,
        attack=request.attack,
        weapon_state=request.weapon_state,
        next_reload_cycle_id=request.next_reload_cycle_id,
        uses_optional_reload_bonus=request.uses_optional_reload_bonus,
        rule_id=request.rule_id,
    )


def _spent_weapon_state(
    request: ReloadableRangedAttackExecutionRequest,
) -> ReloadableWeaponState:
    profile = ranged_weapon_reload_profile(request.weapon_state.weapon_id)
    if (
        profile.trigger is RangedReloadTrigger.AFTER_OPTIONAL_BONUS
        and not request.uses_optional_reload_bonus
    ):
        return request.weapon_state
    cycle_id = request.next_reload_cycle_id
    assert cycle_id is not None
    return ReloadableWeaponState(
        weapon_instance_id=request.weapon_state.weapon_instance_id,
        weapon_id=request.weapon_state.weapon_id,
        reload_cycle_id=cycle_id,
        required_successes=request.weapon_state.required_successes,
        loaded=False,
        exacting=ExactingTestProgress(
            id=f"{cycle_id}:exacting",
            required_successes=request.weapon_state.required_successes,
        ),
        reload_cycle_ids=(
            *request.weapon_state.reload_cycle_ids,
            cycle_id,
        ),
        rule_id=request.weapon_state.rule_id,
    )


def _validate_reload_trigger(
    request: ReloadableRangedAttackExecutionRequest,
) -> None:
    profile = ranged_weapon_reload_profile(request.weapon_state.weapon_id)
    bonus_modifiers = tuple(
        modifier
        for modifier in (
            request.attack.kernel_request.attack.attacker_test.dice_modifiers
        )
        if modifier.rule_id == REPEATER_SHOOTING_BONUS_RULE_ID
    )
    if profile.trigger is RangedReloadTrigger.AFTER_EVERY_SHOT:
        if request.uses_optional_reload_bonus or bonus_modifiers:
            raise ValueError("ordinary reload weapon has no Repeater bonus")
        if request.next_reload_cycle_id is None:
            raise ValueError("this shot requires a next reload cycle")
        return
    if profile.trigger is not RangedReloadTrigger.AFTER_OPTIONAL_BONUS:
        raise ValueError("free-reload weapon does not use reloadable state")

    if request.uses_optional_reload_bonus:
        expected = profile.optional_bonus_modifier()
        if bonus_modifiers != (expected,):
            raise ValueError("Repeater bonus must match the weapon profile")
        if request.next_reload_cycle_id is None:
            raise ValueError("bonus Repeater shot requires a reload cycle")
    else:
        if bonus_modifiers:
            raise ValueError("Repeater modifier requires explicit bonus use")
        if request.next_reload_cycle_id is not None:
            raise ValueError("ordinary Repeater shot does not open reload")


def _validate_rule_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    rule_ids = tuple(values)
    if not rule_ids:
        raise ValueError("applied_rule_ids must not be empty")
    for value in rule_ids:
        _validate_non_empty_string(value, "applied Rule ID")
    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError("applied_rule_ids must be unique")
    return rule_ids


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
