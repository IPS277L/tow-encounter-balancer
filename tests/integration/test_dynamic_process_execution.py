"""Actual spawn workers: reuse, cooperative cancellation and final cleanup."""
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, replace
import json
from pathlib import Path
from random import Random
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic, sleep
import unittest
from unittest.mock import patch

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.adapters.dynamic_encounter_json import parse_dynamic_encounter_request
from towr.application.dynamic_encounter import (
    DynamicEncounterCancelled, DynamicProgressPhase, search_dynamic_encounter,
)
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_process import PcMeleeProcessSession, PcMeleeSimulationCancelled
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation


MODULE = 'towr.simulation.pc_melee_process'
EXECUTION = SimulationExecutionOptions(SimulationExecutionMode.PROCESS, 2, 1)


class SlowRecordingRandom:
    def __init__(self, seed, path):
        self.random = Random(seed)
        self.path = path

    def randint(self, start, end):
        with open(self.path, 'ab') as stream:
            stream.write(b'x')
        sleep(.12)
        return self.random.randint(start, end)


@dataclass(frozen=True)
class SlowRecordingFactory:
    path: str

    def __call__(self, seed):
        return SlowRecordingRandom(seed, self.path)


class FailingRandom:
    def randint(self, start, end):
        raise RuntimeError('intentional spawned RNG failure')


def failing_factory(seed):
    return FailingRandom()


class TrackedExecutor(ProcessPoolExecutor):
    """Retain process handles before stdlib clears them during shutdown."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stopped_processes = ()
        self.shutdown_count = 0

    def shutdown(self, *args, **kwargs):
        self.shutdown_count += 1
        self.stopped_processes = tuple(self._processes.values()) if self._processes else ()
        return super().shutdown(*args, **kwargs)


@contextmanager
def tracked_pools():
    pools = []
    def create(**kwargs):
        pool = TrackedExecutor(**kwargs)
        pools.append(pool)
        return pool
    with patch(MODULE + '.ProcessPoolExecutor', side_effect=create):
        yield pools


class DynamicProcessExecutionTests(unittest.TestCase):
    def source(self, *, trials=3, seed=42):
        return PcMeleeSimulationRequest(make_pc_melee_scenario(max_rounds=1), seed, trials)

    def assert_closed(self, pools):
        self.assertTrue(pools)
        for pool in pools:
            self.assertEqual(pool.shutdown_count, 1)
            self.assertTrue(pool.stopped_processes)
            self.assertTrue(all(not process.is_alive() for process in pool.stopped_processes))

    def test_real_spawn_pool_is_reused_and_matches_both_sequential_sources(self):
        first = self.source()
        second = replace(first, scenario=replace(first.scenario, id='next-candidate'), master_seed=73)
        references = [run_pc_melee_simulation(source) for source in (first, second)]
        with tracked_pools() as pools:
            with PcMeleeProcessSession(workers=2) as session:
                self.assertEqual(session.run(first), references[0])
                self.assertEqual(len(pools), 1)
                processes = tuple(pools[0]._processes.values())
                pids = tuple(process.pid for process in processes)
                self.assertEqual(len(pids), 2)
                self.assertTrue(all(process.is_alive() for process in processes))
                self.assertEqual(session.run(second), references[1])
                self.assertEqual(len(pools), 1)
                self.assertEqual(tuple(pools[0]._processes), pids)
            self.assert_closed(pools)
            self.assertTrue(all(not process.is_alive() for process in processes))

    def test_cancel_during_worker_rng_finishes_workers_before_ack_and_next_run_succeeds(self):
        source = self.source(trials=8)
        observed = []
        with TemporaryDirectory(prefix='towr-process-cancel-') as directory:
            recording = Path(directory) / 'rolls.bin'
            started = monotonic()
            def cancel_after_worker_roll():
                if recording.exists() and recording.stat().st_size:
                    return True
                if monotonic() - started > 15:
                    raise AssertionError('spawned worker did not reach its first RNG call')
                return False
            with tracked_pools() as pools:
                session = PcMeleeProcessSession(workers=2,
                    cancel_requested=cancel_after_worker_roll)
                with self.assertRaises(PcMeleeSimulationCancelled):
                    session.run(source, rng_factory=SlowRecordingFactory(str(recording)),
                        on_trial_complete=observed.append)
                self.assertEqual(observed, [])
                self.assert_closed(pools)
                count_after_ack = recording.stat().st_size
                self.assertGreater(count_after_ack, 0)
                sleep(.25)
                self.assertEqual(recording.stat().st_size, count_after_ack)
                # A new session owns a new signal and must remain usable.
                fresh_source = replace(source, trials=2)
                with PcMeleeProcessSession(workers=2) as fresh:
                    self.assertEqual(fresh.run(fresh_source), run_pc_melee_simulation(fresh_source))
                self.assertEqual(len(pools), 2)
                self.assert_closed(pools)

    def test_dynamic_validation_cancellation_closes_pool_before_return_and_allows_new_search(self):
        raw = json.loads(Path('docs/examples/dynamic/search.request.json').read_bytes())
        raw['npc_count'] = dict(minimum=1, maximum=1)
        raw['max_rounds'] = 1
        raw['targets']['started_rounds'] = dict(numerator=1, denominator=1)
        raw['search'].update(max_candidates=1, exploration_trials=1,
            finalist_trials=3, top_k=1, max_total_trials=4)
        request = parse_dynamic_encounter_request(json.dumps(raw)).request
        cancel = Event()
        progress = []
        def observe(event):
            progress.append(event)
            if event.stage == 'validate' and event.completed_trials >= 1:
                cancel.set()
        with tracked_pools() as pools:
            with self.assertRaises(DynamicEncounterCancelled):
                search_dynamic_encounter(request, execution=EXECUTION,
                    cancel_requested=cancel.is_set, on_progress=observe)
            self.assertTrue(cancel.is_set())
            self.assertTrue(any(event.stage == 'explore' and event.completed_trials == 1
                for event in progress))
            self.assertEqual(progress[-1].stage, 'validate')
            self.assertEqual(progress[-1].completed_trials, 1)
            self.assertNotIn(DynamicProgressPhase.COMPLETE, [event.phase for event in progress])
            totals = [event.total_completed_trials for event in progress]
            self.assertEqual(totals, sorted(totals))
            self.assert_closed(pools)
            result = search_dynamic_encounter(request, execution=EXECUTION)
            self.assertEqual(result, search_dynamic_encounter(request))
            self.assertEqual(result.total_trials, 4)
            self.assertEqual(len(pools), 2)
            self.assert_closed(pools)

    def test_real_worker_exception_returns_no_partial_result_and_closes_processes(self):
        observed = []
        with tracked_pools() as pools:
            session = PcMeleeProcessSession(workers=2)
            with self.assertRaisesRegex(RuntimeError, 'intentional spawned RNG failure') as caught:
                session.run(self.source(trials=4), rng_factory=failing_factory,
                    on_trial_complete=observed.append)
            self.assertEqual(observed, [])
            self.assertTrue(any('trial index=' in note for note in caught.exception.__notes__))
            self.assertEqual(len(pools), 1)
            self.assert_closed(pools)
            with self.assertRaises(RuntimeError):
                session.run(self.source())


if __name__ == '__main__':
    unittest.main()
