from __future__ import annotations

import inspect
import unittest
from dataclasses import replace

from towr.domain.campaign_consequence_models import (
    CampaignConsequenceState,
    RunForYourLivesCampaignApplicationRequest,
    RunForYourLivesConsequenceSpecification,
)
from towr.domain.campaign_debt_models import (
    CampaignDebtObligation,
    CampaignDebtState,
)
from towr.domain.retreat_models import (
    RUN_FOR_YOUR_LIVES_RULE_ID,
    RetreatCoverKind,
    RunForYourLivesCampaignConsequenceRequest,
    RunForYourLivesOutcome,
)
from towr.domain.run_for_your_lives_indebted_models import (
    RunForYourLivesIndebtedRequest,
    RunForYourLivesIndebtedResult,
)
from towr.rules.run_for_your_lives_campaign_resolution import (
    register_run_for_your_lives_campaign_consequence,
)
from towr.rules.run_for_your_lives_indebted_resolution import (
    register_run_for_your_lives_indebted,
)


def registered_outcome(
    outcome: RunForYourLivesOutcome = RunForYourLivesOutcome.INDEBTED,
):
    table_total = 7 if outcome is RunForYourLivesOutcome.INDEBTED else 10
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
            "creditor:reikland-roadwardens",
            "debt:rescue-from-beastmen",
            "repayment:dangerous-official-service",
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


def indebted_request(
    *,
    state: CampaignDebtState | None = None,
) -> RunForYourLivesIndebtedRequest:
    return RunForYourLivesIndebtedRequest(
        id="indebted:register:1",
        source_campaign=registered_outcome(),
        state=state or CampaignDebtState("campaign:1"),
        obligation_id="debt-obligation:roadwardens:1",
        creditor_reference_id="creditor:reikland-roadwardens",
        debt_reference_id="debt:rescue-from-beastmen",
        repayment_reference_id="repayment:dangerous-official-service",
    )


class K1RunForYourLivesIndebtedResolutionTests(unittest.TestCase):
    def test_registers_outstanding_debt_with_closed_provenance(self) -> None:
        request = indebted_request()

        result = register_run_for_your_lives_indebted(request)

        self.assertEqual(result.previous_state, request.state)
        self.assertEqual(result.state.obligations, (result.obligation,))
        self.assertEqual(
            result.obligation.creditor_reference_id,
            "creditor:reikland-roadwardens",
        )
        self.assertEqual(
            result.obligation.affected_subject_reference_ids,
            ("actor:hero", "actor:ally"),
        )
        self.assertEqual(
            result.obligation.source_consequence_id,
            "consequence:indebted:1",
        )

    def test_source_campaign_outcome_must_be_indebted(self) -> None:
        request = indebted_request()
        with self.assertRaisesRegex(ValueError, "not Indebted"):
            replace(
                request,
                source_campaign=registered_outcome(RunForYourLivesOutcome.MARKED),
            )

    def test_role_references_are_distinct_and_match_registered_order(self) -> None:
        request = indebted_request()
        with self.assertRaisesRegex(ValueError, "exactly match"):
            replace(request, creditor_reference_id="creditor:forged")
        with self.assertRaisesRegex(ValueError, "exactly match"):
            replace(
                request,
                debt_reference_id=request.repayment_reference_id,
                repayment_reference_id=request.debt_reference_id,
            )
        with self.assertRaisesRegex(ValueError, "must be unique"):
            replace(request, debt_reference_id=request.creditor_reference_id)

    def test_registration_is_campaign_bound_and_one_shot(self) -> None:
        request = indebted_request()
        with self.assertRaisesRegex(ValueError, "another campaign"):
            replace(request, state=CampaignDebtState("campaign:2"))

        first = register_run_for_your_lives_indebted(request)
        with self.assertRaisesRegex(ValueError, "already consumed"):
            indebted_request(state=first.state)
        with self.assertRaisesRegex(ValueError, "already registered"):
            replace(
                indebted_request(
                    state=CampaignDebtState(
                        "campaign:1",
                        (
                            replace(
                                first.obligation,
                                source_application_id="application:indebted:old",
                                source_consequence_id="consequence:indebted:old",
                                source_specification_id="specification:indebted:old",
                            ),
                        ),
                    )
                ),
                obligation_id=first.obligation.id,
            )

    def test_preserves_existing_obligations(self) -> None:
        first = register_run_for_your_lives_indebted(indebted_request())
        existing = replace(
            first.obligation,
            id="debt-obligation:old",
            source_application_id="application:indebted:old",
            source_consequence_id="consequence:indebted:old",
            source_specification_id="specification:indebted:old",
        )
        state = CampaignDebtState("campaign:1", (existing,))

        result = register_run_for_your_lives_indebted(indebted_request(state=state))

        self.assertEqual(result.state.obligations, (existing, result.obligation))

    def test_state_and_result_reject_forged_provenance(self) -> None:
        result = register_run_for_your_lives_indebted(indebted_request())
        with self.assertRaisesRegex(ValueError, "belong to the campaign"):
            CampaignDebtState("campaign:2", (result.obligation,))
        with self.assertRaisesRegex(ValueError, "IDs must be unique"):
            CampaignDebtState(
                "campaign:1",
                (result.obligation, result.obligation),
            )
        with self.assertRaisesRegex(ValueError, "stale"):
            replace(result, applied_rule_ids=())
        with self.assertRaisesRegex(ValueError, "stale"):
            replace(
                result,
                obligation=replace(
                    result.obligation,
                    repayment_reference_id="repayment:forged",
                ),
            )

    def test_consumer_has_no_rng_payment_service_or_deadline_inputs(self) -> None:
        result = register_run_for_your_lives_indebted(indebted_request())

        self.assertIsInstance(result, RunForYourLivesIndebtedResult)
        self.assertIsInstance(result.obligation, CampaignDebtObligation)
        self.assertEqual(
            tuple(
                inspect.signature(
                    register_run_for_your_lives_indebted
                ).parameters
            ),
            ("request",),
        )
        self.assertFalse(hasattr(result.obligation, "amount"))
        self.assertFalse(hasattr(result.obligation, "deadline"))
        self.assertFalse(hasattr(result.obligation, "paid"))
        self.assertEqual(result.applied_rule_ids, (RUN_FOR_YOUR_LIVES_RULE_ID,))


if __name__ == "__main__":
    unittest.main()
