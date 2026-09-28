from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.unit.test_m3_npc_ranged_simulation import request, observations
from towr.application.ranged_simulation_errors import RangedSimulationExecutionError
from towr.application.ranged_simulation_models import (
    RangedSimulationCommand, SimulationExecutionMode as Mode, SimulationExecutionOptions,
)
from towr.application import ranged_simulation_service as service
from towr.simulation.npc_ranged_models import NpcRangedSimulationResult


def command(mode):
    source = request()
    order = tuple(dict.fromkeys(p.definition.id for p in source.scenario.initial.current.state.roster.participants))
    execution = (SimulationExecutionOptions(mode) if mode is Mode.SEQUENTIAL
                 else SimulationExecutionOptions(mode, workers=2, batch_size=3))
    return RangedSimulationCommand(source, execution, order)


class M4RangedServiceTests(unittest.TestCase):
    def test_explicit_dispatch_returns_complete_result_without_changing_outcomes(self):
        for mode in Mode:
            source = command(mode)
            result = NpcRangedSimulationResult(source.request, observations(source.request))
            with self.subTest(mode=mode), patch.object(service, "run_npc_ranged_simulation", return_value=result) as seq, \
                    patch.object(service, "run_npc_ranged_simulation_parallel", return_value=result) as proc:
                self.assertIs(service.execute_ranged_simulation(source), result)
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
                        patch.object(service, "run_npc_ranged_simulation", side_effect=cause) as seq, \
                        patch.object(service, "run_npc_ranged_simulation_parallel", side_effect=cause) as proc:
                    with self.assertRaises(RangedSimulationExecutionError) as caught:
                        service.execute_ranged_simulation(source)
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
                    (NpcRangedSimulationResult(foreign, observations(foreign)), ValueError)):
                with self.subTest(mode=mode, cause=cause_type), \
                        patch.object(service, "run_npc_ranged_simulation", return_value=result), \
                        patch.object(service, "run_npc_ranged_simulation_parallel", return_value=result):
                    with self.assertRaises(RangedSimulationExecutionError) as caught:
                        service.execute_ranged_simulation(source)
                    self.assertIsInstance(caught.exception.__cause__, cause_type)

    def test_untyped_argument_is_rejected_before_dispatch(self):
        with patch.object(service, "run_npc_ranged_simulation") as seq, \
                patch.object(service, "run_npc_ranged_simulation_parallel") as proc:
            for value in (None, {}, request()):
                with self.subTest(value=type(value)), self.assertRaises(TypeError):
                    service.execute_ranged_simulation(value)
            seq.assert_not_called()
            proc.assert_not_called()

    def test_interrupts_propagate_without_becoming_execution_errors(self):
        for mode in Mode:
            for interruption in (KeyboardInterrupt(), SystemExit(2)):
                with self.subTest(mode=mode, interruption=type(interruption)), \
                        patch.object(service, "run_npc_ranged_simulation", side_effect=interruption), \
                        patch.object(service, "run_npc_ranged_simulation_parallel", side_effect=interruption):
                    with self.assertRaises(type(interruption)) as caught:
                        service.execute_ranged_simulation(command(mode))
                    self.assertIs(caught.exception, interruption)
