"""Real scheduler/K1 composition; other actors explicitly Recover between casts."""
from dataclasses import replace
import unittest

from tests.unit.test_m8_cowardly_flight_casting import CountingDice
from tests.unit.test_m8_cowardly_flight_casting_models import casting_input
from towr.domain.condition_models import ConditionState
from towr.domain.cowardly_flight_casting_result_models import CowardlyFlightCastingStatus as Status
from towr.domain.magic_models import WizardMagicState
from towr.domain.recover_models import RecoverActionExecutionRequest, RecoverMode, RecoverStandardChoice
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundAdvanceRequest, CombatTurnEndRequest, CombatTurnStartRequest,
)
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting
from towr.rules.recover_resolution import execute_recover_action
from towr.rules.turn_resolution import (
    advance_combat_round, end_combat_turn, reserve_combat_action_slot, start_combat_turn,
)


def next_activation(wait):
    source = wait.source
    combat = end_combat_turn(CombatTurnEndRequest('end:wizard', wait.round_state, 'wizard')).state
    no_dice = CountingDice([])
    for participant in combat.participants[1:]:
        actor = participant.entity_id
        combat = start_combat_turn(CombatTurnStartRequest('turn:' + actor, combat, actor)).state
        combat = reserve_combat_action_slot(CombatActionSlotRequest(
            'slot:' + actor, combat, actor, CombatActionDeclaration(CombatActionKind.RECOVER),
            ActionSlotGrant.STANDARD)).state
        # Only the wizard has active Casting. These other actors have no magic pool,
        # Conditions, treatment or movement; their Recover consumes no dice.
        combat = execute_recover_action(RecoverActionExecutionRequest(
            'recover:' + actor, combat, actor, ConditionState(), actor != 'distant', 1,
            RecoverMode.STANDARD, RecoverStandardChoice(WizardMagicState())), no_dice).round_state
        combat = end_combat_turn(CombatTurnEndRequest('end:' + actor, combat, actor)).state
    assert no_dice.calls == 0 and combat.round_complete
    combat = advance_combat_round(CombatRoundAdvanceRequest('advance', combat, combat.participants)).state
    combat = start_combat_turn(CombatTurnStartRequest('next:wizard', combat, 'wizard')).state
    combat = reserve_combat_action_slot(CombatActionSlotRequest(
        'next:slot', combat, 'wizard', source.round_state.active_turn.action_slots[0].declaration,
        ActionSlotGrant.STANDARD)).state
    return replace(source, id='next:cast', round_state=combat, magic_state=wait.magic_state,
                   spatial_state=replace(wait.spatial_state, round_number=combat.round_number))


class CowardlyFlightCastingIntegrationTests(unittest.TestCase):
    def test_wait_then_cast_across_real_turn_and_round_transitions(self):
        first = execute_cowardly_flight_casting(casting_input(), CountingDice([1, 10, 10]))
        self.assertIs(first.status, Status.WAITING)
        next_request = next_activation(first)
        second = execute_cowardly_flight_casting(next_request, CountingDice([1, 2, 10, 1, 2, 10, 10, 10, 10]))
        self.assertIs(second.status, Status.SPELL_RESOLVED)
        self.assertEqual(second.round_state.round_number, first.round_state.round_number + 1)
        self.assertEqual(second.post_test.decision.previous_casting_successes, 3)
        self.assertEqual(second.post_test.decision.base_potency, 2)
        self.assertIs(next_request.magic_state, first.magic_state)
        self.assertEqual(second.magic_state, WizardMagicState())
        self.assertNotEqual(first.execution.slot.execution.id, second.execution.slot.execution.id)

    def test_round_transition_does_not_clear_pool_before_triggered_miscast(self):
        source = replace(casting_input(), magic_state=WizardMagicState(1))
        first = execute_cowardly_flight_casting(source, CountingDice([9, 1, 10]))
        self.assertIs(first.status, Status.WAITING)
        self.assertEqual(first.magic_state.miscast_dice, 2)
        second = execute_cowardly_flight_casting(next_activation(first), CountingDice([9, 1, 2]))
        self.assertIs(second.status, Status.MISCAST_REQUIRED)
        self.assertEqual(second.magic_state.miscast_dice, 3)
        self.assertEqual(second.magic_state.casting_successes, 3)
        self.assertIsNotNone(second.pending_miscast)
        self.assertIsNone(second.spell)


if __name__ == '__main__':
    unittest.main()
