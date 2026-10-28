"""ADR-0044 finite journal/runner evidence using public production APIs.

PG1.4 Rules / Combat p112; Appendix / Wounds Table pp190-191;
GM1.1 Allies and Antagonists / Champions p92.
The runner publishes the bound death exclusion before attacker end-turn.
This finite scripted experiment makes no statistical or general-battle claim.
"""
from copy import deepcopy
from dataclasses import fields, replace
from random import getstate

from magic_scenario import ScriptedDice, authored_scenario
from towr.domain.npc_magic_scene_models import (
    NpcMagicAttackDeparture, NpcMagicGiveGroundPlan, NpcMagicPairRange,
    NpcMagicSceneFrame, NpcMagicSceneKey,
)
from towr.domain.npc_magic_step_models import NpcMagicUnsupportedReason as Reason, NpcMagicScenarioOutcome as Outcome
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_dead_champion_models import NpcRosterDeadChampionExclusionResult
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndResult
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
from towr.domain.turn_models import CombatRoundState, CombatSide
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario


def three_attackers(wizard_side):
    """Fresh admitted experiment: three numeric archers, two explicit frames."""
    scenario = authored_scenario(wizard_side=wizard_side)
    old = scenario.initial
    enemy = old.roster.participant('enemy')
    extra_ids = ('enemy2', 'enemy3')
    roster = NpcRoster((*old.roster.participants, *(replace(enemy,
        state=replace(enemy.state, actor_id=i)) for i in extra_ids)))
    combat = CombatRoundState(1, roster.turn_participants)
    placement = old.spatial_state.placement_for('enemy')
    spatial = replace(old.spatial_state, placements=(*old.spatial_state.placements,
        *(replace(placement, entity_id=i) for i in extra_ids)))
    initial = replace(old, roster=roster, round_state=combat, spatial_state=spatial,
        champion_attack=replace(old.champion_attack, roster=roster, round_state=combat))
    enemy_ids = ('enemy', *extra_ids)
    actors = tuple(replace(a, target_actor_ids=enemy_ids,
        defeat_decisions=tuple(replace(a.defeat_decisions[0], target_id=i) for i in enemy_ids))
        if a.actor_id == 'ally' else a for a in scenario.actors)
    actors = (*actors, *(replace(scenario.policy_for('enemy'), actor_id=i,
        defeat_decisions=tuple(replace(d, attacker_id=i)
            for d in scenario.policy_for('enemy').defeat_decisions)) for i in extra_ids))
    all_ids = tuple(p.state.actor_id for p in roster.participants)
    frames = []
    route = scenario.initial_frame.give_ground_plans[0].route
    for live in (all_ids, tuple(i for i in all_ids if i != 'wizard')):
        pairs = tuple(NpcMagicPairRange(a, b, Range.SHORT, False, False)
            for index, a in enumerate(live) for b in live[index + 1:]
            if roster.participant(a).state.side is not roster.participant(b).state.side)
        ground = (tuple(NpcMagicGiveGroundPlan(i, True, 'shelter', route, False)
            for i in enemy_ids) if 'wizard' in live else ())
        frames.append(NpcMagicSceneFrame(NpcMagicSceneKey(spatial.placements, live), pairs,
            scenario.initial_frame.zone_ranges, ground, (),
            tuple(NpcMagicAttackDeparture(i, True) for i in live)))
    return replace(scenario, initial=initial, actors=actors,
        activation_order=(*enemy_ids, 'wizard', 'ally'), scene_frames=tuple(frames),
        objective=NpcDefeatObjective(enemy_ids), max_rounds=1)


def verify_exclusion(step, attack):
    """Check the actual bound result and every unchanged owner field."""
    assert isinstance(step.result, NpcRosterDeadChampionExclusionResult)
    assert step.result.source.attack == attack
    source, final = attack.state, step.after
    assert step.before == source
    assert final.round_state == replace(source.round_state,
        excluded_turn_entity_ids=(*source.round_state.excluded_turn_entity_ids, source.wizard.actor_id))
    for field in fields(source):
        if field.name not in ('round_state', 'champion_attack'):
            assert getattr(final, field.name) == getattr(source, field.name)
    for field in fields(source.champion_attack):
        if field.name != 'round_state':
            assert getattr(final.champion_attack, field.name) == getattr(source.champion_attack, field.name)
    assert final.champion_attack.round_state == final.round_state


def main():
    global_rng = getstate()
    # Three successful shots, failed Protection, superficial Wounds 1/2 and
    # lethal Bisection 25. No Wound choice, Endurance or body-location RNG.
    hits = ((1, 2, 3, 10, 10, 10, 1)
        + (1, 2, 3, 10, 10, 10, 1, 1)
        + (1, 2, 3, 10, 10, 10, 10, 10, 5))
    for side in (CombatSide.OPPOSITION, CombatSide.PLAYERS_AND_ALLIES):
        source = three_attackers(side)
        before = deepcopy(source)
        # Allied archer misses. When Wizard acts first, its Curse also fails
        # without accumulating Miscast dice (all tens).
        values = hits + (10,) * 6 if side is CombatSide.OPPOSITION else (10,) * 9 + hits
        rng = ScriptedDice(values)
        result = run_npc_magic_scenario(source, rng)
        assert rng.calls == len(values) and source == before
        attacks = tuple(s.result for s in result.steps if isinstance(s.result, NpcRosterChampionAttackResult))
        assert len(attacks) == 3
        lethal = attacks[-1]
        snapshot = deepcopy(lethal.state)
        injury = lethal.state.roster.participant('wizard').state.injury
        assert injury.dead and tuple(w.table_total for w in injury.wounds) == (1, 2, 25)
        assert lethal.attack.pending_follow_ups == () and lethal.state.champion_attack.pending is None
        assert len(lethal.state.champion_attack.daily_wounds.receipts) == 3
        assert len(lethal.state.champion_attack.consumed_wound_roll_ids) == 3
        if side is CombatSide.OPPOSITION:
            assert result.unsupported is None and result.outcome is Outcome.ROUND_LIMIT_REACHED
            exclusions = tuple(s for s in result.steps if isinstance(s.result, NpcRosterDeadChampionExclusionResult))
            assert len(exclusions) == 1
            step = exclusions[0]
            verify_exclusion(step, lethal)
            index = result.steps.index(step)
            assert result.steps[index - 1].result == lethal
            assert isinstance(result.steps[index + 1].result, NpcWoundTurnEndResult)
            assert result.steps[index + 1].before == step.after
            assert result.current.round_state.excluded_turn_entity_ids == ('wizard',)
            assert 'wizard' not in result.current.round_state.completed_turn_entity_ids
            assert result.current.round_state.active_turn is None
            assert (result.executed_actions, result.started_rounds, result.completed_rounds) == (4, 1, 1)
            print(f'AWAITING: {rng.calls} d10; actual {result.outcome.value}; 3 resolved Wounds (1, 2, 25)')
            print('JOURNAL: matching Attack -> exclusion -> attacker end; archives/ledgers preserved')
            # Removing the supplied post-death frame must stop at the ally's
            # action before its six dice, after mandatory exclusion/end-turn.
            incomplete = replace(source, scene_frames=(source.initial_frame,))
            incomplete_before = deepcopy(incomplete)
            missing_rng = ScriptedDice(hits)
            missing = run_npc_magic_scenario(incomplete, missing_rng)
            assert missing_rng.calls == len(hits) and incomplete == incomplete_before
            assert missing.current.round_state.excluded_turn_entity_ids == ('wizard',)
            assert sum(isinstance(s.result, NpcRosterDeadChampionExclusionResult) for s in missing.steps) == 1
            assert missing.unsupported.reason is Reason.MISSING_SCENE
            assert missing.unsupported.actor_id == 'ally'
            assert missing.unsupported.required_scene_key == source.scene_frames[1].key
            assert missing.unsupported.required_scene_key.live_actor_ids == ('ally', 'enemy', 'enemy2', 'enemy3')
            assert missing.current.spatial_state.placements == source.initial.spatial_state.placements
            assert missing.current.roster.participant('wizard').state.injury.dead
            assert len(missing.current.roster.participants) == len(missing.current.spatial_state.placements) == 5
            assert missing.current.spatial_state.placement_for('wizard') == source.initial.spatial_state.placement_for('wizard')
            print(f'MISSING SCENE CONTROL: {missing_rng.calls} d10; exact post-death live key; all 5 archives retained')
        else:
            assert result.unsupported is None
            assert not any(isinstance(s.result, NpcRosterDeadChampionExclusionResult) for s in result.steps)
            assert 'wizard' in lethal.state.round_state.completed_turn_entity_ids
            assert 'wizard' not in result.current.round_state.excluded_turn_entity_ids
            # This source fails the proposed awaiting-target guard. No second
            # completed/excluded marker or no-op phase is proposed.
            print(f'COMPLETED: {rng.calls} d10; actual {result.outcome.value}; no exclusion phase')
        assert lethal.state == snapshot
    assert getstate() == global_rng
    print('Public production APIs; automatic journal/runner continuation; sources/global RNG unchanged')


if __name__ == '__main__':
    main()
