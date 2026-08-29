from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.condition_models import Condition
from towr.domain.downtime_models import (
    REST_AND_RECOVERY_ENDEAVOUR_RULE_ID,
    RestAndRecoveryEndeavourResult,
)
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
from towr.domain.surgery_models import (
    DOWNTIME_SURGERY_RULE_ID,
    DowntimeSurgeryResult,
)


CATCH_YOUR_BREATH_HEALING_RULE_ID = (
    "RULE-HEALTH-005:catch-your-breath-healing"
)
END_ENCOUNTER_HEALING_OPPORTUNITY_RULE_ID = (
    "RULE-HEALTH-005:end-encounter-healing-opportunity"
)
NIGHTS_RESPITE_HEALING_RULE_ID = (
    "RULE-HEALTH-005:nights-respite-healing"
)
NIGHTS_RESPITE_HEALING_OPPORTUNITY_RULE_ID = (
    "RULE-HEALTH-005:nights-respite-healing-opportunity"
)
REST_AND_RECOVERY_HEALING_RULE_ID = (
    "RULE-HEALTH-005:rest-and-recovery-healing"
)


@dataclass(frozen=True, slots=True)
class EndEncounterHealingOpportunity:
    id: str
    encounter_id: str
    target_id: str
    injury_state: CharacterInjuryState
    encounter_has_ended: bool
    immediate_danger_has_passed: bool
    treatment: EndBattleWoundTreatmentResult | None = None
    rule_id: str = END_ENCOUNTER_HEALING_OPPORTUNITY_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "healing opportunity id")
        _validate_non_empty_string(self.encounter_id, "encounter_id")
        _validate_non_empty_string(self.target_id, "healing target_id")
        if not isinstance(self.injury_state, CharacterInjuryState):
            raise TypeError("injury_state must be a CharacterInjuryState")
        _validate_bool(self.encounter_has_ended, "encounter_has_ended")
        _validate_bool(
            self.immediate_danger_has_passed,
            "immediate_danger_has_passed",
        )
        if self.treatment is not None and not isinstance(
            self.treatment,
            EndBattleWoundTreatmentResult,
        ):
            raise TypeError(
                "treatment must be an end-battle treatment result or None"
            )
        _validate_non_empty_string(
            self.rule_id,
            "healing opportunity rule_id",
        )

        if not self.encounter_has_ended:
            raise ValueError("healing requires a completed encounter")
        if not self.immediate_danger_has_passed:
            raise ValueError("healing requires the immediate danger to pass")
        if self.injury_state.dead:
            raise ValueError("a dead character cannot receive healing")
        if self.treatment is not None:
            if self.treatment.rule_id != END_BATTLE_WOUND_TREATMENT_RULE_ID:
                raise ValueError(
                    "healing opportunity requires canonical treatment"
                )
            if self.target_id != self.treatment.target_id:
                raise ValueError(
                    "treatment belongs to another healing target"
                )
            if self.injury_state != self.treatment.state:
                raise ValueError(
                    "healing opportunity uses stale post-treatment state"
                )
            if (
                self.encounter_id
                != self.treatment.source_request.context.battle_id
            ):
                raise ValueError(
                    "healing opportunity belongs to another encounter"
                )


@dataclass(frozen=True, slots=True)
class NightsRespiteHealingOpportunity:
    id: str
    rest_id: str
    target_id: str
    injury_state: CharacterInjuryState
    took_it_easy: bool
    early_night_completed: bool
    morning_has_arrived: bool
    rule_id: str = NIGHTS_RESPITE_HEALING_OPPORTUNITY_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "night's respite opportunity id")
        _validate_non_empty_string(self.rest_id, "rest_id")
        _validate_non_empty_string(self.target_id, "healing target_id")
        if not isinstance(self.injury_state, CharacterInjuryState):
            raise TypeError("injury_state must be a CharacterInjuryState")
        _validate_bool(self.took_it_easy, "took_it_easy")
        _validate_bool(
            self.early_night_completed,
            "early_night_completed",
        )
        _validate_bool(self.morning_has_arrived, "morning_has_arrived")
        _validate_non_empty_string(
            self.rule_id,
            "night's respite opportunity rule_id",
        )

        if not self.took_it_easy:
            raise ValueError("night's respite requires taking it easy")
        if not self.early_night_completed:
            raise ValueError("night's respite requires a completed early night")
        if not self.morning_has_arrived:
            raise ValueError("night's respite resolves in the morning")
        if self.injury_state.dead:
            raise ValueError("a dead character cannot receive healing")


@dataclass(frozen=True, slots=True)
class CatchYourBreathHealingRequest:
    id: str
    opportunity: EndEncounterHealingOpportunity
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
        if not isinstance(
            self.opportunity,
            EndEncounterHealingOpportunity,
        ):
            raise TypeError("opportunity must be a healing opportunity")
        _validate_non_empty_string(self.target_id, "healing target_id")
        if not isinstance(self.injury_state, CharacterInjuryState):
            raise TypeError("injury_state must be a CharacterInjuryState")
        sequences = _validate_wound_sequences(self.wound_sequences)
        object.__setattr__(self, "wound_sequences", sequences)
        consumed = _validate_consumed_ids(self.consumed_source_ids)
        object.__setattr__(self, "consumed_source_ids", consumed)
        _validate_non_empty_string(self.rule_id, "healing rule_id")

        if (
            self.opportunity.rule_id
            != END_ENCOUNTER_HEALING_OPPORTUNITY_RULE_ID
        ):
            raise ValueError("healing requires a canonical opportunity")
        if self.target_id != self.opportunity.target_id:
            raise ValueError("injury state belongs to another healing target")
        if self.injury_state != self.opportunity.injury_state:
            raise ValueError("healing uses a stale opportunity injury state")
        if self.injury_state.dead:
            raise ValueError("a dead character cannot heal Wounds")
        if self.opportunity.id in consumed:
            raise ValueError("healing opportunity was already consumed")

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
        if consumed != (*previous, source.opportunity.id):
            raise ValueError(
                "consumed source IDs must append the healing opportunity"
            )
        object.__setattr__(self, "previous_consumed_source_ids", previous)
        object.__setattr__(self, "consumed_source_ids", consumed)

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {
            self.rule_id,
            source.opportunity.rule_id,
        }
        if source.opportunity.treatment is not None:
            required.update(
                source.opportunity.treatment.applied_rule_ids
            )
        if not required <= set(rule_ids):
            raise ValueError("healing trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


@dataclass(frozen=True, slots=True)
class NightsRespiteHealingRequest:
    id: str
    opportunity: NightsRespiteHealingOpportunity
    target_id: str
    injury_state: CharacterInjuryState
    wound_sequences: tuple[int, ...]
    condition_source_snapshots: tuple[
        WoundConditionSourceSnapshot, ...
    ] = ()
    consumed_source_ids: tuple[str, ...] = ()
    rule_id: str = NIGHTS_RESPITE_HEALING_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "night's respite request id")
        if not isinstance(
            self.opportunity,
            NightsRespiteHealingOpportunity,
        ):
            raise TypeError(
                "opportunity must be a night's respite opportunity"
            )
        _validate_non_empty_string(self.target_id, "healing target_id")
        if not isinstance(self.injury_state, CharacterInjuryState):
            raise TypeError("injury_state must be a CharacterInjuryState")
        sequences = _validate_wound_sequences(self.wound_sequences)
        object.__setattr__(self, "wound_sequences", sequences)
        consumed = _validate_consumed_ids(self.consumed_source_ids)
        object.__setattr__(self, "consumed_source_ids", consumed)
        _validate_non_empty_string(self.rule_id, "night's respite rule_id")

        if (
            self.opportunity.rule_id
            != NIGHTS_RESPITE_HEALING_OPPORTUNITY_RULE_ID
        ):
            raise ValueError("healing requires a canonical night's respite")
        if self.target_id != self.opportunity.target_id:
            raise ValueError("injury state belongs to another healing target")
        if self.injury_state != self.opportunity.injury_state:
            raise ValueError("healing uses a stale night's respite state")
        if self.injury_state.dead:
            raise ValueError("a dead character cannot heal Wounds")
        if self.opportunity.id in consumed:
            raise ValueError("night's respite opportunity was already consumed")

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
class NightsRespiteHealingResult:
    request_id: str
    rule_id: str
    source_request: NightsRespiteHealingRequest
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
        _validate_non_empty_string(
            self.request_id,
            "night's respite result request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "night's respite result rule_id",
        )
        if not isinstance(
            self.source_request,
            NightsRespiteHealingRequest,
        ):
            raise TypeError("source_request must be a night's respite request")
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
            raise ValueError("night's respite result has stale provenance")
        expected_state, expected_effects, expected_conditions = (
            expected_wound_healing_transition(
                source.injury_state,
                source.wound_sequences,
                source.condition_source_snapshots,
            )
        )
        if (
            self.state != expected_state
            or removed_effects != expected_effects
            or removed_conditions != expected_conditions
        ):
            raise ValueError(
                "night's respite changed unrelated injury state"
            )

        previous = _validate_consumed_ids(
            self.previous_consumed_source_ids
        )
        if previous != source.consumed_source_ids:
            raise ValueError(
                "night's respite result has a stale consumption chain"
            )
        consumed = _validate_consumed_ids(self.consumed_source_ids)
        if consumed != (*previous, source.opportunity.id):
            raise ValueError(
                "consumed source IDs must append the night's respite"
            )
        object.__setattr__(self, "previous_consumed_source_ids", previous)
        object.__setattr__(self, "consumed_source_ids", consumed)

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {
            self.rule_id,
            source.opportunity.rule_id,
        }
        if not required <= set(rule_ids):
            raise ValueError("night's respite trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


@dataclass(frozen=True, slots=True)
class RestAndRecoveryHealingRequest:
    id: str
    endeavour: RestAndRecoveryEndeavourResult
    target_id: str
    injury_state: CharacterInjuryState
    wound_sequence: int
    surgery: DowntimeSurgeryResult | None = None
    condition_source_snapshots: tuple[
        WoundConditionSourceSnapshot, ...
    ] = ()
    consumed_source_ids: tuple[str, ...] = ()
    rule_id: str = REST_AND_RECOVERY_HEALING_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.id,
            "Rest and Recovery healing request id",
        )
        if not isinstance(
            self.endeavour,
            RestAndRecoveryEndeavourResult,
        ):
            raise TypeError(
                "endeavour must be a Rest and Recovery result"
            )
        _validate_non_empty_string(self.target_id, "healing target_id")
        if not isinstance(self.injury_state, CharacterInjuryState):
            raise TypeError("injury_state must be a CharacterInjuryState")
        sequences = _validate_wound_sequences((self.wound_sequence,))
        if self.surgery is not None and not isinstance(
            self.surgery,
            DowntimeSurgeryResult,
        ):
            raise TypeError("surgery must be a downtime surgery result or None")
        consumed = _validate_consumed_ids(self.consumed_source_ids)
        object.__setattr__(self, "consumed_source_ids", consumed)
        _validate_non_empty_string(
            self.rule_id,
            "Rest and Recovery healing rule_id",
        )

        source = self.endeavour.source_request
        if (
            self.endeavour.rule_id
            != REST_AND_RECOVERY_ENDEAVOUR_RULE_ID
        ):
            raise ValueError("healing requires a canonical Endeavour")
        if not self.endeavour.succeeded:
            raise ValueError("healing requires a successful Endeavour")
        if self.target_id != source.target_id:
            raise ValueError("injury state belongs to another healing target")
        if self.injury_state != source.injury_state:
            raise ValueError("healing uses a stale Endeavour injury state")
        if self.injury_state.dead:
            raise ValueError("a dead character cannot heal Wounds")
        if self.endeavour.request_id in consumed:
            raise ValueError("Rest and Recovery was already consumed")

        surgery = self.surgery
        if surgery is not None:
            surgery_source = surgery.source_request
            if surgery.rule_id != DOWNTIME_SURGERY_RULE_ID:
                raise ValueError("healing requires canonical surgery")
            if not surgery.succeeded:
                raise ValueError("healing requires successful surgery")
            if surgery_source.target_id != self.target_id:
                raise ValueError("surgery belongs to another healing target")
            if surgery.state != self.injury_state:
                raise ValueError("healing uses a stale surgery injury state")
            if surgery_source.downtime_id != source.downtime_id:
                raise ValueError("surgery belongs to another downtime")
            if surgery_source.wound_sequence != self.wound_sequence:
                raise ValueError("surgery belongs to another Wound")
            if surgery.request_id in consumed:
                raise ValueError("surgery proof was already consumed")

        wounds_by_sequence = {
            wound.sequence: wound for wound in self.injury_state.wounds
        }
        if self.wound_sequence not in wounds_by_sequence:
            raise ValueError("healing references an unknown Wound")
        selected = wounds_by_sequence[self.wound_sequence]
        if selected.healed:
            raise ValueError("healing requires a Wound that is not healed")
        if not selected.treated:
            raise ValueError("healing requires a treated Wound")
        if not selected.effect_resolved:
            raise ValueError("healing requires a resolved Wound effect")
        snapshots = _validate_condition_source_snapshots(
            self.injury_state,
            sequences,
            self.condition_source_snapshots,
        )
        object.__setattr__(self, "condition_source_snapshots", snapshots)


@dataclass(frozen=True, slots=True)
class RestAndRecoveryHealingResult:
    request_id: str
    rule_id: str
    source_request: RestAndRecoveryHealingRequest
    target_id: str
    healed_wound_sequence: int
    previous_state: CharacterInjuryState
    state: CharacterInjuryState
    removed_effects: tuple[ActiveWoundEffect, ...]
    removed_conditions: tuple[Condition, ...]
    previous_consumed_source_ids: tuple[str, ...]
    consumed_source_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Rest and Recovery result request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "Rest and Recovery result rule_id",
        )
        if not isinstance(
            self.source_request,
            RestAndRecoveryHealingRequest,
        ):
            raise TypeError(
                "source_request must be a Rest and Recovery healing request"
            )
        _validate_wound_sequences((self.healed_wound_sequence,))
        _validate_non_empty_string(self.target_id, "healing target_id")
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
            or self.healed_wound_sequence != source.wound_sequence
            or self.previous_state != source.injury_state
        ):
            raise ValueError("Rest and Recovery result has stale provenance")
        expected_state, expected_effects, expected_conditions = (
            expected_wound_healing_transition(
                source.injury_state,
                (source.wound_sequence,),
                source.condition_source_snapshots,
            )
        )
        if (
            self.state != expected_state
            or removed_effects != expected_effects
            or removed_conditions != expected_conditions
        ):
            raise ValueError(
                "Rest and Recovery changed unrelated injury state"
            )

        previous = _validate_consumed_ids(
            self.previous_consumed_source_ids
        )
        if previous != source.consumed_source_ids:
            raise ValueError(
                "Rest and Recovery result has a stale consumption chain"
            )
        consumed = _validate_consumed_ids(self.consumed_source_ids)
        expected_consumed = (
            *previous,
            *((source.surgery.request_id,) if source.surgery else ()),
            source.endeavour.request_id,
        )
        if consumed != expected_consumed:
            raise ValueError(
                "consumed source IDs must append surgery and Endeavour sources"
            )
        object.__setattr__(self, "previous_consumed_source_ids", previous)
        object.__setattr__(self, "consumed_source_ids", consumed)

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {
            self.rule_id,
            *source.endeavour.applied_rule_ids,
        }
        if source.surgery is not None:
            required.update(source.surgery.applied_rule_ids)
        if not required <= set(rule_ids):
            raise ValueError("Rest and Recovery trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


def expected_catch_your_breath_transition(
    request: CatchYourBreathHealingRequest,
) -> tuple[
    CharacterInjuryState,
    tuple[ActiveWoundEffect, ...],
    tuple[Condition, ...],
]:
    return expected_wound_healing_transition(
        request.injury_state,
        request.wound_sequences,
        request.condition_source_snapshots,
    )


def expected_wound_healing_transition(
    state: CharacterInjuryState,
    wound_sequences: tuple[int, ...],
    condition_source_snapshots: tuple[
        WoundConditionSourceSnapshot, ...
    ],
) -> tuple[
    CharacterInjuryState,
    tuple[ActiveWoundEffect, ...],
    tuple[Condition, ...],
]:
    selected = set(wound_sequences)
    removed_effects = _removable_healing_effects(
        state,
        wound_sequences,
    )
    snapshots = {
        item.condition: item
        for item in condition_source_snapshots
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
    conditions = state.conditions
    for condition in removed_conditions:
        conditions = conditions.without_condition(condition)
    return (
        replace(
            state,
            wounds=tuple(
                replace(wound, healed=True)
                if wound.sequence in selected
                else wound
                for wound in state.wounds
            ),
            conditions=conditions,
            active_wound_effects=tuple(
                effect
                for effect in state.active_wound_effects
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


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")
