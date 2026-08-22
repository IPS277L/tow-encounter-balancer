from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.condition_models import (
    Condition,
    ConditionState,
    EffectClassification,
)
from towr.domain.test_models import (
    OpposedSide,
    OpposedTestRequest,
    OpposedTestResult,
    Skill,
    TestRequest,
    TestResult,
)
from towr.domain.turn_models import (
    ActionExecutionReceipt,
    CombatActionKind,
    CombatActionSlot,
    CombatRoundState,
    ImproviseKind,
)


SKILL_IMPROVISE_ACTION_RULE_ID = (
    "RULE-COMBAT-004:skill-improvise-action-execution"
)
SKILL_IMPROVISE_CONDITION_RULE_ID = (
    "RULE-COMBAT-004:skill-improvise-condition-application"
)

SkillImproviseTestRequest = TestRequest | OpposedTestRequest
SkillImproviseTestResult = TestResult | OpposedTestResult
SKILL_IMPROVISE_DIRECT_CONDITIONS = frozenset(
    (Condition.PRONE, Condition.DISTRACTED)
)


@dataclass(frozen=True, slots=True)
class SkillImproviseApproach:
    id: str
    skill: Skill

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Skill Improvise approach id")
        if not isinstance(self.skill, Skill):
            raise TypeError("Skill Improvise approach requires a Skill")


@dataclass(frozen=True, slots=True)
class SkillImproviseConditionEffect:
    target_id: str
    condition: Condition
    gm_approval_id: str
    classification: EffectClassification = EffectClassification.UNCLASSIFIED

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.target_id, "effect target_id")
        if not isinstance(self.condition, Condition):
            raise TypeError("effect condition must be a Condition")
        if self.condition not in SKILL_IMPROVISE_DIRECT_CONDITIONS:
            raise ValueError(
                "this Condition requires a dedicated Improvise effect resolver"
            )
        _validate_non_empty_string(self.gm_approval_id, "GM approval id")
        if not isinstance(self.classification, EffectClassification):
            raise TypeError(
                "effect classification must be an EffectClassification"
            )


@dataclass(frozen=True, slots=True)
class SkillImproviseConditionApplicationRequest:
    id: str
    source_action_id: str
    source_test_id: str
    actor_id: str
    target_id: str
    condition: Condition
    gm_approval_id: str
    classification: EffectClassification
    rule_id: str = SKILL_IMPROVISE_CONDITION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Condition application id")
        _validate_non_empty_string(self.source_action_id, "source_action_id")
        _validate_non_empty_string(self.source_test_id, "source_test_id")
        _validate_non_empty_string(self.actor_id, "application actor_id")
        _validate_non_empty_string(self.target_id, "application target_id")
        if not isinstance(self.condition, Condition):
            raise TypeError("application condition must be a Condition")
        _validate_non_empty_string(self.gm_approval_id, "GM approval id")
        if not isinstance(self.classification, EffectClassification):
            raise TypeError(
                "application classification must be an "
                "EffectClassification"
            )
        _validate_non_empty_string(self.rule_id, "application rule_id")


@dataclass(frozen=True, slots=True)
class SkillImproviseActionExecutionRequest:
    id: str
    round_state: CombatRoundState
    actor_id: str
    actor_conditions: ConditionState
    slot_index: int
    approach: SkillImproviseApproach
    test: SkillImproviseTestRequest
    condition_effect: SkillImproviseConditionEffect | None = None
    rule_id: str = SKILL_IMPROVISE_ACTION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Skill Improvise request id")
        if not isinstance(self.round_state, CombatRoundState):
            raise TypeError("round_state must be a CombatRoundState")
        _validate_non_empty_string(self.actor_id, "Skill Improvise actor_id")
        if not isinstance(self.actor_conditions, ConditionState):
            raise TypeError("actor_conditions must be a ConditionState")
        _validate_slot_index(self.slot_index)
        if not isinstance(self.approach, SkillImproviseApproach):
            raise TypeError("approach must be a SkillImproviseApproach")
        if not isinstance(self.test, (TestRequest, OpposedTestRequest)):
            raise TypeError("test must be a TestRequest or OpposedTestRequest")
        if self.condition_effect is not None and not isinstance(
            self.condition_effect,
            SkillImproviseConditionEffect,
        ):
            raise TypeError(
                "condition_effect must be a "
                "SkillImproviseConditionEffect or None"
            )
        _validate_non_empty_string(self.rule_id, "Skill Improvise rule_id")

        turn = self.round_state.active_turn
        if turn is None or turn.actor_id != self.actor_id:
            raise ValueError("Skill Improvise requires the actor's active turn")
        if self.condition_effect is not None:
            self.round_state.participant_for(self.condition_effect.target_id)


@dataclass(frozen=True, slots=True)
class SkillImproviseActionExecutionResult:
    request_id: str
    rule_id: str
    source_request: SkillImproviseActionExecutionRequest
    test_result: SkillImproviseTestResult
    condition_application: SkillImproviseConditionApplicationRequest | None
    previous_round_state: CombatRoundState
    round_state: CombatRoundState
    slot: CombatActionSlot
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Skill Improvise result request_id",
        )
        _validate_non_empty_string(self.rule_id, "Skill Improvise result rule_id")
        if not isinstance(
            self.source_request,
            SkillImproviseActionExecutionRequest,
        ):
            raise TypeError(
                "source_request must be a "
                "SkillImproviseActionExecutionRequest"
            )
        if not isinstance(self.test_result, (TestResult, OpposedTestResult)):
            raise TypeError(
                "test_result must be a TestResult or OpposedTestResult"
            )
        if self.condition_application is not None and not isinstance(
            self.condition_application,
            SkillImproviseConditionApplicationRequest,
        ):
            raise TypeError(
                "condition_application must be a "
                "SkillImproviseConditionApplicationRequest or None"
            )
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
        ):
            raise ValueError("Skill Improvise result has stale provenance")
        _validate_test_result(source.test, self.test_result)
        expected_application = _expected_condition_application(
            source,
            self.test_result,
        )
        if self.condition_application != expected_application:
            raise ValueError("Skill Improvise application is inconsistent")
        self._validate_round_transition()

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {self.rule_id, *_test_rule_ids(self.test_result)}
        if not required <= set(rule_ids):
            raise ValueError("Skill Improvise trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)

    def _validate_round_transition(self) -> None:
        source = self.source_request
        previous_turn = self.previous_round_state.active_turn
        current_turn = self.round_state.active_turn
        if previous_turn is None or current_turn is None:
            raise ValueError("Skill Improvise requires an active turn")
        if source.slot_index > len(previous_turn.action_slots):
            raise ValueError("previous state lacks the Skill Improvise slot")
        if any(
            not item.executed
            for item in previous_turn.action_slots[: source.slot_index - 1]
        ):
            raise ValueError("earlier action slots must be executed first")
        previous_slot = previous_turn.action_slots[source.slot_index - 1]
        declaration = previous_slot.declaration
        if (
            declaration.kind is not CombatActionKind.IMPROVISE
            or declaration.improvise_kind is not ImproviseKind.SKILL
        ):
            raise ValueError("result requires a Skill Improvise slot")
        if declaration.improvise_approach_id != source.approach.id:
            raise ValueError("Skill Improvise approach does not match its slot")
        if declaration.improvise_produces_attack:
            raise ValueError("attacking Skill Improvise needs an attack executor")
        if previous_slot.executed or not self.slot.executed:
            raise ValueError("Skill Improvise must execute one unexecuted slot")
        receipt = self.slot.execution
        assert isinstance(receipt, ActionExecutionReceipt)
        if (
            receipt.id != source.id
            or receipt.executor_rule_id != source.rule_id
            or receipt.source_request_id != source.id
            or receipt.result_request_id != _test_result_id(self.test_result)
        ):
            raise ValueError("Skill Improvise receipt has stale provenance")
        if self.slot != replace(previous_slot, execution=receipt):
            raise ValueError("Skill Improvise may only add its receipt")
        expected_slots = tuple(
            self.slot if item.index == source.slot_index else item
            for item in previous_turn.action_slots
        )
        if current_turn != replace(previous_turn, action_slots=expected_slots):
            raise ValueError("Skill Improvise changed unrelated turn state")
        if self.round_state != replace(
            self.previous_round_state,
            active_turn=current_turn,
        ):
            raise ValueError("Skill Improvise changed unrelated round state")


def _expected_condition_application(
    request: SkillImproviseActionExecutionRequest,
    result: SkillImproviseTestResult,
) -> SkillImproviseConditionApplicationRequest | None:
    effect = request.condition_effect
    if effect is None or not _test_succeeded(result):
        return None
    return SkillImproviseConditionApplicationRequest(
        id=f"{request.id}:condition-application",
        source_action_id=request.id,
        source_test_id=_test_result_id(result),
        actor_id=request.actor_id,
        target_id=effect.target_id,
        condition=effect.condition,
        gm_approval_id=effect.gm_approval_id,
        classification=effect.classification,
    )


def _validate_test_result(
    request: SkillImproviseTestRequest,
    result: SkillImproviseTestResult,
) -> None:
    if isinstance(request, TestRequest):
        if not isinstance(result, TestResult):
            raise TypeError("basic Skill Improvise requires a TestResult")
        if result.trace.request_id != request.id:
            raise ValueError("Skill Improvise Test result belongs elsewhere")
        return
    if not isinstance(result, OpposedTestResult):
        raise TypeError("opposed Skill Improvise requires OpposedTestResult")
    if (
        result.request_id != request.id
        or result.initiator.trace.request_id != request.initiator.id
        or result.opponent.trace.request_id != request.opponent.id
    ):
        raise ValueError("Skill Improvise Opposed Test belongs elsewhere")


def _test_succeeded(result: SkillImproviseTestResult) -> bool:
    if isinstance(result, TestResult):
        return result.succeeded
    return result.winner is OpposedSide.INITIATOR


def _test_result_id(result: SkillImproviseTestResult) -> str:
    if isinstance(result, TestResult):
        return result.trace.request_id
    return result.request_id


def _test_rule_ids(result: SkillImproviseTestResult) -> tuple[str, ...]:
    if isinstance(result, TestResult):
        return result.trace.applied_rule_ids
    tie_rule_ids = (
        (result.tie_break_rule_id,)
        if result.tie_break_applied and result.tie_break_rule_id is not None
        else ()
    )
    return tuple(
        dict.fromkeys(
            (
                *result.initiator.trace.applied_rule_ids,
                *result.opponent.trace.applied_rule_ids,
                *tie_rule_ids,
            )
        )
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


def _validate_slot_index(value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("slot_index must be an integer")
    if value not in (1, 2):
        raise ValueError("slot_index must be 1 or 2")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
