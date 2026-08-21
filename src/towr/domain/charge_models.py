from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from towr.domain.condition_models import (
    Condition,
    ConditionApplicationResult,
    ConditionState,
)
from towr.domain.movement_models import MovementSpeed
from towr.domain.resolution_models import KernelAttackRequest, ResolutionResult
from towr.domain.spatial_models import (
    SpatialBattleState,
    SpatialEntityPlacement,
)
from towr.domain.test_models import (
    DiceModifier,
    Skill,
    TestRequest,
    TestResult,
)
from towr.domain.turn_models import (
    ActionExecutionReceipt,
    CombatActionKind,
    CombatActionSlot,
    CombatRoundState,
    ManoeuvreKind,
)


_ATTACK_SKILLS = (
    Skill.MELEE,
    Skill.SHOOTING,
    Skill.THROWING,
    Skill.BRAWN,
)


class LongChargeOutcome(str, Enum):
    REACHED_TARGET_AND_ATTACKED = "reached_target_and_attacked"
    STOPPED_SHORT_STAGGERED = "stopped_short_staggered"
    STOPPED_SHORT_ALREADY_STAGGERED = (
        "stopped_short_already_staggered"
    )


@dataclass(frozen=True, slots=True)
class ChargeActionExecutionRequest:
    id: str
    round_state: CombatRoundState
    spatial_state: SpatialBattleState
    actor_id: str
    target_id: str
    slot_index: int
    speed: MovementSpeed
    actor_conditions: ConditionState
    attack_skill: Skill
    kernel_request: KernelAttackRequest
    actor_began_turn_in_enemy_close_range: bool
    reaches_target_close_range: bool
    path_entity_ids: tuple[str, ...] = ()
    crosses_obstacle: bool = False
    crosses_difficult_terrain: bool = False
    rule_id: str = "RULE-COMBAT-014:charge-action-execution"
    melee_bonus_rule_id: str = "RULE-COMBAT-009:charge-melee-bonus"

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Charge execution request id")
        if not isinstance(self.round_state, CombatRoundState):
            raise TypeError("round_state must be a CombatRoundState")
        if not isinstance(self.spatial_state, SpatialBattleState):
            raise TypeError("spatial_state must be a SpatialBattleState")
        _validate_non_empty_string(self.actor_id, "actor_id")
        _validate_non_empty_string(self.target_id, "target_id")
        if self.actor_id == self.target_id:
            raise ValueError("Charge cannot target the actor")
        _validate_slot_index(self.slot_index)
        if not isinstance(self.speed, MovementSpeed):
            raise TypeError("speed must be a MovementSpeed")
        if not isinstance(self.actor_conditions, ConditionState):
            raise TypeError("actor_conditions must be a ConditionState")
        if not isinstance(self.attack_skill, Skill):
            raise TypeError("attack_skill must be a Skill")
        if self.attack_skill not in _ATTACK_SKILLS:
            raise ValueError("Charge requires an Attack Skill")
        if not isinstance(self.kernel_request, KernelAttackRequest):
            raise TypeError("kernel_request must be a KernelAttackRequest")
        _validate_bool(
            self.actor_began_turn_in_enemy_close_range,
            "actor_began_turn_in_enemy_close_range",
        )
        _validate_bool(
            self.reaches_target_close_range,
            "reaches_target_close_range",
        )
        _validate_bool(self.crosses_obstacle, "crosses_obstacle")
        _validate_bool(
            self.crosses_difficult_terrain,
            "crosses_difficult_terrain",
        )
        _validate_non_empty_string(self.rule_id, "rule_id")
        _validate_non_empty_string(
            self.melee_bonus_rule_id,
            "melee_bonus_rule_id",
        )

        if self.round_state.round_number != self.spatial_state.round_number:
            raise ValueError("turn and spatial state must use the same round")
        active_turn = self.round_state.active_turn
        if active_turn is None:
            raise ValueError("Charge execution requires an active turn")
        if active_turn.actor_id != self.actor_id:
            raise ValueError("Charge execution belongs to another turn actor")
        actor = self.spatial_state.placement_for(self.actor_id)
        target = self.spatial_state.placement_for(self.target_id)
        if target.side_id == actor.side_id:
            raise ValueError("Charge target must be an enemy")

        path_entity_ids = tuple(self.path_entity_ids)
        for entity_id in path_entity_ids:
            _validate_non_empty_string(entity_id, "path entity_id")
            self.spatial_state.placement_for(entity_id)
        if len(set(path_entity_ids)) != len(path_entity_ids):
            raise ValueError("Charge path entity IDs must be unique")
        if self.actor_id in path_entity_ids:
            raise ValueError("Charge path cannot cross the actor")
        if self.target_id in path_entity_ids:
            raise ValueError("Charge target is a destination, not a path entity")
        object.__setattr__(self, "path_entity_ids", path_entity_ids)


@dataclass(frozen=True, slots=True)
class ChargeActionExecutionResult:
    request_id: str
    rule_id: str
    actor_id: str
    target_id: str
    slot_index: int
    speed: MovementSpeed
    attack_skill: Skill
    origin_zone_id: str
    destination_zone_id: str
    target_in_close_range: bool
    previous_round_state: CombatRoundState
    round_state: CombatRoundState
    previous_spatial_state: SpatialBattleState
    spatial_state: SpatialBattleState
    slot: CombatActionSlot
    source_kernel_request: KernelAttackRequest
    kernel_request: KernelAttackRequest
    resolution: ResolutionResult
    melee_bonus: DiceModifier | None
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Charge request_id")
        _validate_non_empty_string(self.rule_id, "rule_id")
        _validate_non_empty_string(self.actor_id, "actor_id")
        _validate_non_empty_string(self.target_id, "target_id")
        _validate_slot_index(self.slot_index)
        if not isinstance(self.speed, MovementSpeed):
            raise TypeError("speed must be a MovementSpeed")
        if self.speed is MovementSpeed.SLOW:
            raise ValueError("a successful Charge cannot use Slow Speed")
        if not isinstance(self.attack_skill, Skill):
            raise TypeError("attack_skill must be a Skill")
        if self.attack_skill not in _ATTACK_SKILLS:
            raise ValueError("Charge result requires an Attack Skill")
        _validate_non_empty_string(self.origin_zone_id, "origin_zone_id")
        _validate_non_empty_string(
            self.destination_zone_id,
            "destination_zone_id",
        )
        if self.target_in_close_range is not True:
            raise ValueError("Charge must finish in Close Range of its target")
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
        if not isinstance(self.source_kernel_request, KernelAttackRequest):
            raise TypeError("source_kernel_request must be a KernelAttackRequest")
        if not isinstance(self.kernel_request, KernelAttackRequest):
            raise TypeError("kernel_request must be a KernelAttackRequest")
        if not isinstance(self.resolution, ResolutionResult):
            raise TypeError("resolution must be a ResolutionResult")

        self._validate_round_transition()
        self._validate_spatial_transition()
        self._validate_attack_transition()
        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        receipt = self.slot.execution
        assert isinstance(receipt, ActionExecutionReceipt)
        if receipt.executor_rule_id not in rule_ids:
            raise ValueError("Charge executor Rule ID is missing from trace")
        if self.rule_id not in rule_ids:
            raise ValueError("Charge source Rule ID is missing from trace")
        if self.melee_bonus is not None:
            if self.melee_bonus.rule_id not in rule_ids:
                raise ValueError("Charge bonus Rule ID is missing from trace")
        object.__setattr__(self, "applied_rule_ids", rule_ids)

    def _validate_round_transition(self) -> None:
        round_number = self.previous_round_state.round_number
        if (
            self.round_state.round_number != round_number
            or self.previous_spatial_state.round_number != round_number
            or self.spatial_state.round_number != round_number
        ):
            raise ValueError("Charge result must remain in one round")
        previous_turn = self.previous_round_state.active_turn
        current_turn = self.round_state.active_turn
        if previous_turn is None or current_turn is None:
            raise ValueError("Charge result requires an active turn")
        if (
            previous_turn.actor_id != self.actor_id
            or current_turn.actor_id != self.actor_id
        ):
            raise ValueError("Charge actor must own both turn states")
        if self.slot_index > len(previous_turn.action_slots):
            raise ValueError("previous state does not contain the Charge slot")
        if any(
            not item.executed
            for item in previous_turn.action_slots[: self.slot_index - 1]
        ):
            raise ValueError("Charge result requires executed earlier slots")
        previous_slot = previous_turn.action_slots[self.slot_index - 1]
        if (
            previous_slot.declaration.kind is not CombatActionKind.MANOEUVRE
            or previous_slot.declaration.manoeuvre is not ManoeuvreKind.CHARGE
        ):
            raise ValueError("Charge result requires a reserved Charge slot")
        if previous_slot.executed:
            raise ValueError("previous Charge slot must be unexecuted")
        if not self.slot.executed:
            raise ValueError("result Charge slot must be executed")
        receipt = self.slot.execution
        assert isinstance(receipt, ActionExecutionReceipt)
        if receipt.id != self.request_id:
            raise ValueError("Charge receipt does not match request")
        if receipt.source_request_id != self.request_id:
            raise ValueError("Charge receipt does not match source request")
        if receipt.result_request_id != self.resolution.request_id:
            raise ValueError("Charge receipt does not match attack result")
        if self.slot != replace(previous_slot, execution=receipt):
            raise ValueError("Charge execution may only add its receipt")
        expected_slots = tuple(
            self.slot if item.index == self.slot_index else item
            for item in previous_turn.action_slots
        )
        if current_turn != replace(previous_turn, action_slots=expected_slots):
            raise ValueError("Charge changed unrelated turn state")
        if self.round_state != replace(
            self.previous_round_state,
            active_turn=current_turn,
        ):
            raise ValueError("Charge changed unrelated round state")

    def _validate_spatial_transition(self) -> None:
        previous_actor = self.previous_spatial_state.placement_for(
            self.actor_id
        )
        target = self.previous_spatial_state.placement_for(self.target_id)
        if target.side_id == previous_actor.side_id:
            raise ValueError("Charge target must be an enemy")
        if previous_actor.zone_id != self.origin_zone_id:
            raise ValueError("previous state does not match Charge origin")
        if target.zone_id != self.destination_zone_id:
            raise ValueError("Charge must enter its target's Zone")
        if not self.previous_spatial_state.graph.are_adjacent(
            self.origin_zone_id,
            self.destination_zone_id,
        ):
            raise ValueError("base Charge target must be at Medium Range")
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
            raise ValueError("Charge changed unrelated spatial state")

    def _validate_attack_transition(self) -> None:
        if self.resolution.request_id != self.kernel_request.id:
            raise ValueError("Charge resolution belongs to another attack")
        if self.resolution.attack.request_id != self.kernel_request.attack.id:
            raise ValueError("Charge resolution contains another Attack Test")
        if (
            self.resolution.attack.attacker_test.trace.request_id
            != self.kernel_request.attack.attacker_test.id
        ):
            raise ValueError("Charge resolution contains another attacker Test")
        if not self.kernel_request.attack.is_close_range:
            raise ValueError("Charge attack must resolve at Close Range")
        source_test = self.source_kernel_request.attack.attacker_test
        if self.attack_skill is Skill.MELEE:
            if not isinstance(self.melee_bonus, DiceModifier):
                raise TypeError("Melee Charge requires a DiceModifier")
            if self.melee_bonus.amount != 1:
                raise ValueError("Melee Charge bonus must be +1d")
            expected_test = replace(
                source_test,
                dice_modifiers=(
                    *source_test.dice_modifiers,
                    self.melee_bonus,
                ),
            )
            expected_kernel = replace(
                self.source_kernel_request,
                attack=replace(
                    self.source_kernel_request.attack,
                    attacker_test=expected_test,
                ),
            )
            if self.kernel_request != expected_kernel:
                raise ValueError("Melee Charge prepared the wrong attack")
        else:
            if self.melee_bonus is not None:
                raise ValueError("only Melee Charge receives +1d")
            if self.kernel_request != self.source_kernel_request:
                raise ValueError("non-Melee Charge changed its attack")


@dataclass(frozen=True, slots=True)
class LongChargeActionExecutionRequest:
    id: str
    round_state: CombatRoundState
    spatial_state: SpatialBattleState
    actor_id: str
    target_id: str
    slot_index: int
    speed: MovementSpeed
    actor_conditions: ConditionState
    attack_skill: Skill
    athletics_test: TestRequest
    kernel_request: KernelAttackRequest
    intermediate_zone_id: str
    actor_began_turn_in_enemy_close_range: bool
    reaches_target_close_range: bool
    path_entity_ids: tuple[str, ...] = ()
    crosses_obstacle: bool = False
    crosses_difficult_terrain: bool = False
    skill: Skill = Skill.ATHLETICS
    rule_id: str = "RULE-COMBAT-014:long-charge-action-execution"
    melee_bonus_rule_id: str = "RULE-COMBAT-009:charge-melee-bonus"

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Long Charge request id")
        if not isinstance(self.round_state, CombatRoundState):
            raise TypeError("round_state must be a CombatRoundState")
        if not isinstance(self.spatial_state, SpatialBattleState):
            raise TypeError("spatial_state must be a SpatialBattleState")
        _validate_non_empty_string(self.actor_id, "actor_id")
        _validate_non_empty_string(self.target_id, "target_id")
        if self.actor_id == self.target_id:
            raise ValueError("Long Charge cannot target the actor")
        _validate_slot_index(self.slot_index)
        if not isinstance(self.speed, MovementSpeed):
            raise TypeError("speed must be a MovementSpeed")
        if not isinstance(self.actor_conditions, ConditionState):
            raise TypeError("actor_conditions must be a ConditionState")
        if not isinstance(self.attack_skill, Skill):
            raise TypeError("attack_skill must be a Skill")
        if self.attack_skill not in _ATTACK_SKILLS:
            raise ValueError("Long Charge requires an Attack Skill")
        if not isinstance(self.athletics_test, TestRequest):
            raise TypeError("athletics_test must be a TestRequest")
        if not isinstance(self.kernel_request, KernelAttackRequest):
            raise TypeError("kernel_request must be a KernelAttackRequest")
        _validate_non_empty_string(
            self.intermediate_zone_id,
            "intermediate_zone_id",
        )
        if not self.spatial_state.graph.contains(self.intermediate_zone_id):
            raise ValueError("Long Charge intermediate Zone is unknown")
        if not isinstance(self.skill, Skill):
            raise TypeError("skill must be a Skill")
        if self.skill is not Skill.ATHLETICS:
            raise ValueError("Long Charge Test must use Athletics")
        _validate_bool(
            self.actor_began_turn_in_enemy_close_range,
            "actor_began_turn_in_enemy_close_range",
        )
        _validate_bool(
            self.reaches_target_close_range,
            "reaches_target_close_range",
        )
        _validate_bool(self.crosses_obstacle, "crosses_obstacle")
        _validate_bool(
            self.crosses_difficult_terrain,
            "crosses_difficult_terrain",
        )
        _validate_non_empty_string(self.rule_id, "rule_id")
        _validate_non_empty_string(
            self.melee_bonus_rule_id,
            "melee_bonus_rule_id",
        )

        if self.round_state.round_number != self.spatial_state.round_number:
            raise ValueError("turn and spatial state must use the same round")
        active_turn = self.round_state.active_turn
        if active_turn is None:
            raise ValueError("Long Charge requires an active turn")
        if active_turn.actor_id != self.actor_id:
            raise ValueError("Long Charge belongs to another turn actor")
        actor = self.spatial_state.placement_for(self.actor_id)
        target = self.spatial_state.placement_for(self.target_id)
        if target.side_id == actor.side_id:
            raise ValueError("Long Charge target must be an enemy")

        path_entity_ids = tuple(self.path_entity_ids)
        for entity_id in path_entity_ids:
            _validate_non_empty_string(entity_id, "path entity_id")
            self.spatial_state.placement_for(entity_id)
        if len(set(path_entity_ids)) != len(path_entity_ids):
            raise ValueError("Long Charge path entity IDs must be unique")
        if self.actor_id in path_entity_ids:
            raise ValueError("Long Charge path cannot cross the actor")
        if self.target_id in path_entity_ids:
            raise ValueError(
                "Long Charge target is a destination, not a path entity"
            )
        object.__setattr__(self, "path_entity_ids", path_entity_ids)


@dataclass(frozen=True, slots=True)
class LongChargeActionExecutionResult:
    request_id: str
    rule_id: str
    actor_id: str
    target_id: str
    slot_index: int
    speed: MovementSpeed
    athletics_skill: Skill
    attack_skill: Skill
    athletics_test_request: TestRequest
    athletics_test_result: TestResult
    outcome: LongChargeOutcome
    origin_zone_id: str
    intermediate_zone_id: str
    target_zone_id: str
    target_in_close_range: bool
    previous_conditions: ConditionState
    conditions: ConditionState
    stagger_application: ConditionApplicationResult | None
    previous_round_state: CombatRoundState
    round_state: CombatRoundState
    previous_spatial_state: SpatialBattleState
    spatial_state: SpatialBattleState
    slot: CombatActionSlot
    source_kernel_request: KernelAttackRequest
    kernel_request: KernelAttackRequest
    resolution: ResolutionResult | None
    melee_bonus: DiceModifier | None
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Long Charge request_id")
        _validate_non_empty_string(self.rule_id, "rule_id")
        _validate_non_empty_string(self.actor_id, "actor_id")
        _validate_non_empty_string(self.target_id, "target_id")
        _validate_slot_index(self.slot_index)
        if not isinstance(self.speed, MovementSpeed):
            raise TypeError("speed must be a MovementSpeed")
        if self.speed is MovementSpeed.SLOW:
            raise ValueError("Long Charge cannot use Slow Speed")
        if self.athletics_skill is not Skill.ATHLETICS:
            raise ValueError("Long Charge result must use Athletics")
        if not isinstance(self.attack_skill, Skill):
            raise TypeError("attack_skill must be a Skill")
        if self.attack_skill not in _ATTACK_SKILLS:
            raise ValueError("Long Charge result requires an Attack Skill")
        if not isinstance(self.athletics_test_request, TestRequest):
            raise TypeError("athletics_test_request must be a TestRequest")
        if not isinstance(self.athletics_test_result, TestResult):
            raise TypeError("athletics_test_result must be a TestResult")
        if (
            self.athletics_test_result.trace.request_id
            != self.athletics_test_request.id
        ):
            raise ValueError("Athletics result belongs to another Test")
        if not isinstance(self.outcome, LongChargeOutcome):
            raise TypeError("outcome must be a LongChargeOutcome")
        for value, name in (
            (self.origin_zone_id, "origin_zone_id"),
            (self.intermediate_zone_id, "intermediate_zone_id"),
            (self.target_zone_id, "target_zone_id"),
        ):
            _validate_non_empty_string(value, name)
        _validate_bool(self.target_in_close_range, "target_in_close_range")
        if not isinstance(self.previous_conditions, ConditionState):
            raise TypeError("previous_conditions must be a ConditionState")
        if not isinstance(self.conditions, ConditionState):
            raise TypeError("conditions must be a ConditionState")
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
        if not isinstance(self.source_kernel_request, KernelAttackRequest):
            raise TypeError("source_kernel_request must be a KernelAttackRequest")
        if not isinstance(self.kernel_request, KernelAttackRequest):
            raise TypeError("kernel_request must be a KernelAttackRequest")
        if self.resolution is not None and not isinstance(
            self.resolution,
            ResolutionResult,
        ):
            raise TypeError("resolution must be a ResolutionResult or None")

        self._validate_round_transition()
        self._validate_spatial_transition()
        self._validate_outcome_transition()
        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        if self.rule_id not in rule_ids:
            raise ValueError("Long Charge Rule ID is missing from trace")
        if not set(self.athletics_test_result.trace.applied_rule_ids) <= set(
            rule_ids
        ):
            raise ValueError("Athletics modifier Rule ID is missing from trace")
        if self.stagger_application is not None and not set(
            self.stagger_application.applied_rule_ids
        ) <= set(rule_ids):
            raise ValueError("Staggered Rule ID is missing from trace")
        if self.melee_bonus is not None and self.melee_bonus.rule_id not in rule_ids:
            raise ValueError("Charge bonus Rule ID is missing from trace")
        object.__setattr__(self, "applied_rule_ids", rule_ids)

    @property
    def succeeded(self) -> bool:
        return self.outcome is LongChargeOutcome.REACHED_TARGET_AND_ATTACKED

    def _validate_round_transition(self) -> None:
        round_number = self.previous_round_state.round_number
        if (
            self.round_state.round_number != round_number
            or self.previous_spatial_state.round_number != round_number
            or self.spatial_state.round_number != round_number
        ):
            raise ValueError("Long Charge result must remain in one round")
        previous_turn = self.previous_round_state.active_turn
        current_turn = self.round_state.active_turn
        if previous_turn is None or current_turn is None:
            raise ValueError("Long Charge result requires an active turn")
        if (
            previous_turn.actor_id != self.actor_id
            or current_turn.actor_id != self.actor_id
        ):
            raise ValueError("Long Charge actor must own both turn states")
        if self.slot_index > len(previous_turn.action_slots):
            raise ValueError("previous state lacks the Long Charge slot")
        if any(
            not item.executed
            for item in previous_turn.action_slots[: self.slot_index - 1]
        ):
            raise ValueError("Long Charge requires executed earlier slots")
        previous_slot = previous_turn.action_slots[self.slot_index - 1]
        if (
            previous_slot.declaration.kind is not CombatActionKind.MANOEUVRE
            or previous_slot.declaration.manoeuvre is not ManoeuvreKind.CHARGE
        ):
            raise ValueError("Long Charge requires a reserved Charge slot")
        if previous_slot.executed:
            raise ValueError("previous Long Charge slot must be unexecuted")
        if not self.slot.executed:
            raise ValueError("result Long Charge slot must be executed")
        receipt = self.slot.execution
        assert isinstance(receipt, ActionExecutionReceipt)
        expected_result_id = (
            self.resolution.request_id
            if self.resolution is not None
            else self.request_id
        )
        if (
            receipt.id != self.request_id
            or receipt.source_request_id != self.request_id
            or receipt.result_request_id != expected_result_id
            or receipt.executor_rule_id != self.rule_id
        ):
            raise ValueError("Long Charge receipt is inconsistent")
        if self.slot != replace(previous_slot, execution=receipt):
            raise ValueError("Long Charge execution may only add its receipt")
        expected_slots = tuple(
            self.slot if item.index == self.slot_index else item
            for item in previous_turn.action_slots
        )
        if current_turn != replace(previous_turn, action_slots=expected_slots):
            raise ValueError("Long Charge changed unrelated turn state")
        if self.round_state != replace(
            self.previous_round_state,
            active_turn=current_turn,
        ):
            raise ValueError("Long Charge changed unrelated round state")

    def _validate_spatial_transition(self) -> None:
        previous_actor = self.previous_spatial_state.placement_for(
            self.actor_id
        )
        target = self.previous_spatial_state.placement_for(self.target_id)
        if target.side_id == previous_actor.side_id:
            raise ValueError("Long Charge target must be an enemy")
        if previous_actor.zone_id != self.origin_zone_id:
            raise ValueError("previous state does not match Long Charge origin")
        if target.zone_id != self.target_zone_id:
            raise ValueError("target Zone changed during Long Charge")
        graph = self.previous_spatial_state.graph
        if graph.are_adjacent(self.origin_zone_id, self.target_zone_id):
            raise ValueError("Long Charge target must not be at Medium Range")
        if not graph.are_adjacent(
            self.origin_zone_id,
            self.intermediate_zone_id,
        ) or not graph.are_adjacent(
            self.intermediate_zone_id,
            self.target_zone_id,
        ):
            raise ValueError("Long Charge route must cross exactly two links")
        final_zone_id = (
            self.target_zone_id if self.succeeded else self.intermediate_zone_id
        )
        expected_placements = tuple(
            SpatialEntityPlacement(
                entity_id=placement.entity_id,
                side_id=placement.side_id,
                zone_id=final_zone_id,
            )
            if placement.entity_id == self.actor_id
            else placement
            for placement in self.previous_spatial_state.placements
        )
        expected_state = replace(
            self.previous_spatial_state,
            placements=expected_placements,
        )
        if self.spatial_state != expected_state:
            raise ValueError("Long Charge changed unrelated spatial state")

    def _validate_outcome_transition(self) -> None:
        if self.athletics_test_result.succeeded != self.succeeded:
            raise ValueError("Long Charge outcome contradicts Athletics")
        if self.succeeded:
            self._validate_success_transition()
        else:
            self._validate_failure_transition()

    def _validate_success_transition(self) -> None:
        if not self.target_in_close_range:
            raise ValueError("successful Long Charge must reach Close Range")
        if self.conditions != self.previous_conditions:
            raise ValueError("successful Long Charge changed Conditions")
        if self.stagger_application is not None:
            raise ValueError("successful Long Charge cannot apply Staggered")
        if not isinstance(self.resolution, ResolutionResult):
            raise TypeError("successful Long Charge requires an attack result")
        if self.resolution.request_id != self.kernel_request.id:
            raise ValueError("Long Charge resolved another kernel request")
        if self.resolution.attack.request_id != self.kernel_request.attack.id:
            raise ValueError("Long Charge resolution contains another attack")
        if (
            self.resolution.attack.attacker_test.trace.request_id
            != self.kernel_request.attack.attacker_test.id
        ):
            raise ValueError("Long Charge resolution contains another Test")
        if not self.kernel_request.attack.is_close_range:
            raise ValueError("Long Charge attack must resolve at Close Range")
        source_test = self.source_kernel_request.attack.attacker_test
        if self.attack_skill is Skill.MELEE:
            if not isinstance(self.melee_bonus, DiceModifier):
                raise TypeError("Melee Long Charge requires a DiceModifier")
            if self.melee_bonus.amount != 1:
                raise ValueError("Melee Long Charge bonus must be +1d")
            expected_test = replace(
                source_test,
                dice_modifiers=(*source_test.dice_modifiers, self.melee_bonus),
            )
            expected_kernel = replace(
                self.source_kernel_request,
                attack=replace(
                    self.source_kernel_request.attack,
                    attacker_test=expected_test,
                ),
            )
            if self.kernel_request != expected_kernel:
                raise ValueError("Melee Long Charge prepared the wrong attack")
        else:
            if self.melee_bonus is not None:
                raise ValueError("only Melee Long Charge receives +1d")
            if self.kernel_request != self.source_kernel_request:
                raise ValueError("non-Melee Long Charge changed its attack")

    def _validate_failure_transition(self) -> None:
        if self.target_in_close_range:
            raise ValueError("failed Long Charge cannot reach Close Range")
        if self.resolution is not None:
            raise ValueError("failed Long Charge cannot resolve an attack")
        if self.melee_bonus is not None:
            raise ValueError("failed Long Charge cannot apply an attack bonus")
        if self.kernel_request != self.source_kernel_request:
            raise ValueError("failed Long Charge cannot prepare an attack")
        application = self.stagger_application
        if not isinstance(application, ConditionApplicationResult):
            raise TypeError("failed Long Charge requires Staggered application")
        if application.condition is not Condition.STAGGERED:
            raise ValueError("failed Long Charge must apply only Staggered")
        if application.request_id != f"{self.request_id}:staggered":
            raise ValueError("Staggered application belongs to another Charge")
        if application.source_rule_id != self.rule_id:
            raise ValueError("Staggered application has another source")
        if application.blocked or application.blocked_by_rule_id is not None:
            raise ValueError("Long Charge Staggered cannot be blocked")
        was_staggered = self.previous_conditions.has(Condition.STAGGERED)
        expected_outcome = (
            LongChargeOutcome.STOPPED_SHORT_ALREADY_STAGGERED
            if was_staggered
            else LongChargeOutcome.STOPPED_SHORT_STAGGERED
        )
        if self.outcome is not expected_outcome:
            raise ValueError("failed Long Charge outcome is inconsistent")
        if application.was_already_present is not was_staggered:
            raise ValueError("Staggered application has inconsistent state")
        expected_conditions = self.previous_conditions.with_condition(
            Condition.STAGGERED
        )
        if application.state != expected_conditions:
            raise ValueError("Staggered application changed unrelated Conditions")
        if self.conditions != expected_conditions:
            raise ValueError("failed Long Charge changed unrelated Conditions")


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


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")
