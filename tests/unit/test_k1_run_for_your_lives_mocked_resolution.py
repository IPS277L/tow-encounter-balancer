from __future__ import annotations

import inspect
import unittest
from dataclasses import replace

from towr.domain.campaign_consequence_models import (
    CampaignConsequenceState,
    RunForYourLivesCampaignApplicationRequest,
    RunForYourLivesConsequenceSpecification,
)
from towr.domain.campaign_reputation_models import (
    CampaignReputationConsequence,
    CampaignReputationState,
)
from towr.domain.retreat_models import (
    RUN_FOR_YOUR_LIVES_RULE_ID,
    RetreatCoverKind,
    RunForYourLivesCampaignConsequenceRequest,
    RunForYourLivesOutcome,
)
from towr.domain.run_for_your_lives_mocked_models import (
    RunForYourLivesMockedRequest,
    RunForYourLivesMockedResult,
)
from towr.rules.run_for_your_lives_campaign_resolution import (
    register_run_for_your_lives_campaign_consequence,
)
from towr.rules.run_for_your_lives_mocked_resolution import (
    register_run_for_your_lives_mocked,
)


def registered_outcome(
    outcome: RunForYourLivesOutcome = RunForYourLivesOutcome.MOCKED,
):
    table_total = 4 if outcome is RunForYourLivesOutcome.MOCKED else 7
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
            "witness:rival-mercenary-company",
            "witness:ubersreik-bystanders",
            "gossip:failed-retreat-from-market-square",
            "reputation-effect:party-seen-as-cowards",
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


def mocked_request(
    *,
    state: CampaignReputationState | None = None,
) -> RunForYourLivesMockedRequest:
    return RunForYourLivesMockedRequest(
        id="mocked:register:1",
        source_campaign=registered_outcome(),
        state=state or CampaignReputationState("campaign:1"),
        reputation_consequence_id="reputation-consequence:market-square:1",
        witness_reference_ids=(
            "witness:rival-mercenary-company",
            "witness:ubersreik-bystanders",
        ),
        gossip_incident_reference_id="gossip:failed-retreat-from-market-square",
        reputation_effect_reference_id="reputation-effect:party-seen-as-cowards",
    )


class K1RunForYourLivesMockedResolutionTests(unittest.TestCase):
    def test_registers_reputation_consequence_with_closed_provenance(self) -> None:
        request = mocked_request()

        result = register_run_for_your_lives_mocked(request)

        self.assertEqual(result.previous_state, request.state)
        self.assertEqual(result.state.consequences, (result.consequence,))
        self.assertEqual(
            result.consequence.witness_reference_ids,
            (
                "witness:rival-mercenary-company",
                "witness:ubersreik-bystanders",
            ),
        )
        self.assertEqual(
            result.consequence.affected_subject_reference_ids,
            ("actor:hero", "actor:ally"),
        )
        self.assertEqual(
            result.consequence.source_consequence_id,
            "consequence:mocked:1",
        )

    def test_source_campaign_outcome_must_be_mocked(self) -> None:
        request = mocked_request()
        with self.assertRaisesRegex(ValueError, "not Mocked"):
            replace(
                request,
                source_campaign=registered_outcome(RunForYourLivesOutcome.INDEBTED),
            )

    def test_witnesses_are_non_empty_unique_and_roles_are_distinct(self) -> None:
        request = mocked_request()
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            replace(request, witness_reference_ids=())
        with self.assertRaisesRegex(ValueError, "must be unique"):
            replace(
                request,
                witness_reference_ids=("witness:rival", "witness:rival"),
            )
        with self.assertRaisesRegex(ValueError, "role references must be unique"):
            replace(
                request,
                reputation_effect_reference_id=request.witness_reference_ids[0],
            )

    def test_role_references_exactly_match_registered_order(self) -> None:
        request = mocked_request()
        with self.assertRaisesRegex(ValueError, "exactly match"):
            replace(
                request,
                witness_reference_ids=tuple(reversed(request.witness_reference_ids)),
            )
        with self.assertRaisesRegex(ValueError, "exactly match"):
            replace(
                request,
                gossip_incident_reference_id="gossip:forged",
            )

    def test_registration_is_campaign_bound_one_shot_and_preserves_history(self) -> None:
        first = register_run_for_your_lives_mocked(mocked_request())
        with self.assertRaisesRegex(ValueError, "already consumed"):
            mocked_request(state=first.state)
        with self.assertRaisesRegex(ValueError, "another campaign"):
            replace(mocked_request(), state=CampaignReputationState("campaign:2"))

        existing = replace(
            first.consequence,
            id="reputation-consequence:old",
            source_application_id="application:mocked:old",
            source_consequence_id="consequence:mocked:old",
            source_specification_id="specification:mocked:old",
        )
        state = CampaignReputationState("campaign:1", (existing,))
        result = register_run_for_your_lives_mocked(mocked_request(state=state))
        self.assertEqual(
            result.state.consequences,
            (existing, result.consequence),
        )

    def test_state_and_result_reject_forged_provenance(self) -> None:
        result = register_run_for_your_lives_mocked(mocked_request())
        with self.assertRaisesRegex(ValueError, "belong to the campaign"):
            CampaignReputationState("campaign:2", (result.consequence,))
        with self.assertRaisesRegex(ValueError, "IDs must be unique"):
            CampaignReputationState(
                "campaign:1",
                (result.consequence, result.consequence),
            )
        with self.assertRaisesRegex(ValueError, "stale"):
            replace(result, applied_rule_ids=())
        with self.assertRaisesRegex(ValueError, "stale"):
            replace(
                result,
                consequence=replace(
                    result.consequence,
                    reputation_effect_reference_id="reputation-effect:forged",
                ),
            )

    def test_consumer_has_no_rng_numeric_penalty_or_duration_inputs(self) -> None:
        result = register_run_for_your_lives_mocked(mocked_request())

        self.assertIsInstance(result, RunForYourLivesMockedResult)
        self.assertIsInstance(result.consequence, CampaignReputationConsequence)
        self.assertEqual(
            tuple(
                inspect.signature(register_run_for_your_lives_mocked).parameters
            ),
            ("request",),
        )
        self.assertFalse(hasattr(result.consequence, "penalty"))
        self.assertFalse(hasattr(result.consequence, "duration"))
        self.assertFalse(hasattr(result.consequence, "social_scope"))
        self.assertEqual(result.applied_rule_ids, (RUN_FOR_YOUR_LIVES_RULE_ID,))


if __name__ == "__main__":
    unittest.main()
