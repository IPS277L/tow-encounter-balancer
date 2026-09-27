import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_m2_npc_give_ground import pending_context
from tests.integration.test_m2_npc_give_ground_cycle import SpatialCandidates
from towr.domain.npc_attack_selection_models import NpcAttackSelectionBlock
from towr.domain.npc_round_models import NpcRoundOutcome
from towr.domain.turn_models import CombatTurnEndResult
from towr.engine.npc_round_coordinator import run_npc_round
from towr.rules import attack_action_execution as attack_executor, npc_give_ground_resolution as resolution


class M2NpcGiveGroundExecutionCycleTests(unittest.TestCase):
    def test_atomic_movement_and_registration_resume_safe_or_enemy_zone_round(self):
        for enemy in (False, True):
            with (
                self.subTest(enemy=enemy),
                patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel,
                patch.object(resolution, "resolve_give_ground", wraps=resolution.resolve_give_ground) as move,
                patch.object(resolution, "consume_npc_give_ground", wraps=resolution.consume_npc_give_ground) as consume,
            ):
                source = pending_context(enemy_zone=enemy)
                self.assertEqual(kernel.call_count, 1)
                move.assert_not_called()
                result = resolution.execute_npc_give_ground(source)
                current, spatial = resolution.apply_npc_give_ground(source.current, source.spatial_state, result)
                self.assertEqual(kernel.call_count, 1)
                provider = SpatialCandidates(spatial)
                rng = SequenceRandom([10] * (6 if enemy else 18) + [7])
                finished = run_npc_round(current, provider, rng)
                self.assertIs(finished.outcome, NpcRoundOutcome.SELECTION_BLOCKED if enemy else NpcRoundOutcome.COMPLETE)
                if enemy:
                    self.assertIs(finished.blocked_selection.blocked_reason, NpcAttackSelectionBlock.ACTOR_BROKEN)
                    self.assertEqual(len(finished.blocked_selection.source_request.candidates), 1)
                    self.assertFalse(finished.round_state.active_turn.action_slots[0].executed)
                self.assertEqual(kernel.call_count, 2 if enemy else 4)
                move.assert_called_once_with(source.movement)
                consume.assert_called_once_with(result.source_request)
                self.assertIsInstance(finished.steps[0], CombatTurnEndResult)
                self.assertEqual(finished.steps[0].completed_turn, source.current.round_state.active_turn)
                self.assertEqual(finished.state.consumed_give_ground_execution_ids, (source.attack.execution.request_id,))
                self.assertEqual(spatial.placement_for("brigand:2").zone_id, "zone:b")
                self.assertEqual(rng.randint(1, 10), 7)
