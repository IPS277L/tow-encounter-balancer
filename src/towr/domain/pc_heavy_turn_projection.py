"""Source-bound PC end phase, including genuinely actionless incapacity turns."""
from dataclasses import replace

from towr.domain.condition_models import Condition
from towr.domain.critical_injury_models import CriticalInjuryTestRequest, CriticalInjuryTestResult
from towr.domain.injury_models import WoundConditionEffect
from towr.domain.test_models import Skill
from towr.domain.pc_fate_test_models import validate_pc_test_fate
from towr.domain.pc_melee_result_models import (
    PcCriticalProof, PcIncapacitatedTurnEndProof, PcTurnEndProof, _decline, _pc_test,
    _test_result, _party_update, pc_after_test, pc_melee_action_id,
    validate_pc_melee_combat_shape, validate_pc_melee_source_types,
)


def project_heavy_turn_end(state,proof,finish):
    combat = state.round_state
    turn = combat.active_turn
    if turn is None or state.pending or state.pending_wound is not None:
        raise ValueError('end phase requires its active turn and closed mandatory work')
    validate_pc_melee_combat_shape(proof.result.state)
    replace(proof.result.completed_turn)
    if type(proof.result.round_complete) is not bool:
        raise TypeError('end phase round-complete must retain its bool type')
    action_id = pc_melee_action_id(state,turn.actor_id)
    is_pc = turn.actor_id in state.source.pc_activation_order
    incapable = isinstance(proof,PcIncapacitatedTurnEndProof)
    if incapable:
        if not is_pc or turn.action_slots or not state.participant(turn.actor_id).injury.conditions.has(Condition.DEFENCELESS):
            raise ValueError('only a truly actionless Defenceless PC has this end path')
        rules = ('RULE-COMBAT-001:rounds-sides-turns','RULE-HEALTH-008:defenceless-turn')
    else:
        if not turn.action_slots or any(not slot.executed for slot in turn.action_slots):
            raise ValueError('ordinary turn end requires all its reserved actions to be executed')
        rules = ('RULE-COMBAT-001:rounds-sides-turns',)
    expected_clock = replace(combat,active_turn=None,completed_turn_entity_ids=(*combat.completed_turn_entity_ids,turn.actor_id))
    expected = (action_id+':end',expected_clock,turn,expected_clock.next_side,expected_clock.round_complete,rules)
    actual = (proof.result.request_id,proof.result.state,proof.result.completed_turn,proof.result.next_side,
        proof.result.round_complete,proof.result.applied_rule_ids)
    if actual != expected:
        raise ValueError('end phase changed its actor, source, actual action or clock')
    validate_pc_melee_source_types(actual,expected)
    if not is_pc:
        if proof.fate_decline is not None or proof.critical is not None:
            raise ValueError('NPC end cannot invent PC Fate or Critical Endurance')
        return finish(round_state=expected_clock)
    member = state.participant(turn.actor_id)
    if member.injury.dead:
        raise ValueError('dead PC cannot initiate another end phase')
    if not incapable:
        _decline(state,proof.fate_decline,turn.actor_id,proof.result.request_id,'action')
    injury = member.injury
    fate = member.fate
    if injury.conditions.has(Condition.CRITICALLY_INJURED):
        critical = proof.critical
        if type(critical) is not PcCriticalProof or type(critical.result) is not CriticalInjuryTestResult:
            raise TypeError('Critical end phase must retain its actual Test and result')
        test_request = _pc_test(state,turn.actor_id,action_id+':critical:endurance',Skill.ENDURANCE)
        if critical.test_request != test_request:
            raise ValueError('critical Endurance differs from the current PC profile/quality')
        validate_pc_melee_source_types(critical.test_request,test_request)
        _,fate = validate_pc_test_fate(state,turn.actor_id,Skill.ENDURANCE,test_request,
            critical.result.test,critical.fate_decline,critical.glorious)
        source = CriticalInjuryTestRequest(action_id+':critical',turn.actor_id,
            pc_after_test(state,turn.actor_id),test_request.id)
        replace(critical.result)
        if critical.result.source_request != source:
            raise ValueError('critical consequence changed its actual post-Test source')
        validate_pc_melee_source_types(critical.result.source_request,source)
        injury = critical.result.state
    elif proof.critical is not None:
        raise ValueError('healthy end phase cannot invent a Critical Test')
    expired = tuple(t.effect for t in member.timed_wounds if t.deadline_round == combat.round_number)
    if any(t.deadline_round < combat.round_number for t in member.timed_wounds):
        raise ValueError('PC expiry clock is stale')
    effects = tuple(effect for effect in injury.active_wound_effects if effect not in expired)
    conditions = injury.conditions
    for effect in expired:
        if not any(isinstance(other,WoundConditionEffect) and other.condition is effect.condition for other in effects):
            conditions = conditions.without_condition(effect.condition)
    injury = replace(injury,active_wound_effects=effects,conditions=conditions)
    return finish(round_state=expected_clock,party=_party_update(state,turn.actor_id,injury=injury,fate=fate,
        timed_wounds=tuple(t for t in member.timed_wounds if t.effect not in expired)))
