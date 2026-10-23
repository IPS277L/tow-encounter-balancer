from dataclasses import replace
import unittest

from tests.unit.test_m8_cowardly_flight_casting import CountingDice
from tests.unit.test_m8_cowardly_flight_casting_movement import movement_input, movement_request
from towr.domain.condition_models import Condition
from towr.domain.cowardly_flight_casting_completion_models import CowardlyFlightCastingCompletionRequest
from towr.domain.cowardly_flight_casting_result_models import CowardlyFlightCastingStatus as Status
from towr.domain.spatial_models import ZoneConnection, ZoneGraph
from towr.engine.cowardly_flight_casting import (
    execute_cowardly_flight_casting, complete_cowardly_flight_casting,
    apply_cowardly_flight_casting_completion,
)
from towr.rules.cowardly_flight_resolution import complete_cowardly_flight_movement
from towr.rules.spatial_resolution import resolve_give_ground


def run_phases(source, target_dice):
    cast_rng = CountingDice([1, 2, 3])
    pending = execute_cowardly_flight_casting(source, cast_rng)
    spatial = pending.spatial_state
    movements = []
    for follow_up in pending.pending_movements:
        movement = resolve_give_ground(movement_request(pending, follow_up, spatial))
        movements.append(complete_cowardly_flight_movement(follow_up, movement))
        spatial = movement.state
    test_rng = CountingDice(target_dice)
    completion = complete_cowardly_flight_casting(
        CowardlyFlightCastingCompletionRequest(pending, tuple(movements), spatial), test_rng)
    current = apply_cowardly_flight_casting_completion(pending, completion)
    return pending, current, cast_rng.calls, test_rng.calls, completion


class CowardlyFlightCastingMovementIntegrationTests(unittest.TestCase):
    def test_two_targets_leave_zone_and_still_test_in_original_order(self):
        source = movement_input()
        pending, current, cast_calls, test_calls, completion = run_phases(source, [1, 2, 3, 10, 10, 10])
        self.assertIs(pending.status, Status.MOVEMENT_REQUIRED)
        self.assertIs(current.status, Status.SPELL_RESOLVED)
        self.assertEqual((cast_calls, test_calls), (3, 6))
        self.assertEqual(tuple(t.target_id for t in current.willpower.targets), ('second', 'first'))
        self.assertEqual(tuple(current.spatial_state.placement_for(t.actor_id).zone_id for t in current.targets), ('empty', 'empty'))
        self.assertFalse(current.targets[0].injury.conditions.has(Condition.BROKEN))
        self.assertTrue(current.targets[1].injury.conditions.has(Condition.BROKEN))
        for actor in ('wizard', 'friend', 'distant'):
            self.assertEqual(current.spatial_state.placement_for(actor), source.spatial_state.placement_for(actor))
        self.assertEqual(current.execution, pending.execution)
        self.assertEqual(current.round_state.active_turn, pending.round_state.active_turn)
        with self.assertRaisesRegex(ValueError, 'already consumed'):
            apply_cowardly_flight_casting_completion(current, completion)

    def test_one_target_cannot_move_but_both_are_affected(self):
        source = movement_input(both=False)
        source = replace(source, spatial_state=replace(source.spatial_state, gave_ground_entity_ids=('first',)))
        pending, current, cast_calls, test_calls, _ = run_phases(source, [10] * 6)
        self.assertEqual(tuple(f.target_id for f in pending.pending_movements), ('second',))
        self.assertEqual(current.spatial_state.placement_for('first').zone_id, 'arena')
        self.assertEqual(current.spatial_state.gave_ground_entity_ids, ('first', 'second'))
        self.assertEqual((cast_calls, test_calls), (3, 6))
        self.assertTrue(all(t.injury.conditions.has(Condition.BROKEN) for t in current.targets))

    def test_broken_from_enemy_destination_survives_resistance_and_keeps_its_trace(self):
        pending, current, _, _, _ = run_phases(movement_input(enemy_destination=True), [1, 2, 3] * 2)
        for movement, target in zip(current.willpower.completed_movements, current.willpower.targets):
            self.assertTrue(movement.resolution.entered_enemy_zone)
            self.assertEqual(movement.resolution.condition_application.source_rule_id, 'RULE-COMBAT-015:give-ground')
            self.assertTrue(target.resisted)
            self.assertTrue(target.state.conditions.has(Condition.BROKEN))
        self.assertTrue(all(not t.injury.defeated for t in current.targets))
        self.assertEqual(current.spell, pending.spell)

    def test_remote_caster_is_bound_as_movement_source_without_assuming_close_range(self):
        source = movement_input()
        spatial = replace(source.spatial_state,
                          graph=ZoneGraph(('arena', 'elsewhere', 'empty'), (
                              ZoneConnection('elsewhere', 'arena'), ZoneConnection('arena', 'empty'))),
                          placements=tuple(replace(p, zone_id='elsewhere') if p.entity_id == 'wizard' else p
                                           for p in source.spatial_state.placements))
        _, current, _, _, _ = run_phases(replace(source, spatial_state=spatial), [1, 2, 3] * 2)
        self.assertEqual(current.spatial_state.placement_for('wizard').zone_id, 'elsewhere')
        self.assertTrue(all(c.resolution.source_request.away_from_entity_id == 'wizard'
                            for c in current.willpower.completed_movements))

    def test_excluded_turn_does_not_remove_a_living_affected_target(self):
        source = movement_input()
        source = replace(source, round_state=replace(source.round_state, excluded_turn_entity_ids=('first',)))
        _, current, _, _, _ = run_phases(source, [1, 2, 3] * 2)
        self.assertEqual(tuple(t.target_id for t in current.willpower.targets), ('second', 'first'))
        self.assertEqual(current.spatial_state.placement_for('first').zone_id, 'empty')
        self.assertEqual(current.round_state.excluded_turn_entity_ids, ('first',))


if __name__ == '__main__':
    unittest.main()
