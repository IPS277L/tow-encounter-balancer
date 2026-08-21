from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.attack_models import (
    AttackRequest,
    DamageImpactSpec,
    DamageProfile,
    ResilienceProfile,
)
from towr.domain.charge_models import (
    LongChargeActionExecutionRequest,
    LongChargeOutcome,
)
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import CharacterInjuryState
from towr.domain.movement_models import MovementSpeed
from towr.domain.resolution_models import (
    KernelAttackRequest,
    TargetInjuryPolicy,
)
from towr.domain.spatial_models import (
    SpatialBattleState,
    SpatialEntityPlacement,
    ZoneConnection,
    ZoneGraph,
)
from towr.domain.test_models import DiceModifier, Skill, TestProfile, TestRequest
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
from towr.rules.charge_action_execution import (
    CHARGE_MELEE_BONUS_RULE_ID,
    LONG_CHARGE_ACTION_EXECUTION_RULE_ID,
    execute_long_charge_action,
)
from towr.rules.spatial_resolution import ZONE_GRAPH_RULE_ID
from towr.rules.turn_resolution import (
    end_combat_turn,
    reserve_combat_action_slot,
    start_combat_turn,
)


def graph(*, direct_link: bool = False) -> ZoneGraph:
    connections = [
        ZoneConnection("zone:a", "zone:b"),
        ZoneConnection("zone:b", "zone:c"),
    ]
    if direct_link:
        connections.append(ZoneConnection("zone:a", "zone:c"))
    return ZoneGraph(
        zone_ids=("zone:a", "zone:b", "zone:c", "zone:d"),
        connections=tuple(connections),
    )


def spatial_state(*, direct_link: bool = False) -> SpatialBattleState:
    return SpatialBattleState(
        graph=graph(direct_link=direct_link),
        placements=(
            SpatialEntityPlacement("hero", "heroes", "zone:a"),
            SpatialEntityPlacement("ally", "heroes", "zone:b"),
            SpatialEntityPlacement("enemy", "enemies", "zone:c"),
            SpatialEntityPlacement("blocker", "enemies", "zone:b"),
        ),
        free_move_used_entity_ids=("hero",),
    )


def reserved_charge() -> CombatRoundState:
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
    return reserve_combat_action_slot(
        CombatActionSlotRequest(
            id="slot:charge",
            state=state,
            actor_id="hero",
            declaration=CombatActionDeclaration(
                CombatActionKind.MANOEUVRE,
                manoeuvre=ManoeuvreKind.CHARGE,
            ),
            grant=ActionSlotGrant.STANDARD,
        )
    ).state


def kernel_request(
    *,
    attacker_is_staggered: bool = False,
    modifiers: tuple[DiceModifier, ...] = (),
) -> KernelAttackRequest:
    return KernelAttackRequest(
        id="kernel:long-charge",
        attack=AttackRequest(
            id="attack:long-charge",
            attacker_test=TestRequest(
                "test:attack",
                TestProfile(1, 5),
                dice_modifiers=modifiers,
            ),
            defender_test=None,
            impact_spec=DamageImpactSpec(
                damage=DamageProfile(0),
                resilience=ResilienceProfile(toughness=5),
            ),
            is_close_range=True,
            attacker_is_staggered=attacker_is_staggered,
        ),
        target_policy=TargetInjuryPolicy.PLAYER,
        target_state=CharacterInjuryState(),
        can_target_leave_zone=True,
        target_has_given_ground_this_round=False,
    )


def request(
    *,
    round_state: CombatRoundState | None = None,
    state: SpatialBattleState | None = None,
    conditions: ConditionState = ConditionState(),
    speed: MovementSpeed = MovementSpeed.NORMAL,
    attack_skill: Skill = Skill.MELEE,
    athletics_test: TestRequest | None = None,
    kernel: KernelAttackRequest | None = None,
    intermediate_zone_id: str = "zone:b",
    actor_began_turn_in_enemy_close_range: bool = False,
    reaches_target_close_range: bool = True,
    path_entity_ids: tuple[str, ...] = (),
    crosses_obstacle: bool = False,
    crosses_difficult_terrain: bool = False,
    terrain_test_recorded: bool = False,
    skill: Skill = Skill.ATHLETICS,
) -> LongChargeActionExecutionRequest:
    selected_state = state or spatial_state()
    if terrain_test_recorded:
        selected_state = replace(
            selected_state,
            difficult_terrain_tested_entity_ids=("hero",),
        )
    return LongChargeActionExecutionRequest(
        id="execute:long-charge",
        round_state=round_state or reserved_charge(),
        spatial_state=selected_state,
        actor_id="hero",
        target_id="enemy",
        slot_index=1,
        speed=speed,
        actor_conditions=conditions,
        attack_skill=attack_skill,
        athletics_test=athletics_test
        or TestRequest("test:athletics", TestProfile(1, 5)),
        kernel_request=kernel
        or kernel_request(
            attacker_is_staggered=conditions.has(Condition.STAGGERED)
        ),
        intermediate_zone_id=intermediate_zone_id,
        actor_began_turn_in_enemy_close_range=(
            actor_began_turn_in_enemy_close_range
        ),
        reaches_target_close_range=reaches_target_close_range,
        path_entity_ids=path_entity_ids,
        crosses_obstacle=crosses_obstacle,
        crosses_difficult_terrain=crosses_difficult_terrain,
        skill=skill,
    )


class K1LongChargeActionExecutionTests(unittest.TestCase):
    def test_success_moves_two_zones_attacks_and_executes_slot(self) -> None:
        source = request()

        result = execute_long_charge_action(
            source,
            SequenceRandom([1, 1, 10]),
        )

        self.assertIs(
            result.outcome,
            LongChargeOutcome.REACHED_TARGET_AND_ATTACKED,
        )
        self.assertTrue(result.succeeded)
        self.assertTrue(result.target_in_close_range)
        self.assertEqual(
            result.spatial_state.placement_for("hero").zone_id,
            "zone:c",
        )
        self.assertEqual(
            result.spatial_state.free_move_used_entity_ids,
            ("hero",),
        )
        self.assertEqual(result.resolution.request_id, "kernel:long-charge")
        self.assertEqual(
            result.resolution.attack.attacker_test.trace.rolled_dice,
            2,
        )
        self.assertEqual(result.melee_bonus.amount, 1)
        self.assertTrue(result.slot.executed)
        self.assertEqual(
            result.slot.execution.result_request_id,
            result.resolution.request_id,
        )
        self.assertEqual(
            result.applied_rule_ids,
            (
                LONG_CHARGE_ACTION_EXECUTION_RULE_ID,
                ZONE_GRAPH_RULE_ID,
                CHARGE_MELEE_BONUS_RULE_ID,
            ),
        )

    def test_failure_moves_one_zone_skips_attack_and_adds_staggered(self) -> None:
        source = request()

        result = execute_long_charge_action(source, SequenceRandom([10]))

        self.assertIs(
            result.outcome,
            LongChargeOutcome.STOPPED_SHORT_STAGGERED,
        )
        self.assertFalse(result.succeeded)
        self.assertFalse(result.target_in_close_range)
        self.assertEqual(
            result.spatial_state.placement_for("hero").zone_id,
            "zone:b",
        )
        self.assertIsNone(result.resolution)
        self.assertIsNone(result.melee_bonus)
        self.assertIs(result.kernel_request, source.kernel_request)
        self.assertTrue(result.conditions.has(Condition.STAGGERED))
        self.assertFalse(result.stagger_application.was_already_present)
        self.assertEqual(
            result.slot.execution.result_request_id,
            source.id,
        )

    def test_failure_keeps_one_existing_staggered(self) -> None:
        conditions = ConditionState({Condition.STAGGERED})

        result = execute_long_charge_action(
            request(conditions=conditions),
            SequenceRandom([10]),
        )

        self.assertIs(
            result.outcome,
            LongChargeOutcome.STOPPED_SHORT_ALREADY_STAGGERED,
        )
        self.assertEqual(result.conditions, conditions)
        self.assertTrue(result.stagger_application.was_already_present)

    def test_non_melee_success_does_not_receive_charge_bonus(self) -> None:
        source = request(attack_skill=Skill.BRAWN)

        result = execute_long_charge_action(source, SequenceRandom([1, 1]))

        self.assertIsNone(result.melee_bonus)
        self.assertIs(result.kernel_request, source.kernel_request)
        self.assertEqual(
            result.resolution.attack.attacker_test.trace.rolled_dice,
            1,
        )

    def test_target_and_route_must_be_exactly_long_range(self) -> None:
        with self.assertRaises(ValueError):
            execute_long_charge_action(
                request(state=spatial_state(direct_link=True)),
                SequenceRandom([]),
            )
        with self.assertRaises(ValueError):
            execute_long_charge_action(
                request(intermediate_zone_id="zone:d"),
                SequenceRandom([]),
            )

    def test_close_and_movement_context_block_before_rng(self) -> None:
        blocked = (
            request(actor_began_turn_in_enemy_close_range=True),
            request(reaches_target_close_range=False),
            request(speed=MovementSpeed.SLOW),
            request(conditions=ConditionState({Condition.BURDENED})),
            request(conditions=ConditionState({Condition.PRONE})),
            request(conditions=ConditionState({Condition.DEFENCELESS})),
            request(path_entity_ids=("blocker",)),
            request(crosses_obstacle=True),
            request(crosses_difficult_terrain=True),
            request(terrain_test_recorded=True),
        )
        for source in blocked:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    execute_long_charge_action(source, SequenceRandom([]))

        result = execute_long_charge_action(
            request(path_entity_ids=("ally",)),
            SequenceRandom([10]),
        )
        self.assertEqual(result.intermediate_zone_id, "zone:b")

    def test_request_requires_athletics_and_ready_attack_context(self) -> None:
        with self.assertRaises(ValueError):
            request(skill=Skill.AWARENESS)

        not_close = replace(
            kernel_request(),
            attack=replace(kernel_request().attack, is_close_range=False),
        )
        stale_stagger = kernel_request(attacker_is_staggered=False)
        sources = (
            request(kernel=not_close),
            request(
                conditions=ConditionState({Condition.STAGGERED}),
                kernel=stale_stagger,
            ),
            request(
                kernel=kernel_request(
                    modifiers=(
                        DiceModifier(CHARGE_MELEE_BONUS_RULE_ID, 1),
                    )
                )
            ),
        )
        for source in sources:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    execute_long_charge_action(source, SequenceRandom([]))

    def test_executor_requires_its_reserved_unexecuted_charge_slot(self) -> None:
        state = reserved_charge()
        turn = state.active_turn
        missing = replace(state, active_turn=replace(turn, action_slots=()))
        wrong_slot = replace(
            state,
            active_turn=replace(
                turn,
                action_slots=(
                    replace(
                        turn.action_slots[0],
                        declaration=CombatActionDeclaration(
                            CombatActionKind.AIM
                        ),
                    ),
                ),
            ),
        )
        for blocked_state in (missing, wrong_slot):
            with self.subTest(state=blocked_state):
                with self.assertRaises(ValueError):
                    execute_long_charge_action(
                        request(round_state=blocked_state),
                        SequenceRandom([]),
                    )

        executed = execute_long_charge_action(request(), SequenceRandom([10]))
        with self.assertRaises(ValueError):
            execute_long_charge_action(
                request(
                    round_state=executed.round_state,
                    state=executed.spatial_state,
                    conditions=executed.conditions,
                ),
                SequenceRandom([]),
            )

    def test_charge_slot_is_consumed_on_both_outcomes(self) -> None:
        for values in ([1, 1, 10], [10]):
            with self.subTest(values=values):
                result = execute_long_charge_action(
                    request(),
                    SequenceRandom(values),
                )
                ended = end_combat_turn(
                    CombatTurnEndRequest(
                        "turn:end",
                        result.round_state,
                        "hero",
                    )
                )
                self.assertTrue(ended.completed_turn.action_slots[0].executed)

    def test_kernel_failure_leaves_source_states_unmodified(self) -> None:
        source = request()

        with self.assertRaises(RuntimeError):
            execute_long_charge_action(source, SequenceRandom([1]))

        self.assertEqual(
            source.spatial_state.placement_for("hero").zone_id,
            "zone:a",
        )
        self.assertFalse(source.round_state.active_turn.action_slots[0].executed)

    def test_result_rejects_forged_branch_state(self) -> None:
        succeeded = execute_long_charge_action(
            request(),
            SequenceRandom([1, 1, 10]),
        )
        failed = execute_long_charge_action(request(), SequenceRandom([10]))

        with self.assertRaises(ValueError):
            replace(succeeded, target_in_close_range=False)
        with self.assertRaises(ValueError):
            replace(succeeded, spatial_state=succeeded.previous_spatial_state)
        with self.assertRaises(ValueError):
            replace(failed, target_in_close_range=True)
        with self.assertRaises(ValueError):
            replace(failed, conditions=failed.previous_conditions)
        with self.assertRaises(ValueError):
            replace(failed, resolution=succeeded.resolution)


if __name__ == "__main__":
    unittest.main()
