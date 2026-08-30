from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.condition_models import (
    Condition,
    ConditionState,
    EffectApplicationResult,
)
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.resolution_models import (
    HazardExposureRequest,
    HazardResolutionRequest,
    HazardResolutionResult,
    IdentifiedHazardTarget,
    TargetInjuryState,
)
from towr.domain.test_models import Skill, TestResult
from towr.domain.turn_models import (
    ActionExecutionReceipt,
    CombatActionKind,
    CombatActionSlot,
    CombatRoundState,
    ImproviseKind,
)


TROLL_VOMIT_RULE_ID = "RULE-NPC-019:troll-vomit"
TROLL_VOMIT_ACTION_EXECUTION_RULE_ID = (
    "RULE-NPC-019:troll-vomit-action-execution"
)


@dataclass(frozen=True, slots=True)
class TrollVomitActionExecutionRequest:
    id: str
    round_state: CombatRoundState
    actor_id: str
    actor_conditions: ConditionState
    actor_ability_rule_ids: tuple[str, ...]
    slot_index: int
    target: IdentifiedHazardTarget
    target_in_close_range: bool
    rule_id: str = TROLL_VOMIT_ACTION_EXECUTION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Troll Vomit request id")
        if not isinstance(self.round_state, CombatRoundState):
            raise TypeError("round_state must be a CombatRoundState")
        _validate_non_empty_string(self.actor_id, "Troll Vomit actor_id")
        if not isinstance(self.actor_conditions, ConditionState):
            raise TypeError("actor_conditions must be a ConditionState")
        ability_rule_ids = _validate_rule_ids(
            self.actor_ability_rule_ids,
            allow_empty=True,
        )
        _validate_slot_index(self.slot_index)
        if not isinstance(self.target, IdentifiedHazardTarget):
            raise TypeError("target must be an IdentifiedHazardTarget")
        _validate_bool(
            self.target_in_close_range,
            "target_in_close_range",
        )
        _validate_non_empty_string(self.rule_id, "Troll Vomit rule_id")

        turn = self.round_state.active_turn
        if turn is None or turn.actor_id != self.actor_id:
            raise ValueError("Troll Vomit requires the actor's active turn")
        self.round_state.participant_for(self.target.target_id)
        object.__setattr__(
            self,
            "actor_ability_rule_ids",
            ability_rule_ids,
        )


@dataclass(frozen=True, slots=True)
class TrollVomitActionExecutionResult:
    request_id: str
    rule_id: str
    source_request: TrollVomitActionExecutionRequest
    actor_id: str
    target_id: str
    slot_index: int
    exposure: HazardExposureRequest
    application: EffectApplicationResult
    avoidance_test: TestResult
    hazard_request: HazardResolutionRequest
    hazard: HazardResolutionResult
    previous_target_state: TargetInjuryState
    target_state: TargetInjuryState
    previous_round_state: CombatRoundState
    round_state: CombatRoundState
    slot: CombatActionSlot
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Troll Vomit request_id")
        _validate_non_empty_string(self.rule_id, "Troll Vomit result rule_id")
        if not isinstance(
            self.source_request,
            TrollVomitActionExecutionRequest,
        ):
            raise TypeError(
                "source_request must be a TrollVomitActionExecutionRequest"
            )
        _validate_non_empty_string(self.actor_id, "Troll Vomit actor_id")
        _validate_non_empty_string(self.target_id, "Troll Vomit target_id")
        _validate_slot_index(self.slot_index)
        if not isinstance(self.exposure, HazardExposureRequest):
            raise TypeError("exposure must be a HazardExposureRequest")
        if not isinstance(self.application, EffectApplicationResult):
            raise TypeError("application must be an EffectApplicationResult")
        if not isinstance(self.avoidance_test, TestResult):
            raise TypeError("avoidance_test must be a TestResult")
        if not isinstance(self.hazard_request, HazardResolutionRequest):
            raise TypeError("hazard_request must be a HazardResolutionRequest")
        if not isinstance(self.hazard, HazardResolutionResult):
            raise TypeError("hazard must be a HazardResolutionResult")
        if not isinstance(
            self.previous_target_state,
            (CharacterInjuryState, ProfileInjuryState),
        ):
            raise TypeError("previous_target_state must be an injury state")
        if not isinstance(
            self.target_state,
            (CharacterInjuryState, ProfileInjuryState),
        ):
            raise TypeError("target_state must be an injury state")
        if not isinstance(self.previous_round_state, CombatRoundState):
            raise TypeError("previous_round_state must be a CombatRoundState")
        if not isinstance(self.round_state, CombatRoundState):
            raise TypeError("round_state must be a CombatRoundState")
        if not isinstance(self.slot, CombatActionSlot):
            raise TypeError("slot must be a CombatActionSlot")

        source = self.source_request
        target = source.target
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.actor_id != source.actor_id
            or self.target_id != target.target_id
            or self.slot_index != source.slot_index
            or self.previous_target_state != target.target_state
            or self.previous_round_state != source.round_state
        ):
            raise ValueError("Troll Vomit result has stale provenance")
        _validate_troll_vomit_context(source)
        self._validate_hazard_transition()
        self._validate_round_transition()

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {
            self.rule_id,
            *self.application.applied_rule_ids,
            *self.avoidance_test.trace.applied_rule_ids,
            *self.hazard.applied_rule_ids,
        }
        if not required <= set(rule_ids):
            raise ValueError("Troll Vomit trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)

    def _validate_hazard_transition(self) -> None:
        source = self.source_request
        target = source.target
        expected_exposure = _troll_vomit_exposure(source)
        if self.exposure != expected_exposure:
            raise ValueError("Troll Vomit exposure is inconsistent")
        expected_application = EffectApplicationResult(
            request_id=f"{self.exposure.test_id}:exposure",
            blocked=False,
            source_rule_id=TROLL_VOMIT_RULE_ID,
            blocked_by_rule_id=None,
            applied_rule_ids=(TROLL_VOMIT_RULE_ID,),
        )
        if self.application != expected_application:
            raise ValueError("Troll Vomit immunity preflight is inconsistent")
        if self.avoidance_test.trace.request_id != target.avoidance_test.id:
            raise ValueError("Troll Vomit Endurance result belongs elsewhere")
        expected_hazard_request = HazardResolutionRequest(
            id=f"{source.id}:hazard",
            target_id=target.target_id,
            exposure=self.exposure,
            avoidance_test=self.avoidance_test,
            target_policy=target.target_policy,
            target_state=target.target_state,
            wound_dice_modifiers=target.wound_dice_modifiers,
            wound_negation_options=target.wound_negation_options,
            additional_profile_wounds=target.additional_profile_wounds,
        )
        if self.hazard_request != expected_hazard_request:
            raise ValueError("Troll Vomit Hazard request is inconsistent")
        expected_shortfall = max(0, 3 - self.avoidance_test.successes)
        if (
            self.hazard.request_id != self.hazard_request.id
            or self.hazard.successes != self.avoidance_test.successes
            or self.hazard.rating != 3
            or self.hazard.shortfall != expected_shortfall
            or self.hazard.avoided is not (expected_shortfall == 0)
            or self.target_state != self.hazard.state
        ):
            raise ValueError("Troll Vomit Hazard result is inconsistent")

    def _validate_round_transition(self) -> None:
        source = self.source_request
        previous_turn = self.previous_round_state.active_turn
        current_turn = self.round_state.active_turn
        if previous_turn is None or current_turn is None:
            raise ValueError("Troll Vomit requires an active turn")
        previous_slot = previous_turn.action_slots[source.slot_index - 1]
        if previous_slot.executed or not self.slot.executed:
            raise ValueError("Troll Vomit must execute one unexecuted slot")
        receipt = self.slot.execution
        assert isinstance(receipt, ActionExecutionReceipt)
        if (
            receipt.id != source.id
            or receipt.executor_rule_id != source.rule_id
            or receipt.source_request_id != source.id
            or receipt.result_request_id != self.hazard.request_id
            or receipt.actor_id != source.actor_id
            or receipt.round_number != source.round_state.round_number
            or receipt.slot_index != source.slot_index
            or receipt.declaration != previous_slot.declaration
        ):
            raise ValueError("Troll Vomit receipt has stale provenance")
        if self.slot != replace(previous_slot, execution=receipt):
            raise ValueError("Troll Vomit may only add its receipt")
        expected_slots = tuple(
            self.slot if item.index == source.slot_index else item
            for item in previous_turn.action_slots
        )
        if current_turn != replace(previous_turn, action_slots=expected_slots):
            raise ValueError("Troll Vomit changed unrelated turn state")
        if self.round_state != replace(
            self.previous_round_state,
            active_turn=current_turn,
        ):
            raise ValueError("Troll Vomit changed unrelated round state")


def _validate_troll_vomit_context(
    request: TrollVomitActionExecutionRequest,
) -> None:
    if request.rule_id != TROLL_VOMIT_ACTION_EXECUTION_RULE_ID:
        raise ValueError("Troll Vomit request uses an unknown source rule")
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
        raise ValueError("only an Ability Improvise can use Troll Vomit")
    if declaration.improvise_approach_id != TROLL_VOMIT_RULE_ID:
        raise ValueError("Troll Vomit Ability must match the action slot")
    if declaration.improvise_produces_attack:
        raise ValueError("Troll Vomit is a Hazard action, not an Attack")
    if slot.executed:
        raise ValueError("the Troll Vomit slot has already been executed")
    if TROLL_VOMIT_RULE_ID not in request.actor_ability_rule_ids:
        raise ValueError("the actor does not have the Troll Vomit Ability")
    if request.actor_conditions.has(Condition.DEFENCELESS):
        raise ValueError("Defenceless characters cannot take actions")

    actor = request.round_state.participant_for(request.actor_id)
    target = request.round_state.participant_for(request.target.target_id)
    if actor.entity_id == target.entity_id or actor.side is target.side:
        raise ValueError("Troll Vomit requires an enemy target")
    if not request.target_in_close_range:
        raise ValueError("Troll Vomit target must be in Close Range")
    if not request.target.target_state.conditions.has(Condition.STAGGERED):
        raise ValueError("Troll Vomit requires a Staggered target")
    if request.target.selected_avoidance_skill is not Skill.ENDURANCE:
        raise ValueError("Troll Vomit requires an explicit Endurance Test")


def _troll_vomit_exposure(
    request: TrollVomitActionExecutionRequest,
) -> HazardExposureRequest:
    return HazardExposureRequest(
        resolution_id=f"{request.id}:exposure",
        test_id=request.target.avoidance_test.id,
        rating=3,
        avoidance_skill=Skill.ENDURANCE,
        rule_id=TROLL_VOMIT_RULE_ID,
        inflicts_wound=True,
        failure_conditions=(),
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
