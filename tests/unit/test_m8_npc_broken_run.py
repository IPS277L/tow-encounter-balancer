from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import random
import unittest
from unittest.mock import patch

from tests.unit.test_m8_npc_broken_recover import request as recover_request
from tests.unit.test_m8_npc_roster_casting import change_injury, bound_request
from tests.unit.test_m8_npc_champion_attack import request as attack_request
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.magic_models import WizardMagicState
from towr.domain.movement_models import FreeMovementRequest, MovementSpeed
from towr.domain.npc_broken_run_models import NpcBrokenRunRequest as Request
from towr.domain.npc_broken_recover_models import NpcBrokenRecoverRequest
from towr.domain.npc_roster_casting_models import NpcRosterCastingRequest
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackRequest
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.spatial_models import ZoneConnection, ZoneGraph
from towr.domain.test_models import InlineProfile
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind, ManoeuvreKind
from towr.engine.npc_broken_run import execute_npc_broken_run as execute, apply_npc_broken_run_result as apply
from towr.rules.free_movement_resolution import resolve_free_movement
from towr.rules.run_action_execution import execute_run_action
from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting


def request(*, actor='wizard', speed=MovementSpeed.NORMAL, pool=0, active_casting=True):
    previous = recover_request(actor=actor, pool=pool, active_casting=active_casting,
                               extra_conditions=(Condition.STAGGERED, Condition.DRAINED))
    state = previous.state
    turn = state.round_state.active_turn
    slot = replace(turn.action_slots[0], declaration=CombatActionDeclaration(
        CombatActionKind.MANOEUVRE, manoeuvre=ManoeuvreKind.RUN))
    combat = replace(state.round_state, active_turn=replace(turn, action_slots=(slot,)))
    zones = ('arena', 'elsewhere', 'empty', 'road')
    graph = ZoneGraph(zones, (ZoneConnection('arena', 'elsewhere'), ZoneConnection('elsewhere', 'empty'),
                              ZoneConnection('arena', 'road'), ZoneConnection('road', 'elsewhere')))
    spatial = replace(state.spatial_state, graph=graph, placements=tuple(
        replace(p, zone_id='road') if speed is MovementSpeed.FAST and p.entity_id == 'first'
        else replace(p, zone_id='elsewhere') if actor != 'wizard' and p.entity_id == 'friend'
        else p for p in state.spatial_state.placements))
    state = replace(state, round_state=combat, spatial_state=spatial)
    route = ('road', 'elsewhere') if speed is MovementSpeed.FAST else ('elsewhere',)
    movement = FreeMovementRequest('broken-run:free-move', combat, spatial, actor, speed,
        state.roster.participant(actor).state.injury.conditions, route)
    return Request('broken-run', state, actor, movement, 'empty', (), False, False, True)


class NpcBrokenRunTests(unittest.TestCase):
    def test_full_free_move_and_one_run_reach_safety_and_keep_all_conditions(self):
        for speed in (MovementSpeed.NORMAL, MovementSpeed.FAST):
            with self.subTest(speed=speed):
                source = request(speed=speed)
                result = execute(source)
                after = apply(source.state, result)
                self.assertEqual(result.movement.traversed_zone_ids, source.movement.traversed_zone_ids)
                self.assertEqual(result.run.origin_zone_id, 'elsewhere')
                self.assertEqual(result.run.destination_zone_id, 'empty')
                self.assertEqual(after.spatial_state.placement_for('wizard').zone_id, 'empty')
                self.assertEqual(after.spatial_state.free_move_used_entity_ids, ('wizard',))
                self.assertIs(after.roster, source.state.roster)
                self.assertEqual(after.roster.participant('wizard').state.injury.conditions,
                                 ConditionState((Condition.BROKEN, Condition.STAGGERED, Condition.DRAINED)))
                self.assertEqual(after.consumed_execution_ids, ('broken-run',))
                self.assertIs(after.round_state.active_turn.action_slots[0].execution, result.run.slot.execution)
                self.assertEqual(after.round_state.completed_turn_entity_ids, ())

    def test_no_rng_test_recover_or_second_execution_occurs(self):
        source = request()
        with patch('towr.engine.npc_broken_run.resolve_free_movement', wraps=resolve_free_movement) as free, \
             patch('towr.engine.npc_broken_run.execute_run_action', wraps=execute_run_action) as run, \
             patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no Test')), \
             patch('towr.rules.recover_resolution.execute_recover_action', side_effect=AssertionError('no Recover')), \
             patch('random.Random.randint', side_effect=AssertionError('no RNG')):
            result = execute(source)
            self.assertEqual(apply(source.state, result), result.state)
        free.assert_called_once_with(source.movement)
        run.assert_called_once_with(source.run_request)

    def test_inactive_wizard_pool_is_preserved_without_a_skipped_die(self):
        source = request(pool=2, active_casting=False)
        result = execute(source)
        self.assertIsNone(result.interruption)
        self.assertIs(result.state.wizard, source.state.wizard)
        self.assertEqual(result.state.wizard.magic_state, WizardMagicState(2))

    def test_minion_run_does_not_change_the_wizards_active_casting(self):
        source = request(actor='first', pool=2)
        result = execute(source)
        self.assertIs(result.state.wizard, source.state.wizard)
        self.assertIsNone(result.interruption)
        self.assertTrue(result.state.roster.participant('first').state.injury.conditions.has(Condition.BROKEN))

    def test_active_wizard_adds_one_receipt_bound_die_and_retains_casting(self):
        source = request(pool=1)
        result = execute(source)
        after = result.state
        self.assertEqual(after.wizard.magic_state, WizardMagicState(2, 1, 'lore:battle-magic', 1))
        self.assertIsNone(after.pending_interruption)
        self.assertIs(result.interruption.action, result.run.slot.execution)
        self.assertEqual(result.interruption.miscast_pool.dice_added, 1)

    def test_triggered_miscast_stops_dispatch_and_does_not_roll_or_clear_pool(self):
        source = request(pool=2)
        result = execute(source)
        after = result.state
        self.assertIs(after.pending_interruption, result.interruption)
        self.assertEqual(after.wizard.magic_state, WizardMagicState(3, 1, 'lore:battle-magic', 1))
        self.assertEqual(after.pending_interruption.miscast_pool.roll_request.pool_dice_count, 3)
        self.assertEqual(after.pending_interruption.miscast_pool.roll_request.bonus_dice, 0)
        with self.assertRaisesRegex(ValueError, 'pending interruption'):
            NpcRosterCastingRequest(after, bound_request().casting)
        with self.assertRaisesRegex(ValueError, 'pending interruption'):
            NpcRosterChampionAttackRequest(after, attack_request())
        with self.assertRaisesRegex(ValueError, 'pending interruption'):
            prepare_npc_roster_casting(request_id='cast', state=after, selected_zone_id='empty', targets=(),
                facts=bound_request().casting.facts, policy=bound_request().casting.policy)
        with self.assertRaisesRegex(ValueError, 'pending continuation'):
            replace(source, state=after)

    def test_no_free_recover_is_available_after_spending_the_run_action(self):
        source = request()
        after = execute(source).state
        with self.assertRaisesRegex(ValueError, 'unexecuted standard Recover'):
            NpcBrokenRecoverRequest('recover', after, 'wizard', InlineProfile(3, 3), None, True, True)

    def test_unnecessary_run_when_free_move_already_reaches_safety_is_rejected(self):
        source = request()
        spatial = replace(source.state.spatial_state, placements=tuple(
            replace(p, zone_id='arena') if p.entity_id == 'distant' else p
            for p in source.state.spatial_state.placements))
        with self.assertRaisesRegex(ValueError, 'already reaches a safe Zone'):
            replace(source, state=replace(source.state, spatial_state=spatial),
                    movement=replace(source.movement, state=spatial))

    def test_fast_actor_cannot_spend_run_instead_of_using_its_full_free_move(self):
        source = request()
        with self.assertRaisesRegex(ValueError, 'full Normal/Fast'):
            replace(source, movement=replace(source.movement, speed=MovementSpeed.FAST))
        with self.assertRaisesRegex(ValueError, 'full Normal/Fast'):
            replace(source, movement=replace(source.movement, speed=MovementSpeed.SLOW))

    def test_obstacles_terrain_enemy_blockers_and_unsafe_destination_rejected(self):
        source = request()
        for changes in ({'run_crosses_obstacle': True}, {'run_crosses_difficult_terrain': True},
                        {'run_path_entity_ids': ('first',)}, {'run_destination_zone_id': 'arena'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(source, **changes)
        for changes in ({'crosses_obstacle': True}, {'crosses_difficult_terrain': True},
                        {'path_entity_ids': ('first',)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(source, movement=replace(source.movement, **changes))

    def test_reused_free_move_disconnected_route_and_run_too_far_rejected(self):
        source = request()
        for spatial in (replace(source.state.spatial_state, free_move_used_entity_ids=('wizard',)),
                        replace(source.state.spatial_state, graph=ZoneGraph(source.state.spatial_state.graph.zone_ids))):
            with self.assertRaises(ValueError):
                replace(source, state=replace(source.state, spatial_state=spatial),
                        movement=replace(source.movement, state=spatial))
        with self.assertRaisesRegex(ValueError, 'one extra adjacent Zone'):
            replace(source, run_destination_zone_id='missing')

    def test_source_round_conditions_speed_id_and_actor_cannot_be_spliced(self):
        source = request()
        for changes in ({'id': 'other'}, {'actor_conditions': ConditionState()},
                        {'state': replace(source.movement.state, gave_ground_entity_ids=('friend',))}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, 'complete current source'):
                replace(source, movement=replace(source.movement, **changes))
        with self.assertRaises(ValueError):
            replace(source, actor_id='friend')
        for condition in (Condition.PRONE, Condition.DEFENCELESS, Condition.BURDENED):
            injury = source.state.roster.participant('wizard').state.injury
            with self.assertRaisesRegex(ValueError, 'living Broken actor'):
                replace(source, state=change_injury(source.state, 'wizard', replace(injury,
                    conditions=injury.conditions.with_condition(condition))))

    def test_result_movement_receipt_and_interruption_are_bound_to_exact_source(self):
        source = request()
        result = execute(source)
        with self.assertRaisesRegex(ValueError, 'free movement differs'):
            replace(result, movement=replace(result.movement, request_id='other'))
        with self.assertRaisesRegex(ValueError, 'skipped Casting'):
            replace(result, interruption=None)
        with self.assertRaisesRegex(ValueError, 'bound action'):
            replace(result, run=replace(result.run,
                    applied_rule_ids=('RULE-COMBAT-014:run-action-execution',)))

    def test_result_replay_and_stale_unaffected_roster_or_history_are_rejected(self):
        source = request()
        result = execute(source)
        with self.assertRaisesRegex(ValueError, 'already consumed'):
            apply(result.state, result)
        for state in (replace(source.state, consumed_execution_ids=('other',)),
                      replace(source.state, roster=NpcRoster(tuple(
                          replace(p, state=replace(p.state, holds_shield=True)) if p.state.actor_id == 'friend' else p
                          for p in source.state.roster.participants)))):
            with self.assertRaisesRegex(ValueError, 'stale complete source'):
                apply(state, result)
        self.assertEqual(apply(deepcopy(source.state), deepcopy(result)), result.state)

    def test_models_are_frozen_and_path_input_is_copied(self):
        source = request()
        path = ['friend']
        source = replace(source, run_path_entity_ids=path)
        path.clear()
        self.assertEqual(source.run_path_entity_ids, ('friend',))
        for obj in (source, execute(source)):
            self.assertFalse(hasattr(obj, '__dict__'))
            with self.assertRaises(FrozenInstanceError):
                setattr(obj, fields(obj)[0].name, None)
        for changes in ({'state': None}, {'movement': None}, {'fastest_route_confirmed': 1},
                        {'run_path_entity_ids': set()}, {'id': None}):
            with self.assertRaises(TypeError):
                replace(source, **changes)
        with self.assertRaises(ValueError):
            replace(source, fastest_route_confirmed=False)

    def test_inputs_global_rng_and_unaffected_participants_remain_unchanged(self):
        source = request()
        before, rng_state = deepcopy(source), random.getstate()
        result = execute(source)
        self.assertEqual(source, before)
        self.assertEqual(random.getstate(), rng_state)
        self.assertIs(result.state.roster, source.state.roster)
        for actor in ('friend', 'second', 'first', 'distant'):
            self.assertIs(result.state.spatial_state.placement_for(actor), source.state.spatial_state.placement_for(actor))

    def test_run_failure_does_not_publish_partial_free_move_or_consumed_receipt(self):
        source = request()
        before = deepcopy(source)
        problem = RuntimeError('Run execution failed')
        with patch('towr.engine.npc_broken_run.execute_run_action', side_effect=problem):
            with self.assertRaises(RuntimeError) as caught:
                execute(source)
        self.assertIs(caught.exception, problem)
        self.assertEqual(source, before)
        self.assertEqual(source.state.spatial_state.free_move_used_entity_ids, ())
        self.assertEqual(source.state.consumed_execution_ids, ())

    def test_public_boundaries_reject_untyped_arguments(self):
        source = request()
        result = execute(source)
        for call in (lambda: execute(None), lambda: apply(None, result), lambda: apply(source.state, None),
                     lambda: replace(result, source=None), lambda: replace(result, movement=None),
                     lambda: replace(result, run=None)):
            with self.assertRaises(TypeError):
                call()


if __name__ == '__main__':
    unittest.main()
