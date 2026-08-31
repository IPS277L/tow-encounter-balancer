from __future__ import annotations

from dataclasses import dataclass, field

from towr.domain.campaign_consequence_models import (
    RunForYourLivesCampaignApplicationResult,
)
from towr.domain.inventory_models import CarriedInventoryState, TrappingSnapshot
from towr.domain.retreat_models import (
    RUN_FOR_YOUR_LIVES_RULE_ID,
    RunForYourLivesOutcome,
)


@dataclass(frozen=True, slots=True)
class RobbedTrappingLossSelection:
    owner_actor_id: str
    trapping_ids: tuple[str, ...]
    consequence_reference_id: str

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.owner_actor_id,
            "Robbed loss owner_actor_id",
        )
        object.__setattr__(
            self,
            "trapping_ids",
            _validate_unique_non_empty_ids(
                self.trapping_ids,
                "Robbed loss trapping ID",
            ),
        )
        _validate_non_empty_string(
            self.consequence_reference_id,
            "Robbed loss consequence_reference_id",
        )


@dataclass(frozen=True, slots=True)
class RunForYourLivesRobbedInventoryRequest:
    id: str
    source_campaign: RunForYourLivesCampaignApplicationResult
    inventories: tuple[CarriedInventoryState, ...]
    selections: tuple[RobbedTrappingLossSelection, ...]
    consumed_consequence_ids: tuple[str, ...] = field(default_factory=tuple)
    rule_id: str = RUN_FOR_YOUR_LIVES_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.id,
            "Run For Your Lives Robbed inventory request id",
        )
        if not isinstance(
            self.source_campaign,
            RunForYourLivesCampaignApplicationResult,
        ):
            raise TypeError(
                "source_campaign must be a "
                "RunForYourLivesCampaignApplicationResult"
            )
        consequence = self.source_campaign.consequence
        if consequence.outcome is not RunForYourLivesOutcome.ROBBED:
            raise ValueError("Run For Your Lives campaign outcome is not Robbed")

        inventories = tuple(self.inventories)
        if not all(
            isinstance(inventory, CarriedInventoryState)
            for inventory in inventories
        ):
            raise TypeError("inventories must contain CarriedInventoryState values")
        expected_owners = consequence.player_character_ids
        inventory_owners = tuple(
            inventory.owner_actor_id for inventory in inventories
        )
        if inventory_owners != expected_owners:
            raise ValueError(
                "Robbed inventories must match the ordered player group"
            )

        selections = tuple(self.selections)
        if not all(
            isinstance(selection, RobbedTrappingLossSelection)
            for selection in selections
        ):
            raise TypeError(
                "selections must contain RobbedTrappingLossSelection values"
            )
        selection_owners = tuple(
            selection.owner_actor_id for selection in selections
        )
        if selection_owners != expected_owners:
            raise ValueError(
                "Robbed selections must cover the ordered player group"
            )
        specification_references = (
            consequence.specification.concrete_consequence_reference_ids
        )
        selection_references = tuple(
            selection.consequence_reference_id for selection in selections
        )
        if selection_references != specification_references:
            raise ValueError(
                "Robbed selections disagree with registered consequence references"
            )
        for inventory, selection in zip(inventories, selections, strict=True):
            missing_ids = tuple(
                trapping_id
                for trapping_id in selection.trapping_ids
                if inventory.trapping(trapping_id) is None
            )
            if missing_ids:
                raise ValueError(
                    "Robbed selected trapping is not carried by its owner"
                )

        consumed = _validate_unique_ids(
            self.consumed_consequence_ids,
            "consumed Run For Your Lives consequence ID",
        )
        if consequence.id in consumed:
            raise ValueError("Run For Your Lives Robbed consequence was already consumed")
        _validate_non_empty_string(
            self.rule_id,
            "Run For Your Lives Robbed rule_id",
        )
        if self.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
            raise ValueError("Run For Your Lives Robbed uses an unknown rule")
        object.__setattr__(self, "inventories", inventories)
        object.__setattr__(self, "selections", selections)
        object.__setattr__(self, "consumed_consequence_ids", consumed)


@dataclass(frozen=True, slots=True)
class RobbedInventoryTransition:
    owner_actor_id: str
    consequence_reference_id: str
    dropped_trappings: tuple[TrappingSnapshot, ...]
    previous_inventory: CarriedInventoryState
    inventory: CarriedInventoryState

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.owner_actor_id,
            "Robbed transition owner_actor_id",
        )
        _validate_non_empty_string(
            self.consequence_reference_id,
            "Robbed transition consequence_reference_id",
        )
        dropped = tuple(self.dropped_trappings)
        if not dropped:
            raise ValueError("Robbed transition must drop at least one trapping")
        if not all(isinstance(item, TrappingSnapshot) for item in dropped):
            raise TypeError(
                "dropped_trappings must contain TrappingSnapshot values"
            )
        if not isinstance(self.previous_inventory, CarriedInventoryState):
            raise TypeError("previous_inventory must be a CarriedInventoryState")
        if not isinstance(self.inventory, CarriedInventoryState):
            raise TypeError("inventory must be a CarriedInventoryState")
        if (
            self.previous_inventory.owner_actor_id != self.owner_actor_id
            or self.inventory.owner_actor_id != self.owner_actor_id
            or any(item.owner_actor_id != self.owner_actor_id for item in dropped)
        ):
            raise ValueError("Robbed transition inventories belong to another actor")
        dropped_ids = tuple(item.id for item in dropped)
        if len(set(dropped_ids)) != len(dropped_ids):
            raise ValueError("Robbed dropped trapping IDs must be unique")
        expected_dropped = tuple(
            item
            for trapping_id in dropped_ids
            for item in (self.previous_inventory.trapping(trapping_id),)
            if item is not None
        )
        expected_inventory = _inventory_after_drop(
            self.previous_inventory,
            dropped_ids,
        )
        if dropped != expected_dropped or self.inventory != expected_inventory:
            raise ValueError("Robbed inventory transition has stale provenance")
        object.__setattr__(self, "dropped_trappings", dropped)


@dataclass(frozen=True, slots=True)
class RunForYourLivesRobbedInventoryResult:
    request_id: str
    rule_id: str
    source_request: RunForYourLivesRobbedInventoryRequest
    transitions: tuple[RobbedInventoryTransition, ...]
    previous_consumed_consequence_ids: tuple[str, ...]
    consumed_consequence_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Run For Your Lives Robbed result request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "Run For Your Lives Robbed result rule_id",
        )
        if not isinstance(
            self.source_request,
            RunForYourLivesRobbedInventoryRequest,
        ):
            raise TypeError(
                "source_request must be a RunForYourLivesRobbedInventoryRequest"
            )
        transitions = tuple(self.transitions)
        if not all(
            isinstance(transition, RobbedInventoryTransition)
            for transition in transitions
        ):
            raise TypeError(
                "transitions must contain RobbedInventoryTransition values"
            )
        source = self.source_request
        expected_transitions = _robbed_transitions(source)
        previous_consumed = _validate_unique_ids(
            self.previous_consumed_consequence_ids,
            "previous consumed Run For Your Lives consequence ID",
        )
        consumed = _validate_unique_ids(
            self.consumed_consequence_ids,
            "consumed Run For Your Lives consequence ID",
        )
        expected_consumed = (
            *source.consumed_consequence_ids,
            source.source_campaign.consequence.id,
        )
        expected_rules = tuple(
            dict.fromkeys((*source.source_campaign.applied_rule_ids, source.rule_id))
        )
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or transitions != expected_transitions
            or previous_consumed != source.consumed_consequence_ids
            or consumed != expected_consumed
            or self.applied_rule_ids != expected_rules
        ):
            raise ValueError("Run For Your Lives Robbed result has stale provenance")
        object.__setattr__(self, "transitions", transitions)
        object.__setattr__(
            self,
            "previous_consumed_consequence_ids",
            previous_consumed,
        )
        object.__setattr__(self, "consumed_consequence_ids", consumed)


def _robbed_transitions(
    request: RunForYourLivesRobbedInventoryRequest,
) -> tuple[RobbedInventoryTransition, ...]:
    transitions: list[RobbedInventoryTransition] = []
    for inventory, selection in zip(
        request.inventories,
        request.selections,
        strict=True,
    ):
        dropped = tuple(
            item
            for trapping_id in selection.trapping_ids
            for item in (inventory.trapping(trapping_id),)
            if item is not None
        )
        transitions.append(
            RobbedInventoryTransition(
                owner_actor_id=selection.owner_actor_id,
                consequence_reference_id=selection.consequence_reference_id,
                dropped_trappings=dropped,
                previous_inventory=inventory,
                inventory=_inventory_after_drop(
                    inventory,
                    selection.trapping_ids,
                ),
            )
        )
    return tuple(transitions)


def _inventory_after_drop(
    inventory: CarriedInventoryState,
    trapping_ids: tuple[str, ...],
) -> CarriedInventoryState:
    dropped_ids = frozenset(trapping_ids)
    return CarriedInventoryState(
        owner_actor_id=inventory.owner_actor_id,
        trappings=tuple(
            item for item in inventory.trappings if item.id not in dropped_ids
        ),
    )


def _validate_unique_non_empty_ids(
    values: tuple[str, ...],
    name: str,
) -> tuple[str, ...]:
    ids = _validate_unique_ids(values, name)
    if not ids:
        raise ValueError(f"{name}s must not be empty")
    return ids


def _validate_unique_ids(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    ids = tuple(values)
    for value in ids:
        _validate_non_empty_string(value, name)
    if len(set(ids)) != len(ids):
        raise ValueError(f"{name}s must be unique")
    return ids


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
