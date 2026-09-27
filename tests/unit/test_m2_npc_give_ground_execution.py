from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.unit.test_m2_npc_give_ground import pending_context
from tests.unit.test_m2_npc_roster_attack_execution import change_participant
from towr.domain.condition_models import Condition
from towr.domain.npc_give_ground_models import NpcGiveGroundExecutionRequest
from towr.domain.resolution_models import GiveGroundRequest
from towr.rules import npc_give_ground_resolution as resolution


class M2NpcGiveGroundExecutionTests(unittest.TestCase):
    def test_one_movement_and_registration_for_safe_enemy_and_already_broken(self):
        for enemy, broken in ((False, False), (True, False), (True, True)):
            with self.subTest(enemy=enemy, broken=broken):
                source = pending_context(enemy_zone=enemy, already_broken=broken)
                before = deepcopy(source)
                with (
                    patch.object(resolution, "resolve_give_ground", wraps=resolution.resolve_give_ground) as move,
                    patch.object(resolution, "consume_npc_give_ground", wraps=resolution.consume_npc_give_ground) as consume,
                ):
                    result = resolution.execute_npc_give_ground(source)
                move.assert_called_once_with(source.movement)
                consume.assert_called_once_with(result.source_request)
                self.assertIs(result.source_request.movement.source_request, source.movement)
                current, spatial = resolution.apply_npc_give_ground(source.current, source.spatial_state, result)
                self.assertEqual(source, before)
                self.assertIs(current.round_state, source.current.round_state)
                self.assertEqual(current.pending_follow_ups, ())
                self.assertEqual(current.state.consumed_give_ground_execution_ids, (source.attack.execution.request_id,))
                self.assertEqual(current.state.roster.participant("brigand:2").state.injury.conditions.has(Condition.BROKEN), enemy or broken)
                self.assertEqual(spatial.gave_ground_entity_ids, ("brigand:2",))

    def test_stale_context_and_wrong_source_rejected_before_movement(self):
        source = pending_context()
        changes = (
            {"current": replace(source.current, state=change_participant(source.current.state, 1, available_attack_ids=()))},
            {"current": replace(source.current, state=replace(source.current.state, consumed_execution_ids=("other", *source.current.state.consumed_execution_ids)))},
            {"current": replace(source.current, round_state=replace(source.current.round_state, active_turn=None))},
            {"current": replace(source.current, pending_follow_ups=())},
            {"current": replace(source.current, pending_follow_ups=source.current.pending_follow_ups * 2)},
            {"spatial_state": replace(source.spatial_state, free_move_used_entity_ids=())},
            {"movement": replace(source.movement, away_from_entity_id="brigand:1")},
            {"movement": replace(source.movement, mover_id="brigand:3")},
            {"movement": replace(source.movement, mover_conditions=source.movement.mover_conditions.with_condition(Condition.PRONE))},
            {"movement": replace(source.movement, source=GiveGroundRequest("foreign"))},
        )
        for change in changes:
            with self.subTest(change=change), patch.object(resolution, "resolve_give_ground") as move:
                with self.assertRaises(ValueError):
                    resolution.execute_npc_give_ground(replace(source, **change))
                move.assert_not_called()

    def test_round_side_and_once_per_round_guards_precede_movement(self):
        source = pending_context()
        for spatial in (
            replace(source.spatial_state, round_number=2),
            replace(source.spatial_state, gave_ground_entity_ids=("brigand:2",)),
            replace(source.spatial_state, placements=tuple(replace(p, side_id="wrong") if p.entity_id == "brigand:1" else p
                                                         for p in source.spatial_state.placements)),
        ):
            with self.subTest(spatial=spatial), patch.object(resolution, "resolve_give_ground") as move:
                with self.assertRaises(ValueError):
                    resolution.execute_npc_give_ground(replace(source, spatial_state=spatial,
                        movement=replace(source.movement, state=spatial)))
                move.assert_not_called()

    def test_replay_with_new_id_and_requeued_pending_is_rejected_before_movement(self):
        source = pending_context()
        result = resolution.execute_npc_give_ground(source)
        current, spatial = resolution.apply_npc_give_ground(source.current, source.spatial_state, result)
        for snapshot in (source.spatial_state, spatial):
            with self.subTest(snapshot=snapshot), patch.object(resolution, "resolve_give_ground") as move:
                with self.assertRaisesRegex(ValueError, "already consumed"):
                    resolution.execute_npc_give_ground(replace(source, id="another",
                        current=replace(current, pending_follow_ups=source.current.pending_follow_ups),
                        spatial_state=snapshot, movement=replace(source.movement, state=snapshot)))
                move.assert_not_called()

    def test_illegal_routes_are_rejected_by_existing_reducer_without_registration(self):
        source = pending_context()
        for change in ({"crosses_obstacle": True}, {"crosses_difficult_terrain": True},
                       {"path_entity_ids": ("brigand:0",)}, {"destination_zone_id": "zone:c"},
                       {"destination_zone_id": "zone:a"}):
            with self.subTest(change=change):
                request = replace(source, movement=replace(source.movement, **change))
                before = deepcopy(request)
                with (
                    patch.object(resolution, "resolve_give_ground", wraps=resolution.resolve_give_ground) as move,
                    patch.object(resolution, "consume_npc_give_ground") as consume,
                ):
                    with self.assertRaises(ValueError):
                        resolution.execute_npc_give_ground(request)
                move.assert_called_once_with(request.movement)
                consume.assert_not_called()
                self.assertEqual(request, before)

    def test_other_pending_and_prior_acknowledgement_history_are_preserved(self):
        source = pending_context()
        prior = replace(source.attack.source_request.state, consumed_execution_ids=("earlier",),
                        acknowledged_defeat_execution_ids=("earlier",))
        attack = replace(source.attack, source_request=replace(source.attack.source_request, state=prior))
        other = GiveGroundRequest("other")
        source = replace(source, attack=attack, current=replace(source.current, state=attack.state,
            pending_follow_ups=(other, *source.current.pending_follow_ups)))
        result = resolution.execute_npc_give_ground(source)
        self.assertEqual(result.continuation.pending_follow_ups, (other,))
        self.assertEqual(result.continuation.state.acknowledged_defeat_execution_ids, ("earlier",))
        self.assertEqual(result.continuation.state.consumed_execution_ids, ("earlier", attack.execution.request_id))

    def test_exceptions_and_foreign_resolver_result_do_not_return_partial_state(self):
        source = pending_context()
        before = deepcopy(source)
        for failing in ("resolve_give_ground", "consume_npc_give_ground"):
            with self.subTest(failing=failing), patch.object(resolution, failing, side_effect=RuntimeError("failure")):
                with self.assertRaisesRegex(RuntimeError, "failure"):
                    resolution.execute_npc_give_ground(source)
                self.assertEqual(source, before)
        foreign = resolution.resolve_give_ground(replace(source.movement, path_entity_ids=("brigand:3",)))
        with patch.object(resolution, "resolve_give_ground", return_value=foreign), patch.object(resolution, "consume_npc_give_ground") as consume:
            with self.assertRaisesRegex(ValueError, "different source"):
                resolution.execute_npc_give_ground(source)
            consume.assert_not_called()
        self.assertEqual(source, before)

    def test_typed_execution_request_rejects_completed_movement_and_malformed_inputs(self):
        source = pending_context()
        for change in ({"id": ""}, {"current": None}, {"spatial_state": None}, {"attack": None},
                       {"movement": resolution.resolve_give_ground(source.movement)}):
            with self.subTest(change=change), self.assertRaises((TypeError, ValueError)):
                replace(source, **change)
        with self.assertRaises(TypeError):
            resolution.execute_npc_give_ground(object())
        self.assertIsInstance(source, NpcGiveGroundExecutionRequest)
