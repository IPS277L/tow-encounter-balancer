from __future__ import annotations

import unittest

from tests.helpers import SequenceRandom
from towr.domain.magic_models import (
    MiscastPoolIncreaseRequest,
    MiscastPoolIncreaseSourceKind,
    MiscastPoolOutcome,
    MiscastPoolResolutionRequest,
    WizardMagicState,
)
from towr.domain.test_models import (
    QualityModifier,
    TestProfile,
    TestQuality,
    TestRequest,
)
from towr.rules.miscast_pool_resolution import (
    MISCAST_POOL_RULE_ID,
    RULE_OF_NINE_RULE_ID,
    resolve_miscast_pool_increase,
    rule_of_nine_reroll_lock,
)
from towr.rules.test_resolution import (
    InvalidTestDecisionError,
    RerollAllFailures,
    resolve_test,
)


TRIGGER_RULE_ID = "RULE-NPC-024:mother-knows-best"


def increase(*, amount: int = 1) -> MiscastPoolIncreaseRequest:
    return MiscastPoolIncreaseRequest(
        resolution_id="mother-knows-best:opposition",
        target_id="troll-hag",
        amount=amount,
        source_kind=MiscastPoolIncreaseSourceKind.TEST,
        source_id="troll-hag:willpower",
        trigger_rule_id=TRIGGER_RULE_ID,
        rule_id=RULE_OF_NINE_RULE_ID,
    )


def request(
    *,
    current: int,
    amount: int = 1,
    level: int = 2,
) -> MiscastPoolResolutionRequest:
    return MiscastPoolResolutionRequest(
        id="troll-hag:miscast-pool",
        source=increase(amount=amount),
        state=WizardMagicState(miscast_dice=current),
        wizard_level=level,
        rule_id=MISCAST_POOL_RULE_ID,
    )


class K1MiscastPoolResolutionTests(unittest.TestCase):
    def test_pool_equal_to_wizard_level_does_not_trigger_miscast(self) -> None:
        result = resolve_miscast_pool_increase(
            request(current=1, amount=1, level=2)
        )

        self.assertIs(result.outcome, MiscastPoolOutcome.ACCUMULATED)
        self.assertEqual(result.previous_miscast_dice, 1)
        self.assertEqual(result.dice_added, 1)
        self.assertEqual(result.state.miscast_dice, 2)
        self.assertIsNone(result.roll_request)

    def test_exceeding_level_requests_roll_of_entire_retained_pool(self) -> None:
        result = resolve_miscast_pool_increase(
            request(current=2, amount=1, level=2)
        )

        self.assertIs(result.outcome, MiscastPoolOutcome.MISCAST_TRIGGERED)
        self.assertEqual(result.state.miscast_dice, 3)
        self.assertIsNotNone(result.roll_request)
        assert result.roll_request is not None
        self.assertEqual(result.roll_request.dice_count, 3)
        self.assertEqual(result.roll_request.target_id, "troll-hag")
        self.assertEqual(
            result.roll_request.source_resolution_id,
            "mother-knows-best:opposition",
        )

    def test_multi_die_increase_preserves_source_rule_trace(self) -> None:
        result = resolve_miscast_pool_increase(
            request(current=1, amount=2, level=2)
        )

        self.assertEqual(result.state.miscast_dice, 3)
        self.assertEqual(result.dice_added, 2)
        self.assertEqual(
            result.applied_rule_ids,
            (TRIGGER_RULE_ID, RULE_OF_NINE_RULE_ID, MISCAST_POOL_RULE_ID),
        )

    def test_more_dice_cannot_be_added_while_miscast_is_pending(self) -> None:
        with self.assertRaises(ValueError):
            request(current=3, amount=1, level=2)

    def test_magic_state_and_wizard_level_are_validated(self) -> None:
        with self.assertRaises(ValueError):
            WizardMagicState(miscast_dice=-1)
        with self.assertRaises(ValueError):
            request(current=0, level=0)

    def test_rule_of_nine_excludes_nine_from_glorious_choices(self) -> None:
        result = resolve_test(
            TestRequest(
                id="casting",
                profile=TestProfile(2, 5),
                quality_modifiers=(
                    QualityModifier("RULE-TEST:glorious", TestQuality.GLORIOUS),
                ),
                reroll_locks=(rule_of_nine_reroll_lock(),),
            ),
            SequenceRandom([9, 10, 2]),
            decisions=RerollAllFailures(),
        )

        self.assertEqual(result.trace.initial_values, (9, 10))
        self.assertEqual(result.trace.final_values, (9, 2))
        self.assertEqual(
            tuple(item.original for item in result.trace.rerolls),
            (10,),
        )
        self.assertIn(RULE_OF_NINE_RULE_ID, result.trace.applied_rule_ids)

    def test_rule_of_nine_also_protects_a_grim_success(self) -> None:
        result = resolve_test(
            TestRequest(
                id="unusually-high-threshold-casting",
                profile=TestProfile(2, 10),
                quality_modifiers=(
                    QualityModifier("RULE-TEST:grim", TestQuality.GRIM),
                ),
                reroll_locks=(rule_of_nine_reroll_lock(),),
            ),
            SequenceRandom([9, 8, 10]),
        )

        self.assertEqual(result.trace.final_values, (9, 10))
        self.assertEqual(
            tuple(item.original for item in result.trace.rerolls),
            (8,),
        )

    def test_decision_provider_cannot_select_a_locked_nine(self) -> None:
        class SelectFirstDie:
            def choose_glorious_rerolls(self, **_: object) -> tuple[int, ...]:
                return (0,)

        with self.assertRaises(InvalidTestDecisionError):
            resolve_test(
                TestRequest(
                    id="casting",
                    profile=TestProfile(2, 5),
                    quality_modifiers=(
                        QualityModifier(
                            "RULE-TEST:glorious",
                            TestQuality.GLORIOUS,
                        ),
                    ),
                    reroll_locks=(rule_of_nine_reroll_lock(),),
                ),
                SequenceRandom([9, 10]),
                decisions=SelectFirstDie(),
            )


if __name__ == "__main__":
    unittest.main()
