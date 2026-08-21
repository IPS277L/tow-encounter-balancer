from __future__ import annotations

import unittest
from dataclasses import replace

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.movement_models import (
    FreeMovementRequest,
    FreeMoveProneRemovalRequest,
    MovementSpeed,
    ProneRemovalTargetKind,
)
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
    FREE_MOVE_PRONE_REMOVAL_RULE_ID,
    resolve_free_movement,
    resolve_free_move_prone_removal,
)
from towr.rules.turn_resolution import start_combat_turn


def spatial_state(
    *,
    round_number: int = 1,
    free_move_used: tuple[str, ...] = (),
) -> SpatialBattleState:
    return SpatialBattleState(
        graph=ZoneGraph(
            zone_ids=("zone:a", "zone:b"),
            connections=(ZoneConnection("zone:a", "zone:b"),),
        ),
        placements=(
            SpatialEntityPlacement("hero", "heroes", "zone:a"),
            SpatialEntityPlacement("ally", "heroes", "zone:a"),
            SpatialEntityPlacement("enemy", "enemies", "zone:a"),
        ),
        round_number=round_number,
        free_move_used_entity_ids=free_move_used,
    )


def active_round(*, round_number: int = 1) -> CombatRoundState:
    state = CombatRoundState(
        round_number=round_number,
        participants=(
            CombatTurnParticipant("hero", CombatSide.PLAYERS_AND_ALLIES),
            CombatTurnParticipant("ally", CombatSide.PLAYERS_AND_ALLIES),
            CombatTurnParticipant("enemy", CombatSide.OPPOSITION),
        ),
    )
    return start_combat_turn(
        CombatTurnStartRequest("turn:hero", state, "hero")
    ).state


def prone_request(
    *,
    round_state: CombatRoundState | None = None,
    state: SpatialBattleState | None = None,
    target_kind: ProneRemovalTargetKind = ProneRemovalTargetKind.SELF,
    target_id: str = "hero",
    target_conditions: ConditionState | None = None,
    target_in_close_range: bool | None = None,
    actor_has_enemy_in_close_range: bool = False,
) -> FreeMoveProneRemovalRequest:
    return FreeMoveProneRemovalRequest(
        id="free-move:remove-prone",
        round_state=round_state or active_round(),
        state=state or spatial_state(),
        actor_id="hero",
        target_kind=target_kind,
        target_id=target_id,
        target_conditions=(
            target_conditions
            if target_conditions is not None
            else ConditionState({Condition.PRONE})
        ),
        target_in_close_range=target_in_close_range,
        actor_has_enemy_in_close_range=actor_has_enemy_in_close_range,
    )


def movement_request(state: SpatialBattleState) -> FreeMovementRequest:
    return FreeMovementRequest(
        id="free-move:movement",
        round_state=active_round(),
        state=state,
        actor_id="hero",
        speed=MovementSpeed.NORMAL,
        actor_conditions=ConditionState(),
        traversed_zone_ids=("zone:b",),
    )


class K1FreeMoveProneRemovalTests(unittest.TestCase):
    def test_actor_removes_own_prone_without_moving_or_using_action(self) -> None:
        request = prone_request(
            target_conditions=ConditionState(
                {Condition.PRONE, Condition.STAGGERED}
            )
        )

        result = resolve_free_move_prone_removal(request)

        self.assertEqual(
            result.target_conditions,
            ConditionState({Condition.STAGGERED}),
        )
        self.assertEqual(result.state.placements, request.state.placements)
        self.assertEqual(result.state.free_move_used_entity_ids, ("hero",))
        self.assertEqual(result.round_state, request.round_state)
        assert result.round_state.active_turn is not None
        self.assertEqual(result.round_state.active_turn.action_slots, ())
        self.assertEqual(
            result.applied_rule_ids,
            (FREE_MOVE_PRONE_REMOVAL_RULE_ID, FREE_MOVEMENT_RULE_ID),
        )

    def test_actor_can_remove_prone_from_close_ally(self) -> None:
        result = resolve_free_move_prone_removal(
            prone_request(
                target_kind=ProneRemovalTargetKind.ALLY,
                target_id="ally",
                target_in_close_range=True,
            )
        )

        self.assertEqual(result.target_id, "ally")
        self.assertEqual(result.target_conditions, ConditionState())
        self.assertEqual(result.state.placement_for("ally").zone_id, "zone:a")

    def test_enemy_in_close_range_prevents_prone_removal(self) -> None:
        with self.assertRaises(ValueError):
            resolve_free_move_prone_removal(
                prone_request(actor_has_enemy_in_close_range=True)
            )

    def test_ally_must_be_close_friendly_and_distinct_from_actor(self) -> None:
        with self.assertRaises(ValueError):
            resolve_free_move_prone_removal(
                prone_request(
                    target_kind=ProneRemovalTargetKind.ALLY,
                    target_id="ally",
                    target_in_close_range=False,
                )
            )
        with self.assertRaises(ValueError):
            prone_request(
                target_kind=ProneRemovalTargetKind.ALLY,
                target_id="enemy",
                target_in_close_range=True,
            )
        with self.assertRaises(ValueError):
            prone_request(
                target_kind=ProneRemovalTargetKind.ALLY,
                target_id="hero",
                target_in_close_range=True,
            )
        with self.assertRaises(ValueError):
            prone_request(target_in_close_range=True)

    def test_target_must_actually_be_prone(self) -> None:
        with self.assertRaises(ValueError):
            resolve_free_move_prone_removal(
                prone_request(target_conditions=ConditionState())
            )

    def test_movement_and_prone_removal_share_one_usage(self) -> None:
        moved = resolve_free_movement(movement_request(spatial_state()))
        with self.assertRaises(ValueError):
            resolve_free_move_prone_removal(prone_request(state=moved.state))

        removed = resolve_free_move_prone_removal(prone_request())
        with self.assertRaises(ValueError):
            resolve_free_movement(movement_request(removed.state))

    def test_request_requires_matching_active_actor_and_round(self) -> None:
        with self.assertRaises(ValueError):
            prone_request(
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
            prone_request(state=spatial_state(round_number=2))

    def test_result_rejects_condition_spatial_or_context_forgery(self) -> None:
        result = resolve_free_move_prone_removal(
            prone_request(
                target_kind=ProneRemovalTargetKind.ALLY,
                target_id="ally",
                target_in_close_range=True,
            )
        )

        with self.assertRaises(ValueError):
            replace(result, target_conditions=ConditionState({Condition.PRONE}))
        with self.assertRaises(ValueError):
            replace(
                result,
                state=replace(result.state, free_move_used_entity_ids=()),
            )
        with self.assertRaises(ValueError):
            replace(result, target_in_close_range=False)
        with self.assertRaises(ValueError):
            replace(result, actor_has_enemy_in_close_range=True)
        with self.assertRaises(ValueError):
            replace(result, rule_id="RULE-COMBAT-014:forged")
        with self.assertRaises(TypeError):
            replace(result, target_kind="ally")


if __name__ == "__main__":
    unittest.main()
