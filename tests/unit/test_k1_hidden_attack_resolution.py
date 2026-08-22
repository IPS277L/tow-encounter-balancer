from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from tests.unit.test_k1_move_quietly_resolution import (
    request as move_quietly_request,
    reserve_action,
)
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.attack_models import (
    AttackOutcome,
    AttackRequest,
    DamageImpactSpec,
    DamageProfile,
    ResilienceProfile,
)
from towr.domain.condition_models import Condition
from towr.domain.hidden_attack_models import (
    HIDDEN_ATTACK_OPPORTUNITY_RULE_ID,
    HiddenAttackOpportunityLossReason,
    MoveQuietlyHiddenAttackExecutionRequest,
    MoveQuietlyHiddenAttackLossRequest,
)
from towr.domain.injury_models import CharacterInjuryState
from towr.domain.resolution_models import (
    KernelAttackRequest,
    TargetInjuryPolicy,
)
from towr.domain.spatial_models import SpatialEntityPlacement
from towr.domain.test_models import TestProfile, TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant,
    CombatActionDeclaration,
    CombatActionKind,
)
from towr.rules.attack_action_execution import ATTACK_ACTION_EXECUTION_RULE_ID
from towr.rules.hidden_attack_resolution import (
    execute_move_quietly_hidden_attack,
    lose_move_quietly_hidden_attack,
)
from towr.rules.move_quietly_resolution import execute_move_quietly_action


def completed_move_quietly():
    return execute_move_quietly_action(
        move_quietly_request(),
        SequenceRandom([1, 10, 10]),
    )


def attack_execution_request(
    move_quietly,
    *,
    actor_id: str = "hero",
    target_id: str = "scout",
    defender_test: TestRequest | None = None,
) -> AttackActionExecutionRequest:
    state = reserve_action(
        move_quietly.round_state,
        CombatActionDeclaration(CombatActionKind.ATTACK),
        grant=ActionSlotGrant.FATE,
    )
    return AttackActionExecutionRequest(
        id="execute:hidden-attack",
        state=state,
        actor_id=actor_id,
        target_id=target_id,
        slot_index=2,
        kernel_request=KernelAttackRequest(
            id="kernel:hidden-attack",
            attack=AttackRequest(
                id="attack:hidden",
                attacker_test=TestRequest(
                    "test:hidden-attacker",
                    TestProfile(2, 5),
                ),
                defender_test=defender_test,
                impact_spec=DamageImpactSpec(
                    damage=DamageProfile(3),
                    resilience=ResilienceProfile(toughness=4, bonus=1),
                ),
                is_close_range=False,
                attacker_is_staggered=False,
            ),
            target_policy=TargetInjuryPolicy.PLAYER,
            target_state=CharacterInjuryState(),
            can_target_leave_zone=True,
            target_has_given_ground_this_round=False,
        ),
    )


def execution_request(
    *,
    move_quietly=None,
    attack: AttackActionExecutionRequest | None = None,
    spatial_state=None,
    actor_id: str = "hero",
    target_id: str = "scout",
    hiding_position_id: str = "hiding:wall",
    target_is_unaware: bool = True,
    consumed: tuple[str, ...] = (),
) -> MoveQuietlyHiddenAttackExecutionRequest:
    move_quietly = move_quietly or completed_move_quietly()
    opportunity = move_quietly.hidden_attack_opportunity
    assert opportunity is not None
    return MoveQuietlyHiddenAttackExecutionRequest(
        id="consume:hidden-attack",
        move_quietly=move_quietly,
        opportunity=opportunity,
        actor_id=actor_id,
        target_id=target_id,
        spatial_state=spatial_state or move_quietly.spatial_state,
        hiding_position_id=hiding_position_id,
        target_is_unaware=target_is_unaware,
        attack=attack or attack_execution_request(
            move_quietly,
            actor_id=actor_id,
            target_id=target_id,
        ),
        consumed_opportunity_ids=consumed,
    )


def loss_request(
    *,
    move_quietly=None,
    spatial_state=None,
    hiding_position_id: str | None = "hiding:wall",
    kind: CombatActionKind = CombatActionKind.ATTACK,
    target_id: str | None = "scout",
    target_is_unaware: bool | None = False,
    consumed: tuple[str, ...] = (),
) -> MoveQuietlyHiddenAttackLossRequest:
    move_quietly = move_quietly or completed_move_quietly()
    opportunity = move_quietly.hidden_attack_opportunity
    assert opportunity is not None
    if kind is not CombatActionKind.ATTACK:
        target_id = None
        target_is_unaware = None
    return MoveQuietlyHiddenAttackLossRequest(
        id="lose:hidden-attack",
        move_quietly=move_quietly,
        opportunity=opportunity,
        actor_id="hero",
        spatial_state=spatial_state or move_quietly.spatial_state,
        hiding_position_id=hiding_position_id,
        next_action_id="execute:next-action",
        declaration=CombatActionDeclaration(kind),
        target_id=target_id,
        target_is_unaware=target_is_unaware,
        consumed_opportunity_ids=consumed,
    )


class K1HiddenAttackResolutionTests(unittest.TestCase):
    def test_valid_opportunity_executes_one_ordinary_unopposed_attack(self) -> None:
        source = execution_request(consumed=("hidden:older",))

        result = execute_move_quietly_hidden_attack(
            source,
            SequenceRandom([1, 10]),
        )

        self.assertIs(
            result.attack.resolution.attack.outcome,
            AttackOutcome.HIT,
        )
        self.assertIsNone(
            source.attack.kernel_request.attack.defender_test,
        )
        self.assertTrue(
            result.attack.resolution.target_state.conditions.has(
                Condition.STAGGERED
            )
        )
        self.assertTrue(result.attack.slot.executed)
        receipt = result.attack.slot.execution
        assert receipt is not None
        self.assertEqual(
            receipt.executor_rule_id,
            ATTACK_ACTION_EXECUTION_RULE_ID,
        )
        self.assertEqual(
            result.consumed_opportunity_ids,
            ("hidden:older", source.opportunity.id),
        )
        self.assertEqual(
            result.revealed_hiding_position_id,
            "hiding:wall",
        )
        self.assertIn(
            HIDDEN_ATTACK_OPPORTUNITY_RULE_ID,
            result.applied_rule_ids,
        )

    def test_execution_context_is_rejected_before_attack_rng(self) -> None:
        move_quietly = completed_move_quietly()
        opposed = TestRequest("test:defender", TestProfile(1, 5))
        invalid_builders = (
            lambda: execution_request(
                move_quietly=move_quietly,
                target_is_unaware=False,
            ),
            lambda: execution_request(
                move_quietly=move_quietly,
                hiding_position_id="hiding:other",
            ),
            lambda: execution_request(
                move_quietly=move_quietly,
                target_id="guard",
                attack=attack_execution_request(
                    move_quietly,
                    target_id="scout",
                ),
            ),
            lambda: execution_request(
                move_quietly=move_quietly,
                attack=attack_execution_request(
                    move_quietly,
                    defender_test=opposed,
                ),
            ),
        )
        for build in invalid_builders:
            with self.subTest(build=build):
                with self.assertRaises(ValueError):
                    build()

    def test_leaving_spatial_placement_rejects_hidden_attack(self) -> None:
        move_quietly = completed_move_quietly()
        moved = replace(
            move_quietly.spatial_state,
            placements=tuple(
                replace(item, zone_id="zone:c")
                if item.entity_id == "hero"
                else item
                for item in move_quietly.spatial_state.placements
            ),
        )

        with self.assertRaises(ValueError):
            execution_request(
                move_quietly=move_quietly,
                spatial_state=moved,
            )

    def test_failed_attack_execution_does_not_consume_opportunity(self) -> None:
        source = execution_request()

        with self.assertRaises(RuntimeError):
            execute_move_quietly_hidden_attack(source, SequenceRandom([]))

        self.assertEqual(source.consumed_opportunity_ids, ())
        self.assertFalse(
            source.attack.state.active_turn.action_slots[1].executed
        )

    def test_opportunity_is_consumed_once(self) -> None:
        source = execution_request()
        result = execute_move_quietly_hidden_attack(
            source,
            SequenceRandom([1, 10]),
        )

        with self.assertRaises(ValueError):
            execution_request(
                move_quietly=source.move_quietly,
                consumed=result.consumed_opportunity_ids,
            )

    def test_other_action_position_target_and_awareness_have_loss_outcomes(
        self,
    ) -> None:
        move_quietly = completed_move_quietly()
        moved = replace(
            move_quietly.spatial_state,
            placements=tuple(
                replace(item, zone_id="zone:c")
                if item.entity_id == "hero"
                else item
                for item in move_quietly.spatial_state.placements
            ),
        )
        cases = (
            (
                loss_request(
                    move_quietly=move_quietly,
                    kind=CombatActionKind.HELP,
                ),
                HiddenAttackOpportunityLossReason.OTHER_ACTION,
            ),
            (
                loss_request(
                    move_quietly=move_quietly,
                    spatial_state=moved,
                    target_is_unaware=True,
                ),
                HiddenAttackOpportunityLossReason.LEFT_HIDING_POSITION,
            ),
            (
                loss_request(
                    move_quietly=move_quietly,
                    target_id="ally",
                    target_is_unaware=True,
                ),
                HiddenAttackOpportunityLossReason.DIFFERENT_TARGET,
            ),
            (
                loss_request(move_quietly=move_quietly),
                HiddenAttackOpportunityLossReason.TARGET_AWARE,
            ),
        )
        for source, expected in cases:
            with self.subTest(expected=expected):
                result = lose_move_quietly_hidden_attack(source)
                self.assertIs(result.reason, expected)
                self.assertEqual(
                    result.consumed_opportunity_ids,
                    (source.opportunity.id,),
                )

    def test_eligible_attack_cannot_be_reported_as_lost(self) -> None:
        with self.assertRaises(ValueError):
            loss_request(target_is_unaware=True)

    def test_results_reject_forged_consumption_reason_and_trace(self) -> None:
        execution = execute_move_quietly_hidden_attack(
            execution_request(),
            SequenceRandom([1, 10]),
        )
        with self.assertRaises(ValueError):
            replace(execution, consumed_opportunity_ids=())
        with self.assertRaises(ValueError):
            replace(
                execution,
                applied_rule_ids=(ATTACK_ACTION_EXECUTION_RULE_ID,),
            )

        loss = lose_move_quietly_hidden_attack(loss_request())
        with self.assertRaises(ValueError):
            replace(
                loss,
                reason=HiddenAttackOpportunityLossReason.OTHER_ACTION,
            )


if __name__ == "__main__":
    unittest.main()
