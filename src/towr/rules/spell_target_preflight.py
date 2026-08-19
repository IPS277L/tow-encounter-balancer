from __future__ import annotations

from towr.domain.magic_models import (
    SpellCastExecutionRequest,
    SpellTargetPreflightOutcome,
    SpellTargetPreflightRequest,
    SpellTargetPreflightResult,
)


SPELL_SCHEMA_RULE_ID = "RULE-MAGIC-005:spell-schema"


def resolve_spell_target_preflight(
    request: SpellTargetPreflightRequest,
) -> SpellTargetPreflightResult:
    source = request.source
    definition = request.definition
    if source.spell_rule_id != definition.rule_id:
        raise ValueError("cast spell Rule ID does not match its definition")
    if source.lore_id != definition.lore_id:
        raise ValueError("cast Magic Lore does not match its definition")
    if source.casting_value != definition.casting_value:
        raise ValueError("cast CV does not match its definition")

    if request.selected_target_kind is not definition.target_kind:
        return _closed_result(
            request,
            SpellTargetPreflightOutcome.INVALID_TARGET_KIND,
        )
    if not request.target_within_range:
        return _closed_result(
            request,
            SpellTargetPreflightOutcome.OUT_OF_RANGE,
        )

    return SpellTargetPreflightResult(
        request_id=request.id,
        source_cast_id=source.resolution_id,
        selected_target_id=request.selected_target_id,
        outcome=SpellTargetPreflightOutcome.READY,
        definition=definition,
        execution_request=SpellCastExecutionRequest(
            id=f"{request.id}:targets",
            source=source,
            selected_target_id=request.selected_target_id,
            targets=request.affected_targets,
        ),
        applied_rule_ids=(request.rule_id, definition.rule_id),
    )


def _closed_result(
    request: SpellTargetPreflightRequest,
    outcome: SpellTargetPreflightOutcome,
) -> SpellTargetPreflightResult:
    return SpellTargetPreflightResult(
        request_id=request.id,
        source_cast_id=request.source.resolution_id,
        selected_target_id=request.selected_target_id,
        outcome=outcome,
        definition=request.definition,
        execution_request=None,
        applied_rule_ids=(request.rule_id,),
    )
