"""Injury-bound Crushed Rib next-Test witnesses (ADR-0055), without RNG.

An authoritative caller supplies actor/injury identity and next-Test chronology.
These models do not prove membership in a battle owner or its journal.
"""
from dataclasses import dataclass, replace

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.drained_test_models import (
    DRAINED_TEST_PREPARATION_RULE_ID, DrainedTestPreparationRequest, DrainedTestPreparationResult,
)
from towr.domain.injury_models import (
    CharacterInjuryState, WoundConditionEffect, WoundEffectDuration, WoundEntryId,
    WoundRecord, WoundRecordOrigin, WoundRestriction, WoundRestrictionEffect,
)
from towr.domain.magic_models import (
    CastingTestRequest, CastingTestResult, MiscastPoolIncreaseRequest,
    MiscastPoolIncreaseSourceKind, WizardMagicState,
)
from towr.domain.test_models import (
    DiceModifier, InitialTestRoll, InlineProfile, QualityModifier, QualityModifierSource,
    RerollLock, RerollTrace, RollTrace, SuccessModifier, TestProfile, TestQuality, TestRequest, TestResult,
)


CRUSHED_RIB_TEST_RULE_ID = 'RULE-WOUND-TABLE:crushed_rib'
_NINE_RULE = 'RULE-MAGIC-003:rule-of-nine'
_GRIM = QualityModifier(CRUSHED_RIB_TEST_RULE_ID, TestQuality.GRIM)


def _typed(value, kind):
    if not isinstance(value, kind):
        raise TypeError(f'Crushed Rib requires {kind.__name__}')


def _identifier(value):
    if not isinstance(value, str):
        raise TypeError('Crushed Rib identifiers must be strings')
    if not value.strip():
        raise ValueError('Crushed Rib identifiers must not be blank')


def _integer(value):
    if type(value) is not int:
        raise TypeError('Crushed Rib numeric values must be strict integers')


def _boolean(value):
    if type(value) is not bool:
        raise TypeError('Crushed Rib flags must be strict booleans')


def _ordered(value):
    if type(value) is not tuple:
        raise TypeError('Crushed Rib original sequences must be tuples')


def _dice(values):
    _ordered(values)
    for value in values:
        _integer(value)
        if not 1 <= value <= 10:
            raise ValueError('Crushed Rib witnesses require actual d10 values')


def _effect(value):
    if not isinstance(value, (WoundConditionEffect, WoundRestrictionEffect)):
        raise TypeError('Crushed Rib requires typed Wound effects')
    _integer(value.wound_sequence)
    replace(value)


def _injury(state, *, pending=True):
    _typed(state, CharacterInjuryState)
    _boolean(state.dead)
    if state.dead:
        raise ValueError('Crushed Rib requires a living character')
    _typed(state.conditions, ConditionState)
    if type(state.conditions.conditions) is not frozenset:
        raise TypeError('Crushed Rib Conditions must retain their admitted form')
    for condition in state.conditions.conditions:
        _typed(condition, Condition)
    if state.conditions.conditions != frozenset((Condition.DRAINED,)):
        raise ValueError('Crushed Rib supports only retained Drained')
    _ordered(state.wounds)
    for index, wound in enumerate(state.wounds, 1):
        _typed(wound, WoundRecord)
        _integer(wound.sequence)
        _integer(wound.table_total)
        for flag in (wound.treated, wound.effect_resolved, wound.healed):
            _boolean(flag)
        _typed(wound.entry_id, WoundEntryId)
        _typed(wound.origin, WoundRecordOrigin)
        _dice(wound.roll_values)
        replace(wound)
        if (wound.sequence != index or wound.origin is not WoundRecordOrigin.TABLE_ROLL
                or wound.treated or wound.healed or not wound.effect_resolved):
            raise ValueError('Crushed Rib requires resolved untreated unhealed rolled Wounds')
        if index == len(state.wounds):
            if wound.entry_id is not WoundEntryId.CRUSHED_RIB or wound.table_total != 10:
                raise ValueError('Crushed Rib requires exactly one last rolled Wound10')
        elif wound.entry_id is not WoundEntryId.SUPERFICIAL_INJURY or not 1 <= wound.table_total <= 3:
            raise ValueError('Crushed Rib permits only previous Superficial Injuries')
    if not state.wounds:
        raise ValueError('Crushed Rib requires its Wound record')
    _ordered(state.active_wound_effects)
    for effect in state.active_wound_effects:
        _effect(effect)
    sequence = state.wounds[-1].sequence
    drained = WoundConditionEffect(sequence, Condition.DRAINED, WoundEffectDuration.UNTIL_TREATED)
    effect = WoundRestrictionEffect(sequence, WoundRestriction.NEXT_TEST_IS_GRIM, WoundEffectDuration.NEXT_TEST)
    actual = state.active_wound_effects
    allowed = ((drained, effect),) if pending is True else ((drained,),)
    if pending is None:
        allowed = (*allowed, (drained, effect))
    if actual not in allowed:
        raise ValueError('Crushed Rib requires exact canonical active Wound effects')
    if replace(state) != state:
        raise ValueError('Crushed Rib injury must not require normalization')
    return effect


def _test(request, *, prepared=False):
    _typed(request, TestRequest)
    _identifier(request.id)
    profile = request.profile
    if not isinstance(profile, (TestProfile, InlineProfile)):
        raise TypeError('Crushed Rib requires a typed Test profile')
    for value in ((profile.characteristic, profile.skill) if isinstance(profile, TestProfile)
                  else (profile.dice, profile.threshold)):
        _integer(value)
    if isinstance(profile, InlineProfile) and profile.pool_cap is not None:
        _integer(profile.pool_cap)
    replace(profile)
    for name, kind in (('dice_modifiers', DiceModifier), ('quality_modifiers', QualityModifier),
                       ('success_modifiers', SuccessModifier), ('reroll_locks', RerollLock)):
        values = getattr(request, name)
        _ordered(values)
        for value in values:
            _typed(value, kind)
            _identifier(value.rule_id)
            if not prepared and value.rule_id == CRUSHED_RIB_TEST_RULE_ID:
                raise ValueError('Crushed Rib canonical modifier is reserved for preparation')
            if isinstance(value, (DiceModifier, SuccessModifier)):
                _integer(value.amount)
            if isinstance(value, DiceModifier):
                _boolean(value.bypasses_pool_cap)
            if isinstance(value, QualityModifier):
                _typed(value.quality, TestQuality)
                _typed(value.source, QualityModifierSource)
                if value.source is not QualityModifierSource.RULE:
                    raise ValueError('Crushed Rib first slice excludes Fate/Talent quality sources')
            if isinstance(value, RerollLock):
                _integer(value.value)
            replace(value)
    if replace(request) != request:
        raise ValueError('Crushed Rib Test source must not require normalization')


def _magic(state):
    _typed(state, WizardMagicState)
    for name in ('miscast_dice', 'casting_successes', 'latest_casting_roll_successes'):
        _integer(getattr(state, name))
    if state.casting_lore_id is not None:
        _identifier(state.casting_lore_id)
    replace(state)


def _casting(request, *, prepared=False):
    _typed(request, CastingTestRequest)
    for value in (request.id, request.caster_id, request.lore_id, request.rule_id):
        _identifier(value)
    _test(request.test, prepared=prepared)
    if any(lock.rule_id == _NINE_RULE for lock in request.test.reroll_locks):
        raise ValueError('Casting owns its canonical Rule of Nine reroll lock')
    _magic(request.state)
    replace(request)


@dataclass(frozen=True, slots=True)
class CrushedRibTestPreparationRequest:
    id: str
    actor_id: str
    state: CharacterInjuryState
    test: TestRequest

    def __post_init__(self):
        _identifier(self.id)
        _identifier(self.actor_id)
        _injury(self.state)
        _test(self.test)


@dataclass(frozen=True, slots=True)
class CrushedRibCastingPreparationRequest:
    id: str
    actor_id: str
    state: CharacterInjuryState
    casting: CastingTestRequest

    def __post_init__(self):
        _identifier(self.id)
        _identifier(self.actor_id)
        _injury(self.state)
        _casting(self.casting)
        if self.casting.caster_id != self.actor_id:
            raise ValueError('Crushed Rib Casting belongs to another actor')


def _drained_request(source):
    original = source.test if isinstance(source, CrushedRibTestPreparationRequest) else source.casting.test
    return DrainedTestPreparationRequest(source.id + ':drained', source.actor_id, source.state.conditions,
        replace(original, quality_modifiers=(*original.quality_modifiers, _GRIM)))


def _preparation(source, effect, drained, request_type):
    _typed(source, request_type)
    replace(source)
    _typed(effect, WoundRestrictionEffect)
    _effect(effect)
    if effect != _injury(source.state):
        raise ValueError('Crushed Rib preparation has a foreign effect')
    _typed(drained, DrainedTestPreparationResult)
    original = drained.source_request
    _typed(original, DrainedTestPreparationRequest)
    _test(original.test, prepared=True)
    for name in ('fate_glorious_proofs', 'lucky_gambling_proofs'):
        _ordered(getattr(original, name))
        if getattr(original, name):
            raise ValueError('Crushed Rib preparation excludes external quality proofs')
    if original.combat_surgeon_effective_effects is not None:
        raise ValueError('Crushed Rib preparation excludes Combat Surgeon suppression')
    _typed(original.conditions, ConditionState)
    if type(original.conditions.conditions) is not frozenset:
        raise TypeError('Drained source Conditions must retain their admitted form')
    for condition in original.conditions.conditions:
        _typed(condition, Condition)
    for value in (original.id, original.actor_id, original.rule_id, drained.request_id, drained.rule_id):
        _identifier(value)
    replace(original)
    _boolean(drained.drained_active)
    for name in ('removed_bonus_modifiers', 'removed_quality_modifiers', 'applied_rule_ids'):
        _ordered(getattr(drained, name))
    # Detached copies in removed lists must not hide malformed equal values.
    _test(replace(original.test, dice_modifiers=drained.removed_bonus_modifiers,
                  quality_modifiers=drained.removed_quality_modifiers), prepared=True)
    _test(drained.test, prepared=True)
    replace(drained)
    if original != _drained_request(source) or drained.applied_rule_ids != (DRAINED_TEST_PREPARATION_RULE_ID,):
        raise ValueError('Crushed Rib Drained preparation differs from its complete source')


@dataclass(frozen=True, slots=True)
class CrushedRibTestPreparationResult:
    source_request: CrushedRibTestPreparationRequest
    effect: WoundRestrictionEffect
    drained: DrainedTestPreparationResult
    test: TestRequest

    def __post_init__(self):
        _preparation(self.source_request, self.effect, self.drained, CrushedRibTestPreparationRequest)
        _test(self.test, prepared=True)
        if self.test != self.drained.test:
            raise ValueError('Crushed Rib prepared Test differs from Drained result')


@dataclass(frozen=True, slots=True)
class CrushedRibCastingPreparationResult:
    source_request: CrushedRibCastingPreparationRequest
    effect: WoundRestrictionEffect
    drained: DrainedTestPreparationResult
    casting: CastingTestRequest

    def __post_init__(self):
        _preparation(self.source_request, self.effect, self.drained, CrushedRibCastingPreparationRequest)
        _casting(self.casting, prepared=True)
        if self.casting != replace(self.source_request.casting, test=self.drained.test):
            raise ValueError('Crushed Rib prepared Casting differs from its complete source')


def _completed_test(request, result):
    """Validate the full Grim witness purely, without re-executing its rolls."""
    _test(request, prepared=True)
    _typed(result, TestResult)
    trace = result.trace
    _typed(trace, RollTrace)
    _identifier(trace.request_id)
    _typed(trace.quality, TestQuality)
    _boolean(trace.minimum_die_rule_applied)
    _dice(trace.initial_values)
    _dice(trace.final_values)
    for name in ('base_dice', 'pool_cap', 'regular_dice_delta', 'cap_bypassing_dice', 'dice_before_minimum',
                 'rolled_dice', 'threshold', 'rolled_successes', 'success_delta', 'successes'):
        _integer(getattr(trace, name))
    initial = InitialTestRoll(request, trace.base_dice, trace.pool_cap, trace.regular_dice_delta,
        trace.cap_bypassing_dice, trace.dice_before_minimum, trace.rolled_dice, trace.threshold,
        trace.minimum_die_rule_applied, trace.initial_values)
    if trace.quality is not TestQuality.GRIM:
        raise ValueError('Crushed Rib completed Test must retain prepared Grim quality')
    _ordered(trace.rerolls)
    eligible = tuple(i for i, value in enumerate(initial.initial_values)
                     if value <= initial.threshold and value not in {lock.value for lock in request.reroll_locks})
    for reroll in trace.rerolls:
        _typed(reroll, RerollTrace)
        _integer(reroll.index)
        _dice((reroll.original, reroll.replacement))
    if tuple(r.index for r in trace.rerolls) != eligible:
        raise ValueError('Crushed Rib requires exactly all eligible Grim rerolls in order')
    final = list(initial.initial_values)
    for reroll in trace.rerolls:
        if reroll.original != initial.initial_values[reroll.index]:
            raise ValueError('Crushed Rib reroll has a foreign original value')
        final[reroll.index] = reroll.replacement
    rolled_successes = sum(v <= initial.threshold for v in final)
    delta = sum(modifier.amount for modifier in request.success_modifiers)
    rules = tuple(modifier.rule_id for modifiers in (request.dice_modifiers, request.quality_modifiers,
                  request.success_modifiers, request.reroll_locks) for modifier in modifiers)
    _ordered(trace.applied_rule_ids)
    for rule_id in trace.applied_rule_ids:
        _identifier(rule_id)
    expected = RollTrace(request.id, initial.base_dice, initial.pool_cap, initial.regular_dice_delta,
        initial.cap_bypassing_dice, initial.dice_before_minimum, initial.rolled_dice, initial.threshold,
        initial.minimum_die_rule_applied, TestQuality.GRIM, initial.initial_values, trace.rerolls,
        tuple(final), rolled_successes, delta, max(0, rolled_successes + delta), rules)
    if trace != expected:
        raise ValueError('Crushed Rib completed Test trace differs from its full prepared source')


def _completed_casting(source, result):
    _typed(result, CastingTestResult)
    request = source.casting
    effective = replace(request.test, reroll_locks=(*request.test.reroll_locks, RerollLock(_NINE_RULE, 9)))
    _completed_test(effective, result.test)
    for value in (result.request_id, result.caster_id, result.lore_id):
        _identifier(value)
    for value in (result.previous_casting_successes, result.latest_roll_successes, result.miscast_dice_added):
        _integer(value)
    _magic(result.state)
    _ordered(result.follow_ups)
    _ordered(result.applied_rule_ids)
    for rule_id in result.applied_rule_ids:
        _identifier(rule_id)
    for follow in result.follow_ups:
        _typed(follow, MiscastPoolIncreaseRequest)
        _integer(follow.amount)
        _typed(follow.source_kind, MiscastPoolIncreaseSourceKind)
        replace(follow)
    successes = result.test.successes
    nines = result.test.trace.final_values.count(9)
    follow_ups = () if not nines else (MiscastPoolIncreaseRequest(request.id + ':rule-of-nine', request.caster_id,
        nines, MiscastPoolIncreaseSourceKind.TEST, request.test.id, request.rule_id, _NINE_RULE),)
    expected = CastingTestResult(request.id, request.caster_id, request.lore_id, result.test,
        replace(request.state, casting_successes=request.state.casting_successes + successes,
                casting_lore_id=request.lore_id, latest_casting_roll_successes=successes),
        request.state.casting_successes, successes, nines, follow_ups, (request.rule_id, _NINE_RULE))
    if result != expected:
        raise ValueError('Crushed Rib Casting result differs from its full parent/state/follow-ups')


def _consumed_state(source):
    return replace(source.source_request.state, active_wound_effects=tuple(
        e for e in source.source_request.state.active_wound_effects if e != source.effect))


def _consumption(source, consumed_effect, state):
    _typed(consumed_effect, WoundRestrictionEffect)
    _effect(consumed_effect)
    _injury(state, pending=False)
    if consumed_effect != source.effect or state != _consumed_state(source):
        raise ValueError('Crushed Rib completion must remove only its exact pending effect')


@dataclass(frozen=True, slots=True)
class CrushedRibTestResult:
    source: CrushedRibTestPreparationResult
    test: TestResult
    consumed_effect: WoundRestrictionEffect
    state: CharacterInjuryState

    def __post_init__(self):
        _typed(self.source, CrushedRibTestPreparationResult)
        replace(self.source)
        _completed_test(self.source.test, self.test)
        _consumption(self.source, self.consumed_effect, self.state)


@dataclass(frozen=True, slots=True)
class CrushedRibCastingResult:
    source: CrushedRibCastingPreparationResult
    casting: CastingTestResult
    consumed_effect: WoundRestrictionEffect
    state: CharacterInjuryState

    def __post_init__(self):
        _typed(self.source, CrushedRibCastingPreparationResult)
        replace(self.source)
        _completed_casting(self.source, self.casting)
        _consumption(self.source, self.consumed_effect, self.state)
