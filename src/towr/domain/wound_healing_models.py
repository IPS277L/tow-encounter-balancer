from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    ActiveWoundEffect,
    CharacterInjuryState,
    WoundConditionEffect,
    WoundConditionSourceSnapshot,
    WoundEffectDuration,
    WoundRestrictionEffect,
)
from towr.domain.recover_models import (
    END_BATTLE_WOUND_TREATMENT_RULE_ID,
    EndBattleWoundTreatmentResult,
)


CATCH_YOUR_BREATH_HEALING_RULE_ID = (
    "RULE-HEALTH-005:catch-your-breath-healing"
)


@dataclass(frozen=True, slots=True)
class CatchYourBreathHealingRequest:
    id: str
    treatment: EndBattleWoundTreatmentResult
    target_id: str
    injury_state: CharacterInjuryState
    wound_sequences: tuple[int, ...]
    condition_source_snapshots: tuple[
        WoundConditionSourceSnapshot, ...
    ] = ()
    consumed_source_ids: tuple[str, ...] = ()
    rule_id: str = CATCH_YOUR_BREATH_HEALING_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "healing request id")
        if not isinstance(self.treatment, EndBattleWoundTreatmentResult):
            raise TypeError(
                "treatment must be an end-battle treatment result"
            )
        _validate_non_empty_string(self.target_id, "healing target_id")
        if not isinstance(self.injury_state, CharacterInjuryState):
            raise TypeError("injury_state must be a CharacterInjuryState")
        sequences = _validate_wound_sequences(self.wound_sequences)
        object.__setattr__(self, "wound_sequences", sequences)
        consumed = _validate_consumed_ids(self.consumed_source_ids)
        object.__setattr__(self, "consumed_source_ids", consumed)
        _validate_non_empty_string(self.rule_id, "healing rule_id")

        if self.treatment.rule_id != END_BATTLE_WOUND_TREATMENT_RULE_ID:
            raise ValueError("healing requires canonical end-battle treatment")
        if self.target_id != self.treatment.target_id:
            raise ValueError("injury state belongs to another healing target")
        if self.injury_state != self.treatment.state:
            raise ValueError("healing uses stale post-treatment injury state")
        if self.injury_state.dead:
            raise ValueError("a dead character cannot heal Wounds")
        if self.treatment.request_id in consumed:
            raise ValueError("end-battle treatment was already consumed")

        wounds_by_sequence = {
            wound.sequence: wound for wound in self.injury_state.wounds
        }
        if any(sequence not in wounds_by_sequence for sequence in sequences):
            raise ValueError("healing references an unknown Wound")
        selected = tuple(wounds_by_sequence[item] for item in sequences)
        if any(wound.healed for wound in selected):
            raise ValueError("healing requires Wounds that are not healed")
        if any(not wound.treated for wound in selected):
            raise ValueError("healing requires treated Wounds")
        if any(not wound.effect_resolved for wound in selected):
            raise ValueError("healing requires resolved Wound effects")
        snapshots = _validate_condition_source_snapshots(
            self.injury_state,
            sequences,
            self.condition_source_snapshots,
        )
        object.__setattr__(self, "condition_source_snapshots", snapshots)


@dataclass(frozen=True, slots=True)
class CatchYourBreathHealingResult:
    request_id: str
    rule_id: str
    source_request: CatchYourBreathHealingRequest
    target_id: str
    healed_wound_sequences: tuple[int, ...]
    previous_state: CharacterInjuryState
    state: CharacterInjuryState
    removed_effects: tuple[ActiveWoundEffect, ...]
    removed_conditions: tuple[Condition, ...]
    previous_consumed_source_ids: tuple[str, ...]
    consumed_source_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "healing result request_id")
        _validate_non_empty_string(self.rule_id, "healing result rule_id")
        if not isinstance(
            self.source_request,
            CatchYourBreathHealingRequest,
        ):
            raise TypeError("source_request must be a healing request")
        _validate_non_empty_string(self.target_id, "healing target_id")
        sequences = _validate_wound_sequences(self.healed_wound_sequences)
        object.__setattr__(self, "healed_wound_sequences", sequences)
        if not isinstance(self.previous_state, CharacterInjuryState):
            raise TypeError("previous_state must be a CharacterInjuryState")
        if not isinstance(self.state, CharacterInjuryState):
            raise TypeError("state must be a CharacterInjuryState")
        removed_effects = tuple(self.removed_effects)
        if not all(
            isinstance(item, (WoundConditionEffect, WoundRestrictionEffect))
            for item in removed_effects
        ):
            raise TypeError("removed_effects must contain active Wound effects")
        object.__setattr__(self, "removed_effects", removed_effects)
        removed_conditions = tuple(self.removed_conditions)
        if not all(isinstance(item, Condition) for item in removed_conditions):
            raise TypeError("removed_conditions must contain Conditions")
        if len(set(removed_conditions)) != len(removed_conditions):
            raise ValueError("removed_conditions must be unique")
        object.__setattr__(self, "removed_conditions", removed_conditions)

        source = self.source_request
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.target_id != source.target_id
            or sequences != source.wound_sequences
            or self.previous_state != source.injury_state
        ):
            raise ValueError("healing result has stale provenance")
        expected_state, expected_effects, expected_conditions = (
            expected_catch_your_breath_transition(source)
        )
        if (
            self.state != expected_state
            or removed_effects != expected_effects
            or removed_conditions != expected_conditions
        ):
            raise ValueError("healing result changed unrelated injury state")

        previous = _validate_consumed_ids(
            self.previous_consumed_source_ids
        )
        if previous != source.consumed_source_ids:
            raise ValueError("healing result has a stale consumption chain")
        consumed = _validate_consumed_ids(self.consumed_source_ids)
        if consumed != (*previous, source.treatment.request_id):
            raise ValueError(
                "consumed source IDs must append the treatment result"
            )
        object.__setattr__(self, "previous_consumed_source_ids", previous)
        object.__setattr__(self, "consumed_source_ids", consumed)

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {
            self.rule_id,
            *source.treatment.applied_rule_ids,
        }
        if not required <= set(rule_ids):
            raise ValueError("healing trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


def expected_catch_your_breath_transition(
    request: CatchYourBreathHealingRequest,
) -> tuple[
    CharacterInjuryState,
    tuple[ActiveWoundEffect, ...],
    tuple[Condition, ...],
]:
    selected = set(request.wound_sequences)
    removed_effects = _removable_healing_effects(
        request.injury_state,
        request.wound_sequences,
    )
    snapshots = {
        item.condition: item
        for item in request.condition_source_snapshots
    }
    removed_conditions: list[Condition] = []
    for effect in removed_effects:
        if not isinstance(effect, WoundConditionEffect):
            continue
        snapshot = snapshots.get(effect.condition)
        if (
            snapshot is not None
            and not snapshot.has_other_active_source
            and effect.condition not in removed_conditions
        ):
            removed_conditions.append(effect.condition)
    conditions = request.injury_state.conditions
    for condition in removed_conditions:
        conditions = conditions.without_condition(condition)
    return (
        replace(
            request.injury_state,
            wounds=tuple(
                replace(wound, healed=True)
                if wound.sequence in selected
                else wound
                for wound in request.injury_state.wounds
            ),
            conditions=conditions,
            active_wound_effects=tuple(
                effect
                for effect in request.injury_state.active_wound_effects
                if effect not in removed_effects
            ),
        ),
        removed_effects,
        tuple(removed_conditions),
    )


def _removable_healing_effects(
    state: CharacterInjuryState,
    wound_sequences: tuple[int, ...],
) -> tuple[ActiveWoundEffect, ...]:
    selected = set(wound_sequences)
    return tuple(
        effect
        for effect in state.active_wound_effects
        if effect.wound_sequence in selected
        and effect.duration is not WoundEffectDuration.PERMANENT
    )


def _validate_condition_source_snapshots(
    state: CharacterInjuryState,
    wound_sequences: tuple[int, ...],
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
    removable = _removable_healing_effects(state, wound_sequences)
    affected_conditions = {
        item.condition
        for item in removable
        if isinstance(item, WoundConditionEffect)
        and state.conditions.has(item.condition)
    }
    if {item.condition for item in snapshots} != affected_conditions:
        raise ValueError(
            "Condition source snapshots must match removable active Conditions"
        )
    remaining = tuple(
        effect
        for effect in state.active_wound_effects
        if effect not in removable
    )
    remaining_conditions = {
        item.condition
        for item in remaining
        if isinstance(item, WoundConditionEffect)
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


def _validate_wound_sequences(values: tuple[int, ...]) -> tuple[int, ...]:
    sequences = tuple(values)
    if not sequences or any(
        not isinstance(item, int) or isinstance(item, bool) or item < 1
        for item in sequences
    ):
        raise ValueError("wound_sequences must be positive integers")
    if len(set(sequences)) != len(sequences):
        raise ValueError("wound_sequences must be unique")
    return sequences


def _validate_consumed_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    consumed = tuple(values)
    for source_id in consumed:
        _validate_non_empty_string(source_id, "consumed healing source id")
    if len(set(consumed)) != len(consumed):
        raise ValueError("consumed healing source IDs must be unique")
    return consumed


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
