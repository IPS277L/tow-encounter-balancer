from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.spatial_models import (
    SpatialBattleState,
    SpatialEntityPlacement,
)
from towr.domain.turn_models import CombatRoundState


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


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")
