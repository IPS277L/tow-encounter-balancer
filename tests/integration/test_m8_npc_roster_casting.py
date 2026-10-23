from dataclasses import replace
import unittest

from tests.unit.test_m8_npc_roster_casting import bound_request, result_for
from tests.integration.test_m8_cowardly_flight_casting import next_activation
from towr.domain.npc_roster_casting_models import NpcRosterCastingRequest
from towr.domain.condition_models import Condition
from towr.domain.cowardly_flight_casting_result_models import CowardlyFlightCastingStatus as Status
from towr.domain.magic_models import WizardMagicState
from towr.domain.turn_models import CombatSide
from towr.rules.npc_roster_casting_resolution import apply_npc_roster_casting_result as apply


class NpcRosterCastingIntegrationTests(unittest.TestCase):
    def test_wait_cast_and_miscast_update_exact_states_for_either_side(self):
        for opposite in (False, True):
            base = bound_request()
            casting = base.casting
            if opposite:
                swap = lambda side: (CombatSide.OPPOSITION if side is CombatSide.PLAYERS_AND_ALLIES
                                     else CombatSide.PLAYERS_AND_ALLIES)
                combat = casting.round_state
                casting = replace(casting, round_state=replace(combat,
                    side_order=tuple(swap(side) for side in combat.side_order),
                    participants=tuple(replace(p, side=swap(p.side)) for p in combat.participants),
                    active_turn=replace(combat.active_turn, side=swap(combat.active_turn.side))),
                    spatial_state=replace(casting.spatial_state, placements=tuple(
                        replace(p, side_id=swap(CombatSide(p.side_id)).value)
                        for p in casting.spatial_state.placements)))
            for values, status in (
                ((1, 10, 10), Status.WAITING),
                ((1, 2, 3, 1, 2, 3, 10, 10, 10), Status.SPELL_RESOLVED),
                ((9, 9, 9), Status.MISCAST_REQUIRED),
            ):
                with self.subTest(opposite=opposite, status=status):
                    source = bound_request(casting)
                    result = result_for(source, values)
                    state = apply(source.state, result)
                    self.assertIs(result.casting.status, status)
                    self.assertEqual(state.round_state, result.casting.round_state)
                    self.assertIs(state.spatial_state, source.state.spatial_state)
                    self.assertEqual(state.wizard.magic_state, result.casting.magic_state)
                    self.assertTrue(state.round_state.active_turn.action_slots[0].executed)
                    self.assertEqual(state.round_state.completed_turn_entity_ids, ())
                    for actor in ('wizard', 'friend', 'distant'):
                        self.assertIs(state.roster.participant(actor), source.state.roster.participant(actor))
                    for target in result.casting.targets:
                        participant = state.roster.participant(target.actor_id)
                        self.assertEqual(participant.state.injury, target.injury)
                        self.assertFalse(participant.state.injury.defeated)
                        self.assertIs(participant.definition, source.state.roster.participant(target.actor_id).definition)
                    self.assertEqual(state.roster.participant('first').state.injury.conditions.has(
                        Condition.BROKEN), status is Status.SPELL_RESOLVED)

    def test_empty_zone_and_zero_potency_preserve_entire_roster(self):
        base = bound_request()
        for casting, values in (
            (replace(base.casting, selected_zone_id='empty', targets=()), (1, 2, 3)),
            (replace(base.casting, magic_state=WizardMagicState(0, 3, 'lore:battle-magic', 3)),
             (10, 10, 10)),
        ):
            source = bound_request(casting)
            result = result_for(source, values)
            state = apply(source.state, result)
            self.assertIs(result.casting.status, Status.SPELL_RESOLVED)
            self.assertEqual(state.roster, source.state.roster)
            self.assertEqual(state.wizard.magic_state, WizardMagicState())
            self.assertEqual(state.consumed_execution_ids, ('cast',))

    def test_wait_then_cast_carries_actor_state_and_history_across_real_round(self):
        first = bound_request()
        first_result = result_for(first)
        waiting = apply(first.state, first_result)
        next_casting = next_activation(first_result.casting)
        # The round driver supplies the next reserved activation, without
        # resetting the roster, actor-bound magic or consumption history.
        next_state = replace(waiting, round_state=next_casting.round_state,
                             spatial_state=next_casting.spatial_state)
        request = NpcRosterCastingRequest(next_state, next_casting)
        result = result_for(request, (1, 2, 10, 1, 2, 10, 10, 10, 10))
        completed = apply(next_state, result)
        self.assertEqual(completed.consumed_execution_ids, ('cast', 'next:cast'))
        self.assertEqual(completed.wizard.magic_state, WizardMagicState())
        self.assertEqual(completed.round_state.round_number, first.state.round_state.round_number + 1)
        self.assertTrue(completed.roster.participant('first').state.injury.conditions.has(Condition.BROKEN))
        for old_result in (first_result, result):
            with self.assertRaisesRegex(ValueError, 'already been consumed'):
                apply(completed, old_result)


if __name__ == '__main__':
    unittest.main()
