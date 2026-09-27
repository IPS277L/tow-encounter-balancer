from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_kernel import FixedKernelDecisions
from tests.unit.test_m2_npc_rounds_runner import NextRounds, SpatialCandidates, request
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult
from towr.domain.npc_round_advance_models import NpcRoundAdvanceRequest
from towr.domain.npc_rounds_models import NpcRoundsOutcome as Outcome, NpcRoundsRequest
from towr.domain.resolution_models import GiveGroundRequest
from towr.domain.injury_models import ProfileStateChangeRequest
from towr.engine import npc_rounds_runner as runner
from towr.rules import attack_action_execution as attack_executor, npc_round_advance as advance


class M2NpcRoundsCycleTests(unittest.TestCase):
    def test_two_real_rounds_preserve_histories_and_conditions_reset_usage_and_change_order(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                source = request(reverse=reverse)
                # Prior caller-owned histories must survive every new Attack/advance.
                state = replace(source.current.state, consumed_execution_ids=("past:defeat", "past:gg"),
                                acknowledged_defeat_execution_ids=("past:defeat",), consumed_give_ground_execution_ids=("past:gg",))
                source = replace(source, current=replace(source.current, state=state))
                before = deepcopy(source)
                candidates, plans = SpatialCandidates(), NextRounds()
                rng = Mock(wraps=SequenceRandom([10] * 48 + [7]))
                with (patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel,
                      patch.object(advance, "advance_combat_round", wraps=advance.advance_combat_round) as combat,
                      patch.object(advance, "start_next_spatial_round", wraps=advance.start_next_spatial_round) as spatial):
                    result = runner.run_npc_rounds(source, candidates, plans, rng)
                self.assertIs(result.outcome, Outcome.ROUND_LIMIT)
                self.assertEqual(len(result.completed_rounds), 2)
                self.assertEqual(len(result.advances), 1)
                self.assertEqual(kernel.call_count, 8)
                combat.assert_called_once()
                spatial.assert_called_once_with(source.spatial_state)
                self.assertEqual(rng.randint.call_count, 48)
                self.assertEqual(rng.randint(1, 10), 7)
                self.assertEqual(len(plans.contexts), 1)
                first_order = ("brigand:2", "brigand:3", "brigand:0", "brigand:1") if reverse else (
                    "brigand:0", "brigand:1", "brigand:2", "brigand:3")
                second_order = (first_order[1], first_order[0], first_order[3], first_order[2])
                self.assertEqual(tuple(c.actor_id for c, _ in candidates.contexts), (*first_order, *second_order))
                self.assertEqual(tuple(r.round_state.round_number for r in result.rounds), (1, 2))
                self.assertEqual(result.current.round_state.side_order, source.current.round_state.side_order)
                self.assertEqual(result.spatial_state.round_number, 2)
                self.assertEqual(result.spatial_state.placements, source.spatial_state.placements)
                self.assertEqual(result.spatial_state.graph, source.spatial_state.graph)
                self.assertEqual((result.spatial_state.gave_ground_entity_ids, result.spatial_state.free_move_used_entity_ids,
                                  result.spatial_state.difficult_terrain_tested_entity_ids), ((), (), ()))
                for context, supplied in candidates.contexts[:4]:
                    self.assertIs(supplied, source.spatial_state)
                for context, supplied in candidates.contexts[4:]:
                    self.assertIs(supplied, result.spatial_state)
                    self.assertEqual(context.round_state.round_number, supplied.round_number)
                    self.assertEqual(supplied.gave_ground_entity_ids, ())
                    self.assertTrue(context.state.roster.participant(context.actor_id).state.injury.conditions.has(Condition.STAGGERED))
                attacks = tuple(s for r in result.rounds for s in r.steps if isinstance(s, NpcRosterAttackExecutionResult))
                ids = tuple(a.execution.request_id for a in attacks)
                self.assertEqual(len(set(ids)), 8)
                self.assertEqual(result.current.state.consumed_execution_ids, (*state.consumed_execution_ids, *ids))
                self.assertEqual(result.current.state.acknowledged_defeat_execution_ids, state.acknowledged_defeat_execution_ids)
                self.assertEqual(result.current.state.consumed_give_ground_execution_ids, state.consumed_give_ground_execution_ids)
                for attack in attacks:
                    self.assertFalse(attack.source_request.execution.state.active_turn.action_slots[0].executed)
                    self.assertEqual(attack.execution.slot.execution.id, attack.execution.request_id)
                self.assertEqual(source, before)

    def test_late_block_can_resume_second_round_without_replaying_first_or_earlier_actor(self):
        source = request(max_rounds=3)
        original = SpatialCandidates()
        provider = Mock()
        provider.get_candidates.side_effect = lambda c, s: c if c.round_state.round_number == 2 and c.actor_id == "brigand:0" else original.get_candidates(c, s)
        plans, rng = NextRounds(), Mock(wraps=SequenceRandom([10] * 30 + [7]))
        with patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel:
            stopped = runner.run_npc_rounds(source, provider, plans, rng)
            self.assertEqual(kernel.call_count, 5)
            self.assertIs(stopped.outcome, Outcome.SELECTION_BLOCKED)
            self.assertEqual(len(stopped.completed_rounds), 1)
            self.assertEqual(stopped.current.round_state.active_turn.actor_id, "brigand:0")
            self.assertEqual(rng.randint.call_count, 30)
            self.assertEqual(rng.randint(1, 10), 7)
            prior = stopped.current.state.consumed_execution_ids
            unused_plans = Mock()
            remainder = Mock(wraps=SequenceRandom([10] * 18 + [8]))
            finished = runner.run_npc_rounds(NpcRoundsRequest(stopped.current, stopped.spatial_state, 1),
                                             original, unused_plans, remainder)
            self.assertEqual(kernel.call_count, 8)
        self.assertIs(finished.outcome, Outcome.ROUND_LIMIT)
        self.assertEqual(finished.current.state.consumed_execution_ids[:5], prior)
        self.assertEqual(len(finished.current.state.consumed_execution_ids), 8)
        self.assertEqual(finished.current.round_state.round_number, 2)
        self.assertEqual(finished.advances, ())
        self.assertEqual(len(plans.contexts), 1)
        unused_plans.get_next_round.assert_not_called()
        self.assertEqual(remainder.randint.call_count, 18)
        self.assertEqual(remainder.randint(1, 10), 8)

    def test_real_second_round_pending_stops_before_movement_acknowledgement_or_third_round(self):
        for choice, pending_type in ((StaggerChoice.GIVE_GROUND, GiveGroundRequest),
                                     (StaggerChoice.SUFFER_WOUND, ProfileStateChangeRequest)):
            with self.subTest(choice=choice):
                source = request(max_rounds=3)
                rng = Mock(wraps=SequenceRandom([10] * 24 + [1, 10, 10, 10, 10, 10, 7]))
                plans, candidates = NextRounds(), SpatialCandidates()
                with patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel:
                    result = runner.run_npc_rounds(source, candidates, plans, rng,
                        decisions=FixedKernelDecisions(stagger=choice))
                    self.assertEqual(kernel.call_count, 5)
                    self.assertIs(result.outcome, Outcome.PENDING_FOLLOW_UPS)
                    self.assertEqual(len(result.completed_rounds), 1)
                    self.assertEqual(len(result.rounds), 2)
                    self.assertIsInstance(result.current.pending_follow_ups[0], pending_type)
                    self.assertTrue(result.current.round_state.active_turn.action_slots[0].executed)
                    self.assertEqual(result.current.round_state.round_number, 2)
                    self.assertEqual(result.spatial_state.placements, source.spatial_state.placements)
                    self.assertEqual(result.spatial_state.gave_ground_entity_ids, ())
                    self.assertEqual(result.current.state.consumed_give_ground_execution_ids, ())
                    self.assertEqual(result.current.state.acknowledged_defeat_execution_ids, ())
                    untouched_candidates, untouched_plans, untouched_rng = Mock(), Mock(), Mock()
                    repeated = runner.run_npc_rounds(NpcRoundsRequest(result.current, result.spatial_state, 3),
                        untouched_candidates, untouched_plans, untouched_rng)
                    self.assertEqual(kernel.call_count, 5)
                self.assertEqual(repeated.current, result.current)
                self.assertEqual(untouched_candidates.mock_calls + untouched_plans.mock_calls + untouched_rng.mock_calls, [])
                self.assertEqual(rng.randint.call_count, 30)
                self.assertEqual(rng.randint(1, 10), 7)
                self.assertEqual(len(plans.contexts), 1)

    def test_explicit_smaller_next_composition_keeps_roster_without_automatic_filtering(self):
        source = request()
        plans = Mock()
        def next_round(current, spatial):
            members = tuple(p for p in current.round_state.participants if p.entity_id in ("brigand:0", "brigand:2"))
            return NpcRoundAdvanceRequest("two", current, spatial, members, ("brigand:2", "brigand:0"))
        plans.get_next_round.side_effect = next_round
        rng = Mock(wraps=SequenceRandom([10] * 36 + [7]))
        result = runner.run_npc_rounds(source, SpatialCandidates(), plans, rng)
        self.assertEqual(len(result.current.state.roster.participants), 4)
        self.assertEqual(result.current.round_state.completed_turn_entity_ids, ("brigand:0", "brigand:2"))
        self.assertEqual(len(result.current.round_state.participants), 2)
        self.assertEqual(len(result.current.state.consumed_execution_ids), 6)
        self.assertEqual(rng.randint.call_count, 36)
        self.assertEqual(rng.randint(1, 10), 7)
