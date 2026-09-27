from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import Mock

from tests.helpers import SequenceRandom
from tests.unit.test_m2_npc_attack_conditions import with_conditions
from tests.unit.test_m2_npc_round_advance import completed_context
from tests.unit.test_m2_npc_round_exclusion import defeat
from tests.unit.test_m2_npc_rounds_runner import NextRounds, SpatialCandidates, request
from towr.domain.condition_models import Condition
from towr.domain.npc_attack_selection_models import NpcAttackSelectionBlock as Block
from towr.domain.npc_rounds_chain_summary_models import NpcRoundsChainSummary
from towr.domain.npc_rounds_models import NpcRoundsOutcome as Outcome, NpcRoundsRequest
from towr.domain.resolution_models import GiveGroundRequest
from towr.engine.npc_rounds_reporting import summarize_npc_rounds_chain
from towr.engine.npc_rounds_runner import run_npc_rounds
from towr.rules.npc_round_advance import advance_npc_round


def completed_chain(reverse=False):
    context = completed_context(reversed_sides=reverse)
    first = run_npc_rounds(NpcRoundsRequest(context.current, context.spatial_state, 1), Mock(), Mock(), Mock())
    advance = advance_npc_round(context)
    last = run_npc_rounds(NpcRoundsRequest(advance.continuation, advance.spatial_state, 1),
                          SpatialCandidates(), NextRounds(), SequenceRandom([10] * 24))
    return first, advance, last


class M2NpcRoundsChainSummaryTests(unittest.TestCase):
    def test_explicit_advance_counts_only_new_actions_and_keeps_exact_sources_on_both_sides(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                steps = completed_chain(reverse)
                before = deepcopy(steps)
                summary = summarize_npc_rounds_chain(steps)
                self.assertEqual(tuple(s.executed_attack_count for s in summary.call_summaries), (0, 4))
                self.assertEqual((summary.visited_round_count, summary.newly_completed_round_count,
                                  summary.executed_attack_count), (2, 1, 4))
                self.assertEqual((summary.initial_round_number, summary.final_round_number), (1, 2))
                self.assertEqual(summary.current, steps[-1].current)
                self.assertIs(summary.spatial_state, steps[-1].spatial_state)
                self.assertIs(summary.outcome, Outcome.ROUND_LIMIT)
                self.assertEqual(summary.defeat_acknowledgements, ())
                self.assertEqual(summary.participants, summary.final_summary.participants)
                self.assertEqual(len(summary.current.state.consumed_execution_ids), 8)
                for source, retained in zip(steps, summary.source_steps):
                    self.assertIs(source, retained)
                self.assertEqual(summarize_npc_rounds_chain(steps), summary)
                self.assertEqual(steps, before)

    def test_missing_reordered_replayed_and_foreign_advance_are_rejected(self):
        first, advance, last = completed_chain()
        foreign = advance_npc_round(replace(advance.source_request,
            current=replace(advance.source_request.current, id="foreign")))
        for steps in ((first, last), (last, advance, first), (first, advance, advance, last),
                      (first, foreign, last), (first, advance, last, first)):
            with self.subTest(steps=len(steps)), self.assertRaisesRegex(ValueError, "source differs"):
                summarize_npc_rounds_chain(steps)

    def test_spatial_changes_cannot_be_hidden_at_advance_or_runner_boundary(self):
        first, advance, last = completed_chain()
        spatial = replace(first.spatial_state, free_move_used_entity_ids=())
        foreign = advance_npc_round(replace(advance.source_request, spatial_state=spatial))
        with self.assertRaisesRegex(ValueError, "spatial snapshot"):
            summarize_npc_rounds_chain((first, foreign, last))
        changed = replace(last.source_request.spatial_state, free_move_used_entity_ids=("brigand:0",))
        foreign_call = run_npc_rounds(replace(last.source_request, spatial_state=changed),
                                     SpatialCandidates(), NextRounds(), SequenceRandom([10] * 24))
        with self.assertRaisesRegex(ValueError, "spatial snapshot"):
            summarize_npc_rounds_chain((first, advance, foreign_call))

    def test_complete_and_blocked_no_op_calls_do_not_duplicate_actions_or_round_completions(self):
        first, advance, last = completed_chain()
        repeated = run_npc_rounds(NpcRoundsRequest(last.current, last.spatial_state, 1), Mock(), Mock(), Mock())
        summary = summarize_npc_rounds_chain((first, advance, last, repeated, repeated))
        self.assertEqual((summary.visited_round_count, summary.newly_completed_round_count,
                          summary.executed_attack_count), (2, 1, 4))
        source = request()
        provider = Mock()
        provider.get_candidates.side_effect = lambda c, s: c
        blocked = run_npc_rounds(source, provider, Mock(), Mock())
        resumed = run_npc_rounds(replace(source, current=blocked.current),
                               SpatialCandidates(), NextRounds(), SequenceRandom([10] * 48))
        summary = summarize_npc_rounds_chain((blocked, resumed))
        self.assertEqual(tuple(s.executed_attack_count for s in summary.call_summaries), (0, 8))
        self.assertEqual((summary.visited_round_count, summary.newly_completed_round_count), (2, 2))
        self.assertIsNone(summary.blocked_reason)

    def test_final_stop_reasons_are_not_terminal_outcomes(self):
        for reverse in (False, True):
            source = request(reverse=reverse)
            actor = source.current.next_actor(source.current.round_state)
            cases = [(replace(source.current, pending_follow_ups=(GiveGroundRequest("one"),)),
                      Outcome.PENDING_FOLLOW_UPS, None, 1),
                     (defeat(source.current, int(actor[-1])), Outcome.DEFEATED_ACTOR, None, 0),
                     (source.current, Outcome.SELECTION_BLOCKED, Block.NO_CANDIDATE, 0)]
            for condition, reason in ((Condition.BROKEN, Block.ACTOR_BROKEN),
                                      (Condition.DEFENCELESS, Block.ACTOR_DEFENCELESS)):
                cases.append((replace(source.current, state=with_conditions(source.current.state, actor, (condition,))),
                              Outcome.SELECTION_BLOCKED, reason, 0))
            for current, outcome, reason, pending in cases:
                provider = Mock()
                provider.get_candidates.side_effect = lambda c, s: c
                rng = Mock()
                result = run_npc_rounds(replace(source, current=current), provider, Mock(), rng)
                summary = summarize_npc_rounds_chain((result,))
                self.assertEqual((summary.outcome, summary.blocked_reason, summary.pending_follow_up_count),
                                 (outcome, reason, pending))
                self.assertEqual((summary.executed_attack_count, summary.newly_completed_round_count), (0, 0))
                self.assertEqual(summary.defeat_acknowledgements, ())
                self.assertEqual(rng.mock_calls, [])

    def test_participants_keep_earlier_compositions_and_final_conditions(self):
        source = request(max_rounds=1)
        first = run_npc_rounds(source, SpatialCandidates(), NextRounds(), SequenceRandom([10] * 24))
        members = first.current.round_state.participants
        plan = NextRounds().get_next_round(first.current, first.spatial_state)
        advance = advance_npc_round(replace(plan, next_round_participants=(members[2], members[0]),
                                            next_actor_order=("brigand:2", "brigand:0")))
        provider = Mock()
        provider.get_candidates.side_effect = lambda c, s: c
        last = run_npc_rounds(NpcRoundsRequest(advance.continuation, advance.spatial_state, 1), provider, Mock(), Mock())
        summary = summarize_npc_rounds_chain((first, advance, last))
        self.assertEqual(tuple(p.actor_id for p in summary.final_summary.participants), ("brigand:2", "brigand:0"))
        self.assertEqual(tuple(p.actor_id for p in summary.participants), tuple(f"brigand:{i}" for i in range(4)))
        for record in summary.participants:
            self.assertEqual(record.conditions, last.current.state.roster.participant(record.actor_id).state.injury.conditions)

    def test_requires_completed_typed_sources_and_runner_endpoints_and_is_immutable(self):
        steps = completed_chain()
        for invalid in (None, (None,), (steps[0].source_request,), (steps[0].rounds[0],)):
            with self.assertRaises(TypeError):
                summarize_npc_rounds_chain(invalid)
        for invalid in ((), steps[1:], steps[:-1]):
            with self.assertRaisesRegex(ValueError, "begin and end"):
                summarize_npc_rounds_chain(invalid)
        supplied = list(steps)
        summary = summarize_npc_rounds_chain(supplied)
        supplied.clear()
        self.assertEqual(summary.source_steps, steps)
        with self.assertRaises(FrozenInstanceError):
            summary.source_steps = ()
        with self.assertRaises(TypeError):
            NpcRoundsChainSummary(steps, executed_attack_count=99)
        with self.assertRaises(ValueError):
            replace(summary, source_steps=(steps[0], steps[-1]))
