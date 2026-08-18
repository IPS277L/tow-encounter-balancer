from __future__ import annotations

from typing import Protocol

from towr.domain.test_models import (
    BasicOutcome,
    BasicTestResult,
    RerollTrace,
    RollTrace,
    TestQuality,
    TestRequest,
    TestResult,
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
    regular_delta = sum(
        modifier.amount
        for modifier in request.dice_modifiers
        if not modifier.bypasses_pool_cap
    )
    bypassing_dice = sum(
        modifier.amount
        for modifier in request.dice_modifiers
        if modifier.bypasses_pool_cap
    )
    capped_dice = min(
        request.profile.base_dice + regular_delta,
        request.profile.maximum_dice,
    )
    dice_before_minimum = capped_dice + bypassing_dice
    minimum_die_rule_applied = dice_before_minimum < 1
    rolled_dice = max(1, dice_before_minimum)
    threshold = 1 if minimum_die_rule_applied else request.profile.threshold
    quality = _resolve_quality(request)
    if quality is TestQuality.GLORIOUS and decisions is None:
        raise MissingTestDecisionError(
            "a Glorious Test requires an explicit TestDecisionProvider"
        )

    initial_values = tuple(rng.randint(1, 10) for _ in range(rolled_dice))
    initial_success_indices = tuple(
        index for index, value in enumerate(initial_values) if value <= threshold
    )
    initial_failure_indices = tuple(
        index for index, value in enumerate(initial_values) if value > threshold
    )

    if quality is TestQuality.GRIM:
        reroll_indices = initial_success_indices
    elif quality is TestQuality.GLORIOUS:
        assert decisions is not None
        chosen_indices = tuple(
            decisions.choose_glorious_rerolls(
                request=request,
                initial_values=initial_values,
                eligible_indices=initial_failure_indices,
            )
        )
        _validate_glorious_decision(chosen_indices, initial_failure_indices)
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
    success_delta = sum(modifier.amount for modifier in request.success_modifiers)
    successes = max(0, rolled_successes + success_delta)
    applied_rule_ids = tuple(
        modifier.rule_id
        for modifiers in (
            request.dice_modifiers,
            request.quality_modifiers,
            request.success_modifiers,
        )
        for modifier in modifiers
    )

    return TestResult(
        trace=RollTrace(
            request_id=request.id,
            base_dice=request.profile.base_dice,
            pool_cap=request.profile.maximum_dice,
            regular_dice_delta=regular_delta,
            cap_bypassing_dice=bypassing_dice,
            dice_before_minimum=dice_before_minimum,
            rolled_dice=rolled_dice,
            threshold=threshold,
            minimum_die_rule_applied=minimum_die_rule_applied,
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
