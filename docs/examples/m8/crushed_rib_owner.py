"""ADR-0056 actual full-owner consumer; copy with three public fixture modules.

PG1.4 Rules pp108,118,123, Casting pp156-157, Wounds p190; GM1.1 p92.
All numeric profiles/scene facts are authored; automatic runner stays stopped.
"""
from copy import deepcopy
from dataclasses import fields, replace
from random import getstate

from generation_contract_probe import authored_reserve
from magic_scenario import ScriptedDice
from stationary_wound_runner import authored_input
from towr.domain import NpcCrushedRibContext as Context, NpcCrushedRibConsumptionWitness as Witness
from towr.domain.cowardly_flight_casting_models import CowardlyFlightCastingFacts, CowardlyFlightCastingPolicy
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult, NpcRosterCastingTargetContext
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_roster_turn_models import NpcRosterTurnStartRequest
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.turn_models import CombatSide, CombatRoundState, CombatActionDeclaration, CombatActionKind
from towr.domain.test_models import Skill, TestQuality
from towr.domain.injury_models import WoundRestriction, WoundRestrictionEffect
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting
from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting, apply_npc_roster_casting_result
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_champion_attack_resolution import apply_npc_roster_champion_attack_result
from towr.rules.npc_roster_shooting_preparation import prepare_npc_roster_shooting
from towr.rules.npc_roster_turn_resolution import start_npc_roster_turn
from towr.rules.npc_wound_turn_end import end_npc_wound_turn


def enemy_first():
    """Author all sides/placements before execution, using an existing fixture."""
    source = authored_reserve()
    roster = NpcRoster(tuple(replace(p, state=replace(p.state, side=(
        CombatSide.OPPOSITION if p.state.actor_id in ('wizard', 'ally') else CombatSide.PLAYERS_AND_ALLIES)))
        for p in source.initial.roster.participants))
    combat = CombatRoundState(1, roster.turn_participants)
    def positions(values):
        return tuple(replace(p, side_id=roster.participant(p.entity_id).state.side.value) for p in values)
    initial = replace(source.initial, roster=roster, round_state=combat,
        spatial_state=replace(source.initial.spatial_state, placements=positions(source.initial.spatial_state.placements)),
        champion_attack=replace(source.initial.champion_attack, roster=roster, round_state=combat))
    return replace(source, initial=initial, activation_order=('E1', 'E2', 'E3', 'wizard', 'ally'),
        perspective_side=CombatSide.OPPOSITION, scene_frames=tuple(replace(f,
            key=replace(f.key, placements=positions(f.key.placements))) for f in source.scene_frames))


def first_ten(source):
    before = deepcopy(source)
    dice = ScriptedDice((1, 2, 3, 10, 10, 10, 10))
    result = run_npc_magic_scenario(source, dice)
    assert dice.calls == 7 and source == before
    assert result.unsupported is not None
    assert result.current.roster.participant('wizard').state.injury.wounds[-1].table_total == 10
    return result.current


def shooting(source, state, identifier, context):
    actor = state.round_state.active_turn.actor_id
    pair = next(p for p in source.initial_frame.pair_ranges
                if {p.first_actor_id, p.second_actor_id} == {actor, 'wizard'})
    departure = next(d for d in source.initial_frame.attack_departures if d.actor_id == 'wizard')
    return prepare_npc_roster_shooting(request_id=identifier, state=state, actor_id=actor,
        target_id='wizard', selected_attack_id=source.policy_for(actor).attack_id, target_range=pair.target_range,
        has_enemy_in_close_range=False, range_approved_by_gm=False, defender_is_aware=True,
        selected_protection_skill=Skill.ATHLETICS, can_target_leave_zone=departure.can_leave_zone,
        crushed_rib_context=context)


def attack(request, values):
    dice = ScriptedDice(values)
    result = NpcRosterChampionAttackResult(request, execute_npc_champion_attack(request.attack, dice))
    assert dice.calls == len(values)
    state = apply_npc_roster_champion_attack_result(request.state, result)
    assert state.roster == state.champion_attack.roster == state.minion_attack.roster
    return result, state


def main():
    global_rng = getstate()
    source = authored_input()
    owner = first_ten(source)
    before = deepcopy(owner)
    context = Context(owner, 'wizard', True)
    facts = CowardlyFlightCastingFacts(**{f.name: True for f in fields(CowardlyFlightCastingFacts)})
    request = prepare_npc_roster_casting(request_id='owner56:cast', state=owner, selected_zone_id='arena',
        targets=(NpcRosterCastingTargetContext('enemy', source.policy_for('enemy').willpower_profile, True),),
        facts=facts, policy=CowardlyFlightCastingPolicy.CAST_WHEN_READY, crushed_rib_context=context)
    dice = ScriptedDice((1, 9, 10, 9))
    result = NpcRosterCastingResult(request, execute_cowardly_flight_casting(request.casting, dice))
    cast_owner = apply_npc_roster_casting_result(owner, result)
    receipt = result.casting.crushed_rib
    assert dice.calls == 4 and receipt.casting.test.trace.quality is TestQuality.GRIM
    assert receipt.casting.test.successes == 0 and cast_owner.wizard.magic_state.miscast_dice == 2
    assert cast_owner.roster.participant('wizard').state.injury == receipt.state
    assert cast_owner.roster == cast_owner.champion_attack.roster == cast_owner.minion_attack.roster
    consumed = Context(cast_owner, 'wizard', True, Witness(result, receipt))
    ended = end_npc_wound_turn(NpcWoundTurnEndRequest('owner56:cast:end', cast_owner, 'wizard',
        crushed_rib_context=consumed)).state
    assert ended.roster.participant('wizard').state.injury == receipt.state
    assert owner == before
    print('CASTING: actual10/7d10 -> slot-bound failed Grim/4d10 -> consumed full owner BEFORE pool0->2/WAIT; end-turn keeps Drained and all Wound histories')

    source = enemy_first()
    owner = first_ten(source)
    before = deepcopy(owner)
    first, current = attack(shooting(source, owner, 'owner56:protection', Context(owner, 'wizard', True)),
        (10, 10, 10, 1, 6, 10, 9))
    receipt = first.attack.crushed_rib
    assert receipt.test.successes == 0 and receipt.test.trace.quality is TestQuality.GRIM
    assert current.roster.participant('wizard').state.injury == receipt.state
    witness = Witness(first, receipt)
    consumed = Context(current, 'wizard', True, witness)
    ended = end_npc_wound_turn(NpcWoundTurnEndRequest('owner56:E2:end', current, 'E2')).state
    next_owner = start_npc_roster_turn(NpcRosterTurnStartRequest('owner56:E3:start', ended, 'E3',
        CombatActionDeclaration(CombatActionKind.ATTACK))).state
    later, final = attack(shooting(source, next_owner, 'owner56:normal-protection',
        Context(next_owner, 'wizard', True, witness)), (10,) * 6)
    assert later.attack.crushed_rib is None
    assert later.attack.execution.resolution.attack.defender_test.trace.quality is TestQuality.NORMAL
    assert final.roster.participant('wizard').state.injury == receipt.state
    Context(final, 'wizard', True, witness)
    assert owner == before
    print('PROTECTION: actual10/7d10 -> current E2 Attack7d10 -> one consumed full-owner receipt; later E3 normal Protection6d10 keeps first witness, Drained and daily/roll histories')

    for values, label in (((5, 5), 'new10'), ((1, 1), 'superficial2')):
        owner = first_ten(source)
        request = shooting(source, owner, 'owner56:' + label, Context(owner, 'wizard', True))
        actual, updated = attack(request, (1, 2, 3, 1, 6, 10, 9, *values))
        injury = updated.roster.participant('wizard').state.injury
        old = actual.attack.crushed_rib
        assert len(injury.wounds) == len(updated.champion_attack.daily_wounds.receipts) == 2
        assert len(updated.champion_attack.consumed_wound_roll_ids) == 2
        assert injury.wounds[-1].table_total == sum(values)
        assert old.consumed_effect not in injury.active_wound_effects
        if label == 'new10':
            assert any(isinstance(e, WoundRestrictionEffect) and e.wound_sequence == 2
                       and e.restriction is WoundRestriction.NEXT_TEST_IS_GRIM for e in injury.active_wound_effects)
        try:
            Context(updated, 'wizard', True, Witness(actual, old))
        except ValueError:
            pass
        else:
            raise AssertionError('new post-Test injury must stop the narrow consumed context')
        print(f'POST-TEST {label}: actual10/7d10 + Attack/Wound9d10; old effect consumed BEFORE new Wound; all consequences/receipts retained, further context refused')
    assert getstate() == global_rng
    print('63 scripted d10; actual public full-owner consumers; immutable sources/global RNG; automatic runner remains unsupported on Wound10')


if __name__ == '__main__':
    main()
