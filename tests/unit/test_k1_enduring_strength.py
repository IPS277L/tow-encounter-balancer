"""The clock's narrow structural exception never grants a third action."""
from copy import deepcopy
from dataclasses import replace
import unittest

from towr.domain.turn_models import (
    ENDURING_STRENGTH_RULE_ID, ActionExecutionReceipt, ActionSlotGrant,
    CombatActionDeclaration, CombatActionKind, CombatActionSlot, CombatActionSlotRequest,
    CombatRoundState, CombatSide, CombatTurnParticipant, CombatTurnState, EnduringStrengthGrant,
)
from towr.rules.turn_resolution import reserve_combat_action_slot


def source_and_grant():
    declaration = CombatActionDeclaration(CombatActionKind.ATTACK)
    receipt = ActionExecutionReceipt('first:execute', 'RULE-COMBAT-004:attack-action-execution',
        'first:kernel', 'first:kernel', 'bear', 1, 1, declaration)
    first = CombatActionSlot(1, declaration, ActionSlotGrant.STANDARD, execution=receipt)
    state = CombatRoundState(1, (CombatTurnParticipant('pc', CombatSide.PLAYERS_AND_ALLIES),
        CombatTurnParticipant('bear', CombatSide.OPPOSITION)), completed_turn_entity_ids=('pc',),
        active_turn=CombatTurnState('bear', CombatSide.OPPOSITION, (first,)))
    grant = EnduringStrengthGrant('bear', 1, 'reserve2', receipt, 'pc1', 'pc2')
    request = CombatActionSlotRequest('reserve2', state, 'bear', declaration,
        ActionSlotGrant.ABILITY, ENDURING_STRENGTH_RULE_ID, enduring_strength=grant)
    return request


class EnduringStrengthClockTests(unittest.TestCase):
    def test_real_second_slot_keeps_first_execution_and_named_target(self):
        request = source_and_grant()
        result = reserve_combat_action_slot(request)
        self.assertEqual(result.slot.index, 2)
        self.assertFalse(result.slot.executed)
        self.assertEqual(result.slot.enduring_strength.target_id, 'pc2')
        self.assertEqual(result.state.active_turn.action_slots[0], request.state.active_turn.action_slots[0])
        self.assertEqual(result.applied_rule_ids, ('RULE-COMBAT-002:action-budget', ENDURING_STRENGTH_RULE_ID))

    def test_rule_id_alone_and_fate_do_not_authorize_repeat_attack(self):
        request = source_and_grant()
        with self.assertRaises(ValueError):
            reserve_combat_action_slot(replace(request, enduring_strength=None))
        with self.assertRaises(ValueError):
            replace(request, grant=ActionSlotGrant.FATE, grant_rule_id=None)

    def test_stale_actor_round_reservation_and_same_target_rejected(self):
        request = source_and_grant()
        for changes in ({'actor_id': 'other'}, {'round_number': 2},
                        {'slot_request_id': 'other'}, {'target_id': 'pc1'}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(request, enduring_strength=replace(request.enduring_strength, **changes))

    def test_receipt_substitution_and_unexecuted_first_slot_rejected(self):
        request = source_and_grant()
        for first in (replace(request.state.active_turn.action_slots[0], execution=None),
                      replace(request.state.active_turn.action_slots[0],
                          execution=replace(request.enduring_strength.first_execution, id='foreign'))):
            state = replace(request.state, active_turn=replace(request.state.active_turn, action_slots=(first,)))
            with self.assertRaises(ValueError):
                reserve_combat_action_slot(replace(request, state=state))

    def test_wrong_slot_kind_and_third_action_rejected(self):
        request = source_and_grant()
        with self.assertRaises(ValueError):
            replace(request, declaration=CombatActionDeclaration(CombatActionKind.RECOVER))
        result = reserve_combat_action_slot(request)
        with self.assertRaises(ValueError):
            reserve_combat_action_slot(replace(request, state=result.state))

    def test_cached_round_rejects_changed_grant_round(self):
        result = reserve_combat_action_slot(source_and_grant())
        forged = deepcopy(result.state)
        object.__setattr__(forged.active_turn.action_slots[1].enduring_strength, 'round_number', 2)
        with self.assertRaises(ValueError):
            replace(forged)


if __name__ == '__main__':
    unittest.main()
