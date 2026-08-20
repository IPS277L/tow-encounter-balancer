from __future__ import annotations

import unittest

from tests.helpers import SequenceRandom
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.magic_models import (
    MiscastPoolIncreaseSourceKind,
    NpcWizardCastingOppositionOutcome,
    NpcWizardCastingOppositionRequest,
)
from towr.domain.test_models import (
    DiceModifier,
    OpposedSide,
    OpposedTestRequest,
    QualityModifier,
    TestProfile,
    TestQuality,
    TestRequest,
    TieBreak,
)
from towr.rules.npc_wizard_casting_opposition_resolution import (
    InvalidCastingOppositionResultError,
    MissingCastingOppositionResultError,
    RULE_OF_NINE_RULE_ID,
    resolve_npc_wizard_casting_opposition,
)
from towr.rules.opposed_test import resolve_opposed_test
from towr.rules.test_resolution import RerollAllFailures, resolve_test
from towr.rules.troll_hag import (
    MOTHER_KNOWS_BEST_RULE_ID,
    TROLL_HAG_WIZARD_LEVEL,
    mother_knows_best_casting_modifier,
)


CASTING_TEST_ID = "enemy:casting"
WILLPOWER_TEST_ID = "troll-hag:willpower"


def completed_opposition(
    values: list[int],
    *,
    reactor_quality: TestQuality = TestQuality.NORMAL,
    decisions=None,
):
    quality_modifiers = (
        (
            QualityModifier(
                "RULE-TEST:reactor-quality",
                reactor_quality,
            ),
        )
        if reactor_quality is not TestQuality.NORMAL
        else ()
    )
    return resolve_opposed_test(
        OpposedTestRequest(
            id="casting:opposition",
            initiator=TestRequest(
                id=CASTING_TEST_ID,
                profile=TestProfile(2, 5),
            ),
            opponent=TestRequest(
                id=WILLPOWER_TEST_ID,
                profile=TestProfile(3, 5),
                quality_modifiers=quality_modifiers,
            ),
            tie_break=TieBreak(
                "RULE-TEST-006:casting-initiator",
                OpposedSide.INITIATOR,
            ),
        ),
        SequenceRandom(values),
        decisions=decisions,
    )


def opposition_request(
    *,
    in_range: bool = True,
    already_used: bool = False,
    opposition=None,
) -> NpcWizardCastingOppositionRequest:
    return NpcWizardCastingOppositionRequest(
        id="mother-knows-best:opposition",
        caster_id="enemy-wizard",
        reactor_id="troll-hag",
        opposed_test_id="casting:opposition",
        casting_test_id=CASTING_TEST_ID,
        reactor_willpower_test_id=WILLPOWER_TEST_ID,
        caster_in_long_range=in_range,
        has_opposed_casting_this_round=already_used,
        opposition=opposition,
        rule_id=MOTHER_KNOWS_BEST_RULE_ID,
    )


class K1MotherKnowsBestTests(unittest.TestCase):
    def test_profile_level_and_zero_wound_casting_bonus_match_book(self) -> None:
        self.assertEqual(TROLL_HAG_WIZARD_LEVEL, 2)
        modifier = mother_knows_best_casting_modifier(
            ProfileInjuryState(wounds=0, wound_limit=6)
        )

        self.assertEqual(
            modifier,
            DiceModifier(MOTHER_KNOWS_BEST_RULE_ID, 1),
        )
        self.assertFalse(modifier.bypasses_pool_cap)
        self.assertIsNone(
            mother_knows_best_casting_modifier(
                ProfileInjuryState(wounds=1, wound_limit=6)
            )
        )

    def test_casting_bonus_uses_the_common_dice_modifier_pipeline(self) -> None:
        modifier = mother_knows_best_casting_modifier(
            ProfileInjuryState(wounds=0, wound_limit=6)
        )
        assert modifier is not None

        result = resolve_test(
            TestRequest(
                id="troll-hag:casting",
                profile=TestProfile(3, 5),
                dice_modifiers=(modifier,),
            ),
            SequenceRandom([10, 10, 10, 10]),
        )

        self.assertEqual(result.trace.rolled_dice, 4)
        self.assertEqual(
            result.trace.applied_rule_ids,
            (MOTHER_KNOWS_BEST_RULE_ID,),
        )

    def test_reactor_nines_add_to_own_pool_regardless_of_winner(self) -> None:
        opposition = completed_opposition([1, 2, 9, 10, 10])
        self.assertIs(opposition.winner, OpposedSide.INITIATOR)

        result = resolve_npc_wizard_casting_opposition(
            opposition_request(opposition=opposition)
        )

        self.assertIs(result.outcome, NpcWizardCastingOppositionOutcome.RESOLVED)
        self.assertTrue(result.opposition_used_this_round)
        self.assertEqual(result.miscast_dice_added, 1)
        self.assertEqual(len(result.follow_ups), 1)
        increase = result.follow_ups[0]
        self.assertEqual(increase.target_id, "troll-hag")
        self.assertEqual(increase.amount, 1)
        self.assertEqual(increase.source_id, WILLPOWER_TEST_ID)
        self.assertIs(
            increase.source_kind,
            MiscastPoolIncreaseSourceKind.TEST,
        )
        self.assertEqual(increase.trigger_rule_id, MOTHER_KNOWS_BEST_RULE_ID)
        self.assertEqual(increase.rule_id, RULE_OF_NINE_RULE_ID)
        self.assertEqual(
            result.applied_rule_ids,
            (MOTHER_KNOWS_BEST_RULE_ID, RULE_OF_NINE_RULE_ID),
        )

    def test_no_nines_marks_opposition_used_without_follow_up(self) -> None:
        opposition = completed_opposition([1, 10, 1, 2, 10])

        result = resolve_npc_wizard_casting_opposition(
            opposition_request(opposition=opposition)
        )

        self.assertTrue(result.opposition_used_this_round)
        self.assertEqual(result.miscast_dice_added, 0)
        self.assertEqual(result.follow_ups, ())

    def test_nine_created_by_a_legal_reroll_is_counted(self) -> None:
        opposition = completed_opposition(
            [1, 10, 10, 1, 2, 9],
            reactor_quality=TestQuality.GLORIOUS,
            decisions=RerollAllFailures(),
        )

        result = resolve_npc_wizard_casting_opposition(
            opposition_request(opposition=opposition)
        )

        self.assertEqual(result.miscast_dice_added, 1)
        self.assertEqual(result.follow_ups[0].amount, 1)

    def test_range_and_round_budget_close_without_completed_test(self) -> None:
        cases = (
            (
                opposition_request(in_range=False),
                NpcWizardCastingOppositionOutcome.UNAVAILABLE_OUT_OF_RANGE,
                False,
            ),
            (
                opposition_request(already_used=True),
                NpcWizardCastingOppositionOutcome.UNAVAILABLE_ALREADY_USED,
                True,
            ),
        )

        for request, outcome, used in cases:
            with self.subTest(outcome=outcome):
                result = resolve_npc_wizard_casting_opposition(request)
                self.assertIs(result.outcome, outcome)
                self.assertIs(result.opposition_used_this_round, used)
                self.assertEqual(result.follow_ups, ())

        completed = completed_opposition([1, 10, 1, 10, 10])
        with self.assertRaises(InvalidCastingOppositionResultError):
            resolve_npc_wizard_casting_opposition(
                opposition_request(in_range=False, opposition=completed)
            )

    def test_available_declared_opposition_requires_matching_result(self) -> None:
        with self.assertRaises(MissingCastingOppositionResultError):
            resolve_npc_wizard_casting_opposition(opposition_request())

        opposition = completed_opposition([1, 10, 1, 10, 10])
        mismatched = NpcWizardCastingOppositionRequest(
            id="mother-knows-best:mismatch",
            caster_id="enemy-wizard",
            reactor_id="troll-hag",
            opposed_test_id="casting:opposition",
            casting_test_id="another:casting",
            reactor_willpower_test_id=WILLPOWER_TEST_ID,
            caster_in_long_range=True,
            has_opposed_casting_this_round=False,
            opposition=opposition,
            rule_id=MOTHER_KNOWS_BEST_RULE_ID,
        )
        with self.assertRaises(InvalidCastingOppositionResultError):
            resolve_npc_wizard_casting_opposition(mismatched)

    def test_rule_of_nine_rejects_a_trace_that_rerolled_nine(self) -> None:
        opposition = completed_opposition(
            [1, 10, 9, 10, 2, 3, 4],
            reactor_quality=TestQuality.GLORIOUS,
            decisions=RerollAllFailures(),
        )

        with self.assertRaises(InvalidCastingOppositionResultError):
            resolve_npc_wizard_casting_opposition(
                opposition_request(opposition=opposition)
            )


if __name__ == "__main__":
    unittest.main()
