from dataclasses import replace
from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_m2_npc_blunderbuss_give_ground import context
from towr.domain.condition_models import Condition
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.npc_round_exclusion_models import NpcRoundExclusionRequest
from towr.domain.npc_round_models import NpcRoundOutcome
from towr.engine.npc_round_coordinator import run_npc_round
from towr.rules import attack_action_execution as attack_executor
from towr.rules import npc_nearby_stagger_resolution as nearby
from towr.rules import npc_nearby_give_ground_resolution as secondary_movement
from towr.rules import npc_blunderbuss_give_ground_resolution as primary_movement
from towr.rules.npc_round_exclusion import exclude_defeated_npc, apply_npc_round_exclusion


class M2BlunderbussPrimaryGiveGroundTests(unittest.TestCase):
    def test_primary_secondary_movements_and_defeat_resume_round_without_replaying_attack(self):
        for enemy, movement_first, disposition in product((False, True), (False, True), NpcDefeatDisposition):
            with self.subTest(enemy=enemy, movement_first=movement_first, disposition=disposition):
                rng = Mock(wraps=SequenceRandom([1, 10, 10, 10, 10, 1, 10, 10, 7]))
                with (
                    patch.object(attack_executor, "resolve_kernel_attack", wraps=attack_executor.resolve_kernel_attack) as kernel,
                    patch.object(nearby, "resolve_nearby_targets_stagger", wraps=nearby.resolve_nearby_targets_stagger) as stagger,
                    patch.object(secondary_movement, "resolve_give_ground", wraps=secondary_movement.resolve_give_ground) as secondary,
                    patch.object(primary_movement, "resolve_give_ground", wraps=primary_movement.resolve_give_ground) as primary,
                    patch.object(primary_movement, "consume_npc_blunderbuss_give_ground", wraps=primary_movement.consume_npc_blunderbuss_give_ground) as consume,
                ):
                    source = context(enemy=enemy, movement_first=movement_first, disposition=disposition, rng=rng)
                    provider = Mock()
                    stopped = run_npc_round(source.current, provider, rng)
                    self.assertIs(stopped.outcome, NpcRoundOutcome.PENDING_FOLLOW_UPS)
                    self.assertEqual(stopped.steps, ())
                    provider.get_candidates.assert_not_called()
                    result = primary_movement.execute_npc_blunderbuss_give_ground(source)
                    current, spatial = primary_movement.apply_npc_blunderbuss_give_ground(source.current, source.spatial_state, result)
                    self.assertEqual(current.pending_follow_ups, ())
                    self.assertEqual(spatial.gave_ground_entity_ids, ("brigand:1", "brigand:2"))
                    self.assertEqual(current.state.roster.participant("brigand:2").state.injury.conditions.has(Condition.BROKEN), enemy)
                    self.assertIs(result.weapon_state, source.attack.weapon_state)
                    self.assertFalse(result.weapon_state.loaded)
                    self.assertIs(result.source_request.completion, source.completion)
                    chain = source.completion.source_request.chain
                    self.assertEqual(chain.acknowledgements[0].source_request.decision.disposition, disposition)
                    self.assertEqual(current.state.acknowledged_nearby_defeats, source.current.state.acknowledged_nearby_defeats)
                    self.assertEqual(current.state.consumed_nearby_give_ground, source.current.state.consumed_nearby_give_ground)
                    self.assertEqual(current.state.completed_nearby_stagger_sources, source.current.state.completed_nearby_stagger_sources)
                    self.assertEqual(current.state.consumed_give_ground_execution_ids,
                        (*source.current.state.consumed_give_ground_execution_ids, source.attack.primary_attack.attack.request_id))
                    exclusion = exclude_defeated_npc(NpcRoundExclusionRequest("exclude:secondary", current, "brigand:3"))
                    current = apply_npc_round_exclusion(current, exclusion)
                    provider.get_candidates.side_effect = lambda request: request
                    continued = run_npc_round(current, provider, rng)
                    self.assertIs(continued.outcome, NpcRoundOutcome.SELECTION_BLOCKED)
                    self.assertEqual(continued.round_state.completed_turn_entity_ids, ("brigand:0",))
                    self.assertEqual(continued.round_state.excluded_turn_entity_ids, ("brigand:3",))
                    self.assertEqual(continued.state, current.state)
                    provider.get_candidates.assert_called_once()
                    requeued = replace(current, state=continued.state, round_state=continued.round_state,
                                       pending_follow_ups=source.current.pending_follow_ups)
                    with self.assertRaisesRegex(ValueError, "already consumed"):
                        primary_movement.apply_npc_blunderbuss_give_ground(requeued, spatial, result)
                    with self.assertRaisesRegex(ValueError, "already consumed"):
                        replace(source, id="another", current=requeued, spatial_state=spatial,
                                movement=replace(source.movement, state=spatial))
                    self.assertEqual(kernel.call_count, 1)
                    self.assertEqual(stagger.call_count, 1)
                    self.assertEqual(secondary.call_count, 1)
                    primary.assert_called_once_with(source.movement)
                    consume.assert_called_once_with(result.source_request)
                    self.assertEqual(rng.randint.call_count, 8)
                    self.assertEqual(rng.randint(1, 10), 7)
