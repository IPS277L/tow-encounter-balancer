from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.magic_models import (
    CastingDecisionRequest,
    CastingDecisionResult,
    CastingTestRequest,
    CastingTestResult,
    MiscastPreparationRequest,
    MiscastPreparationResult,
    MiscastPoolIncreaseRequest,
    MiscastPoolIncreaseSourceKind,
    MiscastPoolOutcome,
    MiscastPoolResolutionResult,
    WizardMagicState,
)
from towr.domain.resolution_models import KernelAttackRequest, ResolutionResult
from towr.domain.turn_models import (
    ActionExecutionReceipt,
    CombatActionKind,
    CombatActionSlot,
    CombatRoundState,
    ImproviseKind,
)


@dataclass(frozen=True, slots=True)
class AttackActionExecutionRequest:
    id: str
    state: CombatRoundState
    actor_id: str
    target_id: str
    slot_index: int
    kernel_request: KernelAttackRequest

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "attack action execution id")
        if not isinstance(self.state, CombatRoundState):
            raise TypeError("state must be a CombatRoundState")
        _validate_non_empty_string(self.actor_id, "attack action actor_id")
        _validate_non_empty_string(self.target_id, "attack action target_id")
        if not isinstance(self.slot_index, int) or isinstance(
            self.slot_index,
            bool,
        ):
            raise TypeError("slot_index must be an integer")
        if self.slot_index not in (1, 2):
            raise ValueError("slot_index must be 1 or 2")
        if not isinstance(self.kernel_request, KernelAttackRequest):
            raise TypeError("kernel_request must be a KernelAttackRequest")
        if self.kernel_request.target_id != self.target_id:
            raise ValueError("kernel request belongs to another target")


@dataclass(frozen=True, slots=True)
class AttackActionExecutionResult:
    request_id: str
    actor_id: str
    target_id: str
    slot_index: int
    previous_state: CombatRoundState
    state: CombatRoundState
    slot: CombatActionSlot
    resolution: ResolutionResult
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "execution request_id")
        _validate_non_empty_string(self.actor_id, "execution actor_id")
        _validate_non_empty_string(self.target_id, "execution target_id")
        if not isinstance(self.slot_index, int) or isinstance(
            self.slot_index,
            bool,
        ):
            raise TypeError("slot_index must be an integer")
        if self.slot_index not in (1, 2):
            raise ValueError("slot_index must be 1 or 2")
        if not isinstance(self.previous_state, CombatRoundState):
            raise TypeError("previous_state must be a CombatRoundState")
        if not isinstance(self.state, CombatRoundState):
            raise TypeError("state must be a CombatRoundState")
        if not isinstance(self.slot, CombatActionSlot):
            raise TypeError("slot must be a CombatActionSlot")
        if not isinstance(self.resolution, ResolutionResult):
            raise TypeError("resolution must be a ResolutionResult")
        rule_ids = _validate_execution_transition(
            request_id=self.request_id,
            actor_id=self.actor_id,
            slot_index=self.slot_index,
            previous_state=self.previous_state,
            state=self.state,
            slot=self.slot,
            source_request_id=self.resolution.request_id,
            result_request_id=self.resolution.request_id,
            expected_executor_rule_id=(
                "RULE-COMBAT-004:attack-action-execution"
            ),
            applied_rule_ids=self.applied_rule_ids,
        )
        object.__setattr__(self, "applied_rule_ids", rule_ids)


@dataclass(frozen=True, slots=True)
class SkippedCastingTestAfterActionRequest:
    id: str
    caster_id: str
    action: ActionExecutionReceipt
    state: WizardMagicState
    wizard_level: int
    consumed_action_execution_ids: tuple[str, ...] = ()
    rule_id: str = "RULE-MAGIC-004:skipped-casting-test"

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.id,
            "skipped Casting Test request id",
        )
        _validate_non_empty_string(self.caster_id, "caster_id")
        if not isinstance(self.action, ActionExecutionReceipt):
            raise TypeError("action must be an ActionExecutionReceipt")
        if self.action.actor_id != self.caster_id:
            raise ValueError("completed action belongs to another actor")
        declaration = self.action.declaration
        if (
            declaration.kind is CombatActionKind.IMPROVISE
            and declaration.improvise_kind is ImproviseKind.SPELL
        ):
            raise ValueError(
                "a completed Casting Test is not a skipped Casting Test"
            )
        if not isinstance(self.state, WizardMagicState):
            raise TypeError("state must be a WizardMagicState")
        if self.state.casting_lore_id is None:
            raise ValueError("skipped Casting Test requires active casting")
        _validate_positive_int(self.wizard_level, "wizard_level")
        consumed = _validate_execution_ids(
            self.consumed_action_execution_ids,
        )
        if self.action.id in consumed:
            raise ValueError("completed action was already consumed")
        object.__setattr__(self, "consumed_action_execution_ids", consumed)
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class SkippedCastingTestAfterActionResult:
    request_id: str
    caster_id: str
    action: ActionExecutionReceipt
    source: MiscastPoolIncreaseRequest
    miscast_pool: MiscastPoolResolutionResult
    state: WizardMagicState
    previous_consumed_action_execution_ids: tuple[str, ...]
    consumed_action_execution_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "skipped request_id")
        _validate_non_empty_string(self.caster_id, "caster_id")
        if not isinstance(self.action, ActionExecutionReceipt):
            raise TypeError("action must be an ActionExecutionReceipt")
        if self.action.actor_id != self.caster_id:
            raise ValueError("completed action belongs to another actor")
        declaration = self.action.declaration
        if (
            declaration.kind is CombatActionKind.IMPROVISE
            and declaration.improvise_kind is ImproviseKind.SPELL
        ):
            raise ValueError(
                "a completed Casting Test is not a skipped Casting Test"
            )
        if not isinstance(self.source, MiscastPoolIncreaseRequest):
            raise TypeError("source must be a MiscastPoolIncreaseRequest")
        if self.source.target_id != self.caster_id:
            raise ValueError("Miscast Pool increase targets another actor")
        if self.source.amount != 1:
            raise ValueError("one skipped Casting Test adds exactly one die")
        if self.source.source_kind is not MiscastPoolIncreaseSourceKind.ACTION:
            raise ValueError("skipped Casting Test must reference an action")
        if self.source.source_id != self.action.id:
            raise ValueError("Miscast Pool increase references another action")
        if not isinstance(
            self.miscast_pool,
            MiscastPoolResolutionResult,
        ):
            raise TypeError(
                "miscast_pool must be a MiscastPoolResolutionResult"
            )
        if self.miscast_pool.target_id != self.caster_id:
            raise ValueError("Miscast Pool result belongs to another actor")
        if self.miscast_pool.dice_added != 1:
            raise ValueError("Miscast Pool result must add exactly one die")
        if not isinstance(self.state, WizardMagicState):
            raise TypeError("state must be a WizardMagicState")
        if self.state != self.miscast_pool.state:
            raise ValueError("state must match the Miscast Pool result")
        previous_consumed = _validate_execution_ids(
            self.previous_consumed_action_execution_ids,
        )
        if self.action.id in previous_consumed:
            raise ValueError("completed action was already consumed")
        consumed = _validate_execution_ids(
            self.consumed_action_execution_ids,
        )
        if consumed != (*previous_consumed, self.action.id):
            raise ValueError(
                "consumed action IDs must append the completed action"
            )
        object.__setattr__(
            self,
            "previous_consumed_action_execution_ids",
            previous_consumed,
        )
        object.__setattr__(self, "consumed_action_execution_ids", consumed)
        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        object.__setattr__(self, "applied_rule_ids", rule_ids)


@dataclass(frozen=True, slots=True)
class CastingAttemptExecutionRequest:
    id: str
    state: CombatRoundState
    actor_id: str
    slot_index: int
    casting_request: CastingTestRequest

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "casting attempt execution id")
        if not isinstance(self.state, CombatRoundState):
            raise TypeError("state must be a CombatRoundState")
        _validate_non_empty_string(self.actor_id, "casting attempt actor_id")
        _validate_slot_index(self.slot_index)
        if not isinstance(self.casting_request, CastingTestRequest):
            raise TypeError("casting_request must be a CastingTestRequest")
        if self.casting_request.caster_id != self.actor_id:
            raise ValueError("casting request caster must match action actor")


@dataclass(frozen=True, slots=True)
class CastingAttemptExecutionResult:
    request_id: str
    actor_id: str
    slot_index: int
    previous_state: CombatRoundState
    state: CombatRoundState
    slot: CombatActionSlot
    casting: CastingTestResult
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "execution request_id")
        _validate_non_empty_string(self.actor_id, "execution actor_id")
        _validate_slot_index(self.slot_index)
        if not isinstance(self.previous_state, CombatRoundState):
            raise TypeError("previous_state must be a CombatRoundState")
        if not isinstance(self.state, CombatRoundState):
            raise TypeError("state must be a CombatRoundState")
        if not isinstance(self.slot, CombatActionSlot):
            raise TypeError("slot must be a CombatActionSlot")
        if not isinstance(self.casting, CastingTestResult):
            raise TypeError("casting must be a CastingTestResult")
        if self.casting.caster_id != self.actor_id:
            raise ValueError("Casting Test result belongs to another actor")
        rule_ids = _validate_execution_transition(
            request_id=self.request_id,
            actor_id=self.actor_id,
            slot_index=self.slot_index,
            previous_state=self.previous_state,
            state=self.state,
            slot=self.slot,
            source_request_id=self.casting.request_id,
            result_request_id=self.casting.request_id,
            expected_executor_rule_id=(
                "RULE-COMBAT-004:casting-improvise-execution"
            ),
            applied_rule_ids=self.applied_rule_ids,
        )
        object.__setattr__(self, "applied_rule_ids", rule_ids)


@dataclass(frozen=True, slots=True)
class CastingActionPostTestRequest:
    id: str
    execution: CastingAttemptExecutionResult
    wizard_level: int
    decision: CastingDecisionRequest | None = None
    rule_id: str = "RULE-COMBAT-004:casting-post-test"

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "casting post-Test request id")
        if not isinstance(self.execution, CastingAttemptExecutionResult):
            raise TypeError(
                "execution must be a CastingAttemptExecutionResult"
            )
        _validate_positive_int(self.wizard_level, "wizard_level")
        if self.decision is not None and not isinstance(
            self.decision,
            CastingDecisionRequest,
        ):
            raise TypeError("decision must be a CastingDecisionRequest")
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class CastingActionPostTestResult:
    request_id: str
    execution: CastingAttemptExecutionResult
    wizard_level: int
    state: WizardMagicState
    miscast_pool: MiscastPoolResolutionResult | None
    decision: CastingDecisionResult | None
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "post-Test request_id")
        if not isinstance(self.execution, CastingAttemptExecutionResult):
            raise TypeError(
                "execution must be a CastingAttemptExecutionResult"
            )
        _validate_positive_int(self.wizard_level, "wizard_level")
        if not isinstance(self.state, WizardMagicState):
            raise TypeError("state must be a WizardMagicState")
        if self.miscast_pool is not None and not isinstance(
            self.miscast_pool,
            MiscastPoolResolutionResult,
        ):
            raise TypeError(
                "miscast_pool must be a MiscastPoolResolutionResult"
            )
        if self.decision is not None and not isinstance(
            self.decision,
            CastingDecisionResult,
        ):
            raise TypeError("decision must be a CastingDecisionResult")

        actor_id = self.execution.actor_id
        if (
            self.miscast_pool is not None
            and self.miscast_pool.target_id != actor_id
        ):
            raise ValueError("Miscast Pool result belongs to another actor")
        triggered = (
            self.miscast_pool is not None
            and self.miscast_pool.outcome
            is MiscastPoolOutcome.MISCAST_TRIGGERED
        )
        if triggered:
            if self.decision is not None:
                raise ValueError("triggered Miscast forbids normal decision")
            expected_state = self.miscast_pool.state
        else:
            if self.decision is None:
                raise ValueError("normal post-Test result requires a decision")
            if self.decision.caster_id != actor_id:
                raise ValueError("Casting decision belongs to another actor")
            expected_state = self.decision.state
        if self.state != expected_state:
            raise ValueError("post-Test state does not match nested result")

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        object.__setattr__(self, "applied_rule_ids", rule_ids)


@dataclass(frozen=True, slots=True)
class CastingActionMiscastPreparationRequest:
    id: str
    post_test: CastingActionPostTestResult
    preparation: MiscastPreparationRequest
    rule_id: str = "RULE-COMBAT-004:casting-miscast-preparation"

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.id,
            "casting Miscast preparation request id",
        )
        if not isinstance(self.post_test, CastingActionPostTestResult):
            raise TypeError(
                "post_test must be a CastingActionPostTestResult"
            )
        if not isinstance(self.preparation, MiscastPreparationRequest):
            raise TypeError(
                "preparation must be a MiscastPreparationRequest"
            )
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class CastingActionMiscastPreparationResult:
    request_id: str
    post_test: CastingActionPostTestResult
    preparation: MiscastPreparationResult
    state: WizardMagicState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "casting Miscast preparation request_id",
        )
        if not isinstance(self.post_test, CastingActionPostTestResult):
            raise TypeError(
                "post_test must be a CastingActionPostTestResult"
            )
        if not isinstance(self.preparation, MiscastPreparationResult):
            raise TypeError(
                "preparation must be a MiscastPreparationResult"
            )
        if not isinstance(self.state, WizardMagicState):
            raise TypeError("state must be a WizardMagicState")
        actor_id = self.post_test.execution.actor_id
        if self.preparation.target_id != actor_id:
            raise ValueError("Miscast preparation belongs to another actor")
        if self.state != self.preparation.state:
            raise ValueError(
                "action Miscast state must match preparation result"
            )
        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        object.__setattr__(self, "applied_rule_ids", rule_ids)


def _validate_execution_transition(
    *,
    request_id: str,
    actor_id: str,
    slot_index: int,
    previous_state: CombatRoundState,
    state: CombatRoundState,
    slot: CombatActionSlot,
    source_request_id: str,
    result_request_id: str,
    expected_executor_rule_id: str,
    applied_rule_ids: tuple[str, ...],
) -> tuple[str, ...]:
    rule_ids = _validate_rule_ids(applied_rule_ids)
    previous_turn = previous_state.active_turn
    current_turn = state.active_turn
    if previous_turn is None or current_turn is None:
        raise ValueError("execution result requires an active turn")
    if (
        previous_turn.actor_id != actor_id
        or current_turn.actor_id != actor_id
    ):
        raise ValueError("execution actor must own both turn states")
    if slot_index > len(previous_turn.action_slots):
        raise ValueError("previous state does not contain the action slot")
    previous_slot = previous_turn.action_slots[slot_index - 1]
    if previous_slot.executed:
        raise ValueError("previous action slot must be unexecuted")
    if not slot.executed:
        raise ValueError("result action slot must be executed")
    receipt = slot.execution
    assert receipt is not None
    if receipt.id != request_id:
        raise ValueError("execution receipt does not match request_id")
    if receipt.actor_id != actor_id:
        raise ValueError("execution receipt belongs to another actor")
    if receipt.round_number != previous_state.round_number:
        raise ValueError("execution receipt belongs to another round")
    if receipt.slot_index != slot_index:
        raise ValueError("execution receipt belongs to another slot")
    if receipt.declaration != previous_slot.declaration:
        raise ValueError("execution receipt uses another action declaration")
    if receipt.executor_rule_id != expected_executor_rule_id:
        raise ValueError("execution receipt uses another executor")
    if receipt.source_request_id != source_request_id:
        raise ValueError("execution receipt does not match source request")
    if receipt.result_request_id != result_request_id:
        raise ValueError("execution receipt does not match source result")
    if receipt.executor_rule_id not in rule_ids:
        raise ValueError("executor Rule ID is missing from result trace")
    if slot != current_turn.action_slots[slot_index - 1]:
        raise ValueError("result slot is not present in the current turn")
    if slot != replace(previous_slot, execution=receipt):
        raise ValueError("execution may only add a receipt to the slot")
    expected_slots = tuple(
        slot if item.index == slot_index else item
        for item in previous_turn.action_slots
    )
    if current_turn != replace(previous_turn, action_slots=expected_slots):
        raise ValueError("execution may only update the selected action slot")
    if state != replace(previous_state, active_turn=current_turn):
        raise ValueError("execution may not mutate other round state")
    return rule_ids


def _validate_slot_index(value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("slot_index must be an integer")
    if value not in (1, 2):
        raise ValueError("slot_index must be 1 or 2")


def _validate_positive_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if value < 1:
        raise ValueError(f"{name} must be positive")


def _validate_rule_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    rule_ids = tuple(values)
    if not rule_ids:
        raise ValueError("applied_rule_ids must not be empty")
    for rule_id in rule_ids:
        _validate_non_empty_string(rule_id, "applied Rule ID")
    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError("applied_rule_ids must be unique")
    return rule_ids


def _validate_execution_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    execution_ids = tuple(values)
    for execution_id in execution_ids:
        _validate_non_empty_string(
            execution_id,
            "consumed action execution id",
        )
    if len(set(execution_ids)) != len(execution_ids):
        raise ValueError("consumed action execution IDs must be unique")
    return execution_ids


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
