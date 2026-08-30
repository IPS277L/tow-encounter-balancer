from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.drained_test_models import DrainedTestPreparationRequest
from towr.domain.fate_models import (
    FATE_SESSION_RULE_ID,
    FateGloriousSpendRequest,
    FateSessionState,
    FateSpendKind,
    FateSpendRecord,
)
from towr.domain.test_models import (
    FATE_GLORIOUS_RULE_ID,
    QualityModifier,
    QualityModifierSource,
    TestProfile,
    TestQuality,
    TestRequest,
)
from towr.rules.drained_test_resolution import prepare_drained_test
from towr.rules.fate_resolution import spend_fate_for_glorious
from towr.rules.test_resolution import (
    RerollAllFailures,
    complete_test,
    resolve_test,
    roll_test_initial,
)


def fate_state(*, rating: int = 2) -> FateSessionState:
    return FateSessionState(
        session_id="session:1",
        actor_id="hero",
        rating=rating,
        session_spend_limit=rating,
    )


def grim_test(test_id: str = "hero:test") -> TestRequest:
    return TestRequest(
        id=test_id,
        profile=TestProfile(2, 5),
        quality_modifiers=(
            QualityModifier("RULE-GRIM", TestQuality.GRIM),
        ),
    )


class K1FateSessionTests(unittest.TestCase):
    def test_session_tracks_permanent_rating_and_remaining_spends(self) -> None:
        state = fate_state(rating=2)

        self.assertEqual(state.rating, 2)
        self.assertEqual(state.session_spend_limit, 2)
        self.assertEqual(state.remaining_spends, 2)
        self.assertEqual(state.spends, ())
        self.assertEqual(state.rule_id, FATE_SESSION_RULE_ID)

        post_burn_snapshot = FateSessionState(
            session_id="session:1",
            actor_id="hero",
            rating=0,
            session_spend_limit=1,
        )
        self.assertEqual(post_burn_snapshot.remaining_spends, 1)

    def test_session_rejects_invalid_or_forged_spend_history(self) -> None:
        spend = FateSpendRecord(
            id="spend:1",
            session_id="session:1",
            actor_id="hero",
            kind=FateSpendKind.GLORIOUS_TEST,
            subject_id="hero:test",
            rule_id=FATE_GLORIOUS_RULE_ID,
        )
        with self.assertRaises(ValueError):
            fate_state(rating=-1)
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            FateSessionState("session:1", "hero", 0, 0, spends=(spend,))
        with self.assertRaisesRegex(ValueError, "IDs must be unique"):
            FateSessionState("session:1", "hero", 2, 2, spends=(spend, spend))
        with self.assertRaisesRegex(ValueError, "same Test"):
            FateSessionState(
                "session:1",
                "hero",
                2,
                2,
                spends=(spend, replace(spend, id="spend:2")),
            )
        with self.assertRaisesRegex(ValueError, "another session or actor"):
            FateSessionState(
                "session:1",
                "other",
                1,
                1,
                spends=(spend,),
            )
        with self.assertRaisesRegex(ValueError, "another session or actor"):
            FateSessionState(
                "session:2",
                "hero",
                1,
                1,
                spends=(spend,),
            )
        with self.assertRaisesRegex(ValueError, "canonical rule"):
            replace(spend, rule_id="RULE-FORGED")


class K1FateGloriousSpendTests(unittest.TestCase):
    def test_spend_after_initial_roll_rerolls_without_rolling_pool_again(self) -> None:
        source_test = TestRequest("hero:after-roll", TestProfile(2, 5))
        initial = roll_test_initial(source_test, SequenceRandom([1, 9]))
        spent = spend_fate_for_glorious(
            FateGloriousSpendRequest(
                id="spend:after-roll",
                state=fate_state(),
                test=source_test,
                initial_roll=initial,
            )
        )

        result = complete_test(
            initial,
            SequenceRandom([2]),
            request=spent.test,
            decisions=RerollAllFailures(),
        )

        self.assertEqual(result.trace.initial_values, (1, 9))
        self.assertEqual(result.trace.final_values, (1, 2))
        self.assertEqual(result.successes, 2)
        self.assertEqual(spent.state.remaining_spends, 1)

    def test_spend_after_grim_initial_roll_cancels_before_mandatory_rerolls(self) -> None:
        source_test = grim_test("hero:grim-after-roll")
        initial = roll_test_initial(source_test, SequenceRandom([1, 9]))
        spent = spend_fate_for_glorious(
            FateGloriousSpendRequest(
                id="spend:grim-after-roll",
                state=fate_state(),
                test=source_test,
                initial_roll=initial,
            )
        )

        result = complete_test(
            initial,
            SequenceRandom([]),
            request=spent.test,
        )

        self.assertIs(result.trace.quality, TestQuality.NORMAL)
        self.assertEqual(result.trace.rerolls, ())
        self.assertEqual(result.trace.final_values, (1, 9))

    def test_after_roll_spend_must_reference_the_exact_source_test(self) -> None:
        source_test = TestRequest("hero:source", TestProfile(2, 5))
        initial = roll_test_initial(source_test, SequenceRandom([1, 9]))

        with self.assertRaisesRegex(ValueError, "another Test request"):
            FateGloriousSpendRequest(
                id="spend:mismatch",
                state=fate_state(),
                test=replace(source_test, id="hero:other"),
                initial_roll=initial,
            )

    def test_spend_updates_state_and_prepares_test_with_bound_proof(self) -> None:
        source_test = grim_test()
        result = spend_fate_for_glorious(
            FateGloriousSpendRequest(
                id="spend:hero:test",
                state=fate_state(),
                test=source_test,
            )
        )

        self.assertEqual(result.previous_state.remaining_spends, 2)
        self.assertEqual(result.state.remaining_spends, 1)
        self.assertEqual(result.state.spends, (result.spend,))
        self.assertIs(result.spend.kind, FateSpendKind.GLORIOUS_TEST)
        self.assertEqual(result.spend.subject_id, source_test.id)
        self.assertEqual(result.proof.session_id, "session:1")
        self.assertEqual(result.proof.actor_id, "hero")
        self.assertEqual(result.proof.test_id, source_test.id)
        self.assertEqual(result.proof.source_spend_id, result.spend.id)
        self.assertEqual(
            result.test.quality_modifiers[:-1],
            source_test.quality_modifiers,
        )
        modifier = result.test.quality_modifiers[-1]
        self.assertIs(modifier.source, QualityModifierSource.FATE)
        self.assertEqual(modifier.source_id, result.proof.id)
        self.assertEqual(
            result.applied_rule_ids,
            (FATE_SESSION_RULE_ID, FATE_GLORIOUS_RULE_ID),
        )
        self.assertEqual(source_test, grim_test())

        rolled = resolve_test(result.test, SequenceRandom([1, 9]))
        self.assertIs(rolled.trace.quality, TestQuality.NORMAL)
        self.assertEqual(rolled.trace.rerolls, ())

    def test_two_different_tests_consume_rating_and_third_is_rejected(self) -> None:
        first = spend_fate_for_glorious(
            FateGloriousSpendRequest(
                id="spend:1",
                state=fate_state(),
                test=TestRequest("hero:test:1", TestProfile(2, 5)),
            )
        )
        second = spend_fate_for_glorious(
            FateGloriousSpendRequest(
                id="spend:2",
                state=first.state,
                test=TestRequest("hero:test:2", TestProfile(2, 5)),
            )
        )

        self.assertEqual(second.state.remaining_spends, 0)
        self.assertEqual(
            tuple(item.id for item in second.state.spends),
            ("spend:1", "spend:2"),
        )
        with self.assertRaisesRegex(ValueError, "no Fate spends remain"):
            FateGloriousSpendRequest(
                id="spend:3",
                state=second.state,
                test=TestRequest("hero:test:3", TestProfile(2, 5)),
            )

    def test_original_test_cannot_hide_a_previous_spend(self) -> None:
        source_test = TestRequest("hero:test", TestProfile(2, 5))
        first = spend_fate_for_glorious(
            FateGloriousSpendRequest(
                id="spend:1",
                state=fate_state(),
                test=source_test,
            )
        )

        with self.assertRaisesRegex(ValueError, "already spent on this Test"):
            FateGloriousSpendRequest(
                id="spend:2",
                state=first.state,
                test=source_test,
            )
        with self.assertRaisesRegex(ValueError, "already Glorious"):
            FateGloriousSpendRequest(
                id="spend:2",
                state=fate_state(),
                test=first.test,
            )

    def test_book_glorious_source_blocks_fate_but_grim_does_not(self) -> None:
        glorious = TestRequest(
            "hero:glorious",
            TestProfile(2, 5),
            quality_modifiers=(
                QualityModifier("RULE-TALENT", TestQuality.GLORIOUS),
            ),
        )
        with self.assertRaisesRegex(ValueError, "already Glorious"):
            FateGloriousSpendRequest(
                id="spend:glorious",
                state=fate_state(),
                test=glorious,
            )

        result = spend_fate_for_glorious(
            FateGloriousSpendRequest(
                id="spend:grim",
                state=fate_state(),
                test=grim_test(),
            )
        )
        self.assertEqual(len(result.test.quality_modifiers), 2)

    def test_produced_fate_glorious_survives_drained(self) -> None:
        spent = spend_fate_for_glorious(
            FateGloriousSpendRequest(
                id="spend:drained",
                state=fate_state(rating=1),
                test=TestRequest("hero:drained-test", TestProfile(2, 5)),
            )
        )
        prepared = prepare_drained_test(
            DrainedTestPreparationRequest(
                id="prepare:drained",
                actor_id="hero",
                conditions=ConditionState({Condition.DRAINED}),
                test=spent.test,
                fate_glorious_proofs=(spent.proof,),
            )
        )

        self.assertEqual(prepared.test, spent.test)
        rolled = resolve_test(
            prepared.test,
            SequenceRandom([1, 9, 2]),
            decisions=RerollAllFailures(),
        )
        self.assertIs(rolled.trace.quality, TestQuality.GLORIOUS)
        self.assertEqual(rolled.successes, 2)

    def test_unknown_rule_and_forged_result_are_rejected(self) -> None:
        request = FateGloriousSpendRequest(
            id="spend:unknown",
            state=fate_state(),
            test=TestRequest("hero:test", TestProfile(2, 5)),
            rule_id="RULE-UNKNOWN",
        )
        with self.assertRaisesRegex(ValueError, "unknown rule"):
            spend_fate_for_glorious(request)

        valid = replace(request, rule_id=FATE_GLORIOUS_RULE_ID)
        result = spend_fate_for_glorious(valid)
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, state=result.previous_state)
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, proof=replace(result.proof, actor_id="other"))
        with self.assertRaisesRegex(ValueError, "trace is incomplete"):
            replace(result, applied_rule_ids=(FATE_GLORIOUS_RULE_ID,))


if __name__ == "__main__":
    unittest.main()
