from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import Mock

from tests.helpers import SequenceRandom
from tests.unit.test_m2_npc_round_coordinator import Candidates, request, resume
from tests.unit.test_m2_npc_roster_attack_execution import change_participant
from tests.unit.test_m2_npc_round_exclusion import exclude
from towr.domain.minion_defeat_models import (
    MinionDefeatAcknowledgementRequest, MinionDefeatAcknowledgementResult,
    MinionDefeatDecision, NpcDefeatDisposition,
)
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult
from towr.domain.npc_round_models import NpcRoundOutcome
from towr.domain.resolution_models import GiveGroundRequest
from towr.engine.npc_round_coordinator import run_npc_round
from towr.rules.minion_defeat_resolution import acknowledge_minion_defeat, apply_minion_defeat_acknowledgement


def defeat_context():
    source = request()
    stopped = run_npc_round(source, Candidates(), SequenceRandom([1, 2, 10, 10, 10, 10]))
    attack = next(step for step in stopped.steps if isinstance(step, NpcRosterAttackExecutionResult))
    return resume(source, stopped), attack


def acknowledgement(current, attack, disposition=NpcDefeatDisposition.KNOCKED_OUT):
    return MinionDefeatAcknowledgementRequest("ack:" + attack.execution.request_id, current, attack,
        MinionDefeatDecision(attack.execution.actor_id, attack.execution.target_id, disposition, True))


class M2MinionDefeatTests(unittest.TestCase):
    def test_all_dispositions_record_choice_without_reapplying_injury_receipt_or_equipment(self):
        current, attack = defeat_context()
        before = deepcopy(current)
        for disposition in NpcDefeatDisposition:
            with self.subTest(disposition=disposition):
                source = acknowledgement(current, attack, disposition)
                result = acknowledge_minion_defeat(source)
                updated = apply_minion_defeat_acknowledgement(current, result)
                self.assertIs(result.source_request, source)
                self.assertIs(result.source_request.decision.disposition, disposition)
                self.assertEqual(updated.pending_follow_ups, ())
                self.assertIs(updated.state.roster, current.state.roster)
                self.assertIs(updated.round_state, current.round_state)
                self.assertEqual(updated.state.consumed_execution_ids, current.state.consumed_execution_ids)
                self.assertEqual(updated.state.acknowledged_defeat_execution_ids, (attack.execution.request_id,))
                self.assertEqual(result.applied_rule_ids, ("RULE-NPC-002",))
                self.assertEqual(current, before)
                with self.assertRaises(FrozenInstanceError):
                    result.source_request = None

    def test_other_follow_ups_keep_order_and_still_block_coordinator_and_exclusion(self):
        current, attack = defeat_context()
        before, after = GiveGroundRequest("other:before"), GiveGroundRequest("other:after")
        current = replace(current, pending_follow_ups=(before, *current.pending_follow_ups, after))
        result = acknowledge_minion_defeat(acknowledgement(current, attack))
        updated = apply_minion_defeat_acknowledgement(current, result)
        self.assertEqual(updated.pending_follow_ups, (before, after))
        self.assertIs(updated.pending_follow_ups[0], before)
        provider, rng = Mock(), Mock()
        stopped = run_npc_round(updated, provider, rng)
        self.assertIs(stopped.outcome, NpcRoundOutcome.PENDING_FOLLOW_UPS)
        self.assertEqual(stopped.steps, ())
        with self.assertRaisesRegex(ValueError, "pending"):
            exclude(updated, attack.execution.target_id)
        provider.get_candidates.assert_not_called()
        rng.randint.assert_not_called()

    def test_matching_profile_must_appear_once_and_cannot_be_replaced_with_other_wound_counts(self):
        current, attack = defeat_context()
        follow_up = current.pending_follow_ups[0]
        for queue in ((), (follow_up, follow_up), (replace(follow_up, current_wounds=2),)):
            with self.subTest(queue=queue), self.assertRaisesRegex(ValueError, "exactly one matching"):
                acknowledgement(replace(current, pending_follow_ups=queue), attack)

    def test_missing_gm_approval_wrong_attacker_or_target_rejected(self):
        current, attack = defeat_context()
        source = acknowledgement(current, attack)
        for change in ({"gm_approved": False}, {"attacker_id": "brigand:1"}, {"target_id": "brigand:3"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(source, decision=replace(source.decision, **change))

    def test_replay_requeued_follow_up_new_id_or_changed_disposition_rejected_by_execution_history(self):
        current, attack = defeat_context()
        source = acknowledgement(current, attack)
        result = acknowledge_minion_defeat(source)
        updated = apply_minion_defeat_acknowledgement(current, result)
        with self.assertRaisesRegex(ValueError, "source differs"):
            apply_minion_defeat_acknowledgement(updated, result)
        requeued = replace(updated, pending_follow_ups=current.pending_follow_ups)
        for disposition in NpcDefeatDisposition:
            with self.subTest(disposition=disposition), self.assertRaisesRegex(ValueError, "already acknowledged"):
                replace(source, id="another-id", current=requeued,
                        decision=replace(source.decision, disposition=disposition))

    def test_stale_roster_history_and_round_rejected_before_acknowledgement(self):
        current, attack = defeat_context()
        changed = (
            replace(current, state=change_participant(current.state, 1, available_attack_ids=())),
            replace(current, state=replace(current.state, consumed_execution_ids=("other", *current.state.consumed_execution_ids))),
            replace(current, round_state=replace(current.round_state, active_turn=None)),
        )
        for stale in changed:
            with self.subTest(stale=stale), self.assertRaisesRegex(ValueError, "exact post-Attack"):
                acknowledgement(stale, attack)

    def test_consumer_rejects_changed_pending_order_context_and_history(self):
        current, attack = defeat_context()
        extra = GiveGroundRequest("other")
        current = replace(current, pending_follow_ups=(*current.pending_follow_ups, extra))
        result = acknowledge_minion_defeat(acknowledgement(current, attack))
        for stale in (
            replace(current, pending_follow_ups=tuple(reversed(current.pending_follow_ups))),
            replace(current, actor_order=tuple(reversed(current.actor_order))),
            replace(current, id="other"),
            replace(current, state=replace(current.state, consumed_execution_ids=("other", *current.state.consumed_execution_ids))),
        ):
            with self.subTest(stale=stale), self.assertRaisesRegex(ValueError, "source differs"):
                apply_minion_defeat_acknowledgement(stale, result)

    def test_identical_anonymous_profile_from_foreign_attack_does_not_bind(self):
        current, attack = defeat_context()
        source = request()
        source = replace(source, actor_order=("brigand:1", "brigand:0", "brigand:2", "brigand:3"))
        stopped = run_npc_round(source, Candidates(), SequenceRandom([1, 2, 10, 10, 10, 10]))
        foreign = next(step for step in stopped.steps if isinstance(step, NpcRosterAttackExecutionResult))
        self.assertEqual(foreign.pending_follow_ups, attack.pending_follow_ups)
        with self.assertRaisesRegex(ValueError, "exact post-Attack"):
            acknowledgement(current, foreign)

    def test_miss_and_staggered_hit_cannot_acknowledge_defeat(self):
        for dice in ([10] * 6, [1, 10, 10, 10, 10, 10]):
            with self.subTest(dice=dice):
                source = request()
                provider = Candidates()
                provide = provider.get_candidates
                provider.get_candidates = lambda context: provide(context) if context.actor_id == "brigand:0" else context
                stopped = run_npc_round(source, provider, SequenceRandom(dice))
                attack = next(step for step in stopped.steps if isinstance(step, NpcRosterAttackExecutionResult))
                # Bind its exact post-Attack turn, so the failure is the injury/outcome guard.
                current = replace(source, state=attack.state, round_state=attack.execution.state,
                                  pending_follow_ups=attack.pending_follow_ups)
                with self.assertRaisesRegex(ValueError, "Minion defeat"):
                    acknowledgement(current, attack)

    def test_acknowledgement_history_is_unique_typed_and_requires_consumed_attack(self):
        current, attack = defeat_context()
        for ids in (("absent",), ("",), (1,), (attack.execution.request_id,) * 2):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                replace(current.state, acknowledged_defeat_execution_ids=ids)
        state = replace(current.state, acknowledged_defeat_execution_ids=[attack.execution.request_id])
        self.assertIsInstance(state.acknowledged_defeat_execution_ids, tuple)

    def test_typed_contracts_reject_malformed_decision_request_and_result(self):
        current, attack = defeat_context()
        source = acknowledgement(current, attack)
        for change in ({"disposition": "killed"}, {"gm_approved": 1}, {"attacker_id": ""}, {"target_id": "brigand:0"}):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                replace(source.decision, **change)
        for change in ({"id": ""}, {"current": object()}, {"attack": object()}, {"decision": object()}):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                replace(source, **change)
        with self.assertRaises(TypeError):
            MinionDefeatAcknowledgementResult(object())
        with self.assertRaises(TypeError):
            apply_minion_defeat_acknowledgement(current, object())
