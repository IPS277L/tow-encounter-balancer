from __future__ import annotations

from dataclasses import dataclass, field

from towr.domain.injury_models import (
    CharacterInjuryState,
    CharacterWoundRequest,
    CharacterWoundResult,
    CharacterWoundType,
    WoundDiceModifier,
    WoundNegationOption,
)
from towr.domain.retreat_models import (
    RETREAT_ALTERNATIVE_PRICE_RULE_ID,
    RetreatAlternativePrice,
    RetreatAlternativePriceResolutionResult,
    RetreatBloodPriceApplicationRequest,
)
from towr.domain.wound_lifecycle_models import (
    CharacterWoundLifecycleCompletionResult,
    CharacterWoundLifecycleRollRequest,
    CharacterWoundLifecycleRollResult,
)


@dataclass(frozen=True, slots=True)
class RetreatBloodPriceWoundRequest:
    """Bind an already selected blood price to one explicit player character."""

    id: str
    source_price: RetreatAlternativePriceResolutionResult
    target_id: str
    state: CharacterInjuryState
    wound_dice_modifiers: tuple[WoundDiceModifier, ...] = field(
        default_factory=tuple
    )
    wound_negation_options: tuple[WoundNegationOption, ...] = field(
        default_factory=tuple
    )
    consumed_application_ids: tuple[str, ...] = field(default_factory=tuple)
    rule_id: str = RETREAT_ALTERNATIVE_PRICE_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Retreat blood price Wound request id")
        if not isinstance(
            self.source_price,
            RetreatAlternativePriceResolutionResult,
        ):
            raise TypeError(
                "source_price must be a RetreatAlternativePriceResolutionResult"
            )
        application = self.source_price.application_request
        if (
            self.source_price.decision.price is not RetreatAlternativePrice.BLOOD
            or self.source_price.proof.price is not RetreatAlternativePrice.BLOOD
            or not isinstance(application, RetreatBloodPriceApplicationRequest)
        ):
            raise ValueError("Retreat price is not blood")
        _validate_non_empty_string(self.target_id, "Retreat blood price target_id")
        if self.target_id not in application.possible_target_actor_ids:
            raise ValueError("Retreat blood price target is not an eligible PC")
        if not isinstance(self.state, CharacterInjuryState):
            raise TypeError("state must be a CharacterInjuryState")
        if self.state.dead:
            raise ValueError("Retreat blood price requires a living PC")
        modifiers = tuple(self.wound_dice_modifiers)
        options = tuple(self.wound_negation_options)
        if not all(isinstance(item, WoundDiceModifier) for item in modifiers):
            raise TypeError(
                "wound_dice_modifiers must contain WoundDiceModifier values"
            )
        if not all(isinstance(item, WoundNegationOption) for item in options):
            raise TypeError(
                "wound_negation_options must contain WoundNegationOption values"
            )
        consumed = _validate_unique_ids(
            self.consumed_application_ids,
            "consumed Retreat price application ID",
        )
        if application.id in consumed:
            raise ValueError("Retreat blood price application was already consumed")
        _validate_non_empty_string(self.rule_id, "Retreat blood price rule_id")
        if self.rule_id != RETREAT_ALTERNATIVE_PRICE_RULE_ID:
            raise ValueError("Retreat blood price uses an unknown rule")
        object.__setattr__(self, "wound_dice_modifiers", modifiers)
        object.__setattr__(self, "wound_negation_options", options)
        object.__setattr__(self, "consumed_application_ids", consumed)


@dataclass(frozen=True, slots=True)
class RetreatBloodPriceApplicationResult:
    request_id: str
    rule_id: str
    source_request: RetreatBloodPriceWoundRequest
    target_id: str
    previous_state: CharacterInjuryState
    state: CharacterInjuryState
    character_wound: CharacterWoundResult
    pending_character_wound: CharacterWoundLifecycleRollResult | None
    character_wound_completion: CharacterWoundLifecycleCompletionResult | None
    previous_consumed_application_ids: tuple[str, ...]
    consumed_application_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Retreat blood price result request_id",
        )
        _validate_non_empty_string(self.rule_id, "Retreat blood price result rule_id")
        if not isinstance(self.source_request, RetreatBloodPriceWoundRequest):
            raise TypeError(
                "source_request must be a RetreatBloodPriceWoundRequest"
            )
        _validate_non_empty_string(self.target_id, "Retreat blood price result target_id")
        if not isinstance(self.previous_state, CharacterInjuryState):
            raise TypeError("previous_state must be a CharacterInjuryState")
        if not isinstance(self.state, CharacterInjuryState):
            raise TypeError("state must be a CharacterInjuryState")
        if not isinstance(self.character_wound, CharacterWoundResult):
            raise TypeError("character_wound must be a CharacterWoundResult")
        if self.pending_character_wound is not None and not isinstance(
            self.pending_character_wound,
            CharacterWoundLifecycleRollResult,
        ):
            raise TypeError("pending_character_wound must be a lifecycle roll or None")
        if self.character_wound_completion is not None and not isinstance(
            self.character_wound_completion,
            CharacterWoundLifecycleCompletionResult,
        ):
            raise TypeError(
                "character_wound_completion must be a lifecycle completion or None"
            )

        source = self.source_request
        application = source.source_price.application_request
        assert isinstance(application, RetreatBloodPriceApplicationRequest)
        previous_consumed = _validate_unique_ids(
            self.previous_consumed_application_ids,
            "previous consumed Retreat price application ID",
        )
        consumed = _validate_unique_ids(
            self.consumed_application_ids,
            "consumed Retreat price application ID",
        )
        expected_consumed = (*source.consumed_application_ids, application.id)
        expected_lifecycle = _wound_lifecycle_request(source)
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.target_id != source.target_id
            or self.previous_state != source.state
            or previous_consumed != source.consumed_application_ids
            or consumed != expected_consumed
        ):
            raise ValueError("Retreat blood price result has stale provenance")

        roll = self.pending_character_wound
        completion = self.character_wound_completion
        if roll is not None and completion is None:
            if (
                roll.source_request != expected_lifecycle
                or self.character_wound != roll.wound_result
                or self.state != roll.wound_result.state
            ):
                raise ValueError("pending Retreat blood price result is stale")
            trace_roll = roll
        elif roll is None and completion is not None:
            completion_roll = completion.source_request.roll
            if (
                completion_roll.source_request != expected_lifecycle
                or completion.previous_state != completion_roll.wound_result.state
                or self.character_wound != completion_roll.wound_result
                or self.state != completion.state
            ):
                raise ValueError("completed Retreat blood price result is stale")
            trace_roll = completion_roll
        else:
            raise ValueError(
                "Retreat blood price must be either pending or completed"
            )

        expected_rules = _ordered_rule_ids(
            *source.source_price.applied_rule_ids,
            source.rule_id,
            *trace_roll.applied_rule_ids,
            *(
                ()
                if completion is None
                else completion.applied_rule_ids
            ),
        )
        if self.applied_rule_ids != expected_rules:
            raise ValueError("Retreat blood price trace is incomplete")
        object.__setattr__(
            self,
            "previous_consumed_application_ids",
            previous_consumed,
        )
        object.__setattr__(self, "consumed_application_ids", consumed)


def _wound_lifecycle_request(
    request: RetreatBloodPriceWoundRequest,
) -> CharacterWoundLifecycleRollRequest:
    return CharacterWoundLifecycleRollRequest(
        id=f"{request.id}:wound-lifecycle",
        target_id=request.target_id,
        wound=CharacterWoundRequest(
            id=f"{request.id}:wound",
            state=request.state,
            subject_type=CharacterWoundType.PLAYER,
            dice_modifiers=request.wound_dice_modifiers,
            negation_options=request.wound_negation_options,
            base_dice=1,
        ),
    )


def _ordered_rule_ids(*rule_ids: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(rule_ids))


def _validate_unique_ids(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    ids = tuple(values)
    for value in ids:
        _validate_non_empty_string(value, name)
    if len(set(ids)) != len(ids):
        raise ValueError(f"{name}s must be unique")
    return ids


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
