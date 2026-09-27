from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_kernel import FixedKernelDecisions
from tests.unit.test_k1_secondary_target_resolution import TargetDecisions
from tests.unit.test_m2_npc_blunderbuss import request as primary_request
from tests.unit.test_m2_npc_nearby_stagger import request as secondary_request
from tests.unit.test_m2_npc_nearby_consequences import append, defeat_request, give_ground_request
from tests.unit.test_m2_npc_nearby_give_ground import spatial_context
from towr.domain.condition_models import Condition, StaggerChoice
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.npc_blunderbuss_give_ground_models import (
    NpcBlunderbussGiveGroundExecutionRequest, NpcBlunderbussGiveGroundConsumptionRequest,
    NpcBlunderbussGiveGroundConsumptionResult,
)
from towr.domain.npc_nearby_completion_models import NpcNearbyCompletionRequest
from towr.domain.npc_nearby_consequence_models import NpcNearbyConsequenceChain
from towr.domain.npc_nearby_stagger_models import NpcNearbyStaggerExecutionRequest
from towr.domain.resolution_models import GiveGroundRequest, GiveGroundResolutionRequest, NearbyTargetsStaggerRequest
from towr.domain.spatial_models import SpatialEntityPlacement, ZoneConnection
from towr.rules import npc_blunderbuss_give_ground_resolution as resolution
from towr.rules.npc_blunderbuss_resolution import execute_npc_blunderbuss_attack, apply_npc_blunderbuss_attack
from towr.rules.npc_nearby_stagger_resolution import execute_npc_nearby_stagger
from towr.rules.npc_nearby_defeat_resolution import acknowledge_npc_nearby_defeat
from towr.rules.npc_nearby_give_ground_resolution import execute_npc_nearby_give_ground
from towr.rules.npc_nearby_completion_resolution import complete_npc_nearby_consequences, apply_npc_nearby_completion
from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack


def context(*, enemy=False, broken=False, empty=False, disposition=NpcDefeatDisposition.KNOCKED_OUT,
            movement_first=True, extra_pending=(), already_used=False, foreign_primary=False,
            foreign_history=False, missing_stagger=False, rng=None):
    conditions = (Condition.STAGGERED, Condition.BROKEN) if broken else (Condition.STAGGERED,)
    secondary = secondary_request(states=((1, (Condition.STAGGERED,)), (2, conditions),
                                           (3, (Condition.STAGGERED, Condition.PRONE))),
                                  targets=() if empty else ("brigand:1", "brigand:3"))
    source = primary_request(roster=secondary.state.roster)
    source = replace(source, current=replace(source.current, state=replace(secondary.state, roster=source.current.state.roster)))
    if foreign_primary:
        preparation = source.preparation.source_request
        source = replace(source, preparation=prepare_ranged_weapon_attack(replace(preparation,
            attack=replace(preparation.attack, id="foreign:primary"))))
    rng = rng if rng is not None else SequenceRandom([1, 10, 10, 10, 10, 1, 10, 10])
    attack = execute_npc_blunderbuss_attack(source, rng, decisions=FixedKernelDecisions(stagger=StaggerChoice.GIVE_GROUND))
    if missing_stagger:
        ranged = attack.primary_attack
        ranged = replace(ranged, attack=replace(ranged.attack, resolution=replace(ranged.attack.resolution, stagger=None)))
        attack = replace(attack, execution=replace(attack.execution, execution=ranged))
    current, _ = apply_npc_blunderbuss_attack(source.current, source.weapon_state, attack)
    trigger, = (p for p in current.pending_follow_ups if isinstance(p, NearbyTargetsStaggerRequest))
    if foreign_history:
        current = replace(current, state=replace(current.state, consumed_execution_ids=(*current.state.consumed_execution_ids, "foreign:history")))
    batch = execute_npc_nearby_stagger(NpcNearbyStaggerExecutionRequest(current.state,
        replace(secondary.resolution, source=trigger), attack.primary_attack), rng,
        decisions=TargetDecisions(stagger_choices={"impact:brigand:1:stagger": StaggerChoice.GIVE_GROUND}))
    spatial = spatial_context(batch)
    spatial = replace(spatial, graph=replace(spatial.graph, zone_ids=(*spatial.graph.zone_ids, "zone:d"),
        connections=(*spatial.graph.connections, ZoneConnection("zone:b", "zone:d"))),
                      placements=tuple(replace(p, zone_id="zone:b") if p.entity_id == "brigand:2" else p
                                               for p in spatial.placements),
                      gave_ground_entity_ids=("brigand:2",) if already_used else ())
    if enemy:
        spatial = replace(spatial, placements=(*spatial.placements, SpatialEntityPlacement(
            "extra:enemy", spatial.placement_for("brigand:0").side_id, "zone:d")))
    chain = NpcNearbyConsequenceChain(batch, spatial)
    if not empty:
        for kind in (("move", "defeat") if movement_first else ("defeat", "move")):
            step = (execute_npc_nearby_give_ground(give_ground_request(chain)) if kind == "move"
                    else acknowledge_npc_nearby_defeat(defeat_request(chain, disposition=disposition)))
            chain = append(chain, step)
    completion = complete_npc_nearby_consequences(NpcNearbyCompletionRequest("complete",
        replace(current, state=chain.state, pending_follow_ups=(*extra_pending, *current.pending_follow_ups)),
        chain.spatial_state, chain))
    current, spatial = apply_npc_nearby_completion(completion.source_request.current, completion.spatial_state, completion)
    follow_up, = (f for f in attack.primary_attack.attack.resolution.follow_ups if isinstance(f, GiveGroundRequest))
    movement = GiveGroundResolutionRequest(follow_up, spatial, "brigand:2", "zone:d",
        current.state.roster.participant("brigand:2").state.injury.conditions, "brigand:0")
    return NpcBlunderbussGiveGroundExecutionRequest("primary:move", current, spatial, attack, completion, movement)


def completed_request(source, movement):
    return NpcBlunderbussGiveGroundConsumptionRequest(source.id, source.current, source.spatial_state,
        source.attack, source.completion, movement)


class M2NpcBlunderbussGiveGroundTests(unittest.TestCase):
    def test_one_movement_preserves_secondary_decisions_history_weapon_and_other_pending(self):
        for enemy, broken, disposition in product((False, True), (False, True), NpcDefeatDisposition):
            with self.subTest(enemy=enemy, broken=broken, disposition=disposition):
                source = context(enemy=enemy, broken=broken, disposition=disposition, extra_pending=(GiveGroundRequest("other"),))
                before = deepcopy(source)
                with (
                    patch.object(resolution, "resolve_give_ground", wraps=resolution.resolve_give_ground) as move,
                    patch.object(resolution, "consume_npc_blunderbuss_give_ground", wraps=resolution.consume_npc_blunderbuss_give_ground) as consume,
                ):
                    result = resolution.execute_npc_blunderbuss_give_ground(source)
                    current, spatial = resolution.apply_npc_blunderbuss_give_ground(source.current, source.spatial_state, result)
                move.assert_called_once_with(source.movement)
                consume.assert_called_once_with(result.source_request)
                self.assertIs(result.source_request.movement.source_request, source.movement)
                self.assertIs(result.source_request.completion, source.completion)
                self.assertIs(result.weapon_state, source.attack.weapon_state)
                self.assertFalse(result.weapon_state.loaded)
                self.assertIs(current.round_state, source.current.round_state)
                self.assertEqual(current.pending_follow_ups, (GiveGroundRequest("other"),))
                self.assertEqual(current.state.consumed_give_ground_execution_ids,
                    (*source.current.state.consumed_give_ground_execution_ids, source.attack.primary_attack.attack.request_id))
                self.assertEqual(replace(current.state, roster=source.current.state.roster,
                    consumed_give_ground_execution_ids=source.current.state.consumed_give_ground_execution_ids), source.current.state)
                target = current.state.roster.participant("brigand:2").state.injury
                self.assertEqual(target.conditions.has(Condition.BROKEN), enemy or broken)
                self.assertEqual(target.wounds, 0)
                for actor in ("brigand:0", "brigand:1", "brigand:3"):
                    self.assertIs(current.state.roster.participant(actor), source.current.state.roster.participant(actor))
                self.assertEqual(spatial.gave_ground_entity_ids, ("brigand:1", "brigand:2"))
                self.assertEqual(spatial.placement_for("brigand:2").zone_id, "zone:d")
                self.assertEqual(spatial.free_move_used_entity_ids, source.spatial_state.free_move_used_entity_ids)
                self.assertEqual(spatial.difficult_terrain_tested_entity_ids, source.spatial_state.difficult_terrain_tested_entity_ids)
                self.assertEqual(source.completion.source_request.chain.acknowledgements[0].source_request.decision.disposition, disposition)
                self.assertIn("RULE-COMBAT-015:give-ground", result.applied_rule_ids)
                self.assertEqual(source, before)

    def test_empty_secondary_and_consume_completed_movement_do_not_execute_twice(self):
        source = context(empty=True)
        movement = resolution.resolve_give_ground(source.movement)
        with patch.object(resolution, "resolve_give_ground") as move:
            result = resolution.consume_npc_blunderbuss_give_ground(completed_request(source, movement))
            current, spatial = resolution.apply_npc_blunderbuss_give_ground(source.current, source.spatial_state, result)
            move.assert_not_called()
        self.assertEqual(current.pending_follow_ups, ())
        self.assertEqual(spatial.gave_ground_entity_ids, ("brigand:2",))
        self.assertEqual(source.completion.source_request.chain.steps, ())

    def test_secondary_movement_can_make_the_primary_destination_hostile(self):
        source = context()
        self.assertEqual(source.spatial_state.placement_for("brigand:1").zone_id, "zone:c")
        source = replace(source, movement=replace(source.movement, destination_zone_id="zone:c"))
        result = resolution.execute_npc_blunderbuss_give_ground(source)
        current, spatial = resolution.apply_npc_blunderbuss_give_ground(source.current, source.spatial_state, result)
        self.assertTrue(current.state.roster.participant("brigand:2").state.injury.conditions.has(Condition.BROKEN))
        self.assertTrue(result.source_request.movement.entered_enemy_zone)
        self.assertEqual(spatial.gave_ground_entity_ids, ("brigand:1", "brigand:2"))

    def test_stale_context_and_foreign_movement_fail_before_execution(self):
        source = context()
        changes = (
            {"current": source.completion.source_request.current},
            {"current": replace(source.current, pending_follow_ups=())},
            {"current": replace(source.current, round_state=replace(source.current.round_state, active_turn=None))},
            {"current": replace(source.current, state=replace(source.current.state, acknowledged_nearby_defeats=()))},
            {"current": replace(source.current, state=replace(source.current.state, consumed_nearby_give_ground=()))},
            {"spatial_state": source.completion.source_request.chain.initial_spatial_state},
            {"movement": replace(source.movement, state=source.completion.source_request.chain.initial_spatial_state)},
            {"movement": replace(source.movement, source=GiveGroundRequest("foreign"))},
            {"movement": replace(source.movement, mover_id="brigand:3")},
            {"movement": replace(source.movement, away_from_entity_id="brigand:1")},
            {"movement": replace(source.movement, mover_conditions=source.movement.mover_conditions.with_condition(Condition.PRONE))},
        )
        for change in changes:
            with self.subTest(change=change), patch.object(resolution, "resolve_give_ground") as move:
                with self.assertRaises(ValueError):
                    resolution.execute_npc_blunderbuss_give_ground(replace(source, **change))
                move.assert_not_called()

    def test_full_primary_post_attack_and_round_provenance_are_required(self):
        source = context()
        foreign = context(foreign_primary=True)
        self.assertEqual(foreign.movement.source, source.movement.source)
        with self.assertRaisesRegex(ValueError, "another primary"):
            replace(source, attack=foreign.attack)
        with self.assertRaisesRegex(ValueError, "post-primary roster/history"):
            context(foreign_history=True)
        for current in (replace(source.completion.source_request.current, id="other"),
                        replace(source.completion.source_request.current, actor_order=tuple(reversed(source.current.actor_order)))):
            completion = replace(source.completion, source_request=replace(source.completion.source_request, current=current))
            with self.assertRaisesRegex(ValueError, "request/order"):
                replace(source, completion=completion, current=completion.continuation)

    def test_completed_stagger_single_pending_and_shared_once_per_round_are_required(self):
        source = context()
        with patch.object(resolution, "resolve_give_ground") as move:
            with self.assertRaisesRegex(ValueError, "completed Stagger"):
                context(missing_stagger=True)
            with self.assertRaisesRegex(ValueError, "exactly one"):
                context(extra_pending=(source.movement.source,))
            with self.assertRaisesRegex(ValueError, "availability"):
                context(already_used=True)
            move.assert_not_called()

    def test_illegal_paths_do_not_register_a_consumption(self):
        source = context(empty=True)
        before = deepcopy(source)
        for change in ({"crosses_obstacle": True}, {"crosses_difficult_terrain": True},
                       {"path_entity_ids": ("brigand:0",)}, {"destination_zone_id": "zone:a"},
                       {"destination_zone_id": "zone:b"}, {"destination_zone_id": "unknown"}):
            with self.subTest(change=change), patch.object(resolution, "consume_npc_blunderbuss_give_ground") as consume:
                with self.assertRaises(ValueError):
                    resolution.execute_npc_blunderbuss_give_ground(replace(source, movement=replace(source.movement, **change)))
                consume.assert_not_called()
        self.assertEqual(source, before)

    def test_application_rejects_stale_snapshots_and_replay_with_requeued_pending(self):
        source = context()
        result = resolution.execute_npc_blunderbuss_give_ground(source)
        current, spatial = resolution.apply_npc_blunderbuss_give_ground(source.current, source.spatial_state, result)
        with self.assertRaisesRegex(ValueError, "source differs"):
            resolution.apply_npc_blunderbuss_give_ground(source.current, spatial, result)
        with self.assertRaisesRegex(ValueError, "source differs"):
            resolution.apply_npc_blunderbuss_give_ground(replace(source.current, pending_follow_ups=()), source.spatial_state, result)
        for pending in ((), source.current.pending_follow_ups):
            requeued = replace(current, pending_follow_ups=pending)
            with self.assertRaisesRegex(ValueError, "already consumed"):
                resolution.apply_npc_blunderbuss_give_ground(requeued, spatial, result)
            with patch.object(resolution, "resolve_give_ground") as move:
                with self.assertRaisesRegex(ValueError, "already consumed"):
                    replace(source, id="new", current=requeued, spatial_state=spatial, movement=replace(source.movement, state=spatial))
                move.assert_not_called()

    def test_completed_movement_requires_source_trace_and_executor_source_identity(self):
        source = context()
        movement = resolution.resolve_give_ground(source.movement)
        for change in ({"source_request": None}, {"applied_rule_ids": ()}):
            with self.assertRaises(ValueError):
                completed_request(source, replace(movement, **change))
        foreign = resolution.resolve_give_ground(replace(source.movement, path_entity_ids=("brigand:3",)))
        with patch.object(resolution, "resolve_give_ground", return_value=foreign), self.assertRaisesRegex(ValueError, "different source"):
            resolution.execute_npc_blunderbuss_give_ground(source)
        before = deepcopy(source)
        with patch.object(resolution, "resolve_give_ground", side_effect=RuntimeError("failed")), self.assertRaises(RuntimeError):
            resolution.execute_npc_blunderbuss_give_ground(source)
        self.assertEqual(source, before)

    def test_typed_frozen_boundaries(self):
        source = context()
        with self.assertRaises(FrozenInstanceError):
            source.id = "changed"
        for change in ({"current": object()}, {"spatial_state": object()}, {"attack": source.attack.primary_attack},
                       {"completion": source.completion.source_request.chain}, {"movement": object()}):
            with self.subTest(change=change), self.assertRaises(TypeError):
                replace(source, **change)
        with self.assertRaises(ValueError):
            replace(source, id="")
        for operation in (lambda: resolution.execute_npc_blunderbuss_give_ground(object()),
                          lambda: resolution.consume_npc_blunderbuss_give_ground(object()),
                          lambda: NpcBlunderbussGiveGroundConsumptionResult(object()),
                          lambda: completed_request(source, source.movement),
                          lambda: resolution.apply_npc_blunderbuss_give_ground(source.current, source.spatial_state, object())):
            with self.assertRaises(TypeError):
                operation()
