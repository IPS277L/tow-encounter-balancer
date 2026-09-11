from __future__ import annotations

from dataclasses import dataclass, field, replace

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.exacting_test_models import (
    EXACTING_TEST_RULE_ID,
    ExactingTestContributionRequest,
    ExactingTestContributionResult,
    ExactingTestProgress,
)
from towr.domain.ranged_weapon_profiles import (
    RANGED_WEAPON_RELOAD_RULE_ID,
    RangedReloadTrigger,
    RangedWeaponId,
    ranged_weapon_reload_profile,
)
from towr.domain.test_models import Skill, TestRequest
from towr.domain.turn_models import (
    ActionExecutionReceipt,
    CombatActionKind,
    CombatActionSlot,
    CombatRoundState,
    ImproviseKind,
)


RELOAD_RULE_ID = RANGED_WEAPON_RELOAD_RULE_ID


def reload_approach_id(weapon_instance_id: str) -> str:
    _validate_non_empty_string(weapon_instance_id, "weapon_instance_id")
    return f"{RELOAD_RULE_ID}:{weapon_instance_id}"


@dataclass(frozen=True, slots=True)
class FreeReloadWeaponState:
    weapon_instance_id: str
    weapon_id: RangedWeaponId
    rule_id: str = RELOAD_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.weapon_instance_id,
            "free reload weapon_instance_id",
        )
        if not isinstance(self.weapon_id, RangedWeaponId):
            raise TypeError("weapon_id must be a RangedWeaponId")
        _validate_non_empty_string(self.rule_id, "free reload state rule_id")
        profile = ranged_weapon_reload_profile(self.weapon_id)
        if self.rule_id != profile.rule_id:
            raise ValueError("free reload state uses another source rule")
        if profile.trigger is not RangedReloadTrigger.FREE_WITH_ATTACK:
            raise ValueError("weapon profile requires Exacting reload progress")


@dataclass(frozen=True, slots=True)
class ReloadableWeaponState:
    weapon_instance_id: str
    weapon_id: RangedWeaponId
    reload_cycle_id: str | None
    required_successes: int
    loaded: bool
    exacting: ExactingTestProgress | None
    reload_cycle_ids: tuple[str, ...] = field(default_factory=tuple)
    rule_id: str = RELOAD_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.weapon_instance_id,
            "reload weapon_instance_id",
        )
        if not isinstance(self.weapon_id, RangedWeaponId):
            raise TypeError("weapon_id must be a RangedWeaponId")
        _validate_positive_int(self.required_successes, "required_successes")
        if not isinstance(self.loaded, bool):
            raise TypeError("loaded must be a boolean")
        _validate_non_empty_string(self.rule_id, "reload state rule_id")
        profile = ranged_weapon_reload_profile(self.weapon_id)
        if self.rule_id != profile.rule_id:
            raise ValueError("reload state uses an unknown source rule")
        if not profile.requires_exacting_reload:
            raise ValueError("weapon profile reloads freely with its Attack")
        if self.required_successes != profile.required_successes:
            raise ValueError("reload target disagrees with the weapon profile")
        cycle_ids = tuple(self.reload_cycle_ids)
        for cycle_id in cycle_ids:
            _validate_non_empty_string(cycle_id, "reload cycle history ID")
        if len(set(cycle_ids)) != len(cycle_ids):
            raise ValueError("reload cycle IDs must be unique")
        object.__setattr__(self, "reload_cycle_ids", cycle_ids)
        if self.reload_cycle_id is None or self.exacting is None:
            if not self.loaded:
                raise ValueError("an unloaded weapon requires a reload cycle")
            if self.reload_cycle_id is not None or self.exacting is not None:
                raise ValueError(
                    "reload cycle ID and Exacting progress must appear together"
                )
            if cycle_ids:
                raise ValueError("initial loaded state has no reload cycles")
            return
        _validate_non_empty_string(self.reload_cycle_id, "reload_cycle_id")
        if not isinstance(self.exacting, ExactingTestProgress):
            raise TypeError("exacting must be an ExactingTestProgress")
        if self.exacting.id != f"{self.reload_cycle_id}:exacting":
            raise ValueError("reload Exacting progress belongs to another cycle")
        if not cycle_ids or cycle_ids[-1] != self.reload_cycle_id:
            raise ValueError("current reload cycle must end the cycle history")
        if (
            self.exacting.rule_id != EXACTING_TEST_RULE_ID
            or self.exacting.required_successes != self.required_successes
        ):
            raise ValueError("reload state has inconsistent Exacting progress")
        if self.loaded != self.exacting.completed:
            raise ValueError(
                "an active reload cycle loads only on Exacting completion"
            )


RangedWeaponReloadState = FreeReloadWeaponState | ReloadableWeaponState


def create_initial_ranged_weapon_reload_state(
    weapon_instance_id: str,
    weapon_id: RangedWeaponId,
) -> RangedWeaponReloadState:
    _validate_non_empty_string(weapon_instance_id, "weapon_instance_id")
    profile = ranged_weapon_reload_profile(weapon_id)
    if profile.trigger is RangedReloadTrigger.FREE_WITH_ATTACK:
        return FreeReloadWeaponState(
            weapon_instance_id=weapon_instance_id,
            weapon_id=weapon_id,
            rule_id=profile.rule_id,
        )
    assert profile.required_successes is not None
    return ReloadableWeaponState(
        weapon_instance_id=weapon_instance_id,
        weapon_id=weapon_id,
        reload_cycle_id=None,
        required_successes=profile.required_successes,
        loaded=True,
        exacting=None,
        reload_cycle_ids=(),
        rule_id=profile.rule_id,
    )


@dataclass(frozen=True, slots=True)
class ReloadActionExecutionRequest:
    id: str
    round_state: CombatRoundState
    actor_id: str
    actor_conditions: ConditionState
    slot_index: int
    weapon_state: ReloadableWeaponState
    dexterity_test: TestRequest
    skill: Skill = Skill.DEXTERITY
    rule_id: str = RELOAD_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "reload action id")
        if not isinstance(self.round_state, CombatRoundState):
            raise TypeError("round_state must be a CombatRoundState")
        _validate_non_empty_string(self.actor_id, "reload actor_id")
        if not isinstance(self.actor_conditions, ConditionState):
            raise TypeError("actor_conditions must be a ConditionState")
        _validate_slot_index(self.slot_index)
        if not isinstance(self.weapon_state, ReloadableWeaponState):
            raise TypeError("weapon_state must be a ReloadableWeaponState")
        if not isinstance(self.dexterity_test, TestRequest):
            raise TypeError("dexterity_test must be a TestRequest")
        if not isinstance(self.skill, Skill):
            raise TypeError("skill must be a Skill")
        _validate_non_empty_string(self.rule_id, "reload action rule_id")
        if self.rule_id != RELOAD_RULE_ID:
            raise ValueError("reload action uses an unknown source rule")
        if self.weapon_state.rule_id != self.rule_id:
            raise ValueError("reload action uses another weapon rule")
        if self.weapon_state.loaded:
            raise ValueError("a loaded weapon does not need reloading")
        if self.skill is not Skill.DEXTERITY:
            raise ValueError("reloading requires a Dexterity Test")
        if self.actor_conditions.has(Condition.DEFENCELESS):
            raise ValueError("Defenceless characters cannot take actions")
        _validate_reload_action_context(self)
        _exacting_request(self)


@dataclass(frozen=True, slots=True)
class ReloadActionExecutionResult:
    request_id: str
    rule_id: str
    source_request: ReloadActionExecutionRequest
    exacting: ExactingTestContributionResult
    previous_state: ReloadableWeaponState
    state: ReloadableWeaponState
    previous_round_state: CombatRoundState
    round_state: CombatRoundState
    slot: CombatActionSlot
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "reload result request_id")
        _validate_non_empty_string(self.rule_id, "reload result rule_id")
        if not isinstance(self.source_request, ReloadActionExecutionRequest):
            raise TypeError("source_request must be a reload action request")
        if not isinstance(self.exacting, ExactingTestContributionResult):
            raise TypeError("exacting must be an Exacting contribution result")
        if not isinstance(self.previous_state, ReloadableWeaponState):
            raise TypeError("previous_state must be a reload weapon state")
        if not isinstance(self.state, ReloadableWeaponState):
            raise TypeError("state must be a reload weapon state")
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
            or self.previous_state != source.weapon_state
            or self.previous_round_state != source.round_state
        ):
            raise ValueError("reload result has stale provenance")
        _validate_reload_action_context(source)
        expected_exacting_request = _exacting_request(source)
        if self.exacting.source_request != expected_exacting_request:
            raise ValueError("reload Exacting result is inconsistent")
        expected_state = replace(
            source.weapon_state,
            exacting=self.exacting.progress,
            loaded=self.exacting.progress.completed,
        )
        if self.state != expected_state:
            raise ValueError("reload changed unrelated weapon state")
        self._validate_round_transition()

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {self.rule_id, *self.exacting.applied_rule_ids}
        if not required <= set(rule_ids):
            raise ValueError("reload trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)

    @property
    def completed(self) -> bool:
        return self.state.loaded

    def _validate_round_transition(self) -> None:
        source = self.source_request
        previous_turn = self.previous_round_state.active_turn
        current_turn = self.round_state.active_turn
        if previous_turn is None or current_turn is None:
            raise ValueError("reload requires an active turn")
        previous_slot = previous_turn.action_slots[source.slot_index - 1]
        if previous_slot.executed or not self.slot.executed:
            raise ValueError("reload must execute one unexecuted slot")
        receipt = self.slot.execution
        assert isinstance(receipt, ActionExecutionReceipt)
        if (
            receipt.id != source.id
            or receipt.executor_rule_id != source.rule_id
            or receipt.source_request_id != source.id
            or receipt.result_request_id != self.exacting.request_id
            or receipt.actor_id != source.actor_id
            or receipt.round_number != source.round_state.round_number
            or receipt.slot_index != source.slot_index
            or receipt.declaration != previous_slot.declaration
        ):
            raise ValueError("reload receipt has stale provenance")
        if self.slot != replace(previous_slot, execution=receipt):
            raise ValueError("reload may only add its receipt")
        expected_slots = tuple(
            self.slot if item.index == source.slot_index else item
            for item in previous_turn.action_slots
        )
        if current_turn != replace(previous_turn, action_slots=expected_slots):
            raise ValueError("reload changed unrelated turn state")
        if self.round_state != replace(
            self.previous_round_state,
            active_turn=current_turn,
        ):
            raise ValueError("reload changed unrelated round state")


def _validate_reload_action_context(
    request: ReloadActionExecutionRequest,
) -> None:
    turn = request.round_state.active_turn
    if turn is None or turn.actor_id != request.actor_id:
        raise ValueError("reload requires the actor's active turn")
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
        or declaration.improvise_kind is not ImproviseKind.SKILL
    ):
        raise ValueError("reload requires a Skill Improvise action")
    if declaration.improvise_approach_id != reload_approach_id(
        request.weapon_state.weapon_instance_id
    ):
        raise ValueError("reload weapon must match the action slot")
    if declaration.improvise_produces_attack:
        raise ValueError("reload is not an Attack")
    if slot.executed:
        raise ValueError("the reload action slot has already been executed")


def _exacting_request(
    request: ReloadActionExecutionRequest,
) -> ExactingTestContributionRequest:
    assert request.weapon_state.exacting is not None
    return ExactingTestContributionRequest(
        id=f"{request.id}:exacting",
        progress=request.weapon_state.exacting,
        contributor_id=request.actor_id,
        test=request.dexterity_test,
    )


def _validate_rule_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    rule_ids = tuple(values)
    if not rule_ids:
        raise ValueError("applied_rule_ids must not be empty")
    for value in rule_ids:
        _validate_non_empty_string(value, "applied Rule ID")
    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError("applied_rule_ids must be unique")
    return rule_ids


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _validate_positive_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if value < 1:
        raise ValueError(f"{name} must be positive")


def _validate_slot_index(value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("slot_index must be an integer")
    if value not in (1, 2):
        raise ValueError("slot_index must be 1 or 2")
