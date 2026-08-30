from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.move_quietly_models import (
    MOVE_QUIETLY_RULE_ID,
    MOVE_QUIETLY_TIE_RULE_ID,
    MoveQuietlyActionExecutionRequest,
    MoveQuietlyHidingChoice,
    MoveQuietlyObserver,
    MoveQuietlyOutcome,
)
from towr.domain.movement_models import FreeMovementRequest, MovementSpeed
from towr.domain.spatial_models import (
    SpatialBattleState,
    SpatialEntityPlacement,
    ZoneConnection,
    ZoneGraph,
)
from towr.domain.test_models import (
    OpposedOutcome,
    OpposedSide,
    OpposedTestRequest,
    Skill,
    TestProfile,
    TestRequest,
    TieBreak,
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
from towr.rules.move_quietly_resolution import execute_move_quietly_action
from towr.rules.turn_resolution import (
    end_combat_turn,
    reserve_combat_action_slot,
    start_combat_turn,
)


def spatial_state(
    *,
    free_move_used: tuple[str, ...] = (),
) -> SpatialBattleState:
    return SpatialBattleState(
        graph=ZoneGraph(
            zone_ids=("zone:a", "zone:b", "zone:c", "zone:d"),
            connections=(
                ZoneConnection("zone:a", "zone:b"),
                ZoneConnection("zone:b", "zone:c"),
            ),
        ),
        placements=(
            SpatialEntityPlacement("hero", "heroes", "zone:a"),
            SpatialEntityPlacement("ally", "heroes", "zone:a"),
            SpatialEntityPlacement("scout", "enemies", "zone:b"),
            SpatialEntityPlacement("guard", "enemies", "zone:c"),
        ),
        gave_ground_entity_ids=("guard",),
        free_move_used_entity_ids=free_move_used,
        difficult_terrain_tested_entity_ids=("guard",),
    )


def active_round() -> CombatRoundState:
    state = CombatRoundState(
        round_number=1,
        participants=(
            CombatTurnParticipant("hero", CombatSide.PLAYERS_AND_ALLIES),
            CombatTurnParticipant("scout", CombatSide.OPPOSITION),
            CombatTurnParticipant("guard", CombatSide.OPPOSITION),
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


def move_quietly_declaration() -> CombatActionDeclaration:
    return CombatActionDeclaration(
        CombatActionKind.MANOEUVRE,
        manoeuvre=ManoeuvreKind.MOVE_QUIETLY,
    )


def reserved_move_quietly() -> CombatRoundState:
    return reserve_action(active_round(), move_quietly_declaration())


def default_observers() -> tuple[MoveQuietlyObserver, ...]:
    return (
        MoveQuietlyObserver(
            "scout",
            TestRequest("test:scout-awareness", TestProfile(3, 5)),
            vigilance_priority=1,
        ),
        MoveQuietlyObserver(
            "guard",
            TestRequest("test:guard-awareness", TestProfile(1, 5)),
            vigilance_priority=3,
        ),
    )


def request(
    *,
    round_state: CombatRoundState | None = None,
    state: SpatialBattleState | None = None,
    observers: tuple[MoveQuietlyObserver, ...] | None = None,
    opposed_test: OpposedTestRequest | None = None,
    slot_index: int = 1,
    speed: MovementSpeed = MovementSpeed.NORMAL,
    conditions: ConditionState = ConditionState(),
    has_cover: bool = True,
    include_movement: bool = True,
    traversed_zone_ids: tuple[str, ...] = ("zone:b",),
    path_entity_ids: tuple[str, ...] = (),
    crosses_obstacle: bool = False,
    crosses_difficult_terrain: bool = False,
    hiding_position_id: str = "hiding:wall",
    used_hiding_position_ids: tuple[str, ...] = (),
    hiding_choice: MoveQuietlyHidingChoice | None = None,
) -> MoveQuietlyActionExecutionRequest:
    round_state = round_state or reserved_move_quietly()
    state = state or spatial_state()
    observers = default_observers() if observers is None else observers
    selected = max(
        enumerate(observers),
        key=lambda item: (item[1].vigilance_priority, -item[0]),
    )[1]
    stealth = TestRequest("test:hero-stealth", TestProfile(2, 5))
    opposed_test = opposed_test or OpposedTestRequest(
        "opposed:move-quietly",
        initiator=stealth,
        opponent=selected.awareness_test,
        tie_break=TieBreak(
            MOVE_QUIETLY_TIE_RULE_ID,
            OpposedSide.INITIATOR,
        ),
    )
    movement = None
    if include_movement:
        movement = FreeMovementRequest(
            id="movement:quietly",
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
    if hiding_choice is None:
        hiding_choice = (
            MoveQuietlyHidingChoice.HIDE_ALONG_ROUTE
            if include_movement
            else MoveQuietlyHidingChoice.DECLINE
        )
    return MoveQuietlyActionExecutionRequest(
        id="execute:move-quietly",
        actor_id="hero",
        slot_index=slot_index,
        speed=speed,
        actor_conditions=conditions,
        observers=observers,
        opposed_test=opposed_test,
        round_state=round_state,
        spatial_state=state,
        has_cover_or_concealment=has_cover,
        hiding_choice=hiding_choice,
        free_movement=movement,
        hiding_position_id=(
            hiding_position_id
            if hiding_choice is not MoveQuietlyHidingChoice.DECLINE
            else None
        ),
        used_hiding_position_ids=used_hiding_position_ids,
    )


class K1MoveQuietlyResolutionTests(unittest.TestCase):
    def test_most_vigilant_enemy_is_opposed_and_success_hides(self) -> None:
        source = request()

        result = execute_move_quietly_action(
            source,
            SequenceRandom([1, 10, 10]),
        )

        self.assertEqual(result.selected_observer.entity_id, "guard")
        self.assertIs(result.outcome, MoveQuietlyOutcome.HIDDEN)
        self.assertEqual(
            result.spatial_state.placement_for("hero").zone_id,
            "zone:b",
        )
        self.assertEqual(result.spatial_state.free_move_used_entity_ids, ("hero",))
        self.assertEqual(result.spatial_state.gave_ground_entity_ids, ("guard",))
        self.assertEqual(
            result.spatial_state.difficult_terrain_tested_entity_ids,
            ("guard",),
        )
        opportunity = result.hidden_attack_opportunity
        self.assertEqual(opportunity.hiding_position_id, "hiding:wall")
        self.assertEqual(opportunity.unaware_enemy_ids, ("scout", "guard"))
        self.assertTrue(result.slot.executed)

        fast = execute_move_quietly_action(
            request(
                speed=MovementSpeed.FAST,
                traversed_zone_ids=("zone:b", "zone:c"),
                hiding_position_id="hiding:tower",
            ),
            SequenceRandom([1, 10, 10]),
        )
        self.assertEqual(
            fast.spatial_state.placement_for("hero").zone_id,
            "zone:c",
        )

    def test_equal_priority_uses_snapshot_order_and_nonzero_tie_wins(self) -> None:
        observers = (
            MoveQuietlyObserver(
                "scout",
                TestRequest("test:scout-awareness", TestProfile(1, 5)),
                vigilance_priority=2,
            ),
            MoveQuietlyObserver(
                "guard",
                TestRequest("test:guard-awareness", TestProfile(1, 5)),
                vigilance_priority=2,
            ),
        )

        result = execute_move_quietly_action(
            request(observers=observers),
            SequenceRandom([1, 10, 1]),
        )

        self.assertEqual(result.selected_observer.entity_id, "scout")
        self.assertIs(
            result.opposed_test_result.outcome,
            OpposedOutcome.INITIATOR_WINS,
        )
        self.assertTrue(result.opposed_test_result.tie_break_applied)
        self.assertIs(result.outcome, MoveQuietlyOutcome.HIDDEN)

    def test_failed_contest_does_not_spend_conditional_free_move(self) -> None:
        for rolls, opposed_outcome in (
            ((10, 10, 1), OpposedOutcome.OPPONENT_WINS),
            ((10, 10, 10), OpposedOutcome.BOTH_FAIL),
        ):
            with self.subTest(rolls=rolls):
                result = execute_move_quietly_action(
                    request(),
                    SequenceRandom(list(rolls)),
                )
                self.assertIs(result.outcome, MoveQuietlyOutcome.FAILED)
                self.assertIs(result.opposed_test_result.outcome, opposed_outcome)
                self.assertEqual(result.spatial_state, result.previous_spatial_state)
                self.assertIsNone(result.free_movement_result)
                self.assertIsNone(result.hidden_attack_opportunity)
                self.assertTrue(result.slot.executed)

    def test_success_without_hiding_is_explicit_and_spends_no_move(self) -> None:
        result = execute_move_quietly_action(
            request(has_cover=False, include_movement=False),
            SequenceRandom([1, 10, 10]),
        )

        self.assertIs(
            result.outcome,
            MoveQuietlyOutcome.SUCCEEDED_WITHOUT_HIDING,
        )
        self.assertEqual(result.spatial_state, result.previous_spatial_state)
        self.assertIsNone(result.hidden_attack_opportunity)

        same_zone = execute_move_quietly_action(
            request(
                include_movement=False,
                hiding_choice=MoveQuietlyHidingChoice.HIDE_IN_CURRENT_ZONE,
                hiding_position_id="hiding:crates",
            ),
            SequenceRandom([1, 10, 10]),
        )
        self.assertIs(same_zone.outcome, MoveQuietlyOutcome.HIDDEN)
        self.assertEqual(
            same_zone.spatial_state.placement_for("hero").zone_id,
            "zone:a",
        )
        self.assertEqual(
            same_zone.spatial_state.free_move_used_entity_ids,
            ("hero",),
        )

    def test_hiding_requires_cover_movement_and_new_position(self) -> None:
        with self.assertRaises(ValueError):
            request(has_cover=False)
        with self.assertRaises(ValueError):
            request(
                used_hiding_position_ids=("hiding:wall",),
            )
        with self.assertRaises(ValueError):
            replace(
                request(include_movement=False),
                hiding_position_id="hiding:wall",
            )
        with self.assertRaises(ValueError):
            request(crosses_difficult_terrain=True)

    def test_movement_and_manoeuvre_blockers_close_before_rng(self) -> None:
        blocked = (
            request(speed=MovementSpeed.SLOW),
            request(conditions=ConditionState({Condition.BURDENED})),
            request(conditions=ConditionState({Condition.PRONE})),
            request(conditions=ConditionState({Condition.DEFENCELESS})),
            request(crosses_obstacle=True),
            request(path_entity_ids=("guard",)),
            request(state=spatial_state(free_move_used=("hero",))),
            request(
                state=spatial_state(free_move_used=("hero",)),
                include_movement=False,
                hiding_choice=MoveQuietlyHidingChoice.HIDE_IN_CURRENT_ZONE,
            ),
            request(traversed_zone_ids=("zone:d",)),
        )
        for source in blocked:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    execute_move_quietly_action(source, SequenceRandom([]))

        allied = execute_move_quietly_action(
            request(path_entity_ids=("ally",)),
            SequenceRandom([1, 10, 10]),
        )
        self.assertIs(allied.outcome, MoveQuietlyOutcome.HIDDEN)

    def test_observer_snapshot_and_opposed_provenance_are_strict(self) -> None:
        with self.assertRaises(ValueError):
            request(observers=())
        ally = MoveQuietlyObserver(
            "ally",
            TestRequest("test:ally-awareness", TestProfile(1, 5)),
            vigilance_priority=4,
        )
        with self.assertRaises(ValueError):
            request(observers=(ally,))
        with self.assertRaises(ValueError):
            MoveQuietlyObserver(
                "guard",
                TestRequest("test:wrong-skill", TestProfile(1, 5)),
                vigilance_priority=1,
                awareness_skill=Skill.STEALTH,
            )

        observers = default_observers()
        wrong = OpposedTestRequest(
            "opposed:wrong",
            initiator=TestRequest("test:hero-stealth", TestProfile(2, 5)),
            opponent=observers[0].awareness_test,
            tie_break=TieBreak(
                MOVE_QUIETLY_TIE_RULE_ID,
                OpposedSide.INITIATOR,
            ),
        )
        with self.assertRaises(ValueError):
            request(observers=observers, opposed_test=wrong)

    def test_slot_must_be_reserved_ordered_and_executed_once(self) -> None:
        aim_state = reserve_action(
            active_round(),
            CombatActionDeclaration(CombatActionKind.AIM),
        )
        with self.assertRaises(ValueError):
            execute_move_quietly_action(
                request(round_state=aim_state),
                SequenceRandom([]),
            )
        with self.assertRaises(ValueError):
            execute_move_quietly_action(request(slot_index=2), SequenceRandom([]))

        state = reserve_action(
            active_round(),
            CombatActionDeclaration(CombatActionKind.AIM),
        )
        state = reserve_action(
            state,
            move_quietly_declaration(),
            grant=ActionSlotGrant.ABILITY,
        )
        with self.assertRaises(ValueError):
            execute_move_quietly_action(
                request(round_state=state, slot_index=2),
                SequenceRandom([]),
            )

        turn = state.active_turn
        first = replace(
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
            active_turn=replace(turn, action_slots=(first, turn.action_slots[1])),
        )
        result = execute_move_quietly_action(
            request(round_state=state, slot_index=2),
            SequenceRandom([1, 10, 10]),
        )
        with self.assertRaises(ValueError):
            replace(result.source_request, round_state=result.round_state)

    def test_failure_still_completes_slot_and_result_rejects_forgery(self) -> None:
        source = request()
        with self.assertRaises(ValueError):
            end_combat_turn(
                CombatTurnEndRequest("turn:end", source.round_state, "hero")
            )

        result = execute_move_quietly_action(
            source,
            SequenceRandom([10, 10, 1]),
        )
        ended = end_combat_turn(
            CombatTurnEndRequest("turn:end", result.round_state, "hero")
        )
        self.assertTrue(ended.completed_turn.action_slots[0].executed)
        with self.assertRaises(ValueError):
            replace(
                result,
                spatial_state=replace(
                    result.previous_spatial_state,
                    free_move_used_entity_ids=("hero",),
                ),
            )
        with self.assertRaises(ValueError):
            replace(result, outcome=MoveQuietlyOutcome.HIDDEN)
        with self.assertRaises(ValueError):
            replace(result, round_state=result.previous_round_state)


if __name__ == "__main__":
    unittest.main()
