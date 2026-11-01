"""ADR-0053 finite native-permission/history boundary, using existing APIs only.

Copy with stationary_wound_runner.py and magic_scenario.py. PG1.4 Rules116,
119,122-123/Wounds190; GM1.1 Champions92. Numeric profiles/facts are authored.
No proposed permission/Scenario type or future journal validator is simulated.
"""
from copy import deepcopy
from dataclasses import replace
from random import getstate

from magic_scenario import ScriptedDice
from stationary_wound_runner import authored_input
from towr.domain.condition_models import Condition
from towr.domain.npc_magic_scenario_result_models import NpcMagicScenarioResult
from towr.domain.npc_magic_step_models import NpcMagicStep, NpcMagicUnsupportedReason
from towr.domain.npc_magic_journal_policy import validate_magic_step_policy
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_leg_spasm_models import NpcRosterLegSpasmStandResult
from towr.domain.npc_roster_repeated_leg_spasm_models import NpcRosterRepeatedLegSpasmStandRequest
from towr.domain.npc_roster_turn_models import NpcRosterTurnStartResult
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndResult
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.npc_roster_repeated_leg_spasm_resolution import (
    stand_npc_roster_repeated_leg_spasm, apply_npc_roster_repeated_leg_spasm_stand,
)


def rejected(operation, error_type):
    try:
        operation()
    except error_type:
        return
    raise AssertionError('expected existing public admission to reject')


def main():
    global_rng = getstate()
    hit = (1, 2, 3, 10, 10, 10)
    repeated = (*hit, 9, *((10,) * 9), *hit, 4, 5)
    results = {}
    total = 0
    for stationary in (False, True):
        for miscast in (False, True):
            source = authored_input(stationary=stationary, miscast=miscast)
            source_before = deepcopy(source)
            dice = ScriptedDice(repeated if stationary else (*hit, 9))
            result = run_npc_magic_scenario(source, dice)
            assert dice.calls == (24 if stationary else 7)
            total += dice.calls
            assert source == source_before and result.source is source
            assert result.unsupported.reason is NpcMagicUnsupportedReason.ACTOR_INJURY
            assert NpcMagicScenarioResult(source, result.steps, result.unsupported) == result
            wounds = result.current.roster.participant('wizard').state.injury.wounds
            assert tuple(w.table_total for w in wounds) == ((9, 9) if stationary else (9,))
            assert sum(isinstance(s.result, NpcRosterLegSpasmStandResult) for s in result.steps) == int(stationary)
            results[stationary, miscast] = result
            print(f'EXISTING stationary={"on" if stationary else "None"} miscast={"on" if miscast else "None"}: '
                  f'{dice.calls} d10; {"second9" if stationary else "first9"} actor-injury stop')
    for stationary in (False, True):
        assert results[stationary, False].steps == results[stationary, True].steps
        assert results[stationary, False].current == results[stationary, True].current
    assert total == 62

    stopped = results[True, False]
    snapshot = deepcopy(stopped)
    indexed_stands = tuple((index, step.result) for index, step in enumerate(stopped.steps)
                          if isinstance(step.result, NpcRosterLegSpasmStandResult))
    indexed_attacks = tuple((index, step.result) for index, step in enumerate(stopped.steps)
                           if isinstance(step.result, NpcRosterChampionAttackResult))
    assert len(indexed_stands) == 1 and len(indexed_attacks) == 2
    stand_index, previous = indexed_stands[0]
    attack_index, attack = indexed_attacks[-1]
    assert stand_index < attack_index == len(stopped.steps) - 3
    end_step, start_step = stopped.steps[attack_index + 1:]
    assert isinstance(end_step.result, NpcWoundTurnEndResult)
    assert isinstance(start_step.result, NpcRosterTurnStartResult)
    assert end_step.before == attack.state and start_step.before == end_step.after
    assert start_step.after == stopped.current
    assert end_step.result.source.actor_id == attack.attack.execution.actor_id
    assert start_step.result.source.actor_id == stopped.current.wizard.actor_id
    assert previous.source.state == stopped.steps[stand_index].before
    assert previous.state == stopped.steps[stand_index].after
    assert attack.source.state == stopped.steps[attack_index].before
    print('CLOSED JOURNAL: reconstructs exactly; stand48 and second Attack witnesses precede actual end/start scheduler tail')

    current = stopped.current
    actor = current.wizard.actor_id
    frame = stopped.source.initial_frame
    assert frame.key.placements == current.spatial_state.placements
    enemies = {p.state.actor_id for p in current.roster.participants
               if p.state.side is not current.roster.participant(actor).state.side}
    pairs = tuple(p for p in frame.pair_ranges if actor in (p.first_actor_id, p.second_actor_id))
    assert {next(a for a in (p.first_actor_id, p.second_actor_id) if a != actor) for p in pairs} == enemies
    assert all(p.target_range is not RangedWeaponRange.CLOSE for p in pairs)
    assert stopped.source.facts.no_external_condition_sources is True
    request = NpcRosterRepeatedLegSpasmStandRequest(stopped.source.id + ':manual-repeat',
        current, actor, False, True, previous, attack)
    bound = stand_npc_roster_repeated_leg_spasm(request)
    standing = apply_npc_roster_repeated_leg_spasm_stand(current, bound)
    injury = standing.roster.participant(actor).state.injury
    old_injury = current.roster.participant(actor).state.injury
    assert not injury.conditions.has(Condition.PRONE)
    assert injury.wounds == old_injury.wounds
    assert injury.active_wound_effects == tuple(e for e in old_injury.active_wound_effects if e not in bound.removed_effects)
    assert len(injury.active_wound_effects) == 2
    assert standing.champion_attack.daily_wounds == current.champion_attack.daily_wounds
    assert standing.champion_attack.consumed_wound_roll_ids == current.champion_attack.consumed_wound_roll_ids
    assert standing.consumed_execution_ids == current.consumed_execution_ids
    assert standing.wound_turn_end_receipts == current.wound_turn_end_receipts
    assert standing.round_state == current.round_state
    assert standing.roster == standing.champion_attack.roster == standing.minion_attack.roster
    assert standing.spatial_state == replace(current.spatial_state,
        free_move_used_entity_ids=(*current.spatial_state.free_move_used_entity_ids, actor))
    rejected(lambda: validate_magic_step_policy(stopped.source, NpcMagicStep(bound)), ValueError)
    assert stopped == snapshot
    print('MANUAL stand52: real journal witnesses; two terrains/history retained; no new receipts; old permission refuses journal step')

    # Equal effects cannot identify which actual attack trace belongs to a journal.
    alternate_values = (*repeated[:16], 3, 2, 1, *repeated[19:])
    alternate_dice = ScriptedDice(alternate_values)
    alternate = run_npc_magic_scenario(stopped.source, alternate_dice)
    total += alternate_dice.calls
    assert alternate_dice.calls == 24
    assert NpcMagicScenarioResult(alternate.source, alternate.steps, alternate.unsupported) == alternate
    foreign_step = alternate.steps[attack_index]
    assert foreign_step.id == stopped.steps[attack_index].id
    assert foreign_step.before == stopped.steps[attack_index].before
    assert foreign_step.after == stopped.steps[attack_index].after
    assert alternate.current == current
    assert foreign_step.result != attack
    assert foreign_step.result.attack.execution.resolution.attack.attacker_test.trace.initial_values == (3, 2, 1)
    assert attack.attack.execution.resolution.attack.attacker_test.trace.initial_values == (1, 2, 3)
    # This is allowed by low-level52's finite lineage contract. The future native
    # boundary must additionally require equality with the recorded journal member.
    foreign_request = replace(request, wound_attack=foreign_step.result)
    assert foreign_request.wound_attack != attack
    assert not any(step.result == foreign_request.wound_attack for step in stopped.steps)
    assert foreign_request.state == request.state
    print('MEMBERSHIP GAP: alternate actual Attack has same ID/source/current but different dice; low-level52 admits its finite lineage')
    print('REQUIRED NATIVE CONTRACT: bind both full witnesses to recorded prefix members; IDs/projected-state equality alone is insufficient')

    for kind in ('raw-policy', 'integer-fact'):
        bad = deepcopy(stopped.source)
        if kind == 'raw-policy':
            object.__setattr__(bad, 'stationary_wound_continuation', bad.stationary_wound_continuation.value)
        else:
            object.__setattr__(bad.facts, 'no_external_condition_sources', 1)
        assert bad == stopped.source
        unchanged = deepcopy(bad)
        no_dice = ScriptedDice(())
        rejected(lambda: run_npc_magic_scenario(bad, no_dice), TypeError)
        assert no_dice.calls == 0 and bad == unchanged
    assert stopped == snapshot and total == 86 and getstate() == global_rng
    print('NATIVE GUARDS: raw stationary enum and detached int-bool facts rejected by runner before RNG')
    print('NATIVE ADMISSION: original nested facts re-admitted; sources/global RNG unchanged')
    print('86 scripted d10; finite public boundary proof; no future permission types, new gameplay or automatic continuation')


if __name__ == '__main__':
    main()
