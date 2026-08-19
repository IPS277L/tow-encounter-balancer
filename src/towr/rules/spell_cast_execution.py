from __future__ import annotations

from towr.domain.magic_models import (
    SpellCastExecutionRequest,
    SpellCastExecutionResult,
    SpellCastTargetResult,
    SpellEffectApplicationRequest,
    SpellPotencyRequest,
)
from towr.rules.spell_potency_resolution import resolve_spell_potency


TARGET_SCOPED_POTENCY_RULE_ID = "RULE-MAGIC-002:target-scoped-potency"


def resolve_spell_cast_targets(
    request: SpellCastExecutionRequest,
) -> SpellCastExecutionResult:
    target_results: list[SpellCastTargetResult] = []
    follow_ups: list[SpellEffectApplicationRequest] = []
    for index, target in enumerate(request.targets):
        potency = resolve_spell_potency(
            SpellPotencyRequest(
                id=f"{request.id}:target:{index}:potency",
                spell_rule_id=request.source.spell_rule_id,
                target_id=target.target_id,
                base_potency=request.source.base_potency,
                modifiers=target.potency_modifiers,
            )
        )
        effect_request = None
        if potency.has_effect:
            effect_request = SpellEffectApplicationRequest(
                resolution_id=f"{request.id}:target:{index}:effect",
                source_cast_id=request.source.resolution_id,
                caster_id=request.source.caster_id,
                spell_rule_id=request.source.spell_rule_id,
                lore_id=request.source.lore_id,
                target_id=target.target_id,
                potency=potency.effective_potency,
                rule_id=request.source.spell_rule_id,
            )
            follow_ups.append(effect_request)
        target_results.append(
            SpellCastTargetResult(
                target_id=target.target_id,
                potency=potency,
                effect_request=effect_request,
            )
        )

    return SpellCastExecutionResult(
        request_id=request.id,
        source_cast_id=request.source.resolution_id,
        caster_id=request.source.caster_id,
        spell_rule_id=request.source.spell_rule_id,
        lore_id=request.source.lore_id,
        selected_target_id=request.selected_target_id,
        targets=tuple(target_results),
        follow_ups=tuple(follow_ups),
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    *(
                        rule_id
                        for result in target_results
                        for rule_id in result.potency.applied_rule_ids
                    ),
                )
            )
        ),
    )
