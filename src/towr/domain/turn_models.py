from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CombatSide(str, Enum):
    PLAYERS_AND_ALLIES = "players_and_allies"
    OPPOSITION = "opposition"


class CombatActionKind(str, Enum):
    AIM = "aim"
    ATTACK = "attack"
    HELP = "help"
    IMPROVISE = "improvise"
    MANOEUVRE = "manoeuvre"
    RECOVER = "recover"


class ManoeuvreKind(str, Enum):
    RUN = "run"
    CHARGE = "charge"
    MOVE_QUIETLY = "move_quietly"
    MOVE_CAREFULLY = "move_carefully"


class ImproviseKind(str, Enum):
    SKILL = "skill"
    SPELL = "spell"
    ABILITY = "ability"


class ActionSlotGrant(str, Enum):
    STANDARD = "standard"
    FATE = "fate"
    ABILITY = "ability"


@dataclass(frozen=True, slots=True)
class ActionExecutionReceipt:
    id: str
    executor_rule_id: str
    source_request_id: str
    result_request_id: str

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "action execution id")
        _validate_non_empty_string(
            self.executor_rule_id,
            "action execution Rule ID",
        )
        _validate_non_empty_string(
            self.source_request_id,
            "action execution source request id",
        )
        _validate_non_empty_string(
            self.result_request_id,
            "action execution result request id",
        )


@dataclass(frozen=True, slots=True)
class CombatActionDeclaration:
    kind: CombatActionKind
    manoeuvre: ManoeuvreKind | None = None
    improvise_kind: ImproviseKind | None = None
    improvise_approach_id: str | None = None
    improvise_produces_attack: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.kind, CombatActionKind):
            raise TypeError("kind must be a CombatActionKind")
        if self.kind is CombatActionKind.MANOEUVRE:
            if not isinstance(self.manoeuvre, ManoeuvreKind):
                raise TypeError("Manoeuvre action requires a ManoeuvreKind")
        elif self.manoeuvre is not None:
            raise ValueError("only a Manoeuvre action may name a manoeuvre")

        if self.kind is CombatActionKind.IMPROVISE:
            if not isinstance(self.improvise_kind, ImproviseKind):
                raise TypeError("Improvise action requires an ImproviseKind")
            if self.improvise_approach_id is None:
                raise ValueError("Improvise action requires an approach ID")
            _validate_non_empty_string(
                self.improvise_approach_id,
                "improvise_approach_id",
            )
        elif (
            self.improvise_kind is not None
            or self.improvise_approach_id is not None
        ):
            raise ValueError("only Improvise may name a kind or approach ID")

        if not isinstance(self.improvise_produces_attack, bool):
            raise TypeError("improvise_produces_attack must be a boolean")
        if (
            self.kind is not CombatActionKind.IMPROVISE
            and self.improvise_produces_attack
        ):
            raise ValueError(
                "only Improvise may explicitly produce an attack"
            )

    @property
    def produces_attack(self) -> bool:
        return (
            self.kind is CombatActionKind.ATTACK
            or (
                self.kind is CombatActionKind.MANOEUVRE
                and self.manoeuvre is ManoeuvreKind.CHARGE
            )
            or self.improvise_produces_attack
        )


@dataclass(frozen=True, slots=True)
class CombatTurnParticipant:
    entity_id: str
    side: CombatSide

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.entity_id, "turn participant entity_id")
        if not isinstance(self.side, CombatSide):
            raise TypeError("side must be a CombatSide")


@dataclass(frozen=True, slots=True)
class CombatActionSlot:
    index: int
    declaration: CombatActionDeclaration
    grant: ActionSlotGrant
    grant_rule_id: str | None = None
    execution: ActionExecutionReceipt | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.index, int) or isinstance(self.index, bool):
            raise TypeError("action slot index must be an integer")
        if self.index not in (1, 2):
            raise ValueError("action slot index must be 1 or 2")
        if not isinstance(self.declaration, CombatActionDeclaration):
            raise TypeError("declaration must be a CombatActionDeclaration")
        if not isinstance(self.grant, ActionSlotGrant):
            raise TypeError("grant must be an ActionSlotGrant")
        if self.grant is ActionSlotGrant.ABILITY:
            if self.grant_rule_id is None:
                raise ValueError("Ability action grant requires a Rule ID")
            _validate_non_empty_string(self.grant_rule_id, "grant_rule_id")
        elif self.grant_rule_id is not None:
            raise ValueError("only an Ability action grant may name a Rule ID")
        if self.execution is not None and not isinstance(
            self.execution,
            ActionExecutionReceipt,
        ):
            raise TypeError("execution must be an ActionExecutionReceipt")

    @property
    def executed(self) -> bool:
        return self.execution is not None


@dataclass(frozen=True, slots=True)
class CombatTurnState:
    actor_id: str
    side: CombatSide
    action_slots: tuple[CombatActionSlot, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.actor_id, "turn actor_id")
        if not isinstance(self.side, CombatSide):
            raise TypeError("side must be a CombatSide")
        slots = tuple(self.action_slots)
        if not all(isinstance(item, CombatActionSlot) for item in slots):
            raise TypeError("action_slots must contain CombatActionSlot values")
        if len(slots) > 2:
            raise ValueError("a turn cannot contain more than two actions")
        if tuple(item.index for item in slots) != tuple(
            range(1, len(slots) + 1)
        ):
            raise ValueError("action slot indices must be consecutive")
        if slots and slots[0].grant is not ActionSlotGrant.STANDARD:
            raise ValueError("the first action must use the standard slot")
        if len(slots) == 2 and slots[1].grant is ActionSlotGrant.STANDARD:
            raise ValueError("the second action requires Fate or an Ability")
        if len(slots) == 2 and (
            slots[0].declaration.kind is slots[1].declaration.kind
        ):
            if slots[0].declaration.kind is not CombatActionKind.IMPROVISE:
                raise ValueError("a turn cannot repeat the same action")
            if (
                slots[0].declaration.improvise_approach_id
                == slots[1].declaration.improvise_approach_id
            ):
                raise ValueError(
                    "repeated Improvise actions require different approaches"
                )
        if sum(item.declaration.produces_attack for item in slots) > 1:
            raise ValueError("a turn cannot contain a second attack")
        object.__setattr__(self, "action_slots", slots)


@dataclass(frozen=True, slots=True)
class CombatRoundState:
    round_number: int
    participants: tuple[CombatTurnParticipant, ...]
    side_order: tuple[CombatSide, CombatSide] = (
        CombatSide.PLAYERS_AND_ALLIES,
        CombatSide.OPPOSITION,
    )
    completed_turn_entity_ids: tuple[str, ...] = field(default_factory=tuple)
    active_turn: CombatTurnState | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.round_number, int) or isinstance(
            self.round_number,
            bool,
        ):
            raise TypeError("round_number must be an integer")
        if self.round_number < 1:
            raise ValueError("round_number must be positive")
        participants = _normalize_participants(self.participants)
        if {item.side for item in participants} != set(CombatSide):
            raise ValueError("a combat round requires participants on both sides")
        side_order = tuple(self.side_order)
        if len(side_order) != 2 or set(side_order) != set(CombatSide):
            raise ValueError("side_order must contain both combat sides once")

        completed = tuple(self.completed_turn_entity_ids)
        for entity_id in completed:
            _validate_non_empty_string(entity_id, "completed turn entity_id")
        if len(set(completed)) != len(completed):
            raise ValueError("completed turn entity IDs must be unique")
        participant_ids = {item.entity_id for item in participants}
        if not set(completed) <= participant_ids:
            raise ValueError("completed turn references an unknown participant")

        if self.active_turn is not None:
            if not isinstance(self.active_turn, CombatTurnState):
                raise TypeError("active_turn must be a CombatTurnState")
            participant = _participant_for(
                participants,
                self.active_turn.actor_id,
            )
            if participant.side is not self.active_turn.side:
                raise ValueError("active turn side does not match participant")
            if participant.entity_id in completed:
                raise ValueError("completed participant cannot have an active turn")
            expected_side = _next_side(participants, side_order, completed)
            if participant.side is not expected_side:
                raise ValueError("active turn belongs to the wrong side")

        object.__setattr__(self, "participants", participants)
        object.__setattr__(self, "side_order", side_order)
        object.__setattr__(self, "completed_turn_entity_ids", completed)

    @property
    def round_complete(self) -> bool:
        return len(self.completed_turn_entity_ids) == len(self.participants)

    @property
    def next_side(self) -> CombatSide | None:
        return _next_side(
            self.participants,
            self.side_order,
            self.completed_turn_entity_ids,
        )

    def participant_for(self, entity_id: str) -> CombatTurnParticipant:
        return _participant_for(self.participants, entity_id)


@dataclass(frozen=True, slots=True)
class CombatTurnStartRequest:
    id: str
    state: CombatRoundState
    actor_id: str

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "turn start request id")
        if not isinstance(self.state, CombatRoundState):
            raise TypeError("state must be a CombatRoundState")
        _validate_non_empty_string(self.actor_id, "actor_id")


@dataclass(frozen=True, slots=True)
class CombatTurnStartResult:
    request_id: str
    state: CombatRoundState
    turn: CombatTurnState
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CombatActionSlotRequest:
    id: str
    state: CombatRoundState
    actor_id: str
    declaration: CombatActionDeclaration
    grant: ActionSlotGrant
    grant_rule_id: str | None = None
    allows_second_improvise: bool = False

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "action slot request id")
        if not isinstance(self.state, CombatRoundState):
            raise TypeError("state must be a CombatRoundState")
        _validate_non_empty_string(self.actor_id, "actor_id")
        if not isinstance(self.declaration, CombatActionDeclaration):
            raise TypeError("declaration must be a CombatActionDeclaration")
        if not isinstance(self.grant, ActionSlotGrant):
            raise TypeError("grant must be an ActionSlotGrant")
        if self.grant is ActionSlotGrant.ABILITY:
            if self.grant_rule_id is None:
                raise ValueError("Ability action grant requires a Rule ID")
            _validate_non_empty_string(self.grant_rule_id, "grant_rule_id")
        elif self.grant_rule_id is not None:
            raise ValueError("only an Ability action grant may name a Rule ID")
        if not isinstance(self.allows_second_improvise, bool):
            raise TypeError("allows_second_improvise must be a boolean")


@dataclass(frozen=True, slots=True)
class CombatActionSlotResult:
    request_id: str
    state: CombatRoundState
    slot: CombatActionSlot
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CombatTurnEndRequest:
    id: str
    state: CombatRoundState
    actor_id: str

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "turn end request id")
        if not isinstance(self.state, CombatRoundState):
            raise TypeError("state must be a CombatRoundState")
        _validate_non_empty_string(self.actor_id, "actor_id")


@dataclass(frozen=True, slots=True)
class CombatTurnEndResult:
    request_id: str
    state: CombatRoundState
    completed_turn: CombatTurnState
    next_side: CombatSide | None
    round_complete: bool
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CombatRoundAdvanceRequest:
    id: str
    state: CombatRoundState
    next_round_participants: tuple[CombatTurnParticipant, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "round advance request id")
        if not isinstance(self.state, CombatRoundState):
            raise TypeError("state must be a CombatRoundState")
        object.__setattr__(
            self,
            "next_round_participants",
            _normalize_participants(self.next_round_participants),
        )


@dataclass(frozen=True, slots=True)
class CombatRoundAdvanceResult:
    request_id: str
    state: CombatRoundState
    applied_rule_ids: tuple[str, ...]


def _normalize_participants(
    values: tuple[CombatTurnParticipant, ...],
) -> tuple[CombatTurnParticipant, ...]:
    participants = tuple(values)
    if not participants:
        raise ValueError("combat participants must not be empty")
    if not all(isinstance(item, CombatTurnParticipant) for item in participants):
        raise TypeError(
            "participants must contain CombatTurnParticipant values"
        )
    entity_ids = tuple(item.entity_id for item in participants)
    if len(set(entity_ids)) != len(entity_ids):
        raise ValueError("combat participant entity IDs must be unique")
    return participants


def _participant_for(
    participants: tuple[CombatTurnParticipant, ...],
    entity_id: str,
) -> CombatTurnParticipant:
    for participant in participants:
        if participant.entity_id == entity_id:
            return participant
    raise ValueError(f"unknown combat participant: {entity_id}")


def _next_side(
    participants: tuple[CombatTurnParticipant, ...],
    side_order: tuple[CombatSide, CombatSide],
    completed_turn_entity_ids: tuple[str, ...],
) -> CombatSide | None:
    completed = set(completed_turn_entity_ids)
    for side in side_order:
        if any(
            participant.side is side
            and participant.entity_id not in completed
            for participant in participants
        ):
            return side
    return None


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
