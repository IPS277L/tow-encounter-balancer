from __future__ import annotations

from dataclasses import replace

from towr.domain.infection_prevention_models import (
    ANATOMY_INFECTION_ALLOCATION_RULE_ID,
    ANATOMY_INFECTION_RECALL_RULE_ID,
    AUTOMATIC_INFECTION_SUCCESS_APPLICATION_RULE_ID,
    AUTOMATIC_INFECTION_SUCCESS_RULE_ID,
    AnatomyInfectionAllocationRequest,
    AnatomyInfectionAllocationResult,
    AnatomyInfectionRecallRequest,
    AnatomyInfectionRecallResult,
    AutomaticInfectionSuccessApplicationRequest,
    AutomaticInfectionSuccessApplicationResult,
    _allocation_proofs,
    _selected_proof,
)
from towr.rules.dice import RandomSource
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


def resolve_anatomy_infection_recall(
    request: AnatomyInfectionRecallRequest,
    rng: RandomSource,
    *,
    decisions: TestDecisionProvider | None = None,
) -> AnatomyInfectionRecallResult:
    """Resolve Anatomy Recall and expose one target slot per success."""
    if request.rule_id != ANATOMY_INFECTION_RECALL_RULE_ID:
        raise ValueError("Anatomy Infection Recall uses an unknown rule")
    test_result = resolve_test(request.recall_test, rng, decisions=decisions)
    return AnatomyInfectionRecallResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        test_result=test_result,
        available_successes=test_result.successes,
        applied_rule_ids=tuple(
            dict.fromkeys(
                (request.rule_id, *test_result.trace.applied_rule_ids)
            )
        ),
    )


def allocate_anatomy_infection_successes(
    request: AnatomyInfectionAllocationRequest,
) -> AnatomyInfectionAllocationResult:
    """Allocate Recall successes to ordered unique self/allied targets."""
    if request.rule_id != ANATOMY_INFECTION_ALLOCATION_RULE_ID:
        raise ValueError("Anatomy Infection allocation uses an unknown rule")
    proofs = _allocation_proofs(request)
    return AnatomyInfectionAllocationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        proofs=proofs,
        allocated_successes=len(proofs),
        unused_successes=request.recall.available_successes - len(proofs),
        previous_consumed_recall_ids=request.consumed_recall_ids,
        consumed_recall_ids=(
            *request.consumed_recall_ids,
            request.recall.request_id,
        ),
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    *request.recall.applied_rule_ids,
                    *((AUTOMATIC_INFECTION_SUCCESS_RULE_ID,) if proofs else ()),
                )
            )
        ),
    )


def apply_automatic_infection_success(
    request: AutomaticInfectionSuccessApplicationRequest,
) -> AutomaticInfectionSuccessApplicationResult:
    """Close one target's Infection day without an Endurance Test."""
    if request.rule_id != AUTOMATIC_INFECTION_SUCCESS_APPLICATION_RULE_ID:
        raise ValueError("automatic Infection success uses an unknown rule")
    proof = _selected_proof(request.allocation, request.proof_id)
    return AutomaticInfectionSuccessApplicationResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        proof=proof,
        target_id=request.target_id,
        previous_daily_wounds=request.daily_wounds,
        daily_wounds=replace(
            request.daily_wounds,
            closed_by_infection_id=request.id,
        ),
        injury_state=request.injury_state,
        previous_festering_wound_state=request.festering_wound_state,
        festering_wound_state=request.festering_wound_state,
        previous_consumed_proof_ids=request.consumed_proof_ids,
        consumed_proof_ids=(*request.consumed_proof_ids, proof.id),
        applied_rule_ids=tuple(
            dict.fromkeys(
                (
                    request.rule_id,
                    proof.rule_id,
                    *request.allocation.applied_rule_ids,
                )
            )
        ),
    )
