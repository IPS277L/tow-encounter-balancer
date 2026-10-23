from dataclasses import replace
import unittest
from unittest.mock import Mock

from tests.helpers import SequenceRandom
from tests.unit.test_m8_npc_champion_attack import request
from towr.domain.condition_models import Condition
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.turn_models import (
    CombatActionSlotRequest, CombatRoundState, CombatTurnStartRequest,
)
from towr.rules.turn_resolution import start_combat_turn, reserve_combat_action_slot
from towr.rules.npc_champion_attack_execution import (
    execute_npc_champion_attack as execute, apply_npc_champion_attack_result as apply,
)


def next_request(result, index):
    """Caller supplies a new reserved round; this is not an encounter runner."""
    state = apply(result.source.state, result)
    original = result.source.execution
    combat = CombatRoundState(index, state.roster.turn_participants)
    combat = start_combat_turn(CombatTurnStartRequest(f'start:{index}', combat, original.actor_id)).state
    slot = original.state.active_turn.action_slots[0]
    combat = reserve_combat_action_slot(CombatActionSlotRequest(
        f'slot:{index}', combat, original.actor_id, slot.declaration, slot.grant)).state
    return replace(result.source, state=replace(state, round_state=combat), execution=replace(
        original, id=f'attack:{index}', state=combat, kernel_request=replace(
            original.kernel_request, id=f'kernel:{index}',
            target_state=state.roster.participant(original.target_id).state.injury)))


class NpcChampionAttackIntegrationTests(unittest.TestCase):
    def test_existing_untreated_wound_adds_a_die_and_preserves_daily_history(self):
        first = execute(request(), SequenceRandom((1, 2, 10, 10, 10, 10, 1)))
        second_request = next_request(first, 2)
        rng = Mock(wraps=SequenceRandom((1, 2, 10, 10, 10, 10, 1, 2)))
        second = execute(second_request, rng)
        self.assertEqual(rng.randint.call_count, 8)
        self.assertEqual(second.resolution.target_state.wounds[-1].roll_values, (1, 2))
        self.assertEqual(len(second.resolution.target_state.wounds), 2)
        self.assertFalse(second.resolution.target_state.dead)
        self.assertEqual(second.state.daily_wounds.wound_count, 2)
        self.assertEqual(second.state.consumed_execution_ids, (first.execution.request_id, 'attack:2'))
        self.assertEqual(len(second.state.consumed_wound_roll_ids), 2)
        self.assertIsNone(second.state.pending)

    def test_treated_prior_wound_does_not_add_a_die(self):
        first = execute(request(), SequenceRandom((1, 2, 10, 10, 10, 10, 1)))
        source = next_request(first, 2)
        target = source.state.roster.participant(source.execution.target_id)
        injury = replace(target.state.injury, wounds=(replace(target.state.injury.wounds[0], treated=True),))
        roster = NpcRoster(tuple(replace(p, state=replace(p.state, injury=injury)) if p is target else p
                                for p in source.state.roster.participants))
        source = replace(source, state=replace(source.state, roster=roster), execution=replace(
            source.execution, kernel_request=replace(source.execution.kernel_request, target_state=injury)))
        rng = Mock(wraps=SequenceRandom((1, 2, 10, 10, 10, 10, 1)))
        second = execute(source, rng)
        self.assertEqual(rng.randint.call_count, 7)
        self.assertEqual(second.resolution.target_state.wounds[-1].roll_values, (1,))
        self.assertEqual(second.state.daily_wounds.wound_count, 2)

    def test_lethal_wound_keeps_death_and_all_followups_without_declaring_victory(self):
        first = execute(request(), SequenceRandom((1, 2, 10, 10, 10, 10, 1)))
        second = execute(next_request(first, 2), SequenceRandom((1, 2, 10, 10, 10, 10, 1, 1)))
        third = execute(next_request(second, 3), SequenceRandom((1, 2, 10, 10, 10, 10, 10, 10, 10)))
        self.assertTrue(third.resolution.target_state.dead)
        self.assertEqual(third.state.daily_wounds.wound_count, 3)
        self.assertEqual(third.state.round_state.completed_turn_entity_ids, ())
        self.assertEqual(third.pending_follow_ups, ())
        self.assertIsNone(third.state.pending)
        with self.assertRaisesRegex(ValueError, 'living actor and target'):
            next_request(third, 4)
        self.assertFalse(third.resolution.target_state.conditions.has(Condition.STAGGERED))


if __name__ == '__main__':
    unittest.main()
