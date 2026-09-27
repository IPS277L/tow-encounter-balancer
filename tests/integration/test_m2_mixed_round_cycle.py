from copy import deepcopy
from dataclasses import replace
from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_kernel import FixedKernelDecisions
from tests.unit.test_k1_spatial_resolution import graph
from tests.unit.test_m2_minion_defeat import acknowledgement
from tests.unit.test_m2_npc_attack_controller import candidate
from tests.unit.test_m2_npc_roster_attack_execution import change_participant
from tests.unit.test_m2_npc_round_coordinator import request, resume
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.npc_give_ground_models import NpcGiveGroundExecutionRequest
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult
from towr.domain.npc_round_advance_models import NpcRoundAdvanceRequest
from towr.domain.npc_round_exclusion_models import NpcRoundExclusionRequest
from towr.domain.npc_round_models import NpcRoundOutcome
from towr.domain.resolution_models import GiveGroundRequest, GiveGroundResolutionRequest
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement
from towr.domain.turn_models import CombatSide, CombatTurnEndResult
from towr.engine.npc_round_coordinator import run_npc_round
from towr.rules import attack_action_execution as attack_executor, npc_give_ground_resolution as give_ground
from towr.rules.minion_defeat_resolution import acknowledge_minion_defeat, apply_minion_defeat_acknowledgement
from towr.rules.npc_round_exclusion import exclude_defeated_npc, apply_npc_round_exclusion
from towr.rules import npc_round_advance as advance


class MixedCandidates:
    def __init__(self, spatial, targets):
        self.spatial = spatial
        self.targets = targets
        self.contexts = []

    def get_candidates(self, context):
        target = self.targets[context.actor_id]
        same_zone = self.spatial.placement_for(context.actor_id).zone_id == self.spatial.placement_for(target).zone_id
        proposed = candidate(context.state, context.id + ":candidate", target_id=target,
                             attack="axe" if same_zone else "warbow")
        proposed = replace(proposed, target_has_given_ground_this_round=target in self.spatial.gave_ground_entity_ids)
        supplied = replace(context, candidates=(proposed,))
        self.contexts.append((supplied, self.spatial))
        return supplied


class M2MixedRoundCycleTests(unittest.TestCase):
    def assert_pending_blocks(self, current):
        provider, rng = Mock(), Mock()
        stopped = run_npc_round(current, provider, rng)
        self.assertIs(stopped.outcome, NpcRoundOutcome.PENDING_FOLLOW_UPS)
        self.assertEqual(stopped.steps, ())
        self.assertEqual(stopped.pending_follow_ups, current.pending_follow_ups)
        provider.get_candidates.assert_not_called()
        rng.randint.assert_not_called()

    def test_give_ground_then_defeat_and_exclusion_preserve_all_histories_in_both_side_orders(self):
        self.check_mixed_cycle()

    def test_next_two_by_one_round_resets_usage_and_keeps_all_histories(self):
        self.check_mixed_cycle(advance_round=True)

    def check_mixed_cycle(self, *, advance_round=False):
        for reversed_sides, disposition in product((False, True), NpcDefeatDisposition):
            with self.subTest(reversed_sides=reversed_sides, disposition=disposition):
                first, second, survivor, defeated = (
                    ("brigand:2", "brigand:3", "brigand:0", "brigand:1") if reversed_sides
                    else ("brigand:0", "brigand:1", "brigand:2", "brigand:3")
                )
                side_order = tuple(reversed(tuple(CombatSide))) if reversed_sides else tuple(CombatSide)
                source = request()
                injury = source.state.roster.participant(survivor).state.injury
                source = replace(source, actor_order=(first, survivor, second, defeated),
                    round_state=replace(source.round_state, side_order=side_order),
                    state=change_participant(source.state, int(survivor[-1]), injury=replace(injury,
                        conditions=injury.conditions.with_condition(Condition.STAGGERED))))
                spatial = SpatialBattleState(graph(), tuple(
                    SpatialEntityPlacement(p.entity_id, p.side.value, "zone:a") for p in source.round_state.participants
                ), free_move_used_entity_ids=(first,), difficult_terrain_tested_entity_ids=(second,))
                original = deepcopy((source, spatial))
                provider = MixedCandidates(spatial, {first: survivor, second: defeated, survivor: first, defeated: second})
                rng = Mock(wraps=SequenceRandom([1, 10, 10, 10, 10, 10] + [1, 2, 10, 10, 10, 10] + [10] * 6 + [7]))
                decisions = FixedKernelDecisions(stagger=StaggerChoice.GIVE_GROUND)
                with (
                    patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel,
                    patch.object(give_ground, "resolve_give_ground", wraps=give_ground.resolve_give_ground) as move,
                    patch.object(give_ground, "consume_npc_give_ground", wraps=give_ground.consume_npc_give_ground) as register,
                ):
                    first_stop = run_npc_round(source, provider, rng, decisions=decisions)
                    attack1 = next(s for s in first_stop.steps if isinstance(s, NpcRosterAttackExecutionResult))
                    current = resume(source, first_stop)
                    self.assert_pending_blocks(current)
                    self.assertIsInstance(current.pending_follow_ups[0], GiveGroundRequest)
                    self.assertEqual(current.round_state.completed_turn_entity_ids, ())
                    movement_request = NpcGiveGroundExecutionRequest("mixed:give-ground", current, spatial, attack1,
                        GiveGroundResolutionRequest(current.pending_follow_ups[0], spatial, survivor, "zone:b",
                            current.state.roster.participant(survivor).state.injury.conditions, first))
                    movement = give_ground.execute_npc_give_ground(movement_request)
                    current, spatial = give_ground.apply_npc_give_ground(current, spatial, movement)
                    self.assertEqual(current.pending_follow_ups, ())
                    self.assertEqual(kernel.call_count, 1)
                    self.assertEqual(rng.randint.call_count, 6)
                    provider.spatial = spatial

                    second_stop = run_npc_round(current, provider, rng, decisions=decisions)
                    attack2 = next(s for s in second_stop.steps if isinstance(s, NpcRosterAttackExecutionResult))
                    current = resume(current, second_stop)
                    self.assert_pending_blocks(current)
                    self.assertEqual(current.round_state.completed_turn_entity_ids, (first,))
                    self.assertTrue(current.state.roster.participant(defeated).state.injury.defeated)
                    with self.assertRaisesRegex(ValueError, "pending"):
                        NpcRoundExclusionRequest("early", current, defeated)
                    confirmation = acknowledge_minion_defeat(acknowledgement(current, attack2, disposition))
                    current = apply_minion_defeat_acknowledgement(current, confirmation)
                    self.assertEqual(current.pending_follow_ups, ())
                    exclusion = exclude_defeated_npc(NpcRoundExclusionRequest("mixed:exclude", current, defeated))
                    current = apply_npc_round_exclusion(current, exclusion)
                    self.assertEqual(kernel.call_count, 2)
                    self.assertEqual(rng.randint.call_count, 12)
                    final = run_npc_round(current, provider, rng, decisions=decisions)
                    attack3 = next(s for s in final.steps if isinstance(s, NpcRosterAttackExecutionResult))
                    final_request = resume(current, final)

                    self.assertIs(final.outcome, NpcRoundOutcome.COMPLETE)
                    self.assertEqual(final.round_state.completed_turn_entity_ids, (first, second, survivor))
                    self.assertEqual(final.round_state.excluded_turn_entity_ids, (defeated,))
                    self.assertEqual(final.round_state.side_order, side_order)
                    self.assertEqual(final.round_state.round_number, 1)
                    self.assertEqual(final.round_state.participants, source.round_state.participants)
                    ids = tuple(a.execution.request_id for a in (attack1, attack2, attack3))
                    self.assertEqual(final.state.consumed_execution_ids, ids)
                    self.assertEqual(final.state.consumed_give_ground_execution_ids, ids[:1])
                    self.assertEqual(final.state.acknowledged_defeat_execution_ids, ids[1:2])
                    self.assertEqual(attack2.source_request.state.consumed_give_ground_execution_ids, ids[:1])
                    self.assertEqual(attack3.source_request.state.acknowledged_defeat_execution_ids, ids[1:2])
                    self.assertEqual(attack3.source_request.state.consumed_give_ground_execution_ids, ids[:1])
                    self.assertIs(confirmation.source_request.decision.disposition, disposition)
                    ended = tuple(s.completed_turn for result in (first_stop, second_stop, final)
                                  for s in result.steps if isinstance(s, CombatTurnEndResult))
                    self.assertEqual(tuple(t.actor_id for t in ended), (first, second, survivor))
                    self.assertEqual(tuple(t.action_slots[0].execution.id for t in ended), ids)
                    self.assertEqual(ended[:2], (first_stop.round_state.active_turn, second_stop.round_state.active_turn))
                    self.assertEqual(tuple(c.actor_id for c, _ in provider.contexts), (first, second, survivor))
                    self.assertIs(provider.contexts[0][1], movement_request.spatial_state)
                    self.assertIs(provider.contexts[1][1], movement.spatial_state)
                    self.assertIs(provider.contexts[2][1], movement.spatial_state)
                    self.assertEqual(provider.contexts[2][0].candidates[0].attack_profile_id, "warbow")
                    self.assertEqual(spatial.placement_for(survivor).zone_id, "zone:b")
                    self.assertEqual(spatial.gave_ground_entity_ids, (survivor,))
                    self.assertEqual(spatial.free_move_used_entity_ids, (first,))
                    self.assertEqual(spatial.difficult_terrain_tested_entity_ids, (second,))
                    self.assertEqual(final.state.roster.participant(defeated), second_stop.state.roster.participant(defeated))
                    self.assertEqual((source, movement_request.spatial_state), original)

                    # Returned histories reject old consequences even if callers requeue them and change IDs.
                    with self.assertRaisesRegex(ValueError, "already consumed"):
                        give_ground.execute_npc_give_ground(replace(movement_request, id="new-movement-id",
                            current=replace(final_request, pending_follow_ups=attack1.pending_follow_ups)))
                    with self.assertRaisesRegex(ValueError, "already acknowledged"):
                        replace(confirmation.source_request, id="new-ack-id",
                                current=replace(final_request, pending_follow_ups=attack2.pending_follow_ups))
                    with self.assertRaisesRegex(ValueError, "source differs"):
                        give_ground.apply_npc_give_ground(final_request, spatial, movement)
                    with self.assertRaisesRegex(ValueError, "source differs"):
                        apply_minion_defeat_acknowledgement(final_request, confirmation)
                    with self.assertRaisesRegex(ValueError, "source differs"):
                        apply_npc_round_exclusion(final_request, exclusion)
                    self.assertEqual(kernel.call_count, 3)
                    move.assert_called_once_with(movement_request.movement)
                    register.assert_called_once_with(movement.source_request)
                    self.assertEqual(rng.randint.call_count, 18)
                    self.assertEqual(rng.randint(1, 10), 7)
                    if advance_round:
                        self.check_next_round(final_request, spatial, provider, (first, second, survivor, defeated))
                        self.assertEqual(kernel.call_count, 6)
                        move.assert_called_once()
                        register.assert_called_once()

    def check_next_round(self, current, spatial, provider, roles):
        first, second, survivor, defeated = roles
        participants = tuple(current.state.roster.participant(actor).turn_participant for actor in (first, second, survivor))
        before = deepcopy((current, spatial))
        request = NpcRoundAdvanceRequest("mixed:round:2", current, spatial, participants, (second, survivor, first))
        with (
            patch.object(advance, "advance_combat_round", wraps=advance.advance_combat_round) as combat,
            patch.object(advance, "start_next_spatial_round", wraps=advance.start_next_spatial_round) as placement,
        ):
            result = advance.advance_npc_round(request)
        combat.assert_called_once_with(request.combat_request)
        placement.assert_called_once_with(spatial)
        upcoming, next_spatial = advance.apply_npc_round_advance(current, spatial, result)
        self.assertEqual((current, spatial), before)
        self.assertIs(upcoming.state, current.state)
        self.assertEqual((upcoming.round_state.round_number, next_spatial.round_number), (2, 2))
        self.assertEqual(upcoming.round_state.side_order, current.round_state.side_order)
        self.assertIsNone(upcoming.round_state.active_turn)
        self.assertEqual(upcoming.round_state.completed_turn_entity_ids, ())
        self.assertEqual(upcoming.round_state.excluded_turn_entity_ids, ())
        self.assertEqual((next_spatial.gave_ground_entity_ids, next_spatial.free_move_used_entity_ids,
                          next_spatial.difficult_terrain_tested_entity_ids), ((), (), ()))
        self.assertEqual(next_spatial.placements, spatial.placements)
        self.assertEqual(upcoming.state.roster.participant(survivor).state.injury.conditions,
                         current.state.roster.participant(survivor).state.injury.conditions)
        provider.spatial = next_spatial
        provider.targets[second] = survivor
        rng = Mock(wraps=SequenceRandom([10] * 18 + [8]))
        next_result = run_npc_round(upcoming, provider, rng)
        self.assertIs(next_result.outcome, NpcRoundOutcome.COMPLETE)
        self.assertEqual(next_result.round_state.completed_turn_entity_ids, (second, first, survivor))
        self.assertEqual(next_result.round_state.participants, participants)
        self.assertEqual(next_result.round_state.excluded_turn_entity_ids, ())
        self.assertEqual(next_result.state.roster.participant(defeated), current.state.roster.participant(defeated))
        self.assertEqual(next_result.state.consumed_execution_ids[:3], current.state.consumed_execution_ids)
        self.assertEqual(next_result.state.consumed_give_ground_execution_ids, current.state.consumed_give_ground_execution_ids)
        self.assertEqual(next_result.state.acknowledged_defeat_execution_ids, current.state.acknowledged_defeat_execution_ids)
        attacks = tuple(s for s in next_result.steps if isinstance(s, NpcRosterAttackExecutionResult))
        self.assertEqual(len(attacks), 3)
        new_ids = tuple(a.execution.request_id for a in attacks)
        self.assertFalse(set(new_ids) & set(current.state.consumed_execution_ids))
        self.assertEqual(next_result.state.consumed_execution_ids[3:], new_ids)
        for attack in attacks:
            slot = attack.source_request.execution.state.active_turn.action_slots[0]
            self.assertFalse(slot.executed)
            self.assertEqual(attack.execution.state.active_turn.action_slots[0].execution.round_number, 2)
        self.assertEqual(tuple(c.actor_id for c, _ in provider.contexts[-3:]), (second, first, survivor))
        for context, supplied_spatial in provider.contexts[-3:]:
            self.assertIs(supplied_spatial, next_spatial)
            self.assertFalse(context.candidates[0].target_has_given_ground_this_round)
            self.assertNotEqual(context.candidates[0].target_id, defeated)
        self.assertEqual(rng.randint.call_count, 18)
        self.assertEqual(rng.randint(1, 10), 8)
        with self.assertRaisesRegex(ValueError, "source differs"):
            advance.apply_npc_round_advance(upcoming, next_spatial, result)
        with self.assertRaisesRegex(ValueError, "source differs"):
            advance.apply_npc_round_advance(resume(upcoming, next_result), next_spatial, result)
