"""ADR-0052 public second stand with both actual full-owner witnesses.

Copy with stationary_wound_runner.py and magic_scenario.py. PG1.4 Rules116,
119,122-123/Wounds190; GM1.1 Champions92. Numeric profiles/facts are authored.
No automatic runner/journal permission is added by this manual transition.
"""
from copy import deepcopy
from dataclasses import fields, replace
from random import getstate

from magic_scenario import ScriptedDice
from stationary_wound_runner import authored_input
from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundConditionEffect, WoundEffectDuration, WoundEntryId, WoundRestriction
from towr.domain.npc_magic_step_models import NpcMagicStep, NpcMagicUnsupportedReason
from towr.domain.npc_magic_journal_policy import validate_magic_step_policy
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult, NpcRosterCastingTargetContext
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_leg_spasm_models import NpcRosterLegSpasmStandResult
from towr.domain.npc_roster_repeated_leg_spasm_models import NpcRosterRepeatedLegSpasmStandRequest
from towr.domain.npc_stationary_wound_models import NpcStationaryWoundContext
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.test_models import TestQuality
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting, apply_npc_roster_casting_result
from towr.rules.npc_roster_repeated_leg_spasm_resolution import (
    stand_npc_roster_repeated_leg_spasm, apply_npc_roster_repeated_leg_spasm_stand,
)
from towr.rules.npc_wound_turn_end import end_npc_wound_turn, apply_npc_wound_turn_end_result


def rejected(operation, error_type=ValueError):
    try:
        operation()
    except error_type:
        return
    raise AssertionError('unsupported or stale transition unexpectedly accepted')


def main():
    global_rng = getstate()
    source = authored_input()
    source_before = deepcopy(source)
    hit = (1, 2, 3, 10, 10, 10)
    values = (*hit, 9, *((10,) * 9), *hit, 4, 5)
    dice = ScriptedDice(values)
    stopped = run_npc_magic_scenario(source, dice)
    assert dice.calls == len(values) == 24
    assert stopped.unsupported.reason is NpcMagicUnsupportedReason.ACTOR_INJURY
    previous_stands = tuple(s.result for s in stopped.steps if isinstance(s.result, NpcRosterLegSpasmStandResult))
    attacks = tuple(s.result for s in stopped.steps if isinstance(s.result, NpcRosterChampionAttackResult))
    assert len(previous_stands) == 1 and len(attacks) == 2
    previous, attack = previous_stands[0], attacks[1]
    current = stopped.current
    before = deepcopy(current)
    actor_id = current.wizard.actor_id
    old_injury = current.roster.participant(actor_id).state.injury
    assert tuple(w.entry_id for w in old_injury.wounds) == (WoundEntryId.LEG_SPASM,) * 2
    assert tuple(w.roll_values for w in old_injury.wounds) == ((9,), (4, 5))
    assert attack.source.state.roster.participant(actor_id).state.injury == previous.state.roster.participant(actor_id).state.injury
    assert attack.state.roster.participant(actor_id).state.injury == old_injury
    assert not current.wound_expiries
    assert current.round_state.round_number == 2 > previous.source.state.round_state.round_number
    assert current.round_state.active_turn.actor_id == actor_id
    print('ACTUAL: 24 scripted d10; first9 -> stand48 -> Casting/end -> second9; unchanged runner actor-injury stop')

    # All hostile ranges are explicitly authored. Zone equality does not stand
    # in for the required no-enemy-Close fact.
    enemies = {p.state.actor_id for p in current.roster.participants
               if p.state.side is not current.roster.participant(actor_id).state.side}
    pairs = tuple(p for p in source.initial_frame.pair_ranges
                  if actor_id in (p.first_actor_id, p.second_actor_id))
    assert {next(a for a in (p.first_actor_id, p.second_actor_id) if a != actor_id) for p in pairs} == enemies
    assert all(p.target_range is not RangedWeaponRange.CLOSE for p in pairs)
    assert source.facts.no_external_condition_sources is True
    request = NpcRosterRepeatedLegSpasmStandRequest('repeat:bound-stand', current, actor_id,
        False, True, previous, attack)
    stand = stand_npc_roster_repeated_leg_spasm(request)
    standing = apply_npc_roster_repeated_leg_spasm_stand(current, stand)
    injury = standing.roster.participant(actor_id).state.injury
    expected_removed = (WoundConditionEffect(old_injury.wounds[-1].sequence,
        Condition.PRONE, WoundEffectDuration.UNTIL_REMOVED),)
    assert stand.source is request and stand.removed_effects == expected_removed
    assert not injury.conditions.has(Condition.PRONE)
    assert injury.wounds == old_injury.wounds
    assert injury.active_wound_effects == tuple(e for e in old_injury.active_wound_effects if e not in expected_removed)
    assert len(injury.active_wound_effects) == 2
    assert all(e.restriction is WoundRestriction.MOVEMENT_IS_DIFFICULT_TERRAIN for e in injury.active_wound_effects)
    assert standing.spatial_state == replace(current.spatial_state,
        free_move_used_entity_ids=(*current.spatial_state.free_move_used_entity_ids, actor_id))
    for field in fields(current):
        if field.name not in ('roster', 'spatial_state', 'champion_attack', 'minion_attack'):
            assert getattr(standing, field.name) == getattr(current, field.name), field.name
    for name in ('champion_attack', 'minion_attack'):
        assert getattr(standing, name) == replace(getattr(current, name), roster=standing.roster)
    assert standing.roster == standing.champion_attack.roster == standing.minion_attack.roster
    assert current == before
    print('BOUND REPEAT: full stand48 + actual Attack witnesses; only new Prone cause removed; one free move; both terrains retained')
    print('OWNER: wounds/d10/daily/roll/consumed histories and positions/actions/magic retained; both child rosters synchronized')

    rejected(lambda: apply_npc_roster_repeated_leg_spasm_stand(standing, stand))
    foreign = replace(current, consumed_execution_ids=(*current.consumed_execution_ids, 'foreign'))
    rejected(lambda: apply_npc_roster_repeated_leg_spasm_stand(foreign, stand))
    rejected(lambda: validate_magic_step_policy(source, NpcMagicStep(stand)))
    rejected(lambda: replace(request, actor_has_enemy_in_close_range=True))
    rejected(lambda: replace(request, underlying_cause_allows_removal=False))
    assert current == before
    print('GUARDS: stale/replay/Close/external-cause refusal; new result excluded from automatic journal; sources immutable')

    context = NpcStationaryWoundContext(standing, actor_id, True)
    assert context.terrain_effects == injury.active_wound_effects
    assert context.can_give_ground is False and not context.active_stomach_blows
    first_cast = next(s.result for s in stopped.steps if isinstance(s.result, NpcRosterCastingResult))
    frame = source.initial_frame
    plans = {p.actor_id: p for p in frame.give_ground_plans}
    targets = tuple(NpcRosterCastingTargetContext(p.state.actor_id,
        source.policy_for(p.state.actor_id).willpower_profile, plans[p.state.actor_id].can_leave_zone)
        for p in standing.roster.participants if p.state.actor_id in enemies
        and standing.spatial_state.placement_for(p.state.actor_id).zone_id == 'arena')
    casting = prepare_npc_roster_casting(request_id='repeat:casting', state=standing,
        selected_zone_id='arena', targets=targets, facts=first_cast.source.casting.facts,
        policy=source.policy_for(actor_id).casting_policy, stationary_wounds=context)
    cast_dice = ScriptedDice((10, 10, 10))
    cast_result = NpcRosterCastingResult(casting, execute_cowardly_flight_casting(casting.casting, cast_dice))
    cast = apply_npc_roster_casting_result(standing, cast_result)
    assert cast_dice.calls == 3 and cast.pending_miscast is None and cast.pending_movement is None
    trace = cast_result.casting.execution.casting.test.trace
    assert trace.quality is TestQuality.NORMAL and trace.regular_dice_delta == 0
    assert trace.rolled_dice == standing.wizard.caster.casting_profile.dice == 3
    end_request = NpcWoundTurnEndRequest('repeat:end', cast, actor_id,
        stationary_wounds=NpcStationaryWoundContext(cast, actor_id, True))
    final = apply_npc_wound_turn_end_result(cast, end_npc_wound_turn(end_request))
    assert final.round_state.active_turn is None
    assert final.roster.participant(actor_id).state.injury == injury
    assert final.champion_attack.daily_wounds == standing.champion_attack.daily_wounds
    assert final.champion_attack.consumed_wound_roll_ids == standing.champion_attack.consumed_wound_roll_ids
    assert final.roster == final.champion_attack.roster == final.minion_attack.roster
    assert len(NpcStationaryWoundContext(final, actor_id, True).terrain_effects) == 2
    assert standing.roster.participant(actor_id).state.injury == injury
    print('POST-STAND: existing context49 -> bound Casting/end; 3 d10; normal Test; no Prone penalty; Give Ground=False')

    legacy = authored_input(stationary=False)
    legacy_before = deepcopy(legacy)
    legacy_dice = ScriptedDice((*hit, 9))
    legacy_result = run_npc_magic_scenario(legacy, legacy_dice)
    assert legacy_dice.calls == 7
    assert legacy_result.unsupported.reason is NpcMagicUnsupportedReason.ACTOR_INJURY
    assert legacy_result.current == previous.source.state
    assert source == source_before and legacy == legacy_before and current == before
    assert getstate() == global_rng
    print('NONE CONTROL: 7 d10; first9 stop; automatic repeated9 scope remains unchanged')
    print('34 scripted d10 total; public full-owner consumer only; no stand RNG/Test/treatment/healing or runner permission')


if __name__ == '__main__':
    main()
