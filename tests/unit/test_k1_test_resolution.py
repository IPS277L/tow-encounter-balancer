from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.test_models import (
    BasicOutcome,
    DiceModifier,
    InlineProfile,
    QualityModifier,
    Skill,
    SuccessModifier,
    TestProfile,
    TestQuality,
    TestRequest,
)
from towr.rules.test_resolution import (
    InvalidTestDecisionError,
    MissingTestDecisionError,
    RerollAllFailures,
    complete_test,
    roll_test_initial,
    resolve_basic_test,
    resolve_test,
)


class K1TestProfileTests(unittest.TestCase):
    def test_skill_enum_contains_the_complete_book_skill_table(self) -> None:
        self.assertEqual(len(Skill), 16)
        self.assertIs(Skill.ENDURANCE, Skill("endurance"))

    def test_profile_uses_characteristic_for_dice_and_skill_for_threshold(self) -> None:
        profile = TestProfile(characteristic=4, skill=5)

        self.assertEqual(profile.base_dice, 4)
        self.assertEqual(profile.threshold, 5)
        self.assertEqual(profile.maximum_dice, 8)

    def test_rejects_invalid_profile_values(self) -> None:
        with self.assertRaises(ValueError):
            TestProfile(characteristic=0, skill=5)
        with self.assertRaises(ValueError):
            TestProfile(characteristic=2, skill=0)
        with self.assertRaises(ValueError):
            TestProfile(characteristic=2, skill=11)

    def test_inline_profile_has_explicit_or_derived_pool_cap(self) -> None:
        self.assertEqual(InlineProfile(3, 4).maximum_dice, 6)
        self.assertEqual(InlineProfile(3, 4, pool_cap=10).maximum_dice, 10)


class K1TestResolutionTests(unittest.TestCase):
    def test_staged_resolution_matches_compatible_one_shot_resolution(self) -> None:
        request = TestRequest(
            id="staged",
            profile=TestProfile(2, 5),
            quality_modifiers=(
                QualityModifier("RULE-GLORIOUS", TestQuality.GLORIOUS),
            ),
        )

        one_shot = resolve_test(
            request,
            SequenceRandom([1, 9, 2]),
            decisions=RerollAllFailures(),
        )
        initial = roll_test_initial(request, SequenceRandom([1, 9]))
        staged = complete_test(
            initial,
            SequenceRandom([2]),
            decisions=RerollAllFailures(),
        )

        self.assertEqual(staged, one_shot)

    def test_initial_roll_is_validated_and_cannot_be_forged(self) -> None:
        request = TestRequest("snapshot", TestProfile(2, 5))
        initial = roll_test_initial(request, SequenceRandom([1, 9]))

        self.assertEqual(initial.initial_values, (1, 9))
        with self.assertRaisesRegex(ValueError, "stale pool provenance"):
            replace(initial, threshold=4)
        with self.assertRaisesRegex(ValueError, "rolled pool"):
            replace(initial, initial_values=(1,))
        with self.assertRaisesRegex(ValueError, "integers from 1 to 10"):
            replace(initial, initial_values=(1, 11))

    def test_completion_rejects_changes_except_appended_fate_glorious(self) -> None:
        source = TestRequest("snapshot", TestProfile(2, 5))
        initial = roll_test_initial(source, SequenceRandom([1, 9]))

        with self.assertRaisesRegex(ValueError, "changes the snapshotted Test"):
            complete_test(
                initial,
                SequenceRandom([]),
                request=replace(source, profile=TestProfile(3, 5)),
            )
        with self.assertRaisesRegex(ValueError, "only append one Fate"):
            complete_test(
                initial,
                SequenceRandom([]),
                request=replace(
                    source,
                    quality_modifiers=(
                        QualityModifier("RULE-GLORIOUS", TestQuality.GLORIOUS),
                    ),
                ),
                decisions=RerollAllFailures(),
            )

    def test_natural_one_die_pool_uses_normal_skill_threshold(self) -> None:
        request = TestRequest(id="awareness", profile=TestProfile(1, 5))

        result = resolve_test(request, SequenceRandom([5]))

        self.assertEqual(result.successes, 1)
        self.assertFalse(result.trace.minimum_die_rule_applied)
        self.assertEqual(result.trace.threshold, 5)

    def test_pool_reduced_below_one_rolls_one_die_succeeding_only_on_one(self) -> None:
        request = TestRequest(
            id="penalised",
            profile=TestProfile(2, 6),
            dice_modifiers=(DiceModifier("RULE-TEST-PENALTY", -3),),
        )

        failure = resolve_test(request, SequenceRandom([2]))
        success = resolve_test(request, SequenceRandom([1]))

        self.assertEqual(failure.successes, 0)
        self.assertEqual(success.successes, 1)
        self.assertEqual(failure.trace.rolled_dice, 1)
        self.assertTrue(failure.trace.minimum_die_rule_applied)
        self.assertEqual(failure.trace.threshold, 1)

    def test_regular_bonus_dice_are_capped_at_twice_characteristic(self) -> None:
        request = TestRequest(
            id="capped",
            profile=TestProfile(3, 4),
            dice_modifiers=(DiceModifier("RULE-BONUS", 10),),
        )

        result = resolve_test(request, SequenceRandom([10] * 6))

        self.assertEqual(result.trace.rolled_dice, 6)
        self.assertEqual(result.trace.pool_cap, 6)

    def test_explicit_bonus_can_bypass_pool_cap(self) -> None:
        request = TestRequest(
            id="uncapped",
            profile=TestProfile(2, 4),
            dice_modifiers=(
                DiceModifier("RULE-NORMAL-BONUS", 4),
                DiceModifier("RULE-EXPLICIT-EXCEPTION", 2, bypasses_pool_cap=True),
            ),
        )

        result = resolve_test(request, SequenceRandom([10] * 6))

        self.assertEqual(result.trace.rolled_dice, 6)
        self.assertEqual(result.trace.cap_bypassing_dice, 2)

    def test_basic_test_classifies_zero_one_two_and_three_successes(self) -> None:
        expected = (
            (10, 10, 10, BasicOutcome.FAILURE),
            (1, 10, 10, BasicOutcome.MARGINAL_SUCCESS),
            (1, 2, 10, BasicOutcome.SUCCESS),
            (1, 2, 3, BasicOutcome.TOTAL_SUCCESS),
        )
        for first, second, third, outcome in expected:
            with self.subTest(outcome=outcome):
                result = resolve_basic_test(
                    TestRequest(id="basic", profile=TestProfile(3, 5)),
                    SequenceRandom([first, second, third]),
                )
                self.assertIs(result.outcome, outcome)

    def test_grim_rerolls_every_initial_success_exactly_once(self) -> None:
        request = TestRequest(
            id="grim",
            profile=TestProfile(3, 5),
            quality_modifiers=(QualityModifier("RULE-GRIM", TestQuality.GRIM),),
        )

        result = resolve_test(request, SequenceRandom([1, 8, 5, 10, 4]))

        self.assertEqual(result.trace.initial_values, (1, 8, 5))
        self.assertEqual(result.trace.final_values, (10, 8, 4))
        self.assertEqual(tuple(item.index for item in result.trace.rerolls), (0, 2))
        self.assertEqual(result.successes, 1)

    def test_glorious_requires_explicit_decision_and_rerolls_chosen_failures(self) -> None:
        request = TestRequest(
            id="glorious",
            profile=TestProfile(3, 5),
            quality_modifiers=(
                QualityModifier("RULE-GLORIOUS", TestQuality.GLORIOUS),
            ),
        )

        with self.assertRaises(MissingTestDecisionError):
            resolve_test(request, SequenceRandom([1, 8, 9]))

        result = resolve_test(
            request,
            SequenceRandom([1, 8, 9, 2, 10]),
            decisions=RerollAllFailures(),
        )
        self.assertEqual(result.trace.final_values, (1, 2, 10))
        self.assertEqual(result.successes, 2)

    def test_grim_and_glorious_cancel_even_with_repeated_sources(self) -> None:
        request = TestRequest(
            id="cancelled",
            profile=TestProfile(2, 5),
            quality_modifiers=(
                QualityModifier("RULE-GRIM-1", TestQuality.GRIM),
                QualityModifier("RULE-GRIM-2", TestQuality.GRIM),
                QualityModifier("RULE-GLORIOUS", TestQuality.GLORIOUS),
            ),
        )

        result = resolve_test(request, SequenceRandom([1, 10]))

        self.assertIs(result.trace.quality, TestQuality.NORMAL)
        self.assertEqual(result.trace.rerolls, ())

    def test_glorious_provider_cannot_reroll_a_success(self) -> None:
        class InvalidDecision:
            def choose_glorious_rerolls(self, **_: object) -> tuple[int, ...]:
                return (0,)

        request = TestRequest(
            id="invalid-decision",
            profile=TestProfile(2, 5),
            quality_modifiers=(
                QualityModifier("RULE-GLORIOUS", TestQuality.GLORIOUS),
            ),
        )

        with self.assertRaises(InvalidTestDecisionError):
            resolve_test(
                request,
                SequenceRandom([1, 10]),
                decisions=InvalidDecision(),
            )

    def test_fixed_success_modifiers_apply_after_rolled_successes_and_not_below_zero(self) -> None:
        request = TestRequest(
            id="fixed-successes",
            profile=TestProfile(2, 5),
            success_modifiers=(
                SuccessModifier("RULE-FREE-SUCCESS", 2),
                SuccessModifier("RULE-REDUCE-SUCCESS", -5),
            ),
        )

        result = resolve_test(request, SequenceRandom([1, 2]))

        self.assertEqual(result.trace.rolled_successes, 2)
        self.assertEqual(result.trace.success_delta, -3)
        self.assertEqual(result.successes, 0)
        self.assertEqual(
            result.trace.applied_rule_ids,
            ("RULE-FREE-SUCCESS", "RULE-REDUCE-SUCCESS"),
        )


if __name__ == "__main__":
    unittest.main()
