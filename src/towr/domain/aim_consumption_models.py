from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.action_execution_models import AttackActionExecutionRequest, AttackActionExecutionResult
from towr.domain.aim_models import (
    AIM_ACTION_RULE_ID,
    AIM_FOLLOW_UP_RULE_ID,
    AimFollowUpOutcome,
    AimFollowUpResult,
    _validate_non_empty_string,
)
from towr.domain.turn_models import ActionExecutionReceipt, CombatActionKind
from towr.domain.test_models import Skill
from towr.domain.prepared_ranged_weapon_attack_models import (
    PreparedRangedWeaponAttackExecutionRequest,
    PreparedRangedWeaponAttackExecutionResult,
    _aim_request_for,
)
from towr.domain.aim_ranged_weapon_attack_models import (
    AIM_RANGED_ATTACK_EXECUTION_RULE_ID,
    AimRangedWeaponAttackExecutionRequest,
    AimRangedWeaponAttackExecutionResult,
)


AIM_LOSS_CONSUMPTION_RULE_ID = "RULE-COMBAT-004:aim-loss-consumption"
AIM_ATTACK_CONSUMPTION_RULE_ID = "RULE-COMBAT-004:aim-attack-consumption"
AIM_ATTACK_LOSS_CONSUMPTION_RULE_ID = "RULE-COMBAT-004:aim-attack-loss-consumption"
REGISTERED_AIM_LOSS_ATTACK_RULE_ID = "RULE-COMBAT-004:registered-aim-loss-attack"
REGISTERED_AIM_RANGED_ATTACK_RULE_ID = "RULE-COMBAT-004:registered-aim-ranged-attack"
REGISTERED_PREPARED_AIM_RANGED_ATTACK_RULE_ID = "RULE-COMBAT-004:registered-prepared-aim-ranged-attack"


@dataclass(frozen=True, slots=True)
class AimConsumptionState:
    actor_id: str
    consumed_aim_source_ids: tuple[str, ...] = ()
    consumed_aim_follow_up_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.actor_id, "Aim history actor_id")
        for name in ("consumed_aim_source_ids", "consumed_aim_follow_up_ids"):
            object.__setattr__(self, name, _unique_ids(getattr(self, name), name))


@dataclass(frozen=True, slots=True)
class AimLossConsumptionRequest:
    id: str
    state: AimConsumptionState
    follow_up: AimFollowUpResult
    action: ActionExecutionReceipt
    rule_id: str = AIM_LOSS_CONSUMPTION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Aim loss consumption id")
        if not isinstance(self.state, AimConsumptionState):
            raise TypeError("state must be an AimConsumptionState")
        if not isinstance(self.follow_up, AimFollowUpResult):
            raise TypeError("follow_up must be a completed AimFollowUpResult")
        if not isinstance(self.action, ActionExecutionReceipt):
            raise TypeError("action must be a completed ActionExecutionReceipt")
        source = self.follow_up.source_request
        aim = source.aim
        if (
            self.rule_id != AIM_LOSS_CONSUMPTION_RULE_ID
            or self.follow_up.rule_id != AIM_FOLLOW_UP_RULE_ID
            or aim.rule_id != AIM_ACTION_RULE_ID
        ):
            raise ValueError("Aim loss consumption uses an unknown rule")
        if self.follow_up.outcome is not AimFollowUpOutcome.LOST:
            raise ValueError("Aim loss consumption requires LOST")
        if self.action.declaration.produces_attack:
            raise ValueError("Aim loss consumption requires a non-attacking action")
        if self.state.actor_id != source.actor_id or self.action.actor_id != source.actor_id:
            raise ValueError("Aim loss belongs to another actor")
        if self.action.id != source.next_action_id or self.action.declaration != source.declaration:
            raise ValueError("Aim loss receipt does not match the follow-up action")
        if (self.action.round_number, self.action.slot_index) <= (aim.round_state.round_number, aim.slot.index):
            raise ValueError("Aim loss action must follow Aim")
        if self.action.round_number > aim.round_state.round_number and self.action.slot_index != 1:
            raise ValueError("Aim loss must use the first slot of a later turn")
        if aim.request_id in self.state.consumed_aim_source_ids:
            raise ValueError("Aim source was already consumed")
        if self.follow_up.request_id in self.state.consumed_aim_follow_up_ids:
            raise ValueError("Aim follow-up was already consumed")


@dataclass(frozen=True, slots=True)
class AimLossConsumptionResult:
    request_id: str
    rule_id: str
    source_request: AimLossConsumptionRequest
    previous_state: AimConsumptionState
    state: AimConsumptionState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, AimLossConsumptionRequest):
            raise TypeError("source_request must be an AimLossConsumptionRequest")
        source = self.source_request
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.previous_state != source.state
            or self.state != _consumed_state(source)
        ):
            raise ValueError("Aim loss consumption has stale provenance or state")
        rules = _unique_ids(self.applied_rule_ids, "Aim loss applied rules")
        if rules != _consumption_rule_ids(source):
            raise ValueError("Aim loss consumption trace is inconsistent")
        object.__setattr__(self, "applied_rule_ids", rules)


@dataclass(frozen=True, slots=True)
class AimAttackLossConsumptionRequest:
    id: str
    state: AimConsumptionState
    follow_up: AimFollowUpResult
    execution: AttackActionExecutionResult
    rule_id: str = AIM_ATTACK_LOSS_CONSUMPTION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Aim Attack loss consumption id")
        if not isinstance(self.state, AimConsumptionState):
            raise TypeError("state must be an AimConsumptionState")
        if not isinstance(self.follow_up, AimFollowUpResult):
            raise TypeError("follow_up must be a completed AimFollowUpResult")
        if not isinstance(self.execution, AttackActionExecutionResult):
            raise TypeError("execution must be a completed AttackActionExecutionResult")
        source = self.follow_up.source_request
        if self.rule_id != AIM_ATTACK_LOSS_CONSUMPTION_RULE_ID:
            raise ValueError("Aim Attack loss uses an unknown rule")
        attack = _validate_attack_loss_preflight(self.state, self.follow_up, self.follow_up.attack)
        execution = self.execution
        action = execution.slot.execution
        if action is None:
            raise ValueError("Aim Attack loss requires a completed receipt")
        if self.state.actor_id != source.actor_id or execution.actor_id != source.actor_id:
            raise ValueError("Aim Attack loss belongs to another actor")
        if (
            execution.request_id != attack.id or execution.target_id != attack.target_id
            or execution.slot_index != attack.slot_index or execution.previous_state != attack.state
            or execution.resolution.request_id != attack.kernel_request.id
            or execution.resolution.attack.request_id != attack.kernel_request.attack.id
            or action.id != source.next_action_id or action.declaration != source.declaration
            or action.actor_id != source.actor_id
        ):
            raise ValueError("Aim Attack loss execution does not match its follow-up Attack")


@dataclass(frozen=True, slots=True)
class AimAttackLossConsumptionResult:
    request_id: str
    rule_id: str
    source_request: AimAttackLossConsumptionRequest
    previous_state: AimConsumptionState
    state: AimConsumptionState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, AimAttackLossConsumptionRequest):
            raise TypeError("source_request must be an AimAttackLossConsumptionRequest")
        source = self.source_request
        if (
            self.request_id != source.id or self.rule_id != source.rule_id
            or self.previous_state != source.state or self.state != _consumed_state(source)
        ):
            raise ValueError("Aim Attack loss consumption has stale provenance or state")
        rules = _unique_ids(self.applied_rule_ids, "Aim Attack loss rules")
        if rules != _attack_loss_rule_ids(source):
            raise ValueError("Aim Attack loss trace is inconsistent")
        object.__setattr__(self, "applied_rule_ids", rules)


@dataclass(frozen=True, slots=True)
class RegisteredAimLossAttackExecutionRequest:
    id: str
    state: AimConsumptionState
    follow_up: AimFollowUpResult
    attack: AttackActionExecutionRequest
    rule_id: str = REGISTERED_AIM_LOSS_ATTACK_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "registered Aim loss Attack id")
        if self.rule_id != REGISTERED_AIM_LOSS_ATTACK_RULE_ID:
            raise ValueError("unknown registered Aim loss Attack rule")
        _validate_attack_loss_preflight(self.state, self.follow_up, self.attack)


@dataclass(frozen=True, slots=True)
class RegisteredAimLossAttackExecutionResult:
    request_id: str
    rule_id: str
    source_request: RegisteredAimLossAttackExecutionRequest
    registration: AimAttackLossConsumptionResult
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, RegisteredAimLossAttackExecutionRequest):
            raise TypeError("source_request must be a registered Aim loss Attack request")
        if not isinstance(self.registration, AimAttackLossConsumptionResult):
            raise TypeError("registration must be an AimAttackLossConsumptionResult")
        source = self.source_request
        if (
            self.request_id != source.id or self.rule_id != source.rule_id
            or self.registration.source_request.id != f"{source.id}:registration"
            or self.registration.previous_state != source.state
            or self.registration.source_request.follow_up != source.follow_up
        ):
            raise ValueError("registered Aim loss Attack has stale provenance")
        rules = _unique_ids(self.applied_rule_ids, "registered Aim loss Attack rules")
        if rules != _registered_loss_rule_ids(source, self.registration):
            raise ValueError("registered Aim loss Attack trace is inconsistent")
        object.__setattr__(self, "applied_rule_ids", rules)

    @property
    def execution(self) -> AttackActionExecutionResult:
        return self.registration.source_request.execution

    @property
    def state(self) -> AimConsumptionState:
        return self.registration.state


def _registered_loss_rule_ids(
    request: RegisteredAimLossAttackExecutionRequest,
    registration: AimAttackLossConsumptionResult,
) -> tuple[str, ...]:
    return tuple(dict.fromkeys((request.rule_id, *registration.applied_rule_ids)))


def _validate_attack_loss_preflight(
    state: AimConsumptionState,
    follow_up: AimFollowUpResult,
    attack: AttackActionExecutionRequest | None,
) -> AttackActionExecutionRequest:
    if not isinstance(state, AimConsumptionState):
        raise TypeError("state must be an AimConsumptionState")
    if not isinstance(follow_up, AimFollowUpResult):
        raise TypeError("follow_up must be a completed AimFollowUpResult")
    source = follow_up.source_request
    aim = source.aim
    if follow_up.rule_id != AIM_FOLLOW_UP_RULE_ID or aim.rule_id != AIM_ACTION_RULE_ID:
        raise ValueError("Aim Attack loss uses an unknown rule")
    if follow_up.outcome is not AimFollowUpOutcome.LOST:
        raise ValueError("Aim Attack loss requires LOST")
    if source.declaration.kind is not CombatActionKind.ATTACK or follow_up.attack is None:
        raise ValueError("Aim Attack loss requires an ordinary Attack follow-up")
    if not isinstance(attack, AttackActionExecutionRequest):
        raise TypeError("attack must be an AttackActionExecutionRequest")
    if attack != follow_up.attack or attack.id != source.next_action_id:
        raise ValueError("Aim loss Attack does not match its follow-up")
    if attack.target_id == aim.bonus.target_id and source.attack_skill is not Skill.MELEE:
        raise ValueError("same-target Aim Attack loss requires Melee")
    if state.actor_id != source.actor_id or attack.actor_id != source.actor_id:
        raise ValueError("Aim Attack loss belongs to another actor")
    turn = attack.state.active_turn
    if (turn is None or turn.actor_id != source.actor_id or attack.slot_index > len(turn.action_slots)
            or turn.action_slots[attack.slot_index - 1].declaration != source.declaration):
        raise ValueError("Aim loss Attack slot does not match its follow-up")
    if (attack.state.round_number, attack.slot_index) <= (aim.round_state.round_number, aim.slot.index):
        raise ValueError("Aim loss Attack must follow Aim")
    if attack.state.round_number > aim.round_state.round_number and attack.slot_index != 1:
        raise ValueError("Aim loss Attack must use the first slot of a later turn")
    if aim.request_id in state.consumed_aim_source_ids:
        raise ValueError("Aim source was already consumed")
    if follow_up.request_id in state.consumed_aim_follow_up_ids:
        raise ValueError("Aim follow-up was already consumed")
    return attack


@dataclass(frozen=True, slots=True)
class AimAttackConsumptionRequest:
    id: str
    state: AimConsumptionState
    execution: AimRangedWeaponAttackExecutionResult
    rule_id: str = AIM_ATTACK_CONSUMPTION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Aim Attack consumption id")
        if not isinstance(self.state, AimConsumptionState):
            raise TypeError("state must be an AimConsumptionState")
        if not isinstance(self.execution, AimRangedWeaponAttackExecutionResult):
            raise TypeError("execution must be a completed Aim ranged Attack")
        if self.rule_id != AIM_ATTACK_CONSUMPTION_RULE_ID:
            raise ValueError("Aim Attack consumption uses an unknown rule")
        _validate_aim_attack_preflight(self.state, self.execution.source_request)
        follow_up = self.execution.source_request.aim_follow_up
        action = self.execution.ranged_attack.attack.slot.execution
        if action is None:
            raise ValueError("Aim Attack consumption requires a completed receipt")
        # Nested result models bind the exact prepared Attack, kernel, turn transition and receipt.
        if (
            action.actor_id != self.state.actor_id
            or action.id != follow_up.source_request.next_action_id
            or action.declaration != follow_up.source_request.declaration
        ):
            raise ValueError("Aim Attack receipt does not match its follow-up")


@dataclass(frozen=True, slots=True)
class AimAttackConsumptionResult:
    request_id: str
    rule_id: str
    source_request: AimAttackConsumptionRequest
    previous_state: AimConsumptionState
    state: AimConsumptionState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, AimAttackConsumptionRequest):
            raise TypeError("source_request must be an AimAttackConsumptionRequest")
        source = self.source_request
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.previous_state != source.state
            or self.state != _attack_consumed_state(source)
        ):
            raise ValueError("Aim Attack consumption has stale provenance or state")
        rules = _unique_ids(self.applied_rule_ids, "Aim Attack consumption rules")
        if rules != _attack_consumption_rule_ids(source):
            raise ValueError("Aim Attack consumption trace is inconsistent")
        object.__setattr__(self, "applied_rule_ids", rules)


@dataclass(frozen=True, slots=True)
class RegisteredAimRangedAttackExecutionRequest:
    id: str
    state: AimConsumptionState
    attack: AimRangedWeaponAttackExecutionRequest
    rule_id: str = REGISTERED_AIM_RANGED_ATTACK_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "registered Aim Attack id")
        if self.rule_id != REGISTERED_AIM_RANGED_ATTACK_RULE_ID:
            raise ValueError("unknown registered Aim Attack rule")
        _validate_aim_attack_preflight(self.state, self.attack)


@dataclass(frozen=True, slots=True)
class RegisteredAimRangedAttackExecutionResult:
    request_id: str
    rule_id: str
    source_request: RegisteredAimRangedAttackExecutionRequest
    registration: AimAttackConsumptionResult
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, RegisteredAimRangedAttackExecutionRequest):
            raise TypeError("source_request must be a registered Aim Attack request")
        if not isinstance(self.registration, AimAttackConsumptionResult):
            raise TypeError("registration must be an AimAttackConsumptionResult")
        source = self.source_request
        if (
            self.request_id != source.id or self.rule_id != source.rule_id
            or self.registration.source_request.id != f"{source.id}:registration"
            or self.registration.previous_state != source.state
            or self.execution.source_request != source.attack
        ):
            raise ValueError("registered Aim Attack result has stale provenance")
        rules = _unique_ids(self.applied_rule_ids, "registered Aim Attack rules")
        if rules != _registered_aim_rule_ids(source, self.registration):
            raise ValueError("registered Aim Attack trace is inconsistent")
        object.__setattr__(self, "applied_rule_ids", rules)

    @property
    def execution(self) -> AimRangedWeaponAttackExecutionResult:
        return self.registration.source_request.execution

    @property
    def state(self) -> AimConsumptionState:
        return self.registration.state


@dataclass(frozen=True, slots=True)
class RegisteredPreparedAimRangedAttackExecutionRequest:
    id: str
    state: AimConsumptionState
    attack: PreparedRangedWeaponAttackExecutionRequest
    rule_id: str = REGISTERED_PREPARED_AIM_RANGED_ATTACK_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "registered prepared Aim Attack id")
        if self.rule_id != REGISTERED_PREPARED_AIM_RANGED_ATTACK_RULE_ID:
            raise ValueError("unknown registered prepared Aim Attack rule")
        _validate_prepared_aim_attack_preflight(self.state, self.attack)


@dataclass(frozen=True, slots=True)
class RegisteredPreparedAimRangedAttackExecutionResult:
    request_id: str
    rule_id: str
    source_request: RegisteredPreparedAimRangedAttackExecutionRequest
    execution: PreparedRangedWeaponAttackExecutionResult
    registration: AimAttackConsumptionResult
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, RegisteredPreparedAimRangedAttackExecutionRequest):
            raise TypeError("source_request must be a registered prepared Aim Attack request")
        if not isinstance(self.execution, PreparedRangedWeaponAttackExecutionResult):
            raise TypeError("execution must be a completed prepared ranged Attack")
        if not isinstance(self.registration, AimAttackConsumptionResult):
            raise TypeError("registration must be an AimAttackConsumptionResult")
        source = self.source_request
        if (
            self.request_id != source.id or self.rule_id != source.rule_id
            or self.execution.source_request != source.attack
            or self.registration.source_request.id != f"{source.id}:registration"
            or self.registration.previous_state != source.state
            or self.registration.source_request.execution != self.execution.execution
        ):
            raise ValueError("registered prepared Aim Attack result has stale provenance")
        rules = _unique_ids(self.applied_rule_ids, "registered prepared Aim Attack rules")
        if rules != _registered_prepared_aim_rule_ids(source, self.execution, self.registration):
            raise ValueError("registered prepared Aim Attack trace is inconsistent")
        object.__setattr__(self, "applied_rule_ids", rules)

    @property
    def state(self) -> AimConsumptionState:
        return self.registration.state


def _validate_prepared_aim_attack_preflight(
    state: AimConsumptionState,
    request: PreparedRangedWeaponAttackExecutionRequest,
) -> None:
    if not isinstance(request, PreparedRangedWeaponAttackExecutionRequest):
        raise TypeError("attack must be a PreparedRangedWeaponAttackExecutionRequest")
    _validate_aim_attack_preflight(state, _aim_request_for(request))


def _registered_prepared_aim_rule_ids(
    request: RegisteredPreparedAimRangedAttackExecutionRequest,
    execution: PreparedRangedWeaponAttackExecutionResult,
    registration: AimAttackConsumptionResult,
) -> tuple[str, ...]:
    return tuple(dict.fromkeys((request.rule_id, *execution.applied_rule_ids, *registration.applied_rule_ids)))


def _registered_aim_rule_ids(
    request: RegisteredAimRangedAttackExecutionRequest,
    registration: AimAttackConsumptionResult,
) -> tuple[str, ...]:
    return tuple(dict.fromkeys((request.rule_id, *registration.applied_rule_ids)))


def _attack_consumed_state(request: AimAttackConsumptionRequest) -> AimConsumptionState:
    aim = request.execution.source_request.aim_follow_up.source_request.aim
    return replace(request.state,
                   consumed_aim_source_ids=(*request.state.consumed_aim_source_ids, aim.request_id),
                   consumed_aim_follow_up_ids=request.execution.consumed_aim_follow_up_ids)


def _attack_consumption_rule_ids(request: AimAttackConsumptionRequest) -> tuple[str, ...]:
    aim = request.execution.source_request.aim_follow_up.source_request.aim
    return tuple(dict.fromkeys((request.rule_id, *aim.applied_rule_ids, *request.execution.applied_rule_ids)))


def _consumed_state(request: AimLossConsumptionRequest | AimAttackLossConsumptionRequest) -> AimConsumptionState:
    return replace(
        request.state,
        consumed_aim_source_ids=(*request.state.consumed_aim_source_ids, request.follow_up.source_request.aim.request_id),
        consumed_aim_follow_up_ids=(*request.state.consumed_aim_follow_up_ids, request.follow_up.request_id),
    )


def _attack_loss_rule_ids(request: AimAttackLossConsumptionRequest) -> tuple[str, ...]:
    return tuple(dict.fromkeys((
        request.rule_id, *request.follow_up.source_request.aim.applied_rule_ids,
        *request.follow_up.applied_rule_ids, *request.execution.applied_rule_ids,
    )))


def _consumption_rule_ids(request: AimLossConsumptionRequest) -> tuple[str, ...]:
    return tuple(dict.fromkeys((
        request.rule_id,
        *request.follow_up.source_request.aim.applied_rule_ids,
        *request.follow_up.applied_rule_ids,
        request.action.executor_rule_id,
    )))


def _unique_ids(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    if isinstance(values, str):
        raise TypeError(f"{name} must be a sequence of IDs")
    identifiers = tuple(values)
    for identifier in identifiers:
        _validate_non_empty_string(identifier, name)
    if len(set(identifiers)) != len(identifiers):
        raise ValueError(f"{name} must be unique")
    return identifiers


def _validate_aim_attack_preflight(
    state: AimConsumptionState,
    request: AimRangedWeaponAttackExecutionRequest,
) -> None:
    if not isinstance(state, AimConsumptionState):
        raise TypeError("state must be an AimConsumptionState")
    if not isinstance(request, AimRangedWeaponAttackExecutionRequest):
        raise TypeError("attack must be an AimRangedWeaponAttackExecutionRequest")
    follow_up = request.aim_follow_up
    aim = follow_up.source_request.aim
    if (request.rule_id != AIM_RANGED_ATTACK_EXECUTION_RULE_ID
            or follow_up.rule_id != AIM_FOLLOW_UP_RULE_ID or aim.rule_id != AIM_ACTION_RULE_ID):
        raise ValueError("Aim Attack consumption uses an unknown rule")
    if follow_up.outcome is not AimFollowUpOutcome.APPLIED_TO_RANGED_ATTACK:
        raise ValueError("Aim Attack consumption requires APPLIED")
    attack = request.ranged_attack.attack
    if state.actor_id != follow_up.source_request.actor_id or state.actor_id != attack.actor_id:
        raise ValueError("Aim Attack belongs to another actor")
    if attack != follow_up.attack or attack.id != follow_up.source_request.next_action_id:
        raise ValueError("Aim Attack does not match its follow-up")
    if (attack.state.round_number, attack.slot_index) <= (aim.round_state.round_number, aim.slot.index):
        raise ValueError("Aim Attack must follow Aim")
    if attack.state.round_number > aim.round_state.round_number and attack.slot_index != 1:
        raise ValueError("Aim Attack must use the first slot of a later turn")
    if aim.request_id in state.consumed_aim_source_ids:
        raise ValueError("Aim source was already consumed")
    if follow_up.request_id in state.consumed_aim_follow_up_ids:
        raise ValueError("Aim follow-up was already consumed")
    if request.consumed_aim_follow_up_ids != state.consumed_aim_follow_up_ids:
        raise ValueError("Aim Attack has a stale consumed follow-up prefix")
