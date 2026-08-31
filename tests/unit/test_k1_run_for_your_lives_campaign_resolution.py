from __future__ import annotations

import inspect
import unittest
from dataclasses import replace

from towr.domain.campaign_consequence_models import (
    CampaignConsequenceState,
    RunForYourLivesCampaignApplicationRequest,
    RunForYourLivesCampaignApplicationResult,
    RunForYourLivesConsequenceSpecification,
)
from towr.domain.retreat_models import (
    RUN_FOR_YOUR_LIVES_RULE_ID,
    RetreatCoverKind,
    RunForYourLivesCampaignConsequenceRequest,
    RunForYourLivesOutcome,
)
from towr.rules.run_for_your_lives_campaign_resolution import (
    register_run_for_your_lives_campaign_consequence,
)


TABLE_TOTALS = {
    RunForYourLivesOutcome.LOST: 1,
    RunForYourLivesOutcome.MOCKED: 4,
    RunForYourLivesOutcome.INDEBTED: 7,
    RunForYourLivesOutcome.MARKED: 10,
    RunForYourLivesOutcome.EXPOSED: 13,
    RunForYourLivesOutcome.HUNTED: 16,
    RunForYourLivesOutcome.ROBBED: 19,
    RunForYourLivesOutcome.SURROUNDED: 22,
    RunForYourLivesOutcome.TRAPPED: 25,
}


def source_consequence(
    outcome: RunForYourLivesOutcome = RunForYourLivesOutcome.ROBBED,
) -> RunForYourLivesCampaignConsequenceRequest:
    player_ids = ("hero", "ally", "scout")
    failed_count = (TABLE_TOTALS[outcome] + 9) // 10
    return RunForYourLivesCampaignConsequenceRequest(
        id=f"campaign-follow-up:{outcome.value}",
        source_request_id="run-for-your-lives:1",
        battle_id="battle:1",
        retreat_id="retreat:battle:1:round:3",
        player_character_ids=player_ids,
        cover_kind=RetreatCoverKind.FATE_REARGUARD,
        cover_proof_id="proof:tactical-retreat:1",
        rearguard_actor_id="hero",
        failed_actor_ids=player_ids[:failed_count],
        complication_ids=(),
        table_total=TABLE_TOTALS[outcome],
        outcome=outcome,
    )


def specification(
    outcome: RunForYourLivesOutcome = RunForYourLivesOutcome.ROBBED,
) -> RunForYourLivesConsequenceSpecification:
    return RunForYourLivesConsequenceSpecification(
        id=f"specification:{outcome.value}:1",
        outcome=outcome,
        description_reference_id=f"gm-description:{outcome.value}:1",
        affected_subject_reference_ids=(
            "actor:hero",
            "actor:ally",
            "actor:scout",
        ),
        concrete_consequence_reference_ids=(f"effect:{outcome.value}:1",),
    )


def application_request(
    outcome: RunForYourLivesOutcome = RunForYourLivesOutcome.ROBBED,
    *,
    state: CampaignConsequenceState | None = None,
) -> RunForYourLivesCampaignApplicationRequest:
    return RunForYourLivesCampaignApplicationRequest(
        id=f"application:{outcome.value}:1",
        source_consequence=source_consequence(outcome),
        campaign_state=state or CampaignConsequenceState("campaign:1"),
        consequence_id=f"consequence:{outcome.value}:1",
        specification=specification(outcome),
    )


class K1RunForYourLivesCampaignResolutionTests(unittest.TestCase):
    def test_registers_explicit_fact_without_executing_consequence(self) -> None:
        request = application_request()

        result = register_run_for_your_lives_campaign_consequence(request)

        self.assertEqual(result.previous_state, request.campaign_state)
        self.assertEqual(result.state.consequences, (result.consequence,))
        self.assertIs(result.consequence.outcome, RunForYourLivesOutcome.ROBBED)
        self.assertEqual(
            result.consequence.specification.concrete_consequence_reference_ids,
            ("effect:robbed:1",),
        )
        self.assertFalse(hasattr(result.consequence, "inventory_state"))
        self.assertEqual(request.campaign_state.consequences, ())

    def test_all_nine_book_outcomes_accept_matching_specification(self) -> None:
        for outcome in RunForYourLivesOutcome:
            with self.subTest(outcome=outcome):
                result = register_run_for_your_lives_campaign_consequence(
                    application_request(outcome)
                )
                self.assertIs(result.consequence.outcome, outcome)
                self.assertIs(result.consequence.specification.outcome, outcome)

    def test_specification_must_match_table_outcome(self) -> None:
        request = application_request(RunForYourLivesOutcome.LOST)
        with self.assertRaisesRegex(ValueError, "does not match"):
            replace(
                request,
                specification=specification(RunForYourLivesOutcome.MOCKED),
            )

    def test_specification_requires_explicit_stable_references(self) -> None:
        source = specification()
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            replace(source, affected_subject_reference_ids=())
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            replace(source, concrete_consequence_reference_ids=())
        with self.assertRaisesRegex(ValueError, "must be unique"):
            replace(
                source,
                affected_subject_reference_ids=("actor:hero", "actor:hero"),
            )

    def test_source_follow_up_is_one_shot_in_campaign_state(self) -> None:
        first = register_run_for_your_lives_campaign_consequence(
            application_request()
        )
        with self.assertRaisesRegex(ValueError, "already registered"):
            application_request(state=first.state)

    def test_state_and_result_reject_forged_provenance(self) -> None:
        result = register_run_for_your_lives_campaign_consequence(
            application_request()
        )
        with self.assertRaisesRegex(ValueError, "belong to the campaign"):
            CampaignConsequenceState(
                campaign_id="campaign:2",
                consequences=(result.consequence,),
            )
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, applied_rule_ids=())
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(
                result,
                consequence=replace(result.consequence, battle_id="battle:forged"),
            )
        with self.assertRaisesRegex(ValueError, "disagrees with table total"):
            replace(result.consequence, table_total=4)

    def test_registration_has_no_rng_or_specific_state_mutation_input(self) -> None:
        result = register_run_for_your_lives_campaign_consequence(
            application_request()
        )

        self.assertIsInstance(
            result,
            RunForYourLivesCampaignApplicationResult,
        )
        self.assertEqual(
            tuple(
                inspect.signature(
                    register_run_for_your_lives_campaign_consequence
                ).parameters
            ),
            ("request",),
        )
        self.assertEqual(result.consequence.battle_id, "battle:1")
        self.assertEqual(result.applied_rule_ids, (RUN_FOR_YOUR_LIVES_RULE_ID,))


if __name__ == "__main__":
    unittest.main()
