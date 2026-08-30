from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.drained_test_models import DrainedTestPreparationRequest
from towr.domain.lucky_models import (
    LUCKY_RULE_ID,
    LuckyGamblingTestPreparationRequest,
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
from towr.rules.lucky_resolution import prepare_lucky_gambling_test
from towr.rules.test_resolution import RerollAllFailures, resolve_test


def gambling_request(
    *,
    test: TestRequest | None = None,
    rule_id: str = LUCKY_RULE_ID,
) -> LuckyGamblingTestPreparationRequest:
    return LuckyGamblingTestPreparationRequest(
        id="lucky:gambling:prepare",
        actor_id="hero",
        game_id="game:brass-dice:1",
        test=test or TestRequest("hero:gambling", TestProfile(2, 5)),
        actor_talent_rule_ids=(LUCKY_RULE_ID,),
        rule_id=rule_id,
    )


class K1LuckyGamblingResolutionTests(unittest.TestCase):
    def test_lucky_makes_game_of_chance_glorious_without_spending_fate(
        self,
    ) -> None:
        source = gambling_request()

        prepared = prepare_lucky_gambling_test(source)

        self.assertEqual(prepared.proof.actor_id, source.actor_id)
        self.assertEqual(prepared.proof.test_id, source.test.id)
        self.assertEqual(prepared.proof.game_id, source.game_id)
        self.assertEqual(prepared.proof.source_request_id, source.id)
        self.assertEqual(len(prepared.test.quality_modifiers), 1)
        modifier = prepared.test.quality_modifiers[0]
        self.assertEqual(modifier.rule_id, LUCKY_RULE_ID)
        self.assertIs(modifier.quality, TestQuality.GLORIOUS)
        self.assertIs(modifier.source, QualityModifierSource.TALENT)
        self.assertEqual(modifier.source_id, prepared.proof.id)
        self.assertEqual(prepared.applied_rule_ids, (LUCKY_RULE_ID,))
        self.assertEqual(source.test.quality_modifiers, ())

        rolled = resolve_test(
            prepared.test,
            SequenceRandom([9, 2, 1]),
            decisions=RerollAllFailures(),
        )
        self.assertIs(rolled.trace.quality, TestQuality.GLORIOUS)
        self.assertEqual(rolled.trace.initial_values, (9, 2))
        self.assertEqual(rolled.trace.final_values, (1, 2))
        self.assertEqual(rolled.successes, 2)
        self.assertIn(LUCKY_RULE_ID, rolled.trace.applied_rule_ids)

    def test_lucky_glorious_cancels_grim_by_the_common_test_rule(self) -> None:
        source_test = TestRequest(
            "hero:grim-gambling",
            TestProfile(2, 5),
            quality_modifiers=(
                QualityModifier("RULE-GRIM:test", TestQuality.GRIM),
            ),
        )
        prepared = prepare_lucky_gambling_test(
            gambling_request(test=source_test)
        )

        rolled = resolve_test(
            prepared.test,
            SequenceRandom([1, 9]),
        )

        self.assertIs(rolled.trace.quality, TestQuality.NORMAL)
        self.assertEqual(rolled.trace.rerolls, ())
        self.assertEqual(rolled.successes, 1)

    def test_drained_removes_lucky_but_preserves_its_provenance(self) -> None:
        prepared = prepare_lucky_gambling_test(gambling_request())
        drained = prepare_drained_test(
            DrainedTestPreparationRequest(
                id="drained:lucky-gambling",
                actor_id="hero",
                conditions=ConditionState({Condition.DRAINED}),
                test=prepared.test,
                lucky_gambling_proofs=(prepared.proof,),
            )
        )

        self.assertTrue(drained.drained_active)
        self.assertEqual(
            drained.removed_quality_modifiers,
            prepared.test.quality_modifiers,
        )
        self.assertEqual(drained.test.quality_modifiers, ())
        self.assertIn(LUCKY_RULE_ID, drained.applied_rule_ids)

        unaffected = prepare_drained_test(
            DrainedTestPreparationRequest(
                id="not-drained:lucky-gambling",
                actor_id="hero",
                conditions=ConditionState(),
                test=prepared.test,
                lucky_gambling_proofs=(prepared.proof,),
            )
        )
        self.assertEqual(unaffected.test, prepared.test)

    def test_lucky_proof_is_required_and_bound_to_actor_test_and_source(
        self,
    ) -> None:
        prepared = prepare_lucky_gambling_test(gambling_request())
        invalid_proofs = (
            (),
            (replace(prepared.proof, id="lucky:other-proof"),),
            (replace(prepared.proof, actor_id="other"),),
            (replace(prepared.proof, test_id="other:test"),),
        )
        for proofs in invalid_proofs:
            with self.subTest(proofs=proofs):
                with self.assertRaises(ValueError):
                    DrainedTestPreparationRequest(
                        id="drained:invalid-lucky-proof",
                        actor_id="hero",
                        conditions=ConditionState({Condition.DRAINED}),
                        test=prepared.test,
                        lucky_gambling_proofs=proofs,
                    )

        with self.assertRaisesRegex(ValueError, "unique"):
            TestRequest(
                "hero:duplicate-bound-source",
                TestProfile(2, 5),
                quality_modifiers=(
                    prepared.test.quality_modifiers[0],
                    replace(
                        prepared.test.quality_modifiers[0],
                        rule_id="RULE-TALENT:other-glorious",
                    ),
                ),
            )

    def test_context_talent_ordering_and_result_provenance_are_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "Lucky Talent"):
            replace(
                gambling_request(),
                actor_talent_rule_ids=("RULE-TALENT:other",),
            )
        with self.assertRaisesRegex(ValueError, "already prepared"):
            gambling_request(
                test=prepare_lucky_gambling_test(
                    gambling_request()
                ).test,
            )

        fate_test = TestRequest(
            "hero:fate-before-lucky",
            TestProfile(2, 5),
            quality_modifiers=(
                QualityModifier(
                    FATE_GLORIOUS_RULE_ID,
                    TestQuality.GLORIOUS,
                    source=QualityModifierSource.FATE,
                    source_id="fate:proof",
                ),
            ),
        )
        with self.assertRaisesRegex(ValueError, "precede any Fate"):
            gambling_request(test=fate_test)

        unknown = gambling_request(rule_id="RULE-UNKNOWN")
        with self.assertRaisesRegex(ValueError, "unknown rule"):
            prepare_lucky_gambling_test(unknown)
        result = prepare_lucky_gambling_test(
            replace(unknown, rule_id=LUCKY_RULE_ID)
        )
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, test=result.source_request.test)


if __name__ == "__main__":
    unittest.main()
