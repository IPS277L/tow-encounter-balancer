"""ADR-0056 finite owner-bridge proposal; existing public APIs only.

Copy with stationary_wound_runner.py, generation_contract_probe.py and magic_scenario.py. PG1.4 pp108,
118,123,156-157,190; GM1.1 p92. Numeric profiles are authored. Completed
K1 injuries never enter an M8 owner. Protection uses a real current second
enemy turn after the first actual Wound, without executing that M8 action.
"""
from copy import deepcopy
from dataclasses import fields, replace
from random import getstate

from magic_scenario import ScriptedDice
from stationary_wound_runner import authored_input
from generation_contract_probe import authored_reserve
from towr.domain.action_execution_models import CastingAttemptExecutionRequest, CastingActionPostTestRequest, AttackActionExecutionRequest
from towr.domain.condition_models import Condition
from towr.domain.cowardly_flight_casting_models import (
    CowardlyFlightCastingRequest, CowardlyFlightCastingTarget, CowardlyFlightCastingFacts,
    CowardlyFlightCastingPolicy,
)
from towr.domain.cowardly_flight_casting_result_models import CowardlyFlightCastingResult, CowardlyFlightCastingStatus
from towr.domain.crushed_rib_test_models import CrushedRibCastingPreparationRequest, CrushedRibTestPreparationRequest
from towr.domain.magic_models import CastingTestRequest, CastingDecisionRequest, CastingChoice
from towr.domain.npc_magic_scenario_result_models import NpcMagicScenarioResult, diagnose_npc_magic_unsupported
from towr.domain.npc_magic_step_models import NpcMagicUnsupportedReason
from towr.domain.npc_roster_casting_models import NpcRosterCastingRequest
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_champion_attack_models import NpcChampionAttackRequest
from towr.domain.npc_attack_preparation_models import NpcAttackPreparationRequest
from towr.domain.npc_roster_turn_models import NpcRosterTurnStartRequest, NpcRosterTurnStartResult
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest, NpcWoundTurnEndResult
from towr.domain.protection_models import ProtectionPreparationRequest
from towr.domain.resolution_models import KernelAttackRequest
from towr.domain.test_models import TestRequest, TestQuality, Skill
from towr.domain.turn_models import CombatSide, CombatRoundState, CombatActionKind, CombatActionDeclaration
from towr.domain.npc_roster_models import NpcRoster
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.attack_resolution import resolve_attack
from towr.rules.casting_action_execution import execute_casting_attempt, resolve_casting_action_post_test
from towr.rules.crushed_rib_test_resolution import (
    prepare_crushed_rib_casting, complete_crushed_rib_casting,
    prepare_crushed_rib_test, complete_crushed_rib_test, apply_crushed_rib_test_result,
)
from towr.rules.protection_preparation import prepare_protection
from towr.rules.npc_attack_preparation import prepare_npc_attack, prepare_npc_attack_protection
from towr.rules.npc_roster_turn_resolution import start_npc_roster_turn, apply_npc_roster_turn_start_result
from towr.rules.npc_wound_turn_end import end_npc_wound_turn, apply_npc_wound_turn_end_result


def refused(call, text):
    try:
        call()
    except (TypeError, ValueError) as error:
        assert text in str(error), str(error)
        return
    raise AssertionError('expected existing admission refusal')


def main():
    global_rng = getstate()
    source = authored_input()
    source_before = deepcopy(source)
    dice = ScriptedDice((1, 2, 3, 10, 10, 10, 10))
    stopped = run_npc_magic_scenario(source, dice)
    assert dice.calls == 7 and stopped.unsupported.reason is NpcMagicUnsupportedReason.ACTOR_INJURY
    assert NpcMagicScenarioResult(source, stopped.steps, stopped.unsupported) == stopped
    owner = stopped.current
    owner_before = deepcopy(owner)
    actor = owner.wizard.actor_id
    injury = owner.roster.participant(actor).state.injury
    assert injury.wounds[0].table_total == 10 and injury.wounds[0].effect_resolved
    assert owner.roster == owner.champion_attack.roster == owner.minion_attack.roster
    assert len(owner.champion_attack.daily_wounds.receipts) == 1
    assert len(owner.champion_attack.consumed_wound_roll_ids) == 1
    assert owner.round_state.active_turn.actor_id == actor
    assert not owner.round_state.active_turn.action_slots[0].executed
    print('ACTUAL OWNER: Wound10 in7d10; Wizard standard spell slot reserved; daily/roll histories and both children retained; actor-injury stop')

    # This lower action source uses the ACTUAL current Wizard slot, definition,
    # magic/spatial snapshots and ordered enemy target. Its full-owner wrapper
    # still rejects the pending restriction; no injury is removed to bypass it.
    target = owner.roster.participant('enemy')
    target_policy = next(a for a in source.actors if a.actor_id == 'enemy')
    action = CowardlyFlightCastingRequest(
        'finite:owner56:casting', owner.wizard.caster, actor, owner.casting_round_state, 1,
        owner.wizard.magic_state, owner.casting_spatial_state, 'arena',
        (CowardlyFlightCastingTarget('enemy', target_policy.willpower_profile, target.state.injury, True),),
        CowardlyFlightCastingFacts(**{f.name: True for f in fields(CowardlyFlightCastingFacts)}),
        CowardlyFlightCastingPolicy.CAST_WHEN_READY)
    refused(lambda: NpcRosterCastingRequest(owner, action), 'Wound10 requires')
    original_casting = CastingTestRequest(action.id + ':casting', actor, source.spell.lore_id,
        TestRequest(action.id + ':willpower', action.caster.casting_profile), action.magic_state)
    prepared = prepare_crushed_rib_casting(CrushedRibCastingPreparationRequest(
        action.id + ':crushed-rib', actor, injury, original_casting))
    assert owner == owner_before and prepared.source_request.state == injury
    cast_dice = ScriptedDice((1, 9, 10, 9))
    execution = execute_casting_attempt(CastingAttemptExecutionRequest(action.id, action.round_state,
        actor, action.slot_index, prepared.casting), cast_dice)
    consumed = complete_crushed_rib_casting(prepared, execution.casting)
    assert cast_dice.calls == 4 and execution.casting.test.trace.quality is TestQuality.GRIM
    assert execution.casting.test.trace.final_values == (9, 9, 10)
    assert execution.casting.test.successes == 0 and execution.casting.miscast_dice_added == 2
    assert apply_crushed_rib_test_result(actor, injury, consumed) == consumed.state
    assert consumed.state.conditions.has(Condition.DRAINED) and consumed.state.wounds == injury.wounds
    assert execution.previous_state == owner.casting_round_state and execution.slot.executed
    assert execution.slot.execution.id == action.id
    assert execution.slot.execution.source_request_id == original_casting.id
    # Actual completion above precedes the real post-Test pool/decision. The
    # pure anticipated pool view is only the existing decision's required input.
    decision_state = replace(execution.casting.state, miscast_dice=2)
    post = resolve_casting_action_post_test(CastingActionPostTestRequest(action.id + ':post-test',
        execution, action.caster.wizard_level, CastingDecisionRequest(action.id + ':post-test:decision',
            actor, decision_state, action.caster.wizard_level, CastingChoice.WAIT)))
    assert post.state == decision_state and post.execution == execution
    assert post.miscast_pool.previous_miscast_dice == 0
    assert post.miscast_pool.dice_added == execution.casting.follow_ups[0].amount == 2
    assert post.state.miscast_dice == 2 and post.decision.choice is CastingChoice.WAIT
    refused(lambda: CowardlyFlightCastingResult(action, execution, post, CowardlyFlightCastingStatus.WAITING),
            'normal Test trace/profile')
    assert owner == owner_before and owner.wizard.magic_state.miscast_dice == 0
    print('CASTING CANDIDATE: actual slot-bound Grim4d10; failed Test consumes in K1 before real pool0->2/WAIT; lower normal-result and full-owner guards still refuse')

    # Independent fresh five-actor fixture: enemies act first. All source
    # scheduling changes are authored BEFORE play, never on an injured owner.
    reserve = authored_reserve()
    roster = NpcRoster(tuple(replace(p, state=replace(p.state, side=(
        CombatSide.OPPOSITION if p.state.actor_id in ('wizard', 'ally') else CombatSide.PLAYERS_AND_ALLIES)))
        for p in reserve.initial.roster.participants))
    combat = CombatRoundState(1, roster.turn_participants)
    def positions(values):
        return tuple(replace(p, side_id=roster.participant(p.entity_id).state.side.value) for p in values)
    spatial = replace(reserve.initial.spatial_state, placements=positions(reserve.initial.spatial_state.placements))
    initial = replace(reserve.initial, roster=roster, round_state=combat, spatial_state=spatial,
                      champion_attack=replace(reserve.initial.champion_attack, roster=roster, round_state=combat))
    reserve = replace(reserve, initial=initial, activation_order=('E1', 'E2', 'E3', 'wizard', 'ally'),
        perspective_side=CombatSide.OPPOSITION,
        scene_frames=tuple(replace(f, key=replace(f.key, placements=positions(f.key.placements)))
                           for f in reserve.scene_frames))
    reserve_before = deepcopy(reserve)
    reserve_dice = ScriptedDice((1, 2, 3, 10, 10, 10, 10))
    reserve_stopped = run_npc_magic_scenario(reserve, reserve_dice)
    assert reserve_dice.calls == 7
    assert reserve_stopped.unsupported.reason is NpcMagicUnsupportedReason.TARGET_INJURY
    assert NpcMagicScenarioResult(reserve, reserve_stopped.steps, reserve_stopped.unsupported) == reserve_stopped
    first = next(s.result for s in reserve_stopped.steps if isinstance(s.result, NpcRosterChampionAttackResult))
    assert first.source.attack.execution.actor_id == 'E1'
    first_owner = first.state
    actual_end = next(s.result for s in reserve_stopped.steps
                      if isinstance(s.result, NpcWoundTurnEndResult) and s.result.source.actor_id == 'E1')
    actual_start = next(s.result for s in reserve_stopped.steps
                        if isinstance(s.result, NpcRosterTurnStartResult) and s.result.source.actor_id == 'E2')
    end = end_npc_wound_turn(NpcWoundTurnEndRequest(actual_end.source.id, first_owner, 'E1'))
    ended = apply_npc_wound_turn_end_result(first_owner, end)
    start = start_npc_roster_turn(NpcRosterTurnStartRequest(actual_start.source.id, ended, 'E2',
        CombatActionDeclaration(CombatActionKind.ATTACK)))
    current = apply_npc_roster_turn_start_result(ended, start)
    assert end == actual_end and start == actual_start and current == reserve_stopped.current
    current_before = deepcopy(current)
    assert reserve_dice.calls == 7  # Scheduling performs no Test.
    assert current.round_state.active_turn.actor_id == 'E2'
    assert not current.round_state.active_turn.action_slots[0].executed
    assert current.round_state.completed_turn_entity_ids == ('E1',)
    assert current.roster == first_owner.roster == current.champion_attack.roster
    assert current.minion_attack.roster == current.roster
    assert current.champion_attack.daily_wounds == first_owner.champion_attack.daily_wounds
    assert current.champion_attack.consumed_wound_roll_ids == first_owner.champion_attack.consumed_wound_roll_ids
    pending_injury = current.roster.participant(actor).state.injury
    assert pending_injury == injury
    attacking = current.roster.participant('E2')
    defending = current.roster.participant(actor)
    pair = next(p for p in reserve.initial_frame.pair_ranges
                if {p.first_actor_id, p.second_actor_id} == {'E2', actor})
    action_id = 'finite:owner56:second-shot'
    npc = prepare_npc_attack(NpcAttackPreparationRequest(action_id + ':prepare', action_id + ':attack',
        action_id + ':attacker-test', attacking.attack_snapshot(action_id + ':snapshot'),
        reserve.policy_for('E2').attack_id, actor, pair.target_range, defending.state.current_resilience,
        False, attacking.state.injury.conditions.has(Condition.STAGGERED), False))
    protected = prepare_npc_attack_protection(npc, ProtectionPreparationRequest(action_id + ':protect',
        actor, npc.attack, Skill.SHOOTING, reserve.facts.targets_aware, False,
        defending.state.wields_weapon, defending.state.holds_shield, Skill.ATHLETICS,
        defending.protection_options(action_id + ':protection-test')))
    departure = next(d for d in reserve.initial_frame.attack_departures if d.actor_id == actor)
    attack_execution = AttackActionExecutionRequest(action_id, current.round_state, 'E2', actor, 1,
        KernelAttackRequest(action_id + ':kernel', actor, protected.attack, defending.definition.injury_policy,
            pending_injury, departure.can_leave_zone, actor in current.spatial_state.gave_ground_entity_ids))
    refused(lambda: NpcChampionAttackRequest(current.champion_attack, protected, attack_execution),
            'supports only initial Staggered')
    protection_source = protected.protection.source_request
    selected = next(o for o in protection_source.options if o.skill is protection_source.selected_skill)
    assert selected.defender_id == actor and selected.test == protected.attack.defender_test
    assert selected.test.profile == next(p.test_profile for p in defending.definition.protection
                                        if p.skill is selected.skill)
    test_prepared = prepare_crushed_rib_test(CrushedRibTestPreparationRequest(
        'finite:owner56:protection', actor, pending_injury, selected.test))
    protection = prepare_protection(replace(protection_source, options=tuple(
        replace(o, test=test_prepared.test) if o.skill is selected.skill else o for o in protection_source.options)))
    attack_dice = ScriptedDice((1, 2, 3, 1, 6, 10, 9))
    attacked = resolve_attack(protection.attack, attack_dice)
    protection_consumed = complete_crushed_rib_test(test_prepared, attacked.defender_test)
    assert attack_dice.calls == 7 and attacked.defender_test.trace.quality is TestQuality.GRIM
    assert attacked.defender_test.successes == 0 and attacked.attacker_test.trace.quality is TestQuality.NORMAL
    assert attacked.request_id == protected.attack.id
    assert apply_crushed_rib_test_result(actor, pending_injury, protection_consumed) == consumed.state
    assert current == current_before and reserve == reserve_before
    assert not current.round_state.active_turn.action_slots[0].executed
    assert owner == owner_before  # No kernel retry, Wound roll or owner mutation.
    print('PROTECTION OWNER: fresh Wound10 in7d10; actual E1 end/E2 start without Tests; current unspent Attack slot, full injury/daily/roll/children retained')
    print('PROTECTION CANDIDATE: current E2 Shooting/selected Athletics; one K1 attack7d10; actual defender Test consumes; normal Champion admission refuses; no M8 action applied')
    print('BOUNDARY GAP: kernel has no post-Test continuation input; no new Wound/daily receipt/action application fabricated; full-owner56 bridge remains unimplemented')
    assert diagnose_npc_magic_unsupported(source, owner, stopped.unsupported.source_id) == stopped.unsupported
    assert source == source_before and owner == owner_before and getstate() == global_rng
    assert dice.calls + cast_dice.calls + reserve_dice.calls + attack_dice.calls == 25
    print('25 scripted d10; real current action sources and K1 receipts; no consumed injury enters M8; immutable sources/owners/global RNG; no future bridge fabricated')


if __name__ == '__main__':
    main()
