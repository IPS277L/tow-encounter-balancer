from __future__ import annotations

from towr.domain.magic_models import (
    MiscastPoolIncreaseRequest,
    MiscastPoolIncreaseSourceKind,
    NpcWizardCastingOppositionOutcome,
    NpcWizardCastingOppositionRequest,
    NpcWizardCastingOppositionResult,
)
from towr.rules.miscast_pool_resolution import RULE_OF_NINE_RULE_ID


class MissingCastingOppositionResultError(RuntimeError):
    pass


class InvalidCastingOppositionResultError(ValueError):
    pass


def resolve_npc_wizard_casting_opposition(
    request: NpcWizardCastingOppositionRequest,
) -> NpcWizardCastingOppositionResult:
    if request.has_opposed_casting_this_round:
        return _unavailable(
            request,
            NpcWizardCastingOppositionOutcome.UNAVAILABLE_ALREADY_USED,
            opposition_used_this_round=True,
        )
    if not request.caster_in_long_range:
        return _unavailable(
            request,
            NpcWizardCastingOppositionOutcome.UNAVAILABLE_OUT_OF_RANGE,
            opposition_used_this_round=False,
        )
    if request.opposition is None:
        raise MissingCastingOppositionResultError(
            "an available declared opposition requires a completed "
            "OpposedTestResult"
        )

    opposition = request.opposition
    if opposition.request_id != request.opposed_test_id:
        raise InvalidCastingOppositionResultError(
            "opposition result must belong to the declared Opposed Test"
        )
    if opposition.initiator.trace.request_id != request.casting_test_id:
        raise InvalidCastingOppositionResultError(
            "opposition initiator must be the declared Casting Test"
        )
    if (
        opposition.opponent.trace.request_id
        != request.reactor_willpower_test_id
    ):
        raise InvalidCastingOppositionResultError(
            "opposition opponent must be the reacting Wizard's Willpower Test"
        )

    reactor_trace = opposition.opponent.trace
    if any(item.original == 9 for item in reactor_trace.rerolls):
        raise InvalidCastingOppositionResultError(
            "Rule of Nine dice cannot be rerolled, even on a Glorious Test"
        )
    miscast_dice = reactor_trace.final_values.count(9)
    follow_ups = (
        (
            MiscastPoolIncreaseRequest(
                resolution_id=request.id,
                target_id=request.reactor_id,
                amount=miscast_dice,
                source_kind=MiscastPoolIncreaseSourceKind.TEST,
                source_id=request.reactor_willpower_test_id,
                trigger_rule_id=request.rule_id,
                rule_id=RULE_OF_NINE_RULE_ID,
            ),
        )
        if miscast_dice
        else ()
    )
    return NpcWizardCastingOppositionResult(
        request_id=request.id,
        caster_id=request.caster_id,
        reactor_id=request.reactor_id,
        outcome=NpcWizardCastingOppositionOutcome.RESOLVED,
        opposition=opposition,
        opposition_used_this_round=True,
        miscast_dice_added=miscast_dice,
        follow_ups=follow_ups,
        applied_rule_ids=(request.rule_id, RULE_OF_NINE_RULE_ID),
    )


def _unavailable(
    request: NpcWizardCastingOppositionRequest,
    outcome: NpcWizardCastingOppositionOutcome,
    *,
    opposition_used_this_round: bool,
) -> NpcWizardCastingOppositionResult:
    if request.opposition is not None:
        raise InvalidCastingOppositionResultError(
            "an unavailable opposition must not contain a completed Test"
        )
    return NpcWizardCastingOppositionResult(
        request_id=request.id,
        caster_id=request.caster_id,
        reactor_id=request.reactor_id,
        outcome=outcome,
        opposition=None,
        opposition_used_this_round=opposition_used_this_round,
        miscast_dice_added=0,
        follow_ups=(),
        applied_rule_ids=(request.rule_id,),
    )
