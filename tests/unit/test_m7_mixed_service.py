from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.unit.test_m7_npc_mixed_simulation import request, observations
from towr.application.mixed_simulation_errors import MixedSimulationExecutionError
from towr.application.ranged_simulation_models import (
    SimulationExecutionMode as Mode, SimulationExecutionOptions,
)
from towr.application.mixed_simulation_models import MixedSimulationCommand
from towr.simulation.npc_mixed_summary import summarize_npc_mixed_simulation
from towr.application import mixed_simulation_service as service
from towr.simulation.npc_mixed_models import NpcMixedSimulationResult


def command(mode):
    source = request()
    order = tuple(dict.fromkeys(p.definition.id for p in source.scenario.initial.current.state.roster.participants))
    execution = (SimulationExecutionOptions(mode) if mode is Mode.SEQUENTIAL
                 else SimulationExecutionOptions(mode, workers=2, batch_size=3))
    return MixedSimulationCommand(source, execution, order)


class M7MixedServiceTests(unittest.TestCase):
    def test_failure_after_one_completed_trial_returns_no_summary(self):
        from towr.simulation import npc_mixed_simulation as simulation
        source = command(Mode.SEQUENTIAL)
        original = simulation.run_npc_mixed_trial
        cause = RuntimeError("second trial failed")

        def fail_second(request, index, **kwargs):
            if index == 1:
                raise cause
            return original(request, index, **kwargs)

        with patch.object(simulation, "run_npc_mixed_trial", side_effect=fail_second) as trial, \
                patch.object(service, "summarize_npc_mixed_simulation") as summarize:
            with self.assertRaises(MixedSimulationExecutionError) as caught:
                service.execute_mixed_simulation(source)
            self.assertEqual(trial.call_count, 2)
            summarize.assert_not_called()
        self.assertIs(caught.exception.__cause__, cause)

    def test_summary_failure_type_and_source_are_execution_failures(self):
        source = command(Mode.SEQUENTIAL)
        result = NpcMixedSimulationResult(source.request, observations(source.request))
        foreign = replace(source.request, master_seed=43)
        foreign_summary = summarize_npc_mixed_simulation(NpcMixedSimulationResult(foreign, observations(foreign)))
        for value, cause_type in ((None, TypeError), (foreign_summary, ValueError)):
            with self.subTest(value=value), patch.object(service, "run_npc_mixed_simulation", return_value=result), \
                    patch.object(service, "summarize_npc_mixed_simulation", return_value=value) as summarize:
                with self.assertRaises(MixedSimulationExecutionError) as caught:
                    service.execute_mixed_simulation(source)
                self.assertIsInstance(caught.exception.__cause__, cause_type)
                summarize.assert_called_once_with(result)
        cause = RuntimeError("summary failed")
        cause.add_note("original summary note")
        with patch.object(service, "run_npc_mixed_simulation", return_value=result), \
                patch.object(service, "summarize_npc_mixed_simulation", side_effect=cause):
            with self.assertRaises(MixedSimulationExecutionError) as caught:
                service.execute_mixed_simulation(source)
        self.assertIs(caught.exception.__cause__, cause)
        self.assertEqual(caught.exception.__cause__.__notes__, ["original summary note"])

    def test_ranged_command_is_rejected_before_dispatch(self):
        from tests.unit.test_m4_ranged_service import command as ranged_command
        from tests.unit.test_m6_melee_service import command as melee_command
        with patch.object(service, "run_npc_mixed_simulation") as seq, \
                patch.object(service, "run_npc_mixed_simulation_parallel") as proc:
            for foreign in (ranged_command(Mode.SEQUENTIAL), melee_command(Mode.SEQUENTIAL)):
                with self.assertRaises(TypeError):
                    service.execute_mixed_simulation(foreign)
            seq.assert_not_called()
            proc.assert_not_called()

    def test_result_source_includes_mixed_pair_order_and_actor_flags(self):
        for mode in Mode:
            source = command(mode)
            scenario = source.request.scenario
            for altered in (
                replace(scenario, pair_ranges=scenario.pair_ranges[::-1]),
                replace(scenario, actor_policies=(replace(scenario.actor_policies[0], can_leave_zone=True),
                                                   *scenario.actor_policies[1:])),
            ):
                foreign = replace(source.request, scenario=altered)
                result = NpcMixedSimulationResult(foreign, observations(foreign))
                with self.subTest(mode=mode), patch.object(service, "run_npc_mixed_simulation", return_value=result), \
                        patch.object(service, "run_npc_mixed_simulation_parallel", return_value=result), \
                        patch.object(service, "summarize_npc_mixed_simulation") as summarize:
                    with self.assertRaises(MixedSimulationExecutionError) as caught:
                        service.execute_mixed_simulation(source)
                    self.assertIsInstance(caught.exception.__cause__, ValueError)
                    summarize.assert_not_called()

    def test_explicit_dispatch_returns_complete_result_without_changing_outcomes(self):
        for mode in Mode:
            source = command(mode)
            result = NpcMixedSimulationResult(source.request, observations(source.request))
            with self.subTest(mode=mode), patch.object(service, "run_npc_mixed_simulation", return_value=result) as seq, \
                    patch.object(service, "run_npc_mixed_simulation_parallel", return_value=result) as proc:
                self.assertEqual(service.execute_mixed_simulation(source), summarize_npc_mixed_simulation(result))
                if mode is Mode.SEQUENTIAL:
                    seq.assert_called_once_with(source.request)
                    proc.assert_not_called()
                else:
                    proc.assert_called_once_with(source.request, workers=2, batch_size=3)
                    seq.assert_not_called()
                self.assertEqual(source, command(mode))

    def test_failure_preserves_cause_and_never_retries_or_falls_back(self):
        for mode in Mode:
            for cause in (RuntimeError("worker failed"), ValueError(), OSError("pool failed")):
                source = command(mode)
                cause.add_note("trial index=1")
                with self.subTest(mode=mode, cause=type(cause)), \
                        patch.object(service, "run_npc_mixed_simulation", side_effect=cause) as seq, \
                        patch.object(service, "run_npc_mixed_simulation_parallel", side_effect=cause) as proc:
                    with self.assertRaises(MixedSimulationExecutionError) as caught:
                        service.execute_mixed_simulation(source)
                    self.assertIs(caught.exception.__cause__, cause)
                    self.assertEqual(caught.exception.__cause__.__notes__, ["trial index=1"])
                    self.assertEqual(caught.exception.request_id, source.request.scenario.initial.current.id)
                    self.assertTrue(str(caught.exception).strip())
                    self.assertEqual((seq.call_count, proc.call_count),
                                     (1, 0) if mode is Mode.SEQUENTIAL else (0, 1))

    def test_wrong_result_type_and_foreign_source_are_execution_failures(self):
        for mode in Mode:
            source = command(mode)
            foreign = replace(source.request, master_seed=43)
            for result, cause_type in ((None, TypeError),
                    (NpcMixedSimulationResult(foreign, observations(foreign)), ValueError)):
                with self.subTest(mode=mode, cause=cause_type), \
                        patch.object(service, "run_npc_mixed_simulation", return_value=result), \
                        patch.object(service, "run_npc_mixed_simulation_parallel", return_value=result), \
                        patch.object(service, "summarize_npc_mixed_simulation") as summarize:
                    with self.assertRaises(MixedSimulationExecutionError) as caught:
                        service.execute_mixed_simulation(source)
                    self.assertIsInstance(caught.exception.__cause__, cause_type)
                    summarize.assert_not_called()

    def test_untyped_argument_is_rejected_before_dispatch(self):
        with patch.object(service, "run_npc_mixed_simulation") as seq, \
                patch.object(service, "run_npc_mixed_simulation_parallel") as proc:
            for value in (None, {}, request()):
                with self.subTest(value=type(value)), self.assertRaises(TypeError):
                    service.execute_mixed_simulation(value)
            seq.assert_not_called()
            proc.assert_not_called()

    def test_interrupts_propagate_without_becoming_execution_errors(self):
        for mode in Mode:
            for interruption in (KeyboardInterrupt(), SystemExit(2)):
                with self.subTest(mode=mode, interruption=type(interruption)), \
                        patch.object(service, "run_npc_mixed_simulation", side_effect=interruption), \
                        patch.object(service, "run_npc_mixed_simulation_parallel", side_effect=interruption):
                    with self.assertRaises(type(interruption)) as caught:
                        service.execute_mixed_simulation(command(mode))
                    self.assertIs(caught.exception, interruption)
