from __future__ import annotations

from dataclasses import dataclass, field, replace

from towr.domain.combat_surgeon_models import (
    COMBAT_SURGEON_RULE_ID,
    CombatSurgeonEffectSuppression,
    CombatSurgeonTreatmentResult,
)
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import (
    ActiveWoundEffect,
    CharacterInjuryState,
    WoundConditionEffect,
    WoundConditionSourceSnapshot,
    WoundEffectDuration,
    WoundRecord,
    WoundRestrictionEffect,
)


COMBAT_SURGEON_SUPPRESSION_REGISTRATION_RULE_ID = (
    "RULE-TALENT-002:combat-surgeon-suppression-registration"
)
COMBAT_SURGEON_EFFECTIVE_EFFECTS_RULE_ID = (
    "RULE-TALENT-002:combat-surgeon-effective-effects"
)


@dataclass(frozen=True, slots=True)
class CombatSurgeonSuppressionAggregate:
    battle_id: str
    suppressions: tuple[CombatSurgeonEffectSuppression, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.battle_id, "suppression battle_id")
        suppressions = tuple(self.suppressions)
        if not all(
            isinstance(item, CombatSurgeonEffectSuppression)
            for item in suppressions
        ):
            raise TypeError(
                "suppressions must contain Combat Surgeon suppressions"
            )
        if any(item.battle_id != self.battle_id for item in suppressions):
            raise ValueError("suppression belongs to another battle")
        if any(item.rule_id != COMBAT_SURGEON_RULE_ID for item in suppressions):
            raise ValueError("aggregate requires canonical suppressions")
        _validate_unique(
            (item.id for item in suppressions),
            "suppression IDs",
        )
        _validate_unique(
            (item.source_request_id for item in suppressions),
            "suppression source request IDs",
        )
        _validate_unique(
            (
                (item.target_id, item.wound_sequence)
                for item in suppressions
            ),
            "suppressed target/Wound pairs",
        )
        object.__setattr__(self, "suppressions", suppressions)


@dataclass(frozen=True, slots=True)
class CombatSurgeonSuppressionRegistrationRequest:
    id: str
    aggregate: CombatSurgeonSuppressionAggregate
    source: CombatSurgeonTreatmentResult
    rule_id: str = COMBAT_SURGEON_SUPPRESSION_REGISTRATION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "suppression registration id")
        if not isinstance(self.aggregate, CombatSurgeonSuppressionAggregate):
            raise TypeError("aggregate must be a suppression aggregate")
        if not isinstance(self.source, CombatSurgeonTreatmentResult):
            raise TypeError("source must be a Combat Surgeon treatment result")
        _validate_non_empty_string(
            self.rule_id,
            "suppression registration rule_id",
        )
        if self.source.rule_id != COMBAT_SURGEON_RULE_ID:
            raise ValueError("registration requires canonical Combat Surgeon")
        suppression = self.source.suppression
        if suppression is None:
            raise ValueError("registration requires successful suppression")
        if suppression.battle_id != self.aggregate.battle_id:
            raise ValueError("suppression belongs to another battle")
        if suppression.id in {
            item.id for item in self.aggregate.suppressions
        }:
            raise ValueError("suppression was already registered")


@dataclass(frozen=True, slots=True)
class CombatSurgeonSuppressionRegistrationResult:
    request_id: str
    rule_id: str
    source_request: CombatSurgeonSuppressionRegistrationRequest
    suppression: CombatSurgeonEffectSuppression
    previous_aggregate: CombatSurgeonSuppressionAggregate
    aggregate: CombatSurgeonSuppressionAggregate
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "suppression registration result request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "suppression registration result rule_id",
        )
        if not isinstance(
            self.source_request,
            CombatSurgeonSuppressionRegistrationRequest,
        ):
            raise TypeError(
                "source_request must be a suppression registration request"
            )
        if not isinstance(self.suppression, CombatSurgeonEffectSuppression):
            raise TypeError("suppression must be a Combat Surgeon suppression")
        if not isinstance(
            self.previous_aggregate,
            CombatSurgeonSuppressionAggregate,
        ):
            raise TypeError("previous_aggregate must be an aggregate")
        if not isinstance(self.aggregate, CombatSurgeonSuppressionAggregate):
            raise TypeError("aggregate must be a suppression aggregate")

        source = self.source_request
        expected_suppression = source.source.suppression
        assert expected_suppression is not None
        expected_aggregate = replace(
            source.aggregate,
            suppressions=(
                *source.aggregate.suppressions,
                expected_suppression,
            ),
        )
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.suppression != expected_suppression
            or self.previous_aggregate != source.aggregate
            or self.aggregate != expected_aggregate
        ):
            raise ValueError("suppression registration has stale provenance")

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {
            self.rule_id,
            *source.source.applied_rule_ids,
        }
        if not required <= set(rule_ids):
            raise ValueError("suppression registration trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


@dataclass(frozen=True, slots=True)
class CombatSurgeonEffectiveEffectsRequest:
    id: str
    battle_id: str
    aggregate: CombatSurgeonSuppressionAggregate
    target_id: str
    injury_state: CharacterInjuryState
    condition_source_snapshots: tuple[
        WoundConditionSourceSnapshot, ...
    ] = ()
    rule_id: str = COMBAT_SURGEON_EFFECTIVE_EFFECTS_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "effective-effects request id")
        _validate_non_empty_string(self.battle_id, "effective battle_id")
        if not isinstance(self.aggregate, CombatSurgeonSuppressionAggregate):
            raise TypeError("aggregate must be a suppression aggregate")
        _validate_non_empty_string(self.target_id, "effective target_id")
        if not isinstance(self.injury_state, CharacterInjuryState):
            raise TypeError("injury_state must be a CharacterInjuryState")
        _validate_non_empty_string(self.rule_id, "effective-effects rule_id")
        if self.battle_id != self.aggregate.battle_id:
            raise ValueError("effective-effects view belongs to another battle")
        matching = tuple(
            item
            for item in self.aggregate.suppressions
            if item.target_id == self.target_id
        )
        if not matching:
            raise ValueError("target has no registered Combat Surgeon suppression")
        _validate_suppression_context(self.injury_state, matching)
        snapshots = _validate_condition_source_snapshots(
            self.injury_state,
            _active_suppressed_effects(self.injury_state, matching),
            self.condition_source_snapshots,
        )
        object.__setattr__(self, "condition_source_snapshots", snapshots)


@dataclass(frozen=True, slots=True)
class CombatSurgeonEffectiveEffectsResult:
    request_id: str
    rule_id: str
    source_request: CombatSurgeonEffectiveEffectsRequest
    target_id: str
    injury_state: CharacterInjuryState
    active_suppressions: tuple[CombatSurgeonEffectSuppression, ...]
    suppressed_effects: tuple[ActiveWoundEffect, ...]
    effective_wound_effects: tuple[ActiveWoundEffect, ...]
    ignored_conditions: tuple[Condition, ...]
    effective_conditions: ConditionState
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "effective-effects result request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "effective-effects result rule_id",
        )
        if not isinstance(
            self.source_request,
            CombatSurgeonEffectiveEffectsRequest,
        ):
            raise TypeError(
                "source_request must be an effective-effects request"
            )
        _validate_non_empty_string(self.target_id, "effective result target_id")
        if not isinstance(self.injury_state, CharacterInjuryState):
            raise TypeError("injury_state must be a CharacterInjuryState")
        active_suppressions = _validate_suppressions(
            self.active_suppressions,
        )
        suppressed_effects = _validate_effects(self.suppressed_effects)
        effective_effects = _validate_effects(self.effective_wound_effects)
        ignored_conditions = tuple(self.ignored_conditions)
        if not all(isinstance(item, Condition) for item in ignored_conditions):
            raise TypeError("ignored_conditions must contain Conditions")
        if len(set(ignored_conditions)) != len(ignored_conditions):
            raise ValueError("ignored_conditions must be unique")
        if not isinstance(self.effective_conditions, ConditionState):
            raise TypeError("effective_conditions must be a ConditionState")

        source = self.source_request
        expected = _expected_effective_view(source)
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.target_id != source.target_id
            or self.injury_state != source.injury_state
            or active_suppressions != expected[0]
            or suppressed_effects != expected[1]
            or effective_effects != expected[2]
            or ignored_conditions != expected[3]
            or self.effective_conditions != expected[4]
        ):
            raise ValueError("effective-effects result has stale provenance")
        object.__setattr__(self, "active_suppressions", active_suppressions)
        object.__setattr__(self, "suppressed_effects", suppressed_effects)
        object.__setattr__(self, "effective_wound_effects", effective_effects)
        object.__setattr__(self, "ignored_conditions", ignored_conditions)

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {
            self.rule_id,
            *(item.rule_id for item in active_suppressions),
        }
        if not required <= set(rule_ids):
            raise ValueError("effective-effects trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


def _expected_effective_view(
    request: CombatSurgeonEffectiveEffectsRequest,
) -> tuple[
    tuple[CombatSurgeonEffectSuppression, ...],
    tuple[ActiveWoundEffect, ...],
    tuple[ActiveWoundEffect, ...],
    tuple[Condition, ...],
    ConditionState,
]:
    matching = tuple(
        item
        for item in request.aggregate.suppressions
        if item.target_id == request.target_id
    )
    active_suppressions = tuple(
        item
        for item in matching
        if not request.injury_state.wounds[item.wound_sequence - 1].healed
    )
    suppressed = _active_suppressed_effects(
        request.injury_state,
        active_suppressions,
    )
    effective_effects = tuple(
        effect
        for effect in request.injury_state.active_wound_effects
        if effect not in suppressed
    )
    snapshot_by_condition = {
        item.condition: item
        for item in request.condition_source_snapshots
    }
    ignored_conditions: list[Condition] = []
    for effect in suppressed:
        if not isinstance(effect, WoundConditionEffect):
            continue
        snapshot = snapshot_by_condition.get(effect.condition)
        if (
            snapshot is not None
            and not snapshot.has_other_active_source
            and effect.condition not in ignored_conditions
        ):
            ignored_conditions.append(effect.condition)
    effective_conditions = request.injury_state.conditions
    for condition in ignored_conditions:
        effective_conditions = effective_conditions.without_condition(condition)
    return (
        active_suppressions,
        suppressed,
        effective_effects,
        tuple(ignored_conditions),
        effective_conditions,
    )


def _validate_suppression_context(
    state: CharacterInjuryState,
    suppressions: tuple[CombatSurgeonEffectSuppression, ...],
) -> None:
    wounds = {item.sequence: item for item in state.wounds}
    for suppression in suppressions:
        current = wounds.get(suppression.wound_sequence)
        if current is None:
            raise ValueError("suppression references an unknown Wound")
        if _wound_identity(current) != _wound_identity(suppression.wound):
            raise ValueError("suppression belongs to another Wound identity")
        if current.healed:
            continue
        if not current.treated or not current.effect_resolved:
            raise ValueError(
                "suppression requires a treated, active, resolved Wound"
            )
        current_effects = tuple(
            effect
            for effect in state.active_wound_effects
            if effect.wound_sequence == suppression.wound_sequence
            and effect.duration is WoundEffectDuration.UNTIL_HEALED
        )
        if current_effects != suppression.suppressed_effects:
            raise ValueError("suppression uses a stale Wound effect set")


def _active_suppressed_effects(
    state: CharacterInjuryState,
    suppressions: tuple[CombatSurgeonEffectSuppression, ...],
) -> tuple[ActiveWoundEffect, ...]:
    suppressed = {
        effect
        for suppression in suppressions
        if not state.wounds[suppression.wound_sequence - 1].healed
        for effect in suppression.suppressed_effects
    }
    return tuple(
        effect
        for effect in state.active_wound_effects
        if effect in suppressed
    )


def _validate_condition_source_snapshots(
    state: CharacterInjuryState,
    suppressed: tuple[ActiveWoundEffect, ...],
    values: tuple[WoundConditionSourceSnapshot, ...],
) -> tuple[WoundConditionSourceSnapshot, ...]:
    snapshots = tuple(values)
    if not all(
        isinstance(item, WoundConditionSourceSnapshot)
        for item in snapshots
    ):
        raise TypeError(
            "condition_source_snapshots must contain source snapshots"
        )
    if len({item.condition for item in snapshots}) != len(snapshots):
        raise ValueError("Condition source snapshots must be unique")
    affected = {
        item.condition
        for item in suppressed
        if isinstance(item, WoundConditionEffect)
        and state.conditions.has(item.condition)
    }
    if {item.condition for item in snapshots} != affected:
        raise ValueError(
            "Condition source snapshots must match suppressed active Conditions"
        )
    remaining_conditions = {
        item.condition
        for item in state.active_wound_effects
        if item not in suppressed
        and isinstance(item, WoundConditionEffect)
    }
    if any(
        not item.has_other_active_source
        and item.condition in remaining_conditions
        for item in snapshots
    ):
        raise ValueError(
            "another active Wound effect is a known Condition source"
        )
    return snapshots


def _wound_identity(wound: WoundRecord) -> tuple[object, ...]:
    return (
        wound.sequence,
        wound.entry_id,
        wound.table_total,
        wound.roll_values,
        wound.origin,
    )


def _validate_suppressions(
    values: tuple[CombatSurgeonEffectSuppression, ...],
) -> tuple[CombatSurgeonEffectSuppression, ...]:
    suppressions = tuple(values)
    if not all(
        isinstance(item, CombatSurgeonEffectSuppression)
        for item in suppressions
    ):
        raise TypeError("active_suppressions must contain suppressions")
    return suppressions


def _validate_effects(
    values: tuple[ActiveWoundEffect, ...],
) -> tuple[ActiveWoundEffect, ...]:
    effects = tuple(values)
    if not all(
        isinstance(item, (WoundConditionEffect, WoundRestrictionEffect))
        for item in effects
    ):
        raise TypeError("Wound effects must contain active Wound effects")
    return effects


def _validate_rule_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    rule_ids = tuple(values)
    if not rule_ids:
        raise ValueError("applied_rule_ids must not be empty")
    for value in rule_ids:
        _validate_non_empty_string(value, "applied Rule ID")
    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError("applied_rule_ids must be unique")
    return rule_ids


def _validate_unique(values, name: str) -> None:
    items = tuple(values)
    if len(set(items)) != len(items):
        raise ValueError(f"{name} must be unique")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
