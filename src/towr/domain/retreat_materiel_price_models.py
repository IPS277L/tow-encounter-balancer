from __future__ import annotations

from dataclasses import dataclass, field

from towr.domain.inventory_models import CarriedInventoryState, TrappingSnapshot
from towr.domain.retreat_models import (
    RETREAT_ALTERNATIVE_PRICE_RULE_ID,
    RetreatAlternativePrice,
    RetreatAlternativePriceResolutionResult,
    RetreatMaterielPriceApplicationRequest,
)


@dataclass(frozen=True, slots=True)
class RetreatMaterielPriceInventoryRequest:
    """Bind an already selected materiel price to one explicit carried item."""

    id: str
    source_price: RetreatAlternativePriceResolutionResult
    owner_actor_id: str
    selected_trapping_id: str
    inventory: CarriedInventoryState
    consumed_application_ids: tuple[str, ...] = field(default_factory=tuple)
    rule_id: str = RETREAT_ALTERNATIVE_PRICE_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.id,
            "Retreat materiel price application request id",
        )
        if not isinstance(
            self.source_price,
            RetreatAlternativePriceResolutionResult,
        ):
            raise TypeError(
                "source_price must be a RetreatAlternativePriceResolutionResult"
            )
        application = self.source_price.application_request
        if (
            self.source_price.decision.price is not RetreatAlternativePrice.MATERIEL
            or self.source_price.proof.price is not RetreatAlternativePrice.MATERIEL
            or not isinstance(application, RetreatMaterielPriceApplicationRequest)
        ):
            raise ValueError("Retreat price is not materiel")
        _validate_non_empty_string(
            self.owner_actor_id,
            "Retreat materiel price owner_actor_id",
        )
        if self.owner_actor_id not in application.possible_owner_actor_ids:
            raise ValueError("Retreat materiel price owner is not an eligible PC")
        _validate_non_empty_string(
            self.selected_trapping_id,
            "Retreat materiel price selected_trapping_id",
        )
        if not isinstance(self.inventory, CarriedInventoryState):
            raise TypeError("inventory must be a CarriedInventoryState")
        if self.inventory.owner_actor_id != self.owner_actor_id:
            raise ValueError("Retreat materiel inventory belongs to another actor")
        selected = self.inventory.trapping(self.selected_trapping_id)
        if selected is None:
            raise ValueError("selected Retreat materiel trapping is not carried")
        if not selected.is_valuable:
            raise ValueError("Retreat materiel price requires a valuable trapping")
        consumed = _validate_unique_ids(
            self.consumed_application_ids,
            "consumed Retreat price application ID",
        )
        if application.id in consumed:
            raise ValueError("Retreat materiel price application was already consumed")
        _validate_non_empty_string(self.rule_id, "Retreat materiel price rule_id")
        if self.rule_id != RETREAT_ALTERNATIVE_PRICE_RULE_ID:
            raise ValueError("Retreat materiel price uses an unknown rule")
        object.__setattr__(self, "consumed_application_ids", consumed)


@dataclass(frozen=True, slots=True)
class RetreatMaterielPriceApplicationResult:
    request_id: str
    rule_id: str
    source_request: RetreatMaterielPriceInventoryRequest
    owner_actor_id: str
    dropped_trapping: TrappingSnapshot
    previous_inventory: CarriedInventoryState
    inventory: CarriedInventoryState
    previous_consumed_application_ids: tuple[str, ...]
    consumed_application_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Retreat materiel price result request_id",
        )
        _validate_non_empty_string(
            self.rule_id,
            "Retreat materiel price result rule_id",
        )
        if not isinstance(
            self.source_request,
            RetreatMaterielPriceInventoryRequest,
        ):
            raise TypeError(
                "source_request must be a RetreatMaterielPriceInventoryRequest"
            )
        _validate_non_empty_string(
            self.owner_actor_id,
            "Retreat materiel price result owner_actor_id",
        )
        if not isinstance(self.dropped_trapping, TrappingSnapshot):
            raise TypeError("dropped_trapping must be a TrappingSnapshot")
        if not isinstance(self.previous_inventory, CarriedInventoryState):
            raise TypeError("previous_inventory must be a CarriedInventoryState")
        if not isinstance(self.inventory, CarriedInventoryState):
            raise TypeError("inventory must be a CarriedInventoryState")

        source = self.source_request
        application = source.source_price.application_request
        assert isinstance(application, RetreatMaterielPriceApplicationRequest)
        selected = source.inventory.trapping(source.selected_trapping_id)
        assert selected is not None
        previous_consumed = _validate_unique_ids(
            self.previous_consumed_application_ids,
            "previous consumed Retreat price application ID",
        )
        consumed = _validate_unique_ids(
            self.consumed_application_ids,
            "consumed Retreat price application ID",
        )
        expected_consumed = (*source.consumed_application_ids, application.id)
        expected_inventory = _inventory_after_drop(source)
        expected_rules = _ordered_rule_ids(
            *source.source_price.applied_rule_ids,
            source.rule_id,
        )
        if (
            self.request_id != source.id
            or self.rule_id != source.rule_id
            or self.owner_actor_id != source.owner_actor_id
            or self.dropped_trapping != selected
            or self.previous_inventory != source.inventory
            or self.inventory != expected_inventory
            or previous_consumed != source.consumed_application_ids
            or consumed != expected_consumed
            or self.applied_rule_ids != expected_rules
        ):
            raise ValueError("Retreat materiel price result has stale provenance")
        object.__setattr__(
            self,
            "previous_consumed_application_ids",
            previous_consumed,
        )
        object.__setattr__(self, "consumed_application_ids", consumed)


def _inventory_after_drop(
    request: RetreatMaterielPriceInventoryRequest,
) -> CarriedInventoryState:
    return CarriedInventoryState(
        owner_actor_id=request.inventory.owner_actor_id,
        trappings=tuple(
            item
            for item in request.inventory.trappings
            if item.id != request.selected_trapping_id
        ),
    )


def _ordered_rule_ids(*rule_ids: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(rule_ids))


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
