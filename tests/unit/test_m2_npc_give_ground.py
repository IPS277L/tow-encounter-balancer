from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_kernel import FixedKernelDecisions
from tests.unit.test_k1_spatial_resolution import graph
from tests.unit.test_m2_npc_round_coordinator import Candidates, request, resume
from tests.unit.test_m2_npc_roster_attack_execution import change_participant
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.npc_give_ground_models import (
    NpcGiveGroundConsumptionRequest, NpcGiveGroundConsumptionResult, NpcGiveGroundExecutionRequest,
)
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionResult
from towr.domain.npc_round_models import NpcRoundOutcome
from towr.domain.resolution_models import GiveGroundRequest, GiveGroundResolutionRequest
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement
from towr.engine.npc_round_coordinator import run_npc_round
from towr.rules.npc_give_ground_resolution import consume_npc_give_ground, apply_npc_give_ground
from towr.rules import spatial_resolution


def pending_context(*, enemy_zone=False, already_broken=False):
    source = request()
    injury = source.state.roster.participant("brigand:2").state.injury
    conditions = injury.conditions.with_condition(Condition.STAGGERED)
    if already_broken:
        conditions = conditions.with_condition(Condition.BROKEN)
    source = replace(source, state=change_participant(source.state, 2, injury=replace(injury, conditions=conditions)))
    stopped = run_npc_round(source, Candidates(), SequenceRandom([1, 10, 10, 10, 10, 10]),
                            decisions=FixedKernelDecisions(stagger=StaggerChoice.GIVE_GROUND))
    attack = next(step for step in stopped.steps if isinstance(step, NpcRosterAttackExecutionResult))
    current = resume(source, stopped)
    spatial = SpatialBattleState(graph(), tuple(
        SpatialEntityPlacement(p.entity_id, p.side.value,
                               "zone:b" if enemy_zone and p.entity_id == "brigand:1" else "zone:a")
        for p in current.round_state.participants
    ), free_move_used_entity_ids=("brigand:0",), difficult_terrain_tested_entity_ids=("brigand:1",))
    movement_request = GiveGroundResolutionRequest(
        attack.pending_follow_ups[0], spatial, "brigand:2", "zone:b", conditions, "brigand:0",
    )
    return NpcGiveGroundExecutionRequest("consume:gg", current, spatial, attack, movement_request)


def context(*, enemy_zone=False, already_broken=False):
    source = pending_context(enemy_zone=enemy_zone, already_broken=already_broken)
    movement = spatial_resolution.resolve_give_ground(source.movement)
    return NpcGiveGroundConsumptionRequest(source.id, source.current, source.spatial_state, source.attack, movement)


class M2NpcGiveGroundTests(unittest.TestCase):
    def test_safe_enemy_and_already_broken_destinations_transfer_once_without_reexecution(self):
        for enemy, broken in ((False, False), (True, False), (True, True)):
            with self.subTest(enemy=enemy, broken=broken):
                source = context(enemy_zone=enemy, already_broken=broken)
                before = deepcopy(source)
                with patch.object(spatial_resolution, "resolve_give_ground", side_effect=AssertionError("reexecuted")):
                    result = consume_npc_give_ground(source)
                    current, spatial = apply_npc_give_ground(source.current, source.spatial_state, result)
                self.assertEqual(source, before)
                self.assertIs(result.source_request, source)
                self.assertIs(spatial, source.movement.state)
                self.assertEqual(spatial.gave_ground_entity_ids, ("brigand:2",))
                self.assertEqual(spatial.free_move_used_entity_ids, source.spatial_state.free_move_used_entity_ids)
                self.assertEqual(spatial.difficult_terrain_tested_entity_ids, source.spatial_state.difficult_terrain_tested_entity_ids)
                self.assertIs(current.round_state, source.current.round_state)
                self.assertEqual(current.pending_follow_ups, ())
                self.assertEqual(current.state.consumed_execution_ids, source.current.state.consumed_execution_ids)
                self.assertEqual(current.state.consumed_give_ground_execution_ids, (source.attack.execution.request_id,))
                target = current.state.roster.participant("brigand:2")
                self.assertEqual(target.state.injury.conditions, source.movement.conditions)
                self.assertTrue(target.state.injury.conditions.has(Condition.STAGGERED))
                self.assertEqual(target.state.injury.conditions.has(Condition.BROKEN), enemy or broken)
                self.assertEqual(target.state.injury.wounds, 0)
                for actor in ("brigand:0", "brigand:1", "brigand:3"):
                    self.assertIs(current.state.roster.participant(actor), source.current.state.roster.participant(actor))
                self.assertEqual(result.applied_rule_ids, source.movement.applied_rule_ids)
                with self.assertRaises(FrozenInstanceError):
                    result.source_request = None

    def test_other_pending_items_keep_order_and_block_round(self):
        source = context()
        before, after = GiveGroundRequest("other:before"), GiveGroundRequest("other:after")
        source = replace(source, current=replace(source.current,
            pending_follow_ups=(before, *source.current.pending_follow_ups, after)))
        current, _ = apply_npc_give_ground(source.current, source.spatial_state, consume_npc_give_ground(source))
        self.assertEqual(current.pending_follow_ups, (before, after))
        provider, rng = Mock(), Mock()
        stopped = run_npc_round(current, provider, rng)
        self.assertIs(stopped.outcome, NpcRoundOutcome.PENDING_FOLLOW_UPS)
        self.assertEqual(stopped.steps, ())
        provider.get_candidates.assert_not_called()
        rng.randint.assert_not_called()

    def test_replay_new_id_and_requeued_follow_up_rejected_even_without_condition_change(self):
        source = context()
        result = consume_npc_give_ground(source)
        current, spatial = apply_npc_give_ground(source.current, source.spatial_state, result)
        with self.assertRaisesRegex(ValueError, "source differs"):
            apply_npc_give_ground(current, spatial, result)
        requeued = replace(current, pending_follow_ups=source.current.pending_follow_ups)
        with self.assertRaisesRegex(ValueError, "already consumed"):
            replace(source, id="new-id", current=requeued)
        self.assertEqual(current.state.roster, source.current.state.roster)

    def test_request_rejects_stale_roster_history_round_and_spatial(self):
        source = context()
        changed = (
            {"current": replace(source.current, state=change_participant(source.current.state, 1, available_attack_ids=()))},
            {"current": replace(source.current, state=replace(source.current.state, consumed_execution_ids=("other", *source.current.state.consumed_execution_ids)))},
            {"current": replace(source.current, round_state=replace(source.current.round_state, active_turn=None))},
            {"spatial_state": replace(source.spatial_state, free_move_used_entity_ids=())},
        )
        for change in changed:
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(source, **change)

    def test_consumer_checks_both_current_snapshots_pending_and_preferences(self):
        source = context()
        result = consume_npc_give_ground(source)
        for current, spatial in (
            (source.current, source.movement.state),
            (replace(source.current, pending_follow_ups=()), source.spatial_state),
            (replace(source.current, actor_order=tuple(reversed(source.current.actor_order))), source.spatial_state),
        ):
            with self.subTest(current=current), self.assertRaisesRegex(ValueError, "source differs"):
                apply_npc_give_ground(current, spatial, result)

    def test_missing_duplicate_or_foreign_pending_item_rejected(self):
        source = context()
        item = source.movement.source
        for queue in ((), (item, item), (GiveGroundRequest("foreign"),)):
            with self.subTest(queue=queue), self.assertRaisesRegex(ValueError, "exactly one matching"):
                replace(source, current=replace(source.current, pending_follow_ups=queue))
        with self.assertRaisesRegex(ValueError, "sole Attack"):
            replace(source, movement=replace(source.movement, source_request=None, source=GiveGroundRequest("foreign")))

    def test_full_movement_source_attacker_target_conditions_and_trace_required(self):
        source = context()
        movement_request = source.movement.source_request
        with self.assertRaisesRegex(ValueError, "complete movement source"):
            replace(source, movement=replace(source.movement, source_request=None))
        for change in ({"away_from_entity_id": None}, {"away_from_entity_id": "brigand:1"},
                       {"mover_id": "brigand:3"},
                       {"mover_conditions": movement_request.mover_conditions.with_condition(Condition.DRAINED)}):
            movement = spatial_resolution.resolve_give_ground(replace(movement_request, **change))
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "target/attacker/source Conditions"):
                replace(source, movement=movement)
        with self.assertRaisesRegex(ValueError, "trace"):
            replace(source, movement=replace(source.movement, applied_rule_ids=(source.movement.source.rule_id,)))

    def test_spatial_round_and_side_binding(self):
        source = context()
        for spatial in (
            replace(source.spatial_state, round_number=2),
            replace(source.spatial_state, placements=tuple(replace(p, side_id="wrong") if p.entity_id == "brigand:1" else p
                                                         for p in source.spatial_state.placements)),
        ):
            movement = spatial_resolution.resolve_give_ground(replace(source.movement.source_request, state=spatial))
            with self.subTest(spatial=spatial), self.assertRaises(ValueError):
                replace(source, spatial_state=spatial, movement=movement)

    def test_completed_result_binds_original_conditions_and_broken_application(self):
        source = context(enemy_zone=True)
        movement = source.movement
        with self.assertRaisesRegex(ValueError, "source Conditions"):
            changed = movement.conditions.with_condition(Condition.DRAINED)
            replace(movement, conditions=changed, condition_application=replace(movement.condition_application, state=changed))
        with self.assertRaisesRegex(ValueError, "application differs"):
            replace(movement, condition_application=replace(movement.condition_application, request_id="foreign"))
        with self.assertRaisesRegex(ValueError, "source request"):
            replace(movement, source_request=replace(movement.source_request, destination_zone_id="zone:c"))

    def test_history_validation_and_typed_guards(self):
        source = context()
        execution_id = source.attack.execution.request_id
        for ids in (("unknown",), ("",), (1,), (execution_id, execution_id)):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                replace(source.current.state, consumed_give_ground_execution_ids=ids)
        normalized = replace(source.current.state, consumed_give_ground_execution_ids=[execution_id])
        self.assertIsInstance(normalized.consumed_give_ground_execution_ids, tuple)
        for change in ({"id": ""}, {"current": object()}, {"spatial_state": object()}, {"attack": object()}, {"movement": object()}):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                replace(source, **change)
        with self.assertRaises(TypeError):
            NpcGiveGroundConsumptionResult(object())
        with self.assertRaises(TypeError):
            apply_npc_give_ground(source.current, source.spatial_state, object())
