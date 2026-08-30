import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.fate_models import (
    FATE_BURN_RULE_ID,
    FATE_SESSION_RULE_ID,
    FATE_UNMITIGATED_SUCCESS_RULE_ID,
    FateBurnResult,
    FateSessionState,
    FateUnmitigatedSuccessBurnRequest,
)
from towr.domain.fate_unmitigated_success_models import (
    FATE_UNMITIGATED_SUCCESS_APPLICATION_RULE_ID,
    FateUnmitigatedSuccessApplicationRequest,
)
from towr.domain.test_models import (
    BasicOutcome,
    InitialTestRoll,
    QualityModifier,
    TestProfile,
    TestQuality,
    TestRequest,
    TestResult,
)
from towr.rules.fate_resolution import burn_fate
from towr.rules.fate_unmitigated_success_resolution import (
    apply_fate_unmitigated_success,
)
from towr.rules.test_resolution import (
    RerollAllFailures,
    complete_test,
    resolve_test,
    roll_test_initial,
)


def fate_state() -> FateSessionState:
    return FateSessionState(
        session_id="session:1",
        actor_id="hero",
        rating=2,
        session_spend_limit=2,
    )


def burn_for(
    test: TestRequest,
    *,
    initial_roll: InitialTestRoll | None = None,
) -> FateBurnResult:
    return burn_fate(
        FateUnmitigatedSuccessBurnRequest(
            id="burn:unmitigated",
            state=fate_state(),
            test=test,
            initial_roll=initial_roll,
            gm_scope_agreement_id="agreement:best-possible",
        )
    )


def application_request(
    *,
    burn: FateBurnResult,
    test_result: TestResult,
    is_attack: bool = False,
    killed_enemy_ids: tuple[str, ...] = (),
    wounds_inflicted: int = 0,
    consumed_effect_ids: tuple[str, ...] = (),
) -> FateUnmitigatedSuccessApplicationRequest:
    return FateUnmitigatedSuccessApplicationRequest(
        id="apply:unmitigated",
        session_id="session:1",
        actor_id="hero",
        burn=burn,
        test_result=test_result,
        outcome_reference_id="outcome:hold-the-bridge",
        realistically_possible_outcome_confirmed=True,
        is_attack=is_attack,
        killed_enemy_ids=killed_enemy_ids,
        wounds_inflicted=wounds_inflicted,
        consumed_effect_ids=consumed_effect_ids,
    )


class K1FateUnmitigatedSuccessApplicationTests(unittest.TestCase):
    def test_failure_becomes_total_success_without_rewriting_test(self) -> None:
        test = TestRequest("test:hold-bridge", TestProfile(2, 5))
        test_result = resolve_test(test, SequenceRandom([9, 10]))
        burn = burn_for(test)

        result = apply_fate_unmitigated_success(
            application_request(burn=burn, test_result=test_result)
        )

        self.assertEqual(result.test_result, test_result)
        self.assertIs(result.ordinary_outcome, BasicOutcome.FAILURE)
        self.assertIs(result.outcome, BasicOutcome.TOTAL_SUCCESS)
        self.assertTrue(result.usual_outcome_superseded)
        self.assertEqual(result.fate_state, burn.state)
        self.assertEqual(
            result.gm_scope_agreement_id,
            "agreement:best-possible",
        )
        self.assertEqual(
            result.consumed_effect_ids,
            ("burn:unmitigated:effect",),
        )
        self.assertEqual(
            result.applied_rule_ids,
            (
                FATE_SESSION_RULE_ID,
                FATE_BURN_RULE_ID,
                FATE_UNMITIGATED_SUCCESS_RULE_ID,
                FATE_UNMITIGATED_SUCCESS_APPLICATION_RULE_ID,
            ),
        )

    def test_after_roll_burn_requires_that_exact_initial_roll(self) -> None:
        test = TestRequest("test:after-roll", TestProfile(2, 5))
        initial_roll = roll_test_initial(test, SequenceRandom([9, 10]))
        burn = burn_for(test, initial_roll=initial_roll)
        completed = complete_test(initial_roll, SequenceRandom([]))

        result = apply_fate_unmitigated_success(
            application_request(burn=burn, test_result=completed)
        )
        self.assertEqual(result.test_result.trace.initial_values, (9, 10))

        another_result = resolve_test(test, SequenceRandom([1, 2]))
        with self.assertRaisesRegex(ValueError, "another initial roll"):
            application_request(burn=burn, test_result=another_result)

    def test_canonical_grim_and_glorious_completions_are_accepted(self) -> None:
        grim = TestRequest(
            "test:grim",
            TestProfile(2, 5),
            quality_modifiers=(
                QualityModifier("RULE-TEST:grim", TestQuality.GRIM),
            ),
        )
        grim_result = resolve_test(grim, SequenceRandom([1, 10, 10]))
        self.assertIs(
            apply_fate_unmitigated_success(
                application_request(
                    burn=burn_for(grim),
                    test_result=grim_result,
                )
            ).ordinary_outcome,
            BasicOutcome.FAILURE,
        )

        glorious = TestRequest(
            "test:glorious",
            TestProfile(2, 5),
            quality_modifiers=(
                QualityModifier("RULE-TEST:glorious", TestQuality.GLORIOUS),
            ),
        )
        glorious_result = resolve_test(
            glorious,
            SequenceRandom([1, 10, 2]),
            decisions=RerollAllFailures(),
        )
        self.assertIs(
            apply_fate_unmitigated_success(
                application_request(
                    burn=burn_for(glorious),
                    test_result=glorious_result,
                )
            ).ordinary_outcome,
            BasicOutcome.SUCCESS,
        )

    def test_attack_limits_are_explicit_and_enforced(self) -> None:
        test = TestRequest("test:attack", TestProfile(2, 5))
        test_result = resolve_test(test, SequenceRandom([1, 10]))
        burn = burn_for(test)

        result = apply_fate_unmitigated_success(
            application_request(
                burn=burn,
                test_result=test_result,
                is_attack=True,
                killed_enemy_ids=("enemy:1",),
                wounds_inflicted=1,
            )
        )
        self.assertTrue(result.is_attack)
        self.assertEqual(result.killed_enemy_ids, ("enemy:1",))
        self.assertEqual(result.wounds_inflicted, 1)

        with self.assertRaisesRegex(ValueError, "kill multiple enemies"):
            application_request(
                burn=burn,
                test_result=test_result,
                is_attack=True,
                killed_enemy_ids=("enemy:1", "enemy:2"),
            )
        with self.assertRaisesRegex(ValueError, "inflict multiple Wounds"):
            application_request(
                burn=burn,
                test_result=test_result,
                is_attack=True,
                wounds_inflicted=2,
            )
        with self.assertRaisesRegex(ValueError, "non-attack"):
            application_request(
                burn=burn,
                test_result=test_result,
                wounds_inflicted=1,
            )

    def test_realistic_outcome_and_narrative_reference_are_required(self) -> None:
        test = TestRequest("test:scope", TestProfile(2, 5))
        test_result = resolve_test(test, SequenceRandom([10, 10]))
        burn = burn_for(test)

        with self.assertRaisesRegex(ValueError, "realistically possible"):
            replace(
                application_request(burn=burn, test_result=test_result),
                realistically_possible_outcome_confirmed=False,
            )
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            replace(
                application_request(burn=burn, test_result=test_result),
                outcome_reference_id=" ",
            )

    def test_foreign_replayed_and_forged_inputs_are_rejected(self) -> None:
        test = TestRequest("test:provenance", TestProfile(2, 5))
        test_result = resolve_test(test, SequenceRandom([10, 10]))
        burn = burn_for(test)
        request = application_request(burn=burn, test_result=test_result)

        with self.assertRaisesRegex(ValueError, "another session"):
            replace(request, session_id="session:other")
        with self.assertRaisesRegex(ValueError, "another actor"):
            replace(request, actor_id="other")
        with self.assertRaisesRegex(ValueError, "already consumed"):
            replace(
                request,
                consumed_effect_ids=(burn.effect_request.id,),
            )
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(
                request,
                test_result=replace(
                    test_result,
                    trace=replace(test_result.trace, successes=99),
                ),
            )

        result = apply_fate_unmitigated_success(request)
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, outcome=BasicOutcome.SUCCESS)
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, test_result=resolve_test(test, SequenceRandom([1, 1])))


if __name__ == "__main__":
    unittest.main()
