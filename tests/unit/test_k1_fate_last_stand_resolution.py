import unittest
from dataclasses import replace

from towr.domain.fate_last_stand_models import (
    FATE_LAST_STAND_APPLICATION_RULE_ID,
    FateLastStandApplicationRequest,
    FateLastStandResolutionStep,
)
from towr.domain.fate_models import (
    FATE_BURN_RULE_ID,
    FATE_LAST_STAND_RULE_ID,
    FATE_SESSION_RULE_ID,
    FateBurnResult,
    FateLastStandBurnRequest,
    FateSessionState,
    FateUnmitigatedSuccessBurnRequest,
)
from towr.domain.injury_models import (
    CharacterInjuryState,
    WoundEntryId,
    WoundRecord,
)
from towr.domain.test_models import TestProfile, TestRequest
from towr.rules.fate_last_stand_resolution import apply_fate_last_stand
from towr.rules.fate_resolution import burn_fate


def fate_state() -> FateSessionState:
    return FateSessionState(
        session_id="session:1",
        actor_id="hero",
        rating=1,
        session_spend_limit=1,
    )


def injury_state() -> CharacterInjuryState:
    return CharacterInjuryState(
        wounds=(
            WoundRecord(
                sequence=1,
                entry_id=WoundEntryId.SUPERFICIAL_INJURY,
                table_total=1,
                roll_values=(1,),
                effect_resolved=True,
            ),
        ),
    )


def last_stand_burn() -> FateBurnResult:
    return burn_fate(
        FateLastStandBurnRequest(
            id="burn:last-stand",
            state=fate_state(),
            battle_id="battle:gate",
            feat_id="feat:hold-the-gate",
            desperate_battle_approval_id="approval:desperate-battle",
            has_suffered_wound=True,
        )
    )


def application_request(
    *,
    burn: FateBurnResult | None = None,
    state: CharacterInjuryState | None = None,
    consumed_effect_ids: tuple[str, ...] = (),
) -> FateLastStandApplicationRequest:
    return FateLastStandApplicationRequest(
        id="apply:last-stand",
        session_id="session:1",
        actor_id="hero",
        battle_id="battle:gate",
        burn=last_stand_burn() if burn is None else burn,
        injury_state=injury_state() if state is None else state,
        qualifying_wound_sequence=1,
        final_scope_reference_id="scope:hold-until-allies-escape",
        affected_subject_ids=("hero", "allies", "gate"),
        accomplishment_reference_ids=(
            "movement:allies-escaped",
            "battle:gate-held",
        ),
        feat_accomplished=True,
        fits_game_tone_confirmed=True,
        within_actor_possibility_limits_confirmed=True,
        gm_adjustment_id="adjustment:final-scope",
        consumed_effect_ids=consumed_effect_ids,
    )


class K1FateLastStandApplicationTests(unittest.TestCase):
    def test_accomplished_feat_is_recorded_before_actor_dies(self) -> None:
        request = application_request()

        result = apply_fate_last_stand(request)

        self.assertEqual(result.previous_injury_state, request.injury_state)
        self.assertFalse(result.previous_injury_state.dead)
        self.assertTrue(result.injury_state.dead)
        self.assertEqual(
            replace(result.injury_state, dead=False),
            result.previous_injury_state,
        )
        self.assertEqual(result.qualifying_wound.sequence, 1)
        self.assertEqual(result.feat_id, "feat:hold-the-gate")
        self.assertEqual(
            result.resolution_steps,
            (
                FateLastStandResolutionStep.FEAT_ACCOMPLISHED,
                FateLastStandResolutionStep.ACTOR_DIED,
            ),
        )
        self.assertFalse(result.test_required)
        self.assertTrue(result.feat_accomplished)
        self.assertTrue(result.fits_game_tone_confirmed)
        self.assertTrue(result.within_actor_possibility_limits_confirmed)
        self.assertTrue(result.actor_dies_after_feat)
        self.assertTrue(result.gm_may_adjust_scope)
        self.assertEqual(result.gm_adjustment_id, "adjustment:final-scope")
        self.assertEqual(result.fate_state.rating, 0)
        self.assertEqual(
            result.consumed_effect_ids,
            ("burn:last-stand:effect",),
        )
        self.assertEqual(
            result.applied_rule_ids,
            (
                FATE_SESSION_RULE_ID,
                FATE_BURN_RULE_ID,
                FATE_LAST_STAND_RULE_ID,
                FATE_LAST_STAND_APPLICATION_RULE_ID,
            ),
        )
        unadjusted = apply_fate_last_stand(
            replace(request, gm_adjustment_id=None)
        )
        self.assertIsNone(unadjusted.gm_adjustment_id)

    def test_exact_previously_suffered_wound_is_required(self) -> None:
        with self.assertRaisesRegex(ValueError, "previously suffered Wound"):
            application_request(state=CharacterInjuryState())
        with self.assertRaisesRegex(ValueError, "previously suffered Wound"):
            replace(application_request(), qualifying_wound_sequence=2)
        with self.assertRaisesRegex(ValueError, "dead actor"):
            application_request(state=replace(injury_state(), dead=True))

    def test_scope_targets_consequences_and_accomplishment_are_explicit(self) -> None:
        request = application_request()

        with self.assertRaisesRegex(ValueError, "feat_accomplished"):
            replace(request, feat_accomplished=False)
        with self.assertRaisesRegex(ValueError, "fits_game_tone_confirmed"):
            replace(request, fits_game_tone_confirmed=False)
        with self.assertRaisesRegex(
            ValueError,
            "within_actor_possibility_limits_confirmed",
        ):
            replace(request, within_actor_possibility_limits_confirmed=False)
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            replace(request, affected_subject_ids=())
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            replace(request, accomplishment_reference_ids=())
        with self.assertRaisesRegex(ValueError, "must be unique"):
            replace(request, affected_subject_ids=("gate", "gate"))

    def test_foreign_wrong_kind_replayed_and_unknown_effects_are_rejected(self) -> None:
        request = application_request()

        with self.assertRaisesRegex(ValueError, "another session"):
            replace(request, session_id="session:other")
        with self.assertRaisesRegex(ValueError, "another actor"):
            replace(request, actor_id="other")
        with self.assertRaisesRegex(ValueError, "another battle"):
            replace(request, battle_id="battle:other")
        with self.assertRaisesRegex(ValueError, "already consumed"):
            replace(
                request,
                consumed_effect_ids=(request.burn.effect_request.id,),
            )
        wrong_burn = burn_fate(
            FateUnmitigatedSuccessBurnRequest(
                id="burn:wrong-kind",
                state=fate_state(),
                test=TestRequest("test:wrong-kind", TestProfile(2, 5)),
            )
        )
        with self.assertRaisesRegex(ValueError, "matching burn result"):
            replace(request, burn=wrong_burn)
        with self.assertRaisesRegex(ValueError, "unknown rule"):
            replace(request, rule_id="RULE-OTHER")

    def test_forged_application_result_is_rejected(self) -> None:
        result = apply_fate_last_stand(application_request())

        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, injury_state=result.previous_injury_state)
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(
                result,
                resolution_steps=(
                    FateLastStandResolutionStep.ACTOR_DIED,
                    FateLastStandResolutionStep.FEAT_ACCOMPLISHED,
                ),
            )
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, accomplishment_reference_ids=("other",))


if __name__ == "__main__":
    unittest.main()
