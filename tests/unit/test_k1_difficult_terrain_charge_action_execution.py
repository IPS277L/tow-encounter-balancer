from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from tests.unit.test_k1_charge_action_execution import (
    kernel_request,
    request as charge_request,
    reserved_charge,
    spatial_state,
)
from towr.domain.charge_models import (
    DifficultTerrainChargeActionExecutionRequest,
)
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.movement_models import (
    DifficultTerrainTraversalRequest,
    MovementSpeed,
)
from towr.domain.test_models import DiceModifier, Skill, TestProfile, TestRequest
from towr.domain.turn_models import CombatTurnEndRequest
from towr.rules.charge_action_execution import (
    CHARGE_ACTION_EXECUTION_RULE_ID,
    CHARGE_MELEE_BONUS_RULE_ID,
    DIFFICULT_TERRAIN_CHARGE_ACTION_EXECUTION_RULE_ID,
    execute_difficult_terrain_charge_action,
)
from towr.rules.difficult_terrain_resolution import (
    DIFFICULT_TERRAIN_TRAVERSAL_RULE_ID,
    resolve_difficult_terrain_traversal,
)
from towr.rules.spatial_resolution import ZONE_GRAPH_RULE_ID
from towr.rules.turn_resolution import end_combat_turn


def terrain_request(
    round_state,
    state,
    conditions: ConditionState = ConditionState(),
    *,
    path_entity_ids: tuple[str, ...] = (),
) -> DifficultTerrainTraversalRequest:
    return DifficultTerrainTraversalRequest(
        id="terrain:charge",
        round_state=round_state,
        state=state,
        actor_id="hero",
        actor_conditions=conditions,
        athletics_test=TestRequest(
            "terrain:charge:athletics",
            TestProfile(1, 5),
        ),
        destination_zone_id="zone:b",
        path_entity_ids=path_entity_ids,
    )


def composite(
    *,
    conditions: ConditionState = ConditionState(),
    terrain_roll: int = 1,
    speed: MovementSpeed = MovementSpeed.NORMAL,
    attack_skill: Skill = Skill.MELEE,
    kernel=None,
    path_entity_ids: tuple[str, ...] = (),
    actor_began_turn_in_enemy_close_range: bool = False,
    reaches_target_close_range: bool = True,
):
    round_state = reserved_charge()
    state = spatial_state()
    traversal = resolve_difficult_terrain_traversal(
        terrain_request(
            round_state,
            state,
            conditions,
            path_entity_ids=path_entity_ids,
        ),
        SequenceRandom([terrain_roll]),
    )
    charge = charge_request(
        round_state=round_state,
        state=state,
        speed=speed,
        conditions=conditions,
        attack_skill=attack_skill,
        kernel=kernel,
        actor_began_turn_in_enemy_close_range=(
            actor_began_turn_in_enemy_close_range
        ),
        reaches_target_close_range=reaches_target_close_range,
        path_entity_ids=path_entity_ids,
        crosses_difficult_terrain=True,
    )
    return DifficultTerrainChargeActionExecutionRequest(
        id="consume:terrain-charge",
        charge_action=charge,
        terrain_traversal=traversal,
        round_state=round_state,
        spatial_state=traversal.state,
    )


class K1DifficultTerrainChargeActionExecutionTests(unittest.TestCase):
    def test_successful_crossing_attacks_and_executes_charge_slot(self) -> None:
        source = composite()

        result = execute_difficult_terrain_charge_action(
            source,
            SequenceRandom([1, 10]),
        )

        self.assertEqual(result.origin_zone_id, "zone:a")
        self.assertEqual(result.destination_zone_id, "zone:b")
        self.assertEqual(
            result.spatial_state,
            source.terrain_traversal.state,
        )
        self.assertTrue(result.slot.executed)
        self.assertEqual(
            result.slot.execution.executor_rule_id,
            DIFFICULT_TERRAIN_CHARGE_ACTION_EXECUTION_RULE_ID,
        )
        self.assertEqual(
            result.slot.execution.result_request_id,
            result.resolution.request_id,
        )
        self.assertEqual(result.melee_bonus.amount, 1)
        self.assertEqual(
            result.resolution.attack.attacker_test.trace.rolled_dice,
            2,
        )
        self.assertEqual(
            result.applied_rule_ids,
            (
                DIFFICULT_TERRAIN_CHARGE_ACTION_EXECUTION_RULE_ID,
                CHARGE_ACTION_EXECUTION_RULE_ID,
                DIFFICULT_TERRAIN_TRAVERSAL_RULE_ID,
                ZONE_GRAPH_RULE_ID,
                CHARGE_MELEE_BONUS_RULE_ID,
            ),
        )

    def test_failed_crossing_falls_prone_but_still_attacks(self) -> None:
        source = composite(terrain_roll=10)

        result = execute_difficult_terrain_charge_action(
            source,
            SequenceRandom([1, 10]),
        )

        self.assertTrue(result.conditions.has(Condition.PRONE))
        self.assertEqual(result.spatial_state.placement_for("hero").zone_id, "zone:b")
        self.assertEqual(
            result.resolution.attack.attacker_test.trace.rolled_dice,
            2,
        )
        self.assertTrue(result.slot.executed)

    def test_non_melee_charge_does_not_gain_charge_bonus(self) -> None:
        source = composite(attack_skill=Skill.BRAWN)

        result = execute_difficult_terrain_charge_action(
            source,
            SequenceRandom([1]),
        )

        self.assertIsNone(result.melee_bonus)
        self.assertEqual(
            result.kernel_request,
            source.charge_action.kernel_request,
        )
        self.assertEqual(
            result.resolution.attack.attacker_test.trace.rolled_dice,
            1,
        )

    def test_composite_rejects_mismatched_provenance(self) -> None:
        source = composite()
        mismatched_path = replace(
            source.charge_action,
            path_entity_ids=("ally",),
        )
        with self.assertRaises(ValueError):
            replace(source, charge_action=mismatched_path)

        mismatched_conditions = replace(
            source.charge_action,
            actor_conditions=ConditionState({Condition.DISTRACTED}),
        )
        with self.assertRaises(ValueError):
            replace(source, charge_action=mismatched_conditions)

        with self.assertRaises(ValueError):
            replace(source, spatial_state=source.charge_action.spatial_state)

    def test_base_charge_restrictions_still_close_before_attack_rng(self) -> None:
        blocked = (
            composite(speed=MovementSpeed.SLOW),
            composite(conditions=ConditionState({Condition.BURDENED})),
            composite(actor_began_turn_in_enemy_close_range=True),
            composite(reaches_target_close_range=False),
        )
        for source in blocked:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    execute_difficult_terrain_charge_action(
                        source,
                        SequenceRandom([]),
                    )

    def test_post_terrain_attack_context_must_be_current(self) -> None:
        conditions = ConditionState({Condition.STAGGERED})
        stale = composite(
            conditions=conditions,
            kernel=kernel_request(attacker_is_staggered=False),
        )
        duplicate_bonus = composite(
            kernel=kernel_request(
                attacker_modifiers=(
                    DiceModifier(CHARGE_MELEE_BONUS_RULE_ID, 1),
                )
            )
        )

        for source in (stale, duplicate_bonus):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    execute_difficult_terrain_charge_action(
                        source,
                        SequenceRandom([]),
                    )

    def test_consumed_slot_cannot_accept_the_same_traversal_again(self) -> None:
        source = composite()
        result = execute_difficult_terrain_charge_action(
            source,
            SequenceRandom([1, 10]),
        )

        with self.assertRaises(ValueError):
            replace(source, round_state=result.round_state)
        ended = end_combat_turn(
            CombatTurnEndRequest("turn:end", result.round_state, "hero")
        )
        self.assertTrue(ended.completed_turn.action_slots[0].executed)

    def test_result_rejects_condition_spatial_attack_and_turn_forgery(
        self,
    ) -> None:
        source = composite(terrain_roll=10)
        result = execute_difficult_terrain_charge_action(
            source,
            SequenceRandom([1, 10]),
        )

        with self.assertRaises(ValueError):
            replace(result, conditions=result.previous_conditions)
        with self.assertRaises(ValueError):
            replace(result, spatial_state=source.charge_action.spatial_state)
        with self.assertRaises(ValueError):
            replace(result, round_state=result.previous_round_state)
        with self.assertRaises(ValueError):
            replace(result, kernel_request=result.source_kernel_request)
        with self.assertRaises(ValueError):
            replace(
                result,
                charge_action_request=replace(
                    result.charge_action_request,
                    reaches_target_close_range=False,
                ),
            )


if __name__ == "__main__":
    unittest.main()
