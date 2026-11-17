"""Execution is separate from source facts and cannot silently be ignored."""
import unittest
from unittest.mock import Mock,patch

from tests.unit.test_dynamic_encounter_progress import tiny_request
from towr.application.dynamic_encounter import search_dynamic_encounter
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode,SimulationExecutionOptions as Options


class DynamicExecutionOptionsTests(unittest.TestCase):
    def test_untyped_options_and_custom_simulator_combination_are_rejected(self):
        source=tiny_request()
        with patch('towr.application.dynamic_encounter._search_dynamic_encounter') as run:
            with self.assertRaises(TypeError):
                search_dynamic_encounter(source,execution={'mode':'process','workers':2})
            for options in (Options(Mode.SEQUENTIAL),Options(Mode.PROCESS,2,1)):
                with self.subTest(mode=options.mode),self.assertRaises(ValueError):
                    search_dynamic_encounter(source,Mock(),execution=options)
            run.assert_not_called()

    def test_dynamic_process_has_internal_single_trial_batch(self):
        with patch('towr.application.dynamic_encounter._search_dynamic_encounter') as run:
            with self.assertRaisesRegex(ValueError,'one-trial'):
                search_dynamic_encounter(tiny_request(),execution=Options(Mode.PROCESS,2,32))
            run.assert_not_called()

    def test_sequential_options_forward_observers_without_a_pool(self):
        source=tiny_request();observer=Mock();cancel=Mock(return_value=False)
        with patch('towr.application.dynamic_encounter._search_dynamic_encounter',return_value='observed') as run, \
                patch('towr.simulation.pc_melee_process.ProcessPoolExecutor') as pool:
            self.assertEqual(search_dynamic_encounter(source,execution=Options(Mode.SEQUENTIAL),
                on_progress=observer,cancel_requested=cancel),'observed')
            run.assert_called_once_with(source,None,cancel_requested=cancel,on_progress=observer)
            pool.assert_not_called()


if __name__=='__main__':unittest.main()
