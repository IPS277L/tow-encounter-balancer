from __future__ import annotations

from dataclasses import dataclass

from towr.domain.test_models import (
    BasicOutcome,
    OpposedOutcome,
    OpposedSide,
    OpposedTestRequest,
    OpposedTestResult,
    TestRequest,
    TestResult,
)


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
class ExactingOpposedTestContribution:
    request_id: str
    opposed_test_id: str
    initiator_test_id: str
    opponent_test_id: str
    contributor_id: str
    contributor_side: OpposedSide
    successes: int
    rule_id: str = EXACTING_TEST_RULE_ID

    def __post_init__(self) -> None:
        for value, name in (
            (self.request_id, "opposed contribution request_id"),
            (self.opposed_test_id, "opposed contribution opposed_test_id"),
            (self.initiator_test_id, "opposed contribution initiator_test_id"),
            (self.opponent_test_id, "opposed contribution opponent_test_id"),
            (self.contributor_id, "opposed contribution contributor_id"),
            (self.rule_id, "opposed contribution rule_id"),
        ):
            _validate_non_empty_string(value, name)
        if not isinstance(self.contributor_side, OpposedSide):
            raise TypeError("contributor_side must be an OpposedSide")
        _validate_non_negative_int(
            self.successes,
            "opposed contribution successes",
        )
        test_ids = (
            self.opposed_test_id,
            self.initiator_test_id,
            self.opponent_test_id,
        )
        if len(set(test_ids)) != len(test_ids):
            raise ValueError("opposed contribution Test IDs must be unique")


ExactingContribution = ExactingTestContribution | ExactingOpposedTestContribution


@dataclass(frozen=True, slots=True)
class ExactingTestProgress:
    id: str
    required_successes: int
    contributions: tuple[ExactingContribution, ...] = ()
    rule_id: str = EXACTING_TEST_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Exacting progress id")
        _validate_positive_int(
            self.required_successes,
            "required_successes",
        )
        contributions = tuple(self.contributions)
        if not all(
            isinstance(
                item,
                (ExactingTestContribution, ExactingOpposedTestContribution),
            )
            for item in contributions
        ):
            raise TypeError(
                "contributions must contain Exacting contribution values"
            )
        request_ids = tuple(item.request_id for item in contributions)
        test_ids = tuple(
            test_id
            for item in contributions
            for test_id in _contribution_test_ids(item)
        )
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
        used_test_ids = {
            test_id
            for item in self.progress.contributions
            for test_id in _contribution_test_ids(item)
        }
        if self.test.id in used_test_ids:
            raise ValueError("Exacting contribution Test was already consumed")


@dataclass(frozen=True, slots=True)
class ExactingOpposedTestContributionRequest:
    id: str
    progress: ExactingTestProgress
    contributor_id: str
    contributor_side: OpposedSide
    test: OpposedTestRequest
    test_result: OpposedTestResult
    rule_id: str = EXACTING_TEST_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.id,
            "Exacting opposed contribution request id",
        )
        if not isinstance(self.progress, ExactingTestProgress):
            raise TypeError("progress must be an ExactingTestProgress")
        _validate_non_empty_string(self.contributor_id, "contributor_id")
        if not isinstance(self.contributor_side, OpposedSide):
            raise TypeError("contributor_side must be an OpposedSide")
        if not isinstance(self.test, OpposedTestRequest):
            raise TypeError("test must be an OpposedTestRequest")
        if not isinstance(self.test_result, OpposedTestResult):
            raise TypeError("test_result must be an OpposedTestResult")
        _validate_opposed_result(self.test, self.test_result)
        _validate_non_empty_string(self.rule_id, "Exacting opposed request rule_id")
        if self.progress.rule_id != self.rule_id:
            raise ValueError("Exacting progress uses another source rule")
        if self.progress.completed:
            raise ValueError("a completed Exacting Test cannot receive progress")
        if self.id in {
            item.request_id for item in self.progress.contributions
        }:
            raise ValueError("Exacting contribution request was already consumed")
        used_test_ids = {
            test_id
            for item in self.progress.contributions
            for test_id in _contribution_test_ids(item)
        }
        source_test_ids = (
            self.test.id,
            self.test.initiator.id,
            self.test.opponent.id,
        )
        if len(set(source_test_ids)) != len(source_test_ids):
            raise ValueError("Exacting opposed Test IDs must be unique")
        if any(test_id in used_test_ids for test_id in source_test_ids):
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


@dataclass(frozen=True, slots=True)
class ExactingOpposedTestContributionResult:
    request_id: str
    rule_id: str
    source_request: ExactingOpposedTestContributionRequest
    test_result: OpposedTestResult
    contribution: ExactingOpposedTestContribution
    previous_progress: ExactingTestProgress
    progress: ExactingTestProgress
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Exacting opposed result request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "Exacting opposed result rule_id",
        )
        if not isinstance(
            self.source_request,
            ExactingOpposedTestContributionRequest,
        ):
            raise TypeError(
                "source_request must be an Exacting opposed contribution request"
            )
        if not isinstance(self.test_result, OpposedTestResult):
            raise TypeError("test_result must be an OpposedTestResult")
        if not isinstance(
            self.contribution,
            ExactingOpposedTestContribution,
        ):
            raise TypeError(
                "contribution must be an Exacting opposed contribution"
            )
        if not isinstance(self.previous_progress, ExactingTestProgress):
            raise TypeError("previous_progress must be Exacting progress")
        if not isinstance(self.progress, ExactingTestProgress):
            raise TypeError("progress must be Exacting progress")

        source = self.source_request
        expected = _expected_opposed_contribution(source)
        expected_progress = ExactingTestProgress(
            id=source.progress.id,
            required_successes=source.progress.required_successes,
            contributions=(*source.progress.contributions, expected),
            rule_id=source.progress.rule_id,
        )
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.test_result != source.test_result
            or self.contribution != expected
            or self.previous_progress != source.progress
            or self.progress != expected_progress
        ):
            raise ValueError("Exacting opposed contribution result is stale")

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {
            self.rule_id,
            *self.test_result.initiator.trace.applied_rule_ids,
            *self.test_result.opponent.trace.applied_rule_ids,
        }
        if self.test_result.tie_break_applied:
            assert self.test_result.tie_break_rule_id is not None
            required.add(self.test_result.tie_break_rule_id)
        if not required <= set(rule_ids):
            raise ValueError("Exacting opposed contribution trace is incomplete")
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


def _expected_opposed_contribution(
    request: ExactingOpposedTestContributionRequest,
) -> ExactingOpposedTestContribution:
    result = request.test_result
    if result.winner is not request.contributor_side:
        successes = 0
    elif result.tie_break_applied:
        successes = 1
    else:
        successes = result.success_margin
    return ExactingOpposedTestContribution(
        request_id=request.id,
        opposed_test_id=request.test.id,
        initiator_test_id=request.test.initiator.id,
        opponent_test_id=request.test.opponent.id,
        contributor_id=request.contributor_id,
        contributor_side=request.contributor_side,
        successes=successes,
        rule_id=request.rule_id,
    )


def _contribution_test_ids(contribution: ExactingContribution) -> tuple[str, ...]:
    if isinstance(contribution, ExactingTestContribution):
        return (contribution.test_id,)
    return (
        contribution.opposed_test_id,
        contribution.initiator_test_id,
        contribution.opponent_test_id,
    )


def _validate_opposed_result(
    request: OpposedTestRequest,
    result: OpposedTestResult,
) -> None:
    if (
        result.request_id != request.id
        or result.initiator.trace.request_id != request.initiator.id
        or result.opponent.trace.request_id != request.opponent.id
    ):
        raise ValueError("Exacting Opposed Test result belongs elsewhere")
    initiator = result.initiator.successes
    opponent = result.opponent.successes
    if initiator == 0 and opponent == 0:
        expected = (
            OpposedOutcome.BOTH_FAIL,
            None,
            0,
            None,
            False,
            None,
        )
    elif initiator == opponent:
        winner = request.tie_break.winner
        expected = (
            (
                OpposedOutcome.INITIATOR_WINS
                if winner is OpposedSide.INITIATOR
                else OpposedOutcome.OPPONENT_WINS
            ),
            winner,
            0,
            BasicOutcome.MARGINAL_SUCCESS,
            True,
            request.tie_break.rule_id,
        )
    else:
        winner = (
            OpposedSide.INITIATOR
            if initiator > opponent
            else OpposedSide.OPPONENT
        )
        margin = abs(initiator - opponent)
        expected = (
            (
                OpposedOutcome.INITIATOR_WINS
                if winner is OpposedSide.INITIATOR
                else OpposedOutcome.OPPONENT_WINS
            ),
            winner,
            margin,
            _basic_outcome(margin),
            False,
            None,
        )
    actual = (
        result.outcome,
        result.winner,
        result.success_margin,
        result.consequence,
        result.tie_break_applied,
        result.tie_break_rule_id,
    )
    if actual != expected:
        raise ValueError("Exacting Opposed Test result is internally inconsistent")


def _basic_outcome(successes: int) -> BasicOutcome:
    if successes == 1:
        return BasicOutcome.MARGINAL_SUCCESS
    if successes == 2:
        return BasicOutcome.SUCCESS
    return BasicOutcome.TOTAL_SUCCESS


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
