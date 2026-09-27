from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_m2_npc_round_coordinator import Candidates, request, resume
from tests.unit.test_m2_npc_round_exclusion import defeat, exclude
from towr.domain.npc_round_models import NpcRoundOutcome
from towr.domain.turn_models import CombatTurnEndResult
from towr.engine.npc_round_coordinator import run_npc_round
from towr.rules import attack_action_execution as attack_executor


class M2NpcRoundExclusionCycleTests(unittest.TestCase):
    def test_two_by_two_wound_acknowledgement_exclusion_and_remaining_turns(self):
        source = request()
        rng = Mock(wraps=SequenceRandom([1, 2, 10, 10, 10, 10] + [10] * 12 + [7]))
        provider = Candidates()
        with patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel:
            first = run_npc_round(source, provider, rng)
            self.assertIs(first.outcome, NpcRoundOutcome.PENDING_FOLLOW_UPS)
            self.assertEqual(kernel.call_count, 1)
            with self.assertRaisesRegex(ValueError, "pending"):
                exclude(resume(source, first), "brigand:2")
            # Attacker/GM acknowledges the disposition outside this coordinator.
            acknowledged = resume(source, first, pending=())
            second = run_npc_round(acknowledged, provider, rng)
            self.assertIs(second.outcome, NpcRoundOutcome.DEFEATED_ACTOR)
            self.assertEqual(kernel.call_count, 2)
            current = exclude(resume(source, second), "brigand:2")
            final = run_npc_round(current, provider, rng)
            self.assertEqual(kernel.call_count, 3)
        self.assertIs(final.outcome, NpcRoundOutcome.COMPLETE)
        self.assertEqual(tuple(c.actor_id for c in provider.contexts), ("brigand:0", "brigand:1", "brigand:3"))
        self.assertEqual(final.round_state.completed_turn_entity_ids, ("brigand:0", "brigand:1", "brigand:3"))
        self.assertEqual(final.round_state.excluded_turn_entity_ids, ("brigand:2",))
        self.assertEqual(final.round_state.participants, source.round_state.participants)
        self.assertEqual(final.state.roster.participant("brigand:2"), first.state.roster.participant("brigand:2"))
        self.assertEqual(final.state.consumed_execution_ids[:2], second.state.consumed_execution_ids)
        self.assertEqual(len(set(final.state.consumed_execution_ids)), 3)
        self.assertEqual(rng.randint.call_count, 18)
        self.assertEqual(rng.randint(1, 10), 7)
        self.assertEqual(tuple(step.completed_turn.actor_id for step in final.steps
                               if isinstance(step, CombatTurnEndResult)), ("brigand:3",))
        provider_after, rng_after = Mock(), Mock()
        repeated = run_npc_round(resume(source, final), provider_after, rng_after)
        self.assertEqual(repeated.steps, ())
        provider_after.get_candidates.assert_not_called()
        rng_after.randint.assert_not_called()

    def test_no_remaining_opposition_does_not_manufacture_victory_or_skip_live_actor(self):
        source = defeat(request(), 2, 3)
        current = exclude(exclude(source, "brigand:2"), "brigand:3")
        rng = Mock()
        # Supplied candidates still point at defeated targets; existing selection rejects them.
        result = run_npc_round(current, Candidates(), rng)
        self.assertIs(result.outcome, NpcRoundOutcome.SELECTION_BLOCKED)
        self.assertEqual(result.round_state.completed_turn_entity_ids, ())
        self.assertFalse(result.round_state.round_complete)
        self.assertEqual(result.round_state.active_turn.actor_id, "brigand:0")
        self.assertEqual(result.round_state.excluded_turn_entity_ids, ("brigand:2", "brigand:3"))
        rng.randint.assert_not_called()

    def test_exclusion_after_acknowledgement_preserves_active_receipt_until_resume(self):
        source = request()
        first = run_npc_round(source, Candidates(), SequenceRandom([1, 2, 10, 10, 10, 10]))
        acknowledged = resume(source, first, pending=())
        current = exclude(acknowledged, "brigand:2")
        self.assertEqual(current.round_state.active_turn, first.round_state.active_turn)
        provider = Candidates()
        final = run_npc_round(current, provider, SequenceRandom([10] * 12))
        self.assertIsInstance(final.steps[0], CombatTurnEndResult)
        self.assertEqual(final.steps[0].completed_turn.action_slots[0].execution,
                         first.round_state.active_turn.action_slots[0].execution)
        self.assertEqual(tuple(c.actor_id for c in provider.contexts), ("brigand:1", "brigand:3"))
        self.assertIs(final.outcome, NpcRoundOutcome.COMPLETE)
        self.assertEqual(len(final.state.consumed_execution_ids), 3)
        # The exclusion result cannot be transplanted onto another current pending queue.
        with self.assertRaisesRegex(ValueError, "pending"):
            exclude(replace(acknowledged, pending_follow_ups=first.pending_follow_ups), "brigand:2")
