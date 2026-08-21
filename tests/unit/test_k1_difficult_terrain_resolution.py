from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.movement_models import (
    DifficultTerrainOutcome,
    DifficultTerrainTraversalRequest,
)
from towr.domain.spatial_models import (
    SpatialBattleState,
    SpatialEntityPlacement,
    ZoneConnection,
    ZoneGraph,
)
from towr.domain.test_models import DiceModifier, Skill, TestProfile, TestRequest
from towr.domain.turn_models import (
    CombatRoundState,
    CombatSide,
    CombatTurnParticipant,
    CombatTurnStartRequest,
)
from towr.rules.difficult_terrain_resolution import (
    DIFFICULT_TERRAIN_TRAVERSAL_RULE_ID,
    resolve_difficult_terrain_traversal,
)
from towr.rules.spatial_resolution import (
    ZONE_GRAPH_RULE_ID,
    start_next_spatial_round,
)
from towr.rules.turn_resolution import start_combat_turn


def active_round(*, actor_id: str = "hero") -> CombatRoundState:
    state = CombatRoundState(
        round_number=1,
        participants=(
            CombatTurnParticipant("hero", CombatSide.PLAYERS_AND_ALLIES),
            CombatTurnParticipant("enemy", CombatSide.OPPOSITION),
        ),
    )
    return start_combat_turn(
        CombatTurnStartRequest(f"turn:{actor_id}", state, actor_id)
    ).state


def spatial_state() -> SpatialBattleState:
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
            SpatialEntityPlacement("ally", "heroes", "zone:b"),
            SpatialEntityPlacement("enemy", "enemies", "zone:b"),
        ),
        gave_ground_entity_ids=("enemy",),
        free_move_used_entity_ids=("enemy",),
    )


def request(
    *,
    round_state: CombatRoundState | None = None,
    state: SpatialBattleState | None = None,
    conditions: ConditionState = ConditionState(),
    athletics_test: TestRequest | None = None,
    destination_zone_id: str = "zone:b",
    path_entity_ids: tuple[str, ...] = (),
    crosses_obstacle: bool = False,
    skill: Skill = Skill.ATHLETICS,
) -> DifficultTerrainTraversalRequest:
    return DifficultTerrainTraversalRequest(
        id="terrain:cross",
        round_state=round_state or active_round(),
        state=state or spatial_state(),
        actor_id="hero",
        actor_conditions=conditions,
        athletics_test=athletics_test
        or TestRequest("terrain:athletics", TestProfile(1, 5)),
        destination_zone_id=destination_zone_id,
        path_entity_ids=path_entity_ids,
        crosses_obstacle=crosses_obstacle,
        skill=skill,
    )


class K1DifficultTerrainResolutionTests(unittest.TestCase):
    def test_success_crosses_and_records_turn_scoped_test(self) -> None:
        source = request(
            athletics_test=TestRequest(
                "terrain:athletics",
                TestProfile(1, 5),
                dice_modifiers=(DiceModifier("terrain:aid", 1),),
            )
        )

        result = resolve_difficult_terrain_traversal(
            source,
            SequenceRandom([1, 10]),
        )

        self.assertIs(result.outcome, DifficultTerrainOutcome.CROSSED_SAFELY)
        self.assertEqual(result.origin_zone_id, "zone:a")
        self.assertEqual(result.destination_zone_id, "zone:b")
        self.assertEqual(result.state.placement_for("hero").zone_id, "zone:b")
        self.assertEqual(
            result.state.difficult_terrain_tested_entity_ids,
            ("hero",),
        )
        self.assertEqual(result.state.gave_ground_entity_ids, ("enemy",))
        self.assertEqual(result.state.free_move_used_entity_ids, ("enemy",))
        self.assertEqual(result.conditions, ConditionState())
        self.assertIsNone(result.prone_application)
        self.assertEqual(
            result.applied_rule_ids,
            (
                DIFFICULT_TERRAIN_TRAVERSAL_RULE_ID,
                ZONE_GRAPH_RULE_ID,
                "terrain:aid",
            ),
        )

    def test_failure_crosses_before_falling_prone(self) -> None:
        result = resolve_difficult_terrain_traversal(
            request(conditions=ConditionState({Condition.DISTRACTED})),
            SequenceRandom([10]),
        )

        self.assertIs(
            result.outcome,
            DifficultTerrainOutcome.CROSSED_AND_FELL_PRONE,
        )
        self.assertEqual(result.state.placement_for("hero").zone_id, "zone:b")
        self.assertEqual(
            result.conditions.conditions,
            frozenset({Condition.DISTRACTED, Condition.PRONE}),
        )
        self.assertFalse(result.prone_application.was_already_present)
        self.assertEqual(
            result.prone_application.source_rule_id,
            DIFFICULT_TERRAIN_TRAVERSAL_RULE_ID,
        )

    def test_second_crossing_retests_without_duplicate_usage(self) -> None:
        first = resolve_difficult_terrain_traversal(
            request(),
            SequenceRandom([1]),
        )
        second = resolve_difficult_terrain_traversal(
            request(
                state=first.state,
                conditions=first.conditions,
                destination_zone_id="zone:c",
            ),
            SequenceRandom([1]),
        )

        self.assertEqual(second.state.placement_for("hero").zone_id, "zone:c")
        self.assertEqual(
            second.state.difficult_terrain_tested_entity_ids,
            ("hero",),
        )

    def test_movement_blockers_and_invalid_route_close_before_rng(self) -> None:
        blocked = (
            request(conditions=ConditionState({Condition.PRONE})),
            request(conditions=ConditionState({Condition.DEFENCELESS})),
            request(destination_zone_id="zone:d"),
            request(path_entity_ids=("enemy",)),
            request(crosses_obstacle=True),
        )
        for source in blocked:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    resolve_difficult_terrain_traversal(
                        source,
                        SequenceRandom([]),
                    )

        result = resolve_difficult_terrain_traversal(
            request(
                conditions=ConditionState({Condition.BURDENED}),
                path_entity_ids=("ally",),
            ),
            SequenceRandom([1]),
        )
        self.assertIs(result.outcome, DifficultTerrainOutcome.CROSSED_SAFELY)

    def test_request_requires_active_actor_and_athletics(self) -> None:
        with self.assertRaises(ValueError):
            request(round_state=active_round(actor_id="enemy"))
        with self.assertRaises(ValueError):
            request(skill=Skill.AWARENESS)

    def test_spatial_usage_is_validated_and_cleared_next_round(self) -> None:
        state = spatial_state()
        with self.assertRaises(ValueError):
            replace(
                state,
                difficult_terrain_tested_entity_ids=("hero", "hero"),
            )
        with self.assertRaises(ValueError):
            replace(
                state,
                difficult_terrain_tested_entity_ids=("unknown",),
            )

        used = replace(
            state,
            difficult_terrain_tested_entity_ids=("hero",),
        )
        advanced = start_next_spatial_round(used)
        self.assertEqual(advanced.difficult_terrain_tested_entity_ids, ())
        self.assertEqual(advanced.gave_ground_entity_ids, ())
        self.assertEqual(advanced.free_move_used_entity_ids, ())

    def test_result_rejects_forged_movement_condition_and_usage(self) -> None:
        succeeded = resolve_difficult_terrain_traversal(
            request(),
            SequenceRandom([1]),
        )
        failed = resolve_difficult_terrain_traversal(
            request(),
            SequenceRandom([10]),
        )

        with self.assertRaises(ValueError):
            replace(succeeded, state=succeeded.previous_state)
        with self.assertRaises(ValueError):
            replace(
                succeeded,
                state=replace(
                    succeeded.state,
                    difficult_terrain_tested_entity_ids=(),
                ),
            )
        with self.assertRaises(ValueError):
            replace(succeeded, conditions=ConditionState({Condition.PRONE}))
        with self.assertRaises(ValueError):
            replace(
                succeeded,
                previous_conditions=ConditionState({Condition.PRONE}),
            )
        with self.assertRaises(ValueError):
            replace(failed, outcome=DifficultTerrainOutcome.CROSSED_SAFELY)
        with self.assertRaises(TypeError):
            replace(failed, prone_application=None)


if __name__ == "__main__":
    unittest.main()
