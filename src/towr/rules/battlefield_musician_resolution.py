"""Execute one Leadership action or free signal, PG1.4 III73 and ADR-0141 C17."""
from dataclasses import replace

from towr.domain.talent_battlefield_musician_models import (
    BATTLEFIELD_MUSICIAN_SIGNAL_RULE_ID, BattlefieldMusicianActionRequest,
    BattlefieldMusicianActionResult, BattlefieldMusicianSignalReceipt,
    BattlefieldMusicianSignalRequest, BattlefieldMusicianSignalResult,
    _action_values, _heard_listeners,
)
from towr.domain.test_models import TestResult
from towr.rules.dice import RandomSource
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


def execute_battlefield_musician_action(request: BattlefieldMusicianActionRequest,
        rng: RandomSource, *, decisions: TestDecisionProvider | None = None
        ) -> BattlefieldMusicianActionResult:
    if type(request) is not BattlefieldMusicianActionRequest:
        raise TypeError('musician action requires its exact complete request')
    replace(request)
    result = resolve_test(request.leadership_test, rng, decisions=decisions)
    return complete_battlefield_musician_action(request, result)


def complete_battlefield_musician_action(request: BattlefieldMusicianActionRequest,
        test_result: TestResult) -> BattlefieldMusicianActionResult:
    """Complete the final prepared Test, including external Fate, with no RNG."""
    selected, slot, updated, rules = _action_values(request, test_result)
    return BattlefieldMusicianActionResult(request.id, request, test_result,
        selected, request.round_state, updated, slot, rules)


def issue_battlefield_musician_signal(request: BattlefieldMusicianSignalRequest
        ) -> BattlefieldMusicianSignalResult:
    if type(request) is not BattlefieldMusicianSignalRequest:
        raise TypeError('musician signal requires its exact complete request')
    replace(request)
    heard = _heard_listeners(request.round_state, request.source,
        request.listeners, inspiration=False)
    receipt = BattlefieldMusicianSignalReceipt(request.id, request.source,
        request.round_state, request.actor_conditions, request.kind, request.listeners,
        tuple(listener.actor_id for listener in heard),
        (BATTLEFIELD_MUSICIAN_SIGNAL_RULE_ID,), audience_participants=request.audience_participants)
    return BattlefieldMusicianSignalResult(request, receipt, (*request.previous_receipts, receipt))
