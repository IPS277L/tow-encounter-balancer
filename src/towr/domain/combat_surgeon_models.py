from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from towr.domain.injury_models import (
    ActiveWoundEffect,
    CharacterInjuryState,
    WoundConditionEffect,
    WoundEffectDuration,
    WoundRestrictionEffect,
)
from towr.domain.recover_models import (
    RECOVER_TREAT_WOUND_APPLICATION_RULE_ID,
    RecoverWoundTreatmentResolutionResult,
)
from towr.domain.test_models import Skill, TestRequest, TestResult


COMBAT_SURGEON_RULE_ID = "RULE-TALENT-002:combat-surgeon"


class CombatSurgeonSuppressionDuration(str, Enum):
    REST_OF_BATTLE = "rest_of_battle"


@dataclass(frozen=True, slots=True)
class CombatSurgeonEffectSuppression:
    id: str
    source_request_id: str
    source_treatment_result_id: str
    source_treatment_application_id: str
    source_test_id: str
    battle_id: str
    surgeon_id: str
    target_id: str
    wound_sequence: int
    suppressed_effects: tuple[ActiveWoundEffect, ...]
    duration: CombatSurgeonSuppressionDuration = (
        CombatSurgeonSuppressionDuration.REST_OF_BATTLE
    )
    rule_id: str = COMBAT_SURGEON_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Combat Surgeon suppression id")
        _validate_non_empty_string(
            self.source_request_id,
            "suppression source_request_id",
        )
        _validate_non_empty_string(
            self.source_treatment_result_id,
            "suppression source_treatment_result_id",
        )
        _validate_non_empty_string(
            self.source_treatment_application_id,
            "suppression source_treatment_application_id",
        )
        _validate_non_empty_string(
            self.source_test_id,
            "suppression source_test_id",
        )
        _validate_non_empty_string(self.battle_id, "suppression battle_id")
        _validate_non_empty_string(self.surgeon_id, "suppression surgeon_id")
        _validate_non_empty_string(self.target_id, "suppression target_id")
        _validate_positive_int(self.wound_sequence, "suppression wound_sequence")
        effects = _validate_effects(self.suppressed_effects)
        if not effects:
            raise ValueError("Combat Surgeon must suppress at least one effect")
        if any(
            effect.wound_sequence != self.wound_sequence
            or effect.duration is not WoundEffectDuration.UNTIL_HEALED
            for effect in effects
        ):
            raise ValueError(
                "Combat Surgeon suppression must contain one Wound's "
                "until-healed effects"
            )
        object.__setattr__(self, "suppressed_effects", effects)
        if not isinstance(self.duration, CombatSurgeonSuppressionDuration):
            raise TypeError("suppression duration must be a duration value")
        if self.duration is not CombatSurgeonSuppressionDuration.REST_OF_BATTLE:
            raise ValueError("Combat Surgeon suppression lasts for this battle")
        _validate_non_empty_string(self.rule_id, "suppression rule_id")


@dataclass(frozen=True, slots=True)
class CombatSurgeonTreatmentRequest:
    id: str
    battle_id: str
    treatment: RecoverWoundTreatmentResolutionResult
    surgeon_id: str
    target_id: str
    injury_state: CharacterInjuryState
    recall_test: TestRequest
    surgeon_has_combat_surgeon: bool
    consumed_treatment_result_ids: tuple[str, ...] = ()
    recall_skill: Skill = Skill.RECALL
    rule_id: str = COMBAT_SURGEON_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Combat Surgeon request id")
        _validate_non_empty_string(self.battle_id, "battle_id")
        if not isinstance(
            self.treatment,
            RecoverWoundTreatmentResolutionResult,
        ):
            raise TypeError(
                "treatment must be a RecoverWoundTreatmentResolutionResult"
            )
        _validate_non_empty_string(self.surgeon_id, "surgeon_id")
        _validate_non_empty_string(self.target_id, "target_id")
        if not isinstance(self.injury_state, CharacterInjuryState):
            raise TypeError("injury_state must be a CharacterInjuryState")
        if not isinstance(self.recall_test, TestRequest):
            raise TypeError("recall_test must be a TestRequest")
        _validate_bool(
            self.surgeon_has_combat_surgeon,
            "surgeon_has_combat_surgeon",
        )
        if not isinstance(self.recall_skill, Skill):
            raise TypeError("recall_skill must be a Skill")
        if self.recall_skill is not Skill.RECALL:
            raise ValueError("Combat Surgeon must use Recall")
        consumed = _validate_consumed_ids(self.consumed_treatment_result_ids)
        object.__setattr__(self, "consumed_treatment_result_ids", consumed)
        _validate_non_empty_string(self.rule_id, "Combat Surgeon rule_id")

        treatment = self.treatment
        if treatment.rule_id != RECOVER_TREAT_WOUND_APPLICATION_RULE_ID:
            raise ValueError("Combat Surgeon requires canonical Wound treatment")
        source_application = treatment.source_request.recover.resolution.treatment
        assert source_application is not None
        if self.surgeon_id != source_application.actor_id:
            raise ValueError("Combat Surgeon belongs to another surgeon")
        if self.target_id != treatment.target_id:
            raise ValueError("Combat Surgeon treatment belongs to another target")
        if self.injury_state != treatment.state:
            raise ValueError("Combat Surgeon uses stale post-treatment state")
        if self.injury_state.dead:
            raise ValueError("Combat Surgeon cannot suppress effects for the dead")
        if not self.surgeon_has_combat_surgeon:
            raise ValueError("surgeon does not have Combat Surgeon")
        if treatment.request_id in consumed:
            raise ValueError("Combat Surgeon already used this treatment result")
        if self.recall_test.id == source_application.source_test_id:
            raise ValueError("Combat Surgeon requires an additional Recall Test")

        wound = self.injury_state.wounds[treatment.wound_sequence - 1]
        if wound.sequence != treatment.wound_sequence:
            raise ValueError("Combat Surgeon treatment references an unknown Wound")
        if not wound.treated or not wound.effect_resolved or wound.healed:
            raise ValueError(
                "Combat Surgeon requires one treated, active, resolved Wound"
            )
        if not _suppressible_effects(self):
            raise ValueError(
                "treated Wound has no ongoing effect until it is healed"
            )


@dataclass(frozen=True, slots=True)
class CombatSurgeonTreatmentResult:
    request_id: str
    rule_id: str
    source_request: CombatSurgeonTreatmentRequest
    recall_test_result: TestResult
    suppression: CombatSurgeonEffectSuppression | None
    previous_state: CharacterInjuryState
    state: CharacterInjuryState
    previous_consumed_treatment_result_ids: tuple[str, ...]
    consumed_treatment_result_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Combat Surgeon result id")
        _validate_non_empty_string(self.rule_id, "Combat Surgeon result rule_id")
        if not isinstance(self.source_request, CombatSurgeonTreatmentRequest):
            raise TypeError(
                "source_request must be a CombatSurgeonTreatmentRequest"
            )
        if not isinstance(self.recall_test_result, TestResult):
            raise TypeError("recall_test_result must be a TestResult")
        if self.suppression is not None and not isinstance(
            self.suppression,
            CombatSurgeonEffectSuppression,
        ):
            raise TypeError(
                "suppression must be a CombatSurgeonEffectSuppression or None"
            )
        if not isinstance(self.previous_state, CharacterInjuryState):
            raise TypeError("previous_state must be a CharacterInjuryState")
        if not isinstance(self.state, CharacterInjuryState):
            raise TypeError("state must be a CharacterInjuryState")

        source = self.source_request
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.recall_test_result.trace.request_id != source.recall_test.id
            or self.previous_state != source.injury_state
            or self.state != source.injury_state
        ):
            raise ValueError("Combat Surgeon result has stale provenance")
        expected = _expected_suppression(source, self.recall_test_result)
        if self.suppression != expected:
            raise ValueError("Combat Surgeon suppression does not match its Test")

        previous = _validate_consumed_ids(
            self.previous_consumed_treatment_result_ids
        )
        if previous != source.consumed_treatment_result_ids:
            raise ValueError("Combat Surgeon result has stale consumption")
        consumed = _validate_consumed_ids(self.consumed_treatment_result_ids)
        if consumed != (*previous, source.treatment.request_id):
            raise ValueError(
                "consumed treatment IDs must append the triggering treatment"
            )
        object.__setattr__(
            self,
            "previous_consumed_treatment_result_ids",
            previous,
        )
        object.__setattr__(self, "consumed_treatment_result_ids", consumed)

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {
            self.rule_id,
            source.treatment.rule_id,
            *self.recall_test_result.trace.applied_rule_ids,
        }
        if not required <= set(rule_ids):
            raise ValueError("Combat Surgeon trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)

    @property
    def succeeded(self) -> bool:
        return self.suppression is not None


def _suppressible_effects(
    request: CombatSurgeonTreatmentRequest,
) -> tuple[ActiveWoundEffect, ...]:
    sequence = request.treatment.wound_sequence
    return tuple(
        effect
        for effect in request.injury_state.active_wound_effects
        if effect.wound_sequence == sequence
        and effect.duration is WoundEffectDuration.UNTIL_HEALED
    )


def _expected_suppression(
    request: CombatSurgeonTreatmentRequest,
    result: TestResult,
) -> CombatSurgeonEffectSuppression | None:
    if not result.succeeded:
        return None
    treatment_application = (
        request.treatment.source_request.recover.resolution.treatment
    )
    assert treatment_application is not None
    return CombatSurgeonEffectSuppression(
        id=f"{request.id}:suppression",
        source_request_id=request.id,
        source_treatment_result_id=request.treatment.request_id,
        source_treatment_application_id=treatment_application.id,
        source_test_id=request.recall_test.id,
        battle_id=request.battle_id,
        surgeon_id=request.surgeon_id,
        target_id=request.target_id,
        wound_sequence=request.treatment.wound_sequence,
        suppressed_effects=_suppressible_effects(request),
        rule_id=request.rule_id,
    )


def _validate_effects(
    values: tuple[ActiveWoundEffect, ...],
) -> tuple[ActiveWoundEffect, ...]:
    effects = tuple(values)
    if not all(
        isinstance(item, (WoundConditionEffect, WoundRestrictionEffect))
        for item in effects
    ):
        raise TypeError("suppressed_effects must contain active Wound effects")
    if len(set(effects)) != len(effects):
        raise ValueError("suppressed_effects must be unique")
    return effects


def _validate_consumed_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    consumed = tuple(values)
    for value in consumed:
        _validate_non_empty_string(value, "consumed treatment result id")
    if len(set(consumed)) != len(consumed):
        raise ValueError("consumed treatment result IDs must be unique")
    return consumed


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


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")
