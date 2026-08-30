from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from tests.unit.test_k1_combat_surgeon_suppression import (
    condition_snapshots,
    registered_source,
)
from towr.domain.combat_surgeon_suppression_models import (
    CombatSurgeonEffectiveEffectsRequest,
)
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.drained_test_models import (
    DRAINED_TEST_PREPARATION_RULE_ID,
    DrainedTestPreparationRequest,
)
from towr.domain.test_models import (
    FATE_GLORIOUS_RULE_ID,
    DiceModifier,
    FateGloriousProof,
    QualityModifier,
    QualityModifierSource,
    RerollLock,
    SuccessModifier,
    TestProfile,
    TestQuality,
    TestRequest,
)
from towr.rules.combat_surgeon_suppression_resolution import (
    resolve_combat_surgeon_effective_effects,
)
from towr.rules.drained_test_resolution import prepare_drained_test
from towr.rules.test_resolution import RerollAllFailures, resolve_test


def bonus_test() -> TestRequest:
    return TestRequest(
        id="hero:test",
        profile=TestProfile(3, 5),
        dice_modifiers=(
            DiceModifier("RULE-BONUS:regular", 2),
            DiceModifier("RULE-PENALTY", -1),
            DiceModifier("RULE-BONUS:bypass", 1, bypasses_pool_cap=True),
        ),
        quality_modifiers=(
            QualityModifier("RULE-GRIM", TestQuality.GRIM),
            QualityModifier("RULE-GLORIOUS", TestQuality.GLORIOUS),
        ),
        success_modifiers=(SuccessModifier("RULE-SUCCESS", 1),),
        reroll_locks=(RerollLock("RULE-LOCK", 1),),
    )


def fate_test() -> tuple[TestRequest, FateGloriousProof]:
    proof = FateGloriousProof(
        id="fate:hero:test",
        session_id="session:1",
        actor_id="hero",
        test_id="hero:fate-test",
        source_spend_id="spend:hero:test",
    )
    test = TestRequest(
        id="hero:fate-test",
        profile=TestProfile(2, 5),
        dice_modifiers=(DiceModifier("RULE-BONUS", 1),),
        quality_modifiers=(
            QualityModifier(
                FATE_GLORIOUS_RULE_ID,
                TestQuality.GLORIOUS,
                source=QualityModifierSource.FATE,
                source_id=proof.id,
            ),
        ),
    )
    return test, proof


def effective_view(*, other_drained_source: bool = False):
    source, registration = registered_source()
    view = resolve_combat_surgeon_effective_effects(
        CombatSurgeonEffectiveEffectsRequest(
            id="battle:1:hero:effective-test-view",
            battle_id="battle:1",
            aggregate=registration.aggregate,
            target_id="hero",
            injury_state=source.state,
            condition_source_snapshots=condition_snapshots(
                drained_has_other_source=other_drained_source,
            ),
        )
    )
    return source, view


class K1DrainedTestPreparationTests(unittest.TestCase):
    def test_drained_removes_bonuses_and_non_fate_glorious(self) -> None:
        source = bonus_test()
        result = prepare_drained_test(
            DrainedTestPreparationRequest(
                id="hero:drained:test",
                actor_id="hero",
                conditions=ConditionState({Condition.DRAINED}),
                test=source,
            )
        )

        self.assertTrue(result.drained_active)
        self.assertEqual(
            tuple(item.rule_id for item in result.removed_bonus_modifiers),
            ("RULE-BONUS:regular", "RULE-BONUS:bypass"),
        )
        self.assertEqual(
            result.removed_quality_modifiers,
            (QualityModifier("RULE-GLORIOUS", TestQuality.GLORIOUS),),
        )
        self.assertEqual(
            result.test.dice_modifiers,
            (DiceModifier("RULE-PENALTY", -1),),
        )
        self.assertEqual(
            result.test.quality_modifiers,
            (QualityModifier("RULE-GRIM", TestQuality.GRIM),),
        )
        self.assertEqual(result.test.success_modifiers, source.success_modifiers)
        self.assertEqual(result.test.reroll_locks, source.reroll_locks)
        self.assertEqual(source, bonus_test())

        rolled = resolve_test(result.test, SequenceRandom([2, 9, 9]))
        self.assertEqual(rolled.trace.rolled_dice, 2)
        self.assertIs(rolled.trace.quality, TestQuality.GRIM)
        self.assertEqual(rolled.trace.regular_dice_delta, -1)
        self.assertEqual(rolled.trace.cap_bypassing_dice, 0)

    def test_character_without_drained_keeps_test_unchanged(self) -> None:
        source = bonus_test()
        result = prepare_drained_test(
            DrainedTestPreparationRequest(
                id="hero:normal:test",
                actor_id="hero",
                conditions=ConditionState({Condition.PRONE}),
                test=source,
            )
        )

        self.assertFalse(result.drained_active)
        self.assertEqual(result.removed_bonus_modifiers, ())
        self.assertEqual(result.removed_quality_modifiers, ())
        self.assertEqual(result.test, source)

    def test_fate_glorious_survives_drained_with_bound_proof(self) -> None:
        test, proof = fate_test()
        result = prepare_drained_test(
            DrainedTestPreparationRequest(
                id="hero:drained:fate-test",
                actor_id="hero",
                conditions=ConditionState({Condition.DRAINED}),
                test=test,
                fate_glorious_proofs=(proof,),
            )
        )

        self.assertEqual(result.removed_bonus_modifiers, test.dice_modifiers)
        self.assertEqual(result.removed_quality_modifiers, ())
        self.assertEqual(result.test.quality_modifiers, test.quality_modifiers)
        self.assertIn(FATE_GLORIOUS_RULE_ID, result.applied_rule_ids)

        rolled = resolve_test(
            result.test,
            SequenceRandom([1, 9, 2]),
            decisions=RerollAllFailures(),
        )
        self.assertIs(rolled.trace.quality, TestQuality.GLORIOUS)
        self.assertEqual(rolled.successes, 2)

    def test_fate_proof_is_required_and_bound_to_actor_and_test(self) -> None:
        test, proof = fate_test()
        invalid_proofs = (
            (),
            (replace(proof, id="fate:other"),),
            (replace(proof, actor_id="other"),),
            (replace(proof, test_id="other:test"),),
        )
        for proofs in invalid_proofs:
            with self.subTest(proofs=proofs):
                with self.assertRaises(ValueError):
                    DrainedTestPreparationRequest(
                        id="hero:invalid:fate-proof",
                        actor_id="hero",
                        conditions=ConditionState({Condition.DRAINED}),
                        test=test,
                        fate_glorious_proofs=proofs,
                    )

    def test_quality_source_rejects_forged_fate_exceptions(self) -> None:
        with self.assertRaisesRegex(ValueError, "only make a Test Glorious"):
            QualityModifier(
                FATE_GLORIOUS_RULE_ID,
                TestQuality.GRIM,
                source=QualityModifierSource.FATE,
                source_id="fate:1",
            )
        with self.assertRaisesRegex(ValueError, "canonical rule"):
            QualityModifier(
                "RULE-FORGED",
                TestQuality.GLORIOUS,
                source=QualityModifierSource.FATE,
                source_id="fate:1",
            )
        with self.assertRaisesRegex(ValueError, "cannot name a source_id"):
            QualityModifier(
                "RULE-GLORIOUS",
                TestQuality.GLORIOUS,
                source_id="forged:source",
            )

        modifier = QualityModifier(
            FATE_GLORIOUS_RULE_ID,
            TestQuality.GLORIOUS,
            source=QualityModifierSource.FATE,
            source_id="fate:1",
        )
        with self.assertRaisesRegex(ValueError, "cannot spend Fate.*twice"):
            TestRequest(
                id="hero:double-fate",
                profile=TestProfile(2, 5),
                quality_modifiers=(modifier, modifier),
            )
        with self.assertRaisesRegex(ValueError, "already Glorious"):
            TestRequest(
                id="hero:already-glorious",
                profile=TestProfile(2, 5),
                quality_modifiers=(
                    QualityModifier("RULE-GLORIOUS", TestQuality.GLORIOUS),
                    modifier,
                ),
            )

    def test_combat_surgeon_view_restores_test_without_mutation(self) -> None:
        source, view = effective_view()
        test = bonus_test()
        result = prepare_drained_test(
            DrainedTestPreparationRequest(
                id="hero:suppressed-drained:test",
                actor_id="hero",
                conditions=source.state.conditions,
                test=test,
                combat_surgeon_effective_effects=view,
            )
        )

        self.assertTrue(source.state.conditions.has(Condition.DRAINED))
        self.assertFalse(view.effective_conditions.has(Condition.DRAINED))
        self.assertFalse(result.drained_active)
        self.assertEqual(result.test, test)
        self.assertEqual(result.removed_bonus_modifiers, ())
        self.assertEqual(result.removed_quality_modifiers, ())
        self.assertIn(view.rule_id, result.applied_rule_ids)

    def test_independent_drained_source_still_applies_restrictions(self) -> None:
        source, view = effective_view(other_drained_source=True)
        result = prepare_drained_test(
            DrainedTestPreparationRequest(
                id="hero:other-drained:test",
                actor_id="hero",
                conditions=source.state.conditions,
                test=bonus_test(),
                combat_surgeon_effective_effects=view,
            )
        )

        self.assertTrue(view.effective_conditions.has(Condition.DRAINED))
        self.assertTrue(result.drained_active)
        self.assertEqual(
            tuple(item.amount for item in result.test.dice_modifiers),
            (-1,),
        )
        self.assertEqual(
            result.test.quality_modifiers,
            (QualityModifier("RULE-GRIM", TestQuality.GRIM),),
        )

    def test_effective_view_must_match_actor_and_canonical_conditions(
        self,
    ) -> None:
        source, view = effective_view()
        invalid = (
            {"actor_id": "other", "conditions": source.state.conditions},
            {"actor_id": "hero", "conditions": ConditionState()},
        )
        for changes in invalid:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    DrainedTestPreparationRequest(
                        id="invalid:effective-view",
                        test=bonus_test(),
                        combat_surgeon_effective_effects=view,
                        **changes,
                    )

    def test_unknown_rule_and_forged_result_are_rejected(self) -> None:
        request = DrainedTestPreparationRequest(
            id="hero:unknown:drained",
            actor_id="hero",
            conditions=ConditionState({Condition.DRAINED}),
            test=bonus_test(),
            rule_id="RULE-UNKNOWN",
        )
        with self.assertRaisesRegex(ValueError, "unknown rule"):
            prepare_drained_test(request)

        valid = replace(request, rule_id=DRAINED_TEST_PREPARATION_RULE_ID)
        result = prepare_drained_test(valid)
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, test=valid.test)


if __name__ == "__main__":
    unittest.main()
