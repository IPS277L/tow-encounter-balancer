from __future__ import annotations

from dataclasses import dataclass

from towr.domain.fate_models import (
    FATE_UNMITIGATED_SUCCESS_RULE_ID,
    FateBurnKind,
    FateBurnResult,
    FateSessionState,
    FateUnmitigatedSuccessEffectRequest,
)
from towr.domain.test_models import (
    BasicOutcome,
    InitialTestRoll,
    RerollTrace,
    RollTrace,
    TestQuality,
    TestRequest,
    TestResult,
    _expected_initial_roll_parameters,
)


FATE_UNMITIGATED_SUCCESS_APPLICATION_RULE_ID = (
    "RULE-FATE-003:unmitigated-success-application"
)


@dataclass(frozen=True, slots=True)
class FateUnmitigatedSuccessApplicationRequest:
    id: str
    session_id: str
    actor_id: str
    burn: FateBurnResult
    test_result: TestResult
    outcome_reference_id: str
    realistically_possible_outcome_confirmed: bool
    is_attack: bool
    killed_enemy_ids: tuple[str, ...] = ()
    wounds_inflicted: int = 0
    consumed_effect_ids: tuple[str, ...] = ()
    rule_id: str = FATE_UNMITIGATED_SUCCESS_APPLICATION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Unmitigated Success application id")
        _validate_non_empty_string(self.session_id, "Unmitigated Success session_id")
        _validate_non_empty_string(self.actor_id, "Unmitigated Success actor_id")
        if not isinstance(self.burn, FateBurnResult):
            raise TypeError("burn must be a FateBurnResult")
        if not isinstance(self.test_result, TestResult):
            raise TypeError("test_result must be a TestResult")
        _validate_non_empty_string(
            self.outcome_reference_id,
            "Unmitigated Success outcome_reference_id",
        )
        if self.realistically_possible_outcome_confirmed is not True:
            raise ValueError(
                "Unmitigated Success outcome must be confirmed realistically possible"
            )
        if not isinstance(self.is_attack, bool):
            raise TypeError("is_attack must be a bool")
        killed_enemy_ids = _validate_unique_ids(
            self.killed_enemy_ids,
            "Unmitigated Success killed enemy ID",
        )
        _validate_non_negative_int(
            self.wounds_inflicted,
            "Unmitigated Success wounds_inflicted",
        )
        consumed = _validate_unique_ids(
            self.consumed_effect_ids,
            "consumed Unmitigated Success effect ID",
        )
        effect = _unmitigated_success_effect(self.burn)
        if self.session_id != effect.session_id:
            raise ValueError("Unmitigated Success burn belongs to another session")
        if self.actor_id != effect.actor_id:
            raise ValueError("Unmitigated Success burn belongs to another actor")
        if effect.id in consumed:
            raise ValueError("Unmitigated Success effect was already consumed")
        if not self.is_attack and (killed_enemy_ids or self.wounds_inflicted):
            raise ValueError("non-attack outcome cannot declare attack consequences")
        if effect.may_not_kill_multiple_enemies and len(killed_enemy_ids) > 1:
            raise ValueError("Unmitigated Success cannot kill multiple enemies")
        if self.wounds_inflicted > effect.maximum_wounds_inflicted:
            raise ValueError("Unmitigated Success cannot inflict multiple Wounds")
        _validate_completed_test(effect, self.test_result)
        if self.rule_id != FATE_UNMITIGATED_SUCCESS_APPLICATION_RULE_ID:
            raise ValueError("Unmitigated Success application uses an unknown rule")
        object.__setattr__(self, "killed_enemy_ids", killed_enemy_ids)
        object.__setattr__(self, "consumed_effect_ids", consumed)


@dataclass(frozen=True, slots=True)
class FateUnmitigatedSuccessApplicationResult:
    request_id: str
    rule_id: str
    source_request: FateUnmitigatedSuccessApplicationRequest
    session_id: str
    actor_id: str
    fate_state: FateSessionState
    test_result: TestResult
    ordinary_outcome: BasicOutcome
    outcome: BasicOutcome
    outcome_reference_id: str
    gm_scope_agreement_id: str | None
    usual_outcome_superseded: bool
    realistically_possible_outcome_confirmed: bool
    is_attack: bool
    killed_enemy_ids: tuple[str, ...]
    wounds_inflicted: int
    previous_consumed_effect_ids: tuple[str, ...]
    consumed_effect_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Unmitigated Success result request_id",
        )
        _validate_non_empty_string(self.rule_id, "Unmitigated Success result rule_id")
        if not isinstance(
            self.source_request,
            FateUnmitigatedSuccessApplicationRequest,
        ):
            raise TypeError(
                "source_request must be an Unmitigated Success application request"
            )
        if not isinstance(self.fate_state, FateSessionState):
            raise TypeError("fate_state must be a FateSessionState")
        if not isinstance(self.test_result, TestResult):
            raise TypeError("test_result must be a TestResult")
        if not isinstance(self.ordinary_outcome, BasicOutcome):
            raise TypeError("ordinary_outcome must be a BasicOutcome")
        if not isinstance(self.outcome, BasicOutcome):
            raise TypeError("outcome must be a BasicOutcome")

        request = self.source_request
        effect = _unmitigated_success_effect(request.burn)
        expected_ordinary_outcome = _classify_basic_outcome(
            request.test_result.successes
        )
        expected_consumed = (*request.consumed_effect_ids, effect.id)
        expected_rules = _unmitigated_success_applied_rule_ids(request)
        if (
            self.request_id != request.id
            or self.rule_id != request.rule_id
            or self.session_id != request.session_id
            or self.actor_id != request.actor_id
            or self.fate_state != request.burn.state
            or self.test_result != request.test_result
            or self.ordinary_outcome is not expected_ordinary_outcome
            or self.outcome is not effect.minimum_outcome
            or self.outcome_reference_id != request.outcome_reference_id
            or self.gm_scope_agreement_id != effect.gm_scope_agreement_id
            or self.usual_outcome_superseded is not effect.usual_outcome_superseded
            or (
                self.realistically_possible_outcome_confirmed
                is not request.realistically_possible_outcome_confirmed
            )
            or self.is_attack is not request.is_attack
            or self.killed_enemy_ids != request.killed_enemy_ids
            or self.wounds_inflicted != request.wounds_inflicted
            or self.previous_consumed_effect_ids != request.consumed_effect_ids
            or self.consumed_effect_ids != expected_consumed
            or self.applied_rule_ids != expected_rules
        ):
            raise ValueError("Unmitigated Success application result has stale provenance")


def _unmitigated_success_effect(
    burn: FateBurnResult,
) -> FateUnmitigatedSuccessEffectRequest:
    if (
        burn.burn.kind is not FateBurnKind.UNMITIGATED_SUCCESS
        or burn.rule_id != FATE_UNMITIGATED_SUCCESS_RULE_ID
        or not isinstance(
            burn.effect_request,
            FateUnmitigatedSuccessEffectRequest,
        )
    ):
        raise ValueError(
            "Unmitigated Success application requires its matching burn result"
        )
    return burn.effect_request


def _validate_completed_test(
    effect: FateUnmitigatedSuccessEffectRequest,
    result: TestResult,
) -> None:
    request = effect.test
    trace = result.trace
    if not isinstance(trace, RollTrace):
        raise TypeError("test_result trace must be a RollTrace")
    expected_parameters = _expected_initial_roll_parameters(request)
    actual_parameters = (
        trace.base_dice,
        trace.pool_cap,
        trace.regular_dice_delta,
        trace.cap_bypassing_dice,
        trace.dice_before_minimum,
        trace.rolled_dice,
        trace.threshold,
        trace.minimum_die_rule_applied,
    )
    if trace.request_id != request.id or actual_parameters != expected_parameters:
        raise ValueError("Unmitigated Success requires the exact completed Test")

    initial_values = _validate_dice_values(
        trace.initial_values,
        trace.rolled_dice,
        "initial Test values",
    )
    final_values = _validate_dice_values(
        trace.final_values,
        trace.rolled_dice,
        "final Test values",
    )
    completed_initial_roll = InitialTestRoll(
        request=request,
        base_dice=trace.base_dice,
        pool_cap=trace.pool_cap,
        regular_dice_delta=trace.regular_dice_delta,
        cap_bypassing_dice=trace.cap_bypassing_dice,
        dice_before_minimum=trace.dice_before_minimum,
        rolled_dice=trace.rolled_dice,
        threshold=trace.threshold,
        minimum_die_rule_applied=trace.minimum_die_rule_applied,
        initial_values=initial_values,
    )
    expected_quality = _test_quality(request)
    if not isinstance(trace.rerolls, tuple):
        raise ValueError("Unmitigated Success requires a canonical Test reroll trace")
    rerolls = trace.rerolls
    if not all(isinstance(item, RerollTrace) for item in rerolls):
        raise ValueError("Unmitigated Success requires a canonical Test reroll trace")
    reroll_indices = tuple(item.index for item in rerolls)
    if (
        trace.quality is not expected_quality
        or reroll_indices != tuple(sorted(set(reroll_indices)))
    ):
        raise ValueError("Unmitigated Success requires a canonical Test reroll trace")

    locked_values = {lock.value for lock in request.reroll_locks}
    initial_successes = tuple(
        index
        for index, value in enumerate(initial_values)
        if value <= trace.threshold and value not in locked_values
    )
    initial_failures = tuple(
        index
        for index, value in enumerate(initial_values)
        if value > trace.threshold and value not in locked_values
    )
    if expected_quality is TestQuality.NORMAL and reroll_indices:
        raise ValueError("normal Test cannot contain rerolls")
    if expected_quality is TestQuality.GRIM and reroll_indices != initial_successes:
        raise ValueError("Grim Test reroll trace is incomplete")
    if expected_quality is TestQuality.GLORIOUS and any(
        index not in initial_failures for index in reroll_indices
    ):
        raise ValueError("Glorious Test reroll trace is invalid")

    reconstructed = list(initial_values)
    for reroll in rerolls:
        if (
            not isinstance(reroll.index, int)
            or isinstance(reroll.index, bool)
            or not isinstance(reroll.original, int)
            or isinstance(reroll.original, bool)
            or not isinstance(reroll.replacement, int)
            or isinstance(reroll.replacement, bool)
            or not 0 <= reroll.index < len(initial_values)
            or reroll.original != initial_values[reroll.index]
            or not 1 <= reroll.replacement <= 10
        ):
            raise ValueError("Unmitigated Success requires a canonical Test reroll trace")
        reconstructed[reroll.index] = reroll.replacement
    if tuple(reconstructed) != final_values:
        raise ValueError("Unmitigated Success Test final values are inconsistent")

    rolled_successes = sum(value <= trace.threshold for value in final_values)
    success_delta = sum(item.amount for item in request.success_modifiers)
    successes = max(0, rolled_successes + success_delta)
    applied_rule_ids = tuple(
        modifier.rule_id
        for modifiers in (
            request.dice_modifiers,
            request.quality_modifiers,
            request.success_modifiers,
            request.reroll_locks,
        )
        for modifier in modifiers
    )
    if (
        trace.rolled_successes != rolled_successes
        or type(trace.rolled_successes) is not type(rolled_successes)
        or trace.success_delta != success_delta
        or type(trace.success_delta) is not type(success_delta)
        or trace.successes != successes
        or type(trace.successes) is not type(successes)
        or trace.applied_rule_ids != applied_rule_ids
    ):
        raise ValueError("Unmitigated Success Test result has stale provenance")

    if (
        effect.initial_roll is not None
        and completed_initial_roll != effect.initial_roll
    ):
        raise ValueError(
            "Unmitigated Success completed Test uses another initial roll"
        )


def _test_quality(request: TestRequest) -> TestQuality:
    has_grim = any(
        item.quality is TestQuality.GRIM for item in request.quality_modifiers
    )
    has_glorious = any(
        item.quality is TestQuality.GLORIOUS
        for item in request.quality_modifiers
    )
    if has_grim == has_glorious:
        return TestQuality.NORMAL
    return TestQuality.GRIM if has_grim else TestQuality.GLORIOUS


def _classify_basic_outcome(successes: int) -> BasicOutcome:
    if successes == 0:
        return BasicOutcome.FAILURE
    if successes == 1:
        return BasicOutcome.MARGINAL_SUCCESS
    if successes == 2:
        return BasicOutcome.SUCCESS
    return BasicOutcome.TOTAL_SUCCESS


def _unmitigated_success_applied_rule_ids(
    request: FateUnmitigatedSuccessApplicationRequest,
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            (
                *request.test_result.trace.applied_rule_ids,
                *request.burn.applied_rule_ids,
                request.rule_id,
            )
        )
    )


def _validate_dice_values(
    values: tuple[int, ...],
    expected_count: int,
    name: str,
) -> tuple[int, ...]:
    if not isinstance(values, tuple):
        raise ValueError(f"{name} must be a tuple from the completed Test")
    result = tuple(values)
    if len(result) != expected_count or any(
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 1 <= value <= 10
        for value in result
    ):
        raise ValueError(f"{name} must match the completed Test pool")
    return result


def _validate_unique_ids(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    result = tuple(values)
    for value in result:
        _validate_non_empty_string(value, name)
    if len(set(result)) != len(result):
        raise ValueError(f"{name}s must be unique")
    return result


def _validate_non_negative_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must not be negative")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
