from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.help_models import (
    HELP_ACTION_RULE_ID,
    HELP_BONUS_RULE_ID,
    HelpActionExecutionRequest,
    HelpBonusApplicationRequest,
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
)
from towr.rules.help_resolution import apply_help_bonus, execute_help_action
from towr.rules.test_resolution import resolve_test
from towr.rules.turn_resolution import (
    end_combat_turn,
    reserve_combat_action_slot,
    start_combat_turn,
)


def active_round() -> CombatRoundState:
    state = CombatRoundState(
        round_number=1,
        participants=(
            CombatTurnParticipant("helper", CombatSide.PLAYERS_AND_ALLIES),
            CombatTurnParticipant("ally", CombatSide.PLAYERS_AND_ALLIES),
            CombatTurnParticipant("enemy", CombatSide.OPPOSITION),
        ),
    )
    return start_combat_turn(
        CombatTurnStartRequest("turn:helper", state, "helper")
    ).state


def reserve_action(
    state: CombatRoundState,
    kind: CombatActionKind,
) -> CombatRoundState:
    return reserve_combat_action_slot(
        CombatActionSlotRequest(
            id="slot:1",
            state=state,
            actor_id="helper",
            declaration=CombatActionDeclaration(kind),
            grant=ActionSlotGrant.STANDARD,
        )
    ).state


def help_request(
    state: CombatRoundState,
    *,
    actor_conditions: ConditionState = ConditionState(),
    beneficiary_id: str = "ally",
    help_skill: Skill = Skill.AWARENESS,
    beneficiary_skill: Skill = Skill.AWARENESS,
    different_skill_approved_by_gm: bool = False,
    rule_id: str = HELP_ACTION_RULE_ID,
) -> HelpActionExecutionRequest:
    return HelpActionExecutionRequest(
        id="help:execute",
        round_state=state,
        actor_id="helper",
        actor_conditions=actor_conditions,
        beneficiary_id=beneficiary_id,
        beneficiary_test_id="beneficiary:test",
        slot_index=1,
        help_test=TestRequest("help:test", TestProfile(3, 5)),
        help_skill=help_skill,
        beneficiary_skill=beneficiary_skill,
        different_skill_approved_by_gm=different_skill_approved_by_gm,
        rule_id=rule_id,
    )


def completed_help(*, values: tuple[int, ...] = (1, 5, 10)):
    state = reserve_action(active_round(), CombatActionKind.HELP)
    return execute_help_action(help_request(state), SequenceRandom(values))


def application_request(
    help_result,
    *,
    beneficiary_id: str = "ally",
    beneficiary_skill: Skill = Skill.AWARENESS,
    test_id: str = "beneficiary:test",
    profile: TestProfile = TestProfile(2, 5),
) -> HelpBonusApplicationRequest:
    return HelpBonusApplicationRequest(
        id="help:apply",
        help=help_result,
        beneficiary_id=beneficiary_id,
        beneficiary_skill=beneficiary_skill,
        test=TestRequest(test_id, profile),
    )


class K1HelpActionExecutionTests(unittest.TestCase):
    def test_help_executes_own_test_and_completes_reserved_slot(self) -> None:
        state = reserve_action(active_round(), CombatActionKind.HELP)

        result = execute_help_action(
            help_request(state),
            SequenceRandom([1, 5, 10]),
        )

        self.assertEqual(result.help_test_result.successes, 2)
        self.assertEqual(result.bonus.bonus_dice, 2)
        self.assertEqual(result.bonus.helper_id, "helper")
        self.assertEqual(result.bonus.beneficiary_id, "ally")
        self.assertEqual(result.bonus.beneficiary_test_id, "beneficiary:test")
        self.assertTrue(result.slot.executed)
        receipt = result.slot.execution
        assert receipt is not None
        self.assertEqual(receipt.source_request_id, "help:execute")
        self.assertEqual(receipt.result_request_id, "help:test")
        self.assertIn(HELP_ACTION_RULE_ID, result.applied_rule_ids)
        self.assertIn(HELP_BONUS_RULE_ID, result.applied_rule_ids)

    def test_failed_help_still_completes_slot_with_zero_bonus(self) -> None:
        state = reserve_action(active_round(), CombatActionKind.HELP)

        result = execute_help_action(
            help_request(state),
            SequenceRandom([8, 9, 10]),
        )

        self.assertEqual(result.help_test_result.successes, 0)
        self.assertEqual(result.bonus.bonus_dice, 0)
        self.assertTrue(result.slot.executed)

    def test_different_skill_requires_explicit_gm_approval(self) -> None:
        state = reserve_action(active_round(), CombatActionKind.HELP)
        with self.assertRaises(ValueError):
            help_request(
                state,
                help_skill=Skill.AWARENESS,
                beneficiary_skill=Skill.RECALL,
            )

        result = execute_help_action(
            help_request(
                state,
                help_skill=Skill.AWARENESS,
                beneficiary_skill=Skill.RECALL,
                different_skill_approved_by_gm=True,
            ),
            SequenceRandom([1, 10, 10]),
        )
        self.assertIs(result.bonus.help_skill, Skill.AWARENESS)
        self.assertIs(result.bonus.beneficiary_skill, Skill.RECALL)
        self.assertTrue(result.bonus.different_skill_approved_by_gm)

    def test_help_requires_another_allied_participant(self) -> None:
        state = reserve_action(active_round(), CombatActionKind.HELP)
        with self.assertRaises(ValueError):
            help_request(state, beneficiary_id="helper")
        with self.assertRaises(ValueError):
            help_request(state, beneficiary_id="enemy")

    def test_deafened_and_defenceless_cannot_execute_help(self) -> None:
        state = reserve_action(active_round(), CombatActionKind.HELP)
        for condition in (Condition.DEAFENED, Condition.DEFENCELESS):
            with self.subTest(condition=condition):
                with self.assertRaises(ValueError):
                    execute_help_action(
                        help_request(
                            state,
                            actor_conditions=ConditionState({condition}),
                        ),
                        SequenceRandom([1, 1, 1]),
                    )

    def test_wrong_or_already_executed_slot_is_rejected(self) -> None:
        attack_state = reserve_action(active_round(), CombatActionKind.ATTACK)
        with self.assertRaises(ValueError):
            execute_help_action(
                help_request(attack_state),
                SequenceRandom([1, 1, 1]),
            )

        completed = completed_help()
        repeated = replace(
            completed.source_request,
            round_state=completed.round_state,
        )
        with self.assertRaises(ValueError):
            execute_help_action(repeated, SequenceRandom([1, 1, 1]))

    def test_turn_cannot_end_with_unexecuted_help(self) -> None:
        state = reserve_action(active_round(), CombatActionKind.HELP)
        with self.assertRaises(ValueError):
            end_combat_turn(CombatTurnEndRequest("turn:end", state, "helper"))

        completed = execute_help_action(
            help_request(state),
            SequenceRandom([8, 9, 10]),
        )
        ended = end_combat_turn(
            CombatTurnEndRequest("turn:end", completed.round_state, "helper")
        )
        self.assertIsNone(ended.state.active_turn)

    def test_result_rejects_forged_bonus(self) -> None:
        result = completed_help()
        with self.assertRaises(ValueError):
            replace(
                result,
                bonus=replace(
                    result.bonus,
                    bonus_dice=result.bonus.bonus_dice + 1,
                ),
            )


class K1HelpBonusApplicationTests(unittest.TestCase):
    def test_bonus_applies_to_exact_test_and_obeys_normal_pool_cap(self) -> None:
        help_result = completed_help(values=(1, 2, 3))

        application = apply_help_bonus(application_request(help_result))

        self.assertEqual(application.modifier.amount, 3)
        self.assertFalse(application.modifier.bypasses_pool_cap)
        self.assertIn(HELP_BONUS_RULE_ID, application.applied_rule_ids)
        resolved = resolve_test(
            application.test,
            SequenceRandom([1, 5, 10, 10]),
        )
        self.assertEqual(resolved.trace.regular_dice_delta, 3)
        self.assertEqual(resolved.trace.rolled_dice, 4)

    def test_zero_bonus_is_applied_without_a_modifier(self) -> None:
        help_result = completed_help(values=(8, 9, 10))
        request = application_request(help_result)

        result = apply_help_bonus(request)

        self.assertIsNone(result.modifier)
        self.assertIs(result.test, request.test)

    def test_help_from_multiple_allies_can_stack_on_the_same_test(self) -> None:
        help_result = completed_help(values=(1, 5, 10))
        previous_help = DiceModifier(HELP_BONUS_RULE_ID, 1)
        test = TestRequest(
            "beneficiary:test",
            TestProfile(3, 5),
            dice_modifiers=(previous_help,),
        )
        request = HelpBonusApplicationRequest(
            id="help:apply",
            help=help_result,
            beneficiary_id="ally",
            beneficiary_skill=Skill.AWARENESS,
            test=test,
        )

        result = apply_help_bonus(request)

        self.assertEqual(
            tuple(item.amount for item in result.test.dice_modifiers),
            (1, 2),
        )

    def test_application_is_bound_to_beneficiary_skill_and_test_id(self) -> None:
        help_result = completed_help()
        with self.assertRaises(ValueError):
            application_request(help_result, beneficiary_id="helper")
        with self.assertRaises(ValueError):
            application_request(help_result, beneficiary_skill=Skill.RECALL)
        with self.assertRaises(ValueError):
            application_request(help_result, test_id="other:test")

    def test_application_result_rejects_forged_test(self) -> None:
        result = apply_help_bonus(application_request(completed_help()))

        with self.assertRaises(ValueError):
            replace(
                result,
                test=TestRequest("beneficiary:test", TestProfile(5, 5)),
            )


if __name__ == "__main__":
    unittest.main()
