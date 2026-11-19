"""Actual-item utility Tests, without combat actions or invented scene effects.

PG1.4 IV93 grants a concealment die to Dagger/Knuckledusters and a resource
harvesting die to Pickaxe. The caller owns the complete Stealth/Toil Test and
actual inventory/hand facts. Success does not itself set Hidden, create an
ambush, award resources, move equipment or advance a clock.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum

from towr.domain.condition_models import ConditionState
from towr.domain.drained_test_models import (
    DRAINED_TEST_PREPARATION_RULE_ID, DrainedTestPreparationRequest,
    DrainedTestPreparationResult, _expected_drained_test_preparation,
)
from towr.domain.lucky_models import LuckyGamblingProof
from towr.domain.test_models import (
    DiceModifier, FateGloriousProof, InitialTestRoll, InlineProfile,
    QualityModifier, RerollLock, RerollTrace, RollTrace, Skill,
    SuccessModifier, TestProfile, TestQuality, TestRequest, TestResult,
    _expected_initial_roll_parameters,
)
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_effect_preparation import (
    DAGGER_CONCEALMENT_RULE_ID, KNUCKLEDUSTERS_CONCEALMENT_RULE_ID,
    PICKAXE_HARVEST_RULE_ID, weapon_kind_test_modifiers,
)
from towr.domain.weapon_inventory_models import (
    WeaponGrip, WeaponInventoryState, WeaponItemLocation, WeaponUnitState,
)


class WeaponUtilityKind(str, Enum):
    CONCEAL_WEAPON = 'conceal_weapon'
    HARVEST = 'harvest'


_UTILITY_RULE_IDS = frozenset((DAGGER_CONCEALMENT_RULE_ID,
    KNUCKLEDUSTERS_CONCEALMENT_RULE_ID, PICKAXE_HARVEST_RULE_ID))


def _identifier(value, label):
    if type(value) is not str or not value.strip():
        raise TypeError(label + ' requires an exact nonempty identifier')


def _typed(value, expected):
    if type(value) is not expected:
        raise TypeError('weapon utility requires exact ' + expected.__name__)
    return replace(value)


def _test(request):
    _typed(request, TestRequest)
    _identifier(request.id, 'actual utility Test')
    if type(request.profile) not in (TestProfile, InlineProfile):
        raise TypeError('weapon utility requires an actual book or inline Test profile')
    replace(request.profile)
    for name, kind in (('dice_modifiers', DiceModifier), ('quality_modifiers', QualityModifier),
            ('success_modifiers', SuccessModifier), ('reroll_locks', RerollLock)):
        values = getattr(request, name)
        if type(values) is not tuple:
            raise TypeError('weapon utility Test collections require exact tuples')
        for value in values:
            _typed(value, kind)
            _identifier(value.rule_id, 'utility Test Rule ID')
            if kind is DiceModifier and type(value.bypasses_pool_cap) is not bool:
                raise TypeError('a utility dice modifier requires an exact cap-bypass bool')


def _modifiers(request):
    item = request.inventory.item(request.item_id)
    return weapon_kind_test_modifiers(item.kind, request.skill, request.conditions,
        concealing_weapon=request.kind is WeaponUtilityKind.CONCEAL_WEAPON,
        harvesting_resources=request.kind is WeaponUtilityKind.HARVEST)


def _drained_source(request):
    test = replace(request.test,
        dice_modifiers=(*request.test.dice_modifiers, *_modifiers(request)))
    return DrainedTestPreparationRequest(request.id + ':drained', request.actor_id,
        request.conditions, test, fate_glorious_proofs=request.fate_glorious_proofs,
        lucky_gambling_proofs=request.lucky_gambling_proofs)


@dataclass(frozen=True, slots=True)
class WeaponUtilityRequest:
    id: str
    actor_id: str
    inventory: WeaponInventoryState
    item_id: str
    kind: WeaponUtilityKind
    skill: Skill
    test: TestRequest
    conditions: ConditionState
    usable_hands: tuple[WeaponGrip, ...] | None = field(default=None, kw_only=True)
    fate_glorious_proofs: tuple[FateGloriousProof, ...] = field(default=(), kw_only=True)
    lucky_gambling_proofs: tuple[LuckyGamblingProof, ...] = field(default=(), kw_only=True)

    def __post_init__(self):
        _identifier(self.id, 'utility request')
        _identifier(self.actor_id, 'current inventory actor')
        _identifier(self.item_id, 'actual physical unit')
        _typed(self.inventory, WeaponInventoryState)
        _typed(self.conditions, ConditionState)
        if type(self.conditions.conditions) is not frozenset:
            raise TypeError('utility Conditions require a canonical frozenset')
        if type(self.kind) is not WeaponUtilityKind or type(self.skill) is not Skill:
            raise TypeError('utility action and explicit Skill must be typed')
        _test(self.test)
        if any(mod.rule_id in _UTILITY_RULE_IDS for group in (self.test.dice_modifiers,
                self.test.quality_modifiers, self.test.success_modifiers, self.test.reroll_locks)
                for mod in group):
            raise ValueError('utility weapon effects cannot already be applied to the source Test')
        if self.usable_hands is not None:
            if (type(self.usable_hands) is not tuple
                    or any(type(hand) is not WeaponGrip for hand in self.usable_hands)):
                raise TypeError('usable hands require exact physical LEFT/RIGHT grips')
            if (WeaponGrip.BOTH in self.usable_hands
                    or len(set(self.usable_hands)) != len(self.usable_hands)):
                raise ValueError('usable hands must list each physical hand at most once')
        item = self.inventory.item(self.item_id)
        if self.kind is WeaponUtilityKind.CONCEAL_WEAPON:
            if self.skill is not Skill.STEALTH:
                raise ValueError('concealing this weapon requires explicitly supplied Stealth')
            if (item.kind not in (WeaponKind.DAGGER, WeaponKind.KNUCKLEDUSTERS)
                    or item.location not in (WeaponItemLocation.HELD, WeaponItemLocation.CARRIED)):
                raise ValueError('concealment requires an actual owned held/carried Dagger or Knuckledusters')
        else:
            if self.skill is not Skill.TOIL:
                raise ValueError('harvesting resources requires explicitly supplied Toil')
            if (item.kind is not WeaponKind.PICKAXE or item.location is not WeaponItemLocation.HELD
                    or item.grip is not WeaponGrip.BOTH):
                raise ValueError('harvesting requires the actual held two-handed Pickaxe')
            if self.usable_hands is None or set(self.usable_hands) != {WeaponGrip.LEFT, WeaponGrip.RIGHT}:
                raise ValueError('harvesting requires both actual usable hands')
        for proofs, kind in ((self.fate_glorious_proofs, FateGloriousProof),
                (self.lucky_gambling_proofs, LuckyGamblingProof)):
            if type(proofs) is not tuple:
                raise TypeError('utility bound quality proofs require exact tuples')
            for proof in proofs:
                _typed(proof, kind)
        _drained_source(self)


@dataclass(frozen=True, slots=True)
class WeaponUtilityPreparation:
    source_request: WeaponUtilityRequest
    item: WeaponUnitState
    drained: DrainedTestPreparationResult

    def __post_init__(self):
        _typed(self.source_request, WeaponUtilityRequest)
        _typed(self.item, WeaponUnitState)
        _typed(self.drained, DrainedTestPreparationResult)
        source = _drained_source(self.source_request)
        active, removed, removed_quality, test = _expected_drained_test_preparation(source)
        rules = tuple(dict.fromkeys((DRAINED_TEST_PREPARATION_RULE_ID,
            *(proof.rule_id for proof in source.fate_glorious_proofs),
            *(proof.rule_id for proof in source.lucky_gambling_proofs))))
        expected = DrainedTestPreparationResult(source.id, source.rule_id, source,
            active, removed, removed_quality, test, rules)
        if self.item != self.source_request.inventory.item(self.source_request.item_id) or self.drained != expected:
            raise ValueError('utility preparation differs from its full actual item/Test/Conditions source')

    @property
    def test(self) -> TestRequest:
        return self.drained.test


def _completed_test(request, result):
    """Check K1 provenance without re-executing RNG or selecting new rerolls."""
    _test(request)
    _typed(result, TestResult)
    trace = result.trace
    _typed(trace, RollTrace)
    parameters = _expected_initial_roll_parameters(request)
    for name in ('base_dice', 'pool_cap', 'regular_dice_delta', 'cap_bypassing_dice',
            'dice_before_minimum', 'rolled_dice', 'threshold', 'rolled_successes',
            'success_delta', 'successes'):
        if type(getattr(trace, name)) is not int:
            raise TypeError('utility Test counters require exact integers')
    if type(trace.minimum_die_rule_applied) is not bool or type(trace.quality) is not TestQuality:
        raise TypeError('utility Test minimum flag/quality must retain exact types')
    for name in ('initial_values', 'final_values', 'rerolls', 'applied_rule_ids'):
        if type(getattr(trace, name)) is not tuple:
            raise TypeError('utility Test trace requires canonical tuples')
    InitialTestRoll(request, *parameters, trace.initial_values)
    if any(type(value) is not int or not 1 <= value <= 10
            for value in (*trace.initial_values, *trace.final_values)):
        raise ValueError('utility Test requires actual d10 values')
    grim = any(mod.quality is TestQuality.GRIM for mod in request.quality_modifiers)
    glorious = any(mod.quality is TestQuality.GLORIOUS for mod in request.quality_modifiers)
    quality = TestQuality.NORMAL if grim == glorious else TestQuality.GRIM if grim else TestQuality.GLORIOUS
    locked = {mod.value for mod in request.reroll_locks}
    eligible = tuple(i for i, value in enumerate(trace.initial_values)
        if value not in locked and (value <= parameters[6] if quality is TestQuality.GRIM else value > parameters[6]))
    for reroll in trace.rerolls:
        _typed(reroll, RerollTrace)
        if any(type(value) is not int for value in (reroll.index, reroll.original, reroll.replacement)):
            raise TypeError('utility reroll coordinates require exact integers')
    indices = tuple(reroll.index for reroll in trace.rerolls)
    if (quality is TestQuality.NORMAL and indices or quality is TestQuality.GRIM and indices != eligible
            or quality is TestQuality.GLORIOUS and (indices != tuple(sorted(set(indices)))
                or any(index not in eligible for index in indices))):
        raise ValueError('utility Test rerolls differ from actual prepared quality/locks')
    final = list(trace.initial_values)
    for reroll in trace.rerolls:
        if reroll.original != final[reroll.index] or not 1 <= reroll.replacement <= 10:
            raise ValueError('utility reroll changed its original value or d10 result')
        final[reroll.index] = reroll.replacement
    successes = sum(value <= parameters[6] for value in final)
    delta = sum(mod.amount for mod in request.success_modifiers)
    rules = tuple(mod.rule_id for mods in (request.dice_modifiers, request.quality_modifiers,
        request.success_modifiers, request.reroll_locks) for mod in mods)
    expected = RollTrace(request.id, *parameters, quality, trace.initial_values,
        trace.rerolls, tuple(final), successes, delta, max(0, successes + delta), rules)
    if trace != expected:
        raise ValueError('utility Test trace differs from its complete bound source')


@dataclass(frozen=True, slots=True)
class WeaponUtilityResult:
    preparation: WeaponUtilityPreparation
    test: TestResult

    def __post_init__(self):
        _typed(self.preparation, WeaponUtilityPreparation)
        _completed_test(self.preparation.test, self.test)

    @property
    def source_request(self) -> WeaponUtilityRequest:
        return self.preparation.source_request


@dataclass(frozen=True, slots=True)
class WeaponUtilityLedger:
    """Explicit once-only receipt IDs; no implicit inventory or scene changes."""
    actor_id: str
    resolved_ids: tuple[str, ...] = ()

    def __post_init__(self):
        _identifier(self.actor_id, 'utility ledger actor')
        if type(self.resolved_ids) is not tuple:
            raise TypeError('resolved utility IDs require an exact tuple')
        for value in self.resolved_ids:
            _identifier(value, 'resolved utility')
        if len(set(self.resolved_ids)) != len(self.resolved_ids):
            raise ValueError('a utility request cannot be applied twice')


def apply_weapon_utility_result(ledger: WeaponUtilityLedger,
        result: WeaponUtilityResult) -> WeaponUtilityLedger:
    _typed(ledger, WeaponUtilityLedger)
    _typed(result, WeaponUtilityResult)
    source = result.source_request
    if ledger.actor_id != source.actor_id:
        raise ValueError('utility result belongs to another actor')
    if source.id in ledger.resolved_ids:
        raise ValueError('utility request has already been applied')
    return replace(ledger, resolved_ids=(*ledger.resolved_ids, source.id))
