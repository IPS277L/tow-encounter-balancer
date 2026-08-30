from __future__ import annotations

from dataclasses import dataclass

from towr.domain.fate_models import (
    FATE_NEAR_MISS_RULE_ID,
    FateBurnKind,
    FateBurnResult,
    FateNearMissEffectRequest,
    FateSessionState,
)
from towr.domain.injury_models import (
    CharacterInjuryState,
    CharacterWoundRequest,
    CharacterWoundResult,
    CharacterWoundType,
    WoundEffectRequest,
    WoundRecord,
    validate_character_wound_result_provenance,
)


FATE_NEAR_MISS_APPLICATION_RULE_ID = (
    "RULE-FATE-003:near-miss-application"
)


@dataclass(frozen=True, slots=True)
class FateNearMissApplicationRequest:
    id: str
    session_id: str
    target_id: str
    burn: FateBurnResult
    wound_request: CharacterWoundRequest
    wound_result: CharacterWoundResult
    consumed_effect_ids: tuple[str, ...] = ()
    rule_id: str = FATE_NEAR_MISS_APPLICATION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Near Miss application id")
        _validate_non_empty_string(self.session_id, "Near Miss session_id")
        _validate_non_empty_string(self.target_id, "Near Miss target_id")
        if not isinstance(self.burn, FateBurnResult):
            raise TypeError("burn must be a FateBurnResult")
        if not isinstance(self.wound_request, CharacterWoundRequest):
            raise TypeError("wound_request must be a CharacterWoundRequest")
        if not isinstance(self.wound_result, CharacterWoundResult):
            raise TypeError("wound_result must be a CharacterWoundResult")
        _validate_non_empty_string(self.rule_id, "Near Miss application rule_id")
        consumed = _validate_consumed_ids(self.consumed_effect_ids)
        effect = _near_miss_effect(self.burn)
        if self.session_id != self.burn.state.session_id:
            raise ValueError("Near Miss burn belongs to another session")
        if self.target_id != self.burn.state.actor_id:
            raise ValueError("Near Miss Wound belongs to another actor")
        if self.wound_request.subject_type is not CharacterWoundType.PLAYER:
            raise ValueError("only a player character can burn Fate for Near Miss")
        if effect.id in consumed:
            raise ValueError("Near Miss effect was already consumed")
        if (
            effect.wound_negation.resolution_id != self.wound_request.id
            or self.wound_result.request_id != self.wound_request.id
        ):
            raise ValueError("Near Miss effect belongs to another Wound resolution")
        _validate_accepted_wound(self.wound_request, self.wound_result)
        object.__setattr__(self, "consumed_effect_ids", consumed)


@dataclass(frozen=True, slots=True)
class FateNearMissApplicationResult:
    request_id: str
    rule_id: str
    source_request: FateNearMissApplicationRequest
    session_id: str
    target_id: str
    fate_state: FateSessionState
    previous_state: CharacterInjuryState
    state: CharacterInjuryState
    cancelled_wound: WoundRecord
    discarded_effect_request: WoundEffectRequest
    previous_consumed_effect_ids: tuple[str, ...]
    consumed_effect_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Near Miss result request_id")
        _validate_non_empty_string(self.rule_id, "Near Miss result rule_id")
        if not isinstance(self.source_request, FateNearMissApplicationRequest):
            raise TypeError("source_request must be a Near Miss application request")
        _validate_non_empty_string(self.session_id, "Near Miss result session_id")
        _validate_non_empty_string(self.target_id, "Near Miss result target_id")
        if not isinstance(self.fate_state, FateSessionState):
            raise TypeError("fate_state must be a FateSessionState")
        if not isinstance(self.previous_state, CharacterInjuryState):
            raise TypeError("previous_state must be a CharacterInjuryState")
        if not isinstance(self.state, CharacterInjuryState):
            raise TypeError("state must be a CharacterInjuryState")
        if not isinstance(self.cancelled_wound, WoundRecord):
            raise TypeError("cancelled_wound must be a WoundRecord")
        if not isinstance(self.discarded_effect_request, WoundEffectRequest):
            raise TypeError("discarded_effect_request must be a WoundEffectRequest")

        request = self.source_request
        effect = _near_miss_effect(request.burn)
        expected_previous = request.wound_result.state
        expected_state = request.wound_request.state
        expected_wound = expected_previous.wounds[-1]
        expected_effect = request.wound_result.effect_request
        assert expected_effect is not None
        previous_consumed = _validate_consumed_ids(
            self.previous_consumed_effect_ids
        )
        consumed = _validate_consumed_ids(self.consumed_effect_ids)
        expected_consumed = (*request.consumed_effect_ids, effect.id)
        expected_rules = _near_miss_applied_rule_ids(request)
        if (
            self.request_id != request.id
            or self.rule_id != request.rule_id
            or self.session_id != request.session_id
            or self.target_id != request.target_id
            or self.fate_state != request.burn.state
            or self.previous_state != expected_previous
            or self.state != expected_state
            or self.cancelled_wound != expected_wound
            or self.discarded_effect_request != expected_effect
            or previous_consumed != request.consumed_effect_ids
            or consumed != expected_consumed
            or self.applied_rule_ids != expected_rules
        ):
            raise ValueError("Near Miss application result has stale provenance")
        object.__setattr__(
            self,
            "previous_consumed_effect_ids",
            previous_consumed,
        )
        object.__setattr__(self, "consumed_effect_ids", consumed)


def _near_miss_effect(burn: FateBurnResult) -> FateNearMissEffectRequest:
    if (
        burn.burn.kind is not FateBurnKind.NEAR_MISS
        or burn.rule_id != FATE_NEAR_MISS_RULE_ID
        or not isinstance(burn.effect_request, FateNearMissEffectRequest)
    ):
        raise ValueError("Near Miss application requires a Near Miss burn result")
    return burn.effect_request


def _validate_accepted_wound(
    request: CharacterWoundRequest,
    result: CharacterWoundResult,
) -> None:
    if (
        result.subject_type is not request.subject_type
        or not result.wound_accepted
        or result.negated_by_rule_id is not None
        or result.effect_request is None
    ):
        raise ValueError("Near Miss requires a newly accepted Wound")
    validate_character_wound_result_provenance(request, result)


def _near_miss_applied_rule_ids(
    request: FateNearMissApplicationRequest,
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            (
                *request.wound_result.applied_rule_ids,
                *request.burn.applied_rule_ids,
                request.rule_id,
            )
        )
    )


def _validate_consumed_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    consumed = tuple(values)
    for value in consumed:
        _validate_non_empty_string(value, "consumed Near Miss effect ID")
    if len(set(consumed)) != len(consumed):
        raise ValueError("consumed Near Miss effect IDs must be unique")
    return consumed


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
