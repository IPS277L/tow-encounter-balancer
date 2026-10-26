"""Public ADR-0038 simulation example; keep magic_scenario.py beside this file.

Authored numeric combatants and facts retain the audited single-run scope.
Scripted observations are finite evidence, not Monte Carlo difficulty estimates.
"""
from copy import deepcopy
from dataclasses import fields, replace
from random import Random, getstate

from magic_scenario import authored_scenario, ScriptedDice
from towr.domain.npc_magic_scenario_models import NpcMagicScenario
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.simulation.npc_magic_models import (
    SEED_SCHEME, NpcMagicOutcomeCounts, NpcMagicSimulationRequest, NpcMagicSimulationResult,
)
from towr.simulation.npc_magic_simulation import run_npc_magic_trial, run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation


def authored_simulation_scenario() -> NpcMagicScenario:
    """Supply the archived-ally scene for a four-round experiment."""
    source = authored_scenario()
    enemy = replace(source.policy_for('enemy'), target_actor_ids=('ally', 'wizard'))
    initial = source.initial_frame
    archive = replace(initial, key=replace(initial.key, live_actor_ids=('wizard', 'enemy')),
        pair_ranges=(initial.pair_ranges[0],),
        attack_departures=tuple(fact for fact in initial.attack_departures if fact.actor_id != 'ally'))
    return replace(source, max_rounds=4,
        actors=tuple(enemy if actor.actor_id == 'enemy' else actor for actor in source.actors),
        scene_frames=(*source.scene_frames, archive))


def observation(record):
    return (record.seed, record.outcome, record.executed_action_count,
            record.started_round_count, record.completed_round_count)


def main() -> None:
    source = authored_simulation_scenario()
    before, global_rng = deepcopy(source), getstate()
    request = NpcMagicSimulationRequest(source, 42, 4)
    wait, miss, hit = (10,) * 3, (10,) * 6, (1, 2, 3, 10, 10, 10)
    scripts = (
        wait + hit,
        wait + miss + hit + wait + hit + (1,) + wait + hit + (1, 1) + wait + hit + (10, 10, 5),
        (10,) * 60,
        (9, 9, 9),
    )
    seeds = tuple(request.seed_for(index) for index in range(request.trials))
    factory_calls, streams = [], []

    def scripted_factory(seed):
        factory_calls.append(seed)
        stream = ScriptedDice(scripts[seeds.index(seed)])
        streams.append(stream)
        return stream

    result = run_npc_magic_simulation(request, rng_factory=scripted_factory)
    assert tuple(factory_calls) == seeds and len({id(stream) for stream in streams}) == 4
    expected = ((Outcome.OBJECTIVE_ACHIEVED, 2, 1, 1), (Outcome.PERSPECTIVE_DEFEATED, 9, 4, 4),
                (Outcome.ROUND_LIMIT_REACHED, 12, 4, 4), (Outcome.UNSUPPORTED_PATH, 1, 1, 0))
    print(f'seed scheme: {SEED_SCHEME}; fresh RNG per indexed trial')
    for record, stream, script, values in zip(result.trials, streams, scripts, expected):
        assert observation(record)[1:] == values
        assert stream.calls == len(script) and record.source_scenario is source
        print(f'scripted {record.trial_index}: {record.outcome.value}; actions={record.executed_action_count}; '
              f'rounds={record.started_round_count}/{record.completed_round_count}; d10={stream.calls}')
    assert NpcMagicSimulationResult(request, list(reversed(result.trials))) == result
    summary = summarize_npc_magic_simulation(result)
    assert summary.source_request is request and summary.trials == 4
    assert summary.outcome_counts == NpcMagicOutcomeCounts(1, 1, 1, 1)
    assert (summary.total_action_count, summary.total_started_round_count,
            summary.total_completed_round_count) == (24, 10, 9)
    assert {field.name for field in fields(summary)} == {'source_request', 'outcome_counts',
        'total_action_count', 'total_started_round_count', 'total_completed_round_count'}
    print('production summary: outcomes=1/1/1/1; actions=24; started=10; completed=9; 120 scripted d10')
    print('summary retains input and aggregates; unsupported is counted separately; no battle journals or balance metric')

    # With a custom factory, replay needs the same stream semantics as the trial.
    # A seed alone cannot reproduce arbitrary different factory implementations.
    replay_rng = ScriptedDice(scripts[1])
    replay = run_npc_magic_scenario(source, replay_rng)
    assert replay_rng.calls == 48 and replay.outcome is result.trials[1].outcome
    assert (replay.executed_actions, replay.started_rounds, replay.completed_rounds) == observation(result.trials[1])[2:]
    wizard = replay.current.roster.participant('wizard').state.injury
    assert wizard.dead and len(wizard.wounds) == 3
    assert len(replay.current.champion_attack.daily_wounds.receipts) == 3
    assert len(replay.current.champion_attack.consumed_wound_roll_ids) == 3
    assert replay.current.round_state.excluded_turn_entity_ids == ('ally',)
    assert len(replay.current.roster.participants) == len(replay.current.spatial_state.placements) == 3
    assert replay.current.pending_minion_attack is None and replay.current.champion_attack.pending is None
    assert replay.current.round_state.active_turn is None
    assert len(replay.steps) > result.trials[1].executed_action_count
    print('replay: three Champion Wounds/daily receipts/rolls; dead Wizard; defeated ally retained in archive; 48 d10')

    zero_source = replace(source, activation_order=('ally', 'wizard', 'enemy'),
        scene_frames=(replace(source.initial_frame, attack_departures=()),))
    zero_request = NpcMagicSimulationRequest(zero_source, 42, 1)
    zero_rng = ScriptedDice(())
    zero = run_npc_magic_simulation(zero_request, rng_factory=lambda seed: zero_rng)
    record = zero.trials[0]
    assert record.outcome is Outcome.UNSUPPORTED_PATH
    assert observation(record)[2:] == (0, 1, 0) and zero_rng.calls == 0
    assert record.seed == result.trials[0].seed and record.source_scenario.id == source.id
    try:
        NpcMagicSimulationResult(replace(request, trials=1), zero.trials)
    except ValueError:
        pass
    else:
        raise AssertionError('same ID/seed must not admit a different full source')
    print('zero-action missing-departure stop: 0 d10; rounds=1/0; foreign full source rejected despite same ID/seed')

    baseline = run_npc_magic_simulation(request)
    assert baseline == run_npc_magic_simulation(request)
    reversed_trials = tuple(run_npc_magic_trial(request, index) for index in reversed(range(4)))
    assert NpcMagicSimulationResult(request, reversed_trials) == baseline
    expanded = run_npc_magic_simulation(replace(request, trials=6))
    assert expanded.trials[:4] == baseline.trials

    def shifted_factory(seed):
        rng = Random(seed)
        if seed == request.seed_for(0):
            for _ in range(17):
                rng.randint(1, 10)
        return rng

    shifted = run_npc_magic_simulation(request, rng_factory=shifted_factory)
    assert shifted.trials[1:] == baseline.trials[1:]
    renamed = run_npc_magic_simulation(replace(request, scenario=replace(source, id='renamed:magic')))
    assert tuple(map(observation, renamed.trials)) == tuple(map(observation, baseline.trials))
    assert source == before and getstate() == global_rng
    print('26 seeded calls: repeat/reverse/prefix/extra-draw isolation/renamed-ID observations OK')
    print('32 total single-run calls; immutable sources/global RNG preserved; public production simulation APIs only')


if __name__ == '__main__':
    main()
