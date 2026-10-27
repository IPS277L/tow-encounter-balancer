"""Finite manual projections for proposed ADR-0042; no production generator.

Keep magic_scenario.py beside this file. Bounds/C/family assertions below are
manual examples, not implementations of future group/request admission.
PG1.4 Rules pp112,114-115,119,122; Magic pp156-157,162; GM1.1 pp91-92.
"""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from random import getstate

from magic_scenario import authored_scenario
from towr.balance.magic_evaluation_models import MagicBalanceCandidate
from towr.balance.magic_staged_evaluation_models import MagicBalanceStage, MagicStagedEvaluationRequest
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.infection_models import DailyWoundState
from towr.domain.npc_champion_attack_models import NpcChampionAttackState
from towr.domain.npc_magic_scene_models import (
    NpcMagicAttackDeparture, NpcMagicBrokenPlan, NpcMagicBrokenPlanKind,
    NpcMagicGiveGroundPlan, NpcMagicPairRange, NpcMagicRouteFacts,
    NpcMagicSceneFrame, NpcMagicSceneKey,
)
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement
from towr.domain.turn_models import CombatRoundState, CombatSide
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest


ENEMIES = ('E1', 'E2', 'E3')


def authored_frame(base, positions, broken=()):
    """Explicit finite fixture facts; no discovery of geometry or routes."""
    distance = {'arena': Range.SHORT, 'shelter': Range.MEDIUM, 'boundary': Range.LONG}
    zones = {placement.entity_id: placement.zone_id for placement in positions}
    pairs = tuple(NpcMagicPairRange(friendly, enemy, distance[zones[enemy]], False, False)
                  for friendly in ('wizard', 'ally') for enemy in ENEMIES)
    plans = tuple(NpcMagicGiveGroundPlan(enemy, zones[enemy] != 'boundary',
        {'arena': 'shelter', 'shelter': 'boundary', 'boundary': None}[zones[enemy]],
        NpcMagicRouteFacts(('E1',) if enemy == 'E2' else (), False, False)
        if zones[enemy] != 'boundary' else None, zones[enemy] == 'boundary') for enemy in ENEMIES)
    return NpcMagicSceneFrame(NpcMagicSceneKey(positions, ('wizard', 'ally', *ENEMIES)),
        pairs, base.initial_frame.zone_ranges, plans, broken,
        tuple(NpcMagicAttackDeparture(actor, actor == 'E2') for actor in ('wizard', 'ally', *ENEMIES)))


def authored_reserve():
    base = authored_scenario()
    enemy = base.initial.roster.participant('enemy')
    roster = NpcRoster((*base.initial.roster.participants[:2], *(replace(enemy,
        state=replace(enemy.state, actor_id=actor)) for actor in ENEMIES)))
    combat = CombatRoundState(1, roster.turn_participants)
    positions = tuple(SpatialEntityPlacement(actor, roster.participant(actor).state.side.value, 'arena')
                      for actor in ('E3', 'wizard', 'E1', 'ally', 'E2'))
    spatial = SpatialBattleState(base.initial.spatial_state.graph, positions)
    state = NpcRosterCastingState(roster, base.initial.wizard, combat, spatial,
        champion_attack=NpcChampionAttackState(roster, combat, base.initial.champion_attack.daily_wounds))
    ally = replace(base.policy_for('ally'), target_actor_ids=('E3', 'E2', 'E1'),
        defeat_decisions=tuple(replace(base.policy_for('ally').defeat_decisions[0], target_id=actor)
                              for actor in ('E3', 'E2', 'E1')))
    enemies = tuple(replace(base.policy_for('enemy'), actor_id=actor,
        defeat_decisions=tuple(replace(decision, attacker_id=actor)
                               for decision in base.policy_for('enemy').defeat_decisions)) for actor in ENEMIES)
    moved = tuple(replace(p, zone_id='shelter') if p.entity_id == 'E1' else p for p in positions)
    recover = NpcMagicBrokenPlan('E1', NpcMagicBrokenPlanKind.SAFE_RECOVER, (), None, None, None, True)
    return replace(base, id='generation:reserve', initial=state,
        actors=(base.policy_for('wizard'), ally, *enemies), activation_order=('ally', 'E1', 'wizard', 'E3', 'E2'),
        objective=NpcDefeatObjective(('E3', 'E2', 'E1')),
        scene_frames=(authored_frame(base, positions), authored_frame(base, moved, (recover,))))


def project(template, retained, candidate_id, facts, scene_frames):
    """Manual finite projection; shared future construction/guards are not added."""
    assert tuple(scene_frames) == template.scene_frames, 'manual family source assertion'
    roster = NpcRoster(tuple(p for p in template.initial.roster.participants if p.state.actor_id in retained))
    combat = CombatRoundState(1, roster.turn_participants)
    spatial = SpatialBattleState(template.initial.spatial_state.graph,
        tuple(p for p in template.initial.spatial_state.placements if p.entity_id in retained))
    daily = template.initial.champion_attack.daily_wounds
    state = NpcRosterCastingState(roster, template.initial.wizard, combat, spatial,
        champion_attack=NpcChampionAttackState(roster, combat, DailyWoundState(daily.day_id, daily.target_id)))

    def route(value):
        return None if value is None else replace(value, path_entity_ids=tuple(
            actor for actor in value.path_entity_ids if actor in retained))

    frames = []
    for frame in scene_frames:
        value = replace(frame, key=replace(frame.key,
            placements=tuple(p for p in frame.key.placements if p.entity_id in retained),
            live_actor_ids=tuple(actor for actor in frame.key.live_actor_ids if actor in retained)),
            pair_ranges=tuple(p for p in frame.pair_ranges
                              if p.first_actor_id in retained and p.second_actor_id in retained),
            give_ground_plans=tuple(replace(p, route=route(p.route))
                                    for p in frame.give_ground_plans if p.actor_id in retained),
            broken_plans=tuple(replace(p, free_move_route=route(p.free_move_route), run_route=route(p.run_route))
                               for p in frame.broken_plans if p.actor_id in retained),
            attack_departures=tuple(p for p in frame.attack_departures if p.actor_id in retained))
        previous = next((other for other in frames if other.key == value.key), None)
        if previous is None:
            frames.append(value)
        elif previous != value:
            raise ValueError('conflicting projected scene frame key')
    policies = tuple(replace(p, target_actor_ids=tuple(actor for actor in p.target_actor_ids if actor in retained),
        defeat_decisions=tuple(d for d in p.defeat_decisions if d.target_id in retained))
        for p in template.actors if p.actor_id in retained)
    return replace(template, id=candidate_id, initial=state, facts=facts, actors=policies,
        activation_order=tuple(actor for actor in template.activation_order if actor in retained),
        objective=NpcDefeatObjective(tuple(actor for actor in template.objective.target_actor_ids if actor in retained)),
        scene_frames=tuple(frames))


def rejected(label, operation, error_type=ValueError):
    try:
        operation()
    except error_type:
        print(f'rejected: {label}')
    else:
        raise AssertionError(f'{label} must fail')


def main():
    source = authored_reserve()
    before, rng_before = deepcopy(source), getstate()
    facts, frames = replace(source.facts), tuple(source.scene_frames)
    vectors = ((1, 0), (1, 1), (2, 0), (2, 1))  # Explicit finite list, not a generator API.
    groups = (('E2', 'E1'), ('E3',))
    assert 2 * 2 == len(vectors) == 4 and 4 * 10 + 2 * 100 == 240
    candidates = []
    for counts in vectors:
        retained = {'wizard', 'ally', *(actor for group, count in zip(groups, counts) for actor in group[:count])}
        identifier = 'probe:counts:' + ','.join(map(str, counts))
        scenario = project(source, retained, identifier, facts, frames)
        expected = tuple(p for p in source.initial.roster.participants if p.state.actor_id in retained)
        assert scenario.initial.roster.participants == expected
        assert scenario.initial.wizard is source.initial.wizard and scenario.spell is source.spell
        assert scenario.initial.spatial_state.graph is source.initial.spatial_state.graph
        assert scenario.initial.champion_attack.daily_wounds == source.initial.champion_attack.daily_wounds
        assert scenario.actors[1].target_actor_ids == tuple(i for i in ('E3', 'E2', 'E1') if i in retained)
        for policy in scenario.actors:
            original = source.policy_for(policy.actor_id)
            assert policy.willpower_profile == original.willpower_profile and policy.speed is original.speed
            assert policy.zone_priorities == original.zone_priorities
            assert policy.defeat_decisions == tuple(d for d in original.defeat_decisions if d.target_id in retained)
        assert tuple((p.actor_id, p.can_leave_zone) for p in scenario.initial_frame.attack_departures) == tuple(
            (p.actor_id, p.can_leave_zone) for p in source.initial_frame.attack_departures if p.actor_id in retained)
        assert scenario.activation_order == tuple(i for i in source.activation_order if i in retained)
        assert tuple(p.entity_id for p in scenario.initial.spatial_state.placements) == tuple(
            p.entity_id for p in source.initial.spatial_state.placements if p.entity_id in retained)
        assert tuple(len(frame.pair_ranges) for frame in scenario.scene_frames) == (2 * sum(counts),) * len(scenario.scene_frames)
        assert len(scenario.scene_frames) == (1 if counts[0] == 1 else 2)
        path = next(plan for plan in scenario.initial_frame.give_ground_plans if plan.actor_id == 'E2').route.path_entity_ids
        assert path == (() if counts[0] == 1 else ('E1',))
        candidates.append(MagicBalanceCandidate(identifier, scenario))
        print(f'{counts}: roster={tuple(p.state.actor_id for p in expected)}; '
              f'pairs={len(scenario.initial_frame.pair_ranges)}; frames={len(scenario.scene_frames)}; E2 path={path}')
    request = MagicStagedEvaluationRequest(tuple(candidates), 42,
        (MagicBalanceStage(10, 2), MagicBalanceStage(100, 1)), 240,
        ObjectiveRateWindow(Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)))
    assert request.planned_trials == 240
    for candidate in candidates:
        small = NpcMagicSimulationRequest(candidate.scenario, 42, 10)
        large = replace(small, trials=100)
        renamed = replace(small, scenario=replace(candidate.scenario, id='different-local-id'))
        assert tuple(small.seed_for(i) for i in range(10)) == tuple(large.seed_for(i) for i in range(10))
        assert tuple(small.seed_for(i) for i in range(10)) == tuple(renamed.seed_for(i) for i in range(10))
    print('manual C=4; public staged planned=240; 10->100 full rerun; indexed seed prefix/renamed IDs equal')
    opposite = replace(source, perspective_side=CombatSide.OPPOSITION,
        objective=NpcDefeatObjective(('wizard', 'ally')))
    mirrored = project(opposite, {'wizard', 'ally', *ENEMIES}, 'probe:opposite:counts:1', facts, frames)
    assert mirrored.initial.wizard is source.initial.wizard and mirrored.objective.target_actor_ids == ('wizard', 'ally')
    print('opposite perspective: all E fixed; Wizard retained outside groups; variable ally prefix=1')
    assert (2 * 2 - 1, 1 * 1 - 1) == (3, 0)  # all-zero is omitted in both perspectives.
    print('manual all-zero exclusion: Wizard always requires an allied and an opposing Minion')
    rejected('public staged budget239', lambda: replace(request, max_total_trials=239))
    rejected('missing live hostile pair', lambda: replace(source,
        scene_frames=(replace(source.initial_frame, pair_ranges=source.initial_frame.pair_ranges[:-1]),)))
    rejected('manual family frame source mismatch', lambda: project(source, {'wizard', 'ally', 'E2'},
        'bad:source', facts, frames[:1]), AssertionError)
    conflict = replace(frames[1], attack_departures=tuple(
        replace(p, can_leave_zone=not p.can_leave_zone) if p.actor_id == 'E2' else p for p in frames[1].attack_departures))
    conflict_source = replace(source, scene_frames=(frames[0], conflict))
    rejected('same projected key with unequal facts', lambda: project(conflict_source, {'wizard', 'ally', 'E2'},
        'bad:collision', facts, conflict_source.scene_frames))
    unsafe_positions = tuple(replace(p, zone_id='boundary') if p.entity_id in ('E2', 'E3') else p
                             for p in source.initial.spatial_state.placements)
    moving = NpcMagicBrokenPlan('ally', NpcMagicBrokenPlanKind.FREE_MOVE_RECOVER, ('shelter',),
        NpcMagicRouteFacts((), False, False), None, None, True)
    unsafe = replace(source, scene_frames=(*frames, authored_frame(source, unsafe_positions, (moving,))))
    rejected('removing enemy invalidates supplied moving Broken plan', lambda: project(unsafe,
        {'wizard', 'ally', 'E2'}, 'bad:broken', facts, unsafe.scene_frames))
    rejected('removing sole Wizard ally', lambda: project(opposite, {'wizard', *ENEMIES},
        'bad:zero-allies', facts, frames))
    print('bounds/group/type/cap/source/result/error guards remain future production work')
    assert source == before and getstate() == rng_before
    print('public constructors only; input/global RNG unchanged; no runner/RNG/evaluation/pool execution')


if __name__ == '__main__':
    main()
