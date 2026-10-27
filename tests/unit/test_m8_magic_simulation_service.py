"""Explicit backend dispatch, full source guards and application failure ownership."""
from copy import deepcopy
from dataclasses import replace
import json
from multiprocessing import active_children
import random
import unittest
from unittest.mock import patch

from tests.unit.test_m8_magic_json import document
from towr.adapters.magic_simulation_json import parse_magic_simulation_request
from towr.application import magic_simulation_service as service
from towr.application.magic_simulation_errors import MagicSimulationExecutionError
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome
from towr.simulation.npc_magic_models import NpcMagicSimulationResult, NpcMagicTrialRecord
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation
from towr.simulation import npc_magic_simulation as simulation


def command():
    return parse_magic_simulation_request(json.dumps(document()))


def result_for(request, outcome=Outcome.UNSUPPORTED_PATH):
    if outcome is Outcome.ROUND_LIMIT_REACHED:
        actions = started = completed = request.scenario.max_rounds
    elif outcome is Outcome.UNSUPPORTED_PATH:
        actions, started, completed = 0, 1, 0
    else:
        actions, started, completed = 1, 1, 0
    return NpcMagicSimulationResult(request, tuple(NpcMagicTrialRecord(
        request.scenario, i, request.seed_for(i), outcome, actions, started, completed)
        for i in range(request.trials)))


def foreign_commands():
    for change in (
        lambda d: d['simulation'].update(master_seed='43'),
        lambda d: d['simulation'].update(trials=3),
        lambda d: d['simulation'].update(round_budget=5),
        lambda d: d['scenario']['wizard'].update(day_id='other-day'),
        lambda d: d['scenario']['wizard']['caster'].update(wizard_level=3),
        lambda d: d['scenario']['actor_policies'][1]['willpower'].update(dice=4),
        lambda d: d['scenario']['definitions'][1]['attacks'][0].update(damage=4),
        lambda d: d['scenario']['activation_order'].reverse(),
    ):
        data = document()
        change(data)
        yield parse_magic_simulation_request(json.dumps(data))


class MagicSimulationServiceTests(unittest.TestCase):
    def test_sequential_dispatch_uses_exact_request_and_no_custom_rng(self):
        source = command()
        result = result_for(source.request)
        expected = summarize_npc_magic_simulation(result)
        with patch.object(service, 'run_npc_magic_simulation', return_value=result) as sequential, \
                patch.object(service, 'run_npc_magic_simulation_parallel') as process:
            self.assertEqual(service.execute_magic_simulation(source), expected)
        sequential.assert_called_once_with(source.request)
        process.assert_not_called()

    def test_process_dispatch_preserves_exact_options_without_fallback(self):
        source = replace(command(), execution=Options(Mode.PROCESS, 2, 7))
        result = result_for(source.request)
        with patch.object(service, 'run_npc_magic_simulation_parallel', return_value=result) as process, \
                patch.object(service, 'run_npc_magic_simulation') as sequential:
            self.assertEqual(service.execute_magic_simulation(source), summarize_npc_magic_simulation(result))
        process.assert_called_once_with(source.request, workers=2, batch_size=7)
        sequential.assert_not_called()

    def test_all_native_outcomes_are_successful_aggregate_results(self):
        source = command()
        for outcome in Outcome:
            with self.subTest(outcome=outcome):
                result = result_for(source.request, outcome)
                with patch.object(service, 'run_npc_magic_simulation', return_value=result):
                    actual = service.execute_magic_simulation(source)
                self.assertEqual(actual, summarize_npc_magic_simulation(result))
                self.assertEqual(getattr(actual.outcome_counts, outcome.value), source.request.trials)

    def test_wrong_root_fails_directly_before_any_runner_or_summary(self):
        source = command()
        with patch.object(service, 'run_npc_magic_simulation') as sequential, \
                patch.object(service, 'run_npc_magic_simulation_parallel') as process, \
                patch.object(service, 'summarize_npc_magic_simulation') as summarize:
            for value in (None, {}, 42, source.request):
                with self.subTest(value=type(value)), self.assertRaises(TypeError):
                    service.execute_magic_simulation(value)
        sequential.assert_not_called()
        process.assert_not_called()
        summarize.assert_not_called()

    def test_wrong_runner_type_is_failure_before_summary(self):
        source = command()
        for value in (None, source.request, summarize_npc_magic_simulation(result_for(source.request))):
            with self.subTest(value=type(value)), \
                    patch.object(service, 'run_npc_magic_simulation', return_value=value), \
                    patch.object(service, 'summarize_npc_magic_simulation') as summarize:
                with self.assertRaises(MagicSimulationExecutionError) as caught:
                    service.execute_magic_simulation(source)
                self.assertIsInstance(caught.exception.__cause__, TypeError)
                self.assertEqual(caught.exception.request_id, source.request_id)
                summarize.assert_not_called()

    def test_result_source_requires_full_value_not_matching_scenario_id(self):
        source = command()
        for other in foreign_commands():
            self.assertEqual(other.request.scenario.id, source.request.scenario.id)
            with self.subTest(request=other.request), \
                    patch.object(service, 'run_npc_magic_simulation', return_value=result_for(other.request)), \
                    patch.object(service, 'summarize_npc_magic_simulation') as summarize:
                with self.assertRaises(MagicSimulationExecutionError) as caught:
                    service.execute_magic_simulation(source)
                self.assertIsInstance(caught.exception.__cause__, ValueError)
                self.assertEqual(caught.exception.request_id, source.request_id)
                summarize.assert_not_called()

    def test_summary_source_requires_full_request_and_typed_family(self):
        source = command()
        result = result_for(source.request)
        wrong = [None, result, source.request]
        wrong.extend(summarize_npc_magic_simulation(result_for(c.request)) for c in foreign_commands())
        for value in wrong:
            with self.subTest(summary=value), \
                    patch.object(service, 'run_npc_magic_simulation', return_value=result), \
                    patch.object(service, 'summarize_npc_magic_simulation', return_value=value) as summarize:
                with self.assertRaises(MagicSimulationExecutionError) as caught:
                    service.execute_magic_simulation(source)
                self.assertIsInstance(caught.exception.__cause__, (TypeError, ValueError))
                self.assertEqual(caught.exception.request_id, source.request_id)
                summarize.assert_called_once_with(result)

    def test_equal_copied_source_and_separate_external_id_are_accepted(self):
        source = command()
        result = result_for(deepcopy(source.request))
        renamed = replace(source, request_id='external:other')
        with patch.object(service, 'run_npc_magic_simulation', return_value=result):
            self.assertEqual(service.execute_magic_simulation(renamed), summarize_npc_magic_simulation(result))
        self.assertNotEqual(renamed.request_id, renamed.request.scenario.id)

    def test_runner_and_summary_errors_keep_exact_cause_notes_and_external_id(self):
        base = command()
        result = result_for(base.request)
        for mode in Mode:
            source = replace(base, execution=Options(mode, 2, 7) if mode is Mode.PROCESS else Options(mode))
            target = 'run_npc_magic_simulation_parallel' if mode is Mode.PROCESS else 'run_npc_magic_simulation'
            other = 'run_npc_magic_simulation' if mode is Mode.PROCESS else 'run_npc_magic_simulation_parallel'
            for phase in ('runner', 'summary'):
                cause = OSError('private cause from ' + phase)
                cause.add_note('private original note')
                with self.subTest(mode=mode, phase=phase), \
                        patch.object(service, target, side_effect=cause if phase == 'runner' else None,
                                     return_value=result) as run, \
                        patch.object(service, other) as unused, \
                        patch.object(service, 'summarize_npc_magic_simulation', side_effect=cause) as summarize:
                    with self.assertRaises(MagicSimulationExecutionError) as caught:
                        service.execute_magic_simulation(source)
                    self.assertIs(caught.exception.__cause__, cause)
                    self.assertEqual(cause.__notes__, ['private original note'])
                    self.assertEqual(caught.exception.request_id, source.request_id)
                    self.assertEqual(str(caught.exception), 'Magic simulation execution failed')
                    self.assertNotIn('private', str(caught.exception))
                    self.assertEqual(run.call_count, 1)
                    self.assertEqual(summarize.call_count, phase == 'summary')
                    unused.assert_not_called()

    def test_base_exceptions_pass_directly_without_wrapping_or_retry(self):
        source = command()
        result = result_for(source.request)
        for phase in ('runner', 'summary'):
            for error in (KeyboardInterrupt('stop'), SystemExit(9)):
                with self.subTest(phase=phase, error=type(error)), \
                        patch.object(service, 'run_npc_magic_simulation',
                            side_effect=error if phase == 'runner' else None, return_value=result) as run, \
                        patch.object(service, 'run_npc_magic_simulation_parallel') as process, \
                        patch.object(service, 'summarize_npc_magic_simulation', side_effect=error):
                    with self.assertRaises(type(error)) as caught:
                        service.execute_magic_simulation(source)
                    self.assertIs(caught.exception, error)
                    self.assertEqual(run.call_count, 1)
                    process.assert_not_called()

    def test_late_trial_failure_preserves_input_rng_children_and_no_retry(self):
        source = command()
        before = deepcopy(source)
        rng_before = random.getstate()
        children = {c.pid for c in active_children()}
        original = simulation.run_npc_magic_trial
        cause = RuntimeError('private second trial failure')
        cause.add_note('private trial note')
        completed = []

        def fail_second(request, index, **kwargs):
            if index == 1:
                raise cause
            self.assertEqual(index, 0)
            record = original(request, index, **kwargs)
            completed.append(record)
            return record

        with patch.object(simulation, 'run_npc_magic_trial', side_effect=fail_second) as trial, \
                patch.object(service, 'run_npc_magic_simulation_parallel') as process, \
                patch.object(service, 'summarize_npc_magic_simulation') as summarize:
            with self.assertRaises(MagicSimulationExecutionError) as caught:
                service.execute_magic_simulation(source)
            self.assertIs(caught.exception.__cause__, cause)
            self.assertEqual(cause.__notes__, ['private trial note'])
            self.assertEqual(caught.exception.request_id, source.request_id)
            self.assertEqual(trial.call_count, 2)
            self.assertEqual(len(completed), 1)
            summarize.assert_not_called()
            process.assert_not_called()
        self.assertEqual(source, before)
        self.assertEqual(random.getstate(), rng_before)
        self.assertEqual({c.pid for c in active_children()}, children)
