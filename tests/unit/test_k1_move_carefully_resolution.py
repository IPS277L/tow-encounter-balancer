from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.movement_models import (
    FreeMovementRequest,
    MoveCarefullyActionExecutionRequest,
    MoveCarefullySearchChoice,
    MovementSpeed,
)
from towr.domain.spatial_models import (
    SpatialBattleState,
    SpatialEntityPlacement,
    ZoneConnection,
    ZoneGraph,
)
from towr.domain.test_models import DiceModifier, Skill, TestProfile, TestRequest
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
from towr.rules.free_movement_resolution import (
    FREE_MOVEMENT_RULE_ID,
    SPEED_MOVEMENT_RULE_ID,
)
from towr.rules.move_carefully_resolution import (
    MOVE_CAREFULLY_ACTION_EXECUTION_RULE_ID,
    execute_move_carefully_action,
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
        ),
    )


def spatial_state(
    *,
    free_move_used: tuple[str, ...] = (),
) -> SpatialBattleState:
    return SpatialBattleState(
        graph=graph(),
        placements=(
            SpatialEntityPlacement("hero", "heroes", "zone:a"),
            SpatialEntityPlacement("ally", "heroes", "zone:a"),
            SpatialEntityPlacement("enemy", "enemies", "zone:a"),
        ),
        gave_ground_entity_ids=("enemy",),
        free_move_used_entity_ids=free_move_used,
        difficult_terrain_tested_entity_ids=("enemy",),
    )


def active_round() -> CombatRoundState:
    state = CombatRoundState(
        round_number=1,
        participants=(
            CombatTurnParticipant("hero", CombatSide.PLAYERS_AND_ALLIES),
            CombatTurnParticipant("enemy", CombatSide.OPPOSITION),
        ),
    )
    return start_combat_turn(
        CombatTurnStartRequest("turn:hero", state, "hero")
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
            grant_rule_id=(
                "RULE-ABILITY:test-extra-action"
                if grant is ActionSlotGrant.ABILITY
                else None
            ),
        )
    ).state


def move_carefully_declaration() -> CombatActionDeclaration:
    return CombatActionDeclaration(
        CombatActionKind.MANOEUVRE,
        manoeuvre=ManoeuvreKind.MOVE_CAREFULLY,
    )


def reserved_move_carefully() -> CombatRoundState:
    return reserve_action(active_round(), move_carefully_declaration())


def movement_request(
    round_state: CombatRoundState,
    state: SpatialBattleState,
    *,
    speed: MovementSpeed = MovementSpeed.NORMAL,
    conditions: ConditionState = ConditionState(),
    traversed_zone_ids: tuple[str, ...] = ("zone:b",),
    path_entity_ids: tuple[str, ...] = (),
    crosses_obstacle: bool = False,
    crosses_difficult_terrain: bool = True,
) -> FreeMovementRequest:
    return FreeMovementRequest(
        id="movement:carefully",
        round_state=round_state,
        state=state,
        actor_id="hero",
        speed=speed,
        actor_conditions=conditions,
        traversed_zone_ids=traversed_zone_ids,
        path_entity_ids=path_entity_ids,
        crosses_obstacle=crosses_obstacle,
        crosses_difficult_terrain=crosses_difficult_terrain,
    )


def request(
    *,
    round_state: CombatRoundState | None = None,
    state: SpatialBattleState | None = None,
    slot_index: int = 1,
    speed: MovementSpeed = MovementSpeed.NORMAL,
    conditions: ConditionState = ConditionState(),
    traversed_zone_ids: tuple[str, ...] = ("zone:b",),
    path_entity_ids: tuple[str, ...] = (),
    crosses_obstacle: bool = False,
    crosses_difficult_terrain: bool = True,
    search_choice: MoveCarefullySearchChoice = (
        MoveCarefullySearchChoice.DECLINE
    ),
    awareness_test: TestRequest | None = None,
    search_skill: Skill | None = None,
) -> MoveCarefullyActionExecutionRequest:
    round_state = round_state or reserved_move_carefully()
    state = state or spatial_state()
    return MoveCarefullyActionExecutionRequest(
        id="execute:move-carefully",
        free_movement=movement_request(
            round_state,
            state,
            speed=speed,
            conditions=conditions,
            traversed_zone_ids=traversed_zone_ids,
            path_entity_ids=path_entity_ids,
            crosses_obstacle=crosses_obstacle,
            crosses_difficult_terrain=crosses_difficult_terrain,
        ),
        slot_index=slot_index,
        search_choice=search_choice,
        awareness_test=awareness_test,
        search_skill=search_skill,
        round_state=round_state,
        spatial_state=state,
    )


def search_request(**kwargs) -> MoveCarefullyActionExecutionRequest:
    return request(
        search_choice=MoveCarefullySearchChoice.SEARCH,
        awareness_test=TestRequest(
            "test:careful-awareness",
            TestProfile(1, 5),
            dice_modifiers=(DiceModifier("search:context", 1),),
        ),
        search_skill=Skill.AWARENESS,
        **kwargs,
    )


class K1MoveCarefullyResolutionTests(unittest.TestCase):
    def test_decline_search_moves_without_rng_or_terrain_test_usage(self) -> None:
        source = request()

        result = execute_move_carefully_action(source, SequenceRandom([]))

        self.assertEqual(result.spatial_state.placement_for("hero").zone_id, "zone:b")
        self.assertEqual(
            result.spatial_state.free_move_used_entity_ids,
            ("hero",),
        )
        self.assertEqual(
            result.spatial_state.difficult_terrain_tested_entity_ids,
            ("enemy",),
        )
        self.assertEqual(
            result.spatial_state.gave_ground_entity_ids,
            ("enemy",),
        )
        self.assertIsNone(result.awareness_test_result)
        self.assertTrue(result.slot.executed)
        self.assertEqual(
            result.applied_rule_ids,
            (
                MOVE_CAREFULLY_ACTION_EXECUTION_RULE_ID,
                FREE_MOVEMENT_RULE_ID,
                SPEED_MOVEMENT_RULE_ID,
                ZONE_GRAPH_RULE_ID,
            ),
        )

    def test_search_resolves_awareness_after_movement(self) -> None:
        for roll, succeeded in ((1, True), (10, False)):
            with self.subTest(roll=roll):
                source = search_request()
                result = execute_move_carefully_action(
                    source,
                    SequenceRandom([roll, 10]),
                )

                self.assertIs(
                    result.awareness_test_result.succeeded,
                    succeeded,
                )
                self.assertEqual(
                    result.awareness_test_result.trace.request_id,
                    "test:careful-awareness",
                )
                self.assertEqual(
                    result.slot.execution.result_request_id,
                    "test:careful-awareness",
                )
                self.assertIn("search:context", result.applied_rule_ids)
                self.assertTrue(result.slot.executed)

    def test_fast_route_can_cross_two_zone_boundaries(self) -> None:
        result = execute_move_carefully_action(
            request(
                speed=MovementSpeed.FAST,
                traversed_zone_ids=("zone:b", "zone:c"),
            ),
            SequenceRandom([]),
        )
        self.assertEqual(result.spatial_state.placement_for("hero").zone_id, "zone:c")

        with self.assertRaises(ValueError):
            request(traversed_zone_ids=("zone:b", "zone:c"))

    def test_search_choice_and_test_must_agree(self) -> None:
        awareness = TestRequest("test:awareness", TestProfile(1, 5))
        with self.assertRaises(ValueError):
            request(awareness_test=awareness, search_skill=Skill.AWARENESS)
        with self.assertRaises(TypeError):
            request(search_choice=MoveCarefullySearchChoice.SEARCH)
        with self.assertRaises(ValueError):
            request(
                search_choice=MoveCarefullySearchChoice.SEARCH,
                awareness_test=awareness,
                search_skill=Skill.ATHLETICS,
            )
        with self.assertRaises(ValueError):
            request(crosses_difficult_terrain=False)

    def test_movement_and_manoeuvre_blockers_close_before_rng(self) -> None:
        blocked = (
            request(speed=MovementSpeed.SLOW),
            request(conditions=ConditionState({Condition.BURDENED})),
            request(conditions=ConditionState({Condition.PRONE})),
            request(conditions=ConditionState({Condition.DEFENCELESS})),
            request(crosses_obstacle=True),
            request(path_entity_ids=("enemy",)),
            request(state=spatial_state(free_move_used=("hero",))),
            request(traversed_zone_ids=("zone:d",)),
        )
        for source in blocked:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    execute_move_carefully_action(
                        source,
                        SequenceRandom([]),
                    )

        with self.assertRaises(ValueError):
            execute_move_carefully_action(
                search_request(path_entity_ids=("enemy",)),
                SequenceRandom([]),
            )

        allied = execute_move_carefully_action(
            request(path_entity_ids=("ally",)),
            SequenceRandom([]),
        )
        self.assertEqual(allied.destination_zone_id, "zone:b")

    def test_requires_reserved_slot_order_and_search_rng(self) -> None:
        aim_state = reserve_action(
            active_round(),
            CombatActionDeclaration(CombatActionKind.AIM),
        )
        with self.assertRaises(ValueError):
            execute_move_carefully_action(
                request(round_state=aim_state),
                SequenceRandom([]),
            )
        with self.assertRaises(ValueError):
            execute_move_carefully_action(request(slot_index=2))
        with self.assertRaises(ValueError):
            execute_move_carefully_action(search_request())

        state = reserve_action(
            active_round(),
            CombatActionDeclaration(CombatActionKind.AIM),
        )
        state = reserve_action(
            state,
            move_carefully_declaration(),
            grant=ActionSlotGrant.ABILITY,
        )
        with self.assertRaises(ValueError):
            execute_move_carefully_action(
                request(round_state=state, slot_index=2),
                SequenceRandom([]),
            )

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
        executed = execute_move_carefully_action(
            request(round_state=state, slot_index=2),
            SequenceRandom([]),
        )
        self.assertIs(executed.round_state.active_turn.action_slots[0], first_slot)

    def test_slot_must_execute_once_before_turn_ends(self) -> None:
        source = request()
        with self.assertRaises(ValueError):
            end_combat_turn(
                CombatTurnEndRequest(
                    "turn:end",
                    source.round_state,
                    "hero",
                )
            )

        result = execute_move_carefully_action(source, SequenceRandom([]))
        ended = end_combat_turn(
            CombatTurnEndRequest("turn:end", result.round_state, "hero")
        )
        self.assertTrue(ended.completed_turn.action_slots[0].executed)
        with self.assertRaises(ValueError):
            replace(source, round_state=result.round_state)

    def test_result_rejects_spatial_search_condition_and_turn_forgery(
        self,
    ) -> None:
        result = execute_move_carefully_action(
            search_request(),
            SequenceRandom([1, 10]),
        )
        with self.assertRaises(ValueError):
            replace(result, spatial_state=result.previous_spatial_state)
        with self.assertRaises(ValueError):
            replace(
                result,
                spatial_state=replace(
                    result.spatial_state,
                    difficult_terrain_tested_entity_ids=("enemy", "hero"),
                ),
            )
        with self.assertRaises(ValueError):
            replace(result, conditions=ConditionState({Condition.PRONE}))
        with self.assertRaises(TypeError):
            replace(result, awareness_test_result=None)
        with self.assertRaises(ValueError):
            replace(result, round_state=result.previous_round_state)


if __name__ == "__main__":
    unittest.main()
