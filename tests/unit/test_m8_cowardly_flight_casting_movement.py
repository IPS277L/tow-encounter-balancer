from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import random
import unittest
from unittest.mock import patch

from tests.unit.test_m8_cowardly_flight_casting import CountingDice, MODULE
from tests.unit.test_m8_cowardly_flight_casting_models import casting_input
from tests.unit.test_m8_npc_roster_casting import bound_request
from towr.domain.condition_models import Condition
from towr.domain.cowardly_flight_casting_completion_models import (
    CowardlyFlightCastingCompletionRequest as CompletionRequest,
    CowardlyFlightCastingCompletionResult as CompletionResult,
)
from towr.domain.cowardly_flight_casting_result_models import CowardlyFlightCastingStatus as Status
from towr.domain.magic_models import WizardMagicState
from towr.domain.resolution_models import GiveGroundResolutionRequest
from towr.domain.spatial_models import ZoneConnection, ZoneGraph
from towr.engine.cowardly_flight_casting import (
    execute_cowardly_flight_casting as execute,
    complete_cowardly_flight_casting as complete,
    apply_cowardly_flight_casting_completion as apply,
)
from towr.rules.cowardly_flight_resolution import complete_cowardly_flight_movement
from towr.rules.spatial_resolution import resolve_give_ground


def movement_input(*, both=True, enemy_destination=False):
    source = casting_input()
    spatial = replace(source.spatial_state,
                      graph=ZoneGraph(('arena', 'elsewhere', 'empty'), (
                          ZoneConnection('arena', 'empty'), ZoneConnection('arena', 'elsewhere'))))
    if enemy_destination:
        spatial = replace(spatial, placements=tuple(
            replace(p, zone_id='empty') if p.entity_id == 'friend' else p for p in spatial.placements))
    return replace(source, spatial_state=spatial,
                   targets=tuple(replace(t, can_give_ground=(both or index == 0))
                                 for index, t in enumerate(source.targets)))


def pending(source=None):
    return execute(source or movement_input(), CountingDice([1, 2, 3]))


def movement_request(casting, follow_up, spatial):
    target = next(t for t in casting.source.targets if t.actor_id == follow_up.target_id)
    return GiveGroundResolutionRequest(
        follow_up.request, spatial, target.actor_id, 'empty', target.injury.conditions,
        away_from_entity_id=casting.source.actor_id)


def completions(casting):
    spatial = casting.spatial_state
    values = []
    for follow_up in casting.pending_movements:
        movement = resolve_give_ground(movement_request(casting, follow_up, spatial))
        values.append(complete_cowardly_flight_movement(follow_up, movement))
        spatial = movement.state
    return tuple(values), spatial


def completion_request(casting=None):
    casting = casting or pending()
    movements, spatial = completions(casting)
    return CompletionRequest(casting, movements, spatial)


class CowardlyFlightCastingMovementTests(unittest.TestCase):
    def test_casting_consumes_one_slot_and_stops_before_all_target_tests(self):
        rng = CountingDice([1, 2, 3])
        result = execute(movement_input(), rng)
        self.assertEqual(rng.calls, 3)
        self.assertIs(result.status, Status.MOVEMENT_REQUIRED)
        self.assertEqual(tuple(f.target_id for f in result.pending_movements), ('second', 'first'))
        self.assertIsNone(result.willpower)
        self.assertEqual(result.magic_state, WizardMagicState())
        self.assertTrue(result.round_state.active_turn.action_slots[0].executed)
        self.assertEqual(result.spatial_state, result.source.spatial_state)
        self.assertEqual(tuple(t.injury for t in result.targets), tuple(t.injury for t in result.source.targets))

    def test_wait_and_miscast_do_not_create_movements(self):
        source = movement_input()
        for magic, dice, status in (
            (WizardMagicState(), [1, 10, 10], Status.WAITING),
            (WizardMagicState(2), [9, 1, 10], Status.MISCAST_REQUIRED),
        ):
            result = execute(replace(source, magic_state=magic), CountingDice(dice))
            self.assertIs(result.status, status)
            self.assertEqual(result.pending_movements, ())
            with self.assertRaisesRegex(ValueError, 'pending movement'):
                CompletionRequest(result, (), result.spatial_state)

    def test_zero_potency_does_not_require_movement_or_willpower(self):
        source = replace(movement_input(), magic_state=WizardMagicState(0, 3, 'lore:battle-magic', 3))
        result = execute(source, CountingDice([10, 10, 10]))
        self.assertIs(result.status, Status.SPELL_RESOLVED)
        self.assertEqual(result.pending_movements, ())
        self.assertEqual(result.willpower.targets, ())

    def test_known_round_usage_cannot_be_claimed_as_available(self):
        source = movement_input()
        spatial = replace(source.spatial_state, gave_ground_entity_ids=('second',))
        with self.assertRaisesRegex(ValueError, 'already gave ground'):
            replace(source, spatial_state=spatial)
        source = replace(source, targets=(replace(source.targets[0], can_give_ground=False), source.targets[1]))
        result = pending(replace(source, spatial_state=spatial))
        self.assertEqual(tuple(f.target_id for f in result.pending_movements), ('first',))

    def test_completion_uses_only_ordered_target_tests_without_casting_or_movement_again(self):
        request = completion_request()
        rng = CountingDice([1, 2, 3, 10, 10, 10])
        with patch(MODULE + 'execute_casting_attempt') as casting:
            result = complete(request, rng)
        casting.assert_not_called()
        self.assertEqual(rng.calls, 6)
        self.assertIs(result.casting.status, Status.SPELL_RESOLVED)
        self.assertEqual(tuple(t.target_id for t in result.casting.willpower.targets), ('second', 'first'))
        self.assertTrue(result.casting.willpower.targets[0].resisted)
        self.assertFalse(result.casting.willpower.targets[1].resisted)
        self.assertEqual(result.casting.round_state, request.pending.round_state)
        self.assertEqual(result.casting.magic_state, request.pending.magic_state)
        self.assertEqual(result.casting.spatial_state.gave_ground_entity_ids, ('second', 'first'))
        self.assertIn('RULE-COMBAT-015:give-ground', result.casting.willpower.applied_rule_ids)

    def test_successful_resistance_preserves_broken_from_enemy_destination(self):
        request = completion_request(pending(movement_input(enemy_destination=True)))
        result = complete(request, CountingDice([1, 2, 3, 1, 2, 3]))
        for target in result.casting.willpower.targets:
            self.assertTrue(target.resisted)
            self.assertTrue(target.state.conditions.has(Condition.BROKEN))
            self.assertIsNone(target.condition_application)

    def test_failed_resistance_marks_broken_as_already_present_after_movement(self):
        request = completion_request(pending(movement_input(enemy_destination=True)))
        result = complete(request, CountingDice([10] * 6))
        self.assertTrue(all(t.condition_application.was_already_present for t in result.casting.willpower.targets))

    def test_existing_conditions_and_independent_usage_survive_completion(self):
        source = movement_input(both=False)
        injury = source.targets[0].injury
        injury = replace(injury, conditions=injury.conditions.with_condition(Condition.STAGGERED).with_condition(Condition.DRAINED))
        source = replace(source, targets=(replace(source.targets[0], injury=injury), source.targets[1]),
                         spatial_state=replace(source.spatial_state, gave_ground_entity_ids=('distant',),
                                               free_move_used_entity_ids=('wizard',),
                                               difficult_terrain_tested_entity_ids=('first',)))
        result = complete(completion_request(pending(source)), CountingDice([1, 2, 3, 10, 10, 10])).casting
        self.assertEqual(result.targets[0].injury, injury)
        self.assertEqual(result.spatial_state.gave_ground_entity_ids, ('distant', 'second'))
        self.assertEqual(result.spatial_state.free_move_used_entity_ids, ('wizard',))
        self.assertEqual(result.spatial_state.difficult_terrain_tested_entity_ids, ('first',))

    def test_missing_duplicate_extra_and_reordered_movements_are_rejected(self):
        request = completion_request()
        values = request.movement_completions
        for movements in ((), values[:1], values[::-1], (*values, values[0]), (values[0], values[0])):
            with self.subTest(movements=movements), self.assertRaises(ValueError):
                replace(request, movement_completions=movements)

    def test_stale_initial_or_final_spatial_history_is_rejected(self):
        request = completion_request()
        with self.assertRaises(ValueError):
            replace(request, spatial_state_after_movements=request.pending.spatial_state)
        changed = replace(request.pending.source.spatial_state, free_move_used_entity_ids=('wizard',))
        other = replace(request.pending, source=replace(request.pending.source, spatial_state=changed))
        with self.assertRaises(ValueError):
            replace(request, pending=other)

    def test_movement_requires_full_source_caster_and_conditions(self):
        request = completion_request()
        first = request.movement_completions[0]
        movement = first.resolution
        wrong_conditions = movement.source_request.mover_conditions.with_condition(Condition.STAGGERED)
        changes = (replace(movement, source_request=None),
                   replace(movement, source_request=replace(movement.source_request, away_from_entity_id=None)),
                   resolve_give_ground(replace(movement.source_request, mover_conditions=wrong_conditions)))
        for changed in changes:
            with self.subTest(movement=changed), self.assertRaises(ValueError):
                replace(request, movement_completions=(replace(first, resolution=changed), request.movement_completions[1]))

    def test_forged_illegal_routes_and_trace_are_rejected_before_willpower(self):
        request = completion_request()
        first = request.movement_completions[0]
        movement = first.resolution
        for changes in ({'crosses_obstacle': True}, {'crosses_difficult_terrain': True},
                        {'path_entity_ids': ('wizard',)}):
            forged = replace(movement, source_request=replace(movement.source_request, **changes))
            with self.assertRaises(ValueError):
                replace(request, movement_completions=(replace(first, resolution=forged), request.movement_completions[1]))
        forged = replace(movement, applied_rule_ids=(movement.source.rule_id,))
        with self.assertRaises(ValueError):
            replace(request, movement_completions=(replace(first, resolution=forged), request.movement_completions[1]))

    def test_route_towards_caster_cannot_be_confirmed_even_with_forged_source(self):
        source = movement_input(both=False)
        spatial = replace(source.spatial_state, placements=tuple(
            replace(p, zone_id='empty') if p.entity_id == 'wizard' else p for p in source.spatial_state.placements))
        cast = pending(replace(source, spatial_state=spatial))
        follow_up = cast.pending_movements[0]
        movement = resolve_give_ground(replace(movement_request(cast, follow_up, spatial), away_from_entity_id=None))
        movement = replace(movement, source_request=replace(movement.source_request, away_from_entity_id='wizard'))
        with self.assertRaisesRegex(ValueError, 'away from the caster'):
            CompletionRequest(cast, (complete_cowardly_flight_movement(follow_up, movement),), movement.state)

    def test_pending_phase_and_completed_result_cannot_skip_required_movements(self):
        cast = pending()
        with self.assertRaises(TypeError):
            replace(cast, status=Status.SPELL_RESOLVED)
        complete_result = complete(completion_request(cast), CountingDice([1, 2, 3, 10, 10, 10]))
        with self.assertRaises(ValueError):
            replace(cast, willpower=complete_result.casting.willpower)
        with self.assertRaises(ValueError):
            replace(complete_result.casting, willpower=replace(complete_result.casting.willpower, completed_movements=()))
        with self.assertRaises(ValueError):
            CompletionRequest(complete_result.casting, (), complete_result.casting.spatial_state)

    def test_apply_is_pure_source_bound_and_rejects_second_consumption(self):
        request = completion_request()
        result = complete(request, CountingDice([1, 2, 3, 10, 10, 10]))
        before, rng_state = deepcopy(request), random.getstate()
        with patch(MODULE + 'execute_casting_attempt') as casting, patch(MODULE + 'resolve_cowardly_flight_willpower_batch') as willpower:
            current = apply(request.pending, result)
        casting.assert_not_called()
        willpower.assert_not_called()
        self.assertEqual(request, before)
        self.assertEqual(random.getstate(), rng_state)
        with self.assertRaisesRegex(ValueError, 'already consumed'):
            apply(current, result)
        other = pending(replace(movement_input(), id='other'))
        with self.assertRaisesRegex(ValueError, 'different current'):
            apply(other, result)

    def test_source_completion_models_are_typed_frozen_and_copy_lists(self):
        request = completion_request()
        movements = list(request.movement_completions)
        copied = replace(request, movement_completions=movements)
        movements.clear()
        self.assertEqual(copied, request)
        result = complete(request, CountingDice([1, 2, 3, 10, 10, 10]))
        for model, field in ((request, 'pending'), (result, 'casting')):
            self.assertFalse(hasattr(model, '__dict__'))
            with self.assertRaises(FrozenInstanceError):
                setattr(model, field, None)
        for field in ('pending', 'movement_completions', 'spatial_state_after_movements'):
            with self.assertRaises(TypeError):
                replace(request, **{field: None})
        with self.assertRaises(TypeError):
            CompletionResult(None, result.casting)
        with self.assertRaises(TypeError):
            complete(None, CountingDice([]))

    def test_full_completion_source_cannot_be_replaced_by_equal_ids(self):
        request = completion_request()
        result = complete(request, CountingDice([1, 2, 3, 10, 10, 10]))
        source = replace(request.pending.source, caster=replace(request.pending.source.caster, id='another-profile'))
        other_request = completion_request(pending(source))
        with self.assertRaisesRegex(ValueError, 'original Casting phases'):
            replace(result, source=other_request)

    def test_willpower_failure_preserves_pending_and_propagates_without_retry(self):
        request = completion_request()
        before = deepcopy(request)
        problem = RuntimeError('Willpower unavailable')
        rng = CountingDice([])
        with patch(MODULE + 'resolve_cowardly_flight_willpower_batch', side_effect=problem) as call:
            with self.assertRaises(RuntimeError) as caught:
                complete(request, rng)
        self.assertIs(caught.exception, problem)
        call.assert_called_once()
        self.assertEqual(rng.calls, 0)
        self.assertEqual(request, before)

    def test_roster_boundary_still_rejects_movement_before_casting_rng(self):
        bound = bound_request()
        casting = replace(bound.casting, targets=tuple(replace(t, can_give_ground=True) for t in bound.casting.targets))
        with self.assertRaisesRegex(ValueError, 'roster does not yet support'):
            replace(bound, casting=casting)


if __name__ == '__main__':
    unittest.main()
