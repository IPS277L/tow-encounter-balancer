"""ADR-0061 finite controls using actual ADR-0060/0061 public consumers.

Copy with magic_scenario.py. No native permission, history helper or
dispatcher is emulated here. The manual oracle compares complete recorded
results; it is not a general journal validator. Numeric profiles are authored.
PG1.4 Characteristics/Skills pp68-70, Prone p123, Wounds Table p190; GM1.1 p92.
"""
from copy import deepcopy
from dataclasses import fields, replace
from random import getstate

from magic_scenario import ScriptedDice, authored_scenario
from towr.domain.condition_models import Condition
from towr.domain.cowardly_flight_casting_models import CowardlyFlightCastingFacts
from towr.domain.npc_magic_journal_policy import validate_magic_step_policy
from towr.domain.npc_magic_scenario_models import (
    NpcMagicBatteredLegPolicy, NpcMagicMiscastContinuationPolicy, NpcMagicPronePolicy,
)
from towr.domain.npc_magic_battered_leg_policy import (
    initial_magic_battered_leg_history, advance_magic_battered_leg_history,
)
from towr.domain.npc_magic_scenario_result_models import (
    NpcMagicScenarioResult, diagnose_npc_magic_unsupported,
)
from towr.domain.npc_magic_step_models import NpcMagicStep, NpcMagicUnsupportedReason
from towr.domain.npc_roster_battered_leg_models import NpcRosterBatteredLegRequest
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult, NpcRosterCastingTargetContext
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_miscast_models import NpcRosterMiscastFacts, NpcRosterMiscastPolicy
from towr.domain.npc_roster_turn_models import NpcRosterTurnStartRequest, NpcRosterRoundAdvanceRequest
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import (
    CombatActionDeclaration, CombatActionKind, CombatSide, ImproviseKind,
)
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_battered_leg_resolution import (
    apply_npc_roster_battered_leg, execute_npc_roster_battered_leg,
)
from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting
from towr.rules.npc_roster_minion_attack_resolution import execute_npc_roster_minion_attack
from towr.rules.npc_roster_shooting_preparation import prepare_npc_roster_shooting
from towr.rules.npc_roster_turn_resolution import start_npc_roster_turn, advance_npc_roster_round
from towr.rules.npc_wound_turn_end import end_npc_wound_turn


FIRST_FIVE = (1, 2, 3, 10, 10, 10, 5)
ENDURANCE = InlineProfile(2, 5)


def refused(operation, error_type, fragment):
    try:
        operation()
    except error_type as error:
        assert fragment in str(error), str(error)
    else:
        raise AssertionError('expected refusal: ' + fragment)


def require_recorded_completion(recorded_attack, recorded_completion, candidate):
    """Finite MANUAL oracle, not any proposed native61 admission API.

    Comparing the injury, Test ID, success count or source alone would miss
    a different otherwise valid recorded Test trace.
    """
    if candidate.source.attack != recorded_attack or candidate != recorded_completion:
        raise ValueError('manual oracle: different full recorded Attack/completion')


def recorded_history(source, prefix, completed):
    """Production helpers on this actual recorded prefix; no fake validator."""
    scoped = replace(source, battered_leg_continuation=NpcMagicBatteredLegPolicy(ENDURANCE))
    history = initial_magic_battered_leg_history(scoped)
    for step in (*prefix.steps, NpcMagicStep(completed)):
        history = advance_magic_battered_leg_history(scoped, history, step)
    return scoped, history


def post_success_new_condition(source, prefix, completed):
    """Actual normal transitions verify the native diagnosis of scope60.

    No edited injury/combat snapshot, invented native61 helper or skipped turn.
    The last constructor refusal is the current manual60 execution boundary.
    """
    scoped, history = recorded_history(source, prefix, completed)

    def record(result):
        nonlocal history
        history = advance_magic_battered_leg_history(scoped, history, NpcMagicStep(result))

    identifier = source.id + ':manual61:later'
    ended = end_npc_wound_turn(NpcWoundTurnEndRequest(identifier + ':enemy:end', completed.state, 'enemy'))
    record(ended)
    wizard = start_npc_roster_turn(NpcRosterTurnStartRequest(identifier + ':wizard:start',
        ended.state, 'wizard', CombatActionDeclaration(CombatActionKind.IMPROVISE,
            improvise_kind=ImproviseKind.SPELL, improvise_approach_id=source.spell.lore_id)))
    record(wizard)
    casting = prepare_npc_roster_casting(request_id=identifier + ':cast', state=wizard.state,
        selected_zone_id='arena', targets=(NpcRosterCastingTargetContext('enemy',
            source.policy_for('enemy').willpower_profile, True),),
        facts=CowardlyFlightCastingFacts(**{f.name: True for f in fields(CowardlyFlightCastingFacts)}),
        policy=source.policy_for('wizard').casting_policy)
    cast_dice = ScriptedDice((10, 10, 10))
    cast = NpcRosterCastingResult(casting, execute_cowardly_flight_casting(casting.casting, cast_dice))
    assert cast_dice.calls == 3
    record(cast)
    ended = end_npc_wound_turn(NpcWoundTurnEndRequest(identifier + ':wizard:end', cast.state, 'wizard'))
    record(ended)
    ally = start_npc_roster_turn(NpcRosterTurnStartRequest(identifier + ':ally:start',
        ended.state, 'ally', CombatActionDeclaration(CombatActionKind.ATTACK)))
    record(ally)

    def shot(state, actor, target, label):
        pair = next(p for p in source.initial_frame.pair_ranges
                    if {p.first_actor_id, p.second_actor_id} == {actor, target})
        departure = next(d for d in source.initial_frame.attack_departures if d.actor_id == target)
        return prepare_npc_roster_shooting(request_id=identifier + label, state=state,
            actor_id=actor, target_id=target, selected_attack_id=source.policy_for(actor).attack_id,
            target_range=pair.target_range, has_enemy_in_close_range=False,
            range_approved_by_gm=False, defender_is_aware=True, selected_protection_skill=Skill.ATHLETICS,
            can_target_leave_zone=departure.can_leave_zone)

    ally_dice = ScriptedDice((10,) * 6)
    missed = execute_npc_roster_minion_attack(shot(ally.state, 'ally', 'enemy', ':ally:shot'), ally_dice)
    assert ally_dice.calls == 6
    record(missed)
    ended = end_npc_wound_turn(NpcWoundTurnEndRequest(identifier + ':ally:end', missed.state, 'ally'))
    record(ended)
    advanced = advance_npc_roster_round(NpcRosterRoundAdvanceRequest(identifier + ':round', ended.state))
    record(advanced)
    enemy = start_npc_roster_turn(NpcRosterTurnStartRequest(identifier + ':enemy:start',
        advanced.state, 'enemy', CombatActionDeclaration(CombatActionKind.ATTACK)))
    record(enemy)
    shooting = shot(enemy.state, 'enemy', 'wizard', ':enemy:shot')
    hit_dice = ScriptedDice((1, 10, 10, 10, 10, 10))
    hit = NpcRosterChampionAttackResult(shooting, execute_npc_champion_attack(shooting.attack, hit_dice))
    assert hit_dice.calls == 6
    record(hit)
    updated = hit.state
    injury = updated.roster.participant('wizard').state.injury
    assert injury.conditions.has(Condition.STAGGERED)
    assert updated.champion_attack.pending is None
    assert updated.battered_leg_receipt == completed.state.battered_leg_receipt
    stop = diagnose_npc_magic_unsupported(scoped, updated, identifier + ':enemy:shot',
        battered_leg_history=history, previous=NpcMagicStep(hit))
    assert stop.reason is NpcMagicUnsupportedReason.END_TURN
    assert stop.actor_id == 'enemy' and stop.missing_actor_ids == ('wizard',)
    refused(lambda: end_npc_wound_turn(NpcWoundTurnEndRequest(identifier + ':blocked:end',
        updated, 'enemy')), ValueError, 'outside the completed Test scope')
    print('CLOSED SCOPE GAP: actual WAIT/ally miss/next-round hit adds Wizard Staggered; native61 diagnoses END_TURN before normal end60; full receipt retained')
    return cast_dice.calls + ally_dice.calls + hit_dice.calls


def main():
    global_rng = getstate()
    source = authored_scenario(wizard_side=CombatSide.OPPOSITION)
    original = deepcopy(source)
    dice = ScriptedDice(FIRST_FIVE)
    prefix = run_npc_magic_scenario(source, dice)
    assert dice.calls == 7 and source == original
    assert prefix.unsupported.reason is NpcMagicUnsupportedReason.WOUND_EFFECT
    assert prefix.unsupported.actor_id == 'enemy'
    assert prefix.unsupported.missing_actor_ids == ('wizard',)
    assert NpcMagicScenarioResult(source, prefix.steps, prefix.unsupported) == prefix
    attack = prefix.steps[-1].result
    assert isinstance(attack, NpcRosterChampionAttackResult)
    assert prefix.unsupported.source_id == attack.attack.execution.request_id
    state = prefix.current
    state_before = deepcopy(state)
    assert state.champion_attack.pending == attack.attack
    assert state.round_state.active_turn.actor_id == 'enemy'
    assert state.round_state.active_turn.action_slots[0].executed
    assert state.battered_leg_receipt is None
    request = NpcRosterBatteredLegRequest(source.id + ':manual61:endurance',
        state, attack, ENDURANCE, source.facts.unmounted_combatants_only,
        source.facts.no_external_condition_sources)
    assert request.k1_request.actor_id == 'wizard'
    assert request.k1_request.endurance_test.id == attack.attack.pending_follow_ups[0].test_id
    print('NATIVE CONTROL: first Wound5 -> exact WOUND_EFFECT stop after 7d10; active enemy, affected Wizard; pending/daily/roll histories retained')

    results = []
    for values, succeeded in (((1, 10), True), ((2, 10), True), ((10, 10), False)):
        test_dice = ScriptedDice(values)
        result = execute_npc_roster_battered_leg(request, test_dice)
        after = apply_npc_roster_battered_leg(state, result)
        assert test_dice.calls == 2 and result.endurance.test_result.succeeded is succeeded
        assert after.champion_attack.pending is None
        assert after.roster == after.champion_attack.roster == after.minion_attack.roster
        assert after.battered_leg_receipt.attack == attack
        assert after.battered_leg_receipt.endurance == result.endurance
        assert after.round_state == state.round_state
        assert after.spatial_state == state.spatial_state
        assert after.wizard == state.wizard
        assert after.consumed_execution_ids == state.consumed_execution_ids
        assert after.champion_attack.daily_wounds == state.champion_attack.daily_wounds
        assert after.champion_attack.consumed_wound_roll_ids == state.champion_attack.consumed_wound_roll_ids
        assert after.roster.participant('wizard').state.injury.conditions.has(Condition.PRONE) is (not succeeded)
        refused(lambda: apply_npc_roster_battered_leg(after, result), ValueError, 'already consumed')
        step = NpcMagicStep(result)
        assert step.actor_id == 'wizard' and step.before.round_state.active_turn.actor_id == 'enemy'
        refused(lambda: validate_magic_step_policy(source, step), ValueError, 'permission')
        results.append(result)
    success, alternate_success, failure = results
    print('MANUAL60: success, alternate success and failure each use 2d10; exact follow-up closes once; no extra action; failure retains Wound-sourced Prone')
    assert success.source == alternate_success.source
    assert success.endurance.wound_result.state == alternate_success.endurance.wound_result.state
    assert success.endurance.test_result.successes == alternate_success.endurance.test_result.successes
    assert success.endurance.test_result != alternate_success.endurance.test_result
    require_recorded_completion(attack, success, success)
    refused(lambda: require_recorded_completion(attack, success, alternate_success),
            ValueError, 'full recorded Attack/completion')
    print('MANUAL ORACLE: equal source/Test ID/successes/injury do not identify the full recorded Endurance trace; alternate actual completion refused')

    other_profile = replace(request, endurance_profile=InlineProfile(2, 4))
    profile_dice = ScriptedDice((1, 10))
    rebound = execute_npc_roster_battered_leg(other_profile, profile_dice)
    assert profile_dice.calls == 2 and rebound.source.endurance_profile != ENDURANCE
    assert rebound.endurance.wound_result.state == success.endurance.wound_result.state
    refused(lambda: require_recorded_completion(attack, success, rebound),
            ValueError, 'full recorded Attack/completion')
    print('PROFILE AUTHORITY: another authored profile can produce equal injury; manual oracle still refuses substitution; native profile must belong to Scenario')

    for result in (success, failure):
        after = result.state
        ended = end_npc_wound_turn(NpcWoundTurnEndRequest(source.id + ':manual61:enemy:end',
            after, 'enemy'))
        refused(lambda: validate_magic_step_policy(source, NpcMagicStep(ended)), ValueError, 'permission')
        scoped, history = recorded_history(source, prefix, result)
        history = advance_magic_battered_leg_history(scoped, history, NpcMagicStep(ended))
        wizard = start_npc_roster_turn(NpcRosterTurnStartRequest(source.id + ':manual61:wizard:start',
            ended.state, 'wizard', CombatActionDeclaration(CombatActionKind.IMPROVISE,
                improvise_kind=ImproviseKind.SPELL, improvise_approach_id=source.spell.lore_id)))
        history = advance_magic_battered_leg_history(scoped, history, NpcMagicStep(wizard))
        stop = diagnose_npc_magic_unsupported(scoped, wizard.state, wizard.source.id,
            battered_leg_history=history, previous=NpcMagicStep(wizard))
        if result is success:
            assert stop is None
        else:
            assert stop.reason is NpcMagicUnsupportedReason.ACTOR_INJURY
            assert stop.actor_id == 'wizard'
            assert wizard.state.battered_leg_receipt == after.battered_leg_receipt
        # Omitting the unsupported completion Step cannot bridge the state gap.
        refused(lambda: NpcMagicScenarioResult(source, (*prefix.steps, NpcMagicStep(ended))),
                ValueError, 'continuous full-owner')
    print('CLOSED JOURNAL BOUNDARY: Step admits completion60 with Wizard actor; native61 None refuses completion and descendants; skipping completion fails continuous Result admission')
    print('FAILURE TAIL: enemy end then Wizard start retains Prone/receipt and yields ACTOR_INJURY')

    opted = replace(source, miscast_continuation=NpcMagicMiscastContinuationPolicy(
        NpcRosterMiscastPolicy.DECLINE_CAST_BEFORE_MISCAST,
        NpcRosterMiscastFacts(True, True, True, True, True),
        NpcMagicPronePolicy.SELF_STAND_WHEN_SAFE))
    opted_before = deepcopy(opted)
    opted_dice = ScriptedDice(FIRST_FIVE)
    opted_prefix = run_npc_magic_scenario(opted, opted_dice)
    assert opted_dice.calls == 7 and opted_prefix.unsupported.reason is NpcMagicUnsupportedReason.WOUND_EFFECT
    opted_request = replace(request, state=opted_prefix.current, attack=opted_prefix.steps[-1].result)
    opted_test = ScriptedDice((10, 10))
    failed = execute_npc_roster_battered_leg(opted_request, opted_test)
    assert opted_test.calls == 2
    ended = end_npc_wound_turn(NpcWoundTurnEndRequest(source.id + ':manual61:opted:end', failed.state, 'enemy'))
    wizard = start_npc_roster_turn(NpcRosterTurnStartRequest(source.id + ':manual61:opted:start',
        ended.state, 'wizard', CombatActionDeclaration(CombatActionKind.IMPROVISE,
            improvise_kind=ImproviseKind.SPELL, improvise_approach_id=source.spell.lore_id)))
    scoped, history = recorded_history(opted, opted_prefix, failed)
    history = advance_magic_battered_leg_history(scoped, history, NpcMagicStep(ended))
    history = advance_magic_battered_leg_history(scoped, history, NpcMagicStep(wizard))
    stop = diagnose_npc_magic_unsupported(scoped, wizard.state, wizard.source.id,
        battered_leg_history=history, previous=NpcMagicStep(wizard))
    assert stop.reason is NpcMagicUnsupportedReason.ACTOR_INJURY and opted == opted_before
    print('INDEPENDENT MISCAST OPT-IN: same 7d10 Wound stop; manual failure 2d10 still yields sourced-Prone ACTOR_INJURY, without a stand')

    stripped = replace(state, champion_attack=replace(state.champion_attack, pending=None))
    refused(lambda: end_npc_wound_turn(NpcWoundTurnEndRequest(source.id + ':manual61:stripped:end',
        stripped, 'enemy')), ValueError, 'Battered Leg')
    later_draws = post_success_new_condition(source, prefix, success)
    assert state == state_before and source == original and getstate() == global_rng
    assert dice.calls + 3 * 2 + profile_dice.calls + opted_dice.calls + opted_test.calls + later_draws == 39
    print('39 scripted d10; actual native61 permission/history/diagnosis + manual60; pending stripping refused; sources/global RNG unchanged; automatic runner has a separate public example')


if __name__ == '__main__':
    main()
