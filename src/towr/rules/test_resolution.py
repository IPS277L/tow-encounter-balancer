from __future__ import annotations

from typing import Protocol

from towr.domain.test_models import (
    BasicOutcome,
    BasicTestResult,
    InitialTestRoll,
    QualityModifierSource,
    RerollTrace,
    RollTrace,
    TestQuality,
    TestRequest,
    TestResult,
    _expected_initial_roll_parameters,
)
from towr.rules.dice import RandomSource


class MissingTestDecisionError(RuntimeError):
    pass


class InvalidTestDecisionError(ValueError):
    pass


class TestDecisionProvider(Protocol):
    def choose_glorious_rerolls(
        self,
        *,
        request: TestRequest,
        initial_values: tuple[int, ...],
        eligible_indices: tuple[int, ...],
    ) -> tuple[int, ...]: ...


class RerollAllFailures:
    def choose_glorious_rerolls(
        self,
        *,
        request: TestRequest,
        initial_values: tuple[int, ...],
        eligible_indices: tuple[int, ...],
    ) -> tuple[int, ...]:
        del request, initial_values
        return eligible_indices


class KeepAllFailures:
    def choose_glorious_rerolls(
        self,
        *,
        request: TestRequest,
        initial_values: tuple[int, ...],
        eligible_indices: tuple[int, ...],
    ) -> tuple[int, ...]:
        del request, initial_values, eligible_indices
        return ()


def resolve_test(
    request: TestRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> TestResult:
    quality = _resolve_quality(request)
    if quality is TestQuality.GLORIOUS and decisions is None:
        raise MissingTestDecisionError(
            "a Glorious Test requires an explicit TestDecisionProvider"
        )
    initial_roll = roll_test_initial(request, rng)
    return complete_test(initial_roll, rng, decisions=decisions)


def roll_test_initial(
    request: TestRequest,
    rng: RandomSource,
) -> InitialTestRoll:
    """Roll only the immutable initial pool, before Grim/Glorious rerolls."""
    (
        base_dice,
        pool_cap,
        regular_delta,
        bypassing_dice,
        dice_before_minimum,
        rolled_dice,
        threshold,
        minimum_die_rule_applied,
    ) = _expected_initial_roll_parameters(request)
    return InitialTestRoll(
        request=request,
        base_dice=base_dice,
        pool_cap=pool_cap,
        regular_dice_delta=regular_delta,
        cap_bypassing_dice=bypassing_dice,
        dice_before_minimum=dice_before_minimum,
        rolled_dice=rolled_dice,
        threshold=threshold,
        minimum_die_rule_applied=minimum_die_rule_applied,
        initial_values=tuple(rng.randint(1, 10) for _ in range(rolled_dice)),
    )


def complete_test(
    initial_roll: InitialTestRoll,
    rng: RandomSource,
    *,
    request: TestRequest | None = None,
    decisions: TestDecisionProvider | None = None,
) -> TestResult:
    """Complete a snapshotted initial roll without rolling its pool again."""
    if not isinstance(initial_roll, InitialTestRoll):
        raise TypeError("initial_roll must be an InitialTestRoll")
    completion_request = initial_roll.request if request is None else request
    _validate_completion_request(initial_roll.request, completion_request)
    quality = _resolve_quality(completion_request)
    if quality is TestQuality.GLORIOUS and decisions is None:
        raise MissingTestDecisionError(
            "a Glorious Test requires an explicit TestDecisionProvider"
        )

    initial_values = initial_roll.initial_values
    threshold = initial_roll.threshold
    initial_success_indices = tuple(
        index for index, value in enumerate(initial_values) if value <= threshold
    )
    initial_failure_indices = tuple(
        index for index, value in enumerate(initial_values) if value > threshold
    )
    locked_values = {lock.value for lock in completion_request.reroll_locks}
    rerollable_success_indices = tuple(
        index
        for index in initial_success_indices
        if initial_values[index] not in locked_values
    )
    rerollable_failure_indices = tuple(
        index
        for index in initial_failure_indices
        if initial_values[index] not in locked_values
    )

    if quality is TestQuality.GRIM:
        reroll_indices = rerollable_success_indices
    elif quality is TestQuality.GLORIOUS:
        assert decisions is not None
        chosen_indices = tuple(
            decisions.choose_glorious_rerolls(
                request=completion_request,
                initial_values=initial_values,
                eligible_indices=rerollable_failure_indices,
            )
        )
        _validate_glorious_decision(
            chosen_indices,
            rerollable_failure_indices,
        )
        reroll_indices = tuple(sorted(chosen_indices))
    else:
        reroll_indices = ()

    final_values = list(initial_values)
    rerolls: list[RerollTrace] = []
    for index in reroll_indices:
        replacement = rng.randint(1, 10)
        rerolls.append(
            RerollTrace(
                index=index,
                original=initial_values[index],
                replacement=replacement,
            )
        )
        final_values[index] = replacement

    rolled_successes = sum(value <= threshold for value in final_values)
    success_delta = sum(
        modifier.amount for modifier in completion_request.success_modifiers
    )
    successes = max(0, rolled_successes + success_delta)
    applied_rule_ids = tuple(
        modifier.rule_id
        for modifiers in (
            completion_request.dice_modifiers,
            completion_request.quality_modifiers,
            completion_request.success_modifiers,
            completion_request.reroll_locks,
        )
        for modifier in modifiers
    )

    return TestResult(
        trace=RollTrace(
            request_id=completion_request.id,
            base_dice=initial_roll.base_dice,
            pool_cap=initial_roll.pool_cap,
            regular_dice_delta=initial_roll.regular_dice_delta,
            cap_bypassing_dice=initial_roll.cap_bypassing_dice,
            dice_before_minimum=initial_roll.dice_before_minimum,
            rolled_dice=initial_roll.rolled_dice,
            threshold=threshold,
            minimum_die_rule_applied=initial_roll.minimum_die_rule_applied,
            quality=quality,
            initial_values=initial_values,
            rerolls=tuple(rerolls),
            final_values=tuple(final_values),
            rolled_successes=rolled_successes,
            success_delta=success_delta,
            successes=successes,
            applied_rule_ids=applied_rule_ids,
        )
    )


def resolve_basic_test(
    request: TestRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> BasicTestResult:
    test = resolve_test(request, rng, decisions=decisions)
    return BasicTestResult(test=test, outcome=classify_basic_outcome(test.successes))


def classify_basic_outcome(successes: int) -> BasicOutcome:
    if successes < 0:
        raise ValueError("successes must not be negative")
    if successes == 0:
        return BasicOutcome.FAILURE
    if successes == 1:
        return BasicOutcome.MARGINAL_SUCCESS
    if successes == 2:
        return BasicOutcome.SUCCESS
    return BasicOutcome.TOTAL_SUCCESS


def _resolve_quality(request: TestRequest) -> TestQuality:
    has_grim = any(
        modifier.quality is TestQuality.GRIM
        for modifier in request.quality_modifiers
    )
    has_glorious = any(
        modifier.quality is TestQuality.GLORIOUS
        for modifier in request.quality_modifiers
    )
    if has_grim == has_glorious:
        return TestQuality.NORMAL
    return TestQuality.GRIM if has_grim else TestQuality.GLORIOUS


def _validate_completion_request(
    source: TestRequest,
    completion: TestRequest,
) -> None:
    if not isinstance(completion, TestRequest):
        raise TypeError("completion request must be a TestRequest")
    if (
        completion.id != source.id
        or completion.profile != source.profile
        or completion.dice_modifiers != source.dice_modifiers
        or completion.success_modifiers != source.success_modifiers
        or completion.reroll_locks != source.reroll_locks
    ):
        raise ValueError("completion request changes the snapshotted Test")
    if completion.quality_modifiers == source.quality_modifiers:
        return
    if (
        len(completion.quality_modifiers) == len(source.quality_modifiers) + 1
        and completion.quality_modifiers[:-1] == source.quality_modifiers
        and completion.quality_modifiers[-1].source is QualityModifierSource.FATE
        and completion.quality_modifiers[-1].quality is TestQuality.GLORIOUS
    ):
        return
    raise ValueError(
        "completion may only append one Fate Glorious modifier after the initial roll"
    )


def _validate_glorious_decision(
    chosen_indices: tuple[int, ...],
    eligible_indices: tuple[int, ...],
) -> None:
    if any(
        not isinstance(index, int) or isinstance(index, bool)
        for index in chosen_indices
    ):
        raise InvalidTestDecisionError("reroll indices must be integers")
    if len(set(chosen_indices)) != len(chosen_indices):
        raise InvalidTestDecisionError("reroll indices must be unique")
    eligible = set(eligible_indices)
    if any(index not in eligible for index in chosen_indices):
        raise InvalidTestDecisionError(
            "a Glorious Test can reroll only initial failures"
        )
