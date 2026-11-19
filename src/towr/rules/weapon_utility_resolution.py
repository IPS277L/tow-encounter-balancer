"""Resolve the actual PG93 Stealth/Toil item Test with an explicit RNG."""
from dataclasses import replace

from towr.domain.weapon_utility_models import (
    WeaponUtilityPreparation, WeaponUtilityRequest, WeaponUtilityResult,
    _drained_source,
)
from towr.rules.dice import RandomSource
from towr.rules.drained_test_resolution import prepare_drained_test
from towr.rules.test_resolution import TestDecisionProvider, resolve_test


def prepare_weapon_utility(request: WeaponUtilityRequest) -> WeaponUtilityPreparation:
    if type(request) is not WeaponUtilityRequest:
        raise TypeError('weapon utility requires its exact typed request')
    replace(request)
    return WeaponUtilityPreparation(request, request.inventory.item(request.item_id),
        prepare_drained_test(_drained_source(request)))


def execute_weapon_utility(preparation: WeaponUtilityPreparation, rng: RandomSource,
        *, decisions: TestDecisionProvider | None = None) -> WeaponUtilityResult:
    if type(preparation) is not WeaponUtilityPreparation:
        raise TypeError('weapon utility execution requires its exact prepared source')
    replace(preparation)
    return WeaponUtilityResult(preparation, resolve_test(preparation.test, rng, decisions=decisions))
