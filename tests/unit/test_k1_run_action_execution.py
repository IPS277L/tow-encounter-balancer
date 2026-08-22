from __future__ import annotations

import unittest
from dataclasses import replace

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.movement_models import (
    MovementSpeed,
    RunActionExecutionRequest,
)
from towr.domain.spatial_models import (
    SpatialBattleState,
    SpatialEntityPlacement,
    ZoneConnection,
    ZoneGraph,
)
from towr.domain.turn_models import (
    ActionExecutionReceipt,
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
from towr.rules.free_movement_resolution import SPEED_MOVEMENT_RULE_ID
from towr.rules.run_action_execution import (
    RUN_ACTION_EXECUTION_RULE_ID,
    execute_run_action,
)
from towr.rules.spatial_resolution import ZONE_GRAPH_RULE_ID
from towr.rules.turn_resolution import (
    end_combat_turn,
    reserve_combat_action_slot,
    start_combat_turn,
)


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
) -> SpatialBattleState:
    return SpatialBattleState(
        graph=graph(),
        placements=(
            SpatialEntityPlacement("hero", "heroes", "zone:a"),
            SpatialEntityPlacement("ally", "heroes", "zone:a"),
            SpatialEntityPlacement("enemy", "enemies", "zone:a"),
        ),
        round_number=round_number,
        free_move_used_entity_ids=free_move_used,
    )


def active_round() -> CombatRoundState:
    source = CombatRoundState(
        round_number=1,
        participants=(
            CombatTurnParticipant(
                "hero",
                CombatSide.PLAYERS_AND_ALLIES,
            ),
            CombatTurnParticipant("enemy", CombatSide.OPPOSITION),
        ),
    )
    return start_combat_turn(
        CombatTurnStartRequest("turn:hero", source, "hero")
    ).state


def reserve_action(
    state: CombatRoundState,
    declaration: CombatActionDeclaration,
    *,
    grant: ActionSlotGrant = ActionSlotGrant.STANDARD,
) -> CombatRoundState:
    return reserve_combat_action_slot(
        CombatActionSlotRequest(
            id=f"slot:{len(state.active_turn.action_slots) + 1}",
            state=state,
            actor_id="hero",
            declaration=declaration,
            grant=grant,
        )
    ).state


def run_declaration() -> CombatActionDeclaration:
    return CombatActionDeclaration(
        CombatActionKind.MANOEUVRE,
        manoeuvre=ManoeuvreKind.RUN,
    )


def reserved_run() -> CombatRoundState:
    return reserve_action(active_round(), run_declaration())


def request(
    *,
    round_state: CombatRoundState | None = None,
    state: SpatialBattleState | None = None,
    actor_id: str = "hero",
    slot_index: int = 1,
    speed: MovementSpeed = MovementSpeed.NORMAL,
    conditions: ConditionState = ConditionState(),
    destination_zone_id: str = "zone:b",
    path_entity_ids: tuple[str, ...] = (),
    crosses_obstacle: bool = False,
    crosses_difficult_terrain: bool = False,
) -> RunActionExecutionRequest:
    return RunActionExecutionRequest(
        id="execute:run",
        round_state=round_state or reserved_run(),
        spatial_state=state or spatial_state(),
        actor_id=actor_id,
        slot_index=slot_index,
        speed=speed,
        actor_conditions=conditions,
        destination_zone_id=destination_zone_id,
        path_entity_ids=path_entity_ids,
        crosses_obstacle=crosses_obstacle,
        crosses_difficult_terrain=crosses_difficult_terrain,
    )


class K1RunActionExecutionTests(unittest.TestCase):
    def test_normal_run_moves_one_extra_zone_and_executes_slot(self) -> None:
        source = request(state=spatial_state(free_move_used=("hero",)))

        result = execute_run_action(source)

        self.assertEqual(result.origin_zone_id, "zone:a")
        self.assertEqual(result.destination_zone_id, "zone:b")
        self.assertEqual(
            result.spatial_state.placement_for("hero").zone_id,
            "zone:b",
        )
        self.assertEqual(
            result.spatial_state.free_move_used_entity_ids,
            ("hero",),
        )
        self.assertTrue(result.slot.executed)
        self.assertEqual(result.slot.execution.source_request_id, source.id)
        self.assertEqual(result.slot.execution.result_request_id, source.id)
        self.assertEqual(
            result.applied_rule_ids,
            (
                RUN_ACTION_EXECUTION_RULE_ID,
                SPEED_MOVEMENT_RULE_ID,
                ZONE_GRAPH_RULE_ID,
            ),
        )

    def test_normal_and_fast_run_have_the_same_base_distance(self) -> None:
        for speed in (MovementSpeed.NORMAL, MovementSpeed.FAST):
            with self.subTest(speed=speed):
                result = execute_run_action(request(speed=speed))
                self.assertEqual(result.destination_zone_id, "zone:b")

    def test_slow_and_movement_conditions_block_run(self) -> None:
        blocked = (
            request(speed=MovementSpeed.SLOW),
            request(conditions=ConditionState({Condition.BURDENED})),
            request(conditions=ConditionState({Condition.PRONE})),
            request(conditions=ConditionState({Condition.DEFENCELESS})),
        )

        for source in blocked:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    execute_run_action(source)
                self.assertFalse(
                    source.round_state.active_turn.action_slots[0].executed
                )

    def test_run_requires_one_adjacent_known_zone(self) -> None:
        for destination in ("zone:c", "zone:unknown", "zone:a"):
            with self.subTest(destination=destination):
                with self.assertRaises(ValueError):
                    execute_run_action(
                        request(destination_zone_id=destination)
                    )

    def test_incomplete_or_enemy_blocked_path_is_rejected(self) -> None:
        blocked = (
            request(crosses_obstacle=True),
            request(crosses_difficult_terrain=True),
            request(path_entity_ids=("enemy",)),
        )
        for source in blocked:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    execute_run_action(source)

        result = execute_run_action(request(path_entity_ids=("ally",)))
        self.assertEqual(result.destination_zone_id, "zone:b")

    def test_run_requires_matching_active_round_actor_and_slot(self) -> None:
        with self.assertRaises(ValueError):
            request(actor_id="enemy")
        with self.assertRaises(ValueError):
            request(state=spatial_state(round_number=2))

        aim_state = reserve_action(
            active_round(),
            CombatActionDeclaration(CombatActionKind.AIM),
        )
        with self.assertRaises(ValueError):
            execute_run_action(request(round_state=aim_state))
        with self.assertRaises(ValueError):
            execute_run_action(request(slot_index=2))

    def test_second_slot_requires_completed_first_slot(self) -> None:
        state = reserve_action(
            active_round(),
            CombatActionDeclaration(CombatActionKind.AIM),
        )
        state = reserve_action(
            state,
            run_declaration(),
            grant=ActionSlotGrant.FATE,
        )
        with self.assertRaises(ValueError):
            execute_run_action(request(round_state=state, slot_index=2))

        turn = state.active_turn
        first_slot = replace(
            turn.action_slots[0],
            execution=ActionExecutionReceipt(
                id="execute:aim",
                executor_rule_id="RULE-COMBAT-004:aim-action-execution",
                source_request_id="aim:test",
                result_request_id="aim:test",
                actor_id=turn.actor_id,
                round_number=state.round_number,
                slot_index=turn.action_slots[0].index,
                declaration=turn.action_slots[0].declaration,
            ),
        )
        state = replace(
            state,
            active_turn=replace(
                turn,
                action_slots=(first_slot, turn.action_slots[1]),
            ),
        )

        result = execute_run_action(
            request(round_state=state, slot_index=2)
        )

        self.assertIs(result.round_state.active_turn.action_slots[0], first_slot)
        self.assertTrue(result.round_state.active_turn.action_slots[1].executed)

    def test_run_slot_must_execute_before_turn_ends_and_only_once(self) -> None:
        state = reserved_run()
        with self.assertRaises(ValueError):
            end_combat_turn(CombatTurnEndRequest("turn:end", state, "hero"))

        result = execute_run_action(request(round_state=state))
        ended = end_combat_turn(
            CombatTurnEndRequest("turn:end", result.round_state, "hero")
        )
        self.assertTrue(ended.completed_turn.action_slots[0].executed)

        with self.assertRaises(ValueError):
            execute_run_action(
                request(
                    round_state=result.round_state,
                    state=result.spatial_state,
                )
            )

    def test_result_rejects_forged_spatial_and_turn_transitions(self) -> None:
        result = execute_run_action(request())

        with self.assertRaises(ValueError):
            replace(result, spatial_state=result.previous_spatial_state)
        with self.assertRaises(ValueError):
            replace(result, round_state=result.previous_round_state)
        with self.assertRaises(ValueError):
            replace(result, speed=MovementSpeed.SLOW)


if __name__ == "__main__":
    unittest.main()
