from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.combat_surgeon_suppression_models import (
    COMBAT_SURGEON_EFFECTIVE_EFFECTS_RULE_ID,
    CombatSurgeonEffectiveEffectsResult,
)
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.test_models import (
    DiceModifier,
    FateGloriousProof,
    QualityModifier,
    QualityModifierSource,
    TestQuality,
    TestRequest,
)


DRAINED_TEST_PREPARATION_RULE_ID = "RULE-HEALTH-008:drained-test"


@dataclass(frozen=True, slots=True)
class DrainedTestPreparationRequest:
    id: str
    actor_id: str
    conditions: ConditionState
    test: TestRequest
    combat_surgeon_effective_effects: (
        CombatSurgeonEffectiveEffectsResult | None
    ) = None
    fate_glorious_proofs: tuple[FateGloriousProof, ...] = ()
    rule_id: str = DRAINED_TEST_PREPARATION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Drained request id")
        _validate_non_empty_string(self.actor_id, "Drained actor_id")
        if not isinstance(self.conditions, ConditionState):
            raise TypeError("conditions must be a ConditionState")
        if not isinstance(self.test, TestRequest):
            raise TypeError("test must be a TestRequest")
        _validate_non_empty_string(self.rule_id, "Drained rule_id")
        _validate_fate_proofs(self)

        effective = self.combat_surgeon_effective_effects
        if effective is None:
            return
        if not isinstance(effective, CombatSurgeonEffectiveEffectsResult):
            raise TypeError(
                "combat_surgeon_effective_effects must be an effective "
                "effects result or None"
            )
        if effective.rule_id != COMBAT_SURGEON_EFFECTIVE_EFFECTS_RULE_ID:
            raise ValueError("Drained preparation requires a canonical view")
        if effective.target_id != self.actor_id:
            raise ValueError("Combat Surgeon view belongs to another actor")
        if effective.injury_state.conditions != self.conditions:
            raise ValueError("Combat Surgeon view uses stale Conditions")


@dataclass(frozen=True, slots=True)
class DrainedTestPreparationResult:
    request_id: str
    rule_id: str
    source_request: DrainedTestPreparationRequest
    drained_active: bool
    removed_bonus_modifiers: tuple[DiceModifier, ...]
    removed_quality_modifiers: tuple[QualityModifier, ...]
    test: TestRequest
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Drained result request_id")
        _validate_non_empty_string(self.rule_id, "Drained result rule_id")
        if not isinstance(self.source_request, DrainedTestPreparationRequest):
            raise TypeError("source_request must be a Drained request")
        if not isinstance(self.drained_active, bool):
            raise TypeError("drained_active must be a boolean")
        removed = tuple(self.removed_bonus_modifiers)
        if not all(isinstance(item, DiceModifier) for item in removed):
            raise TypeError("removed bonuses must contain DiceModifier values")
        removed_quality = tuple(self.removed_quality_modifiers)
        if not all(isinstance(item, QualityModifier) for item in removed_quality):
            raise TypeError(
                "removed qualities must contain QualityModifier values"
            )
        if not isinstance(self.test, TestRequest):
            raise TypeError("test must be a TestRequest")

        source = self.source_request
        expected_active, expected_removed, expected_quality, expected_test = (
            _expected_drained_test_preparation(source)
        )
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.drained_active is not expected_active
            or removed != expected_removed
            or removed_quality != expected_quality
            or self.test != expected_test
        ):
            raise ValueError("Drained Test result has stale provenance")
        object.__setattr__(self, "removed_bonus_modifiers", removed)
        object.__setattr__(self, "removed_quality_modifiers", removed_quality)

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {self.rule_id}
        effective = source.combat_surgeon_effective_effects
        if effective is not None:
            required.update(effective.applied_rule_ids)
        required.update(
            proof.rule_id for proof in source.fate_glorious_proofs
        )
        if not required <= set(rule_ids):
            raise ValueError("Drained Test trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


def _expected_drained_test_preparation(
    request: DrainedTestPreparationRequest,
) -> tuple[
    bool,
    tuple[DiceModifier, ...],
    tuple[QualityModifier, ...],
    TestRequest,
]:
    effective = request.combat_surgeon_effective_effects
    conditions = (
        request.conditions
        if effective is None
        else effective.effective_conditions
    )
    drained_active = conditions.has(Condition.DRAINED)
    if not drained_active:
        return False, (), (), request.test

    removed = tuple(
        modifier
        for modifier in request.test.dice_modifiers
        if modifier.amount > 0
    )
    removed_quality = tuple(
        modifier
        for modifier in request.test.quality_modifiers
        if modifier.quality is TestQuality.GLORIOUS
        and modifier.source is not QualityModifierSource.FATE
    )
    if not removed and not removed_quality:
        return True, (), (), request.test
    return (
        True,
        removed,
        removed_quality,
        replace(
            request.test,
            dice_modifiers=tuple(
                modifier
                for modifier in request.test.dice_modifiers
                if modifier.amount < 0
            ),
            quality_modifiers=tuple(
                modifier
                for modifier in request.test.quality_modifiers
                if modifier not in removed_quality
            ),
        ),
    )


def _validate_fate_proofs(request: DrainedTestPreparationRequest) -> None:
    proofs = tuple(request.fate_glorious_proofs)
    if not all(isinstance(item, FateGloriousProof) for item in proofs):
        raise TypeError("fate_glorious_proofs must contain Fate proofs")
    expected_ids = tuple(
        modifier.source_id
        for modifier in request.test.quality_modifiers
        if modifier.source is QualityModifierSource.FATE
    )
    actual_ids = tuple(proof.id for proof in proofs)
    if actual_ids != expected_ids:
        raise ValueError("Fate proofs must match ordered Glorious modifiers")
    if any(
        proof.actor_id != request.actor_id or proof.test_id != request.test.id
        for proof in proofs
    ):
        raise ValueError("Fate proof belongs to another actor or Test")
    object.__setattr__(request, "fate_glorious_proofs", proofs)


def _validate_rule_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    rule_ids = tuple(values)
    if not rule_ids:
        raise ValueError("applied_rule_ids must not be empty")
    for rule_id in rule_ids:
        _validate_non_empty_string(rule_id, "applied Rule ID")
    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError("applied_rule_ids must be unique")
    return rule_ids


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
