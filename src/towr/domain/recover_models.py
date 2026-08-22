from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import (
    ActiveWoundEffect,
    CharacterInjuryState,
    WoundConditionEffect,
    WoundEffectDuration,
    WoundRestrictionEffect,
)
from towr.domain.magic_models import WizardMagicState
from towr.domain.test_models import Skill, TestRequest, TestResult
from towr.domain.turn_models import (
    ActionExecutionReceipt,
    CombatActionKind,
    CombatActionSlot,
    CombatRoundState,
)


RECOVER_ACTION_RULE_ID = "RULE-COMBAT-004:recover-action-execution"
RECOVER_TREAT_WOUND_RULE_ID = "RULE-HEALTH-005:recover-treatment"
RECOVER_TREAT_WOUND_APPLICATION_RULE_ID = (
    "RULE-HEALTH-005:treatment-application"
)
RECOVER_CONDITION_RULE_ID = "RULE-HEALTH-007:recover-condition-removal"


class RecoverMode(str, Enum):
    STANDARD = "standard"
    TREAT_WOUND = "treat_wound"
    REMOVE_CONDITION = "remove_condition"


@dataclass(frozen=True, slots=True)
class RecoverConditionTarget:
    entity_id: str
    conditions: ConditionState
    in_close_range: bool | None

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.entity_id, "Recover target entity_id")
        if not isinstance(self.conditions, ConditionState):
            raise TypeError("conditions must be a ConditionState")
        if self.in_close_range is not None and not isinstance(
            self.in_close_range,
            bool,
        ):
            raise TypeError("in_close_range must be a boolean or None")


@dataclass(frozen=True, slots=True)
class RecoverMountFollowUp:
    id: str
    actor_id: str
    mount_id: str
    mount_in_close_range: bool
    actor_already_mounted: bool = False
    rule_id: str = RECOVER_ACTION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Recover mount follow-up id")
        _validate_non_empty_string(self.actor_id, "mount actor_id")
        _validate_non_empty_string(self.mount_id, "mount_id")
        _validate_bool(self.mount_in_close_range, "mount_in_close_range")
        _validate_bool(self.actor_already_mounted, "actor_already_mounted")
        _validate_non_empty_string(self.rule_id, "mount follow-up rule_id")


@dataclass(frozen=True, slots=True)
class RecoverObjectInteractionFollowUp:
    id: str
    actor_id: str
    object_id: str
    object_in_close_range: bool
    rule_id: str = RECOVER_ACTION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Recover object follow-up id")
        _validate_non_empty_string(self.actor_id, "object actor_id")
        _validate_non_empty_string(self.object_id, "object_id")
        _validate_bool(self.object_in_close_range, "object_in_close_range")
        _validate_non_empty_string(self.rule_id, "object follow-up rule_id")


@dataclass(frozen=True, slots=True)
class RecoverStandardChoice:
    magic_state: WizardMagicState
    staggered_target: RecoverConditionTarget | None = None
    prone_target: RecoverConditionTarget | None = None
    mount: RecoverMountFollowUp | None = None
    object_interaction: RecoverObjectInteractionFollowUp | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.magic_state, WizardMagicState):
            raise TypeError("magic_state must be a WizardMagicState")
        if self.staggered_target is not None and not isinstance(
            self.staggered_target,
            RecoverConditionTarget,
        ):
            raise TypeError("staggered_target must be a Recover target or None")
        if self.prone_target is not None and not isinstance(
            self.prone_target,
            RecoverConditionTarget,
        ):
            raise TypeError("prone_target must be a Recover target or None")
        if self.mount is not None and not isinstance(
            self.mount,
            RecoverMountFollowUp,
        ):
            raise TypeError("mount must be a RecoverMountFollowUp or None")
        if self.object_interaction is not None and not isinstance(
            self.object_interaction,
            RecoverObjectInteractionFollowUp,
        ):
            raise TypeError(
                "object_interaction must be a Recover object follow-up or None"
            )
        if self.prone_target is not None and self.mount is not None:
            raise ValueError("Recover cannot remove Prone and mount a steed")
        if (
            self.staggered_target is not None
            and self.prone_target is not None
            and self.staggered_target.entity_id == self.prone_target.entity_id
            and self.staggered_target != self.prone_target
        ):
            raise ValueError("one Recover target must use one Condition snapshot")


@dataclass(frozen=True, slots=True)
class RecoverTreatWoundChoice:
    target: RecoverConditionTarget
    injury_state: CharacterInjuryState
    wound_sequence: int
    has_required_trappings: bool
    recall_test: TestRequest | None = None
    automatic_lore_id: str | None = None
    recall_skill: Skill = Skill.RECALL
    rule_id: str = RECOVER_TREAT_WOUND_RULE_ID

    def __post_init__(self) -> None:
        if not isinstance(self.target, RecoverConditionTarget):
            raise TypeError("target must be a RecoverConditionTarget")
        if not isinstance(self.injury_state, CharacterInjuryState):
            raise TypeError("injury_state must be a CharacterInjuryState")
        _validate_positive_int(self.wound_sequence, "wound_sequence")
        _validate_bool(self.has_required_trappings, "has_required_trappings")
        if self.recall_test is not None and not isinstance(
            self.recall_test,
            TestRequest,
        ):
            raise TypeError("recall_test must be a TestRequest or None")
        if self.automatic_lore_id is not None:
            _validate_non_empty_string(self.automatic_lore_id, "automatic_lore_id")
        if (self.recall_test is None) == (self.automatic_lore_id is None):
            raise ValueError("treatment requires exactly one Test or automatic Lore")
        if not isinstance(self.recall_skill, Skill):
            raise TypeError("recall_skill must be a Skill")
        if self.recall_skill is not Skill.RECALL:
            raise ValueError("Wound treatment must use Recall")
        if self.target.conditions != self.injury_state.conditions:
            raise ValueError("treatment target and injury Conditions must match")
        matching = tuple(
            wound
            for wound in self.injury_state.wounds
            if wound.sequence == self.wound_sequence
        )
        if not matching:
            raise ValueError("treatment references an unknown Wound")
        if matching[0].treated:
            raise ValueError("the selected Wound is already treated")
        _validate_non_empty_string(self.rule_id, "treatment rule_id")


@dataclass(frozen=True, slots=True)
class RecoverConditionRemovalChoice:
    target: RecoverConditionTarget
    condition: Condition
    test: TestRequest
    test_skill: Skill
    underlying_cause_allows_removal: bool
    rule_id: str = RECOVER_CONDITION_RULE_ID

    def __post_init__(self) -> None:
        if not isinstance(self.target, RecoverConditionTarget):
            raise TypeError("target must be a RecoverConditionTarget")
        if not isinstance(self.condition, Condition):
            raise TypeError("condition must be a Condition")
        if self.condition in (Condition.STAGGERED, Condition.PRONE):
            raise ValueError("Staggered and Prone use standard Recover")
        if not self.target.conditions.has(self.condition):
            raise ValueError("Recover target lacks the selected Condition")
        if not isinstance(self.test, TestRequest):
            raise TypeError("test must be a TestRequest")
        if not isinstance(self.test_skill, Skill):
            raise TypeError("test_skill must be a Skill")
        _validate_bool(
            self.underlying_cause_allows_removal,
            "underlying_cause_allows_removal",
        )
        _validate_non_empty_string(self.rule_id, "Condition removal rule_id")


RecoverChoice = (
    RecoverStandardChoice
    | RecoverTreatWoundChoice
    | RecoverConditionRemovalChoice
)


@dataclass(frozen=True, slots=True)
class RecoverActionExecutionRequest:
    id: str
    round_state: CombatRoundState
    actor_id: str
    actor_conditions: ConditionState
    actor_has_enemy_in_zone: bool
    slot_index: int
    mode: RecoverMode
    choice: RecoverChoice
    rule_id: str = RECOVER_ACTION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Recover request id")
        if not isinstance(self.round_state, CombatRoundState):
            raise TypeError("round_state must be a CombatRoundState")
        _validate_non_empty_string(self.actor_id, "Recover actor_id")
        if not isinstance(self.actor_conditions, ConditionState):
            raise TypeError("actor_conditions must be a ConditionState")
        _validate_bool(self.actor_has_enemy_in_zone, "actor_has_enemy_in_zone")
        _validate_slot_index(self.slot_index)
        if not isinstance(self.mode, RecoverMode):
            raise TypeError("mode must be a RecoverMode")
        expected_type = {
            RecoverMode.STANDARD: RecoverStandardChoice,
            RecoverMode.TREAT_WOUND: RecoverTreatWoundChoice,
            RecoverMode.REMOVE_CONDITION: RecoverConditionRemovalChoice,
        }[self.mode]
        if not isinstance(self.choice, expected_type):
            raise TypeError("Recover mode and choice do not match")
        _validate_non_empty_string(self.rule_id, "Recover rule_id")

        turn = self.round_state.active_turn
        if turn is None or turn.actor_id != self.actor_id:
            raise ValueError("Recover requires the actor's active turn")
        if isinstance(self.choice, RecoverStandardChoice):
            self._validate_standard(self.choice)
        elif isinstance(self.choice, RecoverTreatWoundChoice):
            self._validate_target(self.choice.target)
        else:
            self._validate_target(self.choice.target)

    def _validate_standard(self, choice: RecoverStandardChoice) -> None:
        for target, condition in (
            (choice.staggered_target, Condition.STAGGERED),
            (choice.prone_target, Condition.PRONE),
        ):
            if target is None:
                continue
            self._validate_target(target)
            if not target.conditions.has(condition):
                raise ValueError(f"Recover target lacks {condition.value}")
        if choice.mount is not None:
            if choice.mount.actor_id != self.actor_id:
                raise ValueError("mount follow-up belongs to another actor")
            if not choice.mount.mount_in_close_range:
                raise ValueError("Recover mount must be in Close Range")
            if choice.mount.actor_already_mounted:
                raise ValueError("an already mounted actor cannot mount again")
            if self.actor_conditions.has(Condition.PRONE):
                raise ValueError("a Prone actor cannot use Recover to mount")
        if choice.object_interaction is not None:
            interaction = choice.object_interaction
            if interaction.actor_id != self.actor_id:
                raise ValueError("object follow-up belongs to another actor")
            if not interaction.object_in_close_range:
                raise ValueError("Recover object must be in Close Range")

    def _validate_target(self, target: RecoverConditionTarget) -> None:
        actor = self.round_state.participant_for(self.actor_id)
        selected = self.round_state.participant_for(target.entity_id)
        if target.entity_id == self.actor_id:
            if target.in_close_range is not None:
                raise ValueError("self Recover target has no range fact")
            if target.conditions != self.actor_conditions:
                raise ValueError("self Recover target has stale Conditions")
            return
        if selected.side is not actor.side:
            raise ValueError("Recover target must be an ally")
        if target.in_close_range is not True:
            raise ValueError("Recover ally must be in Close Range")


@dataclass(frozen=True, slots=True)
class RecoverConditionChange:
    entity_id: str
    previous_conditions: ConditionState
    conditions: ConditionState
    removed_conditions: tuple[Condition, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.entity_id, "condition change entity_id")
        if not isinstance(self.previous_conditions, ConditionState):
            raise TypeError("previous_conditions must be a ConditionState")
        if not isinstance(self.conditions, ConditionState):
            raise TypeError("conditions must be a ConditionState")
        removed = tuple(self.removed_conditions)
        if not removed or not all(isinstance(item, Condition) for item in removed):
            raise ValueError("removed_conditions must contain Conditions")
        if len(set(removed)) != len(removed):
            raise ValueError("removed_conditions must be unique")
        expected = self.previous_conditions
        for condition in removed:
            if not expected.has(condition):
                raise ValueError("cannot remove an absent Condition")
            expected = expected.without_condition(condition)
        if self.conditions != expected:
            raise ValueError("Recover changed unrelated Conditions")
        object.__setattr__(self, "removed_conditions", removed)


@dataclass(frozen=True, slots=True)
class RecoverStandardResult:
    source: RecoverStandardChoice
    condition_changes: tuple[RecoverConditionChange, ...]
    previous_magic_state: WizardMagicState
    magic_state: WizardMagicState
    miscast_dice_removed: int
    mount_follow_up: RecoverMountFollowUp | None
    object_interaction_follow_up: RecoverObjectInteractionFollowUp | None

    def __post_init__(self) -> None:
        if not isinstance(self.source, RecoverStandardChoice):
            raise TypeError("source must be a RecoverStandardChoice")
        changes = tuple(self.condition_changes)
        if not all(isinstance(item, RecoverConditionChange) for item in changes):
            raise TypeError("condition_changes must contain Recover changes")
        if len({item.entity_id for item in changes}) != len(changes):
            raise ValueError("Recover condition target IDs must be unique")
        if changes != _expected_standard_changes(self.source):
            raise ValueError("Recover condition changes do not match its choices")
        object.__setattr__(self, "condition_changes", changes)
        if self.previous_magic_state != self.source.magic_state:
            raise ValueError("Recover uses stale previous magic state")
        expected_removed = min(1, self.previous_magic_state.miscast_dice)
        if self.miscast_dice_removed != expected_removed:
            raise ValueError("Recover removes at most one Miscast die")
        if self.magic_state != replace(
            self.previous_magic_state,
            miscast_dice=(
                self.previous_magic_state.miscast_dice - expected_removed
            ),
        ):
            raise ValueError("Recover changed unrelated magic state")
        if (
            self.mount_follow_up != self.source.mount
            or self.object_interaction_follow_up
            != self.source.object_interaction
        ):
            raise ValueError("Recover follow-up has stale provenance")


@dataclass(frozen=True, slots=True)
class RecoverWoundTreatmentApplicationRequest:
    id: str
    source_action_id: str
    actor_id: str
    target_id: str
    injury_state: CharacterInjuryState
    wound_sequence: int
    automatic_lore_id: str | None
    source_test_id: str | None
    rule_id: str = RECOVER_TREAT_WOUND_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "treatment application id")
        _validate_non_empty_string(self.source_action_id, "source_action_id")
        _validate_non_empty_string(self.actor_id, "treatment actor_id")
        _validate_non_empty_string(self.target_id, "treatment target_id")
        if not isinstance(self.injury_state, CharacterInjuryState):
            raise TypeError("injury_state must be a CharacterInjuryState")
        _validate_positive_int(self.wound_sequence, "wound_sequence")
        if self.automatic_lore_id is not None:
            _validate_non_empty_string(self.automatic_lore_id, "automatic_lore_id")
        if self.source_test_id is not None:
            _validate_non_empty_string(self.source_test_id, "source_test_id")
        if (self.automatic_lore_id is None) == (self.source_test_id is None):
            raise ValueError("treatment application requires one success source")
        matching = tuple(
            wound
            for wound in self.injury_state.wounds
            if wound.sequence == self.wound_sequence
        )
        if not matching:
            raise ValueError("treatment application references an unknown Wound")
        if matching[0].treated:
            raise ValueError("treatment application requires an untreated Wound")
        _validate_non_empty_string(self.rule_id, "treatment rule_id")


@dataclass(frozen=True, slots=True)
class RecoverTreatWoundResult:
    source: RecoverTreatWoundChoice
    test_result: TestResult | None
    automatically_succeeded: bool
    treatment: RecoverWoundTreatmentApplicationRequest | None

    def __post_init__(self) -> None:
        if not isinstance(self.source, RecoverTreatWoundChoice):
            raise TypeError("source must be a RecoverTreatWoundChoice")
        if self.test_result is not None and not isinstance(
            self.test_result,
            TestResult,
        ):
            raise TypeError("test_result must be a TestResult or None")
        _validate_bool(self.automatically_succeeded, "automatically_succeeded")
        if self.treatment is not None and not isinstance(
            self.treatment,
            RecoverWoundTreatmentApplicationRequest,
        ):
            raise TypeError("treatment must be a treatment request or None")
        automatic = self.source.automatic_lore_id is not None
        if self.automatically_succeeded != automatic:
            raise ValueError("treatment success source is inconsistent")
        if automatic:
            if self.test_result is not None:
                raise ValueError("automatic treatment must not roll a Test")
            succeeded = True
        else:
            if self.test_result is None:
                raise ValueError("non-automatic treatment requires a Test result")
            assert self.source.recall_test is not None
            if self.test_result.trace.request_id != self.source.recall_test.id:
                raise ValueError("treatment Test result has stale provenance")
            succeeded = self.test_result.succeeded
        if succeeded != (self.treatment is not None):
            raise ValueError("successful treatment requires an application request")


@dataclass(frozen=True, slots=True)
class RecoverConditionRemovalResult:
    source: RecoverConditionRemovalChoice
    test_result: TestResult
    previous_conditions: ConditionState
    conditions: ConditionState
    removed: bool

    def __post_init__(self) -> None:
        if not isinstance(self.source, RecoverConditionRemovalChoice):
            raise TypeError("source must be a RecoverConditionRemovalChoice")
        if not isinstance(self.test_result, TestResult):
            raise TypeError("test_result must be a TestResult")
        if not isinstance(self.previous_conditions, ConditionState):
            raise TypeError("previous_conditions must be a ConditionState")
        if not isinstance(self.conditions, ConditionState):
            raise TypeError("conditions must be a ConditionState")
        _validate_bool(self.removed, "removed")
        if self.test_result.trace.request_id != self.source.test.id:
            raise ValueError("Condition removal Test has stale provenance")
        if self.previous_conditions != self.source.target.conditions:
            raise ValueError("Condition removal uses stale Conditions")
        expected_removed = (
            self.test_result.succeeded
            and self.source.underlying_cause_allows_removal
        )
        if self.removed != expected_removed:
            raise ValueError("Condition removal outcome is inconsistent")
        expected = (
            self.previous_conditions.without_condition(self.source.condition)
            if expected_removed
            else self.previous_conditions
        )
        if self.conditions != expected:
            raise ValueError("Condition removal changed unrelated Conditions")


RecoverResolution = (
    RecoverStandardResult
    | RecoverTreatWoundResult
    | RecoverConditionRemovalResult
)


@dataclass(frozen=True, slots=True)
class RecoverActionExecutionResult:
    request_id: str
    rule_id: str
    source_request: RecoverActionExecutionRequest
    resolution: RecoverResolution
    previous_round_state: CombatRoundState
    round_state: CombatRoundState
    slot: CombatActionSlot
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Recover result request_id")
        _validate_non_empty_string(self.rule_id, "Recover result rule_id")
        if not isinstance(self.source_request, RecoverActionExecutionRequest):
            raise TypeError("source_request must be a Recover action request")
        if not isinstance(
            self.resolution,
            (
                RecoverStandardResult,
                RecoverTreatWoundResult,
                RecoverConditionRemovalResult,
            ),
        ):
            raise TypeError("resolution must be a Recover resolution")
        if not isinstance(self.previous_round_state, CombatRoundState):
            raise TypeError("previous_round_state must be a CombatRoundState")
        if not isinstance(self.round_state, CombatRoundState):
            raise TypeError("round_state must be a CombatRoundState")
        if not isinstance(self.slot, CombatActionSlot):
            raise TypeError("slot must be a CombatActionSlot")
        source = self.source_request
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.previous_round_state != source.round_state
            or self.resolution.source != source.choice
        ):
            raise ValueError("Recover result has stale provenance")
        expected_type = {
            RecoverMode.STANDARD: RecoverStandardResult,
            RecoverMode.TREAT_WOUND: RecoverTreatWoundResult,
            RecoverMode.REMOVE_CONDITION: RecoverConditionRemovalResult,
        }[source.mode]
        if not isinstance(self.resolution, expected_type):
            raise ValueError("Recover result does not match the selected mode")
        self._validate_resolution_provenance()
        self._validate_round_transition()
        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {self.rule_id}
        if isinstance(self.resolution, RecoverTreatWoundResult):
            required.add(self.resolution.source.rule_id)
            if self.resolution.test_result is not None:
                required.update(
                    self.resolution.test_result.trace.applied_rule_ids
                )
        elif isinstance(self.resolution, RecoverConditionRemovalResult):
            required.add(self.resolution.source.rule_id)
            required.update(self.resolution.test_result.trace.applied_rule_ids)
        if not required <= set(rule_ids):
            raise ValueError("Recover trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)

    def _validate_resolution_provenance(self) -> None:
        if not isinstance(self.resolution, RecoverTreatWoundResult):
            return
        treatment = self.resolution.treatment
        if treatment is None:
            return
        choice = self.resolution.source
        expected_test_id = (
            None
            if self.resolution.test_result is None
            else self.resolution.test_result.trace.request_id
        )
        if (
            treatment.id != f"{self.source_request.id}:treatment"
            or treatment.source_action_id != self.source_request.id
            or treatment.actor_id != self.source_request.actor_id
            or treatment.target_id != choice.target.entity_id
            or treatment.injury_state != choice.injury_state
            or treatment.wound_sequence != choice.wound_sequence
            or treatment.automatic_lore_id != choice.automatic_lore_id
            or treatment.source_test_id != expected_test_id
            or treatment.rule_id != choice.rule_id
        ):
            raise ValueError("treatment application has stale provenance")

    def _validate_round_transition(self) -> None:
        source = self.source_request
        previous_turn = self.previous_round_state.active_turn
        current_turn = self.round_state.active_turn
        if previous_turn is None or current_turn is None:
            raise ValueError("Recover requires an active turn")
        if source.slot_index > len(previous_turn.action_slots):
            raise ValueError("previous state lacks the Recover slot")
        if any(
            not item.executed
            for item in previous_turn.action_slots[: source.slot_index - 1]
        ):
            raise ValueError("earlier action slots must be executed first")
        previous_slot = previous_turn.action_slots[source.slot_index - 1]
        if previous_slot.declaration.kind is not CombatActionKind.RECOVER:
            raise ValueError("result requires a Recover slot")
        if previous_slot.executed or not self.slot.executed:
            raise ValueError("Recover must execute one unexecuted slot")
        receipt = self.slot.execution
        assert isinstance(receipt, ActionExecutionReceipt)
        expected_result_id = _resolution_result_id(source, self.resolution)
        if (
            receipt.id != source.id
            or receipt.executor_rule_id != source.rule_id
            or receipt.source_request_id != source.id
            or receipt.result_request_id != expected_result_id
        ):
            raise ValueError("Recover receipt has stale provenance")
        if self.slot != replace(previous_slot, execution=receipt):
            raise ValueError("Recover may only add its receipt")
        expected_slots = tuple(
            self.slot if item.index == source.slot_index else item
            for item in previous_turn.action_slots
        )
        if current_turn != replace(previous_turn, action_slots=expected_slots):
            raise ValueError("Recover changed unrelated turn state")
        if self.round_state != replace(
            self.previous_round_state,
            active_turn=current_turn,
        ):
            raise ValueError("Recover changed unrelated round state")


@dataclass(frozen=True, slots=True)
class RecoverWoundConditionSourceSnapshot:
    condition: Condition
    has_other_active_source: bool

    def __post_init__(self) -> None:
        if not isinstance(self.condition, Condition):
            raise TypeError("condition must be a Condition")
        _validate_bool(
            self.has_other_active_source,
            "has_other_active_source",
        )


@dataclass(frozen=True, slots=True)
class RecoverWoundTreatmentResolutionRequest:
    id: str
    recover: RecoverActionExecutionResult
    target_id: str
    injury_state: CharacterInjuryState
    condition_source_snapshots: tuple[
        RecoverWoundConditionSourceSnapshot, ...
    ] = ()
    consumed_application_ids: tuple[str, ...] = ()
    rule_id: str = RECOVER_TREAT_WOUND_APPLICATION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "treatment resolution id")
        if not isinstance(self.recover, RecoverActionExecutionResult):
            raise TypeError("recover must be a RecoverActionExecutionResult")
        _validate_non_empty_string(self.target_id, "treatment target_id")
        if not isinstance(self.injury_state, CharacterInjuryState):
            raise TypeError("injury_state must be a CharacterInjuryState")
        snapshots = tuple(self.condition_source_snapshots)
        if not all(
            isinstance(item, RecoverWoundConditionSourceSnapshot)
            for item in snapshots
        ):
            raise TypeError(
                "condition_source_snapshots must contain source snapshots"
            )
        if len({item.condition for item in snapshots}) != len(snapshots):
            raise ValueError("Condition source snapshots must be unique")
        object.__setattr__(self, "condition_source_snapshots", snapshots)
        consumed = _validate_consumed_ids(self.consumed_application_ids)
        object.__setattr__(self, "consumed_application_ids", consumed)
        _validate_non_empty_string(self.rule_id, "treatment resolution rule_id")

        resolution = self.recover.resolution
        if self.recover.rule_id != RECOVER_ACTION_RULE_ID:
            raise ValueError("treatment requires a canonical Recover action")
        if not isinstance(resolution, RecoverTreatWoundResult):
            raise ValueError("treatment requires a Treat Wound Recover result")
        treatment = resolution.treatment
        if treatment is None:
            raise ValueError("failed treatment has no application to resolve")
        if treatment.rule_id != RECOVER_TREAT_WOUND_RULE_ID:
            raise ValueError("treatment application uses an unknown source rule")
        if self.target_id != treatment.target_id:
            raise ValueError("injury state belongs to another treatment target")
        if self.injury_state != treatment.injury_state:
            raise ValueError("treatment uses stale injury state")
        if treatment.id in consumed:
            raise ValueError("treatment application was already consumed")

        removable = _removable_treatment_effects(
            self.injury_state,
            treatment.wound_sequence,
        )
        affected_conditions = {
            item.condition
            for item in removable
            if isinstance(item, WoundConditionEffect)
            and self.injury_state.conditions.has(item.condition)
        }
        if {item.condition for item in snapshots} != affected_conditions:
            raise ValueError(
                "Condition source snapshots must match removable active Conditions"
            )
        remaining = tuple(
            effect
            for effect in self.injury_state.active_wound_effects
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


@dataclass(frozen=True, slots=True)
class RecoverWoundTreatmentResolutionResult:
    request_id: str
    rule_id: str
    source_request: RecoverWoundTreatmentResolutionRequest
    target_id: str
    wound_sequence: int
    previous_state: CharacterInjuryState
    state: CharacterInjuryState
    removed_effects: tuple[ActiveWoundEffect, ...]
    removed_conditions: tuple[Condition, ...]
    previous_consumed_application_ids: tuple[str, ...]
    consumed_application_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "treatment result request_id")
        _validate_non_empty_string(self.rule_id, "treatment result rule_id")
        if not isinstance(
            self.source_request,
            RecoverWoundTreatmentResolutionRequest,
        ):
            raise TypeError(
                "source_request must be a treatment resolution request"
            )
        _validate_non_empty_string(self.target_id, "treatment target_id")
        _validate_positive_int(self.wound_sequence, "wound_sequence")
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
        treatment = source.recover.resolution.treatment
        assert treatment is not None
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.target_id != source.target_id
            or self.wound_sequence != treatment.wound_sequence
            or self.previous_state != source.injury_state
        ):
            raise ValueError("treatment result has stale provenance")
        expected_state, expected_effects, expected_conditions = (
            _expected_wound_treatment_transition(source)
        )
        if (
            self.state != expected_state
            or removed_effects != expected_effects
            or removed_conditions != expected_conditions
        ):
            raise ValueError("treatment result changed unrelated injury state")
        previous = _validate_consumed_ids(
            self.previous_consumed_application_ids
        )
        if previous != source.consumed_application_ids:
            raise ValueError("treatment result has a stale consumption chain")
        consumed = _validate_consumed_ids(self.consumed_application_ids)
        if consumed != (*previous, treatment.id):
            raise ValueError(
                "consumed application IDs must append the treatment application"
            )
        object.__setattr__(
            self,
            "previous_consumed_application_ids",
            previous,
        )
        object.__setattr__(self, "consumed_application_ids", consumed)
        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {
            self.rule_id,
            treatment.rule_id,
            *source.recover.applied_rule_ids,
        }
        if not required <= set(rule_ids):
            raise ValueError("treatment application trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


def _resolution_result_id(
    request: RecoverActionExecutionRequest,
    resolution: RecoverResolution,
) -> str:
    if isinstance(resolution, RecoverTreatWoundResult):
        if resolution.test_result is not None:
            return resolution.test_result.trace.request_id
    elif isinstance(resolution, RecoverConditionRemovalResult):
        return resolution.test_result.trace.request_id
    return request.id


def _removable_treatment_effects(
    state: CharacterInjuryState,
    wound_sequence: int,
) -> tuple[ActiveWoundEffect, ...]:
    return tuple(
        effect
        for effect in state.active_wound_effects
        if effect.wound_sequence == wound_sequence
        and effect.duration is WoundEffectDuration.UNTIL_TREATED
    )


def _expected_wound_treatment_transition(
    request: RecoverWoundTreatmentResolutionRequest,
) -> tuple[
    CharacterInjuryState,
    tuple[ActiveWoundEffect, ...],
    tuple[Condition, ...],
]:
    treatment = request.recover.resolution.treatment
    assert treatment is not None
    removed_effects = _removable_treatment_effects(
        request.injury_state,
        treatment.wound_sequence,
    )
    snapshot_by_condition = {
        item.condition: item for item in request.condition_source_snapshots
    }
    removed_conditions: list[Condition] = []
    for effect in removed_effects:
        if not isinstance(effect, WoundConditionEffect):
            continue
        snapshot = snapshot_by_condition.get(effect.condition)
        if (
            snapshot is not None
            and not snapshot.has_other_active_source
            and effect.condition not in removed_conditions
        ):
            removed_conditions.append(effect.condition)
    conditions = request.injury_state.conditions
    for condition in removed_conditions:
        conditions = conditions.without_condition(condition)
    state = replace(
        request.injury_state,
        wounds=tuple(
            replace(wound, treated=True)
            if wound.sequence == treatment.wound_sequence
            else wound
            for wound in request.injury_state.wounds
        ),
        conditions=conditions,
        active_wound_effects=tuple(
            effect
            for effect in request.injury_state.active_wound_effects
            if not (
                effect.wound_sequence == treatment.wound_sequence
                and effect.duration is WoundEffectDuration.UNTIL_TREATED
            )
        ),
    )
    return state, removed_effects, tuple(removed_conditions)


def _expected_standard_changes(
    choice: RecoverStandardChoice,
) -> tuple[RecoverConditionChange, ...]:
    changes: dict[str, tuple[ConditionState, list[Condition]]] = {}
    for target, condition in (
        (choice.staggered_target, Condition.STAGGERED),
        (choice.prone_target, Condition.PRONE),
    ):
        if target is None:
            continue
        if target.entity_id not in changes:
            changes[target.entity_id] = (target.conditions, [])
        changes[target.entity_id][1].append(condition)
    results = []
    for entity_id, (previous, removed) in changes.items():
        current = previous
        for condition in removed:
            current = current.without_condition(condition)
        results.append(
            RecoverConditionChange(
                entity_id=entity_id,
                previous_conditions=previous,
                conditions=current,
                removed_conditions=tuple(removed),
            )
        )
    return tuple(results)


def _validate_rule_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    rule_ids = tuple(values)
    if not rule_ids:
        raise ValueError("applied_rule_ids must not be empty")
    for rule_id in rule_ids:
        _validate_non_empty_string(rule_id, "applied Rule ID")
    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError("applied_rule_ids must be unique")
    return rule_ids


def _validate_consumed_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    consumed = tuple(values)
    for application_id in consumed:
        _validate_non_empty_string(
            application_id,
            "consumed treatment application id",
        )
    if len(set(consumed)) != len(consumed):
        raise ValueError("consumed treatment application IDs must be unique")
    return consumed


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")


def _validate_positive_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if value < 1:
        raise ValueError(f"{name} must be positive")


def _validate_slot_index(value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("slot_index must be an integer")
    if value not in (1, 2):
        raise ValueError("slot_index must be 1 or 2")
