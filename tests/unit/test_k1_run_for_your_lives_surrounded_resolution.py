from __future__ import annotations

import inspect
import unittest
from dataclasses import replace

from towr.domain.campaign_conflict_models import (
    CampaignConflictOpportunity,
    CampaignConflictOpportunityState,
)
from towr.domain.campaign_consequence_models import (
    CampaignConsequenceState,
    RunForYourLivesCampaignApplicationRequest,
    RunForYourLivesConsequenceSpecification,
)
from towr.domain.retreat_models import (
    RUN_FOR_YOUR_LIVES_RULE_ID,
    RetreatCoverKind,
    RunForYourLivesCampaignConsequenceRequest,
    RunForYourLivesOutcome,
)
from towr.domain.run_for_your_lives_surrounded_models import (
    RunForYourLivesSurroundedRequest,
    RunForYourLivesSurroundedResult,
)
from towr.rules.run_for_your_lives_campaign_resolution import (
    register_run_for_your_lives_campaign_consequence,
)
from towr.rules.run_for_your_lives_surrounded_resolution import (
    register_run_for_your_lives_surrounded,
)


def registered_outcome(
    outcome: RunForYourLivesOutcome = RunForYourLivesOutcome.SURROUNDED,
    *,
    application_id: str = "application:surrounded:1",
    consequence_id: str = "consequence:surrounded:1",
):
    table_total = 22 if outcome is RunForYourLivesOutcome.SURROUNDED else 19
    source = RunForYourLivesCampaignConsequenceRequest(
        id=f"campaign-follow-up:{outcome.value}",
        source_request_id="run-for-your-lives:1",
        battle_id="battle:1",
        retreat_id="retreat:battle:1:round:3",
        player_character_ids=("hero", "ally"),
        cover_kind=RetreatCoverKind.FATE_REARGUARD,
        cover_proof_id="proof:tactical-retreat:1",
        rearguard_actor_id="hero",
        failed_actor_ids=("hero", "ally"),
        complication_ids=(),
        table_total=table_total,
        outcome=outcome,
    )
    specification = RunForYourLivesConsequenceSpecification(
        id=f"specification:{outcome.value}:1",
        outcome=outcome,
        description_reference_id=f"gm-description:{outcome.value}:1",
        affected_subject_reference_ids=("actor:hero", "actor:ally"),
        concrete_consequence_reference_ids=(
            "opposition:roadwardens",
            "encounter-setup:blocked-crossroads",
        ),
    )
    return register_run_for_your_lives_campaign_consequence(
        RunForYourLivesCampaignApplicationRequest(
            id=application_id,
            source_consequence=source,
            campaign_state=CampaignConsequenceState("campaign:1"),
            consequence_id=consequence_id,
            specification=specification,
        )
    )


def surrounded_request(
    *,
    state: CampaignConflictOpportunityState | None = None,
) -> RunForYourLivesSurroundedRequest:
    return RunForYourLivesSurroundedRequest(
        id="surrounded:register:1",
        source_campaign=registered_outcome(),
        state=state or CampaignConflictOpportunityState("campaign:1"),
        opportunity_id="conflict-opportunity:crossroads:1",
        opposition_reference_id="opposition:roadwardens",
        encounter_setup_reference_id="encounter-setup:blocked-crossroads",
    )


class K1RunForYourLivesSurroundedResolutionTests(unittest.TestCase):
    def test_registers_explicit_conflict_hook_without_starting_it(self) -> None:
        request = surrounded_request()

        result = register_run_for_your_lives_surrounded(request)

        self.assertEqual(result.previous_state, request.state)
        self.assertEqual(result.state.opportunities, (result.opportunity,))
        self.assertEqual(
            result.opportunity.opposition_reference_id,
            "opposition:roadwardens",
        )
        self.assertEqual(
            result.opportunity.encounter_setup_reference_id,
            "encounter-setup:blocked-crossroads",
        )
        self.assertEqual(
            result.opportunity.affected_subject_reference_ids,
            ("actor:hero", "actor:ally"),
        )
        self.assertFalse(hasattr(result.opportunity, "battle_state"))
        self.assertFalse(hasattr(result.opportunity, "negotiation_result"))

    def test_source_campaign_outcome_must_be_surrounded(self) -> None:
        request = surrounded_request()
        with self.assertRaisesRegex(ValueError, "not Surrounded"):
            replace(
                request,
                source_campaign=registered_outcome(RunForYourLivesOutcome.ROBBED),
            )

    def test_role_references_exactly_match_registered_order(self) -> None:
        request = surrounded_request()
        with self.assertRaisesRegex(ValueError, "exactly match"):
            replace(
                request,
                opposition_reference_id="opposition:forged",
            )
        with self.assertRaisesRegex(ValueError, "exactly match"):
            replace(
                request,
                opposition_reference_id=request.encounter_setup_reference_id,
                encounter_setup_reference_id=request.opposition_reference_id,
            )
        with self.assertRaisesRegex(ValueError, "must be distinct"):
            replace(
                request,
                encounter_setup_reference_id=request.opposition_reference_id,
            )

    def test_state_rejects_cross_campaign_and_duplicate_records(self) -> None:
        result = register_run_for_your_lives_surrounded(surrounded_request())
        opportunity = result.opportunity
        with self.assertRaisesRegex(ValueError, "belong to the campaign"):
            CampaignConflictOpportunityState(
                campaign_id="campaign:2",
                opportunities=(opportunity,),
            )
        with self.assertRaisesRegex(ValueError, "IDs must be unique"):
            CampaignConflictOpportunityState(
                campaign_id="campaign:1",
                opportunities=(opportunity, opportunity),
            )

    def test_preserves_existing_hooks_and_consumes_consequence_once(self) -> None:
        first = register_run_for_your_lives_surrounded(surrounded_request())
        with self.assertRaisesRegex(ValueError, "already consumed"):
            surrounded_request(state=first.state)

        existing = replace(
            first.opportunity,
            id="conflict-opportunity:old",
            source_application_id="application:surrounded:old",
            source_consequence_id="consequence:surrounded:old",
            source_specification_id="specification:surrounded:old",
        )
        state = CampaignConflictOpportunityState("campaign:1", (existing,))
        result = register_run_for_your_lives_surrounded(surrounded_request(state=state))
        self.assertEqual(result.state.opportunities, (existing, result.opportunity))

    def test_result_provenance_and_state_are_closed(self) -> None:
        result = register_run_for_your_lives_surrounded(surrounded_request())
        self.assertIsInstance(result, RunForYourLivesSurroundedResult)
        with self.assertRaisesRegex(ValueError, "stale"):
            replace(result, applied_rule_ids=())
        with self.assertRaisesRegex(ValueError, "stale"):
            replace(
                result,
                opportunity=replace(
                    result.opportunity,
                    encounter_setup_reference_id="encounter-setup:forged",
                ),
            )

    def test_consumer_has_no_rng_or_conflict_resolution_inputs(self) -> None:
        result = register_run_for_your_lives_surrounded(surrounded_request())

        self.assertIsInstance(result.opportunity, CampaignConflictOpportunity)
        self.assertEqual(
            tuple(
                inspect.signature(
                    register_run_for_your_lives_surrounded
                ).parameters
            ),
            ("request",),
        )
        self.assertEqual(result.opportunity.source_application_id, "application:surrounded:1")
        self.assertEqual(result.opportunity.source_consequence_id, "consequence:surrounded:1")
        self.assertEqual(result.applied_rule_ids, (RUN_FOR_YOUR_LIVES_RULE_ID,))


if __name__ == "__main__":
    unittest.main()
