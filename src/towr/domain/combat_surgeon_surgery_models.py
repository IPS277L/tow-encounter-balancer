from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.combat_surgeon_models import COMBAT_SURGEON_RULE_ID
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.exacting_test_models import (
    EXACTING_TEST_RULE_ID,
    ExactingTestContributionRequest,
    ExactingTestContributionResult,
    ExactingTestProgress,
)
from towr.domain.injury_models import CharacterInjuryState
from towr.domain.surgery_models import (
    SURGERY_FAILURE_RISK_RULE_ID,
    SurgeryFailureRiskRequest,
)
from towr.domain.test_models import Skill, TestRequest
from towr.domain.turn_models import (
    ActionExecutionReceipt,
    CombatActionKind,
    CombatActionSlot,
    CombatRoundState,
    ImproviseKind,
)


COMBAT_SURGEON_BATTLE_SURGERY_RULE_ID = (
    "RULE-TALENT-002:combat-surgeon-battle-surgery"
)
COMBAT_SURGEON_BATTLE_SURGERY_REQUIRED_SUCCESSES = 8


@dataclass(frozen=True, slots=True)
class CombatSurgeonBattleSurgeryProgress:
    id: str
    battle_id: str
    surgeon_id: str
    target_id: str
    injury_state: CharacterInjuryState
    wound_sequence: int
    exacting: ExactingTestProgress
    rule_id: str = COMBAT_SURGEON_BATTLE_SURGERY_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "battle surgery progress id")
        _validate_non_empty_string(self.battle_id, "battle surgery battle_id")
        _validate_non_empty_string(self.surgeon_id, "battle surgery surgeon_id")
        _validate_non_empty_string(self.target_id, "battle surgery target_id")
        if not isinstance(self.injury_state, CharacterInjuryState):
            raise TypeError("injury_state must be a CharacterInjuryState")
        _validate_positive_int(self.wound_sequence, "wound_sequence")
        if not isinstance(self.exacting, ExactingTestProgress):
            raise TypeError("exacting must be an ExactingTestProgress")
        _validate_non_empty_string(self.rule_id, "battle surgery progress rule_id")
        if self.exacting.id != f"{self.id}:exacting":
            raise ValueError("battle surgery Exacting progress has another ID")
        if (
            self.exacting.rule_id != EXACTING_TEST_RULE_ID
            or self.exacting.required_successes
            != COMBAT_SURGEON_BATTLE_SURGERY_REQUIRED_SUCCESSES
        ):
            raise ValueError("battle surgery requires Exacting progress of 8")
        if any(
            item.contributor_id != self.surgeon_id
            for item in self.exacting.contributions
        ):
            raise ValueError("another character contributed to battle surgery")
        _validate_surgery_wound(self.injury_state, self.wound_sequence)

    @property
    def completed(self) -> bool:
        return self.exacting.completed


@dataclass(frozen=True, slots=True)
class CombatSurgeonBattleSurgeryProof:
    id: str
    surgery_id: str
    final_action_request_id: str
    source_exacting_progress_id: str
    battle_id: str
    surgeon_id: str
    target_id: str
    injury_state: CharacterInjuryState
    wound_sequence: int
    accumulated_successes: int
    required_successes: int = (
        COMBAT_SURGEON_BATTLE_SURGERY_REQUIRED_SUCCESSES
    )
    rule_id: str = COMBAT_SURGEON_BATTLE_SURGERY_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "battle surgery proof id")
        _validate_non_empty_string(self.surgery_id, "proof surgery_id")
        _validate_non_empty_string(
            self.final_action_request_id,
            "proof final_action_request_id",
        )
        _validate_non_empty_string(
            self.source_exacting_progress_id,
            "proof source_exacting_progress_id",
        )
        _validate_non_empty_string(self.battle_id, "proof battle_id")
        _validate_non_empty_string(self.surgeon_id, "proof surgeon_id")
        _validate_non_empty_string(self.target_id, "proof target_id")
        if not isinstance(self.injury_state, CharacterInjuryState):
            raise TypeError("proof injury_state must be a CharacterInjuryState")
        _validate_positive_int(self.wound_sequence, "proof wound_sequence")
        _validate_non_negative_int(
            self.accumulated_successes,
            "proof accumulated_successes",
        )
        _validate_positive_int(self.required_successes, "required_successes")
        if (
            self.required_successes
            != COMBAT_SURGEON_BATTLE_SURGERY_REQUIRED_SUCCESSES
            or self.accumulated_successes < self.required_successes
        ):
            raise ValueError("battle surgery proof requires at least 8 successes")
        _validate_non_empty_string(self.rule_id, "battle surgery proof rule_id")
        _validate_surgery_wound(self.injury_state, self.wound_sequence)


@dataclass(frozen=True, slots=True)
class CombatSurgeonBattleSurgeryActionRequest:
    id: str
    surgery_id: str
    battle_id: str
    round_state: CombatRoundState
    surgeon_id: str
    surgeon_conditions: ConditionState
    surgeon_talent_rule_ids: tuple[str, ...]
    slot_index: int
    target_id: str
    target_in_close_range: bool | None
    injury_state: CharacterInjuryState
    wound_sequence: int
    dexterity_test: TestRequest
    has_specialist_medical_tools: bool
    has_recovery_supports: bool
    progress: CombatSurgeonBattleSurgeryProgress | None = None
    skill: Skill = Skill.DEXTERITY
    rule_id: str = COMBAT_SURGEON_BATTLE_SURGERY_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "battle surgery action id")
        _validate_non_empty_string(self.surgery_id, "surgery_id")
        _validate_non_empty_string(self.battle_id, "battle_id")
        if not isinstance(self.round_state, CombatRoundState):
            raise TypeError("round_state must be a CombatRoundState")
        _validate_non_empty_string(self.surgeon_id, "surgeon_id")
        if not isinstance(self.surgeon_conditions, ConditionState):
            raise TypeError("surgeon_conditions must be a ConditionState")
        talent_ids = _validate_rule_ids(self.surgeon_talent_rule_ids)
        object.__setattr__(self, "surgeon_talent_rule_ids", talent_ids)
        _validate_slot_index(self.slot_index)
        _validate_non_empty_string(self.target_id, "surgery target_id")
        if self.target_in_close_range is not None:
            _validate_bool(
                self.target_in_close_range,
                "target_in_close_range",
            )
        if not isinstance(self.injury_state, CharacterInjuryState):
            raise TypeError("injury_state must be a CharacterInjuryState")
        _validate_positive_int(self.wound_sequence, "wound_sequence")
        if not isinstance(self.dexterity_test, TestRequest):
            raise TypeError("dexterity_test must be a TestRequest")
        _validate_bool(
            self.has_specialist_medical_tools,
            "has_specialist_medical_tools",
        )
        _validate_bool(
            self.has_recovery_supports,
            "has_recovery_supports",
        )
        if self.progress is not None and not isinstance(
            self.progress,
            CombatSurgeonBattleSurgeryProgress,
        ):
            raise TypeError("progress must be battle surgery progress or None")
        if not isinstance(self.skill, Skill):
            raise TypeError("skill must be a Skill")
        _validate_non_empty_string(self.rule_id, "battle surgery action rule_id")

        turn = self.round_state.active_turn
        if turn is None or turn.actor_id != self.surgeon_id:
            raise ValueError("battle surgery requires the surgeon's active turn")
        surgeon = self.round_state.participant_for(self.surgeon_id)
        target = self.round_state.participant_for(self.target_id)
        if target.side is not surgeon.side:
            raise ValueError("battle surgery target must be an ally")
        if self.target_id == self.surgeon_id:
            if self.target_in_close_range is not None:
                raise ValueError("self surgery has no Close Range fact")
        elif self.target_in_close_range is not True:
            raise ValueError("battle surgery ally must be in Close Range")
        if self.skill is not Skill.DEXTERITY:
            raise ValueError("battle surgery requires a Dexterity Test")
        if COMBAT_SURGEON_RULE_ID not in talent_ids:
            raise ValueError("the surgeon does not have Combat Surgeon")
        if self.surgeon_conditions.has(Condition.DEFENCELESS):
            raise ValueError("Defenceless characters cannot take actions")
        if not self.has_specialist_medical_tools:
            raise ValueError("battle surgery requires specialist medical tools")
        if not self.has_recovery_supports:
            raise ValueError("battle surgery requires recovery supports")
        _validate_surgery_wound(self.injury_state, self.wound_sequence)

        if self.progress is not None:
            if (
                self.progress.id != self.surgery_id
                or self.progress.battle_id != self.battle_id
                or self.progress.surgeon_id != self.surgeon_id
                or self.progress.target_id != self.target_id
                or self.progress.injury_state != self.injury_state
                or self.progress.wound_sequence != self.wound_sequence
                or self.progress.rule_id != self.rule_id
            ):
                raise ValueError("battle surgery uses stale progress context")
            if self.progress.completed:
                raise ValueError("completed battle surgery needs no more actions")
            if self.dexterity_test.id in {
                item.test_id for item in self.progress.exacting.contributions
            }:
                raise ValueError("battle surgery Test was already consumed")


@dataclass(frozen=True, slots=True)
class CombatSurgeonBattleSurgeryActionResult:
    request_id: str
    rule_id: str
    source_request: CombatSurgeonBattleSurgeryActionRequest
    exacting: ExactingTestContributionResult
    previous_progress: CombatSurgeonBattleSurgeryProgress
    progress: CombatSurgeonBattleSurgeryProgress
    proof: CombatSurgeonBattleSurgeryProof | None
    failure_risk: SurgeryFailureRiskRequest | None
    previous_state: CharacterInjuryState
    state: CharacterInjuryState
    previous_round_state: CombatRoundState
    round_state: CombatRoundState
    slot: CombatActionSlot
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "battle surgery result id")
        _validate_non_empty_string(self.rule_id, "battle surgery result rule_id")
        if not isinstance(
            self.source_request,
            CombatSurgeonBattleSurgeryActionRequest,
        ):
            raise TypeError("source_request must be a battle surgery request")
        if not isinstance(self.exacting, ExactingTestContributionResult):
            raise TypeError("exacting must be an Exacting contribution result")
        if not isinstance(
            self.previous_progress,
            CombatSurgeonBattleSurgeryProgress,
        ):
            raise TypeError("previous_progress must be battle surgery progress")
        if not isinstance(self.progress, CombatSurgeonBattleSurgeryProgress):
            raise TypeError("progress must be battle surgery progress")
        if self.proof is not None and not isinstance(
            self.proof,
            CombatSurgeonBattleSurgeryProof,
        ):
            raise TypeError("proof must be a battle surgery proof or None")
        if self.failure_risk is not None and not isinstance(
            self.failure_risk,
            SurgeryFailureRiskRequest,
        ):
            raise TypeError("failure_risk must be a surgery risk request or None")
        if not isinstance(self.previous_state, CharacterInjuryState):
            raise TypeError("previous_state must be a CharacterInjuryState")
        if not isinstance(self.state, CharacterInjuryState):
            raise TypeError("state must be a CharacterInjuryState")
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
            or self.previous_state != source.injury_state
            or self.state != source.injury_state
            or self.previous_round_state != source.round_state
        ):
            raise ValueError("battle surgery result has stale provenance")
        _validate_battle_surgery_context(source)
        expected_previous = _source_progress(source)
        if self.previous_progress != expected_previous:
            raise ValueError("battle surgery result has stale progress")
        expected_exacting_request = _exacting_request(source, expected_previous)
        if self.exacting.source_request != expected_exacting_request:
            raise ValueError("battle surgery Exacting result is inconsistent")
        expected_progress = replace(
            expected_previous,
            exacting=self.exacting.progress,
        )
        if self.progress != expected_progress:
            raise ValueError("battle surgery changed unrelated progress")
        if self.proof != _expected_proof(source, expected_progress):
            raise ValueError("battle surgery proof is inconsistent")
        if self.failure_risk != _expected_failure_risk(source, self.exacting):
            raise ValueError("battle surgery failure risk is inconsistent")
        self._validate_round_transition()

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {
            self.rule_id,
            COMBAT_SURGEON_RULE_ID,
            *self.exacting.applied_rule_ids,
        }
        if self.failure_risk is not None:
            required.add(self.failure_risk.rule_id)
        if not required <= set(rule_ids):
            raise ValueError("battle surgery trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)

    @property
    def completed(self) -> bool:
        return self.proof is not None

    def _validate_round_transition(self) -> None:
        source = self.source_request
        previous_turn = self.previous_round_state.active_turn
        current_turn = self.round_state.active_turn
        if previous_turn is None or current_turn is None:
            raise ValueError("battle surgery requires an active turn")
        previous_slot = previous_turn.action_slots[source.slot_index - 1]
        if previous_slot.executed or not self.slot.executed:
            raise ValueError("battle surgery must execute one unexecuted slot")
        receipt = self.slot.execution
        assert isinstance(receipt, ActionExecutionReceipt)
        if (
            receipt.id != source.id
            or receipt.executor_rule_id != source.rule_id
            or receipt.source_request_id != source.id
            or receipt.result_request_id != self.exacting.request_id
            or receipt.actor_id != source.surgeon_id
            or receipt.round_number != source.round_state.round_number
            or receipt.slot_index != source.slot_index
            or receipt.declaration != previous_slot.declaration
        ):
            raise ValueError("battle surgery receipt has stale provenance")
        if self.slot != replace(previous_slot, execution=receipt):
            raise ValueError("battle surgery may only add its receipt")
        expected_slots = tuple(
            self.slot if item.index == source.slot_index else item
            for item in previous_turn.action_slots
        )
        if current_turn != replace(previous_turn, action_slots=expected_slots):
            raise ValueError("battle surgery changed unrelated turn state")
        if self.round_state != replace(
            self.previous_round_state,
            active_turn=current_turn,
        ):
            raise ValueError("battle surgery changed unrelated round state")


def _validate_battle_surgery_context(
    request: CombatSurgeonBattleSurgeryActionRequest,
) -> None:
    if request.rule_id != COMBAT_SURGEON_BATTLE_SURGERY_RULE_ID:
        raise ValueError("battle surgery uses an unknown source rule")
    turn = request.round_state.active_turn
    assert turn is not None
    if request.slot_index > len(turn.action_slots):
        raise ValueError("the requested action slot has not been reserved")
    if any(
        not slot.executed
        for slot in turn.action_slots[: request.slot_index - 1]
    ):
        raise ValueError("earlier action slots must be executed first")
    slot = turn.action_slots[request.slot_index - 1]
    declaration = slot.declaration
    if (
        declaration.kind is not CombatActionKind.IMPROVISE
        or declaration.improvise_kind is not ImproviseKind.ABILITY
    ):
        raise ValueError("only an Ability Improvise can use battle surgery")
    if declaration.improvise_approach_id != COMBAT_SURGEON_RULE_ID:
        raise ValueError("Combat Surgeon must match the action slot")
    if declaration.improvise_produces_attack:
        raise ValueError("battle surgery is not an Attack")
    if slot.executed:
        raise ValueError("the battle surgery slot has already been executed")


def _source_progress(
    request: CombatSurgeonBattleSurgeryActionRequest,
) -> CombatSurgeonBattleSurgeryProgress:
    if request.progress is not None:
        return request.progress
    return CombatSurgeonBattleSurgeryProgress(
        id=request.surgery_id,
        battle_id=request.battle_id,
        surgeon_id=request.surgeon_id,
        target_id=request.target_id,
        injury_state=request.injury_state,
        wound_sequence=request.wound_sequence,
        exacting=ExactingTestProgress(
            id=f"{request.surgery_id}:exacting",
            required_successes=(
                COMBAT_SURGEON_BATTLE_SURGERY_REQUIRED_SUCCESSES
            ),
        ),
        rule_id=request.rule_id,
    )


def _exacting_request(
    request: CombatSurgeonBattleSurgeryActionRequest,
    progress: CombatSurgeonBattleSurgeryProgress,
) -> ExactingTestContributionRequest:
    return ExactingTestContributionRequest(
        id=f"{request.id}:exacting",
        progress=progress.exacting,
        contributor_id=request.surgeon_id,
        test=request.dexterity_test,
    )


def _expected_proof(
    request: CombatSurgeonBattleSurgeryActionRequest,
    progress: CombatSurgeonBattleSurgeryProgress,
) -> CombatSurgeonBattleSurgeryProof | None:
    if not progress.completed:
        return None
    return CombatSurgeonBattleSurgeryProof(
        id=f"{request.surgery_id}:proof",
        surgery_id=request.surgery_id,
        final_action_request_id=request.id,
        source_exacting_progress_id=progress.exacting.id,
        battle_id=request.battle_id,
        surgeon_id=request.surgeon_id,
        target_id=request.target_id,
        injury_state=request.injury_state,
        wound_sequence=request.wound_sequence,
        accumulated_successes=progress.exacting.accumulated_successes,
        rule_id=request.rule_id,
    )


def _expected_failure_risk(
    request: CombatSurgeonBattleSurgeryActionRequest,
    exacting: ExactingTestContributionResult,
) -> SurgeryFailureRiskRequest | None:
    if exacting.contribution.successes > 0:
        return None
    return SurgeryFailureRiskRequest(
        id=f"{request.id}:failure-risk",
        source_surgery_id=request.id,
        source_test_id=request.dexterity_test.id,
        surgeon_id=request.surgeon_id,
        target_id=request.target_id,
        wound_sequence=request.wound_sequence,
        rule_id=SURGERY_FAILURE_RISK_RULE_ID,
    )


def _validate_surgery_wound(
    state: CharacterInjuryState,
    wound_sequence: int,
) -> None:
    if state.dead:
        raise ValueError("a dead character cannot undergo battle surgery")
    wounds = {wound.sequence: wound for wound in state.wounds}
    if wound_sequence not in wounds:
        raise ValueError("battle surgery references an unknown Wound")
    wound = wounds[wound_sequence]
    if wound.healed:
        raise ValueError("battle surgery requires an unhealed Wound")
    if not wound.treated:
        raise ValueError("battle surgery requires a treated Wound")
    if not wound.effect_resolved:
        raise ValueError("battle surgery requires a resolved Wound effect")


def _validate_rule_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    rule_ids = tuple(values)
    for value in rule_ids:
        _validate_non_empty_string(value, "Rule ID")
    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError("Rule IDs must be unique")
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


def _validate_non_negative_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must not be negative")


def _validate_slot_index(value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("slot_index must be an integer")
    if value not in (1, 2):
        raise ValueError("slot_index must be 1 or 2")


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")
