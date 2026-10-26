"""ADR-0038 trial dispatch, exact sources and failure transparency."""
from contextlib import ExitStack
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, PropertyMock, patch

from tests.unit.test_m8_npc_magic_scenario_runner import Dice
from tests.unit.test_m8_npc_magic_simulation_models import request
from towr.domain.npc_magic_scenario_result_models import NpcMagicScenarioResult
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.simulation import npc_magic_simulation as simulation
from towr.simulation.npc_magic_models import NpcMagicOutcomeCounts, NpcMagicTrialRecord


def miscast_result(source):
    return run_npc_magic_scenario(source.scenario, Dice((9, 9, 9)))


class MagicSimulationExecutionTests(unittest.TestCase):
    def test_one_trial_calls_factory_and_existing_runner_once_with_exact_input(self):
        source = request(1)
        result = miscast_result(source)
        rng = Mock()
        factory = Mock(return_value=rng)
        with patch.object(simulation, 'run_npc_magic_scenario', return_value=result) as run:
            record = simulation.run_npc_magic_trial(source, 0, rng_factory=factory)
        factory.assert_called_once_with(source.seed_for(0))
        run.assert_called_once_with(source.scenario, rng)
        self.assertIs(run.call_args.args[0], source.scenario)
        self.assertIs(record.source_scenario, source.scenario)
        self.assertEqual(record, NpcMagicTrialRecord(source.scenario, 0, source.seed_for(0),
            Outcome.UNSUPPORTED_PATH, result.executed_actions, result.started_rounds, result.completed_rounds))
        self.assertNotEqual(record.executed_action_count, len(result.steps))

    def test_default_rng_is_seeded_random_without_modifying_global_rng(self):
        from random import Random, getstate
        source = request(1)
        result = miscast_result(source)
        before = getstate()
        with patch.object(simulation, 'run_npc_magic_scenario', return_value=result) as run:
            simulation.run_npc_magic_trial(source, 0)
        rng = run.call_args.args[1]
        self.assertIsInstance(rng, Random)
        self.assertEqual(rng.getstate(), Random(source.seed_for(0)).getstate())
        self.assertEqual(getstate(), before)

    def test_invalid_request_or_index_rejected_before_factory_or_runner(self):
        from tests.unit.test_m7_npc_mixed_simulation import request as mixed_request
        source = request(2)
        factory = Mock()
        with patch.object(simulation, 'run_npc_magic_scenario', side_effect=AssertionError('no execution')) as run:
            for value in (None, {}, source.scenario, mixed_request()):
                for execute in (simulation.run_npc_magic_simulation,
                                lambda r, **kw: simulation.run_npc_magic_trial(r, 0, **kw)):
                    with self.subTest(value=type(value)), self.assertRaises(TypeError):
                        execute(value, rng_factory=factory)
            for index in (True, False, 1.0, '1', None):
                with self.subTest(index=index), self.assertRaises(TypeError):
                    simulation.run_npc_magic_trial(source, index, rng_factory=factory)
            for index in (-1, 2, 2**64):
                with self.subTest(index=index), self.assertRaises(ValueError):
                    simulation.run_npc_magic_trial(source, index, rng_factory=factory)
        factory.assert_not_called()
        run.assert_not_called()

    def test_batch_uses_index_order_new_rng_per_trial_and_shared_input(self):
        source = request(3)
        result = miscast_result(source)
        streams = tuple(Mock(name=f'rng:{i}') for i in range(3))
        factory = Mock(side_effect=streams)
        with patch.object(simulation, 'run_npc_magic_scenario', return_value=result) as run:
            batch = simulation.run_npc_magic_simulation(source, rng_factory=factory)
        self.assertEqual(tuple(c.args[0] for c in factory.call_args_list), tuple(source.seed_for(i) for i in range(3)))
        self.assertEqual(tuple(c.args[1] for c in run.call_args_list), streams)
        self.assertTrue(all(c.args[0] is source.scenario for c in run.call_args_list))
        self.assertTrue(all(r.source_scenario is source.scenario for r in batch.trials))
        self.assertEqual(batch.outcome_counts, NpcMagicOutcomeCounts(0, 0, 0, 3))
        self.assertEqual(tuple(r.trial_index for r in batch.trials), (0, 1, 2))

    def test_source_check_precedes_every_scalar_projection_even_for_same_id(self):
        source = request(1)
        other = replace(source, scenario=replace(source.scenario, max_rounds=4))
        foreign = miscast_result(other)
        self.assertEqual(foreign.source.id, source.scenario.id)
        self.assertNotEqual(foreign.source, source.scenario)
        with ExitStack() as stack:
            stack.enter_context(patch.object(simulation, 'run_npc_magic_scenario', return_value=foreign))
            for name in ('outcome', 'executed_actions', 'started_rounds', 'completed_rounds'):
                stack.enter_context(patch.object(NpcMagicScenarioResult, name, new_callable=PropertyMock,
                                                 side_effect=AssertionError('no projection')))
            with self.assertRaises(ValueError): simulation.run_npc_magic_trial(source, 0)

    def test_wrong_result_type_is_not_accepted_as_duck_typed_or_foreign_family(self):
        source = request(1)
        for value in (None, {}, SimpleNamespace(source=source.scenario, outcome=Outcome.UNSUPPORTED_PATH,
                                                executed_actions=1, started_rounds=1, completed_rounds=0)):
            with self.subTest(result=type(value)), \
                    patch.object(simulation, 'run_npc_magic_scenario', return_value=value):
                with self.assertRaises(TypeError): simulation.run_npc_magic_trial(source, 0)

    def test_equal_immutable_source_copy_is_allowed_but_record_keeps_original(self):
        source = request(1)
        copy_source = replace(source, scenario=replace(source.scenario))
        result = miscast_result(copy_source)
        self.assertIsNot(result.source, source.scenario)
        with patch.object(simulation, 'run_npc_magic_scenario', return_value=result):
            record = simulation.run_npc_magic_trial(source, 0)
        self.assertIs(record.source_scenario, source.scenario)

    def test_factory_failure_preserves_exception_and_stops_before_third_trial(self):
        source = request(3)
        good = miscast_result(source)
        for failure in (RuntimeError('factory failure'), KeyboardInterrupt('factory interrupted')):
            factory = Mock(side_effect=(Mock(), failure, Mock()))
            with self.subTest(error=type(failure)), \
                    patch.object(simulation, 'run_npc_magic_scenario', return_value=good) as run:
                with self.assertRaises(type(failure)) as caught:
                    simulation.run_npc_magic_simulation(source, rng_factory=factory)
            self.assertIs(caught.exception, failure)
            self.assertEqual((factory.call_count, run.call_count), (2, 1))

    def test_runner_failure_keeps_exception_cause_notes_and_no_partial_batch(self):
        source = request(3)
        good = miscast_result(source)
        cause = ValueError('upstream cause')
        failure = RuntimeError('runner failed')
        failure.__cause__ = cause
        failure.add_note('original note')
        for error in (failure, KeyboardInterrupt('runner interrupted')):
            factory = Mock(side_effect=lambda seed: Mock())
            with self.subTest(error=type(error)), \
                    patch.object(simulation, 'run_npc_magic_scenario', side_effect=(good, error, good)) as run:
                with self.assertRaises(type(error)) as caught:
                    simulation.run_npc_magic_simulation(source, rng_factory=factory)
            self.assertIs(caught.exception, error)
            self.assertEqual((factory.call_count, run.call_count), (2, 2))
        self.assertIs(failure.__cause__, cause)
        self.assertEqual(failure.__notes__, ['original note'])

    def test_bad_result_or_source_on_second_trial_stops_before_third(self):
        source = request(3)
        good = miscast_result(source)
        foreign = miscast_result(replace(source, scenario=replace(source.scenario, max_rounds=4)))
        for value, error in ((None, TypeError), (foreign, ValueError)):
            factory = Mock(side_effect=lambda seed: Mock())
            with self.subTest(error=error), \
                    patch.object(simulation, 'run_npc_magic_scenario', side_effect=(good, value, good)) as run:
                with self.assertRaises(error): simulation.run_npc_magic_simulation(source, rng_factory=factory)
            self.assertEqual((factory.call_count, run.call_count), (2, 2))

    def test_rng_error_and_invalid_rng_propagate_from_existing_runner(self):
        source = request(1)
        failure = RuntimeError('broken RNG')
        rng = Mock()
        rng.randint.side_effect = failure
        with self.assertRaises(RuntimeError) as caught:
            simulation.run_npc_magic_trial(source, 0, rng_factory=lambda seed: rng)
        self.assertIs(caught.exception, failure)
        with self.assertRaises(TypeError):
            simulation.run_npc_magic_trial(source, 0, rng_factory=lambda seed: None)

    def test_record_constructor_failure_is_not_caught_or_retried(self):
        source = request(3)
        good = miscast_result(source)
        first = NpcMagicTrialRecord(source.scenario, 0, source.seed_for(0), good.outcome,
            good.executed_actions, good.started_rounds, good.completed_rounds)
        failure = ValueError('record construction')
        failure.__cause__ = RuntimeError('original construction cause')
        failure.add_note('original record note')
        factory = Mock(return_value=Mock())
        with patch.object(simulation, 'run_npc_magic_scenario', return_value=good) as run, \
                patch.object(simulation, 'NpcMagicTrialRecord', side_effect=(first, failure)) as construct:
            with self.assertRaises(ValueError) as caught:
                simulation.run_npc_magic_simulation(source, rng_factory=factory)
        self.assertIs(caught.exception, failure)
        self.assertEqual(str(caught.exception.__cause__), 'original construction cause')
        self.assertEqual(caught.exception.__notes__, ['original record note'])
        self.assertEqual((factory.call_count, run.call_count, construct.call_count), (2, 2, 2))

    def test_final_constructor_failure_propagates_after_exactly_requested_trials(self):
        source = request(2)
        good = miscast_result(source)
        failure = ValueError('batch construction')
        failure.__cause__ = RuntimeError('original batch cause')
        failure.add_note('original batch note')
        factory = Mock(side_effect=lambda seed: Mock())
        with patch.object(simulation, 'run_npc_magic_scenario', return_value=good) as run, \
                patch.object(simulation, 'NpcMagicSimulationResult', side_effect=failure) as construct:
            with self.assertRaises(ValueError) as caught:
                simulation.run_npc_magic_simulation(source, rng_factory=factory)
        self.assertIs(caught.exception, failure)
        self.assertEqual(str(caught.exception.__cause__), 'original batch cause')
        self.assertEqual(caught.exception.__notes__, ['original batch note'])
        self.assertEqual((factory.call_count, run.call_count, construct.call_count), (2, 2, 1))
