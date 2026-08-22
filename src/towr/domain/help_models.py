from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.condition_models import ConditionState
from towr.domain.test_models import DiceModifier, Skill, TestRequest, TestResult
from towr.domain.turn_models import (
    ActionExecutionReceipt,
    CombatActionKind,
    CombatActionSlot,
    CombatRoundState,
)


HELP_ACTION_RULE_ID = "RULE-COMBAT-004:help-action-execution"
HELP_BONUS_RULE_ID = "RULE-TEST-005:help-bonus-application"


@dataclass(frozen=True, slots=True)
class HelpBonusSnapshot:
    id: str
    source_request_id: str
    source_test_id: str
    helper_id: str
    beneficiary_id: str
    beneficiary_test_id: str
    help_skill: Skill
    beneficiary_skill: Skill
    bonus_dice: int
    different_skill_approved_by_gm: bool
    rule_id: str = HELP_BONUS_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Help bonus id")
        _validate_non_empty_string(
            self.source_request_id,
            "Help bonus source_request_id",
        )
        _validate_non_empty_string(self.source_test_id, "Help source_test_id")
        _validate_non_empty_string(self.helper_id, "Help helper_id")
        _validate_non_empty_string(self.beneficiary_id, "Help beneficiary_id")
        _validate_non_empty_string(
            self.beneficiary_test_id,
            "Help beneficiary_test_id",
        )
        if not isinstance(self.help_skill, Skill):
            raise TypeError("help_skill must be a Skill")
        if not isinstance(self.beneficiary_skill, Skill):
            raise TypeError("beneficiary_skill must be a Skill")
        if not isinstance(self.bonus_dice, int) or isinstance(
            self.bonus_dice,
            bool,
        ):
            raise TypeError("Help bonus_dice must be an integer")
        if self.bonus_dice < 0:
            raise ValueError("Help bonus_dice must not be negative")
        if not isinstance(self.different_skill_approved_by_gm, bool):
            raise TypeError("different_skill_approved_by_gm must be a boolean")
        if (
            self.help_skill is not self.beneficiary_skill
            and not self.different_skill_approved_by_gm
        ):
            raise ValueError("a different Help Skill requires GM approval")
        _validate_non_empty_string(self.rule_id, "Help bonus rule_id")


@dataclass(frozen=True, slots=True)
class HelpActionExecutionRequest:
    id: str
    round_state: CombatRoundState
    actor_id: str
    actor_conditions: ConditionState
    beneficiary_id: str
    beneficiary_test_id: str
    slot_index: int
    help_test: TestRequest
    help_skill: Skill
    beneficiary_skill: Skill
    different_skill_approved_by_gm: bool = False
    rule_id: str = HELP_ACTION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Help request id")
        if not isinstance(self.round_state, CombatRoundState):
            raise TypeError("round_state must be a CombatRoundState")
        _validate_non_empty_string(self.actor_id, "Help actor_id")
        if not isinstance(self.actor_conditions, ConditionState):
            raise TypeError("actor_conditions must be a ConditionState")
        _validate_non_empty_string(self.beneficiary_id, "beneficiary_id")
        _validate_non_empty_string(self.beneficiary_test_id, "beneficiary_test_id")
        _validate_slot_index(self.slot_index)
        if not isinstance(self.help_test, TestRequest):
            raise TypeError("help_test must be a TestRequest")
        if not isinstance(self.help_skill, Skill):
            raise TypeError("help_skill must be a Skill")
        if not isinstance(self.beneficiary_skill, Skill):
            raise TypeError("beneficiary_skill must be a Skill")
        if not isinstance(self.different_skill_approved_by_gm, bool):
            raise TypeError("different_skill_approved_by_gm must be a boolean")
        if (
            self.help_skill is not self.beneficiary_skill
            and not self.different_skill_approved_by_gm
        ):
            raise ValueError("a different Help Skill requires GM approval")
        if self.help_test.id == self.beneficiary_test_id:
            raise ValueError("Help and beneficiary Tests require different IDs")
        _validate_non_empty_string(self.rule_id, "Help rule_id")

        turn = self.round_state.active_turn
        if turn is None or turn.actor_id != self.actor_id:
            raise ValueError("Help requires the actor's active turn")
        if self.actor_id == self.beneficiary_id:
            raise ValueError("Help requires another character")
        actor = self.round_state.participant_for(self.actor_id)
        beneficiary = self.round_state.participant_for(self.beneficiary_id)
        if actor.side is not beneficiary.side:
            raise ValueError("Help beneficiary must be an ally")


@dataclass(frozen=True, slots=True)
class HelpActionExecutionResult:
    request_id: str
    rule_id: str
    source_request: HelpActionExecutionRequest
    help_test_result: TestResult
    bonus: HelpBonusSnapshot
    previous_round_state: CombatRoundState
    round_state: CombatRoundState
    slot: CombatActionSlot
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Help result request_id")
        _validate_non_empty_string(self.rule_id, "Help result rule_id")
        if not isinstance(self.source_request, HelpActionExecutionRequest):
            raise TypeError("source_request must be a HelpActionExecutionRequest")
        if not isinstance(self.help_test_result, TestResult):
            raise TypeError("help_test_result must be a TestResult")
        if not isinstance(self.bonus, HelpBonusSnapshot):
            raise TypeError("bonus must be a HelpBonusSnapshot")
        if not isinstance(self.previous_round_state, CombatRoundState):
            raise TypeError("previous_round_state must be a CombatRoundState")
        if not isinstance(self.round_state, CombatRoundState):
            raise TypeError("round_state must be a CombatRoundState")
        if not isinstance(self.slot, CombatActionSlot):
            raise TypeError("slot must be a CombatActionSlot")

        source = self.source_request
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.previous_round_state != source.round_state
            or self.help_test_result.trace.request_id != source.help_test.id
        ):
            raise ValueError("Help result has stale provenance")
        expected_bonus = HelpBonusSnapshot(
            id=f"{source.id}:bonus",
            source_request_id=source.id,
            source_test_id=source.help_test.id,
            helper_id=source.actor_id,
            beneficiary_id=source.beneficiary_id,
            beneficiary_test_id=source.beneficiary_test_id,
            help_skill=source.help_skill,
            beneficiary_skill=source.beneficiary_skill,
            bonus_dice=self.help_test_result.successes,
            different_skill_approved_by_gm=(
                source.different_skill_approved_by_gm
            ),
        )
        if self.bonus != expected_bonus:
            raise ValueError("Help bonus does not match its source Test")
        self._validate_round_transition()

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {
            self.rule_id,
            self.bonus.rule_id,
            *self.help_test_result.trace.applied_rule_ids,
        }
        if not required <= set(rule_ids):
            raise ValueError("Help trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)

    def _validate_round_transition(self) -> None:
        source = self.source_request
        previous_turn = self.previous_round_state.active_turn
        current_turn = self.round_state.active_turn
        if previous_turn is None or current_turn is None:
            raise ValueError("Help requires an active turn")
        if source.slot_index > len(previous_turn.action_slots):
            raise ValueError("previous state lacks the Help slot")
        if any(
            not item.executed
            for item in previous_turn.action_slots[: source.slot_index - 1]
        ):
            raise ValueError("earlier action slots must be executed first")
        previous_slot = previous_turn.action_slots[source.slot_index - 1]
        if previous_slot.declaration.kind is not CombatActionKind.HELP:
            raise ValueError("result requires a Help slot")
        if previous_slot.executed or not self.slot.executed:
            raise ValueError("Help must execute one unexecuted slot")
        receipt = self.slot.execution
        assert isinstance(receipt, ActionExecutionReceipt)
        if (
            receipt.id != source.id
            or receipt.executor_rule_id != source.rule_id
            or receipt.source_request_id != source.id
            or receipt.result_request_id != self.help_test_result.trace.request_id
        ):
            raise ValueError("Help receipt has stale provenance")
        if self.slot != replace(previous_slot, execution=receipt):
            raise ValueError("Help may only add its receipt")
        expected_slots = tuple(
            self.slot if item.index == source.slot_index else item
            for item in previous_turn.action_slots
        )
        if current_turn != replace(previous_turn, action_slots=expected_slots):
            raise ValueError("Help changed unrelated turn state")
        if self.round_state != replace(
            self.previous_round_state,
            active_turn=current_turn,
        ):
            raise ValueError("Help changed unrelated round state")


@dataclass(frozen=True, slots=True)
class HelpBonusApplicationRequest:
    id: str
    help: HelpActionExecutionResult
    beneficiary_id: str
    beneficiary_skill: Skill
    test: TestRequest
    rule_id: str = HELP_BONUS_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Help application request id")
        if not isinstance(self.help, HelpActionExecutionResult):
            raise TypeError("help must be a HelpActionExecutionResult")
        _validate_non_empty_string(self.beneficiary_id, "beneficiary_id")
        if not isinstance(self.beneficiary_skill, Skill):
            raise TypeError("beneficiary_skill must be a Skill")
        if not isinstance(self.test, TestRequest):
            raise TypeError("test must be a TestRequest")
        _validate_non_empty_string(self.rule_id, "Help application rule_id")

        bonus = self.help.bonus
        if (
            self.beneficiary_id != bonus.beneficiary_id
            or self.beneficiary_skill is not bonus.beneficiary_skill
            or self.test.id != bonus.beneficiary_test_id
        ):
            raise ValueError("Help application does not match its intended Test")


@dataclass(frozen=True, slots=True)
class HelpBonusApplicationResult:
    request_id: str
    rule_id: str
    source_request: HelpBonusApplicationRequest
    test: TestRequest
    modifier: DiceModifier | None
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Help application request_id")
        _validate_non_empty_string(self.rule_id, "Help application rule_id")
        if not isinstance(self.source_request, HelpBonusApplicationRequest):
            raise TypeError(
                "source_request must be a HelpBonusApplicationRequest"
            )
        if not isinstance(self.test, TestRequest):
            raise TypeError("test must be a TestRequest")
        if self.modifier is not None and not isinstance(self.modifier, DiceModifier):
            raise TypeError("modifier must be a DiceModifier or None")

        source = self.source_request
        if self.request_id != source.id or self.rule_id != source.rule_id:
            raise ValueError("Help application result has stale provenance")
        expected_test, expected_modifier = _expected_help_application(source)
        if self.test != expected_test or self.modifier != expected_modifier:
            raise ValueError("Help application result is inconsistent")
        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        if {self.rule_id, source.help.rule_id} - set(rule_ids):
            raise ValueError("Help application trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


def _expected_help_application(
    request: HelpBonusApplicationRequest,
) -> tuple[TestRequest, DiceModifier | None]:
    if request.help.bonus.bonus_dice == 0:
        return request.test, None
    modifier = DiceModifier(
        rule_id=request.rule_id,
        amount=request.help.bonus.bonus_dice,
    )
    return (
        replace(
            request.test,
            dice_modifiers=(*request.test.dice_modifiers, modifier),
        ),
        modifier,
    )


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


def _validate_slot_index(value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("slot_index must be an integer")
    if value not in (1, 2):
        raise ValueError("slot_index must be 1 or 2")
