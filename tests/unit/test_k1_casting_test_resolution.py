from __future__ import annotations

import unittest

from tests.helpers import SequenceRandom
from towr.domain.magic_models import (
    CastingTestRequest,
    MiscastPoolIncreaseSourceKind,
    MiscastPoolOutcome,
    MiscastPoolResolutionRequest,
    WizardMagicState,
)
from towr.domain.test_models import (
    QualityModifier,
    RerollLock,
    TestProfile,
    TestQuality,
    TestRequest,
)
from towr.rules.casting_test_resolution import (
    CASTING_TEST_RULE_ID,
    resolve_casting_test,
)
from towr.rules.miscast_pool_resolution import (
    MISCAST_POOL_RULE_ID,
    RULE_OF_NINE_RULE_ID,
    resolve_miscast_pool_increase,
)
from towr.rules.test_resolution import RerollAllFailures


def casting_request(
    *,
    state: WizardMagicState = WizardMagicState(),
    quality: TestQuality = TestQuality.NORMAL,
    lore_id: str = "lore:beasts",
) -> CastingTestRequest:
    quality_modifiers = (
        (QualityModifier("RULE-TEST:quality", quality),)
        if quality is not TestQuality.NORMAL
        else ()
    )
    return CastingTestRequest(
        id="wizard:casting-step",
        caster_id="wizard",
        lore_id=lore_id,
        test=TestRequest(
            id="wizard:willpower",
            profile=TestProfile(3, 5),
            quality_modifiers=quality_modifiers,
        ),
        state=state,
    )


class K1CastingTestResolutionTests(unittest.TestCase):
    def test_accumulates_successes_and_preserves_latest_roll_for_potency(self) -> None:
        state = WizardMagicState(
            casting_successes=2,
            casting_lore_id="lore:beasts",
            latest_casting_roll_successes=2,
        )

        result = resolve_casting_test(
            casting_request(state=state),
            SequenceRandom([1, 2, 10]),
        )

        self.assertEqual(result.previous_casting_successes, 2)
        self.assertEqual(result.latest_roll_successes, 2)
        self.assertEqual(result.state.casting_successes, 4)
        self.assertEqual(result.state.latest_casting_roll_successes, 2)
        self.assertEqual(result.state.casting_lore_id, "lore:beasts")
        self.assertEqual(result.miscast_dice_added, 0)
        self.assertEqual(result.follow_ups, ())

    def test_rule_of_nine_locks_initial_nine_and_counts_final_nines(self) -> None:
        result = resolve_casting_test(
            casting_request(quality=TestQuality.GLORIOUS),
            SequenceRandom([9, 10, 8, 2, 9]),
            decisions=RerollAllFailures(),
        )

        self.assertEqual(result.test.trace.initial_values, (9, 10, 8))
        self.assertEqual(result.test.trace.final_values, (9, 2, 9))
        self.assertEqual(
            tuple(item.original for item in result.test.trace.rerolls),
            (10, 8),
        )
        self.assertEqual(result.latest_roll_successes, 1)
        self.assertEqual(result.miscast_dice_added, 2)
        self.assertEqual(len(result.follow_ups), 1)
        increase = result.follow_ups[0]
        self.assertEqual(increase.amount, 2)
        self.assertEqual(increase.target_id, "wizard")
        self.assertEqual(increase.source_id, "wizard:willpower")
        self.assertIs(
            increase.source_kind,
            MiscastPoolIncreaseSourceKind.TEST,
        )
        self.assertEqual(increase.trigger_rule_id, CASTING_TEST_RULE_ID)
        self.assertEqual(increase.rule_id, RULE_OF_NINE_RULE_ID)
        self.assertIn(
            RULE_OF_NINE_RULE_ID,
            result.test.trace.applied_rule_ids,
        )

    def test_zero_successes_still_starts_casting_for_declared_lore(self) -> None:
        result = resolve_casting_test(
            casting_request(),
            SequenceRandom([10, 10, 10]),
        )

        self.assertEqual(result.state.casting_successes, 0)
        self.assertEqual(result.state.latest_casting_roll_successes, 0)
        self.assertEqual(result.state.casting_lore_id, "lore:beasts")

    def test_follow_up_connects_to_existing_miscast_pool_lifecycle(self) -> None:
        casting = resolve_casting_test(
            casting_request(state=WizardMagicState(miscast_dice=1)),
            SequenceRandom([9, 9, 1]),
        )

        pool = resolve_miscast_pool_increase(
            MiscastPoolResolutionRequest(
                id="wizard:miscast-pool",
                source=casting.follow_ups[0],
                state=casting.state,
                wizard_level=2,
                rule_id=MISCAST_POOL_RULE_ID,
            )
        )

        self.assertIs(pool.outcome, MiscastPoolOutcome.MISCAST_TRIGGERED)
        self.assertEqual(pool.state.miscast_dice, 3)
        self.assertIsNotNone(pool.roll_request)

    def test_active_casting_cannot_switch_lore(self) -> None:
        state = WizardMagicState(
            casting_lore_id="lore:beasts",
        )

        with self.assertRaises(ValueError):
            casting_request(state=state, lore_id="lore:fire")

    def test_casting_request_owns_the_nine_reroll_lock(self) -> None:
        with self.assertRaises(ValueError):
            CastingTestRequest(
                id="wizard:casting-step",
                caster_id="wizard",
                lore_id="lore:beasts",
                test=TestRequest(
                    id="wizard:willpower",
                    profile=TestProfile(3, 5),
                    reroll_locks=(RerollLock("OTHER-RULE", 9),),
                ),
                state=WizardMagicState(),
            )

    def test_magic_state_rejects_successes_without_lore_or_invalid_latest_roll(self) -> None:
        with self.assertRaises(ValueError):
            WizardMagicState(casting_successes=1)
        with self.assertRaises(ValueError):
            WizardMagicState(
                casting_successes=1,
                casting_lore_id="lore:beasts",
                latest_casting_roll_successes=2,
            )


if __name__ == "__main__":
    unittest.main()
