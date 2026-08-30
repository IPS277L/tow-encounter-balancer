from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from towr.domain.injury_models import DecisionOwner
from towr.domain.turn_models import CombatRoundState, CombatSide


RETREAT_RULE_ID = "RULE-COMBAT-016:group-retreat"
RETREAT_ALTERNATIVE_PRICE_RULE_ID = (
    "RULE-COMBAT-016:alternative-retreat-price"
)


class RetreatTiming(str, Enum):
    START_OF_ROUND = "start_of_round"
    START_OF_PLAYERS_SIDE = "start_of_players_side"


class RetreatAlternativePrice(str, Enum):
    BLOOD = "blood"
    MATERIEL = "materiel"
    MISFORTUNE = "misfortune"


@dataclass(frozen=True, slots=True)
class GroupRetreatDeclaration:
    id: str
    battle_id: str
    initiator_actor_id: str
    player_character_ids: tuple[str, ...]
    consenting_player_character_ids: tuple[str, ...]
    round_state: CombatRoundState
    rule_id: str = RETREAT_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "retreat declaration id")
        _validate_non_empty_string(self.battle_id, "retreat battle_id")
        _validate_non_empty_string(
            self.initiator_actor_id,
            "retreat initiator_actor_id",
        )
        player_ids = _validate_unique_ids(
            self.player_character_ids,
            "retreat player_character_ids",
        )
        consent_ids = _validate_unique_ids(
            self.consenting_player_character_ids,
            "retreat consenting_player_character_ids",
        )
        if self.initiator_actor_id not in player_ids:
            raise ValueError("retreat initiator must be a player character")
        if set(consent_ids) != set(player_ids):
            raise ValueError("group Retreat requires unanimous player consent")
        if not isinstance(self.round_state, CombatRoundState):
            raise TypeError("round_state must be a CombatRoundState")
        for actor_id in player_ids:
            participant = self.round_state.participant_for(actor_id)
            if participant.side is not CombatSide.PLAYERS_AND_ALLIES:
                raise ValueError(
                    "retreat player characters must belong to the players side"
                )
        if self.round_state.active_turn is not None:
            raise ValueError("Retreat must be declared before a turn starts")
        _validate_retreat_timing(self.round_state)
        _validate_non_empty_string(self.rule_id, "retreat rule_id")
        if self.rule_id != RETREAT_RULE_ID:
            raise ValueError("group Retreat requires its canonical rule")
        object.__setattr__(self, "player_character_ids", player_ids)
        object.__setattr__(
            self,
            "consenting_player_character_ids",
            consent_ids,
        )

    @property
    def timing(self) -> RetreatTiming:
        if not self.round_state.completed_turn_entity_ids:
            return RetreatTiming.START_OF_ROUND
        return RetreatTiming.START_OF_PLAYERS_SIDE


@dataclass(frozen=True, slots=True)
class RetreatRearGuardResult:
    request_id: str
    source_request: GroupRetreatDeclaration
    rearguard_actor_id: str
    fate_proof_id: str
    source_spend_id: str
    covered_player_character_ids: tuple[str, ...]
    pursuit_decision_required: bool
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "retreat rearguard result request_id",
        )
        if not isinstance(self.source_request, GroupRetreatDeclaration):
            raise TypeError("source_request must be a GroupRetreatDeclaration")
        _validate_non_empty_string(
            self.rearguard_actor_id,
            "retreat rearguard_actor_id",
        )
        if self.rearguard_actor_id not in self.source_request.player_character_ids:
            raise ValueError("retreat rearguard must be a player character")
        _validate_non_empty_string(self.fate_proof_id, "retreat fate_proof_id")
        _validate_non_empty_string(
            self.source_spend_id,
            "retreat source_spend_id",
        )
        covered = _validate_unique_ids(
            self.covered_player_character_ids,
            "covered_player_character_ids",
        )
        if covered != self.source_request.player_character_ids:
            raise ValueError("retreat rearguard must cover the declared group")
        if self.request_id != self.source_request.id:
            raise ValueError("retreat result belongs to another declaration")
        if self.pursuit_decision_required is not True:
            raise ValueError(
                "covered Retreat must preserve the enemy pursuit decision"
            )
        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        if not rule_ids or rule_ids[0] != RETREAT_RULE_ID:
            raise ValueError("retreat rearguard rule trace is incomplete")
        object.__setattr__(self, "covered_player_character_ids", covered)
        object.__setattr__(self, "applied_rule_ids", rule_ids)


@dataclass(frozen=True, slots=True)
class RetreatAlternativePriceRequest:
    id: str
    source_retreat: GroupRetreatDeclaration
    exhausted_fate_actor_ids: tuple[str, ...]
    possible_prices: tuple[RetreatAlternativePrice, ...] = (
        RetreatAlternativePrice.BLOOD,
        RetreatAlternativePrice.MATERIEL,
        RetreatAlternativePrice.MISFORTUNE,
    )
    decision_owner: DecisionOwner = DecisionOwner.GM
    rule_id: str = RETREAT_ALTERNATIVE_PRICE_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "retreat price request id")
        if not isinstance(self.source_retreat, GroupRetreatDeclaration):
            raise TypeError("source_retreat must be a GroupRetreatDeclaration")
        exhausted = _validate_unique_ids(
            self.exhausted_fate_actor_ids,
            "exhausted_fate_actor_ids",
        )
        if set(exhausted) != set(self.source_retreat.player_character_ids):
            raise ValueError(
                "retreat price requires exhausted Fate for every player character"
            )
        prices = tuple(self.possible_prices)
        if prices != (
            RetreatAlternativePrice.BLOOD,
            RetreatAlternativePrice.MATERIEL,
            RetreatAlternativePrice.MISFORTUNE,
        ):
            raise ValueError("retreat price must expose all book-defined options")
        if self.decision_owner is not DecisionOwner.GM:
            raise ValueError("the GM chooses the alternative Retreat price")
        _validate_non_empty_string(self.rule_id, "retreat price rule_id")
        if self.rule_id != RETREAT_ALTERNATIVE_PRICE_RULE_ID:
            raise ValueError("retreat price requires its canonical rule")
        object.__setattr__(self, "exhausted_fate_actor_ids", exhausted)
        object.__setattr__(self, "possible_prices", prices)


def _validate_retreat_timing(state: CombatRoundState) -> None:
    completed = set(state.completed_turn_entity_ids)
    if not completed:
        if state.side_order[0] is CombatSide.PLAYERS_AND_ALLIES:
            return
        raise ValueError(
            "Retreat waits for the players side when enemies act first"
        )
    if state.side_order[0] is not CombatSide.OPPOSITION:
        raise ValueError("Retreat is no longer at the start of the round")
    opposition_ids = {
        item.entity_id
        for item in state.participants
        if item.side is CombatSide.OPPOSITION
    }
    if completed != opposition_ids or state.next_side is not CombatSide.PLAYERS_AND_ALLIES:
        raise ValueError(
            "Retreat after enemy actions requires the start of the players side"
        )


def _validate_unique_ids(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    ids = tuple(values)
    if not ids:
        raise ValueError(f"{name} must not be empty")
    for value in ids:
        _validate_non_empty_string(value, name)
    if len(set(ids)) != len(ids):
        raise ValueError(f"{name} must be unique")
    return ids


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
