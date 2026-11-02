"""ADR-0057 finite native proposal using existing public ADR-0056 APIs.

Copy with crushed_rib_owner.py, stationary_wound_runner.py,
generation_contract_probe.py and magic_scenario.py. Native57 execution has a
separate public example; this probe emulates no permission/history/dispatcher.
The explicitly manual
membership oracle compares an actual recorded full result and its receipt.
PG1.4 pp108,118,123,156-157,190; GM1.1 p92. Profiles/facts are authored.
"""
from copy import deepcopy
from dataclasses import fields
from random import getstate

from crushed_rib_owner import enemy_first, shooting, attack
from magic_scenario import ScriptedDice
from stationary_wound_runner import authored_input
from towr.domain import NpcCrushedRibContext as Context, NpcCrushedRibConsumptionWitness as Witness
from towr.domain.condition_models import Condition
from towr.domain.cowardly_flight_casting_models import CowardlyFlightCastingFacts
from towr.domain.npc_magic_journal_policy import validate_magic_step_policy
from towr.domain.npc_magic_scenario_result_models import NpcMagicScenarioResult, diagnose_npc_magic_unsupported
from towr.domain.npc_magic_step_models import NpcMagicStep, NpcMagicUnsupportedReason
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult, NpcRosterCastingTargetContext
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_turn_models import NpcRosterTurnStartRequest
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.test_models import TestQuality
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting, apply_npc_roster_casting_result
from towr.rules.npc_roster_turn_resolution import start_npc_roster_turn
from towr.rules.npc_wound_turn_end import end_npc_wound_turn


FIRST_TEN = (1, 2, 3, 10, 10, 10, 10)


def fresh_prefix(source):
    """Run a fresh scenario once, never replay a completed receipt's RNG."""
    before = deepcopy(source)
    dice = ScriptedDice(FIRST_TEN)
    result = run_npc_magic_scenario(source, dice)
    assert dice.calls == 7 and source == before
    assert source.miscast_continuation is None
    assert source.stationary_wound_continuation is None
    assert source.repeated_leg_spasm_continuation is None
    assert source.crushed_rib_continuation is None
    assert result.unsupported.reason in (NpcMagicUnsupportedReason.ACTOR_INJURY,
                                        NpcMagicUnsupportedReason.TARGET_INJURY)
    assert NpcMagicScenarioResult(source, result.steps, result.unsupported) == result
    assert diagnose_npc_magic_unsupported(source, result.current,
        result.unsupported.source_id) == result.unsupported
    state = result.current
    assert state.roster == state.champion_attack.roster == state.minion_attack.roster
    assert state.roster.participant('wizard').state.injury.wounds[-1].table_total == 10
    assert len(state.champion_attack.daily_wounds.receipts) == 1
    assert len(state.champion_attack.consumed_wound_roll_ids) == 1
    return result, dice.calls


def require_recorded_first_consumption(recorded_steps, witness):
    """MANUAL finite oracle, not an implementation of future native admission.

    Only compare the supplied actual recorded first result and complete K1
    receipt. This does not validate arbitrary journals or derive permission.
    """
    for step in recorded_steps:
        result = step.result
        receipt = (result.attack.crushed_rib if isinstance(result, NpcRosterChampionAttackResult)
                   else result.casting.crushed_rib if isinstance(result, NpcRosterCastingResult)
                   else None)
        if receipt is not None:
            if witness.result != result or witness.consumption != receipt:
                raise ValueError('manual oracle: witness differs from the full recorded first consumption')
            return
    raise ValueError('manual oracle: no recorded first consumption')


def require_native_none_refusal(operation):
    """The implemented57 boundary must reject manual56 evidence under None."""
    try:
        operation()
    except ValueError as error:
        assert 'Crushed Rib' in str(error) and 'permission' in str(error), str(error)
    else:
        raise AssertionError('native57 None accepted unpermissioned manual56 evidence')


def main():
    global_rng = getstate()
    total = 0

    # Actual Casting-first source and complete owner application, not an
    # injury-only view. The old step vocabulary already contains these types.
    casting_source = authored_input(stationary=False)
    casting_before = deepcopy(casting_source)
    cast_prefix, draws = fresh_prefix(casting_source)
    total += draws
    original_cast_owner = deepcopy(cast_prefix.current)
    owner = cast_prefix.current
    context = Context(owner, 'wizard', True)
    request = prepare_npc_roster_casting(
        request_id=casting_source.id + ':finite57:casting', state=owner, selected_zone_id='arena',
        targets=(NpcRosterCastingTargetContext('enemy', casting_source.policy_for('enemy').willpower_profile, True),),
        facts=CowardlyFlightCastingFacts(**{f.name: True for f in fields(CowardlyFlightCastingFacts)}),
        policy=casting_source.policy_for('wizard').casting_policy, crushed_rib_context=context)
    cast_dice = ScriptedDice((1, 9, 10, 9))
    cast = NpcRosterCastingResult(request, execute_cowardly_flight_casting(request.casting, cast_dice))
    after_cast = apply_npc_roster_casting_result(owner, cast)
    receipt = cast.casting.crushed_rib
    assert cast_dice.calls == 4 and receipt.casting.test.trace.quality is TestQuality.GRIM
    assert receipt.casting.test.successes == 0 and after_cast.wizard.magic_state.miscast_dice == 2
    assert after_cast.roster.participant('wizard').state.injury == receipt.state
    assert after_cast.roster == after_cast.champion_attack.roster == after_cast.minion_attack.roster
    cast_step = NpcMagicStep(cast)
    assert cast_step.before == owner and cast_step.after == after_cast
    require_native_none_refusal(lambda: validate_magic_step_policy(casting_source, cast_step))
    cast_witness = Witness(cast, receipt)
    require_recorded_first_consumption((*cast_prefix.steps, cast_step), cast_witness)
    end = end_npc_wound_turn(NpcWoundTurnEndRequest(casting_source.id + ':finite57:cast:end',
        after_cast, 'wizard', crushed_rib_context=Context(after_cast, 'wizard', True, cast_witness)))
    assert NpcMagicStep(end).before == after_cast
    assert end.state.roster.participant('wizard').state.injury == receipt.state
    assert owner == original_cast_owner
    total += cast_dice.calls
    print('CASTING-FIRST: fresh legacy stop7d10 -> actual56 failed Grim4d10 -> pool0->2/WAIT -> full-owner end; native57 None-policy refuses its step; Drained/history retained')

    # Two independent fresh executions of equal authored input. No completed
    # Attack is rerun to validate its receipt. Same IDs and post-state do not
    # distinguish the two genuine different observed defender Tests.
    source_a, source_b = enemy_first(), enemy_first()
    sources_before = deepcopy((source_a, source_b))
    assert source_a == source_b and source_a is not source_b
    prefix_a, draws_a = fresh_prefix(source_a)
    prefix_b, draws_b = fresh_prefix(source_b)
    assert prefix_a.steps == prefix_b.steps and prefix_a.current == prefix_b.current
    pending_a, pending_b = deepcopy(prefix_a.current), deepcopy(prefix_b.current)
    identifier = source_a.id + ':finite57:protection'
    first_a, current_a = attack(shooting(source_a, prefix_a.current, identifier,
        Context(prefix_a.current, 'wizard', True)), (10, 10, 10, 1, 6, 10, 9))
    first_b, current_b = attack(shooting(source_b, prefix_b.current, identifier,
        Context(prefix_b.current, 'wizard', True)), (10,) * 6)
    step_a, step_b = NpcMagicStep(first_a), NpcMagicStep(first_b)
    assert step_a.id == step_b.id and first_a.source == first_b.source
    assert current_a == current_b and first_a != first_b
    assert first_a.attack.crushed_rib != first_b.attack.crushed_rib
    assert first_a.attack.crushed_rib.test.trace.initial_values != first_b.attack.crushed_rib.test.trace.initial_values
    assert first_a.attack.crushed_rib.test.successes == first_b.attack.crushed_rib.test.successes == 0
    assert first_b.attack.crushed_rib.test.trace.quality is TestQuality.GRIM
    assert len(first_a.attack.crushed_rib.test.trace.rerolls) == 1
    assert first_b.attack.crushed_rib.test.trace.rerolls == ()
    witness_a, witness_b = Witness(first_a, first_a.attack.crushed_rib), Witness(first_b, first_b.attack.crushed_rib)
    # This acceptance is correct for the standalone ADR56 compatibility API.
    # It is not journal membership, which belongs to the future native bridge.
    Context(current_a, 'wizard', True, witness_b)
    recorded = (*prefix_a.steps, step_a)
    require_recorded_first_consumption(recorded, witness_a)
    try:
        require_recorded_first_consumption(recorded, witness_b)
    except ValueError as error:
        assert 'full recorded first consumption' in str(error)
    else:
        raise AssertionError('manual membership oracle accepted the alternative actual Test')
    assert prefix_a.current == pending_a and prefix_b.current == pending_b
    total += draws_a + draws_b + 7 + 6
    print('PROTECTION-FIRST: independent fresh7+7d10 prefixes; actual Grim7d10 versus zero-initial6d10 have same IDs/full final owner but different complete results/55 receipts')
    print('MANUAL MEMBERSHIP ORACLE: standalone56 accepts compatible alternative witness; explicit recorded full-parent+receipt comparison accepts A and rejects B; no native57 validator invented')

    ended = end_npc_wound_turn(NpcWoundTurnEndRequest(source_a.id + ':finite57:E2:end', current_a, 'E2')).state
    next_owner = start_npc_roster_turn(NpcRosterTurnStartRequest(source_a.id + ':finite57:E3:start', ended,
        'E3', CombatActionDeclaration(CombatActionKind.ATTACK))).state
    next_owner_before = deepcopy(next_owner)
    later, final = attack(shooting(source_a, next_owner, source_a.id + ':finite57:normal',
        Context(next_owner, 'wizard', True, witness_a)), (10,) * 6)
    assert later.attack.crushed_rib is None
    assert later.attack.execution.resolution.attack.defender_test.trace.quality is TestQuality.NORMAL
    assert final.roster.participant('wizard').state.injury == first_a.attack.crushed_rib.state
    Context(final, 'wizard', True, witness_a)
    total += 6
    print('LATER MANUAL56: actual E2 end/E3 start -> normal Protection6d10; first recorded witness, exact Drained injury and full histories retained')

    # The old journal gap is now closed by actual57 None-policy admission.
    # The manual56 action still retains the full pending Wound4 outcome; only
    # its unpermissioned publication/reconstruction is refused.
    gap_source = enemy_first()
    gap_before = deepcopy(gap_source)
    gap_prefix, draws = fresh_prefix(gap_source)
    gap_owner_before = deepcopy(gap_prefix.current)
    gap_id = gap_source.id + ':finite57:current-journal-gap'
    gap, gap_owner = attack(shooting(gap_source, gap_prefix.current, gap_id,
        Context(gap_prefix.current, 'wizard', True)), (1, 2, 3, 10, 10, 10, 1, 3))
    gap_step = NpcMagicStep(gap)
    require_native_none_refusal(lambda: validate_magic_step_policy(gap_source, gap_step))
    assert gap.attack.crushed_rib is not None and gap_owner.champion_attack.pending is not None
    assert tuple(w.table_total for w in gap_owner.roster.participant('wizard').state.injury.wounds) == (10, 4)
    assert len(gap_owner.champion_attack.daily_wounds.receipts) == 2
    assert len(gap_owner.champion_attack.consumed_wound_roll_ids) == 2
    stop = diagnose_npc_magic_unsupported(gap_source, gap_owner, gap_step.id)
    assert stop.reason is NpcMagicUnsupportedReason.WOUND_EFFECT
    require_native_none_refusal(lambda: NpcMagicScenarioResult(gap_source, (*gap_prefix.steps, gap_step), stop))
    total += draws + 8
    print('CLOSED NATIVE GAP: existing Step stores manual56, but actual57 policy + continuous full Result REFUSE it under None; low-level new4/pending WOUND_EFFECT and both receipts retained')

    assert casting_source == casting_before and (source_a, source_b) == sources_before and gap_source == gap_before
    assert cast_prefix.current == original_cast_owner
    assert prefix_a.current == pending_a and prefix_b.current == pending_b
    assert next_owner == next_owner_before and gap_prefix.current == gap_owner_before
    assert final.roster.participant('wizard').state.injury.conditions.has(Condition.DRAINED)
    assert getstate() == global_rng and total == 59
    print('59 scripted d10; legacy runner None still stops after first10/7d10; actual None-policy refusals and full manual56 owners; sources/global RNG unchanged; no57 API emulation or stripped owner')


if __name__ == '__main__':
    main()
