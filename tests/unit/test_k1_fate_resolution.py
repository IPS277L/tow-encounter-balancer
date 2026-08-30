from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.drained_test_models import DrainedTestPreparationRequest
from towr.domain.fate_models import (
    FATE_BURN_RULE_ID,
    FATE_LAST_STAND_RULE_ID,
    FATE_LUCKY_RULE_ID,
    FATE_NEAR_MISS_RULE_ID,
    FATE_REFRESH_RULE_ID,
    FATE_SECOND_ACTION_RULE_ID,
    FATE_SESSION_RULE_ID,
    FATE_UNMITIGATED_SUCCESS_RULE_ID,
    FateBurnKind,
    FateGloriousSpendRequest,
    FateLastStandBurnRequest,
    FateLastStandEffectRequest,
    FateNearMissBurnRequest,
    FateNearMissEffectRequest,
    FateRefreshRequest,
    FateSecondActionSpendRequest,
    FateSessionState,
    FateSpendKind,
    FateSpendFunding,
    FateSpendRecord,
    FateUnmitigatedSuccessBurnRequest,
    FateUnmitigatedSuccessEffectRequest,
)
from towr.domain.injury_models import DecisionOwner
from towr.domain.resolution_models import ConsumeWoundNegationRequest
from towr.domain.test_models import (
    BasicOutcome,
    FATE_GLORIOUS_RULE_ID,
    QualityModifier,
    QualityModifierSource,
    TestProfile,
    TestQuality,
    TestRequest,
)
from towr.domain.turn_models import (
    ActionSlotGrant,
    CombatActionDeclaration,
    CombatActionKind,
    CombatActionSlotRequest,
    CombatRoundState,
    CombatSide,
    CombatTurnParticipant,
    CombatTurnStartRequest,
    ManoeuvreKind,
)
from towr.rules.drained_test_resolution import prepare_drained_test
from towr.rules.fate_resolution import (
    burn_fate,
    refresh_fate,
    spend_fate_for_glorious,
    spend_fate_for_second_action,
)
from towr.rules.test_resolution import (
    RerollAllFailures,
    complete_test,
    resolve_test,
    roll_test_initial,
)
from towr.rules.turn_resolution import (
    ACTION_BUDGET_RULE_ID,
    reserve_combat_action_slot,
    start_combat_turn,
)


def fate_state(*, rating: int = 2, has_lucky: bool = False) -> FateSessionState:
    return FateSessionState(
        session_id="session:1",
        actor_id="hero",
        rating=rating,
        session_spend_limit=rating,
        has_lucky=has_lucky,
    )


def grim_test(test_id: str = "hero:test") -> TestRequest:
    return TestRequest(
        id=test_id,
        profile=TestProfile(2, 5),
        quality_modifiers=(
            QualityModifier("RULE-GRIM", TestQuality.GRIM),
        ),
    )


def second_action_request(
    *,
    first: CombatActionDeclaration | None = None,
    second: CombatActionDeclaration | None = None,
    actor_id: str = "hero",
    request_id: str = "slot:hero:2",
) -> CombatActionSlotRequest:
    round_state = CombatRoundState(
        round_number=1,
        participants=(
            CombatTurnParticipant("hero", CombatSide.PLAYERS_AND_ALLIES),
            CombatTurnParticipant("enemy", CombatSide.OPPOSITION),
        ),
    )
    started = start_combat_turn(
        CombatTurnStartRequest("turn:hero", round_state, "hero")
    )
    first_result = reserve_combat_action_slot(
        CombatActionSlotRequest(
            id="slot:hero:1",
            state=started.state,
            actor_id="hero",
            declaration=first
            or CombatActionDeclaration(CombatActionKind.AIM),
            grant=ActionSlotGrant.STANDARD,
        )
    )
    return CombatActionSlotRequest(
        id=request_id,
        state=first_result.state,
        actor_id=actor_id,
        declaration=second
        or CombatActionDeclaration(CombatActionKind.ATTACK),
        grant=ActionSlotGrant.FATE,
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


class K1FateLuckyTests(unittest.TestCase):
    def test_first_session_spend_is_free_even_at_zero_rating(self) -> None:
        source = fate_state(rating=0, has_lucky=True)

        result = spend_fate_for_glorious(
            FateGloriousSpendRequest(
                id="spend:lucky:free",
                state=source,
                test=TestRequest("test:lucky:free", TestProfile(2, 5)),
            )
        )

        self.assertTrue(source.lucky_free_spend_available)
        self.assertTrue(source.can_spend)
        self.assertIs(result.spend.funding, FateSpendFunding.LUCKY_FREE)
        self.assertEqual(result.spend.session_cost, 0)
        self.assertEqual(result.state.remaining_spends, 0)
        self.assertFalse(result.state.lucky_free_spend_available)
        self.assertFalse(result.state.can_spend)
        self.assertEqual(
            result.applied_rule_ids,
            (
                FATE_SESSION_RULE_ID,
                FATE_LUCKY_RULE_ID,
                FATE_GLORIOUS_RULE_ID,
            ),
        )

    def test_only_first_spend_is_free_then_shared_pool_is_used(self) -> None:
        first = spend_fate_for_glorious(
            FateGloriousSpendRequest(
                id="spend:lucky:first",
                state=fate_state(rating=1, has_lucky=True),
                test=TestRequest("test:lucky:first", TestProfile(2, 5)),
            )
        )
        second = spend_fate_for_second_action(
            FateSecondActionSpendRequest(
                id="spend:lucky:second",
                state=first.state,
                slot_request=second_action_request(),
            )
        )

        self.assertEqual(first.state.remaining_spends, 1)
        self.assertIs(second.spend.funding, FateSpendFunding.SESSION_POOL)
        self.assertEqual(second.state.remaining_spends, 0)
        self.assertNotIn(FATE_LUCKY_RULE_ID, second.applied_rule_ids)
        with self.assertRaisesRegex(ValueError, "no Fate spends remain"):
            FateGloriousSpendRequest(
                id="spend:lucky:third",
                state=second.state,
                test=TestRequest("test:lucky:third", TestProfile(2, 5)),
            )

    def test_lucky_funding_cannot_be_forged_or_delayed(self) -> None:
        paid = FateSpendRecord(
            id="spend:paid",
            session_id="session:1",
            actor_id="hero",
            kind=FateSpendKind.GLORIOUS_TEST,
            subject_id="test:paid",
            rule_id=FATE_GLORIOUS_RULE_ID,
        )
        free = replace(paid, funding=FateSpendFunding.LUCKY_FREE)
        with self.assertRaisesRegex(ValueError, "Lucky actor"):
            FateSessionState(
                "session:1",
                "hero",
                0,
                0,
                spends=(free,),
            )
        with self.assertRaisesRegex(ValueError, "first Fate spend must be free"):
            FateSessionState(
                "session:1",
                "hero",
                1,
                1,
                spends=(paid,),
                has_lucky=True,
            )
        with self.assertRaisesRegex(ValueError, "first Fate spend can be free"):
            FateSessionState(
                "session:1",
                "hero",
                1,
                1,
                spends=(paid, replace(free, id="spend:late", subject_id="test:late")),
                has_lucky=True,
            )


class K1FateRefreshTests(unittest.TestCase):
    def test_gm_refresh_restores_remaining_spends_to_current_rating(self) -> None:
        spent = spend_fate_for_glorious(
            FateGloriousSpendRequest(
                id="spend:before-refresh",
                state=fate_state(rating=2),
                test=TestRequest("test:before-refresh", TestProfile(2, 5)),
            )
        )
        request = FateRefreshRequest(
            id="refresh:mid-session:1",
            state=spent.state,
            mid_session_break_id="break:mid-session:1",
            gm_approval_id="approval:refresh:1",
        )

        result = refresh_fate(request)

        self.assertEqual(result.previous_state.remaining_spends, 1)
        self.assertEqual(result.refresh.restored_spends, 1)
        self.assertEqual(result.refresh.previous_spend_limit, 2)
        self.assertEqual(result.refresh.new_spend_limit, 3)
        self.assertEqual(result.state.remaining_spends, 2)
        self.assertEqual(result.state.spends, spent.state.spends)
        self.assertEqual(result.state.refreshes, (result.refresh,))
        self.assertEqual(
            result.applied_rule_ids,
            (FATE_SESSION_RULE_ID, FATE_REFRESH_RULE_ID),
        )

    def test_refresh_preserves_history_and_can_follow_later_breaks(self) -> None:
        first = spend_fate_for_glorious(
            FateGloriousSpendRequest(
                id="spend:refresh:first",
                state=fate_state(rating=1),
                test=TestRequest("test:refresh:first", TestProfile(2, 5)),
            )
        )
        refreshed = refresh_fate(
            FateRefreshRequest(
                id="refresh:first",
                state=first.state,
                mid_session_break_id="break:first",
                gm_approval_id="approval:first",
            )
        )
        second = spend_fate_for_glorious(
            FateGloriousSpendRequest(
                id="spend:refresh:second",
                state=refreshed.state,
                test=TestRequest("test:refresh:second", TestProfile(2, 5)),
            )
        )

        with self.assertRaisesRegex(ValueError, "break already refreshed"):
            FateRefreshRequest(
                id="refresh:duplicate-break",
                state=second.state,
                mid_session_break_id="break:first",
                gm_approval_id="approval:second",
            )
        again = refresh_fate(
            FateRefreshRequest(
                id="refresh:second",
                state=second.state,
                mid_session_break_id="break:second",
                gm_approval_id="approval:second",
            )
        )
        self.assertEqual(again.state.remaining_spends, 1)
        self.assertEqual(len(again.state.spends), 2)
        self.assertEqual(len(again.state.refreshes), 2)

    def test_refresh_requires_loss_break_and_gm_approval(self) -> None:
        with self.assertRaisesRegex(ValueError, "already refreshed"):
            FateRefreshRequest(
                id="refresh:full",
                state=fate_state(rating=2),
                mid_session_break_id="break:full",
                gm_approval_id="approval:full",
            )
        with self.assertRaisesRegex(ValueError, "zero Fate rating"):
            FateRefreshRequest(
                id="refresh:zero",
                state=fate_state(rating=0),
                mid_session_break_id="break:zero",
                gm_approval_id="approval:zero",
            )
        spent = spend_fate_for_glorious(
            FateGloriousSpendRequest(
                id="spend:refresh-owner",
                state=fate_state(rating=1),
                test=TestRequest("test:refresh-owner", TestProfile(2, 5)),
            )
        )
        with self.assertRaisesRegex(ValueError, "only the GM"):
            FateRefreshRequest(
                id="refresh:wrong-owner",
                state=spent.state,
                mid_session_break_id="break:owner",
                gm_approval_id="approval:owner",
                decision_owner=DecisionOwner.ACTOR,
            )

    def test_unknown_rule_and_forged_refresh_are_rejected(self) -> None:
        spent = spend_fate_for_glorious(
            FateGloriousSpendRequest(
                id="spend:refresh-forgery",
                state=fate_state(rating=1),
                test=TestRequest("test:refresh-forgery", TestProfile(2, 5)),
            )
        )
        request = FateRefreshRequest(
            id="refresh:forgery",
            state=spent.state,
            mid_session_break_id="break:forgery",
            gm_approval_id="approval:forgery",
            rule_id="RULE-UNKNOWN",
        )
        with self.assertRaisesRegex(ValueError, "unknown rule"):
            refresh_fate(request)

        result = refresh_fate(replace(request, rule_id=FATE_REFRESH_RULE_ID))
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, state=result.previous_state)
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(
                result,
                refresh=replace(result.refresh, restored_spends=2, new_spend_limit=3),
            )


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


class K1FateSecondActionSpendTests(unittest.TestCase):
    def test_spend_atomically_reserves_bound_second_action(self) -> None:
        slot_request = second_action_request()
        source_state = fate_state()

        result = spend_fate_for_second_action(
            FateSecondActionSpendRequest(
                id="spend:second-action",
                state=source_state,
                slot_request=slot_request,
            )
        )

        self.assertEqual(source_state.remaining_spends, 2)
        self.assertEqual(result.state.remaining_spends, 1)
        self.assertIs(result.spend.kind, FateSpendKind.SECOND_ACTION)
        self.assertEqual(result.spend.subject_id, slot_request.id)
        self.assertEqual(result.proof.session_id, source_state.session_id)
        self.assertEqual(result.proof.actor_id, "hero")
        self.assertEqual(result.proof.slot_request_id, slot_request.id)
        self.assertEqual(result.proof.round_number, 1)
        self.assertEqual(result.proof.slot_index, 2)
        self.assertEqual(result.proof.declaration, slot_request.declaration)
        self.assertEqual(result.proof.source_spend_id, result.spend.id)
        self.assertEqual(result.slot_result.slot.index, 2)
        self.assertIs(result.slot_result.slot.grant, ActionSlotGrant.FATE)
        self.assertEqual(
            result.applied_rule_ids,
            (
                FATE_SESSION_RULE_ID,
                ACTION_BUDGET_RULE_ID,
                FATE_SECOND_ACTION_RULE_ID,
            ),
        )
        self.assertEqual(
            len(result.slot_result.state.active_turn.action_slots),
            2,
        )
        self.assertEqual(
            len(slot_request.state.active_turn.action_slots),
            1,
        )

    def test_raw_fate_grant_and_mismatched_actor_are_rejected(self) -> None:
        slot_request = second_action_request()
        with self.assertRaisesRegex(ValueError, "requires a spend proof"):
            reserve_combat_action_slot(slot_request)

        with self.assertRaisesRegex(ValueError, "another action actor"):
            FateSecondActionSpendRequest(
                id="spend:other",
                state=replace(fate_state(), actor_id="other"),
                slot_request=slot_request,
            )
        with self.assertRaisesRegex(ValueError, "another action actor"):
            FateSecondActionSpendRequest(
                id="spend:request-other",
                state=fate_state(),
                slot_request=second_action_request(actor_id="other"),
            )

    def test_invalid_second_action_does_not_produce_a_spend_result(self) -> None:
        repeated = second_action_request(
            first=CombatActionDeclaration(CombatActionKind.AIM),
            second=CombatActionDeclaration(CombatActionKind.AIM),
        )
        with self.assertRaisesRegex(ValueError, "cannot repeat"):
            spend_fate_for_second_action(
                FateSecondActionSpendRequest(
                    id="spend:repeated",
                    state=fate_state(),
                    slot_request=repeated,
                )
            )

        second_attack = second_action_request(
            first=CombatActionDeclaration(CombatActionKind.ATTACK),
            second=CombatActionDeclaration(
                CombatActionKind.MANOEUVRE,
                manoeuvre=ManoeuvreKind.CHARGE,
            ),
        )
        with self.assertRaisesRegex(ValueError, "second attack"):
            spend_fate_for_second_action(
                FateSecondActionSpendRequest(
                    id="spend:second-attack",
                    state=fate_state(),
                    slot_request=second_attack,
                )
            )

    def test_same_bound_slot_cannot_consume_fate_twice(self) -> None:
        slot_request = second_action_request()
        first = spend_fate_for_second_action(
            FateSecondActionSpendRequest(
                id="spend:first",
                state=fate_state(),
                slot_request=slot_request,
            )
        )

        with self.assertRaisesRegex(ValueError, "already spent"):
            FateSecondActionSpendRequest(
                id="spend:second",
                state=first.state,
                slot_request=slot_request,
            )

    def test_glorious_and_second_action_share_one_session_pool(self) -> None:
        glorious = spend_fate_for_glorious(
            FateGloriousSpendRequest(
                id="spend:glorious-first",
                state=fate_state(),
                test=TestRequest("hero:test:shared", TestProfile(2, 5)),
            )
        )
        second_action = spend_fate_for_second_action(
            FateSecondActionSpendRequest(
                id="spend:action-second",
                state=glorious.state,
                slot_request=second_action_request(),
            )
        )

        self.assertEqual(second_action.state.remaining_spends, 0)
        self.assertEqual(
            tuple(item.kind for item in second_action.state.spends),
            (FateSpendKind.GLORIOUS_TEST, FateSpendKind.SECOND_ACTION),
        )

    def test_third_action_is_rejected_before_spending_fate(self) -> None:
        second_request = second_action_request()
        second_slot = reserve_combat_action_slot(
            replace(
                second_request,
                grant=ActionSlotGrant.ABILITY,
                grant_rule_id="RULE-ABILITY:test-extra-action",
            )
        )
        third_request = CombatActionSlotRequest(
            id="slot:hero:3",
            state=second_slot.state,
            actor_id="hero",
            declaration=CombatActionDeclaration(CombatActionKind.RECOVER),
            grant=ActionSlotGrant.FATE,
        )

        with self.assertRaisesRegex(ValueError, "third action"):
            spend_fate_for_second_action(
                FateSecondActionSpendRequest(
                    id="spend:third-action",
                    state=fate_state(),
                    slot_request=third_request,
                )
            )

    def test_unknown_rule_and_forged_composite_are_rejected(self) -> None:
        request = FateSecondActionSpendRequest(
            id="spend:unknown-second",
            state=fate_state(),
            slot_request=second_action_request(),
            rule_id="RULE-UNKNOWN",
        )
        with self.assertRaisesRegex(ValueError, "unknown rule"):
            spend_fate_for_second_action(request)

        result = spend_fate_for_second_action(
            replace(request, rule_id=FATE_SECOND_ACTION_RULE_ID)
        )
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, state=result.previous_state)
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(
                result,
                proof=replace(result.proof, actor_id="other"),
            )
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(
                result,
                slot_result=replace(
                    result.slot_result,
                    applied_rule_ids=(FATE_SECOND_ACTION_RULE_ID,),
                ),
            )
        with self.assertRaisesRegex(ValueError, "trace is incomplete"):
            replace(
                result,
                applied_rule_ids=(FATE_SECOND_ACTION_RULE_ID,),
            )


class K1FateBurnTests(unittest.TestCase):
    def test_unmitigated_success_can_be_declared_before_or_after_initial_roll(
        self,
    ) -> None:
        test = TestRequest("hero:test:critical", TestProfile(2, 5))
        before = burn_fate(
            FateUnmitigatedSuccessBurnRequest(
                id="burn:before-roll",
                state=fate_state(),
                test=test,
                gm_scope_agreement_id="agreement:critical-feat",
            )
        )

        self.assertEqual(before.state.rating, 1)
        self.assertEqual(before.state.session_spend_limit, 1)
        self.assertEqual(before.state.remaining_spends, 1)
        self.assertEqual(before.burn.kind, FateBurnKind.UNMITIGATED_SUCCESS)
        self.assertTrue(before.burn.current_session_allowance_reduced)
        self.assertIsInstance(
            before.effect_request,
            FateUnmitigatedSuccessEffectRequest,
        )
        self.assertEqual(
            before.effect_request.minimum_outcome,
            BasicOutcome.TOTAL_SUCCESS,
        )
        self.assertEqual(before.effect_request.maximum_wounds_inflicted, 1)
        self.assertTrue(before.effect_request.may_not_kill_multiple_enemies)
        self.assertEqual(
            before.applied_rule_ids,
            (
                FATE_SESSION_RULE_ID,
                FATE_BURN_RULE_ID,
                FATE_UNMITIGATED_SUCCESS_RULE_ID,
            ),
        )

        initial_roll = roll_test_initial(test, SequenceRandom([1, 10]))
        after = burn_fate(
            FateUnmitigatedSuccessBurnRequest(
                id="burn:after-roll",
                state=fate_state(rating=1),
                test=test,
                initial_roll=initial_roll,
            )
        )
        self.assertEqual(after.effect_request.initial_roll, initial_roll)

        other_roll = roll_test_initial(
            TestRequest("hero:test:other", TestProfile(2, 5)),
            SequenceRandom([1, 2]),
        )
        with self.assertRaisesRegex(ValueError, "another Test"):
            FateUnmitigatedSuccessBurnRequest(
                id="burn:mismatched-roll",
                state=fate_state(),
                test=test,
                initial_roll=other_roll,
            )

    def test_near_miss_emits_exact_wound_negation_without_state_mutation(
        self,
    ) -> None:
        negation = ConsumeWoundNegationRequest(
            resolution_id="wound:hero:7",
            rule_id=FATE_NEAR_MISS_RULE_ID,
        )
        result = burn_fate(
            FateNearMissBurnRequest(
                id="burn:near-miss",
                state=fate_state(rating=1),
                wound_negation=negation,
            )
        )

        self.assertEqual(result.state.rating, 0)
        self.assertEqual(result.proof.subject_id, negation.resolution_id)
        self.assertIsInstance(result.effect_request, FateNearMissEffectRequest)
        self.assertEqual(result.effect_request.wound_negation, negation)
        self.assertTrue(result.effect_request.negates_just_suffered_wound)
        self.assertTrue(result.effect_request.does_not_increase_future_wound_dice)
        self.assertTrue(result.effect_request.preserves_pre_wound_staggered)

        with self.assertRaisesRegex(ValueError, "canonical rule"):
            FateNearMissBurnRequest(
                id="burn:wrong-negation",
                state=fate_state(rating=1),
                wound_negation=replace(negation, rule_id="RULE-OTHER"),
            )

    def test_last_stand_requires_a_wound_and_emits_terminal_follow_up(self) -> None:
        with self.assertRaisesRegex(ValueError, "suffered a Wound"):
            FateLastStandBurnRequest(
                id="burn:last-stand:invalid",
                state=fate_state(rating=1),
                battle_id="battle:1",
                feat_id="feat:hold-the-gate",
                desperate_battle_approval_id="approval:desperate-battle",
                has_suffered_wound=False,
            )

        result = burn_fate(
            FateLastStandBurnRequest(
                id="burn:last-stand",
                state=fate_state(rating=1),
                battle_id="battle:1",
                feat_id="feat:hold-the-gate",
                desperate_battle_approval_id="approval:desperate-battle",
                has_suffered_wound=True,
            )
        )

        self.assertIsInstance(result.effect_request, FateLastStandEffectRequest)
        self.assertFalse(result.effect_request.test_required)
        self.assertTrue(result.effect_request.actor_dies_after_feat)
        self.assertTrue(result.effect_request.gm_may_adjust_scope)
        self.assertEqual(result.effect_request.rule_id, FATE_LAST_STAND_RULE_ID)

    def test_exhausted_pool_defers_allowance_penalty_until_next_session(
        self,
    ) -> None:
        spent = spend_fate_for_glorious(
            FateGloriousSpendRequest(
                id="spend:all-fate",
                state=fate_state(rating=1),
                test=TestRequest("hero:test:spent", TestProfile(2, 5)),
            )
        )
        self.assertEqual(spent.state.remaining_spends, 0)

        burned = burn_fate(
            FateNearMissBurnRequest(
                id="burn:while-empty",
                state=spent.state,
                wound_negation=ConsumeWoundNegationRequest(
                    "wound:hero:empty-pool",
                    FATE_NEAR_MISS_RULE_ID,
                ),
            )
        )

        self.assertEqual(burned.state.rating, 0)
        self.assertEqual(burned.state.session_spend_limit, 1)
        self.assertEqual(burned.state.remaining_spends, 0)
        self.assertFalse(burned.burn.current_session_allowance_reduced)
        self.assertEqual(burned.state.session_refresh_rating, 1)

        refreshed = refresh_fate(
            FateRefreshRequest(
                id="refresh:after-deferred-burn",
                state=burned.state,
                mid_session_break_id="break:after-deferred-burn",
                gm_approval_id="approval:after-deferred-burn",
            )
        )
        self.assertEqual(refreshed.state.rating, 0)
        self.assertEqual(refreshed.state.remaining_spends, 1)
        self.assertEqual(refreshed.state.session_refresh_rating, 1)

        next_session = FateSessionState(
            session_id="session:2",
            actor_id="hero",
            rating=refreshed.state.rating,
            session_spend_limit=refreshed.state.rating,
        )
        self.assertEqual(next_session.remaining_spends, 0)

    def test_refresh_and_burn_share_a_validated_resource_event_order(self) -> None:
        spent = spend_fate_for_glorious(
            FateGloriousSpendRequest(
                id="spend:before-events",
                state=fate_state(),
                test=TestRequest("hero:test:event", TestProfile(2, 5)),
            )
        )
        refreshed = refresh_fate(
            FateRefreshRequest(
                id="refresh:event:1",
                state=spent.state,
                mid_session_break_id="break:event:1",
                gm_approval_id="approval:event:1",
            )
        )
        burned = burn_fate(
            FateUnmitigatedSuccessBurnRequest(
                id="burn:event:2",
                state=refreshed.state,
                test=TestRequest("hero:test:event:burn", TestProfile(2, 5)),
            )
        )

        self.assertEqual(
            burned.state.resource_event_ids,
            ("refresh:event:1", "burn:event:2"),
        )
        self.assertEqual(burned.state.rating, 1)
        self.assertEqual(burned.state.remaining_spends, 1)
        with self.assertRaisesRegex(ValueError, "resource history"):
            replace(
                burned.state,
                resource_event_ids=("burn:event:2", "refresh:event:1"),
            )

    def test_zero_rating_duplicates_and_forged_results_are_rejected(self) -> None:
        test = TestRequest("hero:test:burn-once", TestProfile(2, 5))
        with self.assertRaisesRegex(ValueError, "zero rating"):
            FateUnmitigatedSuccessBurnRequest(
                id="burn:zero",
                state=fate_state(rating=0),
                test=test,
            )

        result = burn_fate(
            FateUnmitigatedSuccessBurnRequest(
                id="burn:once",
                state=fate_state(),
                test=test,
            )
        )
        with self.assertRaisesRegex(ValueError, "subject and kind"):
            FateUnmitigatedSuccessBurnRequest(
                id="burn:twice",
                state=result.state,
                test=test,
            )
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, state=result.previous_state)
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(
                result,
                effect_request=replace(result.effect_request, actor_id="other"),
            )


if __name__ == "__main__":
    unittest.main()
