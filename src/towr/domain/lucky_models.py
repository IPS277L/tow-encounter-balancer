from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.test_models import (
    QualityModifier,
    QualityModifierSource,
    TestQuality,
    TestRequest,
)


LUCKY_RULE_ID = "RULE-TALENT-078:lucky"


@dataclass(frozen=True, slots=True)
class LuckyGamblingProof:
    id: str
    actor_id: str
    test_id: str
    game_id: str
    source_request_id: str
    rule_id: str = LUCKY_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Lucky gambling proof id")
        _validate_non_empty_string(self.actor_id, "Lucky gambling actor_id")
        _validate_non_empty_string(self.test_id, "Lucky gambling test_id")
        _validate_non_empty_string(self.game_id, "Lucky gambling game_id")
        _validate_non_empty_string(
            self.source_request_id,
            "Lucky gambling source_request_id",
        )
        if self.rule_id != LUCKY_RULE_ID:
            raise ValueError("Lucky gambling proof requires its canonical rule")


@dataclass(frozen=True, slots=True)
class LuckyGamblingTestPreparationRequest:
    id: str
    actor_id: str
    game_id: str
    test: TestRequest
    actor_talent_rule_ids: tuple[str, ...]
    rule_id: str = LUCKY_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Lucky gambling request id")
        _validate_non_empty_string(self.actor_id, "Lucky gambling actor_id")
        _validate_non_empty_string(self.game_id, "Lucky gambling game_id")
        if not isinstance(self.test, TestRequest):
            raise TypeError("test must be a TestRequest")
        talent_rule_ids = _validate_rule_ids(self.actor_talent_rule_ids)
        if LUCKY_RULE_ID not in talent_rule_ids:
            raise ValueError("gambling Test requires the actor's Lucky Talent")
        if any(
            modifier.rule_id == LUCKY_RULE_ID
            for modifier in self.test.quality_modifiers
        ):
            raise ValueError("Lucky already prepared this gambling Test")
        if any(
            modifier.source is QualityModifierSource.FATE
            for modifier in self.test.quality_modifiers
        ):
            raise ValueError(
                "Lucky gambling preparation must precede any Fate spend"
            )
        _validate_non_empty_string(self.rule_id, "Lucky gambling rule_id")
        object.__setattr__(self, "actor_talent_rule_ids", talent_rule_ids)


@dataclass(frozen=True, slots=True)
class LuckyGamblingTestPreparationResult:
    request_id: str
    rule_id: str
    source_request: LuckyGamblingTestPreparationRequest
    proof: LuckyGamblingProof
    test: TestRequest
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Lucky gambling result request_id")
        _validate_non_empty_string(self.rule_id, "Lucky gambling result rule_id")
        if not isinstance(
            self.source_request,
            LuckyGamblingTestPreparationRequest,
        ):
            raise TypeError("source_request must be a Lucky gambling request")
        if not isinstance(self.proof, LuckyGamblingProof):
            raise TypeError("proof must be a LuckyGamblingProof")
        if not isinstance(self.test, TestRequest):
            raise TypeError("test must be a TestRequest")
        expected_proof, expected_test = _expected_lucky_gambling_test(
            self.source_request
        )
        if (
            self.request_id != self.source_request.id
            or self.rule_id != self.source_request.rule_id
            or self.proof != expected_proof
            or self.test != expected_test
            or self.applied_rule_ids != (LUCKY_RULE_ID,)
        ):
            raise ValueError("Lucky gambling result has stale provenance")


def _expected_lucky_gambling_test(
    request: LuckyGamblingTestPreparationRequest,
) -> tuple[LuckyGamblingProof, TestRequest]:
    proof = LuckyGamblingProof(
        id=f"{request.id}:proof",
        actor_id=request.actor_id,
        test_id=request.test.id,
        game_id=request.game_id,
        source_request_id=request.id,
    )
    test = replace(
        request.test,
        quality_modifiers=(
            *request.test.quality_modifiers,
            QualityModifier(
                rule_id=LUCKY_RULE_ID,
                quality=TestQuality.GLORIOUS,
                source=QualityModifierSource.TALENT,
                source_id=proof.id,
            ),
        ),
    )
    return proof, test


def _validate_rule_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    rule_ids = tuple(values)
    if not rule_ids:
        raise ValueError("actor_talent_rule_ids must not be empty")
    for rule_id in rule_ids:
        _validate_non_empty_string(rule_id, "Talent Rule ID")
    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError("actor_talent_rule_ids must be unique")
    return rule_ids


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
