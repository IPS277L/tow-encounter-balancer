"""Pure post-initial-roll Fate choices, bound to the current PC resource owner."""
from dataclasses import replace

from towr.domain.fate_models import (
    FateGloriousSpendRequest, FateGloriousSpendResult,
    _expected_fate_glorious_spend, _fate_spend_rule_ids,
)
from towr.domain.pc_melee_models import PcFatePolicy
from towr.domain.test_models import InitialTestRoll, RollTrace, TestResult, TestQuality, _expected_initial_roll_parameters


def build_pc_glorious_spend(state, actor_id, skill, initial):
    """Choose from this PC's own initial dice, never another actor's Test."""
    participant = state.source.participant(actor_id)
    member = state.participant(actor_id)
    strategy = participant.glorious_policy
    if participant.fate_policy is not PcFatePolicy.CONFIGURED or strategy is None:
        return None
    successes = sum(value <= initial.threshold for value in initial.initial_values)
    grim = any(m.quality is TestQuality.GRIM for m in initial.request.quality_modifiers)
    glorious = any(m.quality is TestQuality.GLORIOUS for m in initial.request.quality_modifiers)
    locked = {m.value for m in initial.request.reroll_locks}
    useful = any(value not in locked and ((value <= initial.threshold) if grim else
        (value > initial.threshold)) for value in initial.initial_values)
    cost = 0 if member.fate.lucky_free_spend_available else 1
    if (skill not in strategy.skills or successes > strategy.maximum_initial_successes
            or not member.fate.can_spend
            or member.fate.remaining_spends-cost < strategy.minimum_remaining_spends
            or glorious or not useful):
        return None
    base_id = initial.request.id + ':glorious-spend'
    used = {*member.fate.resource_event_ids, *(item.id for item in member.fate.spends)}
    spend_id, suffix = base_id, 0
    while spend_id in used:
        suffix += 1
        spend_id = f'{base_id}:{suffix}'
    return FateGloriousSpendRequest(spend_id,member.fate,initial.request,initial)


def validate_pc_test_fate(state, actor_id, skill, request, test, decline, glorious):
    """Return the exact effective request/resource after checking one Test window."""
    from towr.domain.pc_melee_result_models import (
        _decline, _test_result, validate_pc_melee_source_types,
    )

    def same(actual, expected, message):
        if actual != expected:
            raise ValueError(message)
        validate_pc_melee_source_types(actual,expected)

    if type(test) is not TestResult or type(test.trace) is not RollTrace:
        raise TypeError('PC Fate window requires the actual typed Test result and trace')
    parameters = _expected_initial_roll_parameters(request)
    initial = InitialTestRoll(request,*parameters,test.trace.initial_values)
    expected = build_pc_glorious_spend(state,actor_id,skill,initial)
    if expected is None:
        if glorious is not None:
            raise ValueError('Glorious spend differs from the selected skill/initial dice/resource policy')
        _decline(state,decline,actor_id,request.id,'test')
        _test_result(request,test)
        return request,state.participant(actor_id).fate
    if decline is not None:
        raise ValueError('a selected Glorious Test cannot also decline Fate')
    if type(glorious) is not FateGloriousSpendResult:
        raise TypeError('selected Glorious Test requires its typed actual spend proof')
    spend, proof, fate, effective = _expected_fate_glorious_spend(expected)
    canonical = FateGloriousSpendResult(expected.id,expected.rule_id,expected,
        expected.state,fate,spend,proof,effective,_fate_spend_rule_ids(expected.state,expected.rule_id))
    same(glorious,canonical,'Glorious proof changed the exact initial roll, resource or complete provenance')
    _test_result(effective,test)
    return effective,fate
