"""Finite ADR-0038 probe over the public single-run API.

Observation/seed/aggregation below are illustrative, not production simulation
models, admission guards or a batch service. No tests/private helpers are used.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, replace
from hashlib import sha256
from random import Random, getstate
from struct import pack

from magic_scenario import authored_scenario, ScriptedDice
from towr.domain.npc_magic_scenario_models import NpcMagicScenario
from towr.domain.npc_magic_scenario_result_models import NpcMagicScenarioResult
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.dice import RandomSource
from towr.simulation.npc_ranged_models import npc_ranged_trial_seed
from towr.simulation.npc_melee_models import npc_melee_trial_seed
from towr.simulation.npc_mixed_models import npc_mixed_trial_seed


SCHEME = 'towr:npc-magic-trial:v1'
MASTER_SEED = 42
VECTORS = (
    (0, 0, 'fd32be1af91a33565dc651e426c0293ce371728db87f9147b0ea927de35fa60e'),
    (42, 7, '0b95a33629128179ab8ff2862038f7c1331078d98dcb552fce2037bf90581dac'),
    ((1 << 64) - 1, (1 << 64) - 1, 'ce26ddf15185ed7cbff2fb2e86929fe80c7eb0f531eacc02a59430860ceebb34'),
)


def proposed_seed(master: int, index: int) -> int:
    # Only fixed valid inputs in this probe. Production guards are a later slice.
    return int.from_bytes(sha256(SCHEME.encode('ascii') + b'\0'
        + master.to_bytes(8, 'big') + index.to_bytes(8, 'big')).digest(), 'big')


@dataclass(frozen=True, slots=True)
class Observation:
    source: NpcMagicScenario  # shared immutable input, not the post-battle owner
    index: int
    seed: int
    outcome: Outcome
    actions: int
    started: int
    completed: int


def observe(source: NpcMagicScenario, index: int, rng: RandomSource) -> Observation:
    result = run_npc_magic_scenario(source, rng)
    assert isinstance(result, NpcMagicScenarioResult) and result.source == source
    assert 1 <= result.started_rounds <= source.max_rounds
    assert 0 <= result.started_rounds - result.completed_rounds <= 1
    assert result.completed_rounds <= result.executed_actions <= len(source.actors) * result.started_rounds
    if result.outcome is Outcome.ROUND_LIMIT_REACHED:
        assert result.started_rounds == result.completed_rounds == source.max_rounds
    if result.outcome is Outcome.UNSUPPORTED_PATH:
        assert result.unsupported is not None
    else:
        assert result.current.round_state.active_turn is None
    # Retain the input and scalars only; full journal/pending remain replayable
    # through the existing single-run API, not through this compact observation.
    return Observation(source, index, proposed_seed(MASTER_SEED, index), result.outcome,
        result.executed_actions, result.started_rounds, result.completed_rounds)


def same_input_fixture() -> NpcMagicScenario:
    source = authored_scenario()
    # Enemy first defeats the allied Minion, then may wound the Wizard on later
    # turns. A separate supplied key permits continuing with that archive.
    policy = replace(source.policy_for('enemy'), target_actor_ids=('ally', 'wizard'))
    first = source.initial_frame
    archive = replace(first, key=replace(first.key, live_actor_ids=('wizard', 'enemy')),
        pair_ranges=(first.pair_ranges[0],),
        attack_departures=tuple(d for d in first.attack_departures if d.actor_id != 'ally'))
    return replace(source, max_rounds=4,
        actors=tuple(policy if p.actor_id == 'enemy' else p for p in source.actors),
        scene_frames=(*source.scene_frames, archive))


def main() -> None:
    for master, index, expected in VECTORS:
        seed = proposed_seed(master, index)
        assert f'{seed:064x}' == expected
        assert sha256(SCHEME.encode('ascii') + b'\0' + pack('>QQ', master, index)).hexdigest() == expected
        assert seed not in (npc_ranged_trial_seed(master, index), npc_melee_trial_seed(master, index),
                            npc_mixed_trial_seed(master, index))
    print(f'seed scheme: {SCHEME}; three golden vectors/struct encoding/family separation OK')

    source = same_input_fixture()
    before, global_rng = deepcopy(source), getstate()
    wait, miss, hit = (10,) * 3, (10,) * 6, (1, 2, 3, 10, 10, 10)
    scripts = (
        wait + hit,
        wait + miss + hit + wait + hit + (1,) + wait + hit + (1, 1) + wait + hit + (10, 10, 5),
        (10,) * 60,
        (9, 9, 9),
    )
    expected = ((Outcome.OBJECTIVE_ACHIEVED, 2, 1, 1), (Outcome.PERSPECTIVE_DEFEATED, 9, 4, 4),
                (Outcome.ROUND_LIMIT_REACHED, 12, 4, 4), (Outcome.UNSUPPORTED_PATH, 1, 1, 0))
    streams = tuple(ScriptedDice(values) for values in scripts)
    records = tuple(observe(source, index, rng) for index, rng in enumerate(streams))
    assert len({id(rng) for rng in streams}) == 4
    for record, rng, values, observed in zip(records, streams, scripts, expected):
        assert (record.outcome, record.actions, record.started, record.completed) == observed
        assert rng.calls == len(values) and record.source is source
        print(f'scripted {record.index}: {record.outcome.value}; actions={record.actions}; '
              f'rounds={record.started}/{record.completed}; d10={rng.calls}')
    counts = Counter(record.outcome for record in records)
    assert tuple(counts[o] for o in Outcome) == (1, 1, 1, 1)
    actions, started, completed = (sum(getattr(r, name) for r in records) for name in ('actions', 'started', 'completed'))
    assert (actions, started, completed) == (24, 10, 9)
    assert tuple(sorted(reversed(records), key=lambda r: r.index)) == records
    print('illustrative aggregate: outcomes=1/1/1/1; actions=24; started=10; completed=9; 120 scripted d10')
    print('all four observations retained; unsupported is neither defeat nor discarded; no balance metric')

    # A fresh scenario can stop at a reserved slot before executing any action.
    zero_source = replace(source, activation_order=('ally', 'wizard', 'enemy'),
        scene_frames=(replace(source.initial_frame, attack_departures=()),))
    zero_rng = ScriptedDice(())
    zero = observe(zero_source, 0, zero_rng)
    assert (zero.actions, zero.started, zero.completed, zero_rng.calls) == (0, 1, 0, 0)
    assert zero.outcome is Outcome.UNSUPPORTED_PATH
    assert zero.source.id == source.id and zero.source != source and zero.seed == records[0].seed
    print('zero-action missing-departure stop: 0 d10; rounds=1/0; same ID/seed, different full source')

    def seeded(indices: range, *, shifted: bool = False, scenario: NpcMagicScenario = source) -> dict[int, Observation]:
        observed = {}
        for index in indices:
            rng = Random(proposed_seed(MASTER_SEED, index))
            if shifted and index == 0:
                for _ in range(17):
                    rng.randint(1, 10)
            observed[index] = observe(scenario, index, rng)
        return observed

    baseline = seeded(range(4))
    assert baseline == seeded(range(4)) == seeded(range(3, -1, -1))
    expanded = seeded(range(6))
    assert baseline == {i: expanded[i] for i in range(4)}
    shifted = seeded(range(4), shifted=True)
    assert tuple(baseline[i] for i in range(1, 4)) == tuple(shifted[i] for i in range(1, 4))
    renamed = seeded(range(4), scenario=replace(source, id='renamed:magic'))
    for index in range(4):
        first, other = baseline[index], renamed[index]
        assert (first.seed, first.outcome, first.actions, first.started, first.completed) == (
            other.seed, other.outcome, other.actions, other.started, other.completed)
    assert source == before and getstate() == global_rng
    print('26 seeded calls: repeat/reverse/prefix/extra-draw isolation/renamed-ID observations OK')
    print('31 total single-run calls; immutable sources/global RNG unchanged; no full journal in observations')
    print('Production magic simulation request/record/result/summary and validation are NOT implemented by this probe')


if __name__ == '__main__':
    main()
