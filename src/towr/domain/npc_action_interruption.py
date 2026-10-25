"""Exact skipped-Casting receipt validation shared by Broken Recover/Run.

PG1.4 Magic in the Old World / Interrupted Casting and Miscasts pp156-157.
No dispatch, rule discovery, resolution or RNG.
"""
from dataclasses import replace

from towr.domain.action_execution_models import SkippedCastingTestAfterActionResult
from towr.domain.magic_models import (
    MiscastPoolIncreaseRequest, MiscastPoolIncreaseSourceKind, MiscastPoolOutcome,
    MiscastPoolResolutionResult, MiscastRollRequest,
)
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.turn_models import ActionExecutionReceipt


def validate_npc_casting_interruption(
    state: NpcRosterCastingState, actor_id: str, action_id: str,
    receipt: ActionExecutionReceipt, interruption: SkippedCastingTestAfterActionResult | None,
) -> None:
    active = actor_id == state.wizard.actor_id and state.wizard.magic_state.casting_lore_id is not None
    if not active:
        if interruption is not None:
            raise ValueError('only the active Casting Wizard receives a skipped-Test die')
        return
    wizard = state.wizard
    identifier = action_id + ':skipped-casting'
    rule = 'RULE-MAGIC-004:skipped-casting-test'
    pool_rule = 'RULE-MAGIC-004:miscast-pool'
    magic = replace(wizard.magic_state, miscast_dice=wizard.magic_state.miscast_dice + 1)
    triggered = magic.miscast_dice > wizard.caster.wizard_level
    roll = (MiscastRollRequest(identifier + ':miscast-pool', identifier + ':increase',
                              wizard.actor_id, magic.miscast_dice, rule_id=pool_rule) if triggered else None)
    expected = SkippedCastingTestAfterActionResult(
        identifier, wizard.actor_id, receipt,
        MiscastPoolIncreaseRequest(identifier + ':increase', wizard.actor_id, 1,
            MiscastPoolIncreaseSourceKind.ACTION, action_id, rule, rule),
        MiscastPoolResolutionResult(identifier + ':miscast-pool', wizard.actor_id, magic,
            wizard.magic_state.miscast_dice, 1,
            MiscastPoolOutcome.MISCAST_TRIGGERED if triggered else MiscastPoolOutcome.ACCUMULATED,
            roll, (rule, pool_rule)),
        magic, state.consumed_execution_ids,
        (*state.consumed_execution_ids, action_id), (rule, pool_rule),
    )
    if interruption != expected:
        raise ValueError('skipped Casting result differs from the completed action/magic/history')
