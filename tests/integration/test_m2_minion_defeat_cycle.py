from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_m2_minion_defeat import acknowledgement
from tests.unit.test_m2_npc_round_coordinator import Candidates, request, resume
from tests.unit.test_m2_npc_round_exclusion import exclude
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult
from towr.domain.npc_round_models import NpcRoundOutcome
from towr.domain.turn_models import CombatTurnEndResult
from towr.engine.npc_round_coordinator import run_npc_round
from towr.rules import attack_action_execution as attack_executor
from towr.rules.minion_defeat_resolution import acknowledge_minion_defeat, apply_minion_defeat_acknowledgement


def confirm(current, attack, disposition):
    result = acknowledge_minion_defeat(acknowledgement(current, attack, disposition))
    return apply_minion_defeat_acknowledgement(current, result), result


class M2MinionDefeatCycleTests(unittest.TestCase):
    def test_every_disposition_allows_exclusion_and_resume_without_manual_queue_clear(self):
        for disposition in NpcDefeatDisposition:
            with self.subTest(disposition=disposition):
                source = request()
                provider = Candidates()
                rng = Mock(wraps=SequenceRandom([1, 2, 10, 10, 10, 10] + [10] * 12 + [7]))
                with patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel:
                    stopped = run_npc_round(source, provider, rng)
                    self.assertIs(stopped.outcome, NpcRoundOutcome.PENDING_FOLLOW_UPS)
                    attack = next(step for step in stopped.steps if isinstance(step, NpcRosterAttackExecutionResult))
                    acknowledged, confirmation = confirm(resume(source, stopped), attack, disposition)
                    self.assertEqual(kernel.call_count, 1)
                    self.assertEqual(rng.randint.call_count, 6)
                    self.assertEqual(acknowledged.pending_follow_ups, ())
                    current = exclude(acknowledged, attack.execution.target_id)
                    completed = run_npc_round(current, provider, rng)
                    self.assertEqual(kernel.call_count, 3)
                self.assertIs(completed.outcome, NpcRoundOutcome.COMPLETE)
                self.assertIsInstance(completed.steps[0], CombatTurnEndResult)
                self.assertEqual(completed.steps[0].completed_turn, stopped.round_state.active_turn)
                self.assertEqual(completed.round_state.completed_turn_entity_ids, ("brigand:0", "brigand:1", "brigand:3"))
                self.assertEqual(completed.round_state.excluded_turn_entity_ids, ("brigand:2",))
                self.assertEqual(len(completed.state.consumed_execution_ids), 3)
                self.assertEqual(completed.state.acknowledged_defeat_execution_ids, (attack.execution.request_id,))
                self.assertEqual(completed.state.roster.participant("brigand:2"), stopped.state.roster.participant("brigand:2"))
                self.assertIs(confirmation.source_request.decision.disposition, disposition)
                self.assertEqual(rng.randint.call_count, 18)
                self.assertEqual(rng.randint(1, 10), 7)
                with self.assertRaisesRegex(ValueError, "source differs"):
                    apply_minion_defeat_acknowledgement(resume(source, completed), confirmation)

    def test_two_defeats_preserve_both_histories_and_complete_only_the_round(self):
        source = request()
        rng = Mock(wraps=SequenceRandom([1, 2, 10, 10, 10, 10] * 2 + [7]))
        provider = Candidates()
        with patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel:
            first = run_npc_round(source, provider, rng)
            attack1 = next(step for step in first.steps if isinstance(step, NpcRosterAttackExecutionResult))
            current, confirmed1 = confirm(resume(source, first), attack1, NpcDefeatDisposition.KNOCKED_OUT)
            current = exclude(current, "brigand:2")
            second = run_npc_round(current, provider, rng)
            self.assertIs(second.outcome, NpcRoundOutcome.PENDING_FOLLOW_UPS)
            attack2 = next(step for step in second.steps if isinstance(step, NpcRosterAttackExecutionResult))
            self.assertEqual(attack2.source_request.state.acknowledged_defeat_execution_ids, (attack1.execution.request_id,))
            current, confirmed2 = confirm(resume(current, second), attack2, NpcDefeatDisposition.DISARMED_AND_SURRENDERED)
            current = exclude(current, "brigand:3")
            completed = run_npc_round(current, provider, rng)
            self.assertEqual(kernel.call_count, 2)
        self.assertIs(completed.outcome, NpcRoundOutcome.COMPLETE)
        self.assertEqual(completed.round_state.round_number, 1)
        self.assertEqual(completed.round_state.participants, source.round_state.participants)
        self.assertEqual(completed.round_state.completed_turn_entity_ids, ("brigand:0", "brigand:1"))
        self.assertEqual(completed.round_state.excluded_turn_entity_ids, ("brigand:2", "brigand:3"))
        ids = (attack1.execution.request_id, attack2.execution.request_id)
        self.assertEqual(completed.state.consumed_execution_ids, ids)
        self.assertEqual(completed.state.acknowledged_defeat_execution_ids, ids)
        self.assertEqual(tuple(c.actor_id for c in provider.contexts), ("brigand:0", "brigand:1"))
        self.assertEqual(rng.randint.call_count, 12)
        self.assertEqual(rng.randint(1, 10), 7)
        for attack, confirmation in ((attack1, confirmed1), (attack2, confirmed2)):
            # Even if the caller puts the old anonymous follow-up back, history rejects it.
            requeued = replace(resume(current, completed), pending_follow_ups=attack.pending_follow_ups)
            with self.assertRaisesRegex(ValueError, "already acknowledged"):
                acknowledgement(requeued, attack)
            with self.assertRaisesRegex(ValueError, "source differs"):
                apply_minion_defeat_acknowledgement(requeued, confirmation)
