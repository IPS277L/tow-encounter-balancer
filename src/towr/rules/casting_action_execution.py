from __future__ import annotations

from dataclasses import replace

from towr.domain.action_execution_models import (
    CastingActionMiscastPreparationRequest,
    CastingActionMiscastPreparationResult,
    CastingActionPostTestRequest,
    CastingActionPostTestResult,
    CastingAttemptExecutionRequest,
    CastingAttemptExecutionResult,
)
from towr.domain.magic_models import (
    CastingTestResult,
    MiscastPreparationRequest,
    MiscastPoolIncreaseSourceKind,
    MiscastRollRequest,
    MiscastPoolOutcome,
    MiscastPoolResolutionRequest,
    SpellCastRequest,
)
from towr.domain.turn_models import (
    ActionExecutionReceipt,
    CombatActionKind,
    ImproviseKind,
)
from towr.rules.casting_decision_resolution import resolve_casting_decision
from towr.rules.casting_test_resolution import resolve_casting_test
from towr.rules.dice import RandomSource
from towr.rules.miscast_pool_resolution import resolve_miscast_pool_increase
from towr.rules.miscast_resolution import prepare_miscast
from towr.rules.test_resolution import TestDecisionProvider


CASTING_IMPROVISE_EXECUTION_RULE_ID = (
    "RULE-COMBAT-004:casting-improvise-execution"
)
CASTING_POST_TEST_RULE_ID = "RULE-COMBAT-004:casting-post-test"
CASTING_MISCAST_PREPARATION_RULE_ID = (
    "RULE-COMBAT-004:casting-miscast-preparation"
)


def execute_casting_attempt(
    request: CastingAttemptExecutionRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> CastingAttemptExecutionResult:
    """Use one reserved spell Improvise slot for a single Casting Test."""
    turn = request.state.active_turn
    if turn is None:
        raise ValueError("an active combat turn is required")
    if turn.actor_id != request.actor_id:
        raise ValueError("the casting actor does not own the active turn")
    if request.slot_index > len(turn.action_slots):
        raise ValueError("the requested action slot has not been reserved")
    earlier_slots = turn.action_slots[: request.slot_index - 1]
    if any(not slot.executed for slot in earlier_slots):
        raise ValueError("earlier action slots must be executed first")

    slot = turn.action_slots[request.slot_index - 1]
    declaration = slot.declaration
    if (
        declaration.kind is not CombatActionKind.IMPROVISE
        or declaration.improvise_kind is not ImproviseKind.SPELL
    ):
        raise ValueError(
            "only a spell Improvise action slot can use this executor"
        )
    if slot.executed:
        raise ValueError("the casting action slot has already been executed")
    if declaration.improvise_approach_id != request.casting_request.lore_id:
        raise ValueError("spell Improvise approach must match the Casting Lore")

    casting = resolve_casting_test(
        request.casting_request,
        rng,
        decisions=decisions,
    )
    if casting.request_id != request.casting_request.id:
        raise ValueError("Casting Test result does not belong to the request")

    executed_slot = replace(
        slot,
        execution=ActionExecutionReceipt(
            id=request.id,
            executor_rule_id=CASTING_IMPROVISE_EXECUTION_RULE_ID,
            source_request_id=request.casting_request.id,
            result_request_id=casting.request_id,
        ),
    )
    updated_slots = tuple(
        executed_slot if item.index == request.slot_index else item
        for item in turn.action_slots
    )
    updated_turn = replace(turn, action_slots=updated_slots)
    updated_state = replace(request.state, active_turn=updated_turn)

    return CastingAttemptExecutionResult(
        request_id=request.id,
        actor_id=request.actor_id,
        slot_index=request.slot_index,
        previous_state=request.state,
        state=updated_state,
        slot=executed_slot,
        casting=casting,
        applied_rule_ids=(CASTING_IMPROVISE_EXECUTION_RULE_ID,),
    )


def resolve_casting_action_post_test(
    request: CastingActionPostTestRequest,
) -> CastingActionPostTestResult:
    """Apply Rule of Nine threshold, then resolve normal CAST or WAIT."""
    execution = request.execution
    casting = execution.casting
    _validate_casting_follow_ups(execution)

    state = casting.state
    miscast_pool = None
    if casting.follow_ups:
        miscast_pool = resolve_miscast_pool_increase(
            MiscastPoolResolutionRequest(
                id=f"{request.id}:miscast-pool",
                source=casting.follow_ups[0],
                state=state,
                wizard_level=request.wizard_level,
            )
        )
        state = miscast_pool.state

    triggered = (
        miscast_pool is not None
        and miscast_pool.outcome is MiscastPoolOutcome.MISCAST_TRIGGERED
    )
    if triggered:
        if request.decision is not None:
            raise ValueError(
                "triggered Miscast must be prepared before CAST or WAIT"
            )
        decision = None
    else:
        decision_request = request.decision
        if decision_request is None:
            raise ValueError("normal casting outcome requires CAST or WAIT")
        if decision_request.caster_id != execution.actor_id:
            raise ValueError("Casting decision actor does not match execution")
        if decision_request.wizard_level != request.wizard_level:
            raise ValueError("Casting decision uses another Wizard Level")
        if decision_request.state != state:
            raise ValueError(
                "Casting decision state must include post-Test Miscast Pool"
            )
        decision = resolve_casting_decision(decision_request)
        state = decision.state

    nested_rule_ids = (
        () if miscast_pool is None else miscast_pool.applied_rule_ids
    )
    decision_rule_ids = () if decision is None else decision.applied_rule_ids
    return CastingActionPostTestResult(
        request_id=request.id,
        execution=execution,
        wizard_level=request.wizard_level,
        state=state,
        miscast_pool=miscast_pool,
        decision=decision,
        applied_rule_ids=_unique_rule_ids(
            request.rule_id,
            *nested_rule_ids,
            *decision_rule_ids,
        ),
    )


def prepare_casting_action_miscast(
    request: CastingActionMiscastPreparationRequest,
) -> CastingActionMiscastPreparationResult:
    """Bind a triggered casting action to existing Miscast preparation."""
    post_test = request.post_test
    pool = post_test.miscast_pool
    if (
        pool is None
        or pool.outcome is not MiscastPoolOutcome.MISCAST_TRIGGERED
        or pool.roll_request is None
    ):
        raise ValueError("casting action has no triggered Miscast to prepare")
    if post_test.decision is not None:
        raise ValueError("triggered Miscast cannot follow a normal decision")

    preparation_request = request.preparation
    actor_id = post_test.execution.actor_id
    if preparation_request.source != pool.roll_request:
        raise ValueError(
            "Miscast preparation source must match post-Test roll request"
        )
    if preparation_request.rule_id != pool.roll_request.rule_id:
        raise ValueError("Miscast preparation must preserve the pool Rule ID")
    if preparation_request.state != post_test.state:
        raise ValueError(
            "Miscast preparation state must match post-Test state"
        )
    if preparation_request.source.target_id != actor_id:
        raise ValueError("Miscast preparation actor does not match execution")

    preparation = prepare_miscast(preparation_request)
    if preparation.request_id != preparation_request.id:
        raise ValueError("Miscast preparation result belongs to another request")
    if preparation.target_id != actor_id:
        raise ValueError("Miscast preparation result belongs to another actor")
    _validate_preparation_follow_ups(preparation_request, preparation.follow_ups)
    return CastingActionMiscastPreparationResult(
        request_id=request.id,
        post_test=post_test,
        preparation=preparation,
        state=preparation.state,
        applied_rule_ids=_unique_rule_ids(
            request.rule_id,
            *preparation.applied_rule_ids,
        ),
    )


def _validate_casting_follow_ups(
    execution: CastingAttemptExecutionResult,
) -> None:
    casting: CastingTestResult = execution.casting
    expected_nines = casting.test.trace.final_values.count(9)
    if casting.miscast_dice_added != expected_nines:
        raise ValueError("Casting result Miscast count does not match roll")
    if casting.state.casting_lore_id != casting.lore_id:
        raise ValueError("Casting result state uses another Magic Lore")
    if execution.slot.declaration.improvise_approach_id != casting.lore_id:
        raise ValueError("Casting result Lore does not match action slot")
    if not expected_nines:
        if casting.follow_ups:
            raise ValueError("Casting result has an unexpected follow-up")
        return
    if len(casting.follow_ups) != 1:
        raise ValueError("Casting result requires one Miscast Pool follow-up")
    source = casting.follow_ups[0]
    if source.target_id != execution.actor_id:
        raise ValueError("Miscast Pool follow-up targets another actor")
    if source.amount != expected_nines:
        raise ValueError("Miscast Pool follow-up has the wrong amount")
    if source.source_kind is not MiscastPoolIncreaseSourceKind.TEST:
        raise ValueError("Rule of Nine follow-up must reference a Test")
    if source.source_id != casting.test.trace.request_id:
        raise ValueError("Miscast Pool follow-up belongs to another Test")
    if source.resolution_id != f"{casting.request_id}:rule-of-nine":
        raise ValueError("Miscast Pool follow-up belongs to another casting")


def _validate_preparation_follow_ups(
    request: MiscastPreparationRequest,
    follow_ups: tuple[SpellCastRequest | MiscastRollRequest, ...],
) -> None:
    expected_count = 2 if request.spell_to_cast is not None else 1
    if len(follow_ups) != expected_count:
        raise ValueError("Miscast preparation returned invalid follow-ups")
    roll = follow_ups[-1]
    if not isinstance(roll, MiscastRollRequest):
        raise ValueError("Miscast preparation must end with a roll request")
    if (
        roll.target_id != request.source.target_id
        or roll.pool_dice_count != request.source.pool_dice_count
        or roll.source_resolution_id != request.source.source_resolution_id
    ):
        raise ValueError("prepared Miscast roll does not match its source")
    if request.spell_to_cast is None:
        if roll.bonus_dice != 0:
            raise ValueError("Miscast roll has an unexpected bonus die")
        return
    spell = follow_ups[0]
    if not isinstance(spell, SpellCastRequest):
        raise ValueError("spell must precede the prepared Miscast roll")
    if spell.caster_id != request.source.target_id:
        raise ValueError("pre-Miscast spell belongs to another actor")
    if roll.bonus_dice != 1:
        raise ValueError("pre-Miscast spell must add one roll die")


def _unique_rule_ids(*rule_ids: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(rule_ids))
