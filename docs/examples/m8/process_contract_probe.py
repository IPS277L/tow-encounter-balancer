"""Finite ADR-0039 spawn/transport probe, not a production process backend.

Keep magic_simulation.py and magic_scenario.py beside this importable script.
Only explicit tiny partitions are exercised; no lazy scheduler/refill API,
performance claim, gameplay consumer or backend selection is implemented here.
"""
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from dataclasses import dataclass, replace
from multiprocessing import active_children, get_context
import os
from pathlib import Path
import pickle
from queue import Empty
from random import Random, getstate
from tempfile import TemporaryDirectory

from magic_simulation import authored_simulation_scenario
from magic_scenario import ScriptedDice
from towr.domain.npc_magic_scenario_models import NpcMagicScenario
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome
from towr.domain.npc_mixed_scenario_result_models import NpcMixedScenarioOutcome
from towr.simulation.npc_magic_models import (
    SEED_SCHEME, NpcMagicOutcomeCounts, NpcMagicSimulationRequest,
    NpcMagicSimulationResult, NpcMagicTrialRecord,
)
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation, run_npc_magic_trial
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation as summarize


WAIT, MISS, HIT = (10,) * 3, (10,) * 6, (1, 2, 3, 10, 10, 10)
SCRIPTS = (
    WAIT + HIT,
    WAIT + MISS + HIT + WAIT + HIT + (1,) + WAIT + HIT + (1, 1) + WAIT + HIT + (10, 10, 5),
    (10,) * 60,
    (9, 9, 9),
)


@dataclass(frozen=True, slots=True)
class ScriptFactory:
    seeds: tuple[int, ...]
    scripts: tuple[tuple[int, ...], ...]

    def __call__(self, seed):
        return ScriptedDice(self.scripts[self.seeds.index(seed)])


@dataclass(frozen=True, slots=True)
class FailureFactory:
    seeds: tuple[int, ...]
    marker: str

    def __call__(self, seed):
        index = self.seeds.index(seed)
        with Path(self.marker).open('a', encoding='utf-8') as stream:
            stream.write(f'{index}\n')
        if index == 1:
            error = ValueError('probe factory failure at index 1')
            error.add_note('factory sentinel note')
            raise error
        return Random(seed)


def worker_started(diagnostics, parent_pid):
    """Separate PID diagnostic channel; trial payloads contain records only."""
    assert os.getpid() != parent_pid
    diagnostics.put(os.getpid())


def probe_batch(request, indices, factory):
    before, global_rng = deepcopy(request), getstate()
    records, streams = [], []

    def fresh_factory(seed):
        stream = factory(seed)
        assert all(stream is not previous for previous in streams), 'probe factory must create fresh RNGs'
        streams.append(stream)
        return stream

    for index in indices:
        try:
            record = run_npc_magic_trial(request, index, rng_factory=fresh_factory)
            records.append(record)
            if isinstance(streams[-1], ScriptedDice):
                assert streams[-1].calls == len(streams[-1].values)
        except Exception as error:
            error.add_note(f'M8 trial index={index}, seed={request.seed_for(index)}')
            raise
    assert request == before and getstate() == global_rng
    assert all(record.source_scenario is request.scenario for record in records)
    # Pickle memoization shares this scenario within one batch. Another submitted
    # task and another returned payload reconstruct their own equal input copy.
    return tuple(records)


def normalize_batch(request, indices, payload):
    """Probe-local trusted-child validation before canonicalizing source identity."""
    if type(payload) is not tuple:
        raise TypeError('worker payload must be a tuple of magic records')
    if len(payload) != len(indices):
        raise ValueError('worker payload must contain its whole assigned batch')
    normalized = []
    for index, record in zip(indices, payload):
        if not isinstance(record, NpcMagicTrialRecord):
            raise TypeError('worker payload contains a foreign record type')
        if not isinstance(record.source_scenario, NpcMagicScenario):
            raise TypeError('worker record requires its full typed scenario')
        if record.source_scenario != request.scenario:
            raise ValueError('worker record differs from the full parent scenario')
        # Pickle does not run __post_init__. Revalidate outcome/counter/type/bounds
        # while rebinding the already checked equal source to the parent's object.
        # Do this before index/seed equality: False == 0 and True == 1 otherwise.
        canonical = replace(record, source_scenario=request.scenario)
        if canonical.trial_index != index:
            raise ValueError('worker record order/index differs from the assigned batch')
        if canonical.seed != request.seed_for(index):
            raise ValueError('worker record seed differs from the parent request')
        normalized.append(canonical)
    return tuple(normalized)


def collect_fixed_batches(request, partitions, workers, factory):
    """Fixed finite demonstration, not public admission or a refill scheduler."""
    assert workers in (1, 2) and len(partitions) <= 2 * workers
    assert tuple(index for indices in partitions for index in indices) == tuple(range(request.trials))
    # Nothing process-related is constructed before this local serialization gate.
    pickle.dumps((request, factory))
    before_children = {child.pid for child in active_children()}
    context = get_context('spawn')
    diagnostics = context.Queue()
    records, transported_sources = [], []
    # Keep these tiny raw graphs only for the finite cross-batch aliasing proof.
    # The future production collector must release each raw batch after rebinding.
    try:
        with ProcessPoolExecutor(max_workers=workers, mp_context=context,
                initializer=worker_started, initargs=(diagnostics, os.getpid())) as pool:
            futures = tuple(pool.submit(probe_batch, request, indices, factory) for indices in partitions)
            # Deliberately reverse collection; no completion-order seed dependence.
            for indices, future in reversed(tuple(zip(partitions, futures))):
                payload = future.result()
                normalized = normalize_batch(request, indices, payload)
                first_source = payload[0].source_scenario
                assert first_source == request.scenario and first_source is not request.scenario
                assert all(record.source_scenario is first_source for record in payload)
                assert all(first_source is not previous for previous in transported_sources)
                transported_sources.append(first_source)
                records.extend(normalized)
    finally:
        # max_workers is a limit: fast tasks need not start every allowed worker.
        # Shutdown has completed and child Queue feeders have flushed; do not wait
        # for diagnostics from workers that the executor never needed to start.
        worker_pids = set()
        while True:
            try:
                worker_pids.add(diagnostics.get_nowait())
            except Empty:
                break
        diagnostics.close()
        diagnostics.join_thread()
        assert 1 <= len(worker_pids) <= workers and os.getpid() not in worker_pids
        assert {child.pid for child in active_children()} == before_children
    result = NpcMagicSimulationResult(request, tuple(records))
    assert result.source_request is request
    assert all(record.source_scenario is request.scenario for record in result.trials)
    return result


def round_trip(value):
    return pickle.loads(pickle.dumps(value))


def counterfeit(record, **changes):
    """Deliberately bypass frozen construction, then test after a pickle trip."""
    altered = round_trip(record)
    for name, value in changes.items():
        object.__setattr__(altered, name, value)
    return round_trip(altered)


def negative_transport_probes(request, records):
    payload = round_trip(records[:2])
    assert payload[0].source_scenario == request.scenario
    assert payload[0].source_scenario is payload[1].source_scenario
    assert payload[0].source_scenario is not request.scenario
    normalized = normalize_batch(request, (0, 1), payload)
    assert all(record.source_scenario is request.scenario for record in normalized)
    foreign = replace(request.scenario, max_rounds=request.scenario.max_rounds + 1)
    assert foreign.id == request.scenario.id and foreign != request.scenario
    tests = (
        ('foreign full source', ValueError, (counterfeit(payload[0], source_scenario=foreign), payload[1])),
        ('payload type', TypeError, round_trip(list(payload))),
        ('missing record', ValueError, round_trip(payload[:1])),
        ('record type', TypeError, round_trip(('foreign record', payload[1]))),
        ('reversed indices', ValueError, round_trip(tuple(reversed(payload)))),
        ('foreign index', ValueError, (counterfeit(payload[0], trial_index=4), payload[1])),
        ('foreign seed', ValueError, (counterfeit(payload[0], seed=payload[0].seed ^ 1), payload[1])),
        ('string outcome', TypeError, (counterfeit(payload[0], outcome=payload[0].outcome.value), payload[1])),
        ('foreign Enum', TypeError, (counterfeit(payload[0], outcome=NpcMixedScenarioOutcome.UNSUPPORTED_PATH), payload[1])),
        ('bool index', TypeError, (counterfeit(payload[0], trial_index=False), payload[1])),
        ('bool seed', TypeError, (counterfeit(payload[0], seed=True), payload[1])),
        ('bool actions', TypeError, (counterfeit(payload[0], executed_action_count=True), payload[1])),
        ('zero started rounds', ValueError, (counterfeit(payload[0], started_round_count=0), payload[1])),
        ('actions exceed budget', ValueError, (counterfeit(payload[0], executed_action_count=99), payload[1])),
        ('source type', TypeError, (counterfeit(payload[0], source_scenario=request.scenario.id), payload[1])),
    )
    for label, expected, candidate in tests:
        try:
            normalize_batch(request, (0, 1), candidate)
        except expected:
            pass
        else:
            raise AssertionError(f'{label} was accepted after pickle')
    return len(tests)


def main():
    original_rng = getstate()
    original_children = {child.pid for child in active_children()}
    source = authored_simulation_scenario()
    before = deepcopy(source)
    print(f'ADR-0039 finite magic process contract probe; seed_scheme={SEED_SCHEME}')
    print('Existing public trial/result/summary; explicit spawn; tuple-only records and separate child PID diagnostics')
    seeded = NpcMagicSimulationRequest(source, 42, 5)
    assert round_trip(seeded) == seeded
    expected = run_npc_magic_simulation(seeded)
    plans = ((1, ((0, 1, 2), (3, 4))), (2, ((0, 1), (2, 3), (4,))))
    for workers, partitions in plans:
        actual = collect_fixed_batches(seeded, partitions, workers, Random)
        assert actual == expected and summarize(actual) == summarize(expected)
        assert summarize(actual).source_request is seeded
        print(f'seeded N=5: workers={workers}; batch_lengths={tuple(map(len, partitions))}; '
              'reverse collection/full result/summary equal')
    print('Pickle sources: equal but separate across batches; shared within each batch; final records share original parent input')

    scripted = replace(seeded, trials=4)
    factory = ScriptFactory(tuple(scripted.seed_for(index) for index in range(4)), SCRIPTS)
    first_rng, second_rng = factory(scripted.seed_for(0)), factory(scripted.seed_for(0))
    assert first_rng is not second_rng
    expected = run_npc_magic_simulation(scripted, rng_factory=factory)
    assert expected.outcome_counts == NpcMagicOutcomeCounts(1, 1, 1, 1)
    assert (expected.total_action_count, expected.total_started_round_count,
            expected.total_completed_round_count) == (24, 10, 9)
    assert tuple(record.outcome for record in expected.trials) == (
        Outcome.OBJECTIVE_ACHIEVED, Outcome.PERSPECTIVE_DEFEATED,
        Outcome.ROUND_LIMIT_REACHED, Outcome.UNSUPPORTED_PATH)
    for workers in (1, 2):
        actual = collect_fixed_batches(scripted, ((0, 1), (2, 3)), workers, factory)
        assert actual == expected and summarize(actual) == summarize(expected)
        print(f'scripted N=4: workers={workers}; outcomes=1/1/1/1; actions=24; started=10; completed=9; 120 d10')

    zero_source = replace(source, activation_order=('ally', 'wizard', 'enemy'),
        scene_frames=(replace(source.initial_frame, attack_departures=()),))
    zero_request = NpcMagicSimulationRequest(zero_source, 42, 1)
    zero_factory = ScriptFactory((zero_request.seed_for(0),), ((),))
    zero = collect_fixed_batches(zero_request, ((0,),), 1, zero_factory)
    assert zero == run_npc_magic_simulation(zero_request, rng_factory=zero_factory)
    assert (zero.trials[0].executed_action_count, zero.trials[0].started_round_count,
            zero.trials[0].completed_round_count) == (0, 1, 0)
    assert zero.trials[0].outcome is Outcome.UNSUPPORTED_PATH
    print('Separate zero-action missing-departure source: unsupported retained; rounds=1/0; 0 d10')

    count = negative_transport_probes(scripted, expected.trials)
    print(f'{count} post-pickle negative payload/source/index/seed/Enum/bool/counter checks rejected before canonical acceptance')
    try:
        collect_fixed_batches(seeded, plans[0][1], 1, lambda seed: Random(seed))
    except (AttributeError, TypeError, pickle.PicklingError):
        assert {child.pid for child in active_children()} == original_children
        print('Local lambda rejected by parent pickle before pool creation')
    else:
        raise AssertionError('lambda unexpectedly crossed the local serialization gate')

    failure_request = replace(seeded, trials=3)
    with TemporaryDirectory() as directory:
        marker = Path(directory) / 'factory-indices.txt'
        failure_factory = FailureFactory(tuple(failure_request.seed_for(index) for index in range(3)), str(marker))
        try:
            collect_fixed_batches(failure_request, ((0, 1, 2),), 1, failure_factory)
        except ValueError as error:
            assert type(error) is ValueError and str(error) == 'probe factory failure at index 1'
            assert error.__notes__ == ['factory sentinel note', f'M8 trial index=1, seed={failure_request.seed_for(1)}']
            assert marker.read_text(encoding='utf-8').splitlines() == ['0', '1']
            print('Child failure at index=1 preserves type/message/both notes; index=2 never called; no partial result')
        else:
            raise AssertionError('child factory failure did not propagate')
    assert source == before and getstate() == original_rng
    assert {child.pid for child in active_children()} == original_children
    print('19 successful transported trials in 10 fixed batches; one failed batch; inputs/global RNG unchanged; all six spawn pools closed')
    print('Not verified: public preflight, lazy refill, cancellation/submission/wait failures, larger N, other runtimes or performance')
    print('No production process API, cache, backend selection, balance, JSON/CLI or new game rules')


if __name__ == '__main__':
    main()
