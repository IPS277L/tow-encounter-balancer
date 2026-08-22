from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from towr.domain.condition_models import ConditionState
from towr.domain.movement_models import (
    FreeMovementRequest,
    FreeMovementResult,
    MovementSpeed,
)
from towr.domain.spatial_models import SpatialBattleState
from towr.domain.test_models import (
    BasicOutcome,
    OpposedOutcome,
    OpposedSide,
    OpposedTestRequest,
    OpposedTestResult,
    Skill,
    TestRequest,
    TestResult,
    TieBreak,
)
from towr.domain.turn_models import (
    ActionExecutionReceipt,
    CombatActionKind,
    CombatActionSlot,
    CombatRoundState,
    ManoeuvreKind,
)


MOVE_QUIETLY_RULE_ID = "RULE-COMBAT-014:move-quietly-action-execution"
MOVE_QUIETLY_TIE_RULE_ID = "RULE-TEST-006:move-quietly-initiator"


class MoveQuietlyOutcome(str, Enum):
    HIDDEN = "hidden"
    SUCCEEDED_WITHOUT_HIDING = "succeeded_without_hiding"
    FAILED = "failed"


class MoveQuietlyHidingChoice(str, Enum):
    DECLINE = "decline"
    HIDE_IN_CURRENT_ZONE = "hide_in_current_zone"
    HIDE_ALONG_ROUTE = "hide_along_route"


@dataclass(frozen=True, slots=True)
class MoveQuietlyObserver:
    entity_id: str
    awareness_test: TestRequest
    vigilance_priority: int
    awareness_skill: Skill = Skill.AWARENESS

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.entity_id, "observer entity_id")
        if not isinstance(self.awareness_test, TestRequest):
            raise TypeError("awareness_test must be a TestRequest")
        if not isinstance(self.awareness_skill, Skill):
            raise TypeError("awareness_skill must be a Skill")
        if self.awareness_skill is not Skill.AWARENESS:
            raise ValueError("Move Quietly observers must use Awareness")
        if not isinstance(self.vigilance_priority, int) or isinstance(
            self.vigilance_priority,
            bool,
        ):
            raise TypeError("vigilance_priority must be an integer")


@dataclass(frozen=True, slots=True)
class MoveQuietlyHiddenAttackOpportunity:
    id: str
    source_request_id: str
    actor_id: str
    hiding_position_id: str
    unaware_enemy_ids: tuple[str, ...]
    rule_id: str = MOVE_QUIETLY_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "hidden opportunity id")
        _validate_non_empty_string(
            self.source_request_id,
            "hidden opportunity source_request_id",
        )
        _validate_non_empty_string(self.actor_id, "hidden opportunity actor_id")
        _validate_non_empty_string(self.hiding_position_id, "hiding_position_id")
        enemy_ids = tuple(self.unaware_enemy_ids)
        if not enemy_ids:
            raise ValueError("hidden opportunity requires unaware enemies")
        for entity_id in enemy_ids:
            _validate_non_empty_string(entity_id, "unaware enemy entity_id")
        if len(set(enemy_ids)) != len(enemy_ids):
            raise ValueError("unaware enemy IDs must be unique")
        object.__setattr__(self, "unaware_enemy_ids", enemy_ids)
        _validate_non_empty_string(self.rule_id, "hidden opportunity rule_id")


@dataclass(frozen=True, slots=True)
class MoveQuietlyActionExecutionRequest:
    id: str
    actor_id: str
    slot_index: int
    speed: MovementSpeed
    actor_conditions: ConditionState
    observers: tuple[MoveQuietlyObserver, ...]
    opposed_test: OpposedTestRequest
    round_state: CombatRoundState
    spatial_state: SpatialBattleState
    has_cover_or_concealment: bool
    hiding_choice: MoveQuietlyHidingChoice
    free_movement: FreeMovementRequest | None = None
    hiding_position_id: str | None = None
    used_hiding_position_ids: tuple[str, ...] = ()
    stealth_skill: Skill = Skill.STEALTH
    rule_id: str = MOVE_QUIETLY_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Move Quietly request id")
        _validate_non_empty_string(self.actor_id, "actor_id")
        _validate_slot_index(self.slot_index)
        if not isinstance(self.speed, MovementSpeed):
            raise TypeError("speed must be a MovementSpeed")
        if not isinstance(self.actor_conditions, ConditionState):
            raise TypeError("actor_conditions must be a ConditionState")
        if not isinstance(self.stealth_skill, Skill):
            raise TypeError("stealth_skill must be a Skill")
        if self.stealth_skill is not Skill.STEALTH:
            raise ValueError("Move Quietly initiator must use Stealth")
        if not isinstance(self.round_state, CombatRoundState):
            raise TypeError("round_state must be a CombatRoundState")
        if not isinstance(self.spatial_state, SpatialBattleState):
            raise TypeError("spatial_state must be a SpatialBattleState")
        if not isinstance(self.opposed_test, OpposedTestRequest):
            raise TypeError("opposed_test must be an OpposedTestRequest")
        if not isinstance(self.has_cover_or_concealment, bool):
            raise TypeError("has_cover_or_concealment must be a boolean")
        if not isinstance(self.hiding_choice, MoveQuietlyHidingChoice):
            raise TypeError("hiding_choice must be a MoveQuietlyHidingChoice")
        _validate_non_empty_string(self.rule_id, "rule_id")

        if self.round_state.round_number != self.spatial_state.round_number:
            raise ValueError("turn and spatial state must use the same round")
        turn = self.round_state.active_turn
        if turn is None or turn.actor_id != self.actor_id:
            raise ValueError("Move Quietly requires the actor's active turn")
        actor = self.spatial_state.placement_for(self.actor_id)

        observers = tuple(self.observers)
        if not observers:
            raise ValueError("Move Quietly requires at least one enemy observer")
        if not all(isinstance(item, MoveQuietlyObserver) for item in observers):
            raise TypeError("observers must contain MoveQuietlyObserver values")
        observer_ids = tuple(item.entity_id for item in observers)
        if len(set(observer_ids)) != len(observer_ids):
            raise ValueError("Move Quietly observer IDs must be unique")
        test_ids = tuple(item.awareness_test.id for item in observers)
        if len(set(test_ids)) != len(test_ids):
            raise ValueError("observer Awareness Test IDs must be unique")
        for observer in observers:
            placement = self.spatial_state.placement_for(observer.entity_id)
            if placement.side_id == actor.side_id:
                raise ValueError("Move Quietly observers must be enemies")
        object.__setattr__(self, "observers", observers)

        selected = self.selected_observer
        opposed = self.opposed_test
        if not isinstance(opposed.initiator, TestRequest):
            raise TypeError("Move Quietly initiator Test must be a TestRequest")
        if not isinstance(opposed.opponent, TestRequest):
            raise TypeError("Move Quietly opponent Test must be a TestRequest")
        if not isinstance(opposed.tie_break, TieBreak):
            raise TypeError("Move Quietly opposed Test requires a TieBreak")
        if opposed.opponent != selected.awareness_test:
            raise ValueError("Move Quietly must oppose the most vigilant enemy")
        if opposed.initiator.id == opposed.opponent.id:
            raise ValueError("opposed Test sides require different request IDs")
        if (
            opposed.tie_break.rule_id != MOVE_QUIETLY_TIE_RULE_ID
            or opposed.tie_break.winner is not OpposedSide.INITIATOR
        ):
            raise ValueError("Move Quietly uses the initiator contextual tie-break")

        used_positions = tuple(self.used_hiding_position_ids)
        for position_id in used_positions:
            _validate_non_empty_string(position_id, "used hiding position_id")
        if len(set(used_positions)) != len(used_positions):
            raise ValueError("used hiding position IDs must be unique")
        object.__setattr__(self, "used_hiding_position_ids", used_positions)

        movement = self.free_movement
        if self.hiding_choice is MoveQuietlyHidingChoice.DECLINE:
            if movement is not None or self.hiding_position_id is not None:
                raise ValueError("declined hiding cannot include movement or position")
            return
        if not self.has_cover_or_concealment:
            raise ValueError("Move Quietly cannot hide without cover or concealment")
        if self.hiding_position_id is None:
            raise ValueError("conditional movement requires a hiding position ID")
        _validate_non_empty_string(self.hiding_position_id, "hiding_position_id")
        if self.hiding_position_id in used_positions:
            raise ValueError("an unopposed attack requires a new hiding position")
        if self.hiding_choice is MoveQuietlyHidingChoice.HIDE_IN_CURRENT_ZONE:
            if movement is not None:
                raise ValueError("same-Zone hiding cannot include a Zone route")
            return
        if not isinstance(movement, FreeMovementRequest):
            raise TypeError("route hiding requires a FreeMovementRequest")
        if (
            movement.round_state != self.round_state
            or movement.state != self.spatial_state
            or movement.actor_id != self.actor_id
            or movement.speed is not self.speed
            or movement.actor_conditions != self.actor_conditions
        ):
            raise ValueError("Move Quietly free movement has stale provenance")
        if movement.crosses_difficult_terrain:
            raise ValueError("Move Quietly does not bypass Difficult Terrain")

    @property
    def selected_observer(self) -> MoveQuietlyObserver:
        return max(
            enumerate(self.observers),
            key=lambda item: (item[1].vigilance_priority, -item[0]),
        )[1]


@dataclass(frozen=True, slots=True)
class MoveQuietlyActionExecutionResult:
    request_id: str
    rule_id: str
    source_request: MoveQuietlyActionExecutionRequest
    actor_id: str
    slot_index: int
    selected_observer: MoveQuietlyObserver
    opposed_test_request: OpposedTestRequest
    opposed_test_result: OpposedTestResult
    outcome: MoveQuietlyOutcome
    free_movement_result: FreeMovementResult | None
    hidden_attack_opportunity: MoveQuietlyHiddenAttackOpportunity | None
    previous_round_state: CombatRoundState
    round_state: CombatRoundState
    previous_spatial_state: SpatialBattleState
    spatial_state: SpatialBattleState
    slot: CombatActionSlot
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Move Quietly request_id")
        _validate_non_empty_string(self.rule_id, "rule_id")
        if not isinstance(self.source_request, MoveQuietlyActionExecutionRequest):
            raise TypeError(
                "source_request must be a MoveQuietlyActionExecutionRequest"
            )
        if not isinstance(self.selected_observer, MoveQuietlyObserver):
            raise TypeError("selected_observer must be a MoveQuietlyObserver")
        if not isinstance(self.opposed_test_request, OpposedTestRequest):
            raise TypeError("opposed_test_request must be an OpposedTestRequest")
        if not isinstance(self.opposed_test_result, OpposedTestResult):
            raise TypeError("opposed_test_result must be an OpposedTestResult")
        if not isinstance(self.outcome, MoveQuietlyOutcome):
            raise TypeError("outcome must be a MoveQuietlyOutcome")
        if not isinstance(self.previous_round_state, CombatRoundState):
            raise TypeError("previous_round_state must be a CombatRoundState")
        if not isinstance(self.round_state, CombatRoundState):
            raise TypeError("round_state must be a CombatRoundState")
        if not isinstance(self.previous_spatial_state, SpatialBattleState):
            raise TypeError("previous_spatial_state must be a SpatialBattleState")
        if not isinstance(self.spatial_state, SpatialBattleState):
            raise TypeError("spatial_state must be a SpatialBattleState")
        if not isinstance(self.slot, CombatActionSlot):
            raise TypeError("slot must be a CombatActionSlot")

        source = self.source_request
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.actor_id != source.actor_id
            or self.slot_index != source.slot_index
            or self.selected_observer != source.selected_observer
            or self.opposed_test_request != source.opposed_test
            or self.previous_round_state != source.round_state
            or self.previous_spatial_state != source.spatial_state
        ):
            raise ValueError("Move Quietly result has stale provenance")

        _validate_opposed_result(source.opposed_test, self.opposed_test_result)
        contest_won = self.opposed_test_result.winner is OpposedSide.INITIATOR
        if (
            contest_won
            and source.hiding_choice is not MoveQuietlyHidingChoice.DECLINE
        ):
            if self.outcome is not MoveQuietlyOutcome.HIDDEN:
                raise ValueError("successful hiding must use the HIDDEN outcome")
            self._validate_hidden_transition()
        else:
            expected_outcome = (
                MoveQuietlyOutcome.SUCCEEDED_WITHOUT_HIDING
                if contest_won
                else MoveQuietlyOutcome.FAILED
            )
            if self.outcome is not expected_outcome:
                raise ValueError("Move Quietly outcome does not match its contest")
            if self.free_movement_result is not None:
                raise ValueError("unsuccessful hiding cannot spend free movement")
            if self.hidden_attack_opportunity is not None:
                raise ValueError("unsuccessful hiding cannot create an opportunity")
            if self.spatial_state != self.previous_spatial_state:
                raise ValueError("Move Quietly changed spatial state without hiding")

        self._validate_round_transition()
        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {
            self.rule_id,
            MOVE_QUIETLY_TIE_RULE_ID,
            *self.opposed_test_result.initiator.trace.applied_rule_ids,
            *self.opposed_test_result.opponent.trace.applied_rule_ids,
        }
        if self.free_movement_result is not None:
            required.update(self.free_movement_result.applied_rule_ids)
        if self.outcome is MoveQuietlyOutcome.HIDDEN:
            required.add("RULE-COMBAT-014:free-movement")
        if not required <= set(rule_ids):
            raise ValueError("Move Quietly trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)

    def _validate_hidden_transition(self) -> None:
        source = self.source_request
        movement = source.free_movement
        if source.hiding_choice is MoveQuietlyHidingChoice.HIDE_ALONG_ROUTE:
            assert movement is not None
            result = self.free_movement_result
            if not isinstance(result, FreeMovementResult):
                raise TypeError("route hiding requires a FreeMovementResult")
            if (
                result.request_id != movement.id
                or result.rule_id != movement.rule_id
                or result.round_state != movement.round_state
                or result.actor_id != movement.actor_id
                or result.speed is not movement.speed
                or result.origin_zone_id
                != movement.state.placement_for(movement.actor_id).zone_id
                or result.traversed_zone_ids != movement.traversed_zone_ids
                or result.previous_state != movement.state
                or result.state != self.spatial_state
            ):
                raise ValueError("Move Quietly movement result has stale provenance")
        else:
            if self.free_movement_result is not None:
                raise ValueError("same-Zone hiding has no Zone movement result")
            expected_state = replace(
                self.previous_spatial_state,
                free_move_used_entity_ids=(
                    *self.previous_spatial_state.free_move_used_entity_ids,
                    self.actor_id,
                ),
            )
            if self.spatial_state != expected_state:
                raise ValueError("same-Zone hiding changed unrelated spatial state")
        opportunity = self.hidden_attack_opportunity
        if not isinstance(opportunity, MoveQuietlyHiddenAttackOpportunity):
            raise TypeError("hidden Move Quietly requires an attack opportunity")
        if (
            opportunity.id != f"{source.id}:hidden"
            or opportunity.source_request_id != source.id
            or opportunity.actor_id != source.actor_id
            or opportunity.hiding_position_id != source.hiding_position_id
            or opportunity.unaware_enemy_ids
            != tuple(item.entity_id for item in source.observers)
            or opportunity.rule_id != source.rule_id
        ):
            raise ValueError("hidden attack opportunity has stale provenance")

    def _validate_round_transition(self) -> None:
        previous_turn = self.previous_round_state.active_turn
        current_turn = self.round_state.active_turn
        if previous_turn is None or current_turn is None:
            raise ValueError("Move Quietly requires an active turn")
        if self.slot_index > len(previous_turn.action_slots):
            raise ValueError("previous state lacks the Move Quietly slot")
        if any(
            not item.executed
            for item in previous_turn.action_slots[: self.slot_index - 1]
        ):
            raise ValueError("earlier action slots must be executed first")
        previous_slot = previous_turn.action_slots[self.slot_index - 1]
        if (
            previous_slot.declaration.kind is not CombatActionKind.MANOEUVRE
            or previous_slot.declaration.manoeuvre
            is not ManoeuvreKind.MOVE_QUIETLY
        ):
            raise ValueError("result requires a Move Quietly slot")
        if previous_slot.executed or not self.slot.executed:
            raise ValueError("Move Quietly must execute one unexecuted slot")
        receipt = self.slot.execution
        assert isinstance(receipt, ActionExecutionReceipt)
        if (
            receipt.id != self.request_id
            or receipt.executor_rule_id != self.rule_id
            or receipt.source_request_id != self.request_id
            or receipt.result_request_id != self.opposed_test_result.request_id
        ):
            raise ValueError("Move Quietly receipt has stale provenance")
        if self.slot != replace(previous_slot, execution=receipt):
            raise ValueError("Move Quietly may only add its receipt")
        expected_slots = tuple(
            self.slot if item.index == self.slot_index else item
            for item in previous_turn.action_slots
        )
        if current_turn != replace(previous_turn, action_slots=expected_slots):
            raise ValueError("Move Quietly changed unrelated turn state")
        if self.round_state != replace(
            self.previous_round_state,
            active_turn=current_turn,
        ):
            raise ValueError("Move Quietly changed unrelated round state")


def _validate_opposed_result(
    request: OpposedTestRequest,
    result: OpposedTestResult,
) -> None:
    if not isinstance(result.initiator, TestResult):
        raise TypeError("Move Quietly initiator result must be a TestResult")
    if not isinstance(result.opponent, TestResult):
        raise TypeError("Move Quietly opponent result must be a TestResult")
    if (
        result.request_id != request.id
        or result.initiator.trace.request_id != request.initiator.id
        or result.opponent.trace.request_id != request.opponent.id
    ):
        raise ValueError("opposed result belongs to another Move Quietly Test")
    initiator = result.initiator.successes
    opponent = result.opponent.successes
    if initiator == 0 and opponent == 0:
        expected = (
            OpposedOutcome.BOTH_FAIL,
            None,
            0,
            None,
            False,
            None,
        )
    elif initiator == opponent:
        expected = (
            OpposedOutcome.INITIATOR_WINS,
            OpposedSide.INITIATOR,
            0,
            BasicOutcome.MARGINAL_SUCCESS,
            True,
            request.tie_break.rule_id,
        )
    elif initiator > opponent:
        margin = initiator - opponent
        expected = (
            OpposedOutcome.INITIATOR_WINS,
            OpposedSide.INITIATOR,
            margin,
            _basic_outcome(margin),
            False,
            None,
        )
    else:
        margin = opponent - initiator
        expected = (
            OpposedOutcome.OPPONENT_WINS,
            OpposedSide.OPPONENT,
            margin,
            _basic_outcome(margin),
            False,
            None,
        )
    actual = (
        result.outcome,
        result.winner,
        result.success_margin,
        result.consequence,
        result.tie_break_applied,
        result.tie_break_rule_id,
    )
    if actual != expected:
        raise ValueError("Move Quietly opposed result is internally inconsistent")


def _basic_outcome(successes: int) -> BasicOutcome:
    if successes == 1:
        return BasicOutcome.MARGINAL_SUCCESS
    if successes == 2:
        return BasicOutcome.SUCCESS
    return BasicOutcome.TOTAL_SUCCESS


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
