from __future__ import annotations

import inspect
import unittest
from dataclasses import replace

from towr.domain.campaign_consequence_models import (
    CampaignConsequenceState,
    RunForYourLivesCampaignApplicationRequest,
    RunForYourLivesConsequenceSpecification,
)
from towr.domain.campaign_intelligence_models import (
    CampaignIntelligenceExposure,
    CampaignIntelligenceState,
)
from towr.domain.retreat_models import (
    RUN_FOR_YOUR_LIVES_RULE_ID,
    RetreatCoverKind,
    RunForYourLivesCampaignConsequenceRequest,
    RunForYourLivesOutcome,
)
from towr.domain.run_for_your_lives_exposed_models import (
    RunForYourLivesExposedRequest,
    RunForYourLivesExposedResult,
)
from towr.rules.run_for_your_lives_campaign_resolution import (
    register_run_for_your_lives_campaign_consequence,
)
from towr.rules.run_for_your_lives_exposed_resolution import (
    register_run_for_your_lives_exposed,
)


def registered_outcome(
    outcome: RunForYourLivesOutcome = RunForYourLivesOutcome.EXPOSED,
):
    table_total = 13 if outcome is RunForYourLivesOutcome.EXPOSED else 16
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
            "enemy:von-karstein-agent",
            "home:altdorf-townhouse",
            "shelter:innkeeper",
            "shelter:physician",
            "weakness:injured-sibling",
        ),
    )
    return register_run_for_your_lives_campaign_consequence(
        RunForYourLivesCampaignApplicationRequest(
            id=f"application:{outcome.value}:1",
            source_consequence=source,
            campaign_state=CampaignConsequenceState("campaign:1"),
            consequence_id=f"consequence:{outcome.value}:1",
            specification=specification,
        )
    )


def exposed_request(
    *,
    state: CampaignIntelligenceState | None = None,
) -> RunForYourLivesExposedRequest:
    return RunForYourLivesExposedRequest(
        id="exposed:register:1",
        source_campaign=registered_outcome(),
        state=state or CampaignIntelligenceState("campaign:1"),
        exposure_id="intelligence-exposure:vampire-agent:1",
        enemy_reference_id="enemy:von-karstein-agent",
        home_reference_id="home:altdorf-townhouse",
        shelter_reference_ids=("shelter:innkeeper", "shelter:physician"),
        weakness_reference_id="weakness:injured-sibling",
    )


class K1RunForYourLivesExposedResolutionTests(unittest.TestCase):
    def test_registers_explicit_intelligence_without_exploiting_it(self) -> None:
        request = exposed_request()

        result = register_run_for_your_lives_exposed(request)

        self.assertEqual(result.previous_state, request.state)
        self.assertEqual(result.state.exposures, (result.exposure,))
        self.assertEqual(result.exposure.enemy_reference_id, "enemy:von-karstein-agent")
        self.assertEqual(result.exposure.home_reference_id, "home:altdorf-townhouse")
        self.assertEqual(
            result.exposure.shelter_reference_ids,
            ("shelter:innkeeper", "shelter:physician"),
        )
        self.assertEqual(result.exposure.weakness_reference_id, "weakness:injured-sibling")
        self.assertFalse(hasattr(result.exposure, "attack_request"))

    def test_source_campaign_outcome_must_be_exposed(self) -> None:
        request = exposed_request()
        with self.assertRaisesRegex(ValueError, "not Exposed"):
            replace(
                request,
                source_campaign=registered_outcome(RunForYourLivesOutcome.HUNTED),
            )

    def test_shelters_are_non_empty_unique_and_roles_are_distinct(self) -> None:
        request = exposed_request()
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            replace(request, shelter_reference_ids=())
        with self.assertRaisesRegex(ValueError, "must be unique"):
            replace(
                request,
                shelter_reference_ids=("shelter:innkeeper", "shelter:innkeeper"),
            )
        with self.assertRaisesRegex(ValueError, "role references must be unique"):
            replace(request, weakness_reference_id=request.home_reference_id)

    def test_role_references_must_exactly_match_registered_order(self) -> None:
        request = exposed_request()
        with self.assertRaisesRegex(ValueError, "exactly match"):
            replace(request, enemy_reference_id="enemy:forged")
        with self.assertRaisesRegex(ValueError, "exactly match"):
            replace(
                request,
                shelter_reference_ids=tuple(reversed(request.shelter_reference_ids)),
            )

    def test_registration_is_campaign_bound_one_shot_and_preserves_history(self) -> None:
        first = register_run_for_your_lives_exposed(exposed_request())
        with self.assertRaisesRegex(ValueError, "already consumed"):
            exposed_request(state=first.state)
        with self.assertRaisesRegex(ValueError, "another campaign"):
            replace(exposed_request(), state=CampaignIntelligenceState("campaign:2"))

        existing = replace(
            first.exposure,
            id="intelligence-exposure:old",
            source_application_id="application:exposed:old",
            source_consequence_id="consequence:exposed:old",
            source_specification_id="specification:exposed:old",
        )
        state = CampaignIntelligenceState("campaign:1", (existing,))
        result = register_run_for_your_lives_exposed(exposed_request(state=state))
        self.assertEqual(result.state.exposures, (existing, result.exposure))

    def test_state_and_result_reject_forged_provenance(self) -> None:
        result = register_run_for_your_lives_exposed(exposed_request())
        with self.assertRaisesRegex(ValueError, "belong to the campaign"):
            CampaignIntelligenceState("campaign:2", (result.exposure,))
        with self.assertRaisesRegex(ValueError, "IDs must be unique"):
            CampaignIntelligenceState(
                "campaign:1",
                (result.exposure, result.exposure),
            )
        with self.assertRaisesRegex(ValueError, "stale"):
            replace(result, applied_rule_ids=())
        with self.assertRaisesRegex(ValueError, "stale"):
            replace(
                result,
                exposure=replace(
                    result.exposure,
                    weakness_reference_id="weakness:forged",
                ),
            )

    def test_consumer_has_no_rng_or_attack_selection_inputs(self) -> None:
        result = register_run_for_your_lives_exposed(exposed_request())

        self.assertIsInstance(result, RunForYourLivesExposedResult)
        self.assertIsInstance(result.exposure, CampaignIntelligenceExposure)
        self.assertEqual(
            tuple(inspect.signature(register_run_for_your_lives_exposed).parameters),
            ("request",),
        )
        self.assertEqual(result.exposure.source_application_id, "application:exposed:1")
        self.assertEqual(result.applied_rule_ids, (RUN_FOR_YOUR_LIVES_RULE_ID,))


if __name__ == "__main__":
    unittest.main()
