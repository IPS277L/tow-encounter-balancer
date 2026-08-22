from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.test_models import DiceModifier, Skill, TestRequest, TestResult
from towr.domain.turn_models import (
    ActionExecutionReceipt,
    CombatActionDeclaration,
    CombatActionKind,
    CombatActionSlot,
    CombatRoundState,
)


AIM_ACTION_RULE_ID = "RULE-COMBAT-004:aim-action-execution"
AIM_FOLLOW_UP_RULE_ID = "RULE-COMBAT-004:aim-follow-up"


class AimFollowUpOutcome(str, Enum):
    APPLIED_TO_RANGED_ATTACK = "applied_to_ranged_attack"
    LOST = "lost"


@dataclass(frozen=True, slots=True)
class AimBonusSnapshot:
    id: str
    source_request_id: str
    source_test_id: str
    actor_id: str
    target_id: str
    bonus_dice: int
    extreme_range_requires_gm_approval: bool = True
    rule_id: str = AIM_ACTION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Aim bonus id")
        _validate_non_empty_string(
            self.source_request_id,
            "Aim bonus source_request_id",
        )
        _validate_non_empty_string(self.source_test_id, "Aim bonus source_test_id")
        _validate_non_empty_string(self.actor_id, "Aim bonus actor_id")
        _validate_non_empty_string(self.target_id, "Aim bonus target_id")
        if not isinstance(self.bonus_dice, int) or isinstance(
            self.bonus_dice,
            bool,
        ):
            raise TypeError("Aim bonus_dice must be an integer")
        if self.bonus_dice < 0:
            raise ValueError("Aim bonus_dice must not be negative")
        if self.extreme_range_requires_gm_approval is not True:
            raise ValueError("Extreme Range through Aim requires GM approval")
        _validate_non_empty_string(self.rule_id, "Aim bonus rule_id")


@dataclass(frozen=True, slots=True)
class AimActionExecutionRequest:
    id: str
    round_state: CombatRoundState
    actor_id: str
    target_id: str
    slot_index: int
    awareness_test: TestRequest
    awareness_skill: Skill = Skill.AWARENESS
    rule_id: str = AIM_ACTION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Aim request id")
        if not isinstance(self.round_state, CombatRoundState):
            raise TypeError("round_state must be a CombatRoundState")
        _validate_non_empty_string(self.actor_id, "Aim actor_id")
        _validate_non_empty_string(self.target_id, "Aim target_id")
        _validate_slot_index(self.slot_index)
        if not isinstance(self.awareness_test, TestRequest):
            raise TypeError("awareness_test must be a TestRequest")
        if not isinstance(self.awareness_skill, Skill):
            raise TypeError("awareness_skill must be a Skill")
        if self.awareness_skill is not Skill.AWARENESS:
            raise ValueError("Aim must use Awareness")
        _validate_non_empty_string(self.rule_id, "Aim rule_id")

        turn = self.round_state.active_turn
        if turn is None or turn.actor_id != self.actor_id:
            raise ValueError("Aim requires the actor's active turn")
        actor = self.round_state.participant_for(self.actor_id)
        target = self.round_state.participant_for(self.target_id)
        if actor.side is target.side:
            raise ValueError("Aim target must be an enemy")


@dataclass(frozen=True, slots=True)
class AimActionExecutionResult:
    request_id: str
    rule_id: str
    source_request: AimActionExecutionRequest
    awareness_test_result: TestResult
    bonus: AimBonusSnapshot
    previous_round_state: CombatRoundState
    round_state: CombatRoundState
    slot: CombatActionSlot
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Aim result request_id")
        _validate_non_empty_string(self.rule_id, "Aim result rule_id")
        if not isinstance(self.source_request, AimActionExecutionRequest):
            raise TypeError("source_request must be an AimActionExecutionRequest")
        if not isinstance(self.awareness_test_result, TestResult):
            raise TypeError("awareness_test_result must be a TestResult")
        if not isinstance(self.bonus, AimBonusSnapshot):
            raise TypeError("bonus must be an AimBonusSnapshot")
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
            or self.awareness_test_result.trace.request_id
            != source.awareness_test.id
        ):
            raise ValueError("Aim result has stale provenance")
        expected_bonus = AimBonusSnapshot(
            id=f"{source.id}:bonus",
            source_request_id=source.id,
            source_test_id=source.awareness_test.id,
            actor_id=source.actor_id,
            target_id=source.target_id,
            bonus_dice=self.awareness_test_result.successes,
            rule_id=source.rule_id,
        )
        if self.bonus != expected_bonus:
            raise ValueError("Aim bonus does not match the Awareness Test")
        self._validate_round_transition()

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        required = {
            self.rule_id,
            *self.awareness_test_result.trace.applied_rule_ids,
        }
        if not required <= set(rule_ids):
            raise ValueError("Aim trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)

    def _validate_round_transition(self) -> None:
        source = self.source_request
        previous_turn = self.previous_round_state.active_turn
        current_turn = self.round_state.active_turn
        if previous_turn is None or current_turn is None:
            raise ValueError("Aim requires an active turn")
        if source.slot_index > len(previous_turn.action_slots):
            raise ValueError("previous state lacks the Aim slot")
        if any(
            not item.executed
            for item in previous_turn.action_slots[: source.slot_index - 1]
        ):
            raise ValueError("earlier action slots must be executed first")
        previous_slot = previous_turn.action_slots[source.slot_index - 1]
        if previous_slot.declaration.kind is not CombatActionKind.AIM:
            raise ValueError("result requires an Aim slot")
        if previous_slot.executed or not self.slot.executed:
            raise ValueError("Aim must execute one unexecuted slot")
        receipt = self.slot.execution
        assert isinstance(receipt, ActionExecutionReceipt)
        if (
            receipt.id != source.id
            or receipt.executor_rule_id != source.rule_id
            or receipt.source_request_id != source.id
            or receipt.result_request_id != self.awareness_test_result.trace.request_id
        ):
            raise ValueError("Aim receipt has stale provenance")
        if self.slot != replace(previous_slot, execution=receipt):
            raise ValueError("Aim may only add its receipt")
        expected_slots = tuple(
            self.slot if item.index == source.slot_index else item
            for item in previous_turn.action_slots
        )
        if current_turn != replace(previous_turn, action_slots=expected_slots):
            raise ValueError("Aim changed unrelated turn state")
        if self.round_state != replace(
            self.previous_round_state,
            active_turn=current_turn,
        ):
            raise ValueError("Aim changed unrelated round state")


@dataclass(frozen=True, slots=True)
class AimFollowUpRequest:
    id: str
    aim: AimActionExecutionResult
    actor_id: str
    next_action_id: str
    declaration: CombatActionDeclaration
    attack_skill: Skill | None = None
    attack: AttackActionExecutionRequest | None = None
    rule_id: str = AIM_FOLLOW_UP_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Aim follow-up request id")
        if not isinstance(self.aim, AimActionExecutionResult):
            raise TypeError("aim must be an AimActionExecutionResult")
        _validate_non_empty_string(self.actor_id, "Aim follow-up actor_id")
        _validate_non_empty_string(self.next_action_id, "next_action_id")
        if not isinstance(self.declaration, CombatActionDeclaration):
            raise TypeError("declaration must be a CombatActionDeclaration")
        _validate_non_empty_string(self.rule_id, "Aim follow-up rule_id")
        if self.actor_id != self.aim.bonus.actor_id:
            raise ValueError("Aim follow-up belongs to another actor")
        if self.next_action_id == self.aim.request_id:
            raise ValueError("Aim cannot be its own follow-up action")

        if self.declaration.kind is CombatActionKind.ATTACK:
            if not isinstance(self.attack_skill, Skill):
                raise TypeError("Attack follow-up requires an attack Skill")
            if not isinstance(self.attack, AttackActionExecutionRequest):
                raise TypeError("Attack follow-up requires an Attack request")
            if (
                self.attack.id != self.next_action_id
                or self.attack.actor_id != self.actor_id
            ):
                raise ValueError("Attack follow-up has stale action provenance")
        elif self.attack_skill is not None or self.attack is not None:
            raise ValueError("only an Attack follow-up may include attack data")


@dataclass(frozen=True, slots=True)
class AimFollowUpResult:
    request_id: str
    rule_id: str
    source_request: AimFollowUpRequest
    outcome: AimFollowUpOutcome
    attack: AttackActionExecutionRequest | None
    modifier: DiceModifier | None
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Aim follow-up request_id")
        _validate_non_empty_string(self.rule_id, "Aim follow-up rule_id")
        if not isinstance(self.source_request, AimFollowUpRequest):
            raise TypeError("source_request must be an AimFollowUpRequest")
        if not isinstance(self.outcome, AimFollowUpOutcome):
            raise TypeError("outcome must be an AimFollowUpOutcome")
        if self.attack is not None and not isinstance(
            self.attack,
            AttackActionExecutionRequest,
        ):
            raise TypeError("attack must be an AttackActionExecutionRequest or None")
        if self.modifier is not None and not isinstance(self.modifier, DiceModifier):
            raise TypeError("modifier must be a DiceModifier or None")

        source = self.source_request
        if self.request_id != source.id or self.rule_id != source.rule_id:
            raise ValueError("Aim follow-up result has stale provenance")
        expected_outcome, expected_attack, expected_modifier = (
            _expected_follow_up(source)
        )
        if (
            self.outcome is not expected_outcome
            or self.attack != expected_attack
            or self.modifier != expected_modifier
        ):
            raise ValueError("Aim follow-up result is inconsistent")
        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        if {self.rule_id, source.aim.rule_id} - set(rule_ids):
            raise ValueError("Aim follow-up trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


def _expected_follow_up(
    request: AimFollowUpRequest,
) -> tuple[
    AimFollowUpOutcome,
    AttackActionExecutionRequest | None,
    DiceModifier | None,
]:
    attack = request.attack
    eligible = (
        request.declaration.kind is CombatActionKind.ATTACK
        and attack is not None
        and request.attack_skill in (Skill.SHOOTING, Skill.THROWING)
        and attack.target_id == request.aim.bonus.target_id
    )
    if not eligible:
        return AimFollowUpOutcome.LOST, attack, None
    if request.aim.bonus.bonus_dice == 0:
        return AimFollowUpOutcome.APPLIED_TO_RANGED_ATTACK, attack, None

    modifier = DiceModifier(
        rule_id=request.rule_id,
        amount=request.aim.bonus.bonus_dice,
    )
    attacker_test = attack.kernel_request.attack.attacker_test
    if any(
        item.rule_id == request.rule_id
        for item in attacker_test.dice_modifiers
    ):
        raise ValueError("Attack already contains this Aim bonus")
    prepared_test = replace(
        attacker_test,
        dice_modifiers=(*attacker_test.dice_modifiers, modifier),
    )
    prepared_attack = replace(
        attack,
        kernel_request=replace(
            attack.kernel_request,
            attack=replace(
                attack.kernel_request.attack,
                attacker_test=prepared_test,
            ),
        ),
    )
    return AimFollowUpOutcome.APPLIED_TO_RANGED_ATTACK, prepared_attack, modifier


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


def _validate_slot_index(value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("slot_index must be an integer")
    if value not in (1, 2):
        raise ValueError("slot_index must be 1 or 2")
