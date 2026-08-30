from __future__ import annotations

from typing import Protocol

from towr.domain.fate_models import (
    FATE_TACTICAL_RETREAT_RULE_ID,
    FateTacticalRetreatProof,
)
from towr.domain.retreat_models import (
    RETREAT_ALTERNATIVE_PRICE_RULE_ID,
    RETREAT_PURSUIT_RULE_ID,
    RETREAT_RULE_ID,
    RUN_FOR_YOUR_LIVES_RULE_ID,
    GroupRetreatDeclaration,
    RetreatAlternativePriceDecision,
    RetreatAlternativePriceRequest,
    RetreatAlternativePriceResolutionResult,
    RetreatEscapeMethod,
    RetreatEscapeOutcome,
    RetreatEscapeResult,
    RetreatEscapeTestResult,
    RetreatMarginalChoice,
    RetreatMarginalDecision,
    RetreatPursuitResolutionRequest,
    RetreatPursuitResolutionResult,
    RetreatRearGuardResult,
    RunForYourLivesResolutionRequest,
    RunForYourLivesResolutionResult,
    RunForYourLivesRoll,
    RunForYourLivesRollReason,
    _escape_test_is_marginal,
    _escape_test_succeeded,
    _pursuit_rule_ids,
    _retreat_alternative_price_application,
    _retreat_alternative_price_proof,
    _run_for_your_lives_campaign_consequence,
    classify_run_for_your_lives,
)
from towr.domain.test_models import OpposedTestRequest
from towr.rules.dice import RandomSource
from towr.rules.opposed_test import resolve_opposed_test
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


class MissingRetreatMarginalDecisionError(RuntimeError):
    pass


class InvalidRetreatMarginalDecisionError(ValueError):
    pass


class RetreatMarginalDecisionProvider(Protocol):
    def choose_marginal_outcome(
        self,
        *,
        request: RetreatPursuitResolutionRequest,
        attempt_index: int,
        test_result: RetreatEscapeTestResult,
    ) -> RetreatMarginalDecision: ...


def resolve_retreat_alternative_price(
    request: RetreatAlternativePriceRequest,
    decision: RetreatAlternativePriceDecision,
) -> RetreatAlternativePriceResolutionResult:
    """Choose one book-defined no-Fate price without applying its effect."""
    if request.rule_id != RETREAT_ALTERNATIVE_PRICE_RULE_ID:
        raise ValueError("alternative Retreat price uses an unknown rule")
    if not isinstance(decision, RetreatAlternativePriceDecision):
        raise TypeError("decision must be a RetreatAlternativePriceDecision")
    if decision.price not in request.possible_prices:
        raise ValueError("the selected Retreat price is not available")
    proof = _retreat_alternative_price_proof(request, decision)
    return RetreatAlternativePriceResolutionResult(
        request_id=request.id,
        source_request=request,
        decision=decision,
        proof=proof,
        application_request=_retreat_alternative_price_application(
            request,
            proof,
        ),
        covered_player_character_ids=request.source_retreat.player_character_ids,
        pursuit_decision_required=True,
        applied_rule_ids=(
            request.source_retreat.rule_id,
            request.rule_id,
        ),
    )


def secure_group_retreat(
    request: GroupRetreatDeclaration,
    *,
    fate_proof: FateTacticalRetreatProof,
) -> RetreatRearGuardResult:
    """Bind a validated group Retreat to its Fate-funded rearguard."""
    if request.rule_id != RETREAT_RULE_ID:
        raise ValueError("group Retreat uses an unknown rule")
    if not isinstance(fate_proof, FateTacticalRetreatProof):
        raise TypeError("fate_proof must be a FateTacticalRetreatProof")
    if (
        fate_proof.rule_id != FATE_TACTICAL_RETREAT_RULE_ID
        or fate_proof.retreat_id != request.id
        or fate_proof.battle_id != request.battle_id
        or fate_proof.player_character_ids != request.player_character_ids
        or fate_proof.actor_id not in request.player_character_ids
    ):
        raise ValueError("Fate proof belongs to another group Retreat")
    return RetreatRearGuardResult(
        request_id=request.id,
        source_request=request,
        rearguard_actor_id=fate_proof.actor_id,
        fate_proof_id=fate_proof.id,
        source_spend_id=fate_proof.source_spend_id,
        covered_player_character_ids=request.player_character_ids,
        pursuit_decision_required=True,
        applied_rule_ids=(RETREAT_RULE_ID, fate_proof.rule_id),
    )


def resolve_retreat_pursuit(
    request: RetreatPursuitResolutionRequest,
    rng: RandomSource,
    *,
    test_decisions: TestDecisionProvider | None = None,
    marginal_decisions: RetreatMarginalDecisionProvider | None = None,
) -> RetreatPursuitResolutionResult:
    """Resolve the ordered PC escape attempts after a covered Retreat."""
    if request.rule_id != RETREAT_PURSUIT_RULE_ID:
        raise ValueError("Retreat pursuit uses an unknown rule")
    results: list[RetreatEscapeResult] = []
    for index, attempt in enumerate(request.attempts):
        if attempt.method is RetreatEscapeMethod.LORE_AUTOMATIC_SUCCESS:
            results.append(
                RetreatEscapeResult(
                    attempt=attempt,
                    test_result=None,
                    marginal_decision=None,
                    outcome=RetreatEscapeOutcome.AUTOMATIC_SUCCESS,
                )
            )
            continue
        test = attempt.test
        if isinstance(test, OpposedTestRequest):
            test_result = resolve_opposed_test(
                test,
                rng,
                decisions=test_decisions,
            )
        else:
            assert test is not None
            test_result = resolve_test(
                test,
                rng,
                decisions=test_decisions,
            )
        marginal_decision = None
        if _escape_test_succeeded(test_result) and _escape_test_is_marginal(
            test_result
        ):
            if marginal_decisions is None:
                raise MissingRetreatMarginalDecisionError(
                    "a marginal Retreat success requires an explicit decision"
                )
            marginal_decision = marginal_decisions.choose_marginal_outcome(
                request=request,
                attempt_index=index,
                test_result=test_result,
            )
            if not isinstance(marginal_decision, RetreatMarginalDecision):
                raise InvalidRetreatMarginalDecisionError(
                    "Retreat marginal provider returned an invalid decision"
                )
        chose_failure = (
            marginal_decision is not None
            and marginal_decision.choice is RetreatMarginalChoice.CHOOSE_FAILURE
        )
        outcome = (
            RetreatEscapeOutcome.SUCCESS
            if _escape_test_succeeded(test_result) and not chose_failure
            else RetreatEscapeOutcome.FAILURE
        )
        results.append(
            RetreatEscapeResult(
                attempt=attempt,
                test_result=test_result,
                marginal_decision=marginal_decision,
                outcome=outcome,
            )
        )

    escape_results = tuple(results)
    failed_actor_ids = tuple(
        item.attempt.actor_id for item in escape_results if not item.succeeded
    )
    complication_actor_ids = tuple(
        item.attempt.actor_id
        for item in escape_results
        if item.complication_id is not None
    )
    complication_ids = tuple(
        item.complication_id
        for item in escape_results
        if item.complication_id is not None
    )
    return RetreatPursuitResolutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        was_pursued=request.is_pursued,
        escape_results=escape_results,
        failed_actor_ids=failed_actor_ids,
        complication_actor_ids=complication_actor_ids,
        complication_ids=complication_ids,
        mandatory_table_roll_count=len(failed_actor_ids),
        complication_table_roll_option_available=(
            not failed_actor_ids and len(complication_actor_ids) >= 2
        ),
        applied_rule_ids=_pursuit_rule_ids(request, escape_results),
    )


def resolve_run_for_your_lives(
    request: RunForYourLivesResolutionRequest,
    rng: RandomSource,
) -> RunForYourLivesResolutionResult:
    """Roll and aggregate the page 120 table without applying campaign state."""
    if request.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
        raise ValueError("Run For Your Lives uses an unknown rule")
    pursuit = request.source_pursuit
    rolls = tuple(
        RunForYourLivesRoll(
            reason=RunForYourLivesRollReason.FAILED_ESCAPE,
            failed_actor_id=actor_id,
            value=rng.randint(1, 10),
        )
        for actor_id in pursuit.failed_actor_ids
    )
    if request.include_complication_roll:
        rolls += (
            RunForYourLivesRoll(
                reason=RunForYourLivesRollReason.MULTIPLE_COMPLICATIONS,
                source_complication_ids=pursuit.complication_ids,
                value=rng.randint(1, 10),
            ),
        )
    table_total = sum(item.value for item in rolls)
    outcome = classify_run_for_your_lives(table_total) if rolls else None
    return RunForYourLivesResolutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        rolls=rolls,
        table_total=table_total,
        outcome=outcome,
        campaign_consequence=_run_for_your_lives_campaign_consequence(
            request,
            table_total,
            outcome,
        ),
        applied_rule_ids=tuple(
            dict.fromkeys(
                (*pursuit.applied_rule_ids, request.rule_id)
            )
        ),
    )
