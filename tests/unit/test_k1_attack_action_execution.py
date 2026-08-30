from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.attack_models import (
    AttackRequest,
    DamageImpactSpec,
    DamageProfile,
    ResilienceProfile,
)
from towr.domain.condition_models import Condition
from towr.domain.injury_models import CharacterInjuryState
from towr.domain.resolution_models import (
    KernelAttackRequest,
    TargetInjuryPolicy,
)
from towr.domain.test_models import TestProfile, TestRequest
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
from towr.rules.attack_action_execution import (
    ATTACK_ACTION_EXECUTION_RULE_ID,
    execute_attack_action,
)
from towr.rules.turn_resolution import (
    end_combat_turn,
    reserve_combat_action_slot,
    start_combat_turn,
)


def initial_round() -> CombatRoundState:
    return CombatRoundState(
        round_number=1,
        participants=(
            CombatTurnParticipant(
                "hero",
                CombatSide.PLAYERS_AND_ALLIES,
            ),
            CombatTurnParticipant("enemy", CombatSide.OPPOSITION),
        ),
    )


def started_turn() -> CombatRoundState:
    return start_combat_turn(
        CombatTurnStartRequest("turn:start", initial_round(), "hero")
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


def kernel_request(
    *,
    request_id: str = "kernel:attack",
) -> KernelAttackRequest:
    return KernelAttackRequest(
        id=request_id,
        attack=AttackRequest(
            id=f"{request_id}:test",
            attacker_test=TestRequest(
                f"{request_id}:attacker",
                TestProfile(3, 5),
            ),
            defender_test=None,
            impact_spec=DamageImpactSpec(
                damage=DamageProfile(3),
                resilience=ResilienceProfile(toughness=4, bonus=1),
            ),
            is_close_range=True,
            attacker_is_staggered=False,
        ),
        target_policy=TargetInjuryPolicy.PLAYER,
        target_state=CharacterInjuryState(),
        can_target_leave_zone=True,
        target_has_given_ground_this_round=False,
    )


def execution_request(
    state: CombatRoundState,
    *,
    actor_id: str = "hero",
    target_id: str = "enemy",
    slot_index: int = 1,
    request_id: str = "execute:attack",
) -> AttackActionExecutionRequest:
    return AttackActionExecutionRequest(
        id=request_id,
        state=state,
        actor_id=actor_id,
        target_id=target_id,
        slot_index=slot_index,
        kernel_request=kernel_request(),
    )


class K1AttackActionExecutionTests(unittest.TestCase):
    def test_reserved_attack_executes_through_kernel_and_marks_slot(self) -> None:
        state = reserve_action(
            started_turn(),
            CombatActionDeclaration(CombatActionKind.ATTACK),
        )

        result = execute_attack_action(
            execution_request(state),
            SequenceRandom([1, 10, 10]),
        )

        self.assertIs(result.previous_state, state)
        self.assertEqual(result.actor_id, "hero")
        self.assertEqual(result.target_id, "enemy")
        self.assertEqual(result.slot_index, 1)
        self.assertFalse(state.active_turn.action_slots[0].executed)
        self.assertTrue(result.slot.executed)
        self.assertEqual(
            result.state.active_turn.action_slots[0],
            result.slot,
        )
        receipt = result.slot.execution
        assert receipt is not None
        self.assertEqual(receipt.id, "execute:attack")
        self.assertEqual(
            receipt.executor_rule_id,
            ATTACK_ACTION_EXECUTION_RULE_ID,
        )
        self.assertEqual(receipt.source_request_id, "kernel:attack")
        self.assertEqual(receipt.result_request_id, "kernel:attack")
        self.assertEqual(result.resolution.request_id, "kernel:attack")
        self.assertTrue(
            result.resolution.target_state.conditions.has(Condition.STAGGERED)
        )
        self.assertEqual(
            result.applied_rule_ids,
            (ATTACK_ACTION_EXECUTION_RULE_ID,),
        )

    def test_second_attack_slot_executes_without_changing_first_slot(self) -> None:
        state = reserve_action(
            started_turn(),
            CombatActionDeclaration(CombatActionKind.AIM),
        )
        state = reserve_action(
            state,
            CombatActionDeclaration(CombatActionKind.ATTACK),
            grant=ActionSlotGrant.ABILITY,
        )
        with self.assertRaises(ValueError):
            execute_attack_action(
                execution_request(state, slot_index=2),
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

        result = execute_attack_action(
            execution_request(state, slot_index=2),
            SequenceRandom([1, 10, 10]),
        )

        self.assertIs(result.state.active_turn.action_slots[0], first_slot)
        self.assertTrue(result.state.active_turn.action_slots[1].executed)

    def test_non_attack_and_charge_slots_are_rejected_before_rng(self) -> None:
        declarations = (
            CombatActionDeclaration(CombatActionKind.AIM),
            CombatActionDeclaration(
                CombatActionKind.MANOEUVRE,
                manoeuvre=ManoeuvreKind.CHARGE,
            ),
        )
        for declaration in declarations:
            with self.subTest(declaration=declaration):
                state = reserve_action(started_turn(), declaration)
                with self.assertRaises(ValueError):
                    execute_attack_action(
                        execution_request(state),
                        SequenceRandom([]),
                    )

    def test_wrong_actor_and_unreserved_slot_are_rejected_before_rng(self) -> None:
        state = reserve_action(
            started_turn(),
            CombatActionDeclaration(CombatActionKind.ATTACK),
        )

        with self.assertRaises(ValueError):
            execute_attack_action(
                execution_request(state, actor_id="enemy"),
                SequenceRandom([]),
            )
        with self.assertRaises(ValueError):
            execute_attack_action(
                execution_request(state, slot_index=2),
                SequenceRandom([]),
            )

    def test_executed_slot_cannot_run_twice(self) -> None:
        state = reserve_action(
            started_turn(),
            CombatActionDeclaration(CombatActionKind.ATTACK),
        )
        result = execute_attack_action(
            execution_request(state),
            SequenceRandom([1, 10, 10]),
        )

        with self.assertRaises(ValueError):
            execute_attack_action(
                execution_request(
                    result.state,
                    request_id="execute:again",
                ),
                SequenceRandom([]),
            )

    def test_reserved_attack_must_execute_before_turn_can_end(self) -> None:
        state = reserve_action(
            started_turn(),
            CombatActionDeclaration(CombatActionKind.ATTACK),
        )
        with self.assertRaises(ValueError):
            end_combat_turn(
                CombatTurnEndRequest("turn:end", state, "hero")
            )

        executed = execute_attack_action(
            execution_request(state),
            SequenceRandom([1, 10, 10]),
        )
        ended = end_combat_turn(
            CombatTurnEndRequest("turn:end", executed.state, "hero")
        )

        self.assertEqual(ended.completed_turn.actor_id, "hero")
        self.assertTrue(ended.completed_turn.action_slots[0].executed)

    def test_failed_kernel_execution_leaves_reserved_state_unchanged(self) -> None:
        state = reserve_action(
            started_turn(),
            CombatActionDeclaration(CombatActionKind.ATTACK),
        )

        with self.assertRaises(RuntimeError):
            execute_attack_action(
                execution_request(state),
                SequenceRandom([]),
            )

        self.assertFalse(state.active_turn.action_slots[0].executed)

    def test_result_rejects_forged_actor_or_round_mutation(self) -> None:
        state = reserve_action(
            started_turn(),
            CombatActionDeclaration(CombatActionKind.ATTACK),
        )
        result = execute_attack_action(
            execution_request(state),
            SequenceRandom([1, 10, 10]),
        )

        with self.assertRaises(ValueError):
            replace(result, actor_id="enemy")
        with self.assertRaises(ValueError):
            replace(result, state=result.previous_state)


if __name__ == "__main__":
    unittest.main()
