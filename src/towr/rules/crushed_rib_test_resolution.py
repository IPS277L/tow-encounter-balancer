"""Prepare/execute/complete one injury-bound Crushed Rib Test (ADR-0055)."""
from dataclasses import replace

from towr.domain.crushed_rib_test_models import (
    CrushedRibTestPreparationRequest, CrushedRibCastingPreparationRequest,
    CrushedRibTestPreparationResult, CrushedRibCastingPreparationResult,
    CrushedRibTestResult, CrushedRibCastingResult, _drained_request, _injury,
    _consumed_state, _identifier, _typed,
)
from towr.domain.injury_models import CharacterInjuryState
from towr.domain.magic_models import CastingTestResult
from towr.domain.test_models import TestResult
from towr.rules.casting_test_resolution import resolve_casting_test
from towr.rules.dice import RandomSource
from towr.rules.drained_test_resolution import prepare_drained_test
from towr.rules.test_resolution import resolve_test


def prepare_crushed_rib_test(request: CrushedRibTestPreparationRequest) -> CrushedRibTestPreparationResult:
    _typed(request, CrushedRibTestPreparationRequest)
    replace(request)
    drained = prepare_drained_test(_drained_request(request))
    return CrushedRibTestPreparationResult(request, _injury(request.state), drained, drained.test)


def prepare_crushed_rib_casting(request: CrushedRibCastingPreparationRequest) -> CrushedRibCastingPreparationResult:
    _typed(request, CrushedRibCastingPreparationRequest)
    replace(request)
    drained = prepare_drained_test(_drained_request(request))
    return CrushedRibCastingPreparationResult(request, _injury(request.state), drained,
                                             replace(request.casting, test=drained.test))


def complete_crushed_rib_test(preparation: CrushedRibTestPreparationResult, test: TestResult) -> CrushedRibTestResult:
    _typed(preparation, CrushedRibTestPreparationResult)
    replace(preparation)
    return CrushedRibTestResult(preparation, test, preparation.effect, _consumed_state(preparation))


def complete_crushed_rib_casting(preparation: CrushedRibCastingPreparationResult,
                                casting: CastingTestResult) -> CrushedRibCastingResult:
    _typed(preparation, CrushedRibCastingPreparationResult)
    replace(preparation)
    return CrushedRibCastingResult(preparation, casting, preparation.effect, _consumed_state(preparation))


def resolve_crushed_rib_test(preparation: CrushedRibTestPreparationResult, rng: RandomSource) -> CrushedRibTestResult:
    _typed(preparation, CrushedRibTestPreparationResult)
    replace(preparation)
    return complete_crushed_rib_test(preparation, resolve_test(preparation.test, rng))


def resolve_crushed_rib_casting(preparation: CrushedRibCastingPreparationResult, rng: RandomSource) -> CrushedRibCastingResult:
    _typed(preparation, CrushedRibCastingPreparationResult)
    replace(preparation)
    return complete_crushed_rib_casting(preparation, resolve_casting_test(preparation.casting, rng))


def apply_crushed_rib_test_result(actor_id: str, current_injury: CharacterInjuryState,
                                 result: CrushedRibTestResult | CrushedRibCastingResult) -> CharacterInjuryState:
    _identifier(actor_id)
    if not isinstance(result, (CrushedRibTestResult, CrushedRibCastingResult)):
        raise TypeError('Crushed Rib application requires a typed completed result')
    replace(result)
    _injury(current_injury, pending=None)
    source = result.source.source_request
    if actor_id != source.actor_id or current_injury != source.state:
        raise ValueError('Crushed Rib application belongs to another actor or stale injury')
    return result.state
