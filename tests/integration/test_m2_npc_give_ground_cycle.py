from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_m2_npc_give_ground import context
from tests.unit.test_m2_npc_attack_controller import candidate
from towr.domain.condition_models import Condition
from towr.domain.npc_round_models import NpcRoundOutcome
from towr.domain.turn_models import CombatTurnEndResult
from towr.engine.npc_round_coordinator import run_npc_round
from towr.rules import attack_action_execution as attack_executor, spatial_resolution
from towr.rules.npc_give_ground_resolution import consume_npc_give_ground, apply_npc_give_ground


class SpatialCandidates:
    def __init__(self, spatial):
        self.spatial = spatial
        self.contexts = []

    def get_candidates(self, context):
        self.contexts.append(context)
        # Eligibility beyond defeat remains explicit. A Broken actor is not asked to Attack.
        if context.state.roster.participant(context.actor_id).state.injury.conditions.has(Condition.BROKEN):
            return context
        target = {"brigand:1": "brigand:3", "brigand:2": "brigand:0", "brigand:3": "brigand:1"}[context.actor_id]
        same_zone = self.spatial.placement_for(context.actor_id).zone_id == self.spatial.placement_for(target).zone_id
        proposed = candidate(context.state, context.id + ":candidate", target_id=target,
                             attack="axe" if same_zone else "warbow")
        proposed = replace(proposed, target_has_given_ground_this_round=target in self.spatial.gave_ground_entity_ids)
        return replace(context, candidates=(proposed,))


class M2NpcGiveGroundCycleTests(unittest.TestCase):
    def test_safe_movement_resumes_original_receipt_and_carries_history_through_remaining_attacks(self):
        with (
            patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel,
            patch.object(spatial_resolution, "resolve_give_ground", wraps=spatial_resolution.resolve_give_ground) as move,
        ):
            source = context()
            self.assertEqual(kernel.call_count, 1)
            self.assertEqual(move.call_count, 1)
            result = consume_npc_give_ground(source)
            current, spatial = apply_npc_give_ground(source.current, source.spatial_state, result)
            provider = SpatialCandidates(spatial)
            rng = Mock(wraps=SequenceRandom([10] * 18 + [7]))
            completed = run_npc_round(current, provider, rng)
            self.assertEqual(kernel.call_count, 4)
            self.assertEqual(move.call_count, 1)
        self.assertIs(completed.outcome, NpcRoundOutcome.COMPLETE)
        self.assertIsInstance(completed.steps[0], CombatTurnEndResult)
        self.assertEqual(completed.steps[0].completed_turn, source.current.round_state.active_turn)
        self.assertEqual(len(completed.state.consumed_execution_ids), 4)
        self.assertEqual(completed.state.consumed_give_ground_execution_ids, (source.attack.execution.request_id,))
        self.assertEqual(tuple(c.actor_id for c in provider.contexts), ("brigand:1", "brigand:2", "brigand:3"))
        self.assertTrue(all(c.state.consumed_give_ground_execution_ids == (source.attack.execution.request_id,)
                            for c in provider.contexts))
        self.assertEqual(spatial.placement_for("brigand:2").zone_id, "zone:b")
        self.assertEqual(spatial.gave_ground_entity_ids, ("brigand:2",))
        self.assertEqual(rng.randint.call_count, 18)
        self.assertEqual(rng.randint(1, 10), 7)
        # Spatial once-per-round guard still refuses another movement for this target.
        with self.assertRaisesRegex(ValueError, "once per round"):
            spatial_resolution.resolve_give_ground(replace(source.movement.source_request,
                state=spatial, destination_zone_id="zone:c"))

    def test_enemy_zone_broken_reaches_fresh_context_and_provider_stops_that_actor(self):
        with (
            patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel,
            patch.object(spatial_resolution, "resolve_give_ground", wraps=spatial_resolution.resolve_give_ground) as move,
        ):
            source = context(enemy_zone=True)
            current, spatial = apply_npc_give_ground(source.current, source.spatial_state, consume_npc_give_ground(source))
            provider = SpatialCandidates(spatial)
            rng = Mock(wraps=SequenceRandom([10] * 6 + [7]))
            stopped = run_npc_round(current, provider, rng)
            self.assertEqual(kernel.call_count, 2)
            self.assertEqual(move.call_count, 1)
        self.assertIs(stopped.outcome, NpcRoundOutcome.SELECTION_BLOCKED)
        self.assertEqual(stopped.round_state.completed_turn_entity_ids, ("brigand:0", "brigand:1"))
        self.assertEqual(stopped.round_state.active_turn.actor_id, "brigand:2")
        self.assertFalse(stopped.round_state.active_turn.action_slots[0].executed)
        self.assertEqual(tuple(c.actor_id for c in provider.contexts), ("brigand:1", "brigand:2"))
        for supplied in provider.contexts:
            self.assertTrue(supplied.state.roster.participant("brigand:2").state.injury.conditions.has(Condition.BROKEN))
        self.assertEqual(stopped.state.consumed_give_ground_execution_ids, (source.attack.execution.request_id,))
        self.assertEqual(stopped.pending_follow_ups, ())
        self.assertEqual(rng.randint.call_count, 6)
        self.assertEqual(rng.randint(1, 10), 7)
