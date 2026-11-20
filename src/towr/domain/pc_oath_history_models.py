"""Canonical Oath bank from admitted native receipts, without world replay.

The ordinary projector authenticates each world receipt. This fold owns only
the Oath resource prefix: it never reads the submitted final resource bank.
"""
from dataclasses import replace

from towr.domain.condition_models import Condition, ConditionApplicationResult, ConditionState
from towr.domain.honour_bound_models import (
    HONOUR_BOUND_GLORIOUS_RULE_ID, HonourBoundGloriousRequest,
    activate_honour_bound_glorious, activate_honour_bound_unmitigated,
    record_honour_bound_oath_decision,
)
from towr.domain.injury_models import CharacterWoundResult, ProfileWoundResult
from towr.domain.lady_blessing_models import (
    LadyOathDecision, OathDecisionKind, record_lady_broken_gain,
    record_lady_oath_decision, record_lady_wound_negation,
)
from towr.domain.test_models import TestRequest, TestResult
from towr.domain.turn_models import CombatTurnStartResult


def _broken_gains(proof):
    """Actual transition witnesses, including a gain later removed again."""
    from towr.domain.pc_demigryph_models import pc_kernel_attack_types, pc_kernel_resolution
    from towr.domain.pc_give_ground_models import PcGiveGroundProof, PcAfterGiveGroundProof
    from towr.domain.pc_magic_models import PcMagicEffectProof
    if type(proof) in pc_kernel_attack_types():
        result = pc_kernel_resolution(proof)
        before = proof.request.kernel_request.target_state.conditions
        after = result.target_state.conditions
        if not before.has(Condition.BROKEN) and after.has(Condition.BROKEN):
            yield proof.request.target_id, before, after
        # A typed application retains the transition even if a later effect in
        # the same accepted result changes the resulting Conditions again.
        for application in result.condition_applications:
            if (application.condition is Condition.BROKEN and not application.was_already_present
                    and not application.blocked):
                yield proof.request.target_id, application.state.without_condition(Condition.BROKEN), application.state
    elif type(proof) is PcGiveGroundProof:
        before, after = proof.request.mover_conditions, proof.result.conditions
        if not before.has(Condition.BROKEN) and after.has(Condition.BROKEN):
            yield proof.actor_id, before, after
    elif type(proof) is PcAfterGiveGroundProof:
        before, after = proof.previous.conditions, proof.result.state.conditions
        if not before.has(Condition.BROKEN) and after.has(Condition.BROKEN):
            yield proof.actor_id, before, after
    elif type(proof) is PcMagicEffectProof and type(proof.result) is ConditionApplicationResult:
        application = proof.result
        if (application.condition is Condition.BROKEN and not application.was_already_present
                and not application.blocked):
            yield proof.task.target_id, application.state.without_condition(Condition.BROKEN), application.state


def fold_native_oaths(source, history):
    from towr.domain.pc_oath_models import (
        PcLadyPrayerProof, initial_pc_oaths, lady_wound_rule, oath_step_evidence, oath_test_request,
    )
    from towr.domain.talent_lady_prayer_models import execute_lady_prayer
    from towr.domain.pc_broken_battlefield_models import PcBrokenMoveProof, PcBrokenRunProof
    from towr.domain.pc_npc_exit_models import PcNpcExitProof
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types

    rows = initial_pc_oaths(source)
    if not rows:
        return rows
    if type(history) is not tuple:
        raise TypeError('Oath history must retain its exact immutable native prefix')
    witnessed, wound_receipts = {}, {}
    starts = []

    def same(actual, expected, message):
        if actual != expected:
            raise ValueError(message)
        validate_pc_melee_source_types(actual, expected)

    for index, proof in enumerate(history):
        if type(proof) is CombatTurnStartResult:
            starts.append(proof)
        evidence = oath_step_evidence(proof)
        tests = {value.trace.request_id:value for value in evidence if type(value) is TestResult}
        requests = {value.id:oath_test_request(proof,value)
            for value in evidence if type(value) is TestRequest}
        updated = []
        for row in rows:
            honour, lady, uses, negations = row.honour, row.lady, row.honour_uses, row.lady_uses
            if type(proof) is PcLadyPrayerProof and proof.result.blessing.actor_id == row.actor_id:
                request = proof.result.source_request
                same(request.blessing, lady, 'prayer history replaced its actual resource prefix')
                same(request.turn_starts, tuple(starts), 'prayer history replaced the actual first-turn prefix')
                expected = execute_lady_prayer(request)
                same(proof.result, expected, 'prayer history changed its actual paid action result')
                lady = expected.blessing
            for identifier, actual in tests.items():
                request = requests.get(identifier)
                grant = actual.honour_bound
                owner_grant = grant is not None and grant.activation.state.actor_id == row.actor_id
                markers = (() if request is None else tuple(value for value in request.quality_modifiers
                    if value.rule_id == HONOUR_BOUND_GLORIOUS_RULE_ID))
                own_markers = tuple(value for value in markers
                    if value.source_id and value.source_id.startswith('honour:'+str(len(row.actor_id))+':'+row.actor_id+':'))
                if not owner_grant and not own_markers:
                    continue
                if request is None or honour is None:
                    raise ValueError('Oath Test history lost its actual acquired owner or prepared request')
                key = (row.actor_id, identifier)
                if key in witnessed:
                    same((request,actual), witnessed[key], 'repeated Oath Test history changed its already consumed source')
                    continue
                if owner_grant:
                    if row.actor_id not in source.pc_activation_order or own_markers:
                        raise ValueError('Unmitigated history cannot grant NPC Fate or combine activation modes')
                    previous = grant.activation.source_request
                    expected_id = ('honour-outcome:'+str(len(row.actor_id))+':'+row.actor_id+':'+str(index)+':'+identifier)
                    if previous.id != expected_id:
                        raise ValueError('Unmitigated history replaced its actual native prefix identifier')
                    same(previous.test, request, 'Unmitigated history replaced its actual prepared Test')
                    expected = activate_honour_bound_unmitigated(replace(previous,state=honour,context=row.context))
                    same(grant.activation, expected, 'Unmitigated history replaced its actual resource or GM prefix')
                    same(grant.raw_test, previous.final_result, 'Unmitigated history replaced its actual raw Test')
                else:
                    marker_id = 'honour:'+str(len(row.actor_id))+':'+row.actor_id+':'+str(index)
                    if len(own_markers) != 1 or own_markers[0].source_id != marker_id:
                        raise ValueError('Glorious history replaced its actual native actor/prefix marker')
                    marker = own_markers[0]
                    if HONOUR_BOUND_GLORIOUS_RULE_ID not in actual.trace.applied_rule_ids:
                        raise ValueError('Glorious history has no actual consumed Talent Test')
                    ordinary = replace(request,quality_modifiers=tuple(value for value in request.quality_modifiers
                        if value != marker))
                    expected = activate_honour_bound_glorious(HonourBoundGloriousRequest(
                        marker_id,honour,row.context,ordinary))
                    same(replace(expected.test.quality_modifiers[-1],source_id=marker_id),marker,
                        'Glorious history replaced its acquired Talent effect')
                honour, uses = expected.state, (*uses,expected)
                witnessed[key] = request,actual
            if lady is not None:
                for result in evidence:
                    if (type(result) not in (CharacterWoundResult,ProfileWoundResult)
                            or result.negated_by_rule_id != lady_wound_rule(row.actor_id)):
                        continue
                    key = row.actor_id,result.request_id
                    if key in wound_receipts:
                        same(result,wound_receipts[key],'repeated Lady history changed its consumed Wound')
                        continue
                    lady = record_lady_wound_negation(lady,result.request_id)
                    negations = (*negations,result)
                    wound_receipts[key] = result
                for actor,before,after in _broken_gains(proof):
                    if actor == row.actor_id:
                        lady = record_lady_broken_gain(lady,actor,before,after)
            if row.context.fleeing_breaks_oath and type(proof) in (PcBrokenMoveProof,PcBrokenRunProof,PcNpcExitProof):
                actor = (proof.request.actor_id if type(proof) is PcNpcExitProof else proof.actor_id)
                if actor == row.actor_id:
                    decision = LadyOathDecision('oath-flee:'+str(index),actor,OathDecisionKind.BREACH)
                    if honour is not None:
                        honour = record_honour_bound_oath_decision(honour,decision)
                    if lady is not None:
                        lady = record_lady_oath_decision(lady,decision)
            updated.append(replace(row,honour=honour,lady=lady,honour_uses=uses,lady_uses=negations))
        rows = tuple(updated)
    return rows
