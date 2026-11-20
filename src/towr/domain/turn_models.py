from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from towr.domain.weapon_use_models import WeaponUse
    from towr.domain.talent_action_grant_models import RapidReloadGrant


ACTION_BUDGET_RULE_ID = "RULE-COMBAT-002:action-budget"
ENDURING_STRENGTH_RULE_ID = "RULE-PROFILE-CREATURE-010:enduring-strength"
CROWN_OF_ANTLERS_RULE_ID = "RULE-PROFILE-MONSTER-002:crown-of-antlers"
DUELLIST_BLADES_RULE_ID = "RULE-MAGIC-ITEM-003:duellist-second-attack"


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
    actor_id: str
    round_number: int
    slot_index: int
    declaration: CombatActionDeclaration

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
        _validate_non_empty_string(self.actor_id, "action execution actor_id")
        if not isinstance(self.round_number, int) or isinstance(
            self.round_number,
            bool,
        ):
            raise TypeError("action execution round_number must be an integer")
        if self.round_number < 1:
            raise ValueError("action execution round_number must be positive")
        if not isinstance(self.slot_index, int) or isinstance(
            self.slot_index,
            bool,
        ):
            raise TypeError("action execution slot_index must be an integer")
        if self.slot_index not in (1, 2):
            raise ValueError("action execution slot_index must be 1 or 2")
        if not isinstance(self.declaration, CombatActionDeclaration):
            raise TypeError(
                "action execution declaration must be a "
                "CombatActionDeclaration"
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
class EnduringStrengthGrant:
    """Clock projection; its successful source Attack is certified by the owner."""

    actor_id: str
    round_number: int
    slot_request_id: str
    first_execution: ActionExecutionReceipt
    first_target_id: str
    target_id: str

    def __post_init__(self) -> None:
        for value in (self.actor_id, self.slot_request_id, self.first_target_id, self.target_id):
            _validate_non_empty_string(value, "Enduring Strength source/target ID")
        if type(self.round_number) is not int or self.round_number < 1:
            raise ValueError("Enduring Strength requires a positive integer round")
        if type(self.first_execution) is not ActionExecutionReceipt:
            raise TypeError("Enduring Strength requires the first execution receipt")
        replace(self.first_execution)
        replace(self.first_execution.declaration)
        if (self.first_execution.actor_id != self.actor_id
                or self.first_execution.round_number != self.round_number
                or self.first_execution.slot_index != 1
                or self.first_execution.executor_rule_id != 'RULE-COMBAT-004:attack-action-execution'
                or self.first_execution.declaration.kind is not CombatActionKind.ATTACK):
            raise ValueError("Enduring Strength requires this actor's first Attack")
        if self.first_target_id == self.target_id:
            raise ValueError("Enduring Strength requires a different target")


def _validate_crown_declaration(declaration: CombatActionDeclaration) -> None:
    if type(declaration) is not CombatActionDeclaration:
        raise TypeError('Crown requires its exact Attack declaration')
    replace(declaration)
    if (type(declaration.kind) is not CombatActionKind
            or type(declaration.improvise_produces_attack) is not bool):
        raise TypeError('Crown declaration requires exact enum/bool types')


def _validate_crown_receipt(receipt: ActionExecutionReceipt) -> None:
    if type(receipt) is not ActionExecutionReceipt:
        raise TypeError('Crown of Antlers requires its exact first execution receipt')
    replace(receipt)
    for name in ('id','executor_rule_id','source_request_id','result_request_id','actor_id'):
        value = getattr(receipt,name)
        if type(value) is not str or not value.strip():
            raise TypeError('Crown receipt IDs require exact nonempty strings')
    if type(receipt.round_number) is not int or type(receipt.slot_index) is not int:
        raise TypeError('Crown receipt round/slot require exact integers')
    _validate_crown_declaration(receipt.declaration)


@dataclass(frozen=True, slots=True)
class CrownOfAntlersGrant:
    """One same-target Trample; the owner certifies the actual new Prone cause."""

    actor_id: str
    round_number: int
    slot_request_id: str
    first_execution: ActionExecutionReceipt
    first_target_id: str
    target_id: str
    attack_id: str

    def __post_init__(self) -> None:
        for value in (self.actor_id,self.slot_request_id,self.first_target_id,self.target_id,self.attack_id):
            if type(value) is not str or not value.strip():
                raise TypeError('Crown source/target IDs require exact nonempty strings')
        if type(self.round_number) is not int:
            raise TypeError('Crown round requires an exact integer')
        if self.round_number < 1:
            raise ValueError('Crown round must be positive')
        _validate_crown_receipt(self.first_execution)
        if (self.first_execution.actor_id != self.actor_id
                or self.first_execution.round_number != self.round_number
                or self.first_execution.slot_index != 1
                or self.first_execution.executor_rule_id != 'RULE-COMBAT-004:attack-action-execution'
                or self.first_execution.declaration.kind is not CombatActionKind.ATTACK):
            raise ValueError('Crown requires this actor and round first Attack receipt')
        if self.first_target_id != self.target_id or self.attack_id != 'trample':
            raise ValueError('Crown permits only Trample against the first Attack target')


@dataclass(frozen=True, slots=True)
class DuellistBladesGrant:
    """One further Attack with the actual first Duellist Blades unit (GM83)."""

    actor_id: str
    round_number: int
    slot_request_id: str
    first_execution: ActionExecutionReceipt
    weapon_use: WeaponUse
    target_id: str

    def __post_init__(self) -> None:
        from towr.domain.weapon_catalog import WeaponKind
        from towr.domain.weapon_use_models import WeaponUse

        for value in (self.actor_id, self.slot_request_id, self.target_id):
            if type(value) is not str or not value.strip():
                raise TypeError('Duellist grant needs exact actor, slot and target IDs')
        if type(self.round_number) is not int:
            raise TypeError('Duellist grant round must be an exact integer')
        if self.round_number < 1:
            raise ValueError('Duellist grant requires a positive round')
        # These existing exact receipt checks also validate the declaration;
        # they describe a source shape, not a Crown ability authorization.
        _validate_crown_receipt(self.first_execution)
        receipt = self.first_execution
        if (receipt.actor_id != self.actor_id or receipt.round_number != self.round_number
                or receipt.slot_index != 1
                or receipt.executor_rule_id != 'RULE-COMBAT-004:attack-action-execution'
                or receipt.declaration.kind is not CombatActionKind.ATTACK):
            raise ValueError('Duellist grant requires this actor and round first Attack')
        if type(self.weapon_use) is not WeaponUse:
            raise TypeError('Duellist grant requires its exact frozen WeaponUse')
        use = replace(self.weapon_use)
        if (use.actor_id != self.actor_id or use.kind is not WeaponKind.DUELLIST_BLADES
                or use.primary_item_id is None or self.target_id == self.actor_id):
            raise ValueError('Duellist grant lost its actual weapon, actor or enemy target')


@dataclass(frozen=True, slots=True)
class CombatActionSlot:
    index: int
    declaration: CombatActionDeclaration
    grant: ActionSlotGrant
    grant_rule_id: str | None = None
    execution: ActionExecutionReceipt | None = None
    enduring_strength: EnduringStrengthGrant | None = None
    crown_of_antlers: CrownOfAntlersGrant | None = field(default=None, kw_only=True)
    duellist_blades: DuellistBladesGrant | None = field(default=None, kw_only=True)
    rapid_reload: RapidReloadGrant | None = field(default=None, kw_only=True)

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
        from towr.domain.talent_action_grant_models import RAPID_RELOAD_RULE_ID, RapidReloadGrant
        if self.rapid_reload is not None:
            if type(self.rapid_reload) is not RapidReloadGrant:
                raise TypeError('Rapid Reload requires its exact typed grant')
            grant = replace(self.rapid_reload)
            if any(value is not None for value in (
                    self.enduring_strength, self.crown_of_antlers, self.duellist_blades)):
                raise ValueError('Rapid Reload cannot combine with another action grant')
            if (self.index != 2 or self.grant is not ActionSlotGrant.ABILITY
                    or self.grant_rule_id != RAPID_RELOAD_RULE_ID
                    or self.declaration != CombatActionDeclaration(grant.action_kind)):
                raise ValueError('Rapid Reload grants exactly its selected Ability action2')
        elif self.grant_rule_id == RAPID_RELOAD_RULE_ID:
            raise ValueError('Rapid Reload Rule ID alone cannot authorize an action')
        if self.duellist_blades is not None:
            if self.enduring_strength is not None or self.crown_of_antlers is not None:
                raise ValueError('Duellist cannot combine with another second-Attack grant')
            if type(self.duellist_blades) is not DuellistBladesGrant:
                raise TypeError('Duellist slot requires its exact typed grant')
            replace(self.duellist_blades)
            _validate_crown_declaration(self.declaration)
            if (type(self.index) is not int or type(self.grant) is not ActionSlotGrant
                    or type(self.grant_rule_id) is not str):
                raise TypeError('Duellist slot needs exact clock source types')
            if (self.index != 2 or self.grant is not ActionSlotGrant.ABILITY
                    or self.grant_rule_id != DUELLIST_BLADES_RULE_ID
                    or self.declaration.kind is not CombatActionKind.ATTACK):
                raise ValueError('Duellist only grants an Ability Attack slot2')
        elif self.grant_rule_id == DUELLIST_BLADES_RULE_ID:
            raise ValueError('Duellist Rule ID alone cannot authorize an action')
        if self.crown_of_antlers is not None:
            if self.enduring_strength is not None:
                raise ValueError('an action cannot combine Bear and Crown grants')
            if type(self.crown_of_antlers) is not CrownOfAntlersGrant:
                raise TypeError('Crown requires its exact typed grant')
            replace(self.crown_of_antlers)
            if (type(self.index) is not int or type(self.grant) is not ActionSlotGrant
                    or type(self.grant_rule_id) is not str
                    or type(self.declaration) is not CombatActionDeclaration):
                raise TypeError('Crown slot requires exact typed source fields')
            _validate_crown_declaration(self.declaration)
            if (self.index != 2 or self.grant is not ActionSlotGrant.ABILITY
                    or self.grant_rule_id != CROWN_OF_ANTLERS_RULE_ID
                    or self.declaration.kind is not CombatActionKind.ATTACK):
                raise ValueError('Crown only grants ability Attack slot2')
        elif self.grant_rule_id == CROWN_OF_ANTLERS_RULE_ID:
            raise ValueError('Crown Rule ID alone cannot grant an action')
        if self.enduring_strength is not None:
            if type(self.enduring_strength) is not EnduringStrengthGrant:
                raise TypeError("Enduring Strength requires its typed grant")
            replace(self.enduring_strength)
            if (self.index != 2 or self.grant is not ActionSlotGrant.ABILITY
                    or self.grant_rule_id != ENDURING_STRENGTH_RULE_ID
                    or self.declaration.kind is not CombatActionKind.ATTACK):
                raise ValueError("Enduring Strength only grants ability Attack slot2")
        if self.execution is not None and not isinstance(
            self.execution,
            ActionExecutionReceipt,
        ):
            raise TypeError("execution must be an ActionExecutionReceipt")
        if self.execution is not None:
            if self.crown_of_antlers is not None or self.duellist_blades is not None:
                _validate_crown_receipt(self.execution)
            if self.execution.slot_index != self.index:
                raise ValueError("execution receipt belongs to another slot")
            if self.execution.declaration != self.declaration:
                raise ValueError(
                    "execution receipt uses another action declaration"
                )

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
        repeated_attack = False
        for slot in slots:
            replace(slot)
            if slot.rapid_reload is not None:
                grant = slot.rapid_reload
                if (slot.index != 2 or grant.actor_id != self.actor_id
                        or slots[0].execution != grant.first_execution):
                    raise ValueError('Rapid Reload belongs to another executed first action')
            if slot.duellist_blades is not None:
                grant = slot.duellist_blades
                _validate_crown_receipt(slots[0].execution)
                _validate_crown_declaration(slots[0].declaration)
                if (type(self.actor_id) is not str or slot.index != 2
                        or grant.actor_id != self.actor_id
                        or slots[0].execution != grant.first_execution):
                    raise ValueError('Duellist belongs to another executed first Attack')
                repeated_attack = True
            if slot.crown_of_antlers is not None:
                grant = slot.crown_of_antlers
                if type(self.actor_id) is not str:
                    raise TypeError('Crown turn requires its exact actor ID')
                _validate_crown_receipt(slots[0].execution)
                _validate_crown_declaration(slots[0].declaration)
                if (slot.index != 2 or grant.actor_id != self.actor_id
                        or slots[0].execution != grant.first_execution):
                    raise ValueError('Crown belongs to another executed first Attack')
                repeated_attack = True
            if slot.enduring_strength is not None:
                grant = slot.enduring_strength
                if (slot.index != 2 or grant.actor_id != self.actor_id
                        or slots[0].execution != grant.first_execution):
                    raise ValueError("Enduring Strength belongs to another executed first Attack")
                repeated_attack = True
        if len(slots) == 2 and not repeated_attack and (
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
        if not repeated_attack and sum(item.declaration.produces_attack for item in slots) > 1:
            raise ValueError("a turn cannot contain a second attack")
        execution_ids = tuple(
            item.execution.id
            for item in slots
            if item.execution is not None
        )
        if len(set(execution_ids)) != len(execution_ids):
            raise ValueError("action execution receipt IDs must be unique")
        if any(
            item.execution is not None
            and item.execution.actor_id != self.actor_id
            for item in slots
        ):
            raise ValueError("action execution receipt belongs to another actor")
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
    excluded_turn_entity_ids: tuple[str, ...] = field(default_factory=tuple)

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
        excluded = tuple(self.excluded_turn_entity_ids)
        for entity_id in excluded:
            _validate_non_empty_string(entity_id, "excluded turn entity_id")
        if len(set(excluded)) != len(excluded):
            raise ValueError("excluded turn entity IDs must be unique")
        if not set(excluded) <= participant_ids:
            raise ValueError("excluded turn references an unknown participant")
        if set(excluded) & set(completed):
            raise ValueError("excluded participants cannot have completed turns")

        if self.active_turn is not None:
            if not isinstance(self.active_turn, CombatTurnState):
                raise TypeError("active_turn must be a CombatTurnState")
            if any(slot.crown_of_antlers is not None or slot.duellist_blades is not None
                    for slot in self.active_turn.action_slots):
                replace(self.active_turn)
            participant = _participant_for(
                participants,
                self.active_turn.actor_id,
            )
            if participant.side is not self.active_turn.side:
                raise ValueError("active turn side does not match participant")
            if participant.entity_id in completed:
                raise ValueError("completed participant cannot have an active turn")
            if participant.entity_id in excluded:
                raise ValueError("excluded participant cannot have an active turn")
            expected_side = _next_side(participants, side_order, (*completed, *excluded))
            if participant.side is not expected_side:
                raise ValueError("active turn belongs to the wrong side")
            if any(
                slot.execution is not None
                and slot.execution.round_number != self.round_number
                for slot in self.active_turn.action_slots
            ):
                raise ValueError(
                    "action execution receipt belongs to another round"
                )
            if any(slot.enduring_strength is not None
                    and slot.enduring_strength.round_number != self.round_number
                    for slot in self.active_turn.action_slots):
                raise ValueError("Enduring Strength grant belongs to another round")
            if any(slot.crown_of_antlers is not None
                    and (type(self.round_number) is not int
                        or slot.crown_of_antlers.round_number != self.round_number)
                    for slot in self.active_turn.action_slots):
                raise ValueError('Crown grant belongs to another round')
            if any(slot.duellist_blades is not None
                    and (type(self.round_number) is not int
                        or slot.duellist_blades.round_number != self.round_number)
                    for slot in self.active_turn.action_slots):
                raise ValueError('Duellist grant belongs to another round')
            for slot in self.active_turn.action_slots:
                if slot.duellist_blades is not None:
                    target = _participant_for(participants, slot.duellist_blades.target_id)
                    if target.side is self.active_turn.side:
                        raise ValueError('Duellist target must belong to the opposing side')

        object.__setattr__(self, "participants", participants)
        object.__setattr__(self, "side_order", side_order)
        object.__setattr__(self, "completed_turn_entity_ids", completed)
        object.__setattr__(self, "excluded_turn_entity_ids", excluded)

    @property
    def round_complete(self) -> bool:
        return len(self.completed_turn_entity_ids) + len(self.excluded_turn_entity_ids) == len(self.participants)

    @property
    def next_side(self) -> CombatSide | None:
        return _next_side(
            self.participants,
            self.side_order,
            (*self.completed_turn_entity_ids, *self.excluded_turn_entity_ids),
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
    enduring_strength: EnduringStrengthGrant | None = None
    crown_of_antlers: CrownOfAntlersGrant | None = field(default=None, kw_only=True)
    duellist_blades: DuellistBladesGrant | None = field(default=None, kw_only=True)
    rapid_reload: RapidReloadGrant | None = field(default=None, kw_only=True)

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
        from towr.domain.talent_action_grant_models import RAPID_RELOAD_RULE_ID, RapidReloadGrant
        if self.rapid_reload is not None:
            if type(self.rapid_reload) is not RapidReloadGrant:
                raise TypeError('Rapid Reload reservation requires its exact typed grant')
            grant = replace(self.rapid_reload)
            turn = self.state.active_turn
            if (grant.actor_id != self.actor_id or grant.round_number != self.state.round_number
                    or grant.slot_request_id != self.id or self.state != grant.source_reload.round_state
                    or turn is None or turn.actor_id != self.actor_id or len(turn.action_slots) != 1
                    or turn.action_slots[0].execution != grant.first_execution):
                raise ValueError('Rapid Reload reservation changed its actual first Reload source')
            if self.state.participant_for(grant.target_id).side is turn.side:
                raise ValueError('Rapid Reload target must belong to the opposing side')
            CombatActionSlot(2, self.declaration, self.grant, self.grant_rule_id,
                enduring_strength=self.enduring_strength, crown_of_antlers=self.crown_of_antlers,
                duellist_blades=self.duellist_blades, rapid_reload=grant)
        elif self.grant_rule_id == RAPID_RELOAD_RULE_ID:
            raise ValueError('Rapid Reload Rule ID alone cannot reserve an action')
        if self.duellist_blades is not None:
            if self.enduring_strength is not None or self.crown_of_antlers is not None:
                raise ValueError('Duellist cannot combine with another action grant')
            if type(self.duellist_blades) is not DuellistBladesGrant:
                raise TypeError('Duellist reservation requires its exact typed grant')
            grant = replace(self.duellist_blades)
            if type(self.state) is not CombatRoundState:
                raise TypeError('Duellist reservation requires an exact round clock')
            if type(self.id) is not str or type(self.actor_id) is not str:
                raise TypeError('Duellist reservation needs exact source IDs')
            if (grant.actor_id != self.actor_id or grant.round_number != self.state.round_number
                    or grant.slot_request_id != self.id):
                raise ValueError('Duellist belongs to another reservation')
            turn = self.state.active_turn
            if (turn is None or type(turn) is not CombatTurnState or turn.actor_id != self.actor_id
                    or len(turn.action_slots) != 1
                    or turn.action_slots[0].execution != grant.first_execution):
                raise ValueError('Duellist requires its actual executed first Attack')
            _validate_crown_receipt(turn.action_slots[0].execution)
            _validate_crown_declaration(turn.action_slots[0].declaration)
            target = self.state.participant_for(grant.target_id)
            if target.side is turn.side:
                raise ValueError('Duellist target must belong to the opposing side')
            CombatActionSlot(2, self.declaration, self.grant, self.grant_rule_id,
                duellist_blades=grant)
        elif self.grant_rule_id == DUELLIST_BLADES_RULE_ID:
            raise ValueError('Duellist Rule ID alone cannot reserve an action')
        if self.crown_of_antlers is not None:
            if self.enduring_strength is not None:
                raise ValueError('a reservation cannot combine Bear and Crown grants')
            if type(self.crown_of_antlers) is not CrownOfAntlersGrant:
                raise TypeError('Crown requires its exact typed grant')
            grant = replace(self.crown_of_antlers)
            if type(self.id) is not str or type(self.actor_id) is not str or type(self.state.round_number) is not int:
                raise TypeError('Crown reservation requires exact source IDs/round')
            if (grant.actor_id != self.actor_id or grant.round_number != self.state.round_number
                    or grant.slot_request_id != self.id):
                raise ValueError('Crown belongs to another reservation')
            turn = self.state.active_turn
            if (turn is None or turn.actor_id != self.actor_id or len(turn.action_slots) != 1
                    or turn.action_slots[0].execution != grant.first_execution):
                raise ValueError('Crown reservation requires its actual executed first Attack')
            _validate_crown_receipt(turn.action_slots[0].execution)
            _validate_crown_declaration(turn.action_slots[0].declaration)
            CombatActionSlot(2,self.declaration,self.grant,self.grant_rule_id,
                crown_of_antlers=grant)
        elif self.grant_rule_id == CROWN_OF_ANTLERS_RULE_ID:
            raise ValueError('Crown Rule ID alone cannot reserve an action')
        if self.enduring_strength is not None:
            if type(self.enduring_strength) is not EnduringStrengthGrant:
                raise TypeError("Enduring Strength requires its typed grant")
            replace(self.enduring_strength)
            if (self.enduring_strength.actor_id != self.actor_id
                    or self.enduring_strength.round_number != self.state.round_number
                    or self.enduring_strength.slot_request_id != self.id):
                raise ValueError("Enduring Strength belongs to another reservation")
            CombatActionSlot(2, self.declaration, self.grant, self.grant_rule_id,
                enduring_strength=self.enduring_strength)


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
