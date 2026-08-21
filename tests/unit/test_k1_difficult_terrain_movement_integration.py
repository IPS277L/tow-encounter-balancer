from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.movement_models import (
    DifficultTerrainFreeMovementRequest,
    DifficultTerrainRunActionExecutionRequest,
    DifficultTerrainTraversalRequest,
    FreeMovementRequest,
    MovementSpeed,
    RunActionExecutionRequest,
)
from towr.domain.spatial_models import (
    SpatialBattleState,
    SpatialEntityPlacement,
    ZoneConnection,
    ZoneGraph,
)
from towr.domain.test_models import TestProfile, TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant,
    CombatActionDeclaration,
    CombatActionKind,
    CombatActionSlotRequest,
    CombatRoundState,
    CombatSide,
    CombatTurnEndRequest,
    CombatTurnParticipant,
    CombatTurnStartRequest,
    ManoeuvreKind,
)
from towr.rules.difficult_terrain_resolution import (
    resolve_difficult_terrain_traversal,
)
from towr.rules.free_movement_resolution import (
    DIFFICULT_TERRAIN_FREE_MOVEMENT_RULE_ID,
    resolve_difficult_terrain_free_movement,
)
from towr.rules.run_action_execution import (
    DIFFICULT_TERRAIN_RUN_ACTION_EXECUTION_RULE_ID,
    execute_difficult_terrain_run_action,
)
from towr.rules.turn_resolution import (
    end_combat_turn,
    reserve_combat_action_slot,
    start_combat_turn,
)


def active_round(*, reserve_run: bool = False) -> CombatRoundState:
    state = CombatRoundState(
        round_number=1,
        participants=(
            CombatTurnParticipant("hero", CombatSide.PLAYERS_AND_ALLIES),
            CombatTurnParticipant("enemy", CombatSide.OPPOSITION),
        ),
    )
    state = start_combat_turn(
        CombatTurnStartRequest("turn:hero", state, "hero")
    ).state
    if reserve_run:
        state = reserve_combat_action_slot(
            CombatActionSlotRequest(
                id="slot:run",
                state=state,
                actor_id="hero",
                declaration=CombatActionDeclaration(
                    CombatActionKind.MANOEUVRE,
                    manoeuvre=ManoeuvreKind.RUN,
                ),
                grant=ActionSlotGrant.STANDARD,
            )
        ).state
    return state


def spatial_state() -> SpatialBattleState:
    return SpatialBattleState(
        graph=ZoneGraph(
            zone_ids=("zone:a", "zone:b", "zone:c"),
            connections=(
                ZoneConnection("zone:a", "zone:b"),
                ZoneConnection("zone:b", "zone:c"),
            ),
        ),
        placements=(
            SpatialEntityPlacement("hero", "heroes", "zone:a"),
            SpatialEntityPlacement("ally", "heroes", "zone:a"),
            SpatialEntityPlacement("enemy", "enemies", "zone:b"),
        ),
    )


def terrain_request(
    round_state: CombatRoundState,
    state: SpatialBattleState,
    conditions: ConditionState = ConditionState(),
    *,
    path_entity_ids: tuple[str, ...] = (),
) -> DifficultTerrainTraversalRequest:
    return DifficultTerrainTraversalRequest(
        id="terrain:cross",
        round_state=round_state,
        state=state,
        actor_id="hero",
        actor_conditions=conditions,
        athletics_test=TestRequest(
            "terrain:athletics",
            TestProfile(1, 5),
        ),
        destination_zone_id="zone:b",
        path_entity_ids=path_entity_ids,
    )


def free_movement_request(
    round_state: CombatRoundState,
    state: SpatialBattleState,
    conditions: ConditionState = ConditionState(),
    *,
    path_entity_ids: tuple[str, ...] = (),
) -> FreeMovementRequest:
    return FreeMovementRequest(
        id="free:terrain",
        round_state=round_state,
        state=state,
        actor_id="hero",
        speed=MovementSpeed.NORMAL,
        actor_conditions=conditions,
        traversed_zone_ids=("zone:b",),
        path_entity_ids=path_entity_ids,
        crosses_difficult_terrain=True,
    )


def run_request(
    round_state: CombatRoundState,
    state: SpatialBattleState,
    conditions: ConditionState = ConditionState(),
    *,
    speed: MovementSpeed = MovementSpeed.NORMAL,
    path_entity_ids: tuple[str, ...] = (),
) -> RunActionExecutionRequest:
    return RunActionExecutionRequest(
        id="run:terrain",
        round_state=round_state,
        spatial_state=state,
        actor_id="hero",
        slot_index=1,
        speed=speed,
        actor_conditions=conditions,
        destination_zone_id="zone:b",
        path_entity_ids=path_entity_ids,
        crosses_difficult_terrain=True,
    )


class K1DifficultTerrainMovementIntegrationTests(unittest.TestCase):
    def test_free_move_consumes_successful_crossing_without_second_test(
        self,
    ) -> None:
        round_state = active_round()
        state = spatial_state()
        traversal = resolve_difficult_terrain_traversal(
            terrain_request(round_state, state),
            SequenceRandom([1]),
        )
        source = free_movement_request(round_state, state)

        result = resolve_difficult_terrain_free_movement(
            DifficultTerrainFreeMovementRequest(
                id="consume:free",
                free_movement=source,
                terrain_traversal=traversal,
                state=traversal.state,
            )
        )

        self.assertEqual(result.state.placement_for("hero").zone_id, "zone:b")
        self.assertEqual(result.state.free_move_used_entity_ids, ("hero",))
        self.assertEqual(
            result.state.difficult_terrain_tested_entity_ids,
            ("hero",),
        )
        self.assertEqual(result.conditions, ConditionState())
        self.assertEqual(result.round_state, round_state)
        self.assertIn(
            DIFFICULT_TERRAIN_FREE_MOVEMENT_RULE_ID,
            result.applied_rule_ids,
        )

    def test_failed_crossing_still_spends_free_move_and_preserves_prone(
        self,
    ) -> None:
        round_state = active_round()
        state = spatial_state()
        conditions = ConditionState({Condition.DISTRACTED})
        traversal = resolve_difficult_terrain_traversal(
            terrain_request(round_state, state, conditions),
            SequenceRandom([10]),
        )

        result = resolve_difficult_terrain_free_movement(
            DifficultTerrainFreeMovementRequest(
                id="consume:free",
                free_movement=free_movement_request(
                    round_state,
                    state,
                    conditions,
                ),
                terrain_traversal=traversal,
                state=traversal.state,
            )
        )

        self.assertTrue(result.conditions.has(Condition.PRONE))
        self.assertTrue(result.conditions.has(Condition.DISTRACTED))
        self.assertEqual(result.state.placement_for("hero").zone_id, "zone:b")
        self.assertEqual(result.state.free_move_used_entity_ids, ("hero",))

    def test_free_move_rejects_substitution_and_consumed_state(self) -> None:
        round_state = active_round()
        state = spatial_state()
        traversal = resolve_difficult_terrain_traversal(
            terrain_request(round_state, state),
            SequenceRandom([1]),
        )
        mismatched = free_movement_request(
            round_state,
            state,
            path_entity_ids=("ally",),
        )
        with self.assertRaises(ValueError):
            DifficultTerrainFreeMovementRequest(
                "consume:free",
                mismatched,
                traversal,
                traversal.state,
            )

        valid = DifficultTerrainFreeMovementRequest(
            "consume:free",
            free_movement_request(round_state, state),
            traversal,
            traversal.state,
        )
        consumed = resolve_difficult_terrain_free_movement(valid)
        with self.assertRaises(ValueError):
            replace(valid, state=consumed.state)
        with self.assertRaises(ValueError):
            replace(consumed, state=consumed.previous_state)

    def test_run_consumes_successful_crossing_and_executes_slot(self) -> None:
        round_state = active_round(reserve_run=True)
        state = spatial_state()
        traversal = resolve_difficult_terrain_traversal(
            terrain_request(round_state, state),
            SequenceRandom([1]),
        )
        result = execute_difficult_terrain_run_action(
            DifficultTerrainRunActionExecutionRequest(
                id="consume:run",
                run_action=run_request(round_state, state),
                terrain_traversal=traversal,
                round_state=round_state,
                spatial_state=traversal.state,
            )
        )

        self.assertTrue(result.slot.executed)
        self.assertEqual(
            result.slot.execution.executor_rule_id,
            DIFFICULT_TERRAIN_RUN_ACTION_EXECUTION_RULE_ID,
        )
        self.assertEqual(
            result.slot.execution.result_request_id,
            traversal.request_id,
        )
        self.assertEqual(result.spatial_state, traversal.state)
        ended = end_combat_turn(
            CombatTurnEndRequest("turn:end", result.round_state, "hero")
        )
        self.assertTrue(ended.completed_turn.action_slots[0].executed)

    def test_failed_crossing_still_executes_run_and_preserves_prone(
        self,
    ) -> None:
        round_state = active_round(reserve_run=True)
        state = spatial_state()
        traversal = resolve_difficult_terrain_traversal(
            terrain_request(round_state, state),
            SequenceRandom([10]),
        )
        result = execute_difficult_terrain_run_action(
            DifficultTerrainRunActionExecutionRequest(
                id="consume:run",
                run_action=run_request(round_state, state),
                terrain_traversal=traversal,
                round_state=round_state,
                spatial_state=traversal.state,
            )
        )

        self.assertTrue(result.conditions.has(Condition.PRONE))
        self.assertEqual(result.spatial_state.placement_for("hero").zone_id, "zone:b")
        self.assertTrue(result.slot.executed)

    def test_run_rejects_wrong_provenance_and_repeated_consumption(self) -> None:
        round_state = active_round(reserve_run=True)
        state = spatial_state()
        traversal = resolve_difficult_terrain_traversal(
            terrain_request(round_state, state),
            SequenceRandom([1]),
        )
        with self.assertRaises(ValueError):
            DifficultTerrainRunActionExecutionRequest(
                "consume:run",
                run_request(
                    round_state,
                    state,
                    path_entity_ids=("ally",),
                ),
                traversal,
                round_state,
                traversal.state,
            )

        valid = DifficultTerrainRunActionExecutionRequest(
            "consume:run",
            run_request(round_state, state),
            traversal,
            round_state,
            traversal.state,
        )
        consumed = execute_difficult_terrain_run_action(valid)
        with self.assertRaises(ValueError):
            replace(valid, round_state=consumed.round_state)
        with self.assertRaises(ValueError):
            replace(consumed, round_state=consumed.previous_round_state)

    def test_run_keeps_base_speed_and_manoeuvre_restrictions(self) -> None:
        for speed, conditions in (
            (MovementSpeed.SLOW, ConditionState()),
            (MovementSpeed.NORMAL, ConditionState({Condition.BURDENED})),
        ):
            with self.subTest(speed=speed, conditions=conditions):
                round_state = active_round(reserve_run=True)
                state = spatial_state()
                traversal = resolve_difficult_terrain_traversal(
                    terrain_request(round_state, state, conditions),
                    SequenceRandom([1]),
                )
                composite = DifficultTerrainRunActionExecutionRequest(
                    "consume:run",
                    run_request(
                        round_state,
                        state,
                        conditions,
                        speed=speed,
                    ),
                    traversal,
                    round_state,
                    traversal.state,
                )
                with self.assertRaises(ValueError):
                    execute_difficult_terrain_run_action(composite)

    def test_traversal_result_preserves_full_source_request(self) -> None:
        round_state = active_round()
        state = spatial_state()
        source = terrain_request(
            round_state,
            state,
            path_entity_ids=("ally",),
        )
        traversal = resolve_difficult_terrain_traversal(
            source,
            SequenceRandom([1]),
        )
        self.assertEqual(traversal.source_request, source)
        with self.assertRaises(ValueError):
            replace(
                traversal,
                source_request=replace(source, path_entity_ids=()),
            )


if __name__ == "__main__":
    unittest.main()
