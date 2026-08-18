from __future__ import annotations

from towr.domain.magic_models import SpellPotencyRequest, SpellPotencyResult


def resolve_spell_potency(
    request: SpellPotencyRequest,
) -> SpellPotencyResult:
    potency_delta = sum(modifier.amount for modifier in request.modifiers)
    effective_potency = max(0, request.base_potency + potency_delta)
    return SpellPotencyResult(
        request_id=request.id,
        spell_rule_id=request.spell_rule_id,
        target_id=request.target_id,
        base_potency=request.base_potency,
        potency_delta=potency_delta,
        effective_potency=effective_potency,
        has_effect=effective_potency > 0,
        applied_rule_ids=tuple(
            modifier.rule_id for modifier in request.modifiers
        ),
    )
