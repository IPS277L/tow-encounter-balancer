from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.resolution_models import KernelAttackRequest, ResolutionResult
from towr.domain.turn_models import CombatActionSlot, CombatRoundState


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
        rule_ids = tuple(self.applied_rule_ids)
        if not rule_ids:
            raise ValueError("applied_rule_ids must not be empty")
        for rule_id in rule_ids:
            _validate_non_empty_string(rule_id, "applied Rule ID")
        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError("applied_rule_ids must be unique")
        previous_turn = self.previous_state.active_turn
        current_turn = self.state.active_turn
        if previous_turn is None or current_turn is None:
            raise ValueError("execution result requires an active turn")
        if (
            previous_turn.actor_id != self.actor_id
            or current_turn.actor_id != self.actor_id
        ):
            raise ValueError("execution actor must own both turn states")
        if self.slot_index > len(previous_turn.action_slots):
            raise ValueError("previous state does not contain the action slot")
        previous_slot = previous_turn.action_slots[self.slot_index - 1]
        if previous_slot.executed:
            raise ValueError("previous action slot must be unexecuted")
        if not self.slot.executed:
            raise ValueError("result action slot must be executed")
        receipt = self.slot.execution
        assert receipt is not None
        if receipt.id != self.request_id:
            raise ValueError("execution receipt does not match request_id")
        if receipt.source_request_id != self.resolution.request_id:
            raise ValueError("execution source does not match kernel resolution")
        if receipt.result_request_id != self.resolution.request_id:
            raise ValueError("execution result does not match kernel resolution")
        if receipt.executor_rule_id not in rule_ids:
            raise ValueError("executor Rule ID is missing from result trace")
        if self.slot != current_turn.action_slots[self.slot_index - 1]:
            raise ValueError("result slot is not present in the current turn")
        if self.slot != CombatActionSlot(
            index=previous_slot.index,
            declaration=previous_slot.declaration,
            grant=previous_slot.grant,
            grant_rule_id=previous_slot.grant_rule_id,
            execution=receipt,
        ):
            raise ValueError("execution may only add a receipt to the slot")
        expected_slots = tuple(
            self.slot if item.index == self.slot_index else item
            for item in previous_turn.action_slots
        )
        if current_turn != replace(previous_turn, action_slots=expected_slots):
            raise ValueError("execution may only update the selected action slot")
        if self.state != replace(self.previous_state, active_turn=current_turn):
            raise ValueError("execution may not mutate other round state")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
