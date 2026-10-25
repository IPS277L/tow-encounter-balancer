from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import random
import unittest
from unittest.mock import patch

from tests.unit.test_m8_npc_roster_casting import bound_request, change_injury
from tests.unit.test_m8_cowardly_flight_casting import CountingDice
from tests.unit.test_m8_npc_champion_attack import request as attack_request
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.magic_models import WizardMagicState
from towr.domain.movement_models import FreeMovementRequest, MovementSpeed
from towr.domain.npc_broken_recover_models import NpcBrokenRecoverRequest as Request
from towr.domain.npc_roster_casting_models import NpcRosterCastingRequest
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackRequest
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.spatial_models import ZoneConnection, ZoneGraph
from towr.domain.test_models import InlineProfile
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundState, CombatSide, CombatTurnStartRequest,
)
from towr.engine.npc_broken_recover import execute_npc_broken_recover as execute, apply_npc_broken_recover_result as apply
from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting
from towr.rules.free_movement_resolution import resolve_free_movement
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.turn_resolution import start_combat_turn, reserve_combat_action_slot


def request(*, actor='wizard', safe=False, active_casting=True, pool=0, extra_conditions=()):
    state = bound_request().state
    conditions = ConditionState((Condition.BROKEN, *extra_conditions))
    injury = replace(state.roster.participant(actor).state.injury, conditions=conditions)
    state = change_injury(state, actor, injury)
    side = state.roster.participant(actor).state.side
    other = next(s for s in CombatSide if s is not side)
    combat = CombatRoundState(3, state.roster.turn_participants, side_order=(side, other))
    combat = start_combat_turn(CombatTurnStartRequest('start:broken', combat, actor)).state
    combat = reserve_combat_action_slot(CombatActionSlotRequest(
        'slot:broken', combat, actor, CombatActionDeclaration(CombatActionKind.RECOVER), ActionSlotGrant.STANDARD)).state
    spatial = replace(state.spatial_state, graph=ZoneGraph(('arena', 'empty', 'elsewhere'), (
        ZoneConnection('arena', 'empty'), ZoneConnection('arena', 'elsewhere'), ZoneConnection('empty', 'elsewhere'))),
        placements=tuple(replace(p, zone_id='empty') if safe and p.entity_id == actor else p
                         for p in state.spatial_state.placements))
    magic = WizardMagicState(pool, 1, 'lore:battle-magic', 1) if active_casting else WizardMagicState(pool)
    state = replace(state, round_state=combat, spatial_state=spatial,
                    wizard=replace(state.wizard, magic_state=magic))
    movement = None if safe else FreeMovementRequest('broken:free-move', combat, spatial, actor,
        MovementSpeed.NORMAL, conditions, ('empty',))
    return Request('broken', state, actor, InlineProfile(3, 3), movement, True, True)


class NpcBrokenRecoverTests(unittest.TestCase):
    def test_moves_then_recovers_once_and_registers_one_skipped_casting_die(self):
        source = request(extra_conditions=(Condition.STAGGERED, Condition.DRAINED))
        rng = CountingDice([1, 10, 10])
        with patch('towr.engine.npc_broken_recover.resolve_free_movement',
                   wraps=resolve_free_movement) as move:
            result = execute(source, rng)
        self.assertEqual(move.call_count, 1)
        after = apply(source.state, result)
        self.assertEqual(rng.calls, 3)
        self.assertEqual(after.spatial_state.placement_for('wizard').zone_id, 'empty')
        self.assertEqual(after.spatial_state.free_move_used_entity_ids, ('wizard',))
        self.assertEqual(after.roster.participant('wizard').state.injury.conditions,
                         ConditionState((Condition.STAGGERED, Condition.DRAINED)))
        self.assertEqual(after.wizard.magic_state, WizardMagicState(1, 1, 'lore:battle-magic', 1))
        self.assertIsNone(after.pending_interruption)
        self.assertEqual(after.consumed_execution_ids, ('broken',))
        self.assertIs(after.round_state.active_turn.action_slots[0].execution, result.recover.slot.execution)
        self.assertEqual(after.round_state.completed_turn_entity_ids, ())

    def test_failed_recover_keeps_broken_but_spends_action_and_adds_die(self):
        source = request()
        result = execute(source, CountingDice([10, 10, 10]))
        self.assertFalse(result.recover.resolution.removed)
        self.assertTrue(result.state.roster.participant('wizard').state.injury.conditions.has(Condition.BROKEN))
        self.assertEqual(result.state.wizard.magic_state.miscast_dice, 1)
        self.assertTrue(result.state.round_state.active_turn.action_slots[0].executed)

    def test_already_safe_actor_recovers_without_spending_free_move(self):
        source = request(safe=True)
        with patch('towr.engine.npc_broken_recover.resolve_free_movement', side_effect=AssertionError('no move')):
            result = execute(source, CountingDice([1, 2, 3]))
        self.assertIsNone(result.movement)
        self.assertIs(result.state.spatial_state, source.state.spatial_state)
        self.assertEqual(result.state.spatial_state.free_move_used_entity_ids, ())

    def test_slow_actor_can_use_ordinary_free_move_and_recover_without_run(self):
        source = request()
        source = replace(source, movement=replace(source.movement, speed=MovementSpeed.SLOW))
        result = execute(source, CountingDice([1, 2, 3]))
        self.assertEqual(result.state.spatial_state.placement_for('wizard').zone_id, 'empty')
        self.assertFalse(result.state.roster.participant('wizard').state.injury.conditions.has(Condition.BROKEN))

    def test_minion_turn_does_not_interrupt_wizards_casting(self):
        source = request(actor='first', pool=2)
        result = execute(source, CountingDice([1, 2, 3]))
        self.assertIsNone(result.interruption)
        self.assertIs(result.state.wizard, source.state.wizard)
        self.assertEqual(result.state.roster.participant('wizard'), source.state.roster.participant('wizard'))

    def test_wizard_without_active_casting_keeps_pool_without_removal_or_increase(self):
        source = request(pool=2, active_casting=False)
        result = execute(source, CountingDice([1, 2, 3]))
        self.assertIsNone(result.interruption)
        self.assertEqual(result.state.wizard.magic_state, WizardMagicState(2))

    def test_ordinary_recover_nines_do_not_increase_pool_beyond_one_skipped_die(self):
        source = request(pool=1)
        result = execute(source, CountingDice([9, 9, 9]))
        self.assertEqual(result.state.wizard.magic_state.miscast_dice, 2)
        self.assertIsNone(result.state.pending_interruption)
        self.assertEqual(result.interruption.miscast_pool.dice_added, 1)

    def test_triggered_miscast_retains_full_skip_receipt_and_blocks_all_bound_dispatch(self):
        source = request(pool=2)
        result = execute(source, CountingDice([1, 2, 3]))
        after = result.state
        self.assertIs(after.pending_interruption, result.interruption)
        self.assertEqual(after.wizard.magic_state, WizardMagicState(3, 1, 'lore:battle-magic', 1))
        self.assertEqual(after.pending_interruption.miscast_pool.roll_request.pool_dice_count, 3)
        self.assertEqual(after.pending_interruption.miscast_pool.roll_request.bonus_dice, 0)
        self.assertIs(after.pending_interruption.action, result.recover.slot.execution)
        with patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no RNG')):
            with self.assertRaisesRegex(ValueError, 'pending interruption'):
                NpcRosterCastingRequest(after, bound_request().casting)
            with self.assertRaisesRegex(ValueError, 'pending interruption'):
                prepare_npc_roster_casting(request_id='cast', state=after, selected_zone_id='empty', targets=(),
                    facts=bound_request().casting.facts, policy=bound_request().casting.policy)
            with self.assertRaisesRegex(ValueError, 'pending interruption'):
                NpcRosterChampionAttackRequest(after, attack_request())
            with self.assertRaisesRegex(ValueError, 'pending continuation'):
                replace(source, state=after)

    def test_pending_interruption_cannot_be_removed_or_separated_from_round_magic_history(self):
        result = execute(request(pool=2), CountingDice([10] * 3))
        after = result.state
        for changes in ({'pending_interruption': None}, {'consumed_execution_ids': ()},
                        {'wizard': replace(after.wizard, magic_state=WizardMagicState())},
                        {'round_state': replace(after.round_state, active_turn=None)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(after, **changes)
        with self.assertRaises(TypeError):
            replace(after, pending_interruption='pending')
        accumulated = execute(request(), CountingDice([1, 2, 3])).interruption
        with self.assertRaisesRegex(ValueError, 'pending interruption'):
            replace(after, pending_interruption=accumulated)
        skip = after.pending_interruption
        roll = skip.miscast_pool.roll_request
        with self.assertRaisesRegex(ValueError, 'pending interruption'):
            replace(after, pending_interruption=replace(skip, miscast_pool=replace(
                skip.miscast_pool, roll_request=replace(roll, target_id='other'))))

    def test_unsafe_recover_wait_and_unnecessary_movement_are_rejected(self):
        source = request()
        with self.assertRaisesRegex(ValueError, 'safe Zone'):
            replace(source, movement=None)
        safe = request(safe=True)
        with self.assertRaisesRegex(ValueError, 'already safe'):
            replace(safe, movement=replace(source.movement, state=safe.state.spatial_state,
                                          traversed_zone_ids=('elsewhere',)))
        for name in ('fastest_route_confirmed', 'underlying_cause_allows_removal'):
            with self.assertRaises(ValueError):
                replace(source, **{name: False})
            with self.assertRaises(TypeError):
                replace(source, **{name: 1})

    def test_enemy_destination_and_route_past_first_safe_zone_are_rejected(self):
        source = request()
        with self.assertRaisesRegex(ValueError, 'first safe Zone'):
            replace(source, movement=replace(source.movement, traversed_zone_ids=('elsewhere',)))
        with self.assertRaisesRegex(ValueError, 'first safe Zone'):
            replace(source, movement=replace(source.movement, speed=MovementSpeed.FAST,
                    traversed_zone_ids=('empty', 'elsewhere')))

    def test_fast_free_move_crosses_unsafe_intermediate_zone_and_stops_when_safe(self):
        source = request()
        source = replace(source, movement=replace(source.movement, speed=MovementSpeed.FAST,
                         traversed_zone_ids=('elsewhere', 'empty')))
        result = execute(source, CountingDice([1, 2, 3]))
        self.assertEqual(result.movement.traversed_zone_ids, ('elsewhere', 'empty'))
        self.assertEqual(result.state.spatial_state.free_move_used_entity_ids, ('wizard',))

    def test_supported_wound_is_retained_and_restrictions_are_rejected(self):
        source = request()
        for roll, supported in ((6, True), (10, False)):
            attack = execute_npc_champion_attack(attack_request(), CountingDice([1, 2, 10, 10, 10, 10, roll]))
            injury = attack.resolution.target_state
            injury = replace(injury, conditions=injury.conditions.with_condition(Condition.BROKEN))
            state = change_injury(source.state, 'wizard', injury)
            movement = replace(source.movement, actor_conditions=injury.conditions)
            if supported:
                result = execute(replace(source, state=state, movement=movement), CountingDice([1, 2, 3]))
                after = result.state.roster.participant('wizard').state.injury
                self.assertEqual(after.wounds, injury.wounds)
                self.assertEqual(after.active_wound_effects, injury.active_wound_effects)
                self.assertTrue(after.conditions.has(Condition.DRAINED))
            else:
                with self.assertRaises(ValueError):
                    replace(source, state=state, movement=movement)

    def test_obstacles_terrain_enemy_path_and_reused_free_movement_rejected_before_rng(self):
        source = request()
        for changes in ({'crosses_obstacle': True}, {'crosses_difficult_terrain': True},
                        {'path_entity_ids': ('first',)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(source, movement=replace(source.movement, **changes))
        spatial = replace(source.state.spatial_state, free_move_used_entity_ids=('wizard',))
        with self.assertRaisesRegex(ValueError, 'unavailable free movement'):
            replace(source, state=replace(source.state, spatial_state=spatial),
                    movement=replace(source.movement, state=spatial))

    def test_wrong_actor_snapshot_route_id_and_executed_slot_are_rejected(self):
        source = request()
        for changes in ({'id': 'other:free'}, {'actor_conditions': ConditionState()},
                        {'state': replace(source.movement.state, gave_ground_entity_ids=('first',))}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, 'complete current source'):
                replace(source, movement=replace(source.movement, **changes))
        with self.assertRaisesRegex(ValueError, 'active actor'):
            replace(source, actor_id='first', state=change_injury(source.state, 'first', replace(
                source.state.roster.participant('first').state.injury,
                conditions=ConditionState((Condition.BROKEN,)))))
        result = execute(source, CountingDice([1, 2, 3]))
        with self.assertRaises(ValueError):
            replace(source, state=result.state)

    def test_replay_and_stale_unaffected_participant_are_rejected(self):
        source = request()
        result = execute(source, CountingDice([1, 2, 3]))
        with self.assertRaisesRegex(ValueError, 'already consumed'):
            apply(result.state, result)
        changed = replace(source.state, roster=NpcRoster(tuple(
            replace(p, state=replace(p.state, holds_shield=True)) if p.state.actor_id == 'friend' else p
            for p in source.state.roster.participants)))
        with self.assertRaisesRegex(ValueError, 'stale complete source'):
            apply(changed, result)
        self.assertEqual(apply(deepcopy(source.state), deepcopy(result)), result.state)

    def test_result_rejects_spliced_movement_profile_and_interruption(self):
        source = request()
        result = execute(source, CountingDice([1, 2, 3]))
        with self.assertRaisesRegex(ValueError, 'Broken route'):
            replace(result, movement=replace(result.movement, request_id='other'))
        with self.assertRaisesRegex(ValueError, 'Broken route'):
            replace(result, movement=replace(result.movement,
                    applied_rule_ids=(result.movement.rule_id,)))
        with self.assertRaisesRegex(ValueError, 'complete Broken request'):
            replace(result, source=replace(source, willpower_profile=InlineProfile(3, 4)))
        with self.assertRaisesRegex(ValueError, 'skipped Casting'):
            replace(result, interruption=None)
        test = result.recover.resolution.test_result
        with self.assertRaises(ValueError):
            replace(result, recover=replace(result.recover, resolution=replace(result.recover.resolution,
                test_result=replace(test, trace=replace(test.trace, initial_values=(2, 2, 2))))))

    def test_wrong_conditions_and_death_are_rejected(self):
        source = request()
        for conditions in (ConditionState(), ConditionState((Condition.BROKEN, Condition.DEFENCELESS)),
                           ConditionState((Condition.BROKEN, Condition.PRONE))):
            injury = replace(source.state.roster.participant('wizard').state.injury, conditions=conditions)
            with self.assertRaisesRegex(ValueError, 'living Broken actor'):
                replace(source, state=change_injury(source.state, 'wizard', injury))
        with self.assertRaisesRegex(ValueError, 'living Broken actor'):
            replace(source, state=change_injury(source.state, 'wizard', replace(
                source.state.roster.participant('wizard').state.injury, dead=True)))

    def test_models_are_frozen_and_public_boundaries_reject_wrong_types(self):
        source = request()
        result = execute(source, CountingDice([1, 2, 3]))
        for obj in (source, result):
            self.assertFalse(hasattr(obj, '__dict__'))
            with self.assertRaises(FrozenInstanceError):
                setattr(obj, fields(obj)[0].name, None)
        for call in (lambda: execute(None, CountingDice([])), lambda: apply(None, result),
                     lambda: apply(source.state, None), lambda: replace(source, willpower_profile=None),
                     lambda: replace(source, state=None), lambda: replace(result, source=None),
                     lambda: replace(result, recover=None)):
            with self.assertRaises(TypeError):
                call()

    def test_application_does_not_reroll_or_move_and_inputs_and_global_rng_stay_unchanged(self):
        source = request()
        before, rng_state = deepcopy(source), random.getstate()
        result = execute(source, CountingDice([1, 2, 3]))
        with patch('towr.engine.npc_broken_recover.resolve_free_movement', side_effect=AssertionError('no move')), \
             patch('towr.engine.npc_broken_recover.execute_recover_action', side_effect=AssertionError('no Test')):
            self.assertEqual(apply(source.state, result), result.state)
        self.assertEqual(source, before)
        self.assertEqual(random.getstate(), rng_state)

    def test_rng_failure_returns_no_partial_movement_or_consumed_action(self):
        source = request()
        before = deepcopy(source)
        problem = RuntimeError('recover RNG failed')
        rng = CountingDice([])
        with patch.object(rng, 'randint', side_effect=problem):
            with self.assertRaises(RuntimeError) as caught:
                execute(source, rng)
        self.assertIs(caught.exception, problem)
        self.assertEqual(source, before)
        self.assertEqual(source.state.consumed_execution_ids, ())
        self.assertFalse(source.state.round_state.active_turn.action_slots[0].executed)


if __name__ == '__main__':
    unittest.main()
