from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.movement_models import (
    MovementSpeed,
    RunActionExecutionRequest,
    RunAthleticsExtensionRequest,
    RunAthleticsOutcome,
)
from towr.domain.spatial_models import (
    SpatialBattleState,
    SpatialEntityPlacement,
    ZoneConnection,
    ZoneGraph,
)
from towr.domain.test_models import (
    DiceModifier,
    InlineProfile,
    Skill,
    TestRequest,
)
from towr.domain.turn_models import (
    ActionSlotGrant,
    CombatActionDeclaration,
    CombatActionKind,
    CombatActionSlotRequest,
    CombatRoundState,
    CombatSide,
    CombatTurnParticipant,
    CombatTurnStartRequest,
    ManoeuvreKind,
)
from towr.rules.run_action_execution import (
    RUN_ATHLETICS_EXTENSION_RULE_ID,
    execute_run_action,
    resolve_run_athletics_extension,
)
from towr.rules.turn_resolution import (
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


def spatial_state() -> SpatialBattleState:
    return SpatialBattleState(
        graph=graph(),
        placements=(
            SpatialEntityPlacement("hero", "heroes", "zone:a"),
            SpatialEntityPlacement("ally", "heroes", "zone:b"),
            SpatialEntityPlacement("enemy", "enemies", "zone:b"),
        ),
        free_move_used_entity_ids=("hero",),
    )


def reserved_run() -> CombatRoundState:
    state = CombatRoundState(
        round_number=1,
        participants=(
            CombatTurnParticipant(
                "hero",
                CombatSide.PLAYERS_AND_ALLIES,
            ),
            CombatTurnParticipant("enemy", CombatSide.OPPOSITION),
        ),
    )
    state = start_combat_turn(
        CombatTurnStartRequest("turn:hero", state, "hero")
    ).state
    return reserve_combat_action_slot(
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


def completed_base_run(*, terrain_test_recorded: bool = False):
    state = spatial_state()
    if terrain_test_recorded:
        state = replace(
            state,
            difficult_terrain_tested_entity_ids=("hero",),
        )
    return execute_run_action(
        RunActionExecutionRequest(
            id="execute:run",
            round_state=reserved_run(),
            spatial_state=state,
            actor_id="hero",
            slot_index=1,
            speed=MovementSpeed.NORMAL,
            actor_conditions=ConditionState(),
            destination_zone_id="zone:b",
        )
    )


def request(
    *,
    conditions: ConditionState = ConditionState(),
    athletics_test: TestRequest | None = None,
    destination_zone_id: str = "zone:c",
    path_entity_ids: tuple[str, ...] = (),
    crosses_obstacle: bool = False,
    crosses_difficult_terrain: bool = False,
    terrain_test_recorded: bool = False,
) -> RunAthleticsExtensionRequest:
    base_run = completed_base_run(
        terrain_test_recorded=terrain_test_recorded
    )
    return RunAthleticsExtensionRequest(
        id="run:athletics",
        base_run=base_run,
        athletics_test=athletics_test
        or TestRequest("test:athletics", InlineProfile(1, 5)),
        actor_conditions=conditions,
        destination_zone_id=destination_zone_id,
        path_entity_ids=path_entity_ids,
        crosses_obstacle=crosses_obstacle,
        crosses_difficult_terrain=crosses_difficult_terrain,
    )


class K1RunAthleticsExtensionTests(unittest.TestCase):
    def test_success_moves_second_extra_zone_without_new_receipt(self) -> None:
        source = request()
        base_receipt = source.base_run.slot.execution

        result = resolve_run_athletics_extension(
            source,
            SequenceRandom([1]),
        )

        self.assertIs(result.outcome, RunAthleticsOutcome.MOVED_EXTRA_ZONE)
        self.assertEqual(
            result.previous_spatial_state.placement_for("hero").zone_id,
            "zone:b",
        )
        self.assertEqual(
            result.spatial_state.placement_for("hero").zone_id,
            "zone:c",
        )
        self.assertEqual(result.conditions, ConditionState())
        self.assertIsNone(result.stagger_application)
        self.assertIs(result.base_run.slot.execution, base_receipt)
        self.assertEqual(
            result.spatial_state.free_move_used_entity_ids,
            ("hero",),
        )

    def test_failure_does_not_move_and_adds_first_staggered(self) -> None:
        source = request()

        result = resolve_run_athletics_extension(
            source,
            SequenceRandom([10]),
        )

        self.assertIs(result.outcome, RunAthleticsOutcome.FAILED_STAGGERED)
        self.assertEqual(result.spatial_state, source.base_run.spatial_state)
        self.assertTrue(result.conditions.has(Condition.STAGGERED))
        self.assertFalse(result.stagger_application.was_already_present)
        self.assertEqual(
            result.stagger_application.source_rule_id,
            RUN_ATHLETICS_EXTENSION_RULE_ID,
        )

    def test_failure_does_not_duplicate_existing_staggered(self) -> None:
        conditions = ConditionState(
            {Condition.STAGGERED, Condition.DISTRACTED}
        )

        result = resolve_run_athletics_extension(
            request(conditions=conditions),
            SequenceRandom([10]),
        )

        self.assertIs(
            result.outcome,
            RunAthleticsOutcome.FAILED_ALREADY_STAGGERED,
        )
        self.assertEqual(result.conditions, conditions)
        self.assertTrue(result.stagger_application.was_already_present)

    def test_invalid_path_context_is_rejected_before_rng(self) -> None:
        blocked = (
            request(destination_zone_id="zone:b"),
            request(destination_zone_id="zone:d"),
            request(path_entity_ids=("enemy",)),
            request(crosses_obstacle=True),
            request(crosses_difficult_terrain=True),
            request(terrain_test_recorded=True),
        )

        for source in blocked:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    resolve_run_athletics_extension(
                        source,
                        SequenceRandom([]),
                    )

        result = resolve_run_athletics_extension(
            request(path_entity_ids=("ally",)),
            SequenceRandom([1]),
        )
        self.assertIs(result.outcome, RunAthleticsOutcome.MOVED_EXTRA_ZONE)

    def test_new_movement_blockers_close_before_rng(self) -> None:
        for condition in (
            Condition.BURDENED,
            Condition.PRONE,
            Condition.DEFENCELESS,
        ):
            with self.subTest(condition=condition):
                with self.assertRaises(ValueError):
                    resolve_run_athletics_extension(
                        request(conditions=ConditionState({condition})),
                        SequenceRandom([]),
                    )

    def test_request_requires_athletics_and_valid_path_snapshot(self) -> None:
        source = request()
        with self.assertRaises(ValueError):
            replace(source, skill=Skill.ENDURANCE)
        with self.assertRaises(ValueError):
            replace(source, path_entity_ids=("ally", "ally"))
        with self.assertRaises(ValueError):
            replace(source, path_entity_ids=("hero",))
        with self.assertRaises(ValueError):
            resolve_run_athletics_extension(
                replace(source, rule_id="RULE-COMBAT-014:forged"),
                SequenceRandom([]),
            )

    def test_test_trace_and_modifier_rules_are_preserved(self) -> None:
        test = TestRequest(
            "test:athletics:helped",
            InlineProfile(1, 5),
            dice_modifiers=(
                DiceModifier("RULE-COMBAT-004:help", 1),
            ),
        )

        result = resolve_run_athletics_extension(
            request(athletics_test=test),
            SequenceRandom([1, 10]),
        )

        self.assertEqual(
            result.athletics_test_result.trace.request_id,
            test.id,
        )
        self.assertIn(
            "RULE-COMBAT-004:help",
            result.applied_rule_ids,
        )

    def test_result_rejects_forged_outcome_state_and_test(self) -> None:
        success = resolve_run_athletics_extension(
            request(),
            SequenceRandom([1]),
        )
        failure = resolve_run_athletics_extension(
            request(),
            SequenceRandom([10]),
        )

        with self.assertRaises(ValueError):
            replace(success, outcome=RunAthleticsOutcome.FAILED_STAGGERED)
        with self.assertRaises(ValueError):
            replace(success, spatial_state=success.previous_spatial_state)
        with self.assertRaises(ValueError):
            replace(failure, conditions=ConditionState())
        with self.assertRaises(ValueError):
            replace(
                success,
                athletics_test_request=TestRequest(
                    "test:other",
                    InlineProfile(1, 5),
                ),
            )


if __name__ == "__main__":
    unittest.main()
