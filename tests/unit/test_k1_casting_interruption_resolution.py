from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.action_execution_models import (
    AttackActionExecutionRequest,
    AttackActionExecutionResult,
    SkippedCastingTestAfterActionRequest,
)
from towr.domain.attack_models import (
    AttackRequest,
    DamageImpactSpec,
    DamageProfile,
    ResilienceProfile,
)
from towr.domain.injury_models import CharacterInjuryState
from towr.domain.magic_models import (
    MiscastPoolIncreaseSourceKind,
    MiscastPoolOutcome,
    WizardMagicState,
)
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
    CombatTurnParticipant,
    CombatTurnStartRequest,
    ImproviseKind,
    ManoeuvreKind,
)
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.casting_interruption_resolution import (
    SKIPPED_CASTING_TEST_RULE_ID,
    resolve_skipped_casting_test_after_action,
)
from towr.rules.miscast_pool_resolution import MISCAST_POOL_RULE_ID
from towr.rules.turn_resolution import (
    reserve_combat_action_slot,
    start_combat_turn,
)


def executed_attack() -> AttackActionExecutionResult:
    round_state = CombatRoundState(
        round_number=1,
        participants=(
            CombatTurnParticipant(
                "wizard",
                CombatSide.PLAYERS_AND_ALLIES,
            ),
            CombatTurnParticipant("enemy", CombatSide.OPPOSITION),
        ),
    )
    started = start_combat_turn(
        CombatTurnStartRequest("turn:start", round_state, "wizard")
    ).state
    reserved = reserve_combat_action_slot(
        CombatActionSlotRequest(
            id="slot:attack",
            state=started,
            actor_id="wizard",
            declaration=CombatActionDeclaration(CombatActionKind.ATTACK),
            grant=ActionSlotGrant.STANDARD,
        )
    ).state
    return execute_attack_action(
        AttackActionExecutionRequest(
            id="execute:attack",
            state=reserved,
            actor_id="wizard",
            target_id="enemy",
            slot_index=1,
            kernel_request=_kernel_attack(),
        ),
        SequenceRandom([1, 10, 10]),
    )


def _kernel_attack() -> KernelAttackRequest:
    return KernelAttackRequest(
        id="kernel:attack",
        target_id="enemy",
        attack=AttackRequest(
            id="attack:test",
            attacker_test=TestRequest(
                "attack:attacker",
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


def active_magic(*, miscast_dice: int = 0) -> WizardMagicState:
    return WizardMagicState(
        miscast_dice=miscast_dice,
        casting_successes=2,
        casting_lore_id="lore:beasts",
        latest_casting_roll_successes=2,
    )


def skipped_request(
    action: ActionExecutionReceipt,
    *,
    caster_id: str = "wizard",
    state: WizardMagicState | None = None,
    wizard_level: int = 2,
    consumed_action_execution_ids: tuple[str, ...] = (),
) -> SkippedCastingTestAfterActionRequest:
    return SkippedCastingTestAfterActionRequest(
        id="casting:skipped-after-action",
        caster_id=caster_id,
        action=action,
        state=state if state is not None else active_magic(),
        wizard_level=wizard_level,
        consumed_action_execution_ids=consumed_action_execution_ids,
    )


def action_receipt(
    declaration: CombatActionDeclaration,
    *,
    execution_id: str = "execute:action",
    actor_id: str = "wizard",
) -> ActionExecutionReceipt:
    return ActionExecutionReceipt(
        id=execution_id,
        executor_rule_id="RULE-COMBAT-004:test-action-execution",
        source_request_id=f"{execution_id}:source",
        result_request_id=f"{execution_id}:result",
        actor_id=actor_id,
        round_number=1,
        slot_index=1,
        declaration=declaration,
    )


class K1CastingInterruptionResolutionTests(unittest.TestCase):
    def test_attack_while_casting_adds_exactly_one_miscast_die(self) -> None:
        attack = executed_attack()
        receipt = attack.slot.execution
        assert receipt is not None

        result = resolve_skipped_casting_test_after_action(
            skipped_request(receipt)
        )

        self.assertEqual(result.source.amount, 1)
        self.assertIs(
            result.source.source_kind,
            MiscastPoolIncreaseSourceKind.ACTION,
        )
        self.assertEqual(result.source.source_id, "execute:attack")
        self.assertEqual(result.source.target_id, "wizard")
        self.assertIs(
            result.miscast_pool.outcome,
            MiscastPoolOutcome.ACCUMULATED,
        )
        self.assertEqual(result.state.miscast_dice, 1)
        self.assertEqual(result.state.casting_successes, 2)
        self.assertEqual(result.state.casting_lore_id, "lore:beasts")
        self.assertEqual(
            result.consumed_action_execution_ids,
            ("execute:attack",),
        )
        self.assertEqual(
            result.applied_rule_ids,
            (SKIPPED_CASTING_TEST_RULE_ID, MISCAST_POOL_RULE_ID),
        )

    def test_skipped_test_can_trigger_miscast_at_threshold(self) -> None:
        attack = executed_attack()
        receipt = attack.slot.execution
        assert receipt is not None
        result = resolve_skipped_casting_test_after_action(
            skipped_request(
                receipt,
                state=active_magic(miscast_dice=2),
            )
        )

        self.assertIs(
            result.miscast_pool.outcome,
            MiscastPoolOutcome.MISCAST_TRIGGERED,
        )
        self.assertEqual(result.state.miscast_dice, 3)
        self.assertEqual(result.state.casting_successes, 2)
        self.assertIsNotNone(result.miscast_pool.roll_request)
        assert result.miscast_pool.roll_request is not None
        self.assertEqual(result.miscast_pool.roll_request.dice_count, 3)

    def test_request_requires_active_casting_and_matching_actor(self) -> None:
        receipt = action_receipt(
            CombatActionDeclaration(CombatActionKind.HELP)
        )
        with self.assertRaises(ValueError):
            skipped_request(receipt, state=WizardMagicState())
        with self.assertRaises(ValueError):
            skipped_request(receipt, caster_id="enemy")

    def test_already_triggered_pool_rejects_another_skipped_test(self) -> None:
        with self.assertRaises(ValueError):
            resolve_skipped_casting_test_after_action(
                skipped_request(
                    action_receipt(
                        CombatActionDeclaration(CombatActionKind.AIM)
                    ),
                    state=active_magic(miscast_dice=3),
                )
            )

    def test_all_non_casting_action_declarations_are_supported(self) -> None:
        declarations = (
            CombatActionDeclaration(CombatActionKind.AIM),
            CombatActionDeclaration(CombatActionKind.ATTACK),
            CombatActionDeclaration(CombatActionKind.HELP),
            CombatActionDeclaration(CombatActionKind.RECOVER),
            CombatActionDeclaration(
                CombatActionKind.MANOEUVRE,
                manoeuvre=ManoeuvreKind.RUN,
            ),
            CombatActionDeclaration(
                CombatActionKind.IMPROVISE,
                improvise_kind=ImproviseKind.SKILL,
                improvise_approach_id="skill:athletics",
            ),
            CombatActionDeclaration(
                CombatActionKind.IMPROVISE,
                improvise_kind=ImproviseKind.ABILITY,
                improvise_approach_id="ability:example",
            ),
        )
        for index, declaration in enumerate(declarations):
            with self.subTest(declaration=declaration):
                receipt = action_receipt(
                    declaration,
                    execution_id=f"execute:{index}",
                )
                result = resolve_skipped_casting_test_after_action(
                    skipped_request(receipt, wizard_level=10)
                )
                self.assertEqual(result.source.source_id, receipt.id)
                self.assertEqual(result.state.miscast_dice, 1)

    def test_spell_improvise_receipt_is_not_a_skipped_test(self) -> None:
        receipt = action_receipt(
            CombatActionDeclaration(
                CombatActionKind.IMPROVISE,
                improvise_kind=ImproviseKind.SPELL,
                improvise_approach_id="lore:beasts",
            )
        )
        with self.assertRaises(ValueError):
            skipped_request(receipt)

    def test_distinct_actions_chain_and_same_action_cannot_repeat(self) -> None:
        first = action_receipt(
            CombatActionDeclaration(CombatActionKind.AIM),
            execution_id="execute:first",
        )
        second = action_receipt(
            CombatActionDeclaration(CombatActionKind.HELP),
            execution_id="execute:second",
        )
        first_result = resolve_skipped_casting_test_after_action(
            skipped_request(first, wizard_level=10)
        )
        second_result = resolve_skipped_casting_test_after_action(
            skipped_request(
                second,
                state=first_result.state,
                wizard_level=10,
                consumed_action_execution_ids=("execute:first",),
            )
        )

        self.assertEqual(second_result.state.miscast_dice, 2)
        self.assertEqual(
            second_result.consumed_action_execution_ids,
            ("execute:first", "execute:second"),
        )
        with self.assertRaises(ValueError):
            skipped_request(
                first,
                state=second_result.state,
                wizard_level=10,
                consumed_action_execution_ids=(
                    "execute:first",
                    "execute:second",
                ),
            )

    def test_receipt_context_is_bound_to_slot_turn_and_round(self) -> None:
        attack = executed_attack()
        receipt = attack.slot.execution
        assert receipt is not None

        with self.assertRaises(ValueError):
            replace(attack.slot, execution=replace(receipt, slot_index=2))
        turn = attack.state.active_turn
        assert turn is not None
        with self.assertRaises(ValueError):
            replace(turn, actor_id="enemy")
        with self.assertRaises(ValueError):
            replace(attack.state, round_number=2)
        forged_receipt = replace(
            receipt,
            executor_rule_id="RULE-COMBAT-004:forged-attack",
        )
        forged_slot = replace(attack.slot, execution=forged_receipt)
        forged_state = replace(
            attack.state,
            active_turn=replace(turn, action_slots=(forged_slot,)),
        )
        with self.assertRaises(ValueError):
            replace(
                attack,
                state=forged_state,
                slot=forged_slot,
                applied_rule_ids=(forged_receipt.executor_rule_id,),
            )

    def test_result_rejects_source_or_state_forgery(self) -> None:
        result = resolve_skipped_casting_test_after_action(
            skipped_request(
                action_receipt(
                    CombatActionDeclaration(CombatActionKind.RECOVER)
                )
            )
        )

        with self.assertRaises(ValueError):
            replace(result, source=replace(result.source, amount=2))
        with self.assertRaises(ValueError):
            replace(result, state=active_magic())
        with self.assertRaises(ValueError):
            replace(result, consumed_action_execution_ids=())
        with self.assertRaises(TypeError):
            replace(result.source, source_kind="action")


if __name__ == "__main__":
    unittest.main()
