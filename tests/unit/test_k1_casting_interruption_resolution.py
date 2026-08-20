from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.action_execution_models import (
    AttackActionExecutionRequest,
    AttackActionExecutionResult,
    SkippedCastingTestAfterAttackRequest,
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
    ActionSlotGrant,
    CombatActionDeclaration,
    CombatActionKind,
    CombatActionSlotRequest,
    CombatRoundState,
    CombatSide,
    CombatTurnParticipant,
    CombatTurnStartRequest,
)
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.casting_interruption_resolution import (
    SKIPPED_CASTING_TEST_RULE_ID,
    resolve_skipped_casting_test_after_attack,
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
    attack: AttackActionExecutionResult,
    *,
    caster_id: str = "wizard",
    state: WizardMagicState | None = None,
    wizard_level: int = 2,
) -> SkippedCastingTestAfterAttackRequest:
    return SkippedCastingTestAfterAttackRequest(
        id="casting:skipped-after-attack",
        caster_id=caster_id,
        attack=attack,
        state=state if state is not None else active_magic(),
        wizard_level=wizard_level,
    )


class K1CastingInterruptionResolutionTests(unittest.TestCase):
    def test_attack_while_casting_adds_exactly_one_miscast_die(self) -> None:
        attack = executed_attack()

        result = resolve_skipped_casting_test_after_attack(
            skipped_request(attack)
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
            result.applied_rule_ids,
            (SKIPPED_CASTING_TEST_RULE_ID, MISCAST_POOL_RULE_ID),
        )

    def test_skipped_test_can_trigger_miscast_at_threshold(self) -> None:
        result = resolve_skipped_casting_test_after_attack(
            skipped_request(
                executed_attack(),
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
        attack = executed_attack()
        with self.assertRaises(ValueError):
            skipped_request(attack, state=WizardMagicState())
        with self.assertRaises(ValueError):
            skipped_request(attack, caster_id="enemy")

    def test_already_triggered_pool_rejects_another_skipped_test(self) -> None:
        with self.assertRaises(ValueError):
            resolve_skipped_casting_test_after_attack(
                skipped_request(
                    executed_attack(),
                    state=active_magic(miscast_dice=3),
                )
            )

    def test_forged_attack_executor_receipt_is_rejected(self) -> None:
        attack = executed_attack()
        receipt = attack.slot.execution
        assert receipt is not None
        forged_receipt = replace(
            receipt,
            executor_rule_id="RULE-COMBAT-004:forged-attack",
        )
        forged_slot = replace(attack.slot, execution=forged_receipt)
        turn = attack.state.active_turn
        assert turn is not None
        forged_state = replace(
            attack.state,
            active_turn=replace(turn, action_slots=(forged_slot,)),
        )
        forged_attack = replace(
            attack,
            state=forged_state,
            slot=forged_slot,
            applied_rule_ids=(forged_receipt.executor_rule_id,),
        )

        with self.assertRaises(ValueError):
            resolve_skipped_casting_test_after_attack(
                skipped_request(forged_attack)
            )

    def test_result_rejects_source_or_state_forgery(self) -> None:
        result = resolve_skipped_casting_test_after_attack(
            skipped_request(executed_attack())
        )

        with self.assertRaises(ValueError):
            replace(result, source=replace(result.source, amount=2))
        with self.assertRaises(ValueError):
            replace(result, state=active_magic())
        with self.assertRaises(TypeError):
            replace(result.source, source_kind="action")


if __name__ == "__main__":
    unittest.main()
