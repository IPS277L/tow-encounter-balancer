"""Explicit opt-in admission, automatic continuation and legacy source controls."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.unit.test_m8_miscast_continuation_policy import continuation_policy
from tests.unit.test_m8_npc_magic_scenario_runner import admitted, Dice
from tests.unit.test_m8_npc_roster_miscast_preparation import casting_pending, request
from towr.domain.npc_magic_step_models import NpcMagicUnsupportedReason as Reason
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.npc_roster_miscast_resolution import prepare_npc_roster_miscast
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation


class MiscastContinuationAdmissionTests(unittest.TestCase):
    def test_explicit_none_keeps_complete_legacy_trace_ids_stops_and_draws(self):
        cases = (
            (admitted(), (9, 9, 9)),  # raw Miscast stop
            (replace(admitted(), max_rounds=1), (10,) * 15),  # round limit
            (replace(admitted(), activation_order=('ally', 'wizard', 'enemy')),
             (1, 2, 3, 10, 10, 10)),  # victory through a real attack
        )
        for source, values in cases:
            with self.subTest(values=values):
                before = deepcopy(source)
                first_rng, second_rng = Dice(values), Dice(values)
                first = run_npc_magic_scenario(source, first_rng)
                second = run_npc_magic_scenario(replace(source, miscast_continuation=None), second_rng)
                self.assertEqual(first, second)
                first_rng.exhausted()
                second_rng.exhausted()
                self.assertEqual(source, before)

    def test_opt_in_continues_raw_miscast_and_preserves_unsupported_effect(self):
        source = replace(admitted(), miscast_continuation=continuation_policy())
        dice = Dice((9, 9, 9, 1, 1, 1))
        result = run_npc_magic_scenario(source, dice)
        dice.exhausted()
        self.assertIs(result.source, source)
        self.assertIs(result.unsupported.reason, Reason.MISCAST_EFFECT)
        self.assertEqual(result.current.wizard.magic_state.miscast_dice, 3)
        self.assertIsNone(result.current.pending_miscast)
        self.assertIsNotNone(result.current.pending_miscast_continuation)

    def test_opt_in_cannot_turn_raw_or_prepared_state_into_fresh_input(self):
        source, raw = casting_pending()
        source = replace(source, miscast_continuation=continuation_policy())
        prepared = prepare_npc_roster_miscast(request(raw)).state
        for state in (raw, prepared):
            with self.subTest(prepared=state is prepared), self.assertRaises(ValueError):
                replace(source, initial=state)

    def test_native_records_and_summary_keep_opt_in_and_unsupported_denominator(self):
        source = replace(admitted(), miscast_continuation=continuation_policy())
        request = NpcMagicSimulationRequest(source, 42, 2)
        streams = []
        def factory(seed):
            dice = Dice((9, 9, 9, 1, 1, 1))
            streams.append(dice)
            return dice
        result = run_npc_magic_simulation(request, rng_factory=factory)
        summary = summarize_npc_magic_simulation(result)
        self.assertIs(result.source_request, request)
        self.assertIs(summary.source_request, request)
        self.assertEqual(summary.trials, 2)
        self.assertEqual(summary.outcome_counts.unsupported_path, 2)
        self.assertEqual(len(streams), 2)
        self.assertIsNot(streams[0], streams[1])
        for record, stream in zip(result.trials, streams, strict=True):
            self.assertIs(record.source_scenario, source)
            self.assertIs(record.source_scenario.miscast_continuation, source.miscast_continuation)
            stream.exhausted()


if __name__ == '__main__':
    unittest.main()
