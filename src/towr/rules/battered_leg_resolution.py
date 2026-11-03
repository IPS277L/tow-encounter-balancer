"""Execution of the source-bound Battered Leg Endurance Test."""

from dataclasses import replace

from towr.domain.battered_leg_models import (
    BatteredLegEnduranceTestRequest,
    BatteredLegEnduranceTestResult,
)
from towr.rules.dice import RandomSource
from towr.rules.test_resolution import resolve_test
from towr.rules.wound_effect_resolution import resolve_wound_endurance_test


def execute_battered_leg_endurance_test(
    request: BatteredLegEnduranceTestRequest,
    rng: RandomSource,
) -> BatteredLegEnduranceTestResult:
    """Roll the supplied Endurance Test, then apply only its Battered Leg follow-up."""
    if not isinstance(request, BatteredLegEnduranceTestRequest):
        raise TypeError("request must be a BatteredLegEnduranceTestRequest")
    replace(request)
    test_result = resolve_test(request.endurance_test, rng)
    wound_result = resolve_wound_endurance_test(
        request.wound_test,
        request.injury_state,
        test_result,
    )
    return BatteredLegEnduranceTestResult(request, test_result, wound_result)
