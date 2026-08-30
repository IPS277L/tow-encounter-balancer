from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.condition_models import (
    Condition,
    ConditionApplicationResult,
    ConditionState,
    EffectApplicationResult,
    RepeatedConditionReplacement,
)
from towr.domain.resolution_models import (
    HazardExposureRequest,
    IdentifiedHazardTarget,
    TargetInjuryPolicy,
    ZoneHazardRequest,
    ZoneHazardResolutionRequest,
    ZoneHazardResolutionResult,
    ZoneHazardTargetResult,
)
from towr.domain.spatial_models import SpatialBattleState
from towr.domain.test_models import Skill
from towr.domain.turn_models import (
    ActionExecutionReceipt,
    CombatActionKind,
    CombatActionSlot,
    CombatRoundState,
    ImproviseKind,
)


SOPORIFIC_BREATH_RULE_ID = "RULE-NPC-018:soporific-breath"
SOPORIFIC_BREATH_ACTION_EXECUTION_RULE_ID = (
    "RULE-NPC-018:soporific-breath-action-execution"
)


@dataclass(frozen=True, slots=True)
class SoporificBreathActionExecutionRequest:
    id: str
    round_state: CombatRoundState
    spatial_state: SpatialBattleState
    actor_id: str
    actor_conditions: ConditionState
    actor_ability_rule_ids: tuple[str, ...]
    slot_index: int
    target_zone_id: str
    target_zone_in_medium_range: bool
    targets: tuple[IdentifiedHazardTarget, ...]
    rule_id: str = SOPORIFIC_BREATH_ACTION_EXECUTION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Soporific Breath request id")
        if not isinstance(self.round_state, CombatRoundState):
            raise TypeError("round_state must be a CombatRoundState")
        if not isinstance(self.spatial_state, SpatialBattleState):
            raise TypeError("spatial_state must be a SpatialBattleState")
        _validate_non_empty_string(self.actor_id, "Soporific Breath actor_id")
        if not isinstance(self.actor_conditions, ConditionState):
            raise TypeError("actor_conditions must be a ConditionState")
        ability_rule_ids = _validate_rule_ids(
            self.actor_ability_rule_ids,
            allow_empty=True,
        )
        _validate_slot_index(self.slot_index)
        _validate_non_empty_string(self.target_zone_id, "target_zone_id")
        _validate_bool(
            self.target_zone_in_medium_range,
            "target_zone_in_medium_range",
        )
        targets = tuple(self.targets)
        if not all(isinstance(item, IdentifiedHazardTarget) for item in targets):
            raise TypeError("targets must contain IdentifiedHazardTarget values")
        _validate_non_empty_string(self.rule_id, "Soporific Breath rule_id")

        turn = self.round_state.active_turn
        if turn is None or turn.actor_id != self.actor_id:
            raise ValueError("Soporific Breath requires the actor's active turn")
        if self.round_state.round_number != self.spatial_state.round_number:
            raise ValueError("turn and spatial snapshots must use one round")
        self.spatial_state.placement_for(self.actor_id)
        if not self.spatial_state.graph.contains(self.target_zone_id):
            raise ValueError("Soporific Breath target references an unknown Zone")
        object.__setattr__(
            self,
            "actor_ability_rule_ids",
            ability_rule_ids,
        )
        object.__setattr__(self, "targets", targets)


@dataclass(frozen=True, slots=True)
class SoporificBreathActionExecutionResult:
    request_id: str
    rule_id: str
    source_request: SoporificBreathActionExecutionRequest
    actor_id: str
    slot_index: int
    target_zone_id: str
    zone_hazard_request: ZoneHazardResolutionRequest
    zone_hazard: ZoneHazardResolutionResult
    previous_round_state: CombatRoundState
    round_state: CombatRoundState
    previous_spatial_state: SpatialBattleState
    spatial_state: SpatialBattleState
    slot: CombatActionSlot
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Soporific Breath request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "Soporific Breath result rule_id",
        )
        if not isinstance(
            self.source_request,
            SoporificBreathActionExecutionRequest,
        ):
            raise TypeError(
                "source_request must be a "
                "SoporificBreathActionExecutionRequest"
            )
        _validate_non_empty_string(self.actor_id, "Soporific Breath actor_id")
        _validate_slot_index(self.slot_index)
        _validate_non_empty_string(self.target_zone_id, "target_zone_id")
        if not isinstance(
            self.zone_hazard_request,
            ZoneHazardResolutionRequest,
        ):
            raise TypeError(
                "zone_hazard_request must be a ZoneHazardResolutionRequest"
            )
        if not isinstance(self.zone_hazard, ZoneHazardResolutionResult):
            raise TypeError("zone_hazard must be a ZoneHazardResolutionResult")
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
            or self.target_zone_id != source.target_zone_id
            or self.previous_round_state != source.round_state
            or self.previous_spatial_state != source.spatial_state
            or self.spatial_state != source.spatial_state
        ):
            raise ValueError("Soporific Breath result has stale provenance")
        _validate_soporific_breath_context(source)
        self._validate_zone_hazard()
        self._validate_round_transition()

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {
            self.rule_id,
            SOPORIFIC_BREATH_RULE_ID,
            *self.zone_hazard.applied_rule_ids,
            *(
                rule_id
                for result in self.zone_hazard.targets
                if result.avoidance_test is not None
                for rule_id in result.avoidance_test.trace.applied_rule_ids
            ),
        }
        if not required <= set(rule_ids):
            raise ValueError("Soporific Breath trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)

    def _validate_zone_hazard(self) -> None:
        source = self.source_request
        expected_source = _soporific_breath_source(source)
        expected_request = ZoneHazardResolutionRequest(
            id=f"{source.id}:zone-resolution",
            source=expected_source,
            targets=source.targets,
        )
        if self.zone_hazard_request != expected_request:
            raise ValueError(
                "Soporific Breath Zone Hazard request is inconsistent"
            )
        if (
            self.zone_hazard.request_id != expected_request.id
            or self.zone_hazard.source_resolution_id
            != expected_source.resolution_id
        ):
            raise ValueError("Soporific Breath Zone Hazard belongs elsewhere")
        results = tuple(self.zone_hazard.targets)
        if len(results) != len(source.targets):
            raise ValueError(
                "Soporific Breath result has an incomplete target batch"
            )
        for target, result in zip(source.targets, results, strict=True):
            _validate_target_result(expected_request, target, result)
        expected_rule_ids = tuple(
            dict.fromkeys(
                rule_id
                for result in results
                for rule_id in (
                    *result.application.applied_rule_ids,
                    *(
                        result.hazard.applied_rule_ids
                        if result.hazard is not None
                        else ()
                    ),
                )
            )
        )
        if self.zone_hazard.applied_rule_ids != expected_rule_ids:
            raise ValueError(
                "Soporific Breath Zone Hazard trace is inconsistent"
            )

    def _validate_round_transition(self) -> None:
        source = self.source_request
        previous_turn = self.previous_round_state.active_turn
        current_turn = self.round_state.active_turn
        if previous_turn is None or current_turn is None:
            raise ValueError("Soporific Breath requires an active turn")
        previous_slot = previous_turn.action_slots[source.slot_index - 1]
        if previous_slot.executed or not self.slot.executed:
            raise ValueError(
                "Soporific Breath must execute one unexecuted slot"
            )
        receipt = self.slot.execution
        assert isinstance(receipt, ActionExecutionReceipt)
        if (
            receipt.id != source.id
            or receipt.executor_rule_id != source.rule_id
            or receipt.source_request_id != source.id
            or receipt.result_request_id != self.zone_hazard.request_id
            or receipt.actor_id != source.actor_id
            or receipt.round_number != source.round_state.round_number
            or receipt.slot_index != source.slot_index
            or receipt.declaration != previous_slot.declaration
        ):
            raise ValueError("Soporific Breath receipt has stale provenance")
        if self.slot != replace(previous_slot, execution=receipt):
            raise ValueError("Soporific Breath may only add its receipt")
        expected_slots = tuple(
            self.slot if item.index == source.slot_index else item
            for item in previous_turn.action_slots
        )
        if current_turn != replace(previous_turn, action_slots=expected_slots):
            raise ValueError("Soporific Breath changed unrelated turn state")
        if self.round_state != replace(
            self.previous_round_state,
            active_turn=current_turn,
        ):
            raise ValueError("Soporific Breath changed unrelated round state")


def _validate_soporific_breath_context(
    request: SoporificBreathActionExecutionRequest,
) -> None:
    if request.rule_id != SOPORIFIC_BREATH_ACTION_EXECUTION_RULE_ID:
        raise ValueError("Soporific Breath request uses an unknown source rule")
    turn = request.round_state.active_turn
    assert turn is not None
    if request.slot_index > len(turn.action_slots):
        raise ValueError("the requested action slot has not been reserved")
    if any(
        not slot.executed
        for slot in turn.action_slots[: request.slot_index - 1]
    ):
        raise ValueError("earlier action slots must be executed first")
    slot = turn.action_slots[request.slot_index - 1]
    declaration = slot.declaration
    if (
        declaration.kind is not CombatActionKind.IMPROVISE
        or declaration.improvise_kind is not ImproviseKind.ABILITY
    ):
        raise ValueError("only an Ability Improvise can use Soporific Breath")
    if declaration.improvise_approach_id != SOPORIFIC_BREATH_RULE_ID:
        raise ValueError("Soporific Breath Ability must match the action slot")
    if declaration.improvise_produces_attack:
        raise ValueError("Soporific Breath is a Hazard action, not an Attack")
    if slot.executed:
        raise ValueError("the Soporific Breath slot has already been executed")
    if SOPORIFIC_BREATH_RULE_ID not in request.actor_ability_rule_ids:
        raise ValueError("the actor does not have the Soporific Breath Ability")
    if request.actor_conditions.has(Condition.DEFENCELESS):
        raise ValueError("Defenceless characters cannot take actions")
    if request.actor_conditions.has(Condition.STAGGERED):
        raise ValueError("Staggered actors cannot use Soporific Breath")
    if not request.target_zone_in_medium_range:
        raise ValueError("Soporific Breath target Zone must be in Medium Range")

    expected_target_ids = tuple(
        placement.entity_id
        for placement in request.spatial_state.placements_in(
            request.target_zone_id
        )
    )
    target_ids = tuple(target.target_id for target in request.targets)
    if target_ids != expected_target_ids:
        raise ValueError(
            "Soporific Breath targets must exactly match the Zone "
            "placement order"
        )
    test_ids = tuple(target.avoidance_test.id for target in request.targets)
    if len(set(test_ids)) != len(test_ids):
        raise ValueError("Soporific Breath Test request IDs must be unique")
    if any(
        target.selected_avoidance_skill is not Skill.ENDURANCE
        for target in request.targets
    ):
        raise ValueError("Soporific Breath requires explicit Endurance Tests")


def _soporific_breath_source(
    request: SoporificBreathActionExecutionRequest,
) -> ZoneHazardRequest:
    return ZoneHazardRequest(
        resolution_id=f"{request.id}:zone-hazard",
        rating=2,
        avoidance_skill=Skill.ENDURANCE,
        rule_id=SOPORIFIC_BREATH_RULE_ID,
        inflicts_wound=True,
        failure_conditions=(Condition.DRAINED,),
        repeated_condition_replacements=(
            RepeatedConditionReplacement(
                condition=Condition.DRAINED,
                replacement=Condition.DEFENCELESS,
                rule_id=SOPORIFIC_BREATH_RULE_ID,
            ),
        ),
    )


def _validate_target_result(
    request: ZoneHazardResolutionRequest,
    target: IdentifiedHazardTarget,
    result: ZoneHazardTargetResult,
) -> None:
    expected_exposure = HazardExposureRequest(
        resolution_id=request.source.resolution_id,
        test_id=target.avoidance_test.id,
        rating=2,
        avoidance_skill=Skill.ENDURANCE,
        rule_id=SOPORIFIC_BREATH_RULE_ID,
        inflicts_wound=True,
        failure_conditions=(Condition.DRAINED,),
        repeated_condition_replacements=(
            RepeatedConditionReplacement(
                condition=Condition.DRAINED,
                replacement=Condition.DEFENCELESS,
                rule_id=SOPORIFIC_BREATH_RULE_ID,
            ),
        ),
    )
    expected_application = EffectApplicationResult(
        request_id=f"{expected_exposure.test_id}:exposure",
        blocked=False,
        source_rule_id=SOPORIFIC_BREATH_RULE_ID,
        blocked_by_rule_id=None,
        applied_rule_ids=(SOPORIFIC_BREATH_RULE_ID,),
    )
    if (
        result.target_id != target.target_id
        or result.exposure != expected_exposure
        or result.application != expected_application
        or result.avoidance_test is None
        or result.hazard is None
    ):
        raise ValueError("Soporific Breath target result is inconsistent")
    hazard = result.hazard
    expected_shortfall = max(0, 2 - result.avoidance_test.successes)
    if (
        result.avoidance_test.trace.request_id != target.avoidance_test.id
        or hazard.request_id != f"{request.id}:{target.target_id}:hazard"
        or hazard.successes != result.avoidance_test.successes
        or hazard.rating != 2
        or hazard.shortfall != expected_shortfall
        or hazard.avoided is not (expected_shortfall == 0)
        or hazard.applied_rule_ids != (SOPORIFIC_BREATH_RULE_ID,)
    ):
        raise ValueError("Soporific Breath Hazard result is inconsistent")
    if hazard.avoided:
        if (
            hazard.state != target.target_state
            or hazard.character_wound is not None
            or hazard.wound_effect is not None
            or hazard.profile_wound is not None
            or hazard.failure_conditions
            or hazard.condition_applications
            or hazard.follow_ups
        ):
            raise ValueError("avoided Soporific Breath changed the target")
        return

    is_character = target.target_policy in {
        TargetInjuryPolicy.PLAYER,
        TargetInjuryPolicy.CHAMPION,
    }
    if (
        is_character
        and (hazard.character_wound is None or hazard.profile_wound is not None)
    ) or (
        not is_character
        and (hazard.profile_wound is None or hazard.character_wound is not None)
    ):
        raise ValueError("Soporific Breath Wound result is inconsistent")
    if hazard.wound_effect is not None and hazard.character_wound is None:
        raise ValueError("Soporific Breath Wound effect is inconsistent")
    if is_character and hazard.pending_character_wound is not None:
        if (
            hazard.pending_character_wound.wound_result
            != hazard.character_wound
            or hazard.deferred_failure_exposure != expected_exposure
            or hazard.wound_effect is not None
            or hazard.failure_conditions
            or hazard.condition_applications
            or hazard.state != hazard.character_wound.state
        ):
            raise ValueError(
                "pending Soporific Breath Wound result is inconsistent"
            )
        return
    post_wound_state = (
        hazard.wound_effect.state
        if hazard.wound_effect is not None
        else (
            hazard.character_wound.state
            if hazard.character_wound is not None
            else hazard.profile_wound.state
        )
    )
    expected_condition = (
        Condition.DEFENCELESS
        if post_wound_state.conditions.has(Condition.DRAINED)
        else Condition.DRAINED
    )
    if (
        hazard.failure_conditions != (expected_condition,)
        or len(hazard.condition_applications) != 1
    ):
        raise ValueError("Soporific Breath Condition result is inconsistent")
    application = hazard.condition_applications[0]
    _validate_condition_application(
        hazard.request_id,
        post_wound_state.conditions,
        expected_condition,
        application,
    )
    if hazard.state != replace(post_wound_state, conditions=application.state):
        raise ValueError("Soporific Breath final state is inconsistent")


def _validate_condition_application(
    hazard_request_id: str,
    previous_state: ConditionState,
    condition: Condition,
    application: ConditionApplicationResult,
) -> None:
    expected_state = previous_state.with_condition(condition)
    if (
        application.request_id
        != f"{hazard_request_id}:failure-condition:0:{condition.value}"
        or application.state != expected_state
        or application.condition is not condition
        or application.was_already_present
        is not previous_state.has(condition)
        or application.blocked
        or application.source_rule_id != SOPORIFIC_BREATH_RULE_ID
        or application.blocked_by_rule_id is not None
        or application.applied_rule_ids != (SOPORIFIC_BREATH_RULE_ID,)
    ):
        raise ValueError(
            "Soporific Breath Condition application is inconsistent"
        )


def _validate_rule_ids(
    values: tuple[str, ...],
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    rule_ids = tuple(values)
    if not allow_empty and not rule_ids:
        raise ValueError("applied_rule_ids must not be empty")
    for rule_id in rule_ids:
        _validate_non_empty_string(rule_id, "Rule ID")
    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError("Rule IDs must be unique")
    return rule_ids


def _validate_slot_index(value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("slot_index must be an integer")
    if value not in (1, 2):
        raise ValueError("slot_index must be 1 or 2")


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
