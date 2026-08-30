from __future__ import annotations

from towr.domain.retreat_materiel_price_models import (
    RetreatMaterielPriceApplicationResult,
    RetreatMaterielPriceInventoryRequest,
    _inventory_after_drop,
    _ordered_rule_ids,
)
from towr.domain.retreat_models import RETREAT_ALTERNATIVE_PRICE_RULE_ID


def apply_retreat_materiel_price(
    request: RetreatMaterielPriceInventoryRequest,
) -> RetreatMaterielPriceApplicationResult:
    """Drop the one explicitly selected valuable trapping without hidden choice."""
    if request.rule_id != RETREAT_ALTERNATIVE_PRICE_RULE_ID:
        raise ValueError("Retreat materiel price uses an unknown rule")
    application_id = request.source_price.application_request.id
    selected = request.inventory.trapping(request.selected_trapping_id)
    assert selected is not None
    return RetreatMaterielPriceApplicationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        owner_actor_id=request.owner_actor_id,
        dropped_trapping=selected,
        previous_inventory=request.inventory,
        inventory=_inventory_after_drop(request),
        previous_consumed_application_ids=request.consumed_application_ids,
        consumed_application_ids=(
            *request.consumed_application_ids,
            application_id,
        ),
        applied_rule_ids=_ordered_rule_ids(
            *request.source_price.applied_rule_ids,
            request.rule_id,
        ),
    )
