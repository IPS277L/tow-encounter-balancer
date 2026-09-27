from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import Mock

from tests.helpers import SequenceRandom
from tests.unit.test_m2_npc_attack_conditions import with_conditions
from tests.unit.test_m2_npc_attack_controller import candidate
from tests.unit.test_m2_npc_round_advance import completed_context
from tests.unit.test_m2_npc_round_exclusion import defeat, exclude
from tests.unit.test_m2_npc_rounds_runner import NextRounds, SpatialCandidates, request
from towr.domain.condition_models import Condition
from towr.domain.npc_attack_selection_models import NpcAttackSelectionBlock as Block
from towr.domain.npc_round_advance_models import NpcRoundAdvanceRequest
from towr.domain.npc_rounds_models import NpcRoundsOutcome as Outcome, NpcRoundsRequest
from towr.domain.npc_rounds_summary_models import NpcRoundsSummary
from towr.domain.resolution_models import GiveGroundRequest
from towr.engine.npc_rounds_reporting import summarize_npc_rounds
from towr.engine.npc_rounds_runner import run_npc_rounds


class M2NpcRoundsSummaryTests(unittest.TestCase):
    def test_two_rounds_count_only_journal_attacks_with_absolute_round_numbers_on_both_sides(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                source = request(reverse=reverse)
                current = replace(source.current, round_state=replace(source.current.round_state, round_number=7),
                    state=replace(source.current.state, consumed_execution_ids=("old:1", "old:2"),
                        acknowledged_defeat_execution_ids=("old:1",), consumed_give_ground_execution_ids=("old:2",)))
                source = replace(source, current=current, spatial_state=replace(source.spatial_state, round_number=7))
                rng = Mock(wraps=SequenceRandom([10] * 48 + [7]))
                result = run_npc_rounds(source, SpatialCandidates(), NextRounds(), rng)
                before = deepcopy(result)
                summary = summarize_npc_rounds(result)
                self.assertIs(summary.source_result, result)
                self.assertEqual((summary.initial_round_number, summary.final_round_number), (7, 8))
                self.assertEqual((summary.visited_round_count, summary.newly_completed_round_count, summary.executed_attack_count), (2, 2, 8))
                self.assertIs(summary.outcome, Outcome.ROUND_LIMIT)
                self.assertIsNone(summary.blocked_reason)
                self.assertEqual(summary.pending_follow_up_count, 0)
                self.assertEqual(tuple(p.actor_id for p in summary.participants), tuple(f"brigand:{i}" for i in range(4)))
                for record in summary.participants:
                    state = result.current.state.roster.participant(record.actor_id).state
                    self.assertEqual((record.side, record.wounds, record.defeated, record.conditions),
                                     (state.side, 0, False, state.injury.conditions))
                    self.assertTrue(record.conditions.has(Condition.STAGGERED))
                self.assertEqual(summarize_npc_rounds(result), summary)
                self.assertEqual(rng.randint.call_count, 48)
                self.assertEqual(rng.randint(1, 10), 7)
                self.assertEqual(result, before)

    def test_complete_input_is_observed_but_not_newly_completed(self):
        for reverse in (False, True):
            completed = completed_context(reversed_sides=reverse)
            source = NpcRoundsRequest(completed.current, completed.spatial_state, 1)
            candidates, plans, rng = Mock(), Mock(), Mock()
            result = run_npc_rounds(source, candidates, plans, rng)
            summary = summarize_npc_rounds(result)
            self.assertEqual((summary.visited_round_count, summary.newly_completed_round_count, summary.executed_attack_count), (1, 0, 0))
            self.assertEqual(candidates.mock_calls + plans.mock_calls + rng.mock_calls, [])
            continued = run_npc_rounds(replace(source, max_rounds=2), SpatialCandidates(), NextRounds(), SequenceRandom([10] * 24))
            summary = summarize_npc_rounds(continued)
            self.assertEqual((summary.visited_round_count, summary.newly_completed_round_count, summary.executed_attack_count), (2, 1, 4))

    def test_initial_stops_preserve_reason_and_pending_without_inventing_actions(self):
        for reverse in (False, True):
            source = request(reverse=reverse)
            actor = source.current.next_actor(source.current.round_state)
            dead = defeat(source.current, int(actor[-1]))
            cases = [
                (replace(dead, pending_follow_ups=(GiveGroundRequest("one"), GiveGroundRequest("two"))), Outcome.PENDING_FOLLOW_UPS, None, 2),
                (dead, Outcome.DEFEATED_ACTOR, None, 0),
                (source.current, Outcome.SELECTION_BLOCKED, Block.NO_CANDIDATE, 0),
            ]
            for condition, reason in ((Condition.BROKEN, Block.ACTOR_BROKEN), (Condition.DEFENCELESS, Block.ACTOR_DEFENCELESS)):
                cases.append((replace(source.current, state=with_conditions(source.current.state, actor, (condition,))),
                              Outcome.SELECTION_BLOCKED, reason, 0))
            for current, outcome, reason, pending in cases:
                with self.subTest(reverse=reverse, reason=reason, outcome=outcome):
                    candidates, plans, rng = Mock(), Mock(), Mock()
                    candidates.get_candidates.side_effect = lambda c, s: c
                    summary = summarize_npc_rounds(run_npc_rounds(replace(source, current=current), candidates, plans, rng))
                    self.assertIs(summary.outcome, outcome)
                    self.assertIs(summary.blocked_reason, reason)
                    self.assertEqual(summary.pending_follow_up_count, pending)
                    self.assertEqual((summary.visited_round_count, summary.newly_completed_round_count, summary.executed_attack_count), (1, 0, 0))
                    self.assertEqual(plans.mock_calls + rng.mock_calls, [])

    def test_participants_use_first_appearance_not_turn_preference_and_omit_unused_roster_entries(self):
        source = request()
        members = source.current.round_state.participants
        current = replace(source.current, round_state=replace(source.current.round_state, participants=(members[0], members[2])),
                          actor_order=("brigand:2", "brigand:0"))
        source = replace(source, current=current)
        candidates, plans = Mock(), Mock()
        def supply(context, spatial):
            target = "brigand:0" if context.actor_id == "brigand:2" else "brigand:2"
            return replace(context, candidates=(candidate(context.state, context.id + ":candidate", target_id=target),))
        candidates.get_candidates.side_effect = supply
        plans.get_next_round.side_effect = lambda c, s: NpcRoundAdvanceRequest("next", c, s,
            (members[2], members[1], members[0]), ("brigand:1", "brigand:2", "brigand:0"))
        result = run_npc_rounds(source, candidates, plans, SequenceRandom([10] * 30))
        summary = summarize_npc_rounds(result)
        self.assertEqual(summary.executed_attack_count, 5)
        self.assertEqual(tuple(p.actor_id for p in summary.participants), ("brigand:0", "brigand:2", "brigand:1"))
        self.assertEqual(len(result.current.state.roster.participants), 4)

    def test_excluded_defeated_participant_keeps_final_injury_without_becoming_a_new_wound(self):
        source = request()
        current = exclude(defeat(source.current, 1), "brigand:1")
        candidates = Mock()
        candidates.get_candidates.side_effect = lambda c, s: c
        result = run_npc_rounds(replace(source, current=current), candidates, Mock(), Mock())
        summary = summarize_npc_rounds(result)
        record = next(p for p in summary.participants if p.actor_id == "brigand:1")
        self.assertEqual((record.wounds, record.defeated), (1, True))
        self.assertEqual(summary.executed_attack_count, 0)
        self.assertEqual(summary.newly_completed_round_count, 0)

    def test_summary_requires_source_and_cannot_accept_forged_derived_values(self):
        source = request(max_rounds=1)
        result = run_npc_rounds(source, SpatialCandidates(), NextRounds(), SequenceRandom([10] * 24))
        summary = summarize_npc_rounds(result)
        for value in (None, source, result.rounds[0], "result"):
            with self.assertRaises(TypeError):
                summarize_npc_rounds(value)
        with self.assertRaises(TypeError):
            NpcRoundsSummary(result, executed_attack_count=99)
        with self.assertRaises(FrozenInstanceError):
            summary.source_result = None
        with self.assertRaises(FrozenInstanceError):
            summary.participants[0].wounds = 99
        completed = run_npc_rounds(NpcRoundsRequest(result.current, result.spatial_state, 1), Mock(), Mock(), Mock())
        rebound = replace(summary, source_result=completed)
        self.assertIs(rebound.source_result, completed)
        self.assertEqual(rebound.executed_attack_count, 0)
        self.assertEqual(summary.executed_attack_count, 4)

    def test_participant_record_validates_explicit_types(self):
        completed = completed_context()
        result = run_npc_rounds(NpcRoundsRequest(completed.current, completed.spatial_state, 1), Mock(), Mock(), Mock())
        record = summarize_npc_rounds(result).participants[0]
        for changes, error in (({"actor_id": ""}, ValueError), ({"wounds": -1}, ValueError),
                               ({"wounds": True}, ValueError), ({"side": "opposition"}, TypeError),
                               ({"conditions": ()}, TypeError), ({"defeated": 1}, TypeError)):
            with self.subTest(changes=changes), self.assertRaises(error):
                replace(record, **changes)
