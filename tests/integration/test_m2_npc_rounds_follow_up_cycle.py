from copy import deepcopy
from dataclasses import replace
from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.integration.test_m2_mixed_round_cycle import MixedCandidates
from tests.unit.test_k1_kernel import FixedKernelDecisions
from tests.unit.test_k1_spatial_resolution import graph
from tests.unit.test_m2_minion_defeat import acknowledgement
from tests.unit.test_m2_npc_roster_attack_execution import change_participant
from tests.unit.test_m2_npc_round_coordinator import request
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.npc_give_ground_models import NpcGiveGroundExecutionRequest
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult
from towr.domain.npc_round_advance_models import NpcRoundAdvanceRequest
from towr.domain.npc_round_exclusion_models import NpcRoundExclusionRequest
from towr.domain.npc_rounds_models import NpcRoundsOutcome as Outcome, NpcRoundsRequest
from towr.domain.resolution_models import GiveGroundRequest, GiveGroundResolutionRequest
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement
from towr.domain.turn_models import CombatSide, CombatTurnEndResult
from towr.engine.npc_rounds_runner import run_npc_rounds
from towr.rules import attack_action_execution as attack_executor, npc_give_ground_resolution as give_ground
from towr.rules import minion_defeat_resolution as defeat, npc_round_exclusion as exclusion, npc_round_advance as advance


class FollowUpCandidates:
    def __init__(self, roles):
        self.roles = roles
        self.contexts = []

    def get_candidates(self, context, spatial_state):
        first, second, survivor, defeated = self.roles
        targets = {first: survivor, second: defeated, survivor: first, defeated: second}
        if context.round_state.round_number == 2:
            targets[second] = survivor
        supplied = MixedCandidates(spatial_state, targets).get_candidates(context)
        self.contexts.append((supplied, spatial_state))
        return supplied


class M2NpcRoundsFollowUpCycleTests(unittest.TestCase):
    def assert_pending_blocks(self, result):
        candidates, plans, rng = Mock(), Mock(), Mock()
        stopped = run_npc_rounds(NpcRoundsRequest(result.current, result.spatial_state, 2), candidates, plans, rng)
        self.assertIs(stopped.outcome, Outcome.PENDING_FOLLOW_UPS)
        self.assertEqual(stopped.current, result.current)
        self.assertIs(stopped.spatial_state, result.spatial_state)
        self.assertEqual(stopped.rounds[0].steps, ())
        self.assertEqual(stopped.advances, ())
        self.assertEqual(candidates.mock_calls + plans.mock_calls + rng.mock_calls, [])

    def test_real_follow_ups_resume_runner_into_next_round_for_both_sides_and_all_dispositions(self):
        for reverse, disposition in product((False, True), NpcDefeatDisposition):
            with self.subTest(reverse=reverse, disposition=disposition):
                roles = (("brigand:2", "brigand:3", "brigand:0", "brigand:1") if reverse else
                         ("brigand:0", "brigand:1", "brigand:2", "brigand:3"))
                first, second, survivor, defeated = roles
                source = request()
                self.assertEqual((source.state.consumed_execution_ids, source.state.consumed_give_ground_execution_ids,
                                  source.state.acknowledged_defeat_execution_ids), ((), (), ()))
                side_order = tuple(CombatSide)[::-1] if reverse else tuple(CombatSide)
                injury = source.state.roster.participant(survivor).state.injury
                source = replace(source, actor_order=(first, survivor, second, defeated),
                    round_state=replace(source.round_state, side_order=side_order),
                    state=change_participant(source.state, int(survivor[-1]), injury=replace(injury,
                        conditions=injury.conditions.with_condition(Condition.STAGGERED))))
                spatial = SpatialBattleState(graph(), tuple(
                    SpatialEntityPlacement(p.entity_id, p.side.value, "zone:a") for p in source.round_state.participants
                ), free_move_used_entity_ids=(first,), difficult_terrain_tested_entity_ids=(second,))
                original = deepcopy((source, spatial))
                provider, plans = FollowUpCandidates(roles), Mock()
                members = tuple(source.state.roster.participant(actor).turn_participant for actor in (first, second, survivor))
                plans.get_next_round.side_effect = lambda current, current_spatial: NpcRoundAdvanceRequest(
                    "follow-up:next", current, current_spatial, members, (second, survivor, first))
                rng = Mock(wraps=SequenceRandom([1, 10, 10, 10, 10, 10] + [1, 2, 10, 10, 10, 10] + [10] * 24 + [7]))
                decisions = FixedKernelDecisions(stagger=StaggerChoice.GIVE_GROUND)
                with (
                    patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel,
                    patch.object(give_ground, "resolve_give_ground", wraps=give_ground.resolve_give_ground) as move,
                    patch.object(give_ground, "consume_npc_give_ground", wraps=give_ground.consume_npc_give_ground) as consume,
                    patch.object(defeat, "acknowledge_minion_defeat", wraps=defeat.acknowledge_minion_defeat) as acknowledge,
                    patch.object(advance, "advance_combat_round", wraps=advance.advance_combat_round) as combat,
                    patch.object(advance, "start_next_spatial_round", wraps=advance.start_next_spatial_round) as reset,
                ):
                    first_stop = run_npc_rounds(NpcRoundsRequest(source, spatial, 2), provider, plans, rng, decisions=decisions)
                    first_before = deepcopy(first_stop)
                    self.assert_pending_blocks(first_stop)
                    plans.get_next_round.assert_not_called()
                    self.assertIsInstance(first_stop.current.pending_follow_ups[0], GiveGroundRequest)
                    attack1 = next(s for s in first_stop.rounds[0].steps if isinstance(s, NpcRosterAttackExecutionResult))
                    movement_request = NpcGiveGroundExecutionRequest("follow-up:gg", first_stop.current, first_stop.spatial_state,
                        attack1, GiveGroundResolutionRequest(first_stop.current.pending_follow_ups[0], first_stop.spatial_state,
                            survivor, "zone:b", first_stop.current.state.roster.participant(survivor).state.injury.conditions, first))
                    movement = give_ground.execute_npc_give_ground(movement_request)
                    moved, moved_spatial = give_ground.apply_npc_give_ground(first_stop.current, first_stop.spatial_state, movement)
                    self.assertEqual(moved.pending_follow_ups, ())
                    self.assertEqual(moved.state.consumed_give_ground_execution_ids, (attack1.execution.request_id,))
                    self.assertEqual(kernel.call_count, 1)
                    self.assertEqual(rng.randint.call_count, 6)

                    second_stop = run_npc_rounds(NpcRoundsRequest(moved, moved_spatial, 2), provider, plans, rng, decisions=decisions)
                    second_before = deepcopy(second_stop)
                    self.assert_pending_blocks(second_stop)
                    plans.get_next_round.assert_not_called()
                    self.assertIs(second_stop.spatial_state, moved_spatial)
                    self.assertEqual(second_stop.current.round_state.completed_turn_entity_ids, (first,))
                    attack2 = next(s for s in second_stop.rounds[0].steps if isinstance(s, NpcRosterAttackExecutionResult))
                    self.assertTrue(second_stop.current.state.roster.participant(defeated).state.injury.defeated)
                    with self.assertRaisesRegex(ValueError, "pending"):
                        NpcRoundExclusionRequest("too-early", second_stop.current, defeated)
                    confirmation = defeat.acknowledge_minion_defeat(acknowledgement(second_stop.current, attack2, disposition))
                    confirmed = defeat.apply_minion_defeat_acknowledgement(second_stop.current, confirmation)
                    self.assertEqual(confirmed.pending_follow_ups, ())
                    self.assertIs(confirmation.source_request.decision.disposition, disposition)
                    removed = exclusion.exclude_defeated_npc(NpcRoundExclusionRequest("follow-up:exclude", confirmed, defeated))
                    current = exclusion.apply_npc_round_exclusion(confirmed, removed)
                    self.assertEqual(current.round_state.excluded_turn_entity_ids, (defeated,))
                    self.assertEqual(kernel.call_count, 2)
                    self.assertEqual(rng.randint.call_count, 12)
                    final = run_npc_rounds(NpcRoundsRequest(current, moved_spatial, 2), provider, plans, rng, decisions=decisions)

                    self.assertIs(final.outcome, Outcome.ROUND_LIMIT)
                    self.assertEqual(len(final.completed_rounds), 2)
                    self.assertEqual(len(final.advances), 1)
                    transition = final.advances[0]
                    plans.get_next_round.assert_called_once_with(transition.source_request.current, moved_spatial)
                    combat.assert_called_once_with(transition.source_request.combat_request)
                    reset.assert_called_once_with(moved_spatial)
                    self.assertEqual(transition.source_request.current.round_state.completed_turn_entity_ids, (first, second, survivor))
                    self.assertEqual(transition.source_request.current.round_state.excluded_turn_entity_ids, (defeated,))
                    self.assertIs(transition.continuation.state, transition.source_request.current.state)
                    self.assertEqual(final.current.round_state.completed_turn_entity_ids, (second, first, survivor))
                    self.assertEqual(final.current.round_state.excluded_turn_entity_ids, ())
                    self.assertEqual(final.current.round_state.participants, members)
                    self.assertEqual(final.current.round_state.side_order, side_order)
                    self.assertEqual((final.current.round_state.round_number, final.spatial_state.round_number), (2, 2))
                    self.assertEqual(final.current.pending_follow_ups, ())
                    self.assertEqual(final.spatial_state.placements, moved_spatial.placements)
                    self.assertEqual(final.spatial_state.placement_for(survivor).zone_id, "zone:b")
                    self.assertEqual((moved_spatial.gave_ground_entity_ids, moved_spatial.free_move_used_entity_ids,
                                      moved_spatial.difficult_terrain_tested_entity_ids), ((survivor,), (first,), (second,)))
                    self.assertEqual((final.spatial_state.gave_ground_entity_ids, final.spatial_state.free_move_used_entity_ids,
                                      final.spatial_state.difficult_terrain_tested_entity_ids), ((), (), ()))
                    self.assertEqual(final.current.state.roster.participant(defeated), second_stop.current.state.roster.participant(defeated))
                    self.assertEqual(final.current.state.roster.participant(survivor).state.injury.conditions,
                                     moved.state.roster.participant(survivor).state.injury.conditions)

                    rounds = (*first_stop.rounds, *second_stop.rounds, *final.rounds)
                    attacks = tuple(s for r in rounds for s in r.steps if isinstance(s, NpcRosterAttackExecutionResult))
                    ids = tuple(a.execution.request_id for a in attacks)
                    self.assertEqual(len(set(ids)), 6)
                    self.assertEqual(final.current.state.consumed_execution_ids, ids)
                    self.assertEqual(final.current.state.consumed_give_ground_execution_ids, ids[:1])
                    self.assertEqual(final.current.state.acknowledged_defeat_execution_ids, ids[1:2])
                    for attack in attacks[2:]:
                        self.assertEqual(attack.source_request.state.consumed_give_ground_execution_ids, ids[:1])
                        self.assertEqual(attack.source_request.state.acknowledged_defeat_execution_ids, ids[1:2])
                    ended = tuple(s.completed_turn for r in rounds for s in r.steps if isinstance(s, CombatTurnEndResult))
                    self.assertEqual(tuple(t.action_slots[0].execution.id for t in ended), ids)
                    self.assertEqual(ended[:2], (first_stop.current.round_state.active_turn, second_stop.current.round_state.active_turn))
                    self.assertEqual(tuple(c.actor_id for c, _ in provider.contexts), (first, second, survivor, second, first, survivor))
                    self.assertIs(provider.contexts[0][1], spatial)
                    for context, supplied in provider.contexts[1:3]:
                        self.assertIs(supplied, moved_spatial)
                    for context, supplied in provider.contexts[3:]:
                        self.assertIs(supplied, final.spatial_state)
                        self.assertNotEqual(context.candidates[0].target_id, defeated)
                        self.assertFalse(context.candidates[0].target_has_given_ground_this_round)
                    self.assertEqual(provider.contexts[2][0].candidates[0].attack_profile_id, "warbow")

                    # Histories still refuse consequences after another round, including new IDs/requeued items.
                    with self.assertRaisesRegex(ValueError, "already consumed"):
                        replace(attack1.source_request, state=final.current.state)
                    with self.assertRaisesRegex(ValueError, "already consumed"):
                        give_ground.execute_npc_give_ground(replace(movement_request, id="replay:gg",
                            current=replace(final.current, pending_follow_ups=attack1.pending_follow_ups)))
                    with self.assertRaisesRegex(ValueError, "already acknowledged"):
                        replace(confirmation.source_request, id="replay:ack",
                                current=replace(final.current, pending_follow_ups=attack2.pending_follow_ups))
                    with self.assertRaisesRegex(ValueError, "source differs"):
                        give_ground.apply_npc_give_ground(final.current, final.spatial_state, movement)
                    with self.assertRaisesRegex(ValueError, "source differs"):
                        defeat.apply_minion_defeat_acknowledgement(final.current, confirmation)
                    with self.assertRaisesRegex(ValueError, "source differs"):
                        exclusion.apply_npc_round_exclusion(final.current, removed)
                    with self.assertRaisesRegex(ValueError, "source differs"):
                        advance.apply_npc_round_advance(final.current, final.spatial_state, transition)
                    unused_candidates, unused_plans, unused_rng = Mock(), Mock(), Mock()
                    repeated = run_npc_rounds(NpcRoundsRequest(final.current, final.spatial_state, 1),
                                             unused_candidates, unused_plans, unused_rng)
                    self.assertEqual(repeated.current, final.current)
                    self.assertEqual(unused_candidates.mock_calls + unused_plans.mock_calls + unused_rng.mock_calls, [])
                    self.assertEqual(kernel.call_count, 6)
                    move.assert_called_once_with(movement_request.movement)
                    consume.assert_called_once_with(movement.source_request)
                    acknowledge.assert_called_once_with(confirmation.source_request)
                    self.assertEqual(rng.randint.call_count, 36)
                    self.assertEqual(rng.randint(1, 10), 7)
                    self.assertEqual((source, spatial), original)
                    self.assertEqual(first_stop, first_before)
                    self.assertEqual(second_stop, second_before)
