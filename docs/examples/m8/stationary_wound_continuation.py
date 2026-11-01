"""ADR-0049 manual full-owner chain; copy with leg_spasm_stand.py/magic_scenario.py.

PG1.4 Rules pp115-116,118-119,122-123; Wounds Table p190. GM1.1 p92.
Authored numeric profiles and explicit facts; no automatic runner opt-in.
"""
from copy import deepcopy
from random import getstate

from leg_spasm_stand import wounded_case
from magic_scenario import ScriptedDice
from towr.domain.condition_models import Condition
from towr.domain.cowardly_flight_casting_models import CowardlyFlightCastingFacts, CowardlyFlightCastingPolicy
from towr.domain.injury_models import WoundConditionEffect, WoundConditionSourceSnapshot, WoundEntryId
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult, NpcRosterCastingTargetContext
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_leg_spasm_models import NpcRosterLegSpasmStandRequest
from towr.domain.npc_roster_turn_models import NpcRosterTurnStartRequest, NpcRosterRoundAdvanceRequest
from towr.domain.npc_stationary_wound_models import NpcStationaryWoundContext
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind, ImproviseKind
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting, apply_npc_roster_casting_result
from towr.rules.npc_roster_champion_attack_resolution import apply_npc_roster_champion_attack_result
from towr.rules.npc_roster_leg_spasm_resolution import stand_npc_roster_leg_spasm, apply_npc_roster_leg_spasm_stand
from towr.rules.npc_roster_minion_attack_resolution import execute_npc_roster_minion_attack
from towr.rules.npc_roster_shooting_preparation import prepare_npc_roster_shooting
from towr.rules.npc_roster_turn_resolution import start_npc_roster_turn, advance_npc_roster_round
from towr.rules.npc_wound_turn_end import end_npc_wound_turn, apply_npc_wound_turn_end_result


def context(state):
    # The authored scene explicitly excludes external Condition sources.
    return NpcStationaryWoundContext(state, state.wizard.actor_id, True)


def casting_source(state, identifier):
    actor = state.roster.participant(state.wizard.actor_id)
    return prepare_npc_roster_casting(request_id=identifier, state=state, selected_zone_id='arena',
        targets=tuple(NpcRosterCastingTargetContext(p.state.actor_id, InlineProfile(3, 3), True)
                      for p in state.roster.participants if p.state.side is not actor.state.side),
        facts=CowardlyFlightCastingFacts(True, True, True, True, True, True,
                                        True, True, True, True, True, True),
        policy=CowardlyFlightCastingPolicy.CAST_WHEN_READY,
        stationary_wounds=context(state))


def end_turn(state, identifier):
    actor = state.round_state.active_turn.actor_id
    expiries = tuple(e for e in state.wound_expiries if e.actor_id == actor)
    removed = {e.effect for e in expiries}
    injury = state.roster.participant(actor).state.injury
    sources = tuple(WoundConditionSourceSnapshot(condition, any(
        isinstance(e, WoundConditionEffect) and e.condition is condition and e not in removed
        for e in injury.active_wound_effects))
        for condition in dict.fromkeys(e.effect.condition for e in expiries))
    request = NpcWoundTurnEndRequest(identifier, state, actor, sources,
        stationary_wounds=context(state) if actor == state.wizard.actor_id else None)
    return apply_npc_wound_turn_end_result(state, end_npc_wound_turn(request))


def cast_and_end(state, identifier):
    before = deepcopy(state)
    request = casting_source(state, identifier)
    dice = ScriptedDice((10, 10, 10))
    result = NpcRosterCastingResult(request, execute_cowardly_flight_casting(request.casting, dice))
    current = apply_npc_roster_casting_result(state, result)
    assert current.roster.participant(state.wizard.actor_id).state.injury == state.roster.participant(state.wizard.actor_id).state.injury
    final = end_turn(current, identifier + ':end')
    assert state == before and dice.calls == 3
    return final


def start(state, actor, identifier):
    declaration = (CombatActionDeclaration(CombatActionKind.IMPROVISE,
        improvise_kind=ImproviseKind.SPELL, improvise_approach_id='lore:battle-magic')
        if actor == state.wizard.actor_id else CombatActionDeclaration(CombatActionKind.ATTACK))
    return start_npc_roster_turn(NpcRosterTurnStartRequest(identifier, state, actor, declaration)).state


def shooting_turn(state, actor, target, identifier, values):
    state = start(state, actor, identifier + ':start')
    before = deepcopy(state)
    request = prepare_npc_roster_shooting(request_id=identifier, state=state,
        actor_id=actor, target_id=target, selected_attack_id='shot',
        target_range=RangedWeaponRange.SHORT, has_enemy_in_close_range=False,
        range_approved_by_gm=False, defender_is_aware=True,
        selected_protection_skill=Skill.ATHLETICS, can_target_leave_zone=True,
        stationary_wounds=context(state) if target == state.wizard.actor_id else None)
    dice = ScriptedDice(values)
    if target == state.wizard.actor_id:
        assert request.attack.execution.kernel_request.can_target_leave_zone is False
        attack = execute_npc_champion_attack(request.attack, dice)
        current = apply_npc_roster_champion_attack_result(state, NpcRosterChampionAttackResult(request, attack))
    else:
        current = execute_npc_roster_minion_attack(request, dice).state
    assert state == before and dice.calls == len(values)
    return end_turn(current, identifier + ':end')


def main():
    global_rng = getstate()
    scenario, wounded = wounded_case((1, 2, 3, 10, 10, 10, 9), WoundEntryId.LEG_SPASM, opted=False)
    scenario_before, old = deepcopy(scenario), deepcopy(wounded)
    stand = stand_npc_roster_leg_spasm(NpcRosterLegSpasmStandRequest(
        'stationary:stand', wounded, 'wizard', False, True))
    current = apply_npc_roster_leg_spasm_stand(wounded, stand)
    print('WOUND 9: actual registered Leg Spasm; stand spends free move; terrain retained')
    current = cast_and_end(current, 'stationary:r1:wizard')
    print('ROUND 1: bound Casting/end complete; terrain/wound/daily/roll histories retained')
    current = shooting_turn(current, 'ally', 'enemy', 'stationary:r1:ally', (10,) * 6)
    current = advance_npc_roster_round(NpcRosterRoundAdvanceRequest('stationary:r2', current)).state
    current = shooting_turn(current, 'enemy', 'wizard', 'stationary:r2:enemy',
                            (1, 2, 3, 10, 10, 10, 1, 5))
    injury = current.roster.participant('wizard').state.injury
    assert tuple(w.table_total for w in injury.wounds) == (9, 6)
    assert injury.conditions.has(Condition.DRAINED) and len(current.wound_expiries) == 1
    assert current.wound_expiries[0].deadline_round_number == 2
    print('ROUND 2 ATTACK: normal Protection; effective Give Ground=False; actual Wound6 with bound expiry')
    current = start(current, 'wizard', 'stationary:r2:wizard:start')
    current = cast_and_end(current, 'stationary:r2:wizard')
    injury = current.roster.participant('wizard').state.injury
    assert not injury.conditions.has(Condition.DRAINED) and not current.wound_expiries
    assert tuple(w.table_total for w in injury.wounds) == (9, 6)
    print('ROUND 2 WIZARD: bound Casting/end; only timed Drained expires; both wounds and terrain retained')
    current = shooting_turn(current, 'ally', 'enemy', 'stationary:r2:ally', (10,) * 6)
    current = advance_npc_roster_round(NpcRosterRoundAdvanceRequest('stationary:r3', current)).state
    current = shooting_turn(current, 'enemy', 'wizard', 'stationary:r3:enemy', (10,) * 6)
    assert len(context(current).expired_stomach_blow_attack_ids) == 1
    assert len(context(current).terrain_effects) == 1
    assert len(current.champion_attack.daily_wounds.receipts) == 2
    assert current.roster == current.champion_attack.roster == current.minion_attack.roster
    assert wounded == old and scenario == scenario_before and getstate() == global_rng
    print('ROUND 3: Protection admits expired6 history; child rosters synchronized; sources/global RNG immutable')
    print('39 scripted d10; manual full-owner chain; no treatment/healing or automatic runner permission')


if __name__ == '__main__':
    main()
