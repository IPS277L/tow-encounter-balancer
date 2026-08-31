from __future__ import annotations

from dataclasses import dataclass, field, replace

from towr.domain.infection_models import DailyWoundState
from towr.domain.injury_models import (
    CharacterInjuryState,
    CharacterWoundRequest,
    CharacterWoundType,
    WoundDiceModifier,
    WoundNegationOption,
)
from towr.domain.retreat_models import RUN_FOR_YOUR_LIVES_RULE_ID
from towr.domain.run_for_your_lives_trapped_models import (
    RunForYourLivesTrappedCostResult,
    TrappedEscapeCostKind,
    TrappedWoundCostApplicationRequest,
)
from towr.domain.wound_lifecycle_models import (
    CharacterWoundLifecycleCompletionResult,
    CharacterWoundLifecycleRollRequest,
    CharacterWoundLifecycleRollResult,
)


@dataclass(frozen=True, slots=True)
class TrappedWoundCostTarget:
    actor_id: str
    wound_count: int
    state: CharacterInjuryState
    daily_wounds: DailyWoundState
    wound_dice_modifiers: tuple[WoundDiceModifier, ...] = field(
        default_factory=tuple
    )
    wound_negation_options: tuple[WoundNegationOption, ...] = field(
        default_factory=tuple
    )
    consumed_roll_ids: tuple[str, ...] = field(default_factory=tuple)
    consumed_near_miss_effect_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.actor_id, "Trapped Wound target actor_id")
        _validate_positive_int(self.wound_count, "Trapped Wound count")
        if not isinstance(self.state, CharacterInjuryState):
            raise TypeError("state must be a CharacterInjuryState")
        if self.state.dead:
            raise ValueError("Trapped Wounds require an initially living PC")
        if not isinstance(self.daily_wounds, DailyWoundState):
            raise TypeError("daily_wounds must be a DailyWoundState")
        if self.daily_wounds.target_id != self.actor_id:
            raise ValueError("daily Wound state belongs to another Trapped target")
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
        consumed_rolls = _validate_unique_ids(
            self.consumed_roll_ids,
            "consumed Wound lifecycle roll ID",
        )
        consumed_effects = _validate_unique_ids(
            self.consumed_near_miss_effect_ids,
            "consumed Near Miss effect ID",
        )
        object.__setattr__(self, "wound_dice_modifiers", modifiers)
        object.__setattr__(self, "wound_negation_options", options)
        object.__setattr__(self, "consumed_roll_ids", consumed_rolls)
        object.__setattr__(
            self,
            "consumed_near_miss_effect_ids",
            consumed_effects,
        )


@dataclass(frozen=True, slots=True)
class RunForYourLivesTrappedWoundRequest:
    id: str
    source_cost: RunForYourLivesTrappedCostResult
    targets: tuple[TrappedWoundCostTarget, ...]
    consumed_application_ids: tuple[str, ...] = field(default_factory=tuple)
    rule_id: str = RUN_FOR_YOUR_LIVES_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Trapped Wound request id")
        if not isinstance(self.source_cost, RunForYourLivesTrappedCostResult):
            raise TypeError(
                "source_cost must be a RunForYourLivesTrappedCostResult"
            )
        application = self.source_cost.application_request
        if (
            self.source_cost.decision.cost_kind is not TrappedEscapeCostKind.WOUNDS
            or self.source_cost.proof.cost_kind
            is not TrappedEscapeCostKind.WOUNDS
            or not isinstance(application, TrappedWoundCostApplicationRequest)
        ):
            raise ValueError("Trapped escape cost is not Wounds")
        targets = tuple(self.targets)
        if not all(isinstance(item, TrappedWoundCostTarget) for item in targets):
            raise TypeError("targets must contain TrappedWoundCostTarget values")
        if tuple(item.actor_id for item in targets) != application.affected_actor_ids:
            raise ValueError(
                "Trapped Wound targets must match the affected PC group order"
            )
        consumed = _validate_unique_ids(
            self.consumed_application_ids,
            "consumed Trapped Wound application ID",
        )
        if application.id in consumed:
            raise ValueError("Trapped Wound application was already consumed")
        _validate_non_empty_string(self.rule_id, "Trapped Wound rule_id")
        if self.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
            raise ValueError("Trapped Wound application uses an unknown rule")
        object.__setattr__(self, "targets", targets)
        object.__setattr__(self, "consumed_application_ids", consumed)


@dataclass(frozen=True, slots=True)
class TrappedWoundCostTargetProgress:
    source_target: TrappedWoundCostTarget
    previous_state: CharacterInjuryState
    state: CharacterInjuryState
    previous_daily_wounds: DailyWoundState
    daily_wounds: DailyWoundState
    completions: tuple[CharacterWoundLifecycleCompletionResult, ...]
    skipped_wound_count: int
    consumed_roll_ids: tuple[str, ...]
    consumed_near_miss_effect_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_target, TrappedWoundCostTarget):
            raise TypeError("source_target must be a TrappedWoundCostTarget")
        for value, name in (
            (self.previous_state, "previous_state"),
            (self.state, "state"),
        ):
            if not isinstance(value, CharacterInjuryState):
                raise TypeError(f"{name} must be a CharacterInjuryState")
        for value, name in (
            (self.previous_daily_wounds, "previous_daily_wounds"),
            (self.daily_wounds, "daily_wounds"),
        ):
            if not isinstance(value, DailyWoundState):
                raise TypeError(f"{name} must be a DailyWoundState")
        completions = tuple(self.completions)
        if not all(
            isinstance(item, CharacterWoundLifecycleCompletionResult)
            for item in completions
        ):
            raise TypeError("completions must contain Wound lifecycle results")
        _validate_non_negative_int(
            self.skipped_wound_count,
            "skipped Trapped Wound count",
        )
        if len(completions) + self.skipped_wound_count > self.assigned_wound_count:
            raise ValueError("Trapped Wound progress exceeds the assigned count")
        if self.skipped_wound_count:
            if not self.state.dead:
                raise ValueError("only death can skip assigned Trapped Wounds")
            if len(completions) + self.skipped_wound_count != self.assigned_wound_count:
                raise ValueError("death must skip every remaining assigned Wound")
        consumed_rolls = _validate_unique_ids(
            self.consumed_roll_ids,
            "consumed Wound lifecycle roll ID",
        )
        consumed_effects = _validate_unique_ids(
            self.consumed_near_miss_effect_ids,
            "consumed Near Miss effect ID",
        )
        object.__setattr__(self, "completions", completions)
        object.__setattr__(self, "consumed_roll_ids", consumed_rolls)
        object.__setattr__(
            self,
            "consumed_near_miss_effect_ids",
            consumed_effects,
        )

    @property
    def actor_id(self) -> str:
        return self.source_target.actor_id

    @property
    def assigned_wound_count(self) -> int:
        return self.source_target.wound_count

    @property
    def completed_wound_count(self) -> int:
        return len(self.completions)


@dataclass(frozen=True, slots=True)
class RunForYourLivesTrappedWoundResult:
    request_id: str
    rule_id: str
    source_request: RunForYourLivesTrappedWoundRequest
    target_progress: tuple[TrappedWoundCostTargetProgress, ...]
    pending_wound: CharacterWoundLifecycleRollResult | None
    previous_consumed_application_ids: tuple[str, ...]
    consumed_application_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Trapped Wound result request_id")
        _validate_non_empty_string(self.rule_id, "Trapped Wound result rule_id")
        if not isinstance(
            self.source_request,
            RunForYourLivesTrappedWoundRequest,
        ):
            raise TypeError(
                "source_request must be a RunForYourLivesTrappedWoundRequest"
            )
        progress = tuple(self.target_progress)
        if not all(
            isinstance(item, TrappedWoundCostTargetProgress) for item in progress
        ):
            raise TypeError(
                "target_progress must contain TrappedWoundCostTargetProgress values"
            )
        if self.pending_wound is not None and not isinstance(
            self.pending_wound,
            CharacterWoundLifecycleRollResult,
        ):
            raise TypeError("pending_wound must be a Wound lifecycle roll or None")
        source = self.source_request
        completions = tuple(
            completion
            for target_progress in progress
            for completion in target_progress.completions
        )
        expected_progress = _expected_target_progress(
            source,
            completions,
            self.pending_wound,
        )
        previous_consumed = _validate_unique_ids(
            self.previous_consumed_application_ids,
            "previous consumed Trapped Wound application ID",
        )
        consumed = _validate_unique_ids(
            self.consumed_application_ids,
            "consumed Trapped Wound application ID",
        )
        application = source.source_cost.application_request
        assert isinstance(application, TrappedWoundCostApplicationRequest)
        expected_consumed = (*source.consumed_application_ids, application.id)
        expected_rules = _result_rule_ids(
            source,
            completions,
            self.pending_wound,
        )
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or progress != expected_progress
            or previous_consumed != source.consumed_application_ids
            or consumed != expected_consumed
            or self.applied_rule_ids != expected_rules
        ):
            raise ValueError("Run For Your Lives Trapped Wound result is stale")
        object.__setattr__(self, "target_progress", progress)
        object.__setattr__(
            self,
            "previous_consumed_application_ids",
            previous_consumed,
        )
        object.__setattr__(self, "consumed_application_ids", consumed)

    @property
    def completed(self) -> bool:
        return self.pending_wound is None

    @property
    def active_target_id(self) -> str | None:
        if self.pending_wound is None:
            return None
        return self.pending_wound.source_request.target_id


@dataclass(frozen=True, slots=True)
class _CompletedReplay:
    progress: tuple[TrappedWoundCostTargetProgress, ...]
    next_request: CharacterWoundLifecycleRollRequest | None
    next_target_index: int | None


def _replay_completed_wounds(
    request: RunForYourLivesTrappedWoundRequest,
    completions: tuple[CharacterWoundLifecycleCompletionResult, ...],
) -> _CompletedReplay:
    completion_index = 0
    next_request: CharacterWoundLifecycleRollRequest | None = None
    next_target_index: int | None = None
    blocked = False
    progress: list[TrappedWoundCostTargetProgress] = []

    for target_index, target in enumerate(request.targets):
        state = target.state
        daily_wounds = target.daily_wounds
        consumed_rolls = target.consumed_roll_ids
        consumed_effects = target.consumed_near_miss_effect_ids
        target_completions: list[CharacterWoundLifecycleCompletionResult] = []
        skipped = 0

        if not blocked:
            for ordinal in range(1, target.wound_count + 1):
                if state.dead:
                    skipped = target.wound_count - len(target_completions)
                    break
                expected_request = _wound_lifecycle_request(
                    request,
                    target,
                    ordinal,
                    state,
                )
                if completion_index == len(completions):
                    next_request = expected_request
                    next_target_index = target_index
                    blocked = True
                    break
                completion = completions[completion_index]
                if completion.source_request.roll.source_request != expected_request:
                    raise ValueError(
                        "Trapped Wound completion is out of target/ordinal order"
                    )
                if completion.previous_daily_wounds != daily_wounds:
                    raise ValueError("Trapped Wound completion used stale daily state")
                if completion.previous_consumed_roll_ids != consumed_rolls:
                    raise ValueError("Trapped Wound roll consumption chain is stale")
                if (
                    completion.previous_consumed_near_miss_effect_ids
                    != consumed_effects
                ):
                    raise ValueError(
                        "Trapped Wound Near Miss consumption chain is stale"
                    )
                target_completions.append(completion)
                state = completion.state
                daily_wounds = completion.daily_wounds
                consumed_rolls = completion.consumed_roll_ids
                consumed_effects = completion.consumed_near_miss_effect_ids
                completion_index += 1

        progress.append(
            TrappedWoundCostTargetProgress(
                source_target=target,
                previous_state=target.state,
                state=state,
                previous_daily_wounds=target.daily_wounds,
                daily_wounds=daily_wounds,
                completions=tuple(target_completions),
                skipped_wound_count=skipped,
                consumed_roll_ids=consumed_rolls,
                consumed_near_miss_effect_ids=consumed_effects,
            )
        )

    if completion_index != len(completions):
        raise ValueError("Trapped Wound result contains an unexpected completion")
    return _CompletedReplay(
        progress=tuple(progress),
        next_request=next_request,
        next_target_index=next_target_index,
    )


def _expected_target_progress(
    request: RunForYourLivesTrappedWoundRequest,
    completions: tuple[CharacterWoundLifecycleCompletionResult, ...],
    pending: CharacterWoundLifecycleRollResult | None,
) -> tuple[TrappedWoundCostTargetProgress, ...]:
    replay = _replay_completed_wounds(request, completions)
    if replay.next_request is None:
        if pending is not None:
            raise ValueError("completed Trapped Wounds cannot retain a pending roll")
        return replay.progress
    if pending is None:
        raise ValueError("incomplete Trapped Wounds require the next pending roll")
    if pending.source_request != replay.next_request:
        raise ValueError("pending Trapped Wound is out of target/ordinal order")
    assert replay.next_target_index is not None
    progress = list(replay.progress)
    active = progress[replay.next_target_index]
    progress[replay.next_target_index] = replace(
        active,
        state=pending.wound_result.state,
    )
    return tuple(progress)


def _wound_lifecycle_request(
    request: RunForYourLivesTrappedWoundRequest,
    target: TrappedWoundCostTarget,
    ordinal: int,
    state: CharacterInjuryState,
) -> CharacterWoundLifecycleRollRequest:
    stem = f"{request.id}:{target.actor_id}:wound:{ordinal}"
    return CharacterWoundLifecycleRollRequest(
        id=f"{stem}:lifecycle",
        target_id=target.actor_id,
        wound=CharacterWoundRequest(
            id=stem,
            state=state,
            subject_type=CharacterWoundType.PLAYER,
            dice_modifiers=target.wound_dice_modifiers,
            negation_options=target.wound_negation_options,
            base_dice=1,
        ),
    )


def _result_rule_ids(
    request: RunForYourLivesTrappedWoundRequest,
    completions: tuple[CharacterWoundLifecycleCompletionResult, ...],
    pending: CharacterWoundLifecycleRollResult | None,
) -> tuple[str, ...]:
    return _ordered_rule_ids(
        *request.source_cost.applied_rule_ids,
        request.rule_id,
        *(rule_id for item in completions for rule_id in item.applied_rule_ids),
        *(() if pending is None else pending.applied_rule_ids),
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


def _validate_positive_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _validate_non_negative_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
