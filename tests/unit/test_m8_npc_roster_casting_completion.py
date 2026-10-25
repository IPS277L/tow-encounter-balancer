from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import random
import unittest
from unittest.mock import patch

from tests.unit.test_m8_cowardly_flight_casting import CountingDice
from tests.unit.test_m8_cowardly_flight_casting_movement import movement_input, completions
from tests.unit.test_m8_npc_roster_casting import bound_request, change_injury
from tests.unit.test_m8_npc_champion_attack import request as attack_request
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.cowardly_flight_casting_completion_models import CowardlyFlightCastingCompletionRequest
from towr.domain.cowardly_flight_casting_result_models import CowardlyFlightCastingStatus as Status
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.magic_models import WizardMagicState
from towr.domain.npc_roster_casting_models import NpcRosterCastingRequest, NpcRosterCastingResult
from towr.domain.npc_roster_casting_completion_models import (
    NpcRosterCastingCompletionRequest as Request, NpcRosterCastingCompletionResult as Result,
)
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackRequest
from towr.domain.npc_roster_models import NpcRoster
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting, complete_cowardly_flight_casting
from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting, apply_npc_roster_casting_result
from towr.rules.npc_roster_casting_completion_resolution import apply_npc_roster_casting_completion as apply


def begin(source=None, state=None):
    bound = bound_request(source or movement_input())
    if state is not None:
        bound = replace(bound, state=state, casting=replace(bound.casting,
                        round_state=state.casting_round_state, spatial_state=state.casting_spatial_state,
                        magic_state=state.wizard.magic_state))
    rng = CountingDice([1, 2, 3])
    casting = execute_cowardly_flight_casting(bound.casting, rng)
    result = NpcRosterCastingResult(bound, casting)
    return bound, result, apply_npc_roster_casting_result(bound.state, result), rng.calls


def completion_request(state):
    pending = state.pending_movement
    movements, spatial = completions(pending)
    return Request(state, CowardlyFlightCastingCompletionRequest(pending, movements, spatial))


def finish(state, dice=None):
    request = completion_request(state)
    rng = CountingDice([1, 2, 3, 10, 10, 10] if dice is None else dice)
    raw = complete_cowardly_flight_casting(request.completion, rng)
    result = Result(request, raw)
    return result, apply(state, result), rng.calls


def change_equipment(state):
    return replace(state, roster=NpcRoster(tuple(
        replace(p, state=replace(p.state, holds_shield=True)) if p.state.actor_id == 'friend' else p
        for p in state.roster.participants)))


class NpcRosterCastingCompletionTests(unittest.TestCase):
    def test_first_phase_retains_full_pending_and_one_receipt_without_moving(self):
        bound, result, current, calls = begin()
        self.assertEqual(calls, 3)
        self.assertIs(current.pending_movement, result.casting)
        self.assertIs(current.pending_movement.status, Status.MOVEMENT_REQUIRED)
        self.assertEqual(current.roster, bound.state.roster)
        self.assertIs(current.spatial_state, bound.state.spatial_state)
        self.assertEqual(current.consumed_execution_ids, ('cast',))
        self.assertIs(current.round_state.active_turn.action_slots[0].execution,
                      result.casting.execution.slot.execution)
        self.assertEqual(current.round_state.completed_turn_entity_ids, ())
        self.assertIsNone(result.casting.willpower)

    def test_pending_blocks_both_casting_entries_and_bound_attack_before_rng(self):
        bound, _, current, _ = begin()
        with patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no RNG')):
            with self.assertRaisesRegex(ValueError, 'pending movement'):
                NpcRosterCastingRequest(current, bound.casting)
            with self.assertRaisesRegex(ValueError, 'pending movement'):
                prepare_npc_roster_casting(request_id='other', state=current, selected_zone_id='arena',
                    targets=(), facts=bound.casting.facts, policy=bound.casting.policy)
            with self.assertRaisesRegex(ValueError, 'pending movement'):
                NpcRosterChampionAttackRequest(current, attack_request())

    def test_completion_applies_conditions_positions_and_keeps_magic_round_and_history(self):
        _, _, current, _ = begin()
        result, after, calls = finish(current)
        self.assertEqual(calls, 6)
        self.assertIsNone(after.pending_movement)
        self.assertIsNone(after.pending_miscast)
        self.assertIs(after.wizard, current.wizard)
        self.assertIs(after.round_state, current.round_state)
        self.assertIs(after.consumed_execution_ids, current.consumed_execution_ids)
        self.assertEqual(after.spatial_state.gave_ground_entity_ids, ('second', 'first'))
        self.assertEqual(tuple(t.target_id for t in result.completion.casting.willpower.targets), ('second', 'first'))
        self.assertFalse(after.roster.participant('second').state.injury.conditions.has(Condition.BROKEN))
        self.assertTrue(after.roster.participant('first').state.injury.conditions.has(Condition.BROKEN))
        for actor in ('second', 'first'):
            self.assertEqual(after.spatial_state.placement_for(actor).zone_id, 'empty')
            self.assertFalse(after.roster.participant(actor).state.injury.defeated)
        for actor in ('wizard', 'friend', 'distant'):
            self.assertIs(after.roster.participant(actor), current.roster.participant(actor))

    def test_second_application_and_initial_action_replay_are_rejected(self):
        bound, initial, current, _ = begin()
        result, after, _ = finish(current)
        with self.assertRaisesRegex(ValueError, 'already consumed'):
            apply(after, result)
        with self.assertRaisesRegex(ValueError, 'already been consumed'):
            apply_npc_roster_casting_result(after, initial)
        with self.assertRaisesRegex(ValueError, 'already been consumed'):
            replace(bound, state=replace(after, round_state=bound.state.round_state))
        with self.assertRaisesRegex(ValueError, 'requires pending movement'):
            Request(after, result.source.completion)

    def test_stale_full_roster_and_history_are_rejected_even_if_targets_match(self):
        _, _, current, _ = begin()
        result, _, _ = finish(current)
        for state in (change_equipment(current), replace(current, consumed_execution_ids=('earlier', 'cast'))):
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, 'stale source'):
                apply(state, result)
        self.assertEqual(apply(deepcopy(current), deepcopy(result)), result.state)

    def test_foreign_pending_and_same_id_different_source_cannot_be_spliced(self):
        _, _, current, _ = begin()
        source = movement_input()
        other_source = replace(source, caster=replace(source.caster, id='other:definition'))
        _, _, other, _ = begin(other_source)
        request = completion_request(current)
        other_result, _, _ = finish(other)
        with self.assertRaisesRegex(ValueError, 'current pending'):
            replace(request, completion=other_result.source.completion)
        with self.assertRaisesRegex(ValueError, 'complete bound request'):
            Result(request, other_result.completion)

    def test_pending_must_match_actor_magic_round_spatial_targets_and_consumed_id(self):
        _, _, current, _ = begin()
        for changes in (
            {'wizard': replace(current.wizard, magic_state=WizardMagicState(1))},
            {'consumed_execution_ids': ()},
            {'spatial_state': replace(current.spatial_state, free_move_used_entity_ids=('wizard',))},
            {'wizard': replace(current.wizard, caster=replace(current.wizard.caster, id='other'))},
            {'round_state': replace(current.round_state, active_turn=None)},
        ):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, 'pending movement'):
                replace(current, **changes)
        with self.assertRaisesRegex(ValueError, 'target snapshot'):
            change_injury(current, 'first', ProfileInjuryState(0, 1, ConditionState((Condition.BROKEN,))))
        with self.assertRaises(TypeError):
            replace(current, pending_movement='pending')

    def test_completed_movement_cannot_bypass_initial_pending_application(self):
        bound, _, current, _ = begin()
        completed, _, _ = finish(current)
        with self.assertRaisesRegex(ValueError, 'roster completion boundary'):
            NpcRosterCastingResult(bound, completed.completion.casting)

    def test_wait_miscast_and_zero_potency_keep_their_existing_branches(self):
        source = movement_input()
        for magic, values, expected in (
            (WizardMagicState(), [1, 10, 10], Status.WAITING),
            (WizardMagicState(2), [9, 1, 10], Status.MISCAST_REQUIRED),
            (WizardMagicState(0, 3, 'lore:battle-magic', 3), [10, 10, 10], Status.SPELL_RESOLVED),
        ):
            bound = bound_request(replace(source, magic_state=magic))
            result = NpcRosterCastingResult(bound, execute_cowardly_flight_casting(bound.casting, CountingDice(values)))
            self.assertIs(result.casting.status, expected)
            self.assertIsNone(result.state.pending_movement)
            with self.assertRaisesRegex(ValueError, 'MOVEMENT_REQUIRED'):
                replace(result.state, pending_movement=result.casting)

    def test_projection_filters_archived_usage_and_completion_restores_full_history_order(self):
        bound = bound_request(movement_input())
        state = change_injury(bound.state, 'distant', ProfileInjuryState(1, 1, defeated=True))
        spatial = replace(state.spatial_state, gave_ground_entity_ids=('distant', 'friend'),
                          free_move_used_entity_ids=('distant', 'wizard'),
                          difficult_terrain_tested_entity_ids=('friend', 'distant'))
        state = replace(state, spatial_state=spatial,
                        round_state=replace(state.round_state, excluded_turn_entity_ids=('distant',)))
        self.assertEqual(state.casting_spatial_state.gave_ground_entity_ids, ('friend',))
        self.assertEqual(state.casting_spatial_state.free_move_used_entity_ids, ('wizard',))
        self.assertEqual(state.casting_spatial_state.difficult_terrain_tested_entity_ids, ('friend',))
        _, _, current, _ = begin(state=state)
        result, after, _ = finish(current)
        self.assertNotIn('distant', [p.entity_id for p in result.completion.casting.spatial_state.placements])
        self.assertEqual(after.spatial_state.gave_ground_entity_ids, ('distant', 'friend', 'second', 'first'))
        self.assertEqual(after.spatial_state.free_move_used_entity_ids, ('distant', 'wizard'))
        self.assertEqual(after.spatial_state.difficult_terrain_tested_entity_ids, ('friend', 'distant'))
        self.assertIs(after.spatial_state.placement_for('distant'), spatial.placement_for('distant'))
        self.assertIs(after.roster.participant('distant'), state.roster.participant('distant'))
        self.assertEqual(tuple(p.entity_id for p in after.spatial_state.placements),
                         tuple(p.entity_id for p in spatial.placements))
        self.assertEqual(after.round_state.excluded_turn_entity_ids, ('distant',))

    def test_archived_enemy_in_destination_does_not_inflict_broken(self):
        source = movement_input(enemy_destination=True)
        state = change_injury(bound_request(source).state, 'friend', ProfileInjuryState(1, 1, defeated=True))
        _, _, current, _ = begin(source, state)
        _, after, _ = finish(current, [1, 2, 3] * 2)
        for actor in ('second', 'first'):
            self.assertFalse(after.roster.participant(actor).state.injury.conditions.has(Condition.BROKEN))
        self.assertEqual(after.spatial_state.placement_for('friend').zone_id, 'empty')

    def test_once_per_round_usage_is_shared_with_future_casting(self):
        source = movement_input(both=False)
        source = replace(source, spatial_state=replace(source.spatial_state, gave_ground_entity_ids=('first',)))
        bound, _, current, _ = begin(source)
        _, after, _ = finish(current)
        self.assertEqual(after.spatial_state.gave_ground_entity_ids, ('first', 'second'))
        with self.assertRaisesRegex(ValueError, 'already gave ground'):
            replace(bound.casting, spatial_state=after.casting_spatial_state,
                    selected_zone_id='empty', targets=(bound.casting.targets[0],))

    def test_bound_models_are_frozen_typed_and_source_is_not_mutated(self):
        _, _, current, _ = begin()
        result, _, _ = finish(current)
        before = deepcopy(result.source)
        for obj in (result.source, result):
            self.assertFalse(hasattr(obj, '__dict__'))
            with self.assertRaises(FrozenInstanceError):
                setattr(obj, fields(obj)[0].name, None)
        for call in (lambda: Request(None, result.source.completion), lambda: Request(current, None),
                     lambda: Result(None, result.completion), lambda: Result(result.source, None),
                     lambda: apply(None, result), lambda: apply(current, None)):
            with self.assertRaises(TypeError):
                call()
        self.assertEqual(result.source, before)

    def test_pure_application_does_not_move_test_cast_or_modify_global_rng(self):
        _, _, current, _ = begin()
        result, _, _ = finish(current)
        before, global_rng = deepcopy(current), random.getstate()
        with patch('towr.rules.spatial_resolution.resolve_give_ground', side_effect=AssertionError('no move')), \
             patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no Test')), \
             patch('towr.engine.cowardly_flight_casting.execute_casting_attempt', side_effect=AssertionError('no cast')):
            self.assertEqual(apply(current, result), result.state)
        self.assertEqual(current, before)
        self.assertEqual(random.getstate(), global_rng)

    def test_rng_failure_keeps_current_pending_and_never_returns_partial_owner(self):
        _, _, current, _ = begin()
        request, before = completion_request(current), deepcopy(current)
        problem = RuntimeError('test RNG failed on second target')
        rng = CountingDice([])
        with patch.object(rng, 'randint', side_effect=[1, 2, 3, problem]):
            with self.assertRaises(RuntimeError) as caught:
                complete_cowardly_flight_casting(request.completion, rng)
        self.assertIs(caught.exception, problem)
        self.assertEqual(current, before)
        self.assertIsNotNone(current.pending_movement)


if __name__ == '__main__':
    unittest.main()
