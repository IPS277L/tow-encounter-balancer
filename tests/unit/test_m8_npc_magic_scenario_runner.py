"""Admission, evidence and exception boundaries of the single magic runner."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from random import Random, getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_npc_magic_scenario import scenario, frame, OPPOSITION, ROUTE
from towr.domain.npc_magic_scene_models import NpcMagicAttackDeparture, NpcMagicBrokenPlan, NpcMagicBrokenPlanKind
from towr.domain.npc_magic_step_models import NpcMagicUnsupportedReason as Reason
from towr.domain.npc_magic_scenario_result_models import npc_magic_terminal_outcome
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario as run


class Dice:
    def __init__(self, values):
        self.values = tuple(values)
        self.calls = 0

    def randint(self, low, high):
        assert (low, high) == (1, 10) and self.calls < len(self.values), 'unexpected RNG call'
        value = self.values[self.calls]
        self.calls += 1
        assert low <= value <= high
        return value

    def exhausted(self):
        assert self.calls == len(self.values), (self.calls, len(self.values))


def departures(source, *, can_leave=True):
    # Authored facts for these open test arenas, never production inference.
    return replace(source, scene_frames=tuple(replace(f, attack_departures=tuple(
        NpcMagicAttackDeparture(i, can_leave) for i in f.key.live_actor_ids)) for f in source.scene_frames))


def admitted(**kwargs):
    return departures(scenario(**kwargs))


def after_curse(*, plan=None, ally_zone='arena', enemy_zone='arena', max_rounds=1):
    source = scenario(enemy_zone=enemy_zone)
    placements = tuple(replace(p, zone_id=ally_zone) if p.entity_id == 'ally' else p for p in source.initial.spatial_state.placements)
    initial = replace(source.initial, spatial_state=replace(source.initial.spatial_state, placements=placements))
    moved = tuple(replace(p, zone_id='middle' if enemy_zone == 'arena' else 'far')
                  if p.entity_id == 'enemy' else p for p in placements)
    future = frame(initial, placements=moved)
    if plan is not None:
        future = replace(future, broken_plans=(plan,))
    return departures(replace(source, initial=initial, max_rounds=max_rounds, scene_frames=(frame(initial), future)))


class MagicRunnerBoundaryTests(unittest.TestCase):
    def test_type_admission_and_rng_protocol_before_any_draw(self):
        rng = Dice(())
        for source in (None, 'scenario', scenario().initial_runtime_state):
            with self.assertRaises(TypeError): run(source, rng)
        for rng in (None, object(), 1):
            with self.assertRaises(TypeError): run(admitted(), rng)

    def test_complete_scenario_preflight_is_rechecked_once_before_rng(self):
        source = admitted(); rng = Dice(())
        failure = ValueError('invalid full admission')
        with patch('towr.engine.npc_magic_scenario_runner.replace', side_effect=failure) as admission:
            with self.assertRaises(ValueError) as caught: run(source, rng)
        self.assertIs(caught.exception, failure)
        admission.assert_called_once_with(source)
        self.assertEqual(rng.calls, 0)

    def test_repeat_is_equal_with_injected_rng_and_preserves_input_global_rng(self):
        source = admitted(); before = deepcopy(source); global_rng = getstate()
        first, second = run(source, Random(102)), run(source, Random(102))
        self.assertEqual(first, second)
        self.assertIs(first.source, source)
        self.assertEqual(source, before)
        self.assertEqual(getstate(), global_rng)
        with self.assertRaises(FrozenInstanceError): first.source = None

    def test_unknown_attack_departure_is_a_stop_before_attack_rng(self):
        source = scenario(); rng = Dice((10,) * 3)
        result = run(source, rng); rng.exhausted()
        self.assertIs(result.unsupported.reason, Reason.MISSING_ROUTE)
        self.assertEqual(result.unsupported.actor_id, 'ally')
        self.assertEqual(result.unsupported.missing_actor_ids, ('enemy',))
        self.assertFalse(result.current.round_state.active_turn.action_slots[0].executed)
        self.assertEqual(result.executed_actions, 1)

    def test_explicit_false_departure_is_preserved_in_kernel_request(self):
        source = replace(departures(scenario(), can_leave=False), max_rounds=1)
        result = run(source, Dice((10,) * 15))
        attacks = [s.result.source.attack for s in result.steps if hasattr(s.result.source, 'attack')]
        self.assertEqual(len(attacks), 2)
        self.assertTrue(all(not a.execution.kernel_request.can_target_leave_zone for a in attacks))

    def test_journal_rejects_a_bound_attack_that_disagrees_with_supplied_departure(self):
        from tests.unit.test_m8_npc_magic_scenario_result import victory
        result = victory().result()
        with self.assertRaisesRegex(ValueError, 'departure differs'):
            replace(result, source=departures(result.source, can_leave=False))

    def test_departure_types_tuple_copies_ids_and_booleans(self):
        with self.assertRaises(TypeError): NpcMagicAttackDeparture('enemy', 1)
        with self.assertRaises(ValueError): NpcMagicAttackDeparture(' ', True)
        source = scenario(); rows = [NpcMagicAttackDeparture('enemy', False)]
        actual = replace(source.initial_frame, attack_departures=rows); rows.clear()
        self.assertEqual(len(actual.attack_departures), 1)
        with self.assertRaises(FrozenInstanceError): actual.attack_departures = ()
        with self.assertRaises(TypeError): replace(actual, attack_departures=('enemy',))

    def test_departure_frame_cannot_name_unknown_repeated_or_archived_actor(self):
        source = scenario()
        for rows in ((NpcMagicAttackDeparture('other', True),), (NpcMagicAttackDeparture('enemy', True),) * 2):
            with self.assertRaisesRegex(ValueError, 'distinct live'):
                replace(source, scene_frames=(replace(source.initial_frame, attack_departures=rows),))
        positions = source.initial_frame.key.placements
        archived = frame(source.initial, placements=positions, live=('wizard', 'ally'))
        archived = replace(archived, attack_departures=(NpcMagicAttackDeparture('enemy', True),))
        with self.assertRaisesRegex(ValueError, 'distinct live'):
            replace(source, scene_frames=(*source.scene_frames, archived))

    def test_true_departure_requires_an_adjacent_zone_before_rng(self):
        from towr.domain.spatial_models import ZoneGraph
        from towr.domain.npc_magic_scene_models import NpcMagicZoneRange
        from towr.domain.ranged_weapon_profiles import RangedWeaponRange as Range
        source = scenario()
        initial = replace(source.initial, spatial_state=replace(source.initial.spatial_state,
            graph=ZoneGraph(source.initial.spatial_state.graph.zone_ids, ())))
        plan = replace(source.initial_frame.give_ground_plans[0], can_leave_zone=False,
            destination_zone_id=None, route=None, impossible_confirmed=True)
        first = replace(source.initial_frame, zone_ranges=tuple(NpcMagicZoneRange(z,
            Range.SHORT if z == 'arena' else Range.EXTREME) for z in initial.spatial_state.graph.zone_ids),
            give_ground_plans=(plan,), attack_departures=(NpcMagicAttackDeparture('enemy', True),))
        with self.assertRaisesRegex(ValueError, 'adjacent Zone'):
            replace(source, initial=initial, scene_frames=(first,))

    def test_no_rng_or_continuation_after_miscast(self):
        rng = Dice((9, 9, 9))
        with (patch('towr.engine.npc_magic_scenario_runner.end_npc_wound_turn', side_effect=AssertionError('no end')),
              patch('towr.engine.npc_magic_scenario_runner.prepare_npc_attack', side_effect=AssertionError('no attack'))):
            result = run(admitted(), rng)
        rng.exhausted()
        self.assertIs(result.unsupported.reason, Reason.MISCAST_PREPARATION)
        self.assertIsNotNone(result.current.pending_miscast)
        self.assertEqual(len(result.steps), 2)

    def test_unexpected_constructor_value_error_is_not_unsupported_or_retried(self):
        failure = ValueError('unexpected preparation bug'); rng = Dice((10,) * 3)
        with patch('towr.engine.npc_magic_scenario_runner.prepare_npc_attack', side_effect=failure) as prepare:
            with self.assertRaises(ValueError) as caught: run(admitted(), rng)
        self.assertIs(caught.exception, failure)
        self.assertEqual(prepare.call_count, 1); rng.exhausted()

    def test_action_rng_failure_propagates_same_exception_and_keeps_original_source(self):
        source = admitted(); before = deepcopy(source)
        failure = RuntimeError('RNG failed')
        class FailedDice:
            def randint(self, low, high):
                raise failure
        with self.assertRaises(RuntimeError) as caught: run(source, FailedDice())
        self.assertIs(caught.exception, failure)
        self.assertEqual(source, before)

    def test_base_exception_is_not_swallowed(self):
        class InterruptedDice:
            def randint(self, low, high): raise KeyboardInterrupt('stop')
        with self.assertRaises(KeyboardInterrupt): run(admitted(), InterruptedDice())

    def test_end_failure_is_not_hidden_by_a_pending_victory(self):
        source = replace(admitted(), activation_order=('ally', 'wizard', 'enemy'))
        rng = Dice((1, 2, 3, 10, 10, 10)); failure = ValueError('end failed')
        with patch('towr.engine.npc_magic_scenario_runner.end_npc_wound_turn', side_effect=failure):
            with self.assertRaises(ValueError) as caught: run(source, rng)
        self.assertIs(caught.exception, failure); rng.exhausted()

    def test_foreign_complete_executor_source_rejected_before_further_rng(self):
        from tests.unit.test_m8_npc_magic_scenario_result import Journal
        foreign = admitted()
        initial = replace(foreign.initial, champion_attack=replace(foreign.initial.champion_attack,
            daily_wounds=replace(foreign.initial.champion_attack.daily_wounds, day_id='other-day')))
        journal = Journal(replace(foreign, initial=initial))
        journal.start('ally')
        attack = journal.shot('ally', 'enemy')
        rng = Dice(())
        source = replace(admitted(), activation_order=('ally', 'wizard', 'enemy'))
        with patch('towr.engine.npc_magic_scenario_runner.execute_npc_roster_minion_attack', return_value=attack):
            with self.assertRaisesRegex(ValueError, 'another full source'): run(source, rng)
        self.assertEqual(rng.calls, 0)

    def test_foreign_request_id_with_same_before_state_is_rejected_before_rng(self):
        from towr.rules.npc_roster_turn_resolution import start_npc_roster_turn
        rng = Dice(())
        def shifted(request):
            return start_npc_roster_turn(replace(request, id=request.id + ':foreign'))
        with patch('towr.engine.npc_magic_scenario_runner.start_npc_roster_turn', side_effect=shifted):
            with self.assertRaisesRegex(ValueError, 'another full source'): run(admitted(), rng)
        self.assertEqual(rng.calls, 0)

    def test_final_result_constructor_failure_is_not_a_fallback_success(self):
        failure = ValueError('final result failed'); rng = Dice((9, 9, 9))
        with patch('towr.engine.npc_magic_scenario_runner.NpcMagicScenarioResult', side_effect=failure) as result:
            with self.assertRaises(ValueError) as caught: run(admitted(), rng)
        self.assertIs(caught.exception, failure)
        self.assertEqual(result.call_count, 1); rng.exhausted()

    def test_each_scheduler_phase_is_executed_once_per_real_turn(self):
        from towr.rules.npc_roster_turn_resolution import start_npc_roster_turn
        from towr.rules.npc_wound_turn_end import end_npc_wound_turn
        from towr.rules.npc_roster_minion_attack_resolution import execute_npc_roster_minion_attack
        from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
        with (patch('towr.engine.npc_magic_scenario_runner.start_npc_roster_turn', wraps=start_npc_roster_turn) as starts,
              patch('towr.engine.npc_magic_scenario_runner.end_npc_wound_turn', wraps=end_npc_wound_turn) as ends,
              patch('towr.engine.npc_magic_scenario_runner.execute_npc_roster_minion_attack', wraps=execute_npc_roster_minion_attack) as minion,
              patch('towr.engine.npc_magic_scenario_runner.execute_npc_champion_attack', wraps=execute_npc_champion_attack) as champion):
            run(replace(admitted(), max_rounds=1), Dice((10,) * 15))
        self.assertEqual((starts.call_count, ends.call_count, minion.call_count, champion.call_count), (3, 3, 1, 1))

    def test_public_terminal_check_keeps_active_turn_before_objective(self):
        from tests.unit.test_m8_npc_magic_scenario_result import victory
        journal = victory(order=('ally', 'wizard', 'enemy'))
        self.assertIsNone(npc_magic_terminal_outcome(journal.source, journal.steps[-2].after))
        self.assertIsNotNone(npc_magic_terminal_outcome(journal.source, journal.current))
        with self.assertRaises(TypeError): npc_magic_terminal_outcome(None, journal.current)


if __name__ == '__main__':
    unittest.main()
