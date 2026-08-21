from __future__ import annotations

import unittest
from dataclasses import replace

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.movement_models import FreeMovementRequest, MovementSpeed
from towr.domain.spatial_models import (
    SpatialBattleState,
    SpatialEntityPlacement,
    ZoneConnection,
    ZoneGraph,
)
from towr.domain.turn_models import (
    CombatRoundState,
    CombatSide,
    CombatTurnParticipant,
    CombatTurnStartRequest,
)
from towr.rules.free_movement_resolution import (
    FREE_MOVEMENT_RULE_ID,
    SPEED_MOVEMENT_RULE_ID,
    resolve_free_movement,
)
from towr.rules.spatial_resolution import (
    ZONE_GRAPH_RULE_ID,
    start_next_spatial_round,
)
from towr.rules.turn_resolution import start_combat_turn


def graph() -> ZoneGraph:
    return ZoneGraph(
        zone_ids=("zone:a", "zone:b", "zone:c", "zone:d"),
        connections=(
            ZoneConnection("zone:a", "zone:b"),
            ZoneConnection("zone:b", "zone:c"),
            ZoneConnection("zone:b", "zone:d"),
        ),
    )


def spatial_state(
    *,
    round_number: int = 1,
    free_move_used: tuple[str, ...] = (),
    gave_ground: tuple[str, ...] = (),
) -> SpatialBattleState:
    return SpatialBattleState(
        graph=graph(),
        placements=(
            SpatialEntityPlacement("hero", "heroes", "zone:a"),
            SpatialEntityPlacement("ally", "heroes", "zone:a"),
            SpatialEntityPlacement("enemy", "enemies", "zone:a"),
        ),
        round_number=round_number,
        gave_ground_entity_ids=gave_ground,
        free_move_used_entity_ids=free_move_used,
    )


def active_round(
    *,
    round_number: int = 1,
    actor_id: str = "hero",
) -> CombatRoundState:
    state = CombatRoundState(
        round_number=round_number,
        participants=(
            CombatTurnParticipant("hero", CombatSide.PLAYERS_AND_ALLIES),
            CombatTurnParticipant("ally", CombatSide.PLAYERS_AND_ALLIES),
            CombatTurnParticipant("enemy", CombatSide.OPPOSITION),
        ),
    )
    return start_combat_turn(
        CombatTurnStartRequest(
            id=f"turn:{actor_id}",
            state=state,
            actor_id=actor_id,
        )
    ).state


def request(
    *,
    round_state: CombatRoundState | None = None,
    state: SpatialBattleState | None = None,
    actor_id: str = "hero",
    speed: MovementSpeed = MovementSpeed.NORMAL,
    conditions: ConditionState = ConditionState(),
    traversed_zone_ids: tuple[str, ...] = ("zone:b",),
    path_entity_ids: tuple[str, ...] = (),
    crosses_obstacle: bool = False,
    crosses_difficult_terrain: bool = False,
) -> FreeMovementRequest:
    return FreeMovementRequest(
        id="movement:free",
        round_state=round_state or active_round(actor_id=actor_id),
        state=state or spatial_state(),
        actor_id=actor_id,
        speed=speed,
        actor_conditions=conditions,
        traversed_zone_ids=traversed_zone_ids,
        path_entity_ids=path_entity_ids,
        crosses_obstacle=crosses_obstacle,
        crosses_difficult_terrain=crosses_difficult_terrain,
    )


class K1FreeMovementResolutionTests(unittest.TestCase):
    def test_normal_free_move_changes_only_spatial_state(self) -> None:
        source = request()

        result = resolve_free_movement(source)

        self.assertEqual(result.origin_zone_id, "zone:a")
        self.assertEqual(result.destination_zone_id, "zone:b")
        self.assertEqual(result.state.placement_for("hero").zone_id, "zone:b")
        self.assertEqual(result.state.free_move_used_entity_ids, ("hero",))
        self.assertEqual(result.round_state, source.round_state)
        assert result.round_state.active_turn is not None
        self.assertEqual(result.round_state.active_turn.action_slots, ())
        self.assertEqual(
            result.applied_rule_ids,
            (
                FREE_MOVEMENT_RULE_ID,
                SPEED_MOVEMENT_RULE_ID,
                ZONE_GRAPH_RULE_ID,
            ),
        )

    def test_slow_and_burdened_actor_can_still_move_one_zone(self) -> None:
        result = resolve_free_movement(
            request(
                speed=MovementSpeed.SLOW,
                conditions=ConditionState({Condition.BURDENED}),
            )
        )

        self.assertEqual(result.destination_zone_id, "zone:b")

    def test_only_fast_speed_can_cross_two_zone_boundaries(self) -> None:
        fast = resolve_free_movement(
            request(
                speed=MovementSpeed.FAST,
                traversed_zone_ids=("zone:b", "zone:c"),
            )
        )
        self.assertEqual(fast.destination_zone_id, "zone:c")

        for speed in (MovementSpeed.SLOW, MovementSpeed.NORMAL):
            with self.subTest(speed=speed):
                with self.assertRaises(ValueError):
                    request(
                        speed=speed,
                        traversed_zone_ids=("zone:b", "zone:c"),
                    )

    def test_route_must_follow_known_zone_links_without_repetition(self) -> None:
        with self.assertRaises(ValueError):
            resolve_free_movement(
                request(traversed_zone_ids=("zone:d",))
            )
        with self.assertRaises(ValueError):
            resolve_free_movement(
                request(traversed_zone_ids=("zone:unknown",))
            )
        with self.assertRaises(ValueError):
            request(
                speed=MovementSpeed.FAST,
                traversed_zone_ids=("zone:b", "zone:b"),
            )

    def test_request_requires_matching_active_actor_and_round(self) -> None:
        with self.assertRaises(ValueError):
            request(round_state=active_round(), actor_id="ally")
        with self.assertRaises(ValueError):
            request(
                round_state=CombatRoundState(
                    round_number=1,
                    participants=(
                        CombatTurnParticipant(
                            "hero",
                            CombatSide.PLAYERS_AND_ALLIES,
                        ),
                        CombatTurnParticipant(
                            "enemy",
                            CombatSide.OPPOSITION,
                        ),
                    ),
                )
            )
        with self.assertRaises(ValueError):
            request(state=spatial_state(round_number=2))

    def test_prone_defenceless_and_incomplete_path_context_block_move(self) -> None:
        cases = (
            request(conditions=ConditionState({Condition.PRONE})),
            request(conditions=ConditionState({Condition.DEFENCELESS})),
            request(crosses_obstacle=True),
            request(crosses_difficult_terrain=True),
            request(path_entity_ids=("enemy",)),
        )

        for invalid_request in cases:
            with self.subTest(request=invalid_request):
                with self.assertRaises(ValueError):
                    resolve_free_movement(invalid_request)

        allied_path = resolve_free_movement(
            request(path_entity_ids=("ally",))
        )
        self.assertEqual(allied_path.destination_zone_id, "zone:b")

    def test_free_move_is_once_per_turn_and_resets_with_spatial_round(self) -> None:
        first = resolve_free_movement(request())
        with self.assertRaises(ValueError):
            resolve_free_movement(
                request(state=first.state, traversed_zone_ids=("zone:c",))
            )

        marked = replace(first.state, gave_ground_entity_ids=("enemy",))
        next_round = start_next_spatial_round(marked)
        self.assertEqual(next_round.round_number, 2)
        self.assertEqual(next_round.free_move_used_entity_ids, ())
        self.assertEqual(next_round.gave_ground_entity_ids, ())

    def test_spatial_state_rejects_invalid_free_movement_usage(self) -> None:
        with self.assertRaises(ValueError):
            spatial_state(free_move_used=("unknown",))
        with self.assertRaises(ValueError):
            spatial_state(free_move_used=("hero", "hero"))

    def test_result_rejects_unrelated_spatial_or_turn_forgery(self) -> None:
        result = resolve_free_movement(request())
        forged_state = replace(
            result.state,
            placements=(
                result.state.placement_for("hero"),
                SpatialEntityPlacement("ally", "heroes", "zone:c"),
                result.state.placement_for("enemy"),
            ),
        )

        with self.assertRaises(ValueError):
            replace(result, state=forged_state)
        with self.assertRaises(ValueError):
            replace(result, round_state=active_round(round_number=2))
        with self.assertRaises(ValueError):
            replace(result, rule_id="RULE-COMBAT-014:forged")
        with self.assertRaises(TypeError):
            replace(result, speed="normal")


if __name__ == "__main__":
    unittest.main()
