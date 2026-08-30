from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from towr.domain.fate_models import (
    FATE_LAST_STAND_RULE_ID,
    FateBurnKind,
    FateBurnResult,
    FateLastStandEffectRequest,
    FateSessionState,
)
from towr.domain.injury_models import CharacterInjuryState, WoundRecord


FATE_LAST_STAND_APPLICATION_RULE_ID = "RULE-FATE-003:last-stand-application"


class FateLastStandResolutionStep(str, Enum):
    FEAT_ACCOMPLISHED = "feat_accomplished"
    ACTOR_DIED = "actor_died"


@dataclass(frozen=True, slots=True)
class FateLastStandApplicationRequest:
    id: str
    session_id: str
    actor_id: str
    battle_id: str
    burn: FateBurnResult
    injury_state: CharacterInjuryState
    qualifying_wound_sequence: int
    final_scope_reference_id: str
    affected_subject_ids: tuple[str, ...]
    accomplishment_reference_ids: tuple[str, ...]
    feat_accomplished: bool
    fits_game_tone_confirmed: bool
    within_actor_possibility_limits_confirmed: bool
    gm_adjustment_id: str | None = None
    consumed_effect_ids: tuple[str, ...] = ()
    rule_id: str = FATE_LAST_STAND_APPLICATION_RULE_ID

    def __post_init__(self) -> None:
        for value, name in (
            (self.id, "Last Stand application id"),
            (self.session_id, "Last Stand session_id"),
            (self.actor_id, "Last Stand actor_id"),
            (self.battle_id, "Last Stand battle_id"),
            (self.final_scope_reference_id, "Last Stand final scope reference"),
        ):
            _validate_non_empty_string(value, name)
        if not isinstance(self.burn, FateBurnResult):
            raise TypeError("burn must be a FateBurnResult")
        if not isinstance(self.injury_state, CharacterInjuryState):
            raise TypeError("injury_state must be a CharacterInjuryState")
        if self.injury_state.dead:
            raise ValueError("a dead actor cannot accomplish a Last Stand feat")
        _validate_positive_int(
            self.qualifying_wound_sequence,
            "Last Stand qualifying_wound_sequence",
        )
        affected_subject_ids = _validate_unique_non_empty_ids(
            self.affected_subject_ids,
            "Last Stand affected subject ID",
        )
        accomplishment_reference_ids = _validate_unique_non_empty_ids(
            self.accomplishment_reference_ids,
            "Last Stand accomplishment reference ID",
        )
        for value, name in (
            (self.feat_accomplished, "feat_accomplished"),
            (self.fits_game_tone_confirmed, "fits_game_tone_confirmed"),
            (
                self.within_actor_possibility_limits_confirmed,
                "within_actor_possibility_limits_confirmed",
            ),
        ):
            if not isinstance(value, bool):
                raise TypeError(f"{name} must be a bool")
            if not value:
                raise ValueError(f"Last Stand requires {name}")
        if self.gm_adjustment_id is not None:
            _validate_non_empty_string(
                self.gm_adjustment_id,
                "Last Stand gm_adjustment_id",
            )
        consumed_effect_ids = _validate_unique_ids(
            self.consumed_effect_ids,
            "consumed Last Stand effect ID",
        )

        effect = _last_stand_effect(self.burn)
        if self.session_id != effect.session_id:
            raise ValueError("Last Stand burn belongs to another session")
        if self.actor_id != effect.actor_id:
            raise ValueError("Last Stand burn belongs to another actor")
        if self.battle_id != effect.battle_id:
            raise ValueError("Last Stand burn belongs to another battle")
        if effect.id in consumed_effect_ids:
            raise ValueError("Last Stand effect was already consumed")
        _qualifying_wound(
            self.injury_state,
            self.qualifying_wound_sequence,
        )
        if self.rule_id != FATE_LAST_STAND_APPLICATION_RULE_ID:
            raise ValueError("Last Stand application uses an unknown rule")

        object.__setattr__(self, "affected_subject_ids", affected_subject_ids)
        object.__setattr__(
            self,
            "accomplishment_reference_ids",
            accomplishment_reference_ids,
        )
        object.__setattr__(
            self,
            "consumed_effect_ids",
            consumed_effect_ids,
        )


@dataclass(frozen=True, slots=True)
class FateLastStandApplicationResult:
    request_id: str
    rule_id: str
    source_request: FateLastStandApplicationRequest
    session_id: str
    actor_id: str
    battle_id: str
    fate_state: FateSessionState
    previous_injury_state: CharacterInjuryState
    injury_state: CharacterInjuryState
    qualifying_wound: WoundRecord
    feat_id: str
    final_scope_reference_id: str
    affected_subject_ids: tuple[str, ...]
    accomplishment_reference_ids: tuple[str, ...]
    feat_accomplished: bool
    fits_game_tone_confirmed: bool
    within_actor_possibility_limits_confirmed: bool
    desperate_battle_approval_id: str
    gm_adjustment_id: str | None
    test_required: bool
    actor_dies_after_feat: bool
    gm_may_adjust_scope: bool
    resolution_steps: tuple[FateLastStandResolutionStep, ...]
    previous_consumed_effect_ids: tuple[str, ...]
    consumed_effect_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Last Stand result request_id")
        _validate_non_empty_string(self.rule_id, "Last Stand result rule_id")
        if not isinstance(self.source_request, FateLastStandApplicationRequest):
            raise TypeError(
                "source_request must be a Last Stand application request"
            )
        if not isinstance(self.fate_state, FateSessionState):
            raise TypeError("fate_state must be a FateSessionState")
        if not isinstance(self.previous_injury_state, CharacterInjuryState):
            raise TypeError("previous_injury_state must be a CharacterInjuryState")
        if not isinstance(self.injury_state, CharacterInjuryState):
            raise TypeError("injury_state must be a CharacterInjuryState")
        if not isinstance(self.qualifying_wound, WoundRecord):
            raise TypeError("qualifying_wound must be a WoundRecord")

        request = self.source_request
        effect = _last_stand_effect(request.burn)
        expected_state = _last_stand_terminal_state(request.injury_state)
        expected_wound = _qualifying_wound(
            request.injury_state,
            request.qualifying_wound_sequence,
        )
        expected_steps = (
            FateLastStandResolutionStep.FEAT_ACCOMPLISHED,
            FateLastStandResolutionStep.ACTOR_DIED,
        )
        expected_consumed = (*request.consumed_effect_ids, effect.id)
        expected_rules = _last_stand_applied_rule_ids(request)
        if (
            self.request_id != request.id
            or self.rule_id != request.rule_id
            or self.session_id != request.session_id
            or self.actor_id != request.actor_id
            or self.battle_id != request.battle_id
            or self.fate_state != request.burn.state
            or self.previous_injury_state != request.injury_state
            or self.injury_state != expected_state
            or self.qualifying_wound != expected_wound
            or self.feat_id != effect.feat_id
            or self.final_scope_reference_id != request.final_scope_reference_id
            or self.affected_subject_ids != request.affected_subject_ids
            or self.accomplishment_reference_ids
            != request.accomplishment_reference_ids
            or self.feat_accomplished is not request.feat_accomplished
            or (
                self.fits_game_tone_confirmed
                is not request.fits_game_tone_confirmed
            )
            or (
                self.within_actor_possibility_limits_confirmed
                is not request.within_actor_possibility_limits_confirmed
            )
            or self.desperate_battle_approval_id
            != effect.desperate_battle_approval_id
            or self.gm_adjustment_id != request.gm_adjustment_id
            or self.test_required is not effect.test_required
            or self.actor_dies_after_feat is not effect.actor_dies_after_feat
            or self.gm_may_adjust_scope is not effect.gm_may_adjust_scope
            or self.resolution_steps != expected_steps
            or self.previous_consumed_effect_ids != request.consumed_effect_ids
            or self.consumed_effect_ids != expected_consumed
            or self.applied_rule_ids != expected_rules
        ):
            raise ValueError("Last Stand application result has stale provenance")


def _last_stand_effect(burn: FateBurnResult) -> FateLastStandEffectRequest:
    if (
        burn.burn.kind is not FateBurnKind.LAST_STAND
        or burn.rule_id != FATE_LAST_STAND_RULE_ID
        or not isinstance(burn.effect_request, FateLastStandEffectRequest)
    ):
        raise ValueError("Last Stand application requires its matching burn result")
    return burn.effect_request


def _qualifying_wound(
    state: CharacterInjuryState,
    sequence: int,
) -> WoundRecord:
    wound = next(
        (item for item in state.wounds if item.sequence == sequence),
        None,
    )
    if wound is None:
        raise ValueError("Last Stand requires an exact previously suffered Wound")
    return wound


def _last_stand_terminal_state(
    state: CharacterInjuryState,
) -> CharacterInjuryState:
    return replace(state, dead=True)


def _last_stand_applied_rule_ids(
    request: FateLastStandApplicationRequest,
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            (
                *request.burn.applied_rule_ids,
                request.rule_id,
            )
        )
    )


def _validate_unique_non_empty_ids(
    values: tuple[str, ...],
    name: str,
) -> tuple[str, ...]:
    result = _validate_unique_ids(values, name)
    if not result:
        raise ValueError(f"{name}s must not be empty")
    return result


def _validate_unique_ids(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    result = tuple(values)
    for value in result:
        _validate_non_empty_string(value, name)
    if len(set(result)) != len(result):
        raise ValueError(f"{name}s must be unique")
    return result


def _validate_positive_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if value < 1:
        raise ValueError(f"{name} must be positive")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
