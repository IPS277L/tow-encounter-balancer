from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from towr.domain.condition_models import (
    Condition,
    ConditionApplicationResult,
    ConditionState,
)
from towr.domain.spatial_models import (
    SpatialBattleState,
    SpatialEntityPlacement,
)
from towr.domain.turn_models import (
    ActionExecutionReceipt,
    CombatActionKind,
    CombatActionSlot,
    CombatRoundState,
    ManoeuvreKind,
)
from towr.domain.test_models import Skill, TestRequest, TestResult


class MovementSpeed(str, Enum):
    SLOW = "slow"
    NORMAL = "normal"
    FAST = "fast"

    @property
    def free_move_zone_limit(self) -> int:
        return 2 if self is MovementSpeed.FAST else 1


class ProneRemovalTargetKind(str, Enum):
    SELF = "self"
    ALLY = "ally"


class RunAthleticsOutcome(str, Enum):
    MOVED_EXTRA_ZONE = "moved_extra_zone"
    FAILED_STAGGERED = "failed_staggered"
    FAILED_ALREADY_STAGGERED = "failed_already_staggered"


@dataclass(frozen=True, slots=True)
class FreeMovementRequest:
    id: str
    round_state: CombatRoundState
    state: SpatialBattleState
    actor_id: str
    speed: MovementSpeed
    actor_conditions: ConditionState
    traversed_zone_ids: tuple[str, ...]
    path_entity_ids: tuple[str, ...] = ()
    crosses_obstacle: bool = False
    crosses_difficult_terrain: bool = False
    rule_id: str = "RULE-COMBAT-014:free-movement"

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "free movement request id")
        if not isinstance(self.round_state, CombatRoundState):
            raise TypeError("round_state must be a CombatRoundState")
        if not isinstance(self.state, SpatialBattleState):
            raise TypeError("state must be a SpatialBattleState")
        _validate_non_empty_string(self.actor_id, "actor_id")
        if not isinstance(self.speed, MovementSpeed):
            raise TypeError("speed must be a MovementSpeed")
        if not isinstance(self.actor_conditions, ConditionState):
            raise TypeError("actor_conditions must be a ConditionState")
        if self.round_state.round_number != self.state.round_number:
            raise ValueError("turn and spatial state must use the same round")
        active_turn = self.round_state.active_turn
        if active_turn is None:
            raise ValueError("free movement requires an active turn")
        if active_turn.actor_id != self.actor_id:
            raise ValueError("free movement belongs to another turn actor")

        origin_zone_id = self.state.placement_for(self.actor_id).zone_id
        traversed_zone_ids = tuple(self.traversed_zone_ids)
        if not traversed_zone_ids:
            raise ValueError("free movement must cross at least one Zone boundary")
        for zone_id in traversed_zone_ids:
            _validate_non_empty_string(zone_id, "traversed zone_id")
        if len(set(traversed_zone_ids)) != len(traversed_zone_ids):
            raise ValueError("free movement cannot visit a Zone twice")
        if origin_zone_id in traversed_zone_ids:
            raise ValueError("free movement cannot return to its origin Zone")
        if len(traversed_zone_ids) > self.speed.free_move_zone_limit:
            raise ValueError("free movement route exceeds the creature's Speed")
        object.__setattr__(self, "traversed_zone_ids", traversed_zone_ids)

        path_entity_ids = tuple(self.path_entity_ids)
        for entity_id in path_entity_ids:
            _validate_non_empty_string(entity_id, "path entity_id")
            self.state.placement_for(entity_id)
        if len(set(path_entity_ids)) != len(path_entity_ids):
            raise ValueError("path entity IDs must be unique")
        if self.actor_id in path_entity_ids:
            raise ValueError("free movement path cannot cross the actor")
        object.__setattr__(self, "path_entity_ids", path_entity_ids)
        _validate_bool(self.crosses_obstacle, "crosses_obstacle")
        _validate_bool(
            self.crosses_difficult_terrain,
            "crosses_difficult_terrain",
        )
        _validate_non_empty_string(self.rule_id, "rule_id")

    @property
    def destination_zone_id(self) -> str:
        return self.traversed_zone_ids[-1]


@dataclass(frozen=True, slots=True)
class FreeMovementResult:
    request_id: str
    rule_id: str
    round_state: CombatRoundState
    actor_id: str
    speed: MovementSpeed
    origin_zone_id: str
    traversed_zone_ids: tuple[str, ...]
    previous_state: SpatialBattleState
    state: SpatialBattleState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "free movement request_id")
        _validate_non_empty_string(self.rule_id, "rule_id")
        if not isinstance(self.round_state, CombatRoundState):
            raise TypeError("round_state must be a CombatRoundState")
        _validate_non_empty_string(self.actor_id, "actor_id")
        if not isinstance(self.speed, MovementSpeed):
            raise TypeError("speed must be a MovementSpeed")
        _validate_non_empty_string(self.origin_zone_id, "origin_zone_id")
        if not isinstance(self.previous_state, SpatialBattleState):
            raise TypeError("previous_state must be a SpatialBattleState")
        if not isinstance(self.state, SpatialBattleState):
            raise TypeError("state must be a SpatialBattleState")
        if self.round_state.round_number != self.previous_state.round_number:
            raise ValueError("turn and spatial result use different rounds")
        active_turn = self.round_state.active_turn
        if active_turn is None or active_turn.actor_id != self.actor_id:
            raise ValueError("free movement result belongs to another turn")

        traversed_zone_ids = tuple(self.traversed_zone_ids)
        if not traversed_zone_ids:
            raise ValueError("free movement result requires a Zone route")
        for zone_id in traversed_zone_ids:
            _validate_non_empty_string(zone_id, "traversed zone_id")
        if len(set(traversed_zone_ids)) != len(traversed_zone_ids):
            raise ValueError("free movement result cannot repeat a Zone")
        if self.origin_zone_id in traversed_zone_ids:
            raise ValueError("free movement result returns to its origin")
        if len(traversed_zone_ids) > self.speed.free_move_zone_limit:
            raise ValueError("free movement result exceeds Speed")
        object.__setattr__(self, "traversed_zone_ids", traversed_zone_ids)

        previous_actor = self.previous_state.placement_for(self.actor_id)
        if previous_actor.zone_id != self.origin_zone_id:
            raise ValueError("previous state does not match movement origin")
        previous_zone_id = self.origin_zone_id
        for zone_id in traversed_zone_ids:
            if not self.previous_state.graph.are_adjacent(
                previous_zone_id,
                zone_id,
            ):
                raise ValueError("free movement route must follow Zone links")
            previous_zone_id = zone_id

        destination_zone_id = traversed_zone_ids[-1]
        expected_placements = tuple(
            SpatialEntityPlacement(
                entity_id=placement.entity_id,
                side_id=placement.side_id,
                zone_id=destination_zone_id,
            )
            if placement.entity_id == self.actor_id
            else placement
            for placement in self.previous_state.placements
        )
        expected_state = SpatialBattleState(
            graph=self.previous_state.graph,
            placements=expected_placements,
            round_number=self.previous_state.round_number,
            gave_ground_entity_ids=(
                self.previous_state.gave_ground_entity_ids
            ),
            free_move_used_entity_ids=(
                *self.previous_state.free_move_used_entity_ids,
                self.actor_id,
            ),
        )
        if self.state != expected_state:
            raise ValueError("free movement result changed unrelated state")

        rule_ids = tuple(self.applied_rule_ids)
        if not rule_ids:
            raise ValueError("applied_rule_ids must not be empty")
        for rule_id in rule_ids:
            _validate_non_empty_string(rule_id, "applied Rule ID")
        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError("applied_rule_ids must be unique")
        if self.rule_id not in rule_ids:
            raise ValueError("free movement source rule is missing from trace")
        object.__setattr__(self, "applied_rule_ids", rule_ids)

    @property
    def destination_zone_id(self) -> str:
        return self.traversed_zone_ids[-1]


@dataclass(frozen=True, slots=True)
class FreeMoveProneRemovalRequest:
    id: str
    round_state: CombatRoundState
    state: SpatialBattleState
    actor_id: str
    target_kind: ProneRemovalTargetKind
    target_id: str
    target_conditions: ConditionState
    target_in_close_range: bool | None
    actor_has_enemy_in_close_range: bool
    rule_id: str = "RULE-COMBAT-014:free-move-prone-removal"

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Prone removal request id")
        if not isinstance(self.round_state, CombatRoundState):
            raise TypeError("round_state must be a CombatRoundState")
        if not isinstance(self.state, SpatialBattleState):
            raise TypeError("state must be a SpatialBattleState")
        _validate_non_empty_string(self.actor_id, "actor_id")
        if not isinstance(self.target_kind, ProneRemovalTargetKind):
            raise TypeError("target_kind must be a ProneRemovalTargetKind")
        _validate_non_empty_string(self.target_id, "target_id")
        if not isinstance(self.target_conditions, ConditionState):
            raise TypeError("target_conditions must be a ConditionState")
        if self.round_state.round_number != self.state.round_number:
            raise ValueError("turn and spatial state must use the same round")
        active_turn = self.round_state.active_turn
        if active_turn is None:
            raise ValueError("Prone removal requires an active turn")
        if active_turn.actor_id != self.actor_id:
            raise ValueError("Prone removal belongs to another turn actor")

        actor = self.state.placement_for(self.actor_id)
        target = self.state.placement_for(self.target_id)
        if self.target_kind is ProneRemovalTargetKind.SELF:
            if self.target_id != self.actor_id:
                raise ValueError("SELF Prone removal must target the actor")
            if self.target_in_close_range is not None:
                raise ValueError("SELF Prone removal has no ally range fact")
        else:
            if self.target_id == self.actor_id:
                raise ValueError("ALLY Prone removal must target another entity")
            if target.side_id != actor.side_id:
                raise ValueError("Prone removal target must be an ally")
            if not isinstance(self.target_in_close_range, bool):
                raise TypeError(
                    "ALLY Prone removal requires a Close Range fact"
                )
        _validate_bool(
            self.actor_has_enemy_in_close_range,
            "actor_has_enemy_in_close_range",
        )
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class FreeMoveProneRemovalResult:
    request_id: str
    rule_id: str
    round_state: CombatRoundState
    actor_id: str
    target_kind: ProneRemovalTargetKind
    target_id: str
    target_in_close_range: bool | None
    actor_has_enemy_in_close_range: bool
    previous_target_conditions: ConditionState
    target_conditions: ConditionState
    previous_state: SpatialBattleState
    state: SpatialBattleState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Prone removal request_id")
        _validate_non_empty_string(self.rule_id, "rule_id")
        if not isinstance(self.round_state, CombatRoundState):
            raise TypeError("round_state must be a CombatRoundState")
        _validate_non_empty_string(self.actor_id, "actor_id")
        if not isinstance(self.target_kind, ProneRemovalTargetKind):
            raise TypeError("target_kind must be a ProneRemovalTargetKind")
        _validate_non_empty_string(self.target_id, "target_id")
        if not isinstance(self.previous_target_conditions, ConditionState):
            raise TypeError(
                "previous_target_conditions must be a ConditionState"
            )
        if not isinstance(self.target_conditions, ConditionState):
            raise TypeError("target_conditions must be a ConditionState")
        if not isinstance(self.previous_state, SpatialBattleState):
            raise TypeError("previous_state must be a SpatialBattleState")
        if not isinstance(self.state, SpatialBattleState):
            raise TypeError("state must be a SpatialBattleState")
        if self.round_state.round_number != self.previous_state.round_number:
            raise ValueError("turn and spatial result use different rounds")
        active_turn = self.round_state.active_turn
        if active_turn is None or active_turn.actor_id != self.actor_id:
            raise ValueError("Prone removal result belongs to another turn")

        actor = self.previous_state.placement_for(self.actor_id)
        target = self.previous_state.placement_for(self.target_id)
        if self.target_kind is ProneRemovalTargetKind.SELF:
            if self.target_id != self.actor_id:
                raise ValueError("SELF Prone removal must target the actor")
            if self.target_in_close_range is not None:
                raise ValueError("SELF Prone removal has no ally range fact")
        else:
            if self.target_id == self.actor_id:
                raise ValueError("ALLY Prone removal must target another entity")
            if target.side_id != actor.side_id:
                raise ValueError("Prone removal target must be an ally")
            if self.target_in_close_range is not True:
                raise ValueError("Prone removal ally must be in Close Range")
        _validate_bool(
            self.actor_has_enemy_in_close_range,
            "actor_has_enemy_in_close_range",
        )
        if self.actor_has_enemy_in_close_range:
            raise ValueError("an enemy in Close Range prevents Prone removal")

        if not self.previous_target_conditions.has(Condition.PRONE):
            raise ValueError("Prone removal requires a Prone target")
        expected_conditions = (
            self.previous_target_conditions.without_condition(
                Condition.PRONE
            )
        )
        if self.target_conditions != expected_conditions:
            raise ValueError("Prone removal changed unrelated Conditions")
        if self.actor_id in self.previous_state.free_move_used_entity_ids:
            raise ValueError("free move was already used before Prone removal")
        expected_state = SpatialBattleState(
            graph=self.previous_state.graph,
            placements=self.previous_state.placements,
            round_number=self.previous_state.round_number,
            gave_ground_entity_ids=(
                self.previous_state.gave_ground_entity_ids
            ),
            free_move_used_entity_ids=(
                *self.previous_state.free_move_used_entity_ids,
                self.actor_id,
            ),
        )
        if self.state != expected_state:
            raise ValueError("Prone removal changed unrelated spatial state")

        rule_ids = tuple(self.applied_rule_ids)
        if not rule_ids:
            raise ValueError("applied_rule_ids must not be empty")
        for rule_id in rule_ids:
            _validate_non_empty_string(rule_id, "applied Rule ID")
        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError("applied_rule_ids must be unique")
        if self.rule_id not in rule_ids:
            raise ValueError("Prone removal source rule is missing from trace")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


@dataclass(frozen=True, slots=True)
class RunActionExecutionRequest:
    id: str
    round_state: CombatRoundState
    spatial_state: SpatialBattleState
    actor_id: str
    slot_index: int
    speed: MovementSpeed
    actor_conditions: ConditionState
    destination_zone_id: str
    path_entity_ids: tuple[str, ...] = ()
    crosses_obstacle: bool = False
    crosses_difficult_terrain: bool = False

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Run execution request id")
        if not isinstance(self.round_state, CombatRoundState):
            raise TypeError("round_state must be a CombatRoundState")
        if not isinstance(self.spatial_state, SpatialBattleState):
            raise TypeError("spatial_state must be a SpatialBattleState")
        _validate_non_empty_string(self.actor_id, "actor_id")
        _validate_slot_index(self.slot_index)
        if not isinstance(self.speed, MovementSpeed):
            raise TypeError("speed must be a MovementSpeed")
        if not isinstance(self.actor_conditions, ConditionState):
            raise TypeError("actor_conditions must be a ConditionState")
        _validate_non_empty_string(
            self.destination_zone_id,
            "destination_zone_id",
        )
        if self.round_state.round_number != self.spatial_state.round_number:
            raise ValueError("turn and spatial state must use the same round")
        active_turn = self.round_state.active_turn
        if active_turn is None:
            raise ValueError("Run execution requires an active turn")
        if active_turn.actor_id != self.actor_id:
            raise ValueError("Run execution belongs to another turn actor")
        self.spatial_state.placement_for(self.actor_id)

        path_entity_ids = tuple(self.path_entity_ids)
        for entity_id in path_entity_ids:
            _validate_non_empty_string(entity_id, "path entity_id")
            self.spatial_state.placement_for(entity_id)
        if len(set(path_entity_ids)) != len(path_entity_ids):
            raise ValueError("Run path entity IDs must be unique")
        if self.actor_id in path_entity_ids:
            raise ValueError("Run path cannot cross the actor")
        object.__setattr__(self, "path_entity_ids", path_entity_ids)
        _validate_bool(self.crosses_obstacle, "crosses_obstacle")
        _validate_bool(
            self.crosses_difficult_terrain,
            "crosses_difficult_terrain",
        )


@dataclass(frozen=True, slots=True)
class RunActionExecutionResult:
    request_id: str
    actor_id: str
    slot_index: int
    speed: MovementSpeed
    origin_zone_id: str
    destination_zone_id: str
    previous_round_state: CombatRoundState
    round_state: CombatRoundState
    previous_spatial_state: SpatialBattleState
    spatial_state: SpatialBattleState
    slot: CombatActionSlot
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Run execution request_id")
        _validate_non_empty_string(self.actor_id, "actor_id")
        _validate_slot_index(self.slot_index)
        if not isinstance(self.speed, MovementSpeed):
            raise TypeError("speed must be a MovementSpeed")
        if self.speed is MovementSpeed.SLOW:
            raise ValueError("a successful Run result cannot use Slow Speed")
        _validate_non_empty_string(self.origin_zone_id, "origin_zone_id")
        _validate_non_empty_string(
            self.destination_zone_id,
            "destination_zone_id",
        )
        if not isinstance(self.previous_round_state, CombatRoundState):
            raise TypeError("previous_round_state must be a CombatRoundState")
        if not isinstance(self.round_state, CombatRoundState):
            raise TypeError("round_state must be a CombatRoundState")
        if not isinstance(self.previous_spatial_state, SpatialBattleState):
            raise TypeError(
                "previous_spatial_state must be a SpatialBattleState"
            )
        if not isinstance(self.spatial_state, SpatialBattleState):
            raise TypeError("spatial_state must be a SpatialBattleState")
        if not isinstance(self.slot, CombatActionSlot):
            raise TypeError("slot must be a CombatActionSlot")

        round_number = self.previous_round_state.round_number
        if (
            self.round_state.round_number != round_number
            or self.previous_spatial_state.round_number != round_number
            or self.spatial_state.round_number != round_number
        ):
            raise ValueError("Run result must remain in one combat round")
        previous_turn = self.previous_round_state.active_turn
        current_turn = self.round_state.active_turn
        if previous_turn is None or current_turn is None:
            raise ValueError("Run result requires an active turn")
        if (
            previous_turn.actor_id != self.actor_id
            or current_turn.actor_id != self.actor_id
        ):
            raise ValueError("Run actor must own both turn states")
        if self.slot_index > len(previous_turn.action_slots):
            raise ValueError("previous state does not contain the Run slot")
        previous_slot = previous_turn.action_slots[self.slot_index - 1]
        if any(
            not item.executed
            for item in previous_turn.action_slots[: self.slot_index - 1]
        ):
            raise ValueError("Run result requires executed earlier slots")
        if (
            previous_slot.declaration.kind is not CombatActionKind.MANOEUVRE
            or previous_slot.declaration.manoeuvre is not ManoeuvreKind.RUN
        ):
            raise ValueError("Run result requires a reserved Run slot")
        if previous_slot.executed:
            raise ValueError("previous Run slot must be unexecuted")
        if not self.slot.executed:
            raise ValueError("result Run slot must be executed")
        receipt = self.slot.execution
        assert isinstance(receipt, ActionExecutionReceipt)
        if (
            receipt.id != self.request_id
            or receipt.source_request_id != self.request_id
            or receipt.result_request_id != self.request_id
        ):
            raise ValueError("Run execution receipt does not match request")

        rule_ids = tuple(self.applied_rule_ids)
        if not rule_ids:
            raise ValueError("applied_rule_ids must not be empty")
        for rule_id in rule_ids:
            _validate_non_empty_string(rule_id, "applied Rule ID")
        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError("applied_rule_ids must be unique")
        if receipt.executor_rule_id not in rule_ids:
            raise ValueError("Run executor Rule ID is missing from trace")
        object.__setattr__(self, "applied_rule_ids", rule_ids)

        if self.slot != current_turn.action_slots[self.slot_index - 1]:
            raise ValueError("result Run slot is absent from current turn")
        if self.slot != replace(previous_slot, execution=receipt):
            raise ValueError("Run execution may only add its receipt")
        expected_slots = tuple(
            self.slot if item.index == self.slot_index else item
            for item in previous_turn.action_slots
        )
        if current_turn != replace(previous_turn, action_slots=expected_slots):
            raise ValueError("Run execution changed unrelated turn state")
        if self.round_state != replace(
            self.previous_round_state,
            active_turn=current_turn,
        ):
            raise ValueError("Run execution changed unrelated round state")

        previous_actor = self.previous_spatial_state.placement_for(
            self.actor_id
        )
        if previous_actor.zone_id != self.origin_zone_id:
            raise ValueError("previous spatial state does not match Run origin")
        if not self.previous_spatial_state.graph.are_adjacent(
            self.origin_zone_id,
            self.destination_zone_id,
        ):
            raise ValueError("Run must cross exactly one Zone boundary")
        expected_placements = tuple(
            SpatialEntityPlacement(
                entity_id=placement.entity_id,
                side_id=placement.side_id,
                zone_id=self.destination_zone_id,
            )
            if placement.entity_id == self.actor_id
            else placement
            for placement in self.previous_spatial_state.placements
        )
        expected_spatial_state = replace(
            self.previous_spatial_state,
            placements=expected_placements,
        )
        if self.spatial_state != expected_spatial_state:
            raise ValueError("Run changed unrelated spatial state")


@dataclass(frozen=True, slots=True)
class RunAthleticsExtensionRequest:
    id: str
    base_run: RunActionExecutionResult
    athletics_test: TestRequest
    actor_conditions: ConditionState
    destination_zone_id: str
    path_entity_ids: tuple[str, ...] = ()
    crosses_obstacle: bool = False
    crosses_difficult_terrain: bool = False
    tested_difficult_terrain_this_turn: bool = False
    skill: Skill = Skill.ATHLETICS
    rule_id: str = "RULE-COMBAT-014:run-athletics-extension"

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Run Athletics request id")
        if not isinstance(self.base_run, RunActionExecutionResult):
            raise TypeError("base_run must be a RunActionExecutionResult")
        if not isinstance(self.athletics_test, TestRequest):
            raise TypeError("athletics_test must be a TestRequest")
        if not isinstance(self.actor_conditions, ConditionState):
            raise TypeError("actor_conditions must be a ConditionState")
        _validate_non_empty_string(
            self.destination_zone_id,
            "destination_zone_id",
        )
        if not isinstance(self.skill, Skill):
            raise TypeError("skill must be a Skill")
        if self.skill is not Skill.ATHLETICS:
            raise ValueError("Run extension must use Athletics")
        _validate_bool(self.crosses_obstacle, "crosses_obstacle")
        _validate_bool(
            self.crosses_difficult_terrain,
            "crosses_difficult_terrain",
        )
        _validate_bool(
            self.tested_difficult_terrain_this_turn,
            "tested_difficult_terrain_this_turn",
        )
        _validate_non_empty_string(self.rule_id, "rule_id")

        spatial_state = self.base_run.spatial_state
        spatial_state.placement_for(self.base_run.actor_id)
        path_entity_ids = tuple(self.path_entity_ids)
        for entity_id in path_entity_ids:
            _validate_non_empty_string(entity_id, "path entity_id")
            spatial_state.placement_for(entity_id)
        if len(set(path_entity_ids)) != len(path_entity_ids):
            raise ValueError("Run extension path entity IDs must be unique")
        if self.base_run.actor_id in path_entity_ids:
            raise ValueError("Run extension path cannot cross the actor")
        object.__setattr__(self, "path_entity_ids", path_entity_ids)


@dataclass(frozen=True, slots=True)
class RunAthleticsExtensionResult:
    request_id: str
    rule_id: str
    actor_id: str
    skill: Skill
    base_run: RunActionExecutionResult
    athletics_test_request: TestRequest
    athletics_test_result: TestResult
    outcome: RunAthleticsOutcome
    destination_zone_id: str
    previous_conditions: ConditionState
    conditions: ConditionState
    stagger_application: ConditionApplicationResult | None
    previous_spatial_state: SpatialBattleState
    spatial_state: SpatialBattleState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Run Athletics request_id",
        )
        _validate_non_empty_string(self.rule_id, "rule_id")
        _validate_non_empty_string(self.actor_id, "actor_id")
        if not isinstance(self.skill, Skill):
            raise TypeError("skill must be a Skill")
        if self.skill is not Skill.ATHLETICS:
            raise ValueError("Run extension result must use Athletics")
        if not isinstance(self.base_run, RunActionExecutionResult):
            raise TypeError("base_run must be a RunActionExecutionResult")
        if self.base_run.actor_id != self.actor_id:
            raise ValueError("Run extension belongs to another actor")
        if not isinstance(self.athletics_test_request, TestRequest):
            raise TypeError("athletics_test_request must be a TestRequest")
        if not isinstance(self.athletics_test_result, TestResult):
            raise TypeError("athletics_test_result must be a TestResult")
        if (
            self.athletics_test_result.trace.request_id
            != self.athletics_test_request.id
        ):
            raise ValueError("Athletics result belongs to another Test")
        if not isinstance(self.outcome, RunAthleticsOutcome):
            raise TypeError("outcome must be a RunAthleticsOutcome")
        _validate_non_empty_string(
            self.destination_zone_id,
            "destination_zone_id",
        )
        if not isinstance(self.previous_conditions, ConditionState):
            raise TypeError("previous_conditions must be a ConditionState")
        if not isinstance(self.conditions, ConditionState):
            raise TypeError("conditions must be a ConditionState")
        if not isinstance(self.previous_spatial_state, SpatialBattleState):
            raise TypeError(
                "previous_spatial_state must be a SpatialBattleState"
            )
        if not isinstance(self.spatial_state, SpatialBattleState):
            raise TypeError("spatial_state must be a SpatialBattleState")
        if self.previous_spatial_state != self.base_run.spatial_state:
            raise ValueError("Run extension must start after the base Run")

        previous_actor = self.previous_spatial_state.placement_for(
            self.actor_id
        )
        if not self.previous_spatial_state.graph.are_adjacent(
            previous_actor.zone_id,
            self.destination_zone_id,
        ):
            raise ValueError("Run extension must target one adjacent Zone")

        succeeded = self.athletics_test_result.succeeded
        if succeeded:
            if self.outcome is not RunAthleticsOutcome.MOVED_EXTRA_ZONE:
                raise ValueError("successful Athletics must move an extra Zone")
            if self.stagger_application is not None:
                raise ValueError("successful Athletics cannot apply Staggered")
            if self.conditions != self.previous_conditions:
                raise ValueError("successful Run extension changed Conditions")
            expected_placements = tuple(
                SpatialEntityPlacement(
                    entity_id=placement.entity_id,
                    side_id=placement.side_id,
                    zone_id=self.destination_zone_id,
                )
                if placement.entity_id == self.actor_id
                else placement
                for placement in self.previous_spatial_state.placements
            )
            expected_spatial_state = replace(
                self.previous_spatial_state,
                placements=expected_placements,
            )
            if self.spatial_state != expected_spatial_state:
                raise ValueError("successful Run extension changed other state")
        else:
            if self.spatial_state != self.previous_spatial_state:
                raise ValueError("failed Run extension cannot move the actor")
            application = self.stagger_application
            if not isinstance(application, ConditionApplicationResult):
                raise TypeError(
                    "failed Run extension requires a Staggered application"
                )
            if application.condition is not Condition.STAGGERED:
                raise ValueError("failed Run must apply only Staggered")
            if application.request_id != f"{self.request_id}:staggered":
                raise ValueError("Staggered application belongs to another Run")
            if application.source_rule_id != self.rule_id:
                raise ValueError("Staggered application has another source")
            if application.blocked or application.blocked_by_rule_id is not None:
                raise ValueError("Run failure Staggered cannot be blocked")
            if application.state != self.conditions:
                raise ValueError("conditions must match Staggered application")
            was_staggered = self.previous_conditions.has(Condition.STAGGERED)
            expected_outcome = (
                RunAthleticsOutcome.FAILED_ALREADY_STAGGERED
                if was_staggered
                else RunAthleticsOutcome.FAILED_STAGGERED
            )
            if self.outcome is not expected_outcome:
                raise ValueError("failed Run Athletics outcome is inconsistent")
            if application.was_already_present is not was_staggered:
                raise ValueError("Staggered application has inconsistent state")
            expected_conditions = self.previous_conditions.with_condition(
                Condition.STAGGERED
            )
            if self.conditions != expected_conditions:
                raise ValueError("failed Run changed unrelated Conditions")

        rule_ids = tuple(self.applied_rule_ids)
        if not rule_ids:
            raise ValueError("applied_rule_ids must not be empty")
        for rule_id in rule_ids:
            _validate_non_empty_string(rule_id, "applied Rule ID")
        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError("applied_rule_ids must be unique")
        if self.rule_id not in rule_ids:
            raise ValueError("Run Athletics Rule ID is missing from trace")
        if not set(self.athletics_test_result.trace.applied_rule_ids) <= set(
            rule_ids
        ):
            raise ValueError("Athletics modifier Rule ID is missing from trace")
        if self.stagger_application is not None and not set(
            self.stagger_application.applied_rule_ids
        ) <= set(rule_ids):
            raise ValueError("Staggered Rule ID is missing from trace")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")


def _validate_slot_index(value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("slot_index must be an integer")
    if value not in (1, 2):
        raise ValueError("slot_index must be 1 or 2")
