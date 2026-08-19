from __future__ import annotations

from dataclasses import replace

from towr.domain.magic_models import (
    CastingChoice,
    CastingDecisionRequest,
    CastingDecisionResult,
    SpellCastRequest,
)


CAST_OR_WAIT_RULE_ID = "RULE-MAGIC-004:cast-or-wait"


def resolve_casting_decision(
    request: CastingDecisionRequest,
) -> CastingDecisionResult:
    if request.choice is CastingChoice.WAIT:
        return CastingDecisionResult(
            request_id=request.id,
            caster_id=request.caster_id,
            choice=request.choice,
            state=request.state,
            previous_casting_successes=request.state.casting_successes,
            base_potency=None,
            follow_ups=(),
            applied_rule_ids=(request.rule_id,),
        )

    spell = request.selected_spell
    assert spell is not None
    base_potency = request.state.latest_casting_roll_successes
    cast_request = SpellCastRequest(
        resolution_id=f"{request.id}:cast",
        caster_id=request.caster_id,
        spell_rule_id=spell.spell_rule_id,
        lore_id=spell.lore_id,
        casting_value=spell.casting_value,
        base_potency=base_potency,
        rule_id=request.rule_id,
    )
    return CastingDecisionResult(
        request_id=request.id,
        caster_id=request.caster_id,
        choice=request.choice,
        state=replace(
            request.state,
            casting_successes=0,
            casting_lore_id=None,
            latest_casting_roll_successes=0,
        ),
        previous_casting_successes=request.state.casting_successes,
        base_potency=base_potency,
        follow_ups=(cast_request,),
        applied_rule_ids=(request.rule_id,),
    )
