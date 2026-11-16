"""Small deterministic observations prove progress without changing battle RNG."""
from dataclasses import FrozenInstanceError, replace
from threading import Event
import unittest
from unittest.mock import Mock, patch

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10, first_wound_script
from towr.application.dynamic_encounter import (
    DynamicEncounterCancelled, DynamicEncounterProgress, DynamicEncounterRequest,
    DynamicProgressPhase as Phase, NpcSearchSpace, search_dynamic_encounter,
)
from towr.domain.generated_npc_models import GeneratedWeapon
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.pc_melee_result_models import PcMeleeOutcome as Outcome
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation, run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def tiny_request():
    source = make_pc_melee_scenario(max_rounds=1)
    space = NpcSearchSpace(weapon_skill=(2,),strength=(1,),toughness=(1,),agility=(1,),
        melee=(2,),athletics=(2,),defence=(2,),weapon=(GeneratedWeapon.STAFF,),
        light_armour=(False,),shield=(False,),abilities=((),))
    return DynamicEncounterRequest(source.party, source.facts, source.day_id, space,
        1, 1, .5, 1., 42, 3, 2, 3, 2, 12, 1, NpcDefeatDisposition.KILLED)


class SimulationTrialProgressTests(unittest.TestCase):
    def test_observer_receives_actual_records_once_after_each_completed_trial(self):
        source = PcMeleeSimulationRequest(make_pc_melee_scenario(max_rounds=1), 42, 2)
        scripts = [ScriptedD10([1,1,1,10,10]), ScriptedD10(first_wound_script(1))]
        rngs = iter(scripts)
        completed = []
        result = run_pc_melee_simulation(source, rng_factory=lambda seed: next(rngs),
            on_trial_complete=completed.append)
        self.assertEqual(completed, list(result.records))
        self.assertEqual([r.trial_index for r in completed], [0,1])
        self.assertEqual([r.outcome for r in completed], [Outcome.OBJECTIVE_ACHIEVED,Outcome.ROUND_LIMIT])
        self.assertEqual([r.seed for r in completed], [source.seed_for(0), source.seed_for(1)])
        for rng in scripts:
            rng.assert_exhausted()
        with self.assertRaises(FrozenInstanceError):
            completed[0].trial_index = 9

    def test_invalid_observer_fails_before_creating_trial_rng(self):
        source = PcMeleeSimulationRequest(make_pc_melee_scenario(max_rounds=1), 42, 1)
        factory = Mock()
        with self.assertRaises(TypeError):
            run_pc_melee_simulation(source, rng_factory=factory, on_trial_complete=object())
        factory.assert_not_called()

    def test_observer_failure_does_not_start_another_trial(self):
        source = PcMeleeSimulationRequest(make_pc_melee_scenario(max_rounds=1), 42, 2)
        factory = Mock(side_effect=lambda seed: ScriptedD10([1,1,1,10,10]))
        observer = Mock(side_effect=RuntimeError('observer stopped'))
        with self.assertRaisesRegex(RuntimeError, 'observer stopped'):
            run_pc_melee_simulation(source, rng_factory=factory, on_trial_complete=observer)
        self.assertEqual(factory.call_count, 1)
        self.assertEqual(observer.call_count, 1)


class DynamicEncounterProgressTests(unittest.TestCase):
    def test_progress_preserves_seeded_result_and_counts_actual_trials(self):
        source = tiny_request()
        baseline = search_dynamic_encounter(source)
        events, records = [], {}

        def actual_trial(request, index, **kwargs):
            record = run_pc_melee_trial(request, index, **kwargs)
            records.setdefault(request.scenario.id, []).append(record)
            return record

        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_trial', side_effect=actual_trial):
            observed = search_dynamic_encounter(source, on_progress=events.append)
        self.assertEqual(observed, baseline)
        self.assertEqual({e.phase for e in events}, set(Phase))
        self.assertEqual(events[-1].phase, Phase.COMPLETE)
        self.assertEqual(events[-1].total_completed_trials, observed.total_trials)
        # Finite space yields one explored composition and one finalist, even
        # though the configured maxima allow three candidates/two finalists.
        self.assertEqual(observed.total_trials, 5)
        self.assertLess(observed.total_trials, source.max_total_trials)
        self.assertEqual([e.total_completed_trials for e in events],
            sorted(e.total_completed_trials for e in events))
        self.assertTrue(all(e.trial_budget == source.max_total_trials for e in events))
        for stage, expected_trials, expected_count in (('explore',2,3),('validate',3,1)):
            trials = [e for e in events if e.phase is Phase.SIMULATING and e.stage == stage]
            self.assertEqual([e.completed_trials for e in trials], list(range(expected_trials+1)))
            self.assertEqual([e.candidate_count for e in trials], [expected_count]*(expected_trials+1))
            self.assertIsNone(trials[0].win_rate)
            actual = records[f'dynamic:{stage}:0']
            for event in trials[1:]:
                prefix = actual[:event.completed_trials]
                wins = sum(record.outcome is Outcome.OBJECTIVE_ACHIEVED for record in prefix)
                unsupported = sum(record.outcome is Outcome.UNSUPPORTED_PATH for record in prefix)
                self.assertEqual((event.wins,event.unsupported_trials),(wins,unsupported))
                self.assertEqual(event.win_rate, wins/len(prefix))
                self.assertEqual(event.npc_count, 1)
            completed, = [e for e in events if e.phase is Phase.CANDIDATE_COMPLETE and e.stage == stage]
            self.assertEqual(completed.completed_trials, expected_trials)
            self.assertEqual(completed.wins, trials[-1].wins)

    def test_injected_simulator_reports_only_candidate_boundaries(self):
        events = []
        simulator = Mock(side_effect=lambda source:
            summarize_pc_melee_simulation(run_pc_melee_simulation(source)))
        result = search_dynamic_encounter(tiny_request(), simulator, on_progress=events.append)
        self.assertEqual(simulator.call_count, 2)
        self.assertTrue(all(len(call.args) == 1 and not call.kwargs for call in simulator.call_args_list))
        self.assertFalse(any(e.phase is Phase.SIMULATING and 0 < e.completed_trials < e.trial_count for e in events))
        complete = [e for e in events if e.phase is Phase.CANDIDATE_COMPLETE]
        self.assertEqual([e.completed_trials for e in complete], [2,3])
        self.assertEqual(events[-1].total_completed_trials, result.total_trials)

    def test_cancellation_from_first_observation_stops_before_next_trial(self):
        cancelled = Event()
        events = []

        def observer(event):
            events.append(event)
            if event.phase is Phase.SIMULATING and event.completed_trials == 1:
                cancelled.set()

        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_trial', wraps=run_pc_melee_trial) as trial:
            with self.assertRaises(DynamicEncounterCancelled):
                search_dynamic_encounter(tiny_request(), cancel_requested=cancelled.is_set,
                    on_progress=observer)
        self.assertEqual(trial.call_count, 1)
        self.assertFalse(any(e.phase in (Phase.CANDIDATE_COMPLETE, Phase.COMPLETE) for e in events))
        self.assertEqual(events[-1].total_completed_trials, 1)

    def test_invalid_progress_observer_does_not_execute_simulation(self):
        source = tiny_request()
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_trial') as trial:
            with self.assertRaises(TypeError):
                search_dynamic_encounter(source, on_progress=object())
        trial.assert_not_called()

    def test_snapshots_are_frozen_and_reject_impossible_observation_counts(self):
        progress = DynamicEncounterProgress(Phase.SIMULATING,'explore',1,1,1,1,2,1,5,1,0)
        self.assertEqual(progress.win_rate, 1.)
        self.assertIsNone(replace(progress, completed_trials=0, wins=0).win_rate)
        with self.assertRaises(FrozenInstanceError):
            progress.wins = 2
        for changes in ({'completed_trials':True}, {'wins':2}, {'unsupported_trials':1},
                {'total_completed_trials':0}, {'total_completed_trials':6},
                {'candidate_number':2}, {'stage':'unknown'}, {'phase':'simulating'}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(progress, **changes)


if __name__ == '__main__':
    unittest.main()
