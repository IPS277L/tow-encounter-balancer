from __future__ import annotations

import unittest
from dataclasses import replace

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.resolution_models import (
    GiveGroundRequest,
    GiveGroundResolutionRequest,
)
from towr.domain.spatial_models import (
    SpatialBattleState,
    SpatialEntityPlacement,
    ZoneConnection,
    ZoneGraph,
)
from towr.rules.spatial_resolution import (
    GIVE_GROUND_MOVEMENT_RULE_ID,
    ZONE_GRAPH_RULE_ID,
    resolve_give_ground,
    start_next_spatial_round,
)


def graph() -> ZoneGraph:
    return ZoneGraph(
        zone_ids=("zone:a", "zone:b", "zone:c"),
        connections=(
            ZoneConnection("zone:a", "zone:b"),
            ZoneConnection("zone:b", "zone:c"),
        ),
    )


def state(
    *placements: SpatialEntityPlacement,
    gave_ground: tuple[str, ...] = (),
) -> SpatialBattleState:
    return SpatialBattleState(
        graph=graph(),
        placements=placements
        or (
            SpatialEntityPlacement("mover", "heroes", "zone:a"),
            SpatialEntityPlacement("attacker", "enemies", "zone:a"),
        ),
        gave_ground_entity_ids=gave_ground,
    )


def request(
    spatial_state: SpatialBattleState,
    *,
    destination_zone_id: str = "zone:b",
    conditions: ConditionState = ConditionState(),
    away_from_entity_id: str | None = "attacker",
    path_entity_ids: tuple[str, ...] = (),
    crosses_obstacle: bool = False,
    crosses_difficult_terrain: bool = False,
) -> GiveGroundResolutionRequest:
    return GiveGroundResolutionRequest(
        source=GiveGroundRequest("impact:give-ground"),
        state=spatial_state,
        mover_id="mover",
        destination_zone_id=destination_zone_id,
        mover_conditions=conditions,
        away_from_entity_id=away_from_entity_id,
        path_entity_ids=path_entity_ids,
        crosses_obstacle=crosses_obstacle,
        crosses_difficult_terrain=crosses_difficult_terrain,
    )


class K1SpatialModelTests(unittest.TestCase):
    def test_zone_graph_is_undirected_and_preserves_connection_order(self) -> None:
        battlefield = graph()

        self.assertTrue(battlefield.are_adjacent("zone:a", "zone:b"))
        self.assertTrue(battlefield.are_adjacent("zone:b", "zone:a"))
        self.assertEqual(
            battlefield.adjacent_zone_ids("zone:b"),
            ("zone:a", "zone:c"),
        )

    def test_zone_graph_rejects_invalid_or_duplicate_connections(self) -> None:
        with self.assertRaises(ValueError):
            ZoneConnection("zone:a", "zone:a")
        with self.assertRaises(ValueError):
            ZoneGraph(
                zone_ids=("zone:a", "zone:b"),
                connections=(ZoneConnection("zone:a", "zone:unknown"),),
            )
        with self.assertRaises(ValueError):
            ZoneGraph(
                zone_ids=("zone:a", "zone:b"),
                connections=(
                    ZoneConnection("zone:a", "zone:b"),
                    ZoneConnection("zone:b", "zone:a"),
                ),
            )

    def test_spatial_state_rejects_duplicate_or_unknown_entities(self) -> None:
        duplicate = SpatialEntityPlacement("same", "heroes", "zone:a")
        with self.assertRaises(ValueError):
            state(duplicate, duplicate)
        with self.assertRaises(ValueError):
            state(SpatialEntityPlacement("lost", "heroes", "zone:unknown"))
        with self.assertRaises(ValueError):
            state(gave_ground=("unknown",))


class K1GiveGroundSpatialResolutionTests(unittest.TestCase):
    def test_moves_to_adjacent_zone_away_from_attacker_and_marks_round(self) -> None:
        source = state()

        result = resolve_give_ground(request(source))

        self.assertEqual(result.origin_zone_id, "zone:a")
        self.assertEqual(result.destination_zone_id, "zone:b")
        self.assertEqual(result.state.placement_for("mover").zone_id, "zone:b")
        self.assertEqual(
            tuple(item.entity_id for item in result.state.placements),
            ("mover", "attacker"),
        )
        self.assertEqual(result.state.gave_ground_entity_ids, ("mover",))
        self.assertFalse(result.entered_enemy_zone)
        self.assertEqual(result.conditions, ConditionState())
        self.assertIsNone(result.condition_application)
        self.assertEqual(
            result.applied_rule_ids,
            (
                "RULE-HEALTH-003:give-ground",
                ZONE_GRAPH_RULE_ID,
                GIVE_GROUND_MOVEMENT_RULE_ID,
            ),
        )

    def test_entering_enemy_zone_applies_broken_after_movement(self) -> None:
        source = state(
            SpatialEntityPlacement("mover", "heroes", "zone:a"),
            SpatialEntityPlacement("attacker", "enemies", "zone:a"),
            SpatialEntityPlacement("guard", "enemies", "zone:b"),
        )

        result = resolve_give_ground(request(source))

        self.assertTrue(result.entered_enemy_zone)
        self.assertTrue(result.conditions.has(Condition.BROKEN))
        self.assertIsNotNone(result.condition_application)
        assert result.condition_application is not None
        self.assertEqual(
            result.condition_application.source_rule_id,
            GIVE_GROUND_MOVEMENT_RULE_ID,
        )
        self.assertEqual(result.state.placement_for("mover").zone_id, "zone:b")

    def test_entering_allied_zone_does_not_apply_broken(self) -> None:
        source = state(
            SpatialEntityPlacement("mover", "heroes", "zone:a"),
            SpatialEntityPlacement("attacker", "enemies", "zone:a"),
            SpatialEntityPlacement("ally", "heroes", "zone:b"),
        )

        result = resolve_give_ground(request(source))

        self.assertFalse(result.entered_enemy_zone)
        self.assertFalse(result.conditions.has(Condition.BROKEN))

    def test_destination_must_be_adjacent_and_farther_from_attacker(self) -> None:
        source = state()
        with self.assertRaises(ValueError):
            resolve_give_ground(
                request(source, destination_zone_id="zone:c")
            )

        pursuer_ahead = state(
            SpatialEntityPlacement("mover", "heroes", "zone:a"),
            SpatialEntityPlacement("attacker", "enemies", "zone:b"),
        )
        with self.assertRaises(ValueError):
            resolve_give_ground(request(pursuer_ahead))

    def test_prone_defenceless_and_round_limit_prevent_movement(self) -> None:
        cases = (
            request(state(), conditions=ConditionState({Condition.PRONE})),
            request(
                state(),
                conditions=ConditionState({Condition.DEFENCELESS}),
            ),
            request(state(gave_ground=("mover",))),
        )

        for invalid_request in cases:
            with self.subTest(request=invalid_request):
                with self.assertRaises(ValueError):
                    resolve_give_ground(invalid_request)

    def test_obstacle_difficult_terrain_and_crossed_enemy_block_path(self) -> None:
        source = state(
            SpatialEntityPlacement("mover", "heroes", "zone:a"),
            SpatialEntityPlacement("attacker", "enemies", "zone:a"),
            SpatialEntityPlacement("blocker", "enemies", "zone:a"),
        )
        cases = (
            request(source, crosses_obstacle=True),
            request(source, crosses_difficult_terrain=True),
            request(source, path_entity_ids=("blocker",)),
        )

        for invalid_request in cases:
            with self.subTest(request=invalid_request):
                with self.assertRaises(ValueError):
                    resolve_give_ground(invalid_request)

    def test_crossing_an_ally_is_not_treated_as_crossing_an_enemy(self) -> None:
        source = state(
            SpatialEntityPlacement("mover", "heroes", "zone:a"),
            SpatialEntityPlacement("attacker", "enemies", "zone:a"),
            SpatialEntityPlacement("ally", "heroes", "zone:a"),
        )

        result = resolve_give_ground(
            request(source, path_entity_ids=("ally",))
        )

        self.assertEqual(result.state.placement_for("mover").zone_id, "zone:b")

    def test_new_round_resets_round_scoped_movement_limits(self) -> None:
        first = resolve_give_ground(request(state()))

        next_round = start_next_spatial_round(
            replace(first.state, free_move_used_entity_ids=("attacker",))
        )
        second = resolve_give_ground(
            GiveGroundResolutionRequest(
                source=GiveGroundRequest("second:give-ground"),
                state=next_round,
                mover_id="mover",
                destination_zone_id="zone:a",
                mover_conditions=first.conditions,
            )
        )

        self.assertEqual(next_round.round_number, 2)
        self.assertEqual(next_round.gave_ground_entity_ids, ())
        self.assertEqual(next_round.free_move_used_entity_ids, ())
        self.assertEqual(second.state.round_number, 2)
        self.assertEqual(second.state.gave_ground_entity_ids, ("mover",))
        self.assertEqual(second.state.placement_for("mover").zone_id, "zone:a")

    def test_result_rejects_an_unrelated_spatial_state_change(self) -> None:
        result = resolve_give_ground(request(state()))
        forged_state = replace(
            result.state,
            placements=(
                result.state.placement_for("mover"),
                SpatialEntityPlacement("attacker", "enemies", "zone:b"),
            ),
        )

        with self.assertRaises(ValueError):
            replace(result, state=forged_state)
        with self.assertRaises(ValueError):
            replace(
                result,
                state=replace(
                    result.state,
                    free_move_used_entity_ids=("mover",),
                ),
            )


if __name__ == "__main__":
    unittest.main()
