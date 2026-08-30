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
from towr.domain.charge_models import ChargeActionExecutionRequest
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
from towr.domain.test_models import (
    DiceModifier,
    Skill,
    TestProfile,
    TestRequest,
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
from towr.rules.charge_action_execution import (
    CHARGE_ACTION_EXECUTION_RULE_ID,
    CHARGE_MELEE_BONUS_RULE_ID,
    execute_charge_action,
)
from towr.rules.spatial_resolution import ZONE_GRAPH_RULE_ID
from towr.rules.turn_resolution import (
    end_combat_turn,
    reserve_combat_action_slot,
    start_combat_turn,
)


def graph() -> ZoneGraph:
    return ZoneGraph(
        zone_ids=("zone:a", "zone:b", "zone:c"),
        connections=(
            ZoneConnection("zone:a", "zone:b"),
            ZoneConnection("zone:b", "zone:c"),
        ),
    )


def spatial_state(*, target_zone_id: str = "zone:b") -> SpatialBattleState:
    return SpatialBattleState(
        graph=graph(),
        placements=(
            SpatialEntityPlacement("hero", "heroes", "zone:a"),
            SpatialEntityPlacement("ally", "heroes", "zone:a"),
            SpatialEntityPlacement("enemy", "enemies", target_zone_id),
            SpatialEntityPlacement("blocker", "enemies", "zone:a"),
        ),
        free_move_used_entity_ids=("hero",),
    )


def active_round() -> CombatRoundState:
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


def charge_declaration() -> CombatActionDeclaration:
    return CombatActionDeclaration(
        CombatActionKind.MANOEUVRE,
        manoeuvre=ManoeuvreKind.CHARGE,
    )


def reserved_charge() -> CombatRoundState:
    return reserve_action(active_round(), charge_declaration())


def kernel_request(
    *,
    attacker_is_staggered: bool = False,
    attacker_modifiers: tuple[DiceModifier, ...] = (),
) -> KernelAttackRequest:
    return KernelAttackRequest(
        id="kernel:charge",
        target_id="enemy",
        attack=AttackRequest(
            id="attack:charge",
            attacker_test=TestRequest(
                "test:attacker",
                TestProfile(1, 5),
                dice_modifiers=attacker_modifiers,
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
    target_id: str = "enemy",
    slot_index: int = 1,
    speed: MovementSpeed = MovementSpeed.NORMAL,
    conditions: ConditionState = ConditionState(),
    attack_skill: Skill = Skill.MELEE,
    kernel: KernelAttackRequest | None = None,
    actor_began_turn_in_enemy_close_range: bool = False,
    reaches_target_close_range: bool = True,
    path_entity_ids: tuple[str, ...] = (),
    crosses_obstacle: bool = False,
    crosses_difficult_terrain: bool = False,
) -> ChargeActionExecutionRequest:
    return ChargeActionExecutionRequest(
        id="execute:charge",
        round_state=round_state or reserved_charge(),
        spatial_state=state or spatial_state(),
        actor_id="hero",
        target_id=target_id,
        slot_index=slot_index,
        speed=speed,
        actor_conditions=conditions,
        attack_skill=attack_skill,
        kernel_request=kernel or kernel_request(
            attacker_is_staggered=conditions.has(Condition.STAGGERED)
        ),
        actor_began_turn_in_enemy_close_range=(
            actor_began_turn_in_enemy_close_range
        ),
        reaches_target_close_range=reaches_target_close_range,
        path_entity_ids=path_entity_ids,
        crosses_obstacle=crosses_obstacle,
        crosses_difficult_terrain=crosses_difficult_terrain,
    )


class K1ChargeActionExecutionTests(unittest.TestCase):
    def test_melee_charge_moves_attacks_and_executes_one_slot(self) -> None:
        source = request()

        result = execute_charge_action(
            source,
            SequenceRandom([1, 10]),
        )

        self.assertEqual(result.origin_zone_id, "zone:a")
        self.assertEqual(result.destination_zone_id, "zone:b")
        self.assertTrue(result.target_in_close_range)
        self.assertEqual(
            result.spatial_state.placement_for("hero").zone_id,
            "zone:b",
        )
        self.assertEqual(
            result.spatial_state.free_move_used_entity_ids,
            ("hero",),
        )
        self.assertTrue(result.slot.executed)
        self.assertEqual(
            result.slot.execution.source_request_id,
            source.id,
        )
        self.assertEqual(
            result.slot.execution.result_request_id,
            result.resolution.request_id,
        )
        self.assertEqual(result.melee_bonus.amount, 1)
        self.assertEqual(
            result.melee_bonus.rule_id,
            CHARGE_MELEE_BONUS_RULE_ID,
        )
        self.assertEqual(
            result.resolution.attack.attacker_test.trace.rolled_dice,
            2,
        )
        self.assertTrue(
            result.resolution.target_state.conditions.has(Condition.STAGGERED)
        )
        self.assertEqual(
            result.applied_rule_ids,
            (
                CHARGE_ACTION_EXECUTION_RULE_ID,
                ZONE_GRAPH_RULE_ID,
                CHARGE_MELEE_BONUS_RULE_ID,
            ),
        )

    def test_non_melee_charge_does_not_receive_the_bonus(self) -> None:
        source = request(attack_skill=Skill.BRAWN)

        result = execute_charge_action(source, SequenceRandom([1]))

        self.assertIsNone(result.melee_bonus)
        self.assertIs(result.kernel_request, source.kernel_request)
        self.assertEqual(
            result.resolution.attack.attacker_test.trace.rolled_dice,
            1,
        )
        self.assertNotIn(
            CHARGE_MELEE_BONUS_RULE_ID,
            result.applied_rule_ids,
        )

    def test_target_must_be_an_enemy_at_medium_range(self) -> None:
        with self.assertRaises(ValueError):
            request(target_id="ally")

        with self.assertRaises(ValueError):
            execute_charge_action(
                request(state=spatial_state(target_zone_id="zone:c")),
                SequenceRandom([]),
            )

    def test_close_start_and_failed_close_approach_block_before_rng(self) -> None:
        blocked = (
            request(actor_began_turn_in_enemy_close_range=True),
            request(reaches_target_close_range=False),
        )
        for source in blocked:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    execute_charge_action(source, SequenceRandom([]))

    def test_speed_conditions_and_path_context_block_before_rng(self) -> None:
        blocked = (
            request(speed=MovementSpeed.SLOW),
            request(conditions=ConditionState({Condition.BURDENED})),
            request(conditions=ConditionState({Condition.PRONE})),
            request(conditions=ConditionState({Condition.DEFENCELESS})),
            request(path_entity_ids=("blocker",)),
            request(crosses_obstacle=True),
            request(crosses_difficult_terrain=True),
        )
        for source in blocked:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    execute_charge_action(source, SequenceRandom([]))

        result = execute_charge_action(
            request(path_entity_ids=("ally",)),
            SequenceRandom([1, 10]),
        )
        self.assertEqual(result.destination_zone_id, "zone:b")

    def test_attack_context_must_match_close_and_staggered_state(self) -> None:
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
                    attacker_modifiers=(
                        DiceModifier(CHARGE_MELEE_BONUS_RULE_ID, 1),
                    )
                )
            ),
        )
        for source in sources:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    execute_charge_action(source, SequenceRandom([]))

    def test_charge_requires_its_reserved_unexecuted_slot(self) -> None:
        aim_state = reserve_action(
            active_round(),
            CombatActionDeclaration(CombatActionKind.AIM),
        )
        with self.assertRaises(ValueError):
            execute_charge_action(
                request(round_state=aim_state),
                SequenceRandom([]),
            )
        with self.assertRaises(ValueError):
            execute_charge_action(request(slot_index=2), SequenceRandom([]))

        executed = execute_charge_action(
            request(),
            SequenceRandom([1, 10]),
        )
        with self.assertRaises(ValueError):
            execute_charge_action(
                request(
                    round_state=executed.round_state,
                    state=executed.spatial_state,
                ),
                SequenceRandom([]),
            )

    def test_second_slot_waits_for_the_first_slot(self) -> None:
        state = reserve_action(
            active_round(),
            CombatActionDeclaration(CombatActionKind.AIM),
        )
        state = reserve_action(
            state,
            charge_declaration(),
            grant=ActionSlotGrant.ABILITY,
        )
        with self.assertRaises(ValueError):
            execute_charge_action(
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
        result = execute_charge_action(
            request(round_state=state, slot_index=2),
            SequenceRandom([1, 10]),
        )
        self.assertIs(result.round_state.active_turn.action_slots[0], first_slot)
        self.assertTrue(result.round_state.active_turn.action_slots[1].executed)

    def test_failed_attack_resolution_leaves_inputs_unmodified(self) -> None:
        source = request()

        with self.assertRaises(RuntimeError):
            execute_charge_action(source, SequenceRandom([]))

        self.assertEqual(
            source.spatial_state.placement_for("hero").zone_id,
            "zone:a",
        )
        self.assertFalse(
            source.round_state.active_turn.action_slots[0].executed
        )

    def test_charge_must_execute_before_turn_ends(self) -> None:
        state = reserved_charge()
        with self.assertRaises(ValueError):
            end_combat_turn(CombatTurnEndRequest("turn:end", state, "hero"))

        executed = execute_charge_action(
            request(round_state=state),
            SequenceRandom([1, 10]),
        )
        ended = end_combat_turn(
            CombatTurnEndRequest("turn:end", executed.round_state, "hero")
        )
        self.assertTrue(ended.completed_turn.action_slots[0].executed)

    def test_result_rejects_forged_movement_bonus_and_turn(self) -> None:
        result = execute_charge_action(
            request(),
            SequenceRandom([1, 10]),
        )

        with self.assertRaises(ValueError):
            replace(result, target_in_close_range=False)
        with self.assertRaises(ValueError):
            replace(result, spatial_state=result.previous_spatial_state)
        with self.assertRaises(TypeError):
            replace(result, melee_bonus=None)
        with self.assertRaises(ValueError):
            replace(result, round_state=result.previous_round_state)


if __name__ == "__main__":
    unittest.main()
