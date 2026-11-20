"""Canonical recorded Test validation for post-Test Talent consumers."""
from dataclasses import replace
from towr.domain.test_models import (
    DiceModifier, InlineProfile, QualityModifier, RerollLock, SuccessModifier,
    TestProfile, RollTrace, RerollTrace, TestQuality, TestRequest, TestResult,
    _expected_initial_roll_parameters,
)


def validate_completed_talent_test(request, result):
    """Check recorded dice against the bound final Test, without RNG or policy.

    Glorious permits any legal subset of failures; Grim requires every eligible
    success. A Talent consumer cannot silently replace those recorded choices.
    """
    if type(request) is not TestRequest or type(result) is not TestResult or type(result.trace) is not RollTrace:
        raise TypeError('Talent requires its exact final Test and trace')
    if type(request.profile) not in (TestProfile,InlineProfile):
        raise TypeError('Talent Test requires its exact typed roll profile')
    replace(request.profile)
    for field,kind in (('dice_modifiers',DiceModifier),('quality_modifiers',QualityModifier),
            ('success_modifiers',SuccessModifier),('reroll_locks',RerollLock)):
        values = getattr(request, field)
        if type(values) is not tuple or any(type(value) is not kind for value in values):
            raise TypeError('Talent Test source modifiers must remain canonical tuples')
        for value in values:
            replace(value)
            if kind is DiceModifier and type(value.bypasses_pool_cap) is not bool:
                raise TypeError('Talent Test dice modifier cap bypass requires an exact boolean')
    replace(request)
    trace = result.trace
    for field in ('base_dice', 'pool_cap', 'regular_dice_delta', 'cap_bypassing_dice',
            'dice_before_minimum', 'rolled_dice', 'threshold', 'rolled_successes', 'success_delta', 'successes'):
        if type(getattr(trace, field)) is not int:
            raise TypeError('Talent Test trace counters must be exact integers')
    if type(trace.minimum_die_rule_applied) is not bool or type(trace.quality) is not TestQuality:
        raise TypeError('Talent Test trace must retain its exact minimum flag and quality')
    for values in (trace.initial_values, trace.final_values):
        if type(values) is not tuple or any(type(value) is not int or not 1 <= value <= 10 for value in values):
            raise TypeError('Talent Test trace must retain exact d10 tuples')
    if type(trace.rerolls) is not tuple or any(type(value) is not RerollTrace for value in trace.rerolls):
        raise TypeError('Talent Test trace must retain typed reroll tuples')
    if type(trace.applied_rule_ids) is not tuple or any(type(value) is not str for value in trace.applied_rule_ids):
        raise TypeError('Talent Test trace must retain exact rule identifiers')
    parameters = _expected_initial_roll_parameters(request)
    if len(trace.initial_values) != parameters[5] or len(trace.final_values) != parameters[5]:
        raise ValueError('Talent Test trace changed its actual dice pool')
    qualities = {modifier.quality for modifier in request.quality_modifiers}
    quality = (next(iter(qualities)) if len(qualities) == 1 else TestQuality.NORMAL)
    locked = {lock.value for lock in request.reroll_locks}
    eligible = tuple(index for index, value in enumerate(trace.initial_values)
        if value not in locked and (value <= parameters[6] if quality is TestQuality.GRIM else value > parameters[6]))
    indices = tuple(value.index for value in trace.rerolls)
    if any(type(index) is not int for index in indices) or indices != tuple(sorted(set(indices))):
        raise ValueError('Talent Test reroll choices must be exact unique ordered indices')
    if (quality is TestQuality.NORMAL and indices
            or quality is TestQuality.GRIM and indices != eligible
            or quality is TestQuality.GLORIOUS and not set(indices) <= set(eligible)):
        raise ValueError('Talent Test trace changed its legal final reroll choices')
    final = list(trace.initial_values)
    for reroll in trace.rerolls:
        if (any(type(value) is not int for value in (reroll.original, reroll.replacement))
                or not 1 <= reroll.replacement <= 10 or reroll.original != final[reroll.index]):
            raise ValueError('Talent Test trace changed an actual rerolled die')
        final[reroll.index] = reroll.replacement
    successes = sum(value <= parameters[6] for value in final)
    delta = sum(modifier.amount for modifier in request.success_modifiers)
    rules = tuple(modifier.rule_id for values in (request.dice_modifiers, request.quality_modifiers,
        request.success_modifiers, request.reroll_locks) for modifier in values)
    expected = RollTrace(request.id, *parameters[:6], parameters[6], parameters[7], quality,
        trace.initial_values, trace.rerolls, tuple(final), successes, delta, max(0, successes+delta), rules)
    if trace != expected or type(trace.request_id) is not str:
        raise ValueError('Talent Test trace is not canonical for its complete final Test source')

