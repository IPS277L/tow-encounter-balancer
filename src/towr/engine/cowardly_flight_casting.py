"""One Casting action; no end-turn, battle loop or Miscast completion (ADR-0035)."""
from __future__ import annotations

from dataclasses import replace

from towr.domain.cowardly_flight_casting_completion_models import (
    CowardlyFlightCastingCompletionRequest, CowardlyFlightCastingCompletionResult,
)

from towr.domain.action_execution_models import CastingActionPostTestRequest, CastingAttemptExecutionRequest
from towr.domain.cowardly_flight_casting_models import CowardlyFlightCastingRequest
from towr.domain.cowardly_flight_casting_result_models import (
    CowardlyFlightCastingResult, CowardlyFlightCastingStatus,
)
from towr.domain.magic_models import (
    COWARDLY_FLIGHT_SPELL_DEFINITION as SPELL, CastingChoice, CastingDecisionRequest,
    CastingSpellSelection, CastingTestRequest, IdentifiedSpellTarget, MiscastPoolOutcome,
    MiscastPoolResolutionRequest, SpellTargetKind, SpellTargetPreflightRequest,
)
from towr.domain.resolution_models import (
    CowardlyFlightSpellEffectRequest, CowardlyFlightWillpowerBatchRequest, CowardlyFlightZoneBatchRequest,
)
from towr.domain.test_models import TestRequest
from towr.rules.casting_action_execution import execute_casting_attempt, resolve_casting_action_post_test
from towr.rules.cowardly_flight_resolution import (
    resolve_cowardly_flight_willpower_batch, resolve_cowardly_flight_zone_batch,
)
from towr.rules.dice import RandomSource
from towr.rules.miscast_pool_resolution import resolve_miscast_pool_increase
from towr.rules.spell_cast_execution import resolve_spell_cast_targets
from towr.rules.spell_target_preflight import resolve_spell_target_preflight


def execute_cowardly_flight_casting(
    request: CowardlyFlightCastingRequest, rng: RandomSource,
) -> CowardlyFlightCastingResult:
    """Execute CAST_WHEN_READY once, preserving a triggered Miscast as pending.

    The returned round still has the active turn, with the action consumed.
    Errors propagate without retry, RNG rewind, or a partial result.
    """
    if not isinstance(request, CowardlyFlightCastingRequest):
        raise TypeError("request must be a CowardlyFlightCastingRequest")
    execution = execute_casting_attempt(CastingAttemptExecutionRequest(
        request.id, request.round_state, request.actor_id, request.slot_index,
        CastingTestRequest(request.id + ":casting", request.actor_id, SPELL.lore_id,
                           TestRequest(request.id + ":willpower", request.caster.casting_profile),
                           request.magic_state),
    ), rng)
    identifier = request.id + ":post-test"
    state = execution.casting.state
    triggered = False
    if execution.casting.follow_ups:
        # Pure projection needed by the decision request. Post-Test receives the
        # original execution and independently verifies this same pool transition.
        pool = resolve_miscast_pool_increase(MiscastPoolResolutionRequest(
            identifier + ":miscast-pool", execution.casting.follow_ups[0], state,
            request.caster.wizard_level))
        state = pool.state
        triggered = pool.outcome is MiscastPoolOutcome.MISCAST_TRIGGERED
    decision = None
    if not triggered:
        ready = state.casting_successes >= SPELL.casting_value
        decision = CastingDecisionRequest(
            identifier + ":decision", request.actor_id, state, request.caster.wizard_level,
            CastingChoice.CAST if ready else CastingChoice.WAIT,
            CastingSpellSelection(SPELL.rule_id, SPELL.lore_id, SPELL.casting_value) if ready else None,
        )
    post = resolve_casting_action_post_test(CastingActionPostTestRequest(
        identifier, execution, request.caster.wizard_level, decision))
    if triggered:
        return CowardlyFlightCastingResult(request, execution, post, CowardlyFlightCastingStatus.MISCAST_REQUIRED)
    if post.decision.choice is CastingChoice.WAIT:
        return CowardlyFlightCastingResult(request, execution, post, CowardlyFlightCastingStatus.WAITING)

    cast = post.decision.follow_ups[0]
    preflight = resolve_spell_target_preflight(SpellTargetPreflightRequest(
        request.id + ":preflight", cast, SPELL, request.selected_zone_id, SpellTargetKind.ZONE,
        request.facts.target_zone_within_long_range,
        tuple(IdentifiedSpellTarget(t.actor_id) for t in request.targets),
    ))
    spell = resolve_spell_cast_targets(preflight.execution_request)
    targets = {t.actor_id: t for t in request.targets}
    contexts = tuple(CowardlyFlightSpellEffectRequest(
        effect, targets[effect.target_id].can_give_ground,
        TestRequest(effect.resolution_id + ":willpower", targets[effect.target_id].willpower_profile),
        targets[effect.target_id].injury,
    ) for effect in spell.follow_ups)
    zone = resolve_cowardly_flight_zone_batch(CowardlyFlightZoneBatchRequest(
        request.id + ":zone", spell, contexts))
    if zone.movement_follow_ups:
        return CowardlyFlightCastingResult(
            request, execution, post, CowardlyFlightCastingStatus.MOVEMENT_REQUIRED,
            preflight, spell, zone)
    willpower = resolve_cowardly_flight_willpower_batch(CowardlyFlightWillpowerBatchRequest(
        request.id + ":willpower-batch", zone, request.spatial_state, ()), rng)
    return CowardlyFlightCastingResult(request, execution, post, CowardlyFlightCastingStatus.SPELL_RESOLVED,
                                       preflight, spell, zone, willpower)


def complete_cowardly_flight_casting(
    request: CowardlyFlightCastingCompletionRequest, rng: RandomSource,
) -> CowardlyFlightCastingCompletionResult:
    """Resolve only Willpower after all source-bound movements; no Casting retry."""
    if not isinstance(request, CowardlyFlightCastingCompletionRequest):
        raise TypeError("request must be a CowardlyFlightCastingCompletionRequest")
    pending = request.pending
    willpower = resolve_cowardly_flight_willpower_batch(CowardlyFlightWillpowerBatchRequest(
        pending.source.id + ":willpower-batch", pending.zone,
        request.spatial_state_after_movements, request.movement_completions), rng)
    casting = replace(pending, status=CowardlyFlightCastingStatus.SPELL_RESOLVED, willpower=willpower)
    return CowardlyFlightCastingCompletionResult(request, casting)


def apply_cowardly_flight_casting_completion(
    current: CowardlyFlightCastingResult, result: CowardlyFlightCastingCompletionResult,
) -> CowardlyFlightCastingResult:
    """Replace the exact current pending result once, without movement or RNG."""
    if not isinstance(current, CowardlyFlightCastingResult):
        raise TypeError("current must be a CowardlyFlightCastingResult")
    if not isinstance(result, CowardlyFlightCastingCompletionResult):
        raise TypeError("result must be a CowardlyFlightCastingCompletionResult")
    if current.status is not CowardlyFlightCastingStatus.MOVEMENT_REQUIRED:
        raise ValueError("Curse completion was already consumed or movement is not pending")
    if current != result.source.pending:
        raise ValueError("Curse completion belongs to a different current pending result")
    return result.casting
