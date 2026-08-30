from __future__ import annotations

from dataclasses import dataclass

from towr.domain.test_models import TestRequest, TestResult


EXACTING_TEST_RULE_ID = "RULE-TEST-007:exacting-test"


@dataclass(frozen=True, slots=True)
class ExactingTestContribution:
    request_id: str
    test_id: str
    contributor_id: str
    successes: int
    rule_id: str = EXACTING_TEST_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "contribution request_id")
        _validate_non_empty_string(self.test_id, "contribution test_id")
        _validate_non_empty_string(
            self.contributor_id,
            "contribution contributor_id",
        )
        _validate_non_negative_int(self.successes, "contribution successes")
        _validate_non_empty_string(self.rule_id, "contribution rule_id")


@dataclass(frozen=True, slots=True)
class ExactingTestProgress:
    id: str
    required_successes: int
    contributions: tuple[ExactingTestContribution, ...] = ()
    rule_id: str = EXACTING_TEST_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Exacting progress id")
        _validate_positive_int(
            self.required_successes,
            "required_successes",
        )
        contributions = tuple(self.contributions)
        if not all(
            isinstance(item, ExactingTestContribution)
            for item in contributions
        ):
            raise TypeError(
                "contributions must contain ExactingTestContribution values"
            )
        request_ids = tuple(item.request_id for item in contributions)
        test_ids = tuple(item.test_id for item in contributions)
        if len(set(request_ids)) != len(request_ids):
            raise ValueError("Exacting contribution request IDs must be unique")
        if len(set(test_ids)) != len(test_ids):
            raise ValueError("Exacting contribution Test IDs must be unique")
        if any(item.rule_id != self.rule_id for item in contributions):
            raise ValueError("Exacting contributions use another source rule")
        object.__setattr__(self, "contributions", contributions)
        _validate_non_empty_string(self.rule_id, "Exacting progress rule_id")

    @property
    def accumulated_successes(self) -> int:
        return sum(item.successes for item in self.contributions)

    @property
    def completed(self) -> bool:
        return self.accumulated_successes >= self.required_successes


@dataclass(frozen=True, slots=True)
class ExactingTestContributionRequest:
    id: str
    progress: ExactingTestProgress
    contributor_id: str
    test: TestRequest
    rule_id: str = EXACTING_TEST_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Exacting contribution request id")
        if not isinstance(self.progress, ExactingTestProgress):
            raise TypeError("progress must be an ExactingTestProgress")
        _validate_non_empty_string(self.contributor_id, "contributor_id")
        if not isinstance(self.test, TestRequest):
            raise TypeError("test must be a TestRequest")
        _validate_non_empty_string(self.rule_id, "Exacting request rule_id")
        if self.progress.rule_id != self.rule_id:
            raise ValueError("Exacting progress uses another source rule")
        if self.progress.completed:
            raise ValueError("a completed Exacting Test cannot receive progress")
        if self.id in {
            item.request_id for item in self.progress.contributions
        }:
            raise ValueError("Exacting contribution request was already consumed")
        if self.test.id in {item.test_id for item in self.progress.contributions}:
            raise ValueError("Exacting contribution Test was already consumed")


@dataclass(frozen=True, slots=True)
class ExactingTestContributionResult:
    request_id: str
    rule_id: str
    source_request: ExactingTestContributionRequest
    test_result: TestResult
    contribution: ExactingTestContribution
    previous_progress: ExactingTestProgress
    progress: ExactingTestProgress
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Exacting result request_id")
        _validate_non_empty_string(self.rule_id, "Exacting result rule_id")
        if not isinstance(
            self.source_request,
            ExactingTestContributionRequest,
        ):
            raise TypeError(
                "source_request must be an Exacting contribution request"
            )
        if not isinstance(self.test_result, TestResult):
            raise TypeError("test_result must be a TestResult")
        if not isinstance(self.contribution, ExactingTestContribution):
            raise TypeError("contribution must be an Exacting contribution")
        if not isinstance(self.previous_progress, ExactingTestProgress):
            raise TypeError("previous_progress must be Exacting progress")
        if not isinstance(self.progress, ExactingTestProgress):
            raise TypeError("progress must be Exacting progress")

        source = self.source_request
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.test_result.trace.request_id != source.test.id
            or self.previous_progress != source.progress
        ):
            raise ValueError("Exacting contribution result has stale provenance")
        expected = _expected_contribution(source, self.test_result)
        if self.contribution != expected:
            raise ValueError("Exacting contribution disagrees with its Test")
        if self.progress != ExactingTestProgress(
            id=source.progress.id,
            required_successes=source.progress.required_successes,
            contributions=(*source.progress.contributions, expected),
            rule_id=source.progress.rule_id,
        ):
            raise ValueError("Exacting contribution changed unrelated progress")

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {
            self.rule_id,
            *self.test_result.trace.applied_rule_ids,
        }
        if not required <= set(rule_ids):
            raise ValueError("Exacting contribution trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


def _expected_contribution(
    request: ExactingTestContributionRequest,
    result: TestResult,
) -> ExactingTestContribution:
    return ExactingTestContribution(
        request_id=request.id,
        test_id=request.test.id,
        contributor_id=request.contributor_id,
        successes=result.successes,
        rule_id=request.rule_id,
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


def _validate_non_negative_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must not be negative")


def _validate_positive_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if value < 1:
        raise ValueError(f"{name} must be positive")
