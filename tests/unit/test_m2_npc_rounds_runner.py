from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_spatial_resolution import graph
from tests.unit.test_m2_npc_attack_conditions import with_conditions
from tests.unit.test_m2_npc_round_advance import completed_context
from tests.unit.test_m2_npc_round_coordinator import Candidates, request as round_request
from tests.unit.test_m2_npc_round_exclusion import defeat
from towr.domain.condition_models import Condition
from towr.domain.npc_attack_selection_models import NpcAttackSelectionBlock as Block
from towr.domain.npc_round_advance_models import NpcRoundAdvanceRequest
from towr.domain.npc_rounds_models import NpcRoundsOutcome as Outcome, NpcRoundsRequest, NpcRoundsResult
from towr.domain.resolution_models import GiveGroundRequest
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement
from towr.engine import npc_rounds_runner as runner


def request(*, max_rounds=2, reverse=False):
    current = round_request()
    if reverse:
        current = replace(current, round_state=replace(current.round_state, side_order=current.round_state.side_order[::-1]))
    spatial = SpatialBattleState(graph(), tuple(
        SpatialEntityPlacement(p.entity_id, p.side.value, "zone:a") for p in current.round_state.participants
    ), gave_ground_entity_ids=("brigand:0",), free_move_used_entity_ids=("brigand:1",),
       difficult_terrain_tested_entity_ids=("brigand:2",))
    return NpcRoundsRequest(current, spatial, max_rounds)


class SpatialCandidates:
    def __init__(self):
        self.contexts = []

    def get_candidates(self, context, spatial_state):
        self.contexts.append((context, spatial_state))
        proposed = Candidates().get_candidates(context)
        return replace(proposed, candidates=tuple(replace(c,
            target_has_given_ground_this_round=c.target_id in spatial_state.gave_ground_entity_ids)
            for c in proposed.candidates))


class NextRounds:
    def __init__(self):
        self.contexts = []

    def get_next_round(self, current, spatial_state):
        self.contexts.append((current, spatial_state))
        return NpcRoundAdvanceRequest(f"advance:{current.round_state.round_number}", current, spatial_state,
                                      current.round_state.participants, current.actor_order[::-1])


class M2NpcRoundsRunnerTests(unittest.TestCase):
    def test_request_rejects_invalid_limit_types_and_spatial_context(self):
        source = request()
        for limit in (0, -1, True, False, 1.5, "2", None):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                replace(source, max_rounds=limit)
        for changes in ({"current": None}, {"spatial_state": None}):
            with self.assertRaises(TypeError):
                replace(source, **changes)
        for spatial in (replace(source.spatial_state, round_number=2),
                        replace(source.spatial_state, placements=source.spatial_state.placements[1:], gave_ground_entity_ids=()),
                        replace(source.spatial_state, placements=(replace(source.spatial_state.placements[0],
                            side_id="wrong"), *source.spatial_state.placements[1:]))):
            with self.assertRaises(ValueError):
                replace(source, spatial_state=spatial)
        with self.assertRaises(TypeError):
            runner.run_npc_rounds(None, Mock(), Mock(), Mock())

    def test_initial_pending_and_defeated_stop_without_any_provider_or_rng(self):
        source = request()
        defeated = defeat(source.current, 0)
        cases = ((defeated, Outcome.DEFEATED_ACTOR),
                 (replace(defeated, pending_follow_ups=(GiveGroundRequest("pending"),)), Outcome.PENDING_FOLLOW_UPS))
        for current, expected in cases:
            with self.subTest(expected=expected):
                candidates, plans, rng = Mock(), Mock(), Mock()
                value = replace(source, current=current)
                before = deepcopy(value)
                with patch.object(runner, "advance_npc_round") as advance:
                    result = runner.run_npc_rounds(value, candidates, plans, rng)
                self.assertIs(result.outcome, expected)
                self.assertEqual(result.current, current)
                self.assertIs(result.spatial_state, value.spatial_state)
                self.assertEqual(result.completed_rounds, ())
                self.assertEqual(result.rounds[0].steps, ())
                self.assertEqual(result.advances, ())
                self.assertEqual(candidates.mock_calls + plans.mock_calls + rng.mock_calls, [])
                advance.assert_not_called()
                self.assertEqual(value, before)

    def test_blocked_actor_on_either_side_keeps_slot_and_repeated_run_does_not_execute(self):
        for reverse in (False, True):
            for condition, reason in ((Condition.BROKEN, Block.ACTOR_BROKEN),
                                      (Condition.DEFENCELESS, Block.ACTOR_DEFENCELESS)):
                with self.subTest(reverse=reverse, condition=condition):
                    source = request(reverse=reverse)
                    actor = source.current.next_actor(source.current.round_state)
                    current = replace(source.current, state=with_conditions(source.current.state, actor, (condition,)))
                    source = replace(source, current=current)
                    candidates, plans, rng = SpatialCandidates(), Mock(), Mock()
                    result = runner.run_npc_rounds(source, candidates, plans, rng)
                    repeated = runner.run_npc_rounds(replace(source, current=result.current), candidates, plans, rng)
                    self.assertIs(result.outcome, Outcome.SELECTION_BLOCKED)
                    self.assertIs(result.rounds[0].blocked_selection.blocked_reason, reason)
                    self.assertEqual(result.current, repeated.current)
                    self.assertEqual(result.current.state, current.state)
                    self.assertEqual(len(result.current.round_state.active_turn.action_slots), 1)
                    self.assertFalse(result.current.round_state.active_turn.action_slots[0].executed)
                    self.assertEqual(plans.mock_calls + rng.mock_calls, [])

    def test_completed_input_counts_toward_limit_without_reexecuting_receipts(self):
        completed = completed_context()
        source = NpcRoundsRequest(completed.current, completed.spatial_state, 1)
        candidates, plans, rng = Mock(), Mock(), Mock()
        result = runner.run_npc_rounds(source, candidates, plans, rng)
        self.assertIs(result.outcome, Outcome.ROUND_LIMIT)
        self.assertEqual(len(result.completed_rounds), 1)
        self.assertEqual(result.current, completed.current)
        self.assertEqual(result.rounds[0].steps, ())
        self.assertEqual(candidates.mock_calls + plans.mock_calls + rng.mock_calls, [])
        # With budget for two observed rounds, only the next round actually acts.
        candidates, plans = SpatialCandidates(), NextRounds()
        rng = Mock(wraps=SequenceRandom([10] * 24 + [7]))
        continued = runner.run_npc_rounds(replace(source, max_rounds=2), candidates, plans, rng)
        self.assertEqual(len(continued.completed_rounds), 2)
        self.assertEqual(len(plans.contexts), 1)
        self.assertEqual(rng.randint.call_count, 24)
        self.assertEqual(rng.randint(1, 10), 7)
        self.assertEqual(continued.current.state.consumed_execution_ids[:4], source.current.state.consumed_execution_ids)

    def test_stale_or_malformed_next_plan_fails_before_advance_and_new_round_rng(self):
        base = completed_context()
        source = NpcRoundsRequest(base.current, base.spatial_state, 2)
        stale_current = replace(base.current, state=replace(base.current.state,
            acknowledged_defeat_execution_ids=(base.current.state.consumed_execution_ids[0],)))
        variants = (None, replace(base, current=stale_current),
                    replace(base, spatial_state=replace(base.spatial_state, free_move_used_entity_ids=())))
        for planned in variants:
            with self.subTest(planned=planned):
                provider, candidates, rng = Mock(), Mock(), Mock()
                provider.get_next_round.return_value = planned
                with patch.object(runner, "advance_npc_round") as advance:
                    with self.assertRaises((TypeError, ValueError)):
                        runner.run_npc_rounds(source, candidates, provider, rng)
                advance.assert_not_called()
                self.assertEqual(candidates.mock_calls + rng.mock_calls, [])
                provider.get_next_round.assert_called_once_with(source.current, source.spatial_state)

    def test_result_rejects_truncated_reordered_or_foreign_journals(self):
        source = request()
        result = runner.run_npc_rounds(source, SpatialCandidates(), NextRounds(), SequenceRandom([10] * 48))
        for changes in ({"rounds": ()}, {"advances": ()}, {"rounds": result.rounds[::-1]},
                        {"rounds": result.rounds[:1], "advances": ()},
                        {"source_request": replace(source, max_rounds=1)},
                        {"source_request": replace(source, spatial_state=replace(source.spatial_state,
                            gave_ground_entity_ids=()))}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(result, **changes)
        for changes in ({"source_request": None}, {"rounds": (None,)}, {"advances": (None,)}):
            with self.assertRaises(TypeError):
                replace(result, **changes)
        normalized = replace(result, rounds=list(result.rounds), advances=list(result.advances))
        self.assertEqual(normalized, result)
        with self.assertRaises(FrozenInstanceError):
            result.rounds = ()

    def test_result_cannot_continue_after_block_or_swap_advance_source(self):
        source = request()
        completed = runner.run_npc_rounds(source, SpatialCandidates(), NextRounds(), SequenceRandom([10] * 48))
        empty = Mock()
        empty.get_candidates.side_effect = lambda context, spatial: context
        blocked = runner.run_npc_rounds(source, empty, Mock(), Mock())
        with self.assertRaisesRegex(ValueError, "blocking"):
            NpcRoundsResult(source, (blocked.rounds[0], completed.rounds[1]), completed.advances)
        advance = completed.advances[0]
        foreign = runner.advance_npc_round(replace(advance.source_request,
            spatial_state=replace(advance.source_request.spatial_state, gave_ground_entity_ids=())))
        with self.assertRaisesRegex(ValueError, "source snapshots"):
            replace(completed, advances=(foreign,))

    def test_provider_errors_propagate_without_mutating_inputs(self):
        source = request()
        before = deepcopy(source)
        bad, rng = Mock(), Mock()
        bad.get_candidates.side_effect = RuntimeError("provider failed")
        with self.assertRaisesRegex(RuntimeError, "provider failed"):
            runner.run_npc_rounds(source, bad, Mock(), rng)
        rng.randint.assert_not_called()
        bad.get_candidates.side_effect = lambda context, spatial: replace(context, id="foreign")
        with self.assertRaisesRegex(ValueError, "changed"):
            runner.run_npc_rounds(source, bad, Mock(), rng)
        rng.randint.assert_not_called()
        plans = Mock()
        plans.get_next_round.side_effect = RuntimeError("plan failed")
        used = Mock(wraps=SequenceRandom([10] * 24 + [7]))
        with self.assertRaisesRegex(RuntimeError, "plan failed"):
            runner.run_npc_rounds(source, SpatialCandidates(), plans, used)
        self.assertEqual(used.randint.call_count, 24)
        self.assertEqual(used.randint(1, 10), 7)
        self.assertEqual(source, before)

    def test_next_plan_still_requires_two_sides_and_excludes_defeated(self):
        base = completed_context()
        for current, participants in ((base.current, base.current.round_state.participants[:2]),
                                      (defeat(base.current, 3), base.current.round_state.participants)):
            source = NpcRoundsRequest(current, base.spatial_state, 2)
            provider = Mock()
            provider.get_next_round.side_effect = lambda c, s: NpcRoundAdvanceRequest(
                "bad", c, s, participants, tuple(p.entity_id for p in participants))
            rng = Mock()
            with patch.object(runner, "advance_npc_round") as advance:
                with self.assertRaises(ValueError):
                    runner.run_npc_rounds(source, Mock(), provider, rng)
            advance.assert_not_called()
            rng.randint.assert_not_called()

    def test_foreign_round_or_advance_result_is_rejected_before_further_execution(self):
        base = completed_context()
        source = NpcRoundsRequest(base.current, base.spatial_state, 2)
        completed = runner.run_npc_rounds(replace(source, max_rounds=1), Mock(), Mock(), Mock()).rounds[0]
        foreign_round = replace(completed, source_request=replace(completed.source_request, id="foreign"))
        plans, rng = Mock(), Mock()
        with patch.object(runner, "run_npc_round", return_value=foreign_round):
            with self.assertRaisesRegex(ValueError, "executed request"):
                runner.run_npc_rounds(source, Mock(), plans, rng)
        plans.get_next_round.assert_not_called()
        plans.get_next_round.return_value = base
        foreign_advance = runner.advance_npc_round(replace(base, id="foreign"))
        with patch.object(runner, "advance_npc_round", return_value=foreign_advance):
            with self.assertRaisesRegex(ValueError, "planned request"):
                runner.run_npc_rounds(source, Mock(), plans, rng)
        rng.randint.assert_not_called()
