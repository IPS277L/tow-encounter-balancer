"""Real Casting/movement/Willpower and Champion Wound owner handoff."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_m8_cowardly_flight_casting import CountingDice
from tests.unit.test_m8_cowardly_flight_casting_movement import movement_input
from tests.unit.test_m8_npc_roster_casting_completion import begin, finish, completion_request
from tests.integration.test_m8_champion_casting_handoff import incoming_attack, wizard_turn
from towr.domain.condition_models import Condition
from towr.domain.magic_models import WizardMagicState
from towr.domain.npc_roster_casting_models import (
    NpcRosterCastingResult, NpcRosterCastingTargetContext,
)
from towr.domain.npc_roster_casting_completion_models import NpcRosterCastingCompletionResult
from towr.domain.npc_roster_champion_attack_models import (
    NpcRosterChampionAttackRequest, NpcRosterChampionAttackResult,
)
from towr.domain.spatial_models import ZoneConnection, ZoneGraph
from towr.domain.test_models import InlineProfile
from towr.domain.turn_models import CombatSide
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting, complete_cowardly_flight_casting
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_champion_attack_resolution import apply_npc_roster_champion_attack_result as apply_attack
from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting, apply_npc_roster_casting_result
from towr.rules.npc_roster_casting_completion_resolution import apply_npc_roster_casting_completion


class NpcRosterCastingCompletionIntegrationTests(unittest.TestCase):
    def test_both_wizard_sides_move_targets_and_transfer_original_order_and_receipt(self):
        source = movement_input()
        other_side = lambda s: (CombatSide.OPPOSITION if s is CombatSide.PLAYERS_AND_ALLIES
                                else CombatSide.PLAYERS_AND_ALLIES)
        combat = replace(source.round_state,
                         participants=tuple(replace(p, side=other_side(p.side)) for p in source.round_state.participants),
                         side_order=tuple(reversed(source.round_state.side_order)),
                         active_turn=replace(source.round_state.active_turn, side=CombatSide.OPPOSITION))
        spatial = replace(source.spatial_state, placements=tuple(
            replace(p, side_id=other_side(CombatSide(p.side_id)).value) for p in source.spatial_state.placements))
        opposite = replace(source, round_state=combat, spatial_state=spatial)
        for casting in (source, opposite):
            with self.subTest(side=casting.round_state.active_turn.side):
                _, initial, current, casting_calls = begin(casting)
                completion, final, target_calls = finish(current)
                self.assertEqual((casting_calls, target_calls), (3, 6))
                self.assertEqual(tuple(t.target_id for t in completion.completion.casting.willpower.targets),
                                 ('second', 'first'))
                self.assertEqual(final.consumed_execution_ids, ('cast',))
                self.assertIs(final.round_state, current.round_state)
                self.assertIs(final.round_state.active_turn.action_slots[0].execution,
                              initial.casting.execution.slot.execution)
                self.assertTrue(final.roster.participant('first').state.injury.conditions.has(Condition.BROKEN))
                self.assertIsNone(final.pending_movement)
                self.assertEqual(final.round_state.completed_turn_entity_ids, ())

    def test_enemy_destination_broken_survives_successful_curse_resistance(self):
        _, _, current, _ = begin(movement_input(enemy_destination=True))
        result, final, _ = finish(current, [1, 2, 3] * 2)
        for movement, target in zip(result.completion.casting.willpower.completed_movements,
                                    result.completion.casting.willpower.targets):
            self.assertTrue(movement.resolution.entered_enemy_zone)
            self.assertTrue(target.resisted)
            self.assertTrue(final.roster.participant(target.target_id).state.injury.conditions.has(Condition.BROKEN))
            self.assertFalse(final.roster.participant(target.target_id).state.injury.defeated)

    def test_one_immobile_target_still_tests_after_other_target_has_left(self):
        source = movement_input(both=False)
        source = replace(source, spatial_state=replace(source.spatial_state, gave_ground_entity_ids=('first',)))
        _, _, current, _ = begin(source)
        result, final, _ = finish(current, [10] * 6)
        self.assertEqual(tuple(f.target_id for f in current.pending_movement.pending_movements), ('second',))
        self.assertEqual(tuple(t.target_id for t in result.completion.casting.willpower.targets), ('second', 'first'))
        self.assertEqual(final.spatial_state.placement_for('second').zone_id, 'empty')
        self.assertEqual(final.spatial_state.placement_for('first').zone_id, 'arena')
        self.assertEqual(final.spatial_state.gave_ground_entity_ids, ('first', 'second'))
        self.assertTrue(all(final.roster.participant(actor).state.injury.conditions.has(Condition.BROKEN)
                            for actor in ('second', 'first')))

    def test_real_champion_wound_then_curse_completion_preserves_daily_and_both_histories(self):
        source = incoming_attack()
        attack = execute_npc_champion_attack(source.attack, SequenceRandom((1, 2, 10, 10, 10, 10, 6)))
        after_attack = apply_attack(source.state, NpcRosterChampionAttackResult(source, attack))
        current = wizard_turn(after_attack)
        current = replace(current, spatial_state=replace(current.spatial_state,
            graph=ZoneGraph(('arena', 'empty'), (ZoneConnection('arena', 'empty'),))))
        bound = prepare_npc_roster_casting(request_id='injured:cast', state=current, selected_zone_id='arena',
            targets=tuple(NpcRosterCastingTargetContext(actor, InlineProfile(3, 3), True)
                          for actor in ('brigand:0', 'brigand:1')),
            facts=movement_input().facts, policy=movement_input().policy)
        rng = CountingDice([1, 2, 10])
        raw = execute_cowardly_flight_casting(bound.casting, rng)
        pending = apply_npc_roster_casting_result(current, NpcRosterCastingResult(bound, raw))
        self.assertEqual(rng.calls, 3)
        self.assertEqual(pending.wizard.magic_state, WizardMagicState(1))
        self.assertIsNotNone(pending.pending_movement)
        self.assertEqual(pending.champion_attack.roster, pending.roster)
        with patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no RNG')):
            with self.assertRaisesRegex(ValueError, 'pending movement'):
                NpcRosterChampionAttackRequest(pending, source.attack)
        request = completion_request(pending)
        target_rng = CountingDice([1, 2, 10, 10, 10, 10])
        completion = complete_cowardly_flight_casting(request.completion, target_rng)
        result = NpcRosterCastingCompletionResult(request, completion)
        final = apply_npc_roster_casting_completion(pending, result)
        self.assertEqual(target_rng.calls, 6)
        self.assertEqual(final.roster.participant(final.wizard.actor_id).state.injury, attack.resolution.target_state)
        self.assertTrue(final.roster.participant(final.wizard.actor_id).state.injury.conditions.has(Condition.DRAINED))
        self.assertEqual(final.champion_attack.daily_wounds, after_attack.champion_attack.daily_wounds)
        self.assertEqual(final.champion_attack.daily_wounds.wound_count, 1)
        self.assertEqual(final.champion_attack.consumed_wound_roll_ids, after_attack.champion_attack.consumed_wound_roll_ids)
        self.assertEqual(final.champion_attack.consumed_execution_ids, (source.attack.execution.id,))
        self.assertEqual(final.consumed_execution_ids, (source.attack.execution.id, 'injured:cast'))
        self.assertEqual(final.champion_attack.roster, final.roster)
        self.assertIs(final.champion_attack.round_state, final.round_state)
        self.assertIs(final.round_state, pending.round_state)
        self.assertIs(final.wizard, pending.wizard)
        self.assertIsNone(final.pending_movement)
        self.assertIsNone(final.champion_attack.pending)
        for actor in ('brigand:0', 'brigand:1'):
            self.assertEqual(final.spatial_state.placement_for(actor).zone_id, 'empty')

    def test_unrelated_new_attack_result_cannot_apply_while_movement_is_pending(self):
        source = incoming_attack()
        attack = execute_npc_champion_attack(source.attack, SequenceRandom((10,) * 6))
        old_result = NpcRosterChampionAttackResult(source, attack)
        after_attack = wizard_turn(apply_attack(source.state, old_result))
        current = replace(after_attack, spatial_state=replace(after_attack.spatial_state,
            graph=ZoneGraph(('arena', 'empty'), (ZoneConnection('arena', 'empty'),))))
        bound = prepare_npc_roster_casting(request_id='cast', state=current, selected_zone_id='arena',
            targets=tuple(NpcRosterCastingTargetContext(actor, InlineProfile(3, 3), True)
                          for actor in ('brigand:0', 'brigand:1')),
            facts=movement_input().facts, policy=movement_input().policy)
        casting = execute_cowardly_flight_casting(bound.casting, CountingDice([1, 2, 3]))
        pending = apply_npc_roster_casting_result(current, NpcRosterCastingResult(bound, casting))
        with self.assertRaises(ValueError):
            apply_attack(pending, old_result)
        self.assertIs(pending.pending_movement, casting)


if __name__ == '__main__':
    unittest.main()
