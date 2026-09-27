from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import Mock, patch

from tests.unit.test_k1_secondary_target_resolution import TargetDecisions
from tests.unit.test_k1_spatial_resolution import graph
from tests.unit.test_m2_npc_nearby_defeat import acknowledgement, context as defeat_context
from tests.unit.test_m2_npc_roster_attack_execution import change_participant
from towr.domain.condition_models import Condition, ConditionState, StaggerChoice
from towr.domain.npc_nearby_give_ground_models import (
    NpcNearbyGiveGroundConsumptionRequest, NpcNearbyGiveGroundConsumptionResult, NpcNearbyGiveGroundExecutionRequest,
)
from towr.domain.npc_roster_attack_models import NpcNearbyDefeatKey, NpcNearbyGiveGroundKey
from towr.domain.resolution_models import GiveGroundRequest, GiveGroundResolutionRequest
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement
from towr.rules import npc_nearby_give_ground_resolution as resolution
from towr.rules.npc_nearby_defeat_resolution import acknowledge_npc_nearby_defeat, apply_npc_nearby_defeat
from towr.rules.npc_nearby_stagger_resolution import execute_npc_nearby_stagger


def context(*, two_movements=False, enemy=False, broken=False):
    source = defeat_context().source_request
    state = source.state
    for index in ((1, 3) if two_movements else (1,)):
        injury = state.roster.participant(f"brigand:{index}").state.injury
        conditions = ConditionState((Condition.STAGGERED, Condition.BROKEN) if broken else (Condition.STAGGERED,))
        state = change_participant(state, index, injury=replace(injury, conditions=conditions))
    targets = tuple(replace(t, impact=replace(t.impact, target_state=state.roster.participant(t.target_id).state.injury))
                    for t in source.resolution.targets)
    source = replace(source, state=state, resolution=replace(source.resolution, targets=targets))
    rng = Mock()
    batch = execute_npc_nearby_stagger(source, rng, decisions=TargetDecisions(stagger_choices={
        "impact:brigand:1:stagger": StaggerChoice.GIVE_GROUND,
        "impact:brigand:3:stagger": StaggerChoice.GIVE_GROUND,
    }))
    rng.randint.assert_not_called()
    spatial = spatial_context(batch, enemy=enemy)
    return movement_request(batch, batch.state, spatial)


def spatial_context(batch, *, enemy=False):
    placements = tuple(SpatialEntityPlacement(p.state.actor_id, p.turn_participant.side.value,
        "zone:a" if p.state.actor_id in ("brigand:0", "brigand:2") else "zone:b")
        for p in batch.state.roster.participants)
    if enemy:
        placements += (SpatialEntityPlacement("extra:enemy", placements[2].side_id, "zone:c"),)
    return SpatialBattleState(graph(), placements, batch.source_request.primary_attack.attack.state.round_number,
                             free_move_used_entity_ids=("brigand:0",), difficult_terrain_tested_entity_ids=("brigand:0",))


def movement_request(batch, current, spatial, target="brigand:1", previous=None):
    follow_up, = next(t.impact.follow_ups for t in batch.pending_targets if t.target_id == target)
    movement = GiveGroundResolutionRequest(follow_up, spatial, target, "zone:c",
        current.roster.participant(target).state.injury.conditions,
        away_from_entity_id=batch.source_request.primary_attack.attack.actor_id)
    return NpcNearbyGiveGroundExecutionRequest("move:" + target, current, spatial, batch, target, movement, previous)


class M2NpcNearbyGiveGroundTests(unittest.TestCase):
    def test_one_movement_and_consumption_in_safe_enemy_and_already_broken_zone(self):
        for enemy, broken in ((False, False), (True, False), (True, True)):
            with self.subTest(enemy=enemy, broken=broken):
                source = context(enemy=enemy, broken=broken)
                before = deepcopy(source)
                with (
                    patch.object(resolution, "resolve_give_ground", wraps=resolution.resolve_give_ground) as move,
                    patch.object(resolution, "consume_npc_nearby_give_ground", wraps=resolution.consume_npc_nearby_give_ground) as consume,
                ):
                    result = resolution.execute_npc_nearby_give_ground(source)
                    current, spatial = resolution.apply_npc_nearby_give_ground(source.current, source.spatial_state, result)
                move.assert_called_once_with(source.movement)
                consume.assert_called_once_with(result.source_request)
                self.assertIs(result.source_request.movement.source_request, source.movement)
                self.assertEqual(current.consumed_nearby_give_ground, (source.key,))
                self.assertEqual(spatial.gave_ground_entity_ids, ("brigand:1",))
                self.assertEqual(spatial.placement_for("brigand:1").zone_id, "zone:c")
                self.assertEqual(spatial.free_move_used_entity_ids, source.spatial_state.free_move_used_entity_ids)
                self.assertEqual(spatial.difficult_terrain_tested_entity_ids, source.spatial_state.difficult_terrain_tested_entity_ids)
                self.assertEqual(current.roster.participant("brigand:1").state.injury.conditions.has(Condition.BROKEN), enemy or broken)
                for target in ("brigand:0", "brigand:2", "brigand:3"):
                    self.assertIs(current.roster.participant(target), source.current.roster.participant(target))
                self.assertEqual(result.pending_targets, (source.batch.pending_targets[1],))
                self.assertIs(result.pending_targets[0], source.batch.pending_targets[1])
                self.assertEqual(source, before)
                self.assertIn("RULE-COMBAT-015:give-ground", result.applied_rule_ids)

    def test_defeat_acknowledgements_and_old_movement_history_are_preserved(self):
        source = context()
        batch_source = source.batch.source_request
        old = replace(batch_source.resolution.source, resolution_id="old:nearby")
        old_key = NpcNearbyGiveGroundKey(old, "brigand:1")
        prior = replace(batch_source.state, consumed_nearby_stagger_sources=(old,), consumed_nearby_give_ground=(old_key,))
        batch = execute_npc_nearby_stagger(replace(batch_source, state=prior), Mock(),
            decisions=TargetDecisions(stagger_choices={"impact:brigand:1:stagger": StaggerChoice.GIVE_GROUND}))
        ack = acknowledge_npc_nearby_defeat(acknowledgement(batch, target="brigand:3"))
        current = apply_npc_nearby_defeat(batch.state, ack)
        request = movement_request(batch, current, source.spatial_state)
        result = resolution.execute_npc_nearby_give_ground(request)
        self.assertEqual(result.pending_targets, ())
        self.assertEqual(result.state.acknowledged_nearby_defeats, (ack.source_request.key,))
        self.assertEqual(result.state.consumed_nearby_give_ground, (old_key, request.key))
        for field in ("consumed_execution_ids", "acknowledged_defeat_execution_ids", "consumed_give_ground_execution_ids",
                      "consumed_nearby_stagger_sources"):
            self.assertEqual(getattr(result.state, field), getattr(current, field))
        with self.assertRaisesRegex(ValueError, "exact post-batch"):
            replace(request, current=replace(current, consumed_nearby_give_ground=()))

    def test_two_targets_move_sequentially_in_either_order_with_exact_previous_result(self):
        base = context(two_movements=True)
        for targets in (("brigand:1", "brigand:3"), ("brigand:3", "brigand:1")):
            with self.subTest(targets=targets):
                first = resolution.execute_npc_nearby_give_ground(movement_request(base.batch, base.current, base.spatial_state, targets[0]))
                current, spatial = resolution.apply_npc_nearby_give_ground(base.current, base.spatial_state, first)
                second_source = movement_request(base.batch, current, spatial, targets[1], first)
                second = resolution.execute_npc_nearby_give_ground(second_source)
                self.assertEqual(second.pending_targets, ())
                self.assertEqual(tuple(k.target_id for k in second.state.consumed_nearby_give_ground), targets)
                self.assertEqual(second.spatial_state.gave_ground_entity_ids, targets)
                self.assertTrue(second.state.roster.participant(targets[1]).state.injury.conditions.has(Condition.BROKEN))
                with self.assertRaisesRegex(ValueError, "exact post-batch"):
                    replace(second_source, previous=None)
                with self.assertRaisesRegex(ValueError, "previous"):
                    replace(second_source, spatial_state=base.spatial_state,
                            movement=replace(second_source.movement, state=base.spatial_state))
                with self.assertRaisesRegex(ValueError, "previous"):
                    replace(second_source, current=base.current)

    def test_stale_foreign_target_source_and_conditions_fail_before_movement(self):
        source = context()
        changes = (
            {"current": change_participant(source.current, 0, available_attack_ids=())},
            {"current": replace(source.current, consumed_execution_ids=(*source.current.consumed_execution_ids, "foreign"))},
            {"target_id": "brigand:2"}, {"target_id": "brigand:3"},
            {"movement": replace(source.movement, mover_id="brigand:3")},
            {"movement": replace(source.movement, away_from_entity_id="brigand:2")},
            {"movement": replace(source.movement, source=GiveGroundRequest("foreign"))},
            {"movement": replace(source.movement, mover_conditions=ConditionState())},
            {"spatial_state": replace(source.spatial_state, free_move_used_entity_ids=())},
            {"batch": replace(source.batch, source_request=replace(source.batch.source_request, primary_attack=None))},
            {"current": replace(source.current, acknowledged_nearby_defeats=(NpcNearbyDefeatKey(source.key.source, "brigand:1"),))},
        )
        for change in changes:
            with self.subTest(change=change), patch.object(resolution, "resolve_give_ground") as move:
                with self.assertRaises(ValueError):
                    resolution.execute_npc_nearby_give_ground(replace(source, **change))
                move.assert_not_called()

    def test_round_side_and_once_per_round_guards_precede_movement(self):
        source = context()
        for spatial in (
            replace(source.spatial_state, round_number=source.spatial_state.round_number + 1),
            replace(source.spatial_state, gave_ground_entity_ids=(source.target_id,)),
            replace(source.spatial_state, placements=tuple(replace(p, side_id="foreign") if p.entity_id == source.target_id else p
                                                         for p in source.spatial_state.placements)),
        ):
            with self.subTest(spatial=spatial), patch.object(resolution, "resolve_give_ground") as move:
                with self.assertRaises(ValueError):
                    resolution.execute_npc_nearby_give_ground(replace(source, spatial_state=spatial,
                        movement=replace(source.movement, state=spatial)))
                move.assert_not_called()

    def test_illegal_routes_fail_without_consumption_or_input_mutation(self):
        source = context()
        for change in ({"crosses_obstacle": True}, {"crosses_difficult_terrain": True},
                       {"path_entity_ids": ("brigand:2",)}, {"destination_zone_id": "zone:a"},
                       {"destination_zone_id": "zone:b"}):
            request = replace(source, movement=replace(source.movement, **change))
            before = deepcopy(request)
            with self.subTest(change=change), patch.object(resolution, "consume_npc_nearby_give_ground") as consume:
                with self.assertRaises(ValueError):
                    resolution.execute_npc_nearby_give_ground(request)
                consume.assert_not_called()
                self.assertEqual(request, before)

    def test_replay_new_id_and_relabelled_batch_impact_cannot_bypass_history(self):
        source = context()
        result = resolution.execute_npc_nearby_give_ground(source)
        current, spatial = resolution.apply_npc_nearby_give_ground(source.current, source.spatial_state, result)
        for snapshots in ((current, source.spatial_state), (source.current, spatial), (current, spatial)):
            with self.subTest(snapshots=snapshots), self.assertRaisesRegex(ValueError, "source differs"):
                resolution.apply_npc_nearby_give_ground(*snapshots, result)
        original = source.batch.source_request
        relabelled = replace(original, resolution=replace(original.resolution, id="new:batch", targets=tuple(
            replace(t, impact=replace(t.impact, id="new:" + t.impact.id)) for t in original.resolution.targets)))
        new_batch = execute_npc_nearby_stagger(relabelled, Mock(), decisions=TargetDecisions(
            stagger_choices={"new:impact:brigand:1:stagger": StaggerChoice.GIVE_GROUND}))
        for batch in (source.batch, new_batch):
            with self.subTest(batch=batch), patch.object(resolution, "resolve_give_ground") as move:
                with self.assertRaisesRegex(ValueError, "already consumed"):
                    movement_request(batch, current, spatial)
                move.assert_not_called()
        with self.assertRaisesRegex(ValueError, "already consumed"):
            replace(result.source_request, id="another", current=current)

    def test_completed_consumer_requires_full_source_and_does_not_execute_again(self):
        source = context()
        movement = resolution.resolve_give_ground(source.movement)
        request = NpcNearbyGiveGroundConsumptionRequest(source.id, source.current, source.spatial_state,
            source.batch, source.target_id, movement)
        with patch.object(resolution, "resolve_give_ground") as move:
            result = resolution.consume_npc_nearby_give_ground(request)
            resolution.apply_npc_nearby_give_ground(source.current, source.spatial_state, result)
            move.assert_not_called()
        with self.assertRaisesRegex(ValueError, "complete movement source"):
            replace(request, movement=replace(movement, source_request=None))
        foreign = resolution.resolve_give_ground(replace(source.movement, source=GiveGroundRequest("foreign")))
        with self.assertRaisesRegex(ValueError, "different"):
            replace(request, movement=foreign)
        with patch.object(resolution, "resolve_give_ground", return_value=foreign), patch.object(resolution, "consume_npc_nearby_give_ground") as consume:
            with self.assertRaisesRegex(ValueError, "different source"):
                resolution.execute_npc_nearby_give_ground(source)
            consume.assert_not_called()

    def test_fabricated_follow_up_without_stagger_choice_proof_is_rejected(self):
        source = context()
        first, second = source.batch.resolution.targets
        for impact in (replace(first.impact, follow_ups=()),
                       replace(first.impact, stagger=replace(first.impact.stagger, gave_ground=False)),
                       replace(first.impact, stagger=replace(first.impact.stagger, selected_choice=StaggerChoice.FALL_PRONE))):
            batch = replace(source.batch, resolution=replace(source.batch.resolution, targets=(replace(first, impact=impact), second)))
            with self.assertRaisesRegex(ValueError, "scoped completed"):
                replace(source, batch=batch)

    def test_typed_frozen_contracts_and_history_validation(self):
        source = context()
        with self.assertRaises(FrozenInstanceError):
            source.target_id = "other"
        for change in ({"current": object()}, {"batch": object()}, {"spatial_state": object()},
                       {"movement": object()}, {"previous": object()}):
            with self.subTest(change=change), self.assertRaises(TypeError):
                replace(source, **change)
        with self.assertRaises(TypeError):
            NpcNearbyGiveGroundConsumptionResult(object())
        with self.assertRaises(TypeError):
            resolution.execute_npc_nearby_give_ground(object())
        with self.assertRaises(ValueError):
            replace(source, target_id="")
        state = replace(source.current, consumed_nearby_give_ground=[source.key])
        self.assertEqual(state.consumed_nearby_give_ground, (source.key,))
        for keys, error in (((source.key, source.key), ValueError), ((object(),), TypeError),
                            ((replace(source.key, source=replace(source.key.source, resolution_id="unknown")),), ValueError)):
            with self.subTest(keys=keys), self.assertRaises(error):
                replace(source.current, consumed_nearby_give_ground=keys)
