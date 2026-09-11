from __future__ import annotations

import inspect
import unittest
from dataclasses import replace

from towr.domain.campaign_consequence_models import (
    CampaignConsequenceState,
    RunForYourLivesCampaignApplicationRequest,
    RunForYourLivesConsequenceSpecification,
)
from towr.domain.campaign_trapped_other_models import (
    CampaignTrappedOtherCost,
    CampaignTrappedOtherState,
)
from towr.domain.retreat_models import (
    RUN_FOR_YOUR_LIVES_RULE_ID,
    RetreatCoverKind,
    RunForYourLivesCampaignConsequenceRequest,
    RunForYourLivesOutcome,
)
from towr.domain.run_for_your_lives_trapped_models import (
    RunForYourLivesTrappedCostRequest,
    TrappedEscapeCostDecision,
    TrappedEscapeCostKind,
)
from towr.domain.run_for_your_lives_trapped_other_models import (
    RunForYourLivesTrappedOtherRequest,
    RunForYourLivesTrappedOtherResult,
)
from towr.rules.run_for_your_lives_campaign_resolution import (
    register_run_for_your_lives_campaign_consequence,
)
from towr.rules.run_for_your_lives_trapped_other_resolution import (
    apply_run_for_your_lives_trapped_other,
)
from towr.rules.run_for_your_lives_trapped_resolution import (
    resolve_run_for_your_lives_trapped_cost,
)


def trapped_cost(
    kind: TrappedEscapeCostKind = TrappedEscapeCostKind.OTHER,
):
    references = (
        "escape-price:oath-to-the-crone",
        "escape-price:abandon-the-crossing",
    )
    source = RunForYourLivesCampaignConsequenceRequest(
        id="campaign-follow-up:trapped:other:1",
        source_request_id="run-for-your-lives:1",
        battle_id="battle:1",
        retreat_id="retreat:battle:1:round:3",
        player_character_ids=("hero", "ally", "scout"),
        cover_kind=RetreatCoverKind.FATE_REARGUARD,
        cover_proof_id="proof:fate-rearguard:1",
        rearguard_actor_id="hero",
        failed_actor_ids=("hero", "ally"),
        complication_ids=(),
        table_total=25,
        outcome=RunForYourLivesOutcome.TRAPPED,
    )
    registered = register_run_for_your_lives_campaign_consequence(
        RunForYourLivesCampaignApplicationRequest(
            id="application:trapped:other:campaign:1",
            source_consequence=source,
            campaign_state=CampaignConsequenceState("campaign:1"),
            consequence_id="consequence:trapped:other:1",
            specification=RunForYourLivesConsequenceSpecification(
                id="specification:trapped:other:1",
                outcome=RunForYourLivesOutcome.TRAPPED,
                description_reference_id="gm-description:trapped:other:1",
                affected_subject_reference_ids=("actor:hero", "actor:ally"),
                concrete_consequence_reference_ids=references,
            ),
        )
    )
    return resolve_run_for_your_lives_trapped_cost(
        RunForYourLivesTrappedCostRequest(
            id="trapped-cost:other:1",
            source_campaign=registered,
        ),
        TrappedEscapeCostDecision(
            id=f"decision:trapped:{kind.value}:1",
            cost_kind=kind,
            affected_actor_ids=("hero", "ally"),
            consequence_reference_ids=references,
        ),
    )


def other_request(
    *,
    source_cost=None,
    state: CampaignTrappedOtherState | None = None,
) -> RunForYourLivesTrappedOtherRequest:
    return RunForYourLivesTrappedOtherRequest(
        id="trapped-other:register:1",
        source_cost=source_cost or trapped_cost(),
        state=state or CampaignTrappedOtherState("campaign:1"),
        other_cost_id="trapped-other-cost:1",
    )


class K1RunForYourLivesTrappedOtherResolutionTests(unittest.TestCase):
    def test_registers_exact_opaque_price_with_closed_provenance(self) -> None:
        request = other_request()

        result = apply_run_for_your_lives_trapped_other(request)

        self.assertEqual(result.previous_state, request.state)
        self.assertEqual(result.state.costs, (result.cost,))
        self.assertEqual(result.cost.affected_actor_ids, ("hero", "ally"))
        self.assertEqual(
            result.cost.consequence_reference_ids,
            (
                "escape-price:oath-to-the-crone",
                "escape-price:abandon-the-crossing",
            ),
        )
        self.assertEqual(
            result.cost.description_reference_id,
            "gm-description:trapped:other:1",
        )
        self.assertEqual(
            result.cost.source_proof_id,
            request.source_cost.proof.id,
        )
        self.assertEqual(
            result.cost.source_decision_id,
            request.source_cost.decision.id,
        )

    def test_requires_other_branch(self) -> None:
        with self.assertRaisesRegex(ValueError, "not other"):
            other_request(
                source_cost=trapped_cost(TrappedEscapeCostKind.CAPTURE)
            )

    def test_registration_is_campaign_bound_and_one_shot(self) -> None:
        request = other_request()
        with self.assertRaisesRegex(ValueError, "another campaign"):
            replace(
                request,
                state=CampaignTrappedOtherState("campaign:other"),
            )

        result = apply_run_for_your_lives_trapped_other(request)
        with self.assertRaisesRegex(ValueError, "already consumed"):
            replace(request, state=result.state)

    def test_duplicate_record_id_is_rejected(self) -> None:
        first = apply_run_for_your_lives_trapped_other(other_request())
        existing = replace(
            first.cost,
            source_application_id="application:trapped:other:old",
            source_proof_id="proof:trapped:other:old",
            source_consequence_id="consequence:trapped:other:old",
            source_specification_id="specification:trapped:other:old",
            source_decision_id="decision:trapped:other:old",
        )
        state = CampaignTrappedOtherState("campaign:1", (existing,))

        with self.assertRaisesRegex(ValueError, "already registered"):
            other_request(state=state)

    def test_preserves_existing_cost_history(self) -> None:
        first = apply_run_for_your_lives_trapped_other(other_request())
        existing = replace(
            first.cost,
            id="trapped-other-cost:old",
            source_application_id="application:trapped:other:old",
            source_proof_id="proof:trapped:other:old",
            source_consequence_id="consequence:trapped:other:old",
            source_specification_id="specification:trapped:other:old",
            source_decision_id="decision:trapped:other:old",
        )
        state = CampaignTrappedOtherState("campaign:1", (existing,))

        result = apply_run_for_your_lives_trapped_other(
            other_request(state=state)
        )

        self.assertEqual(result.state.costs, (existing, result.cost))

    def test_state_and_result_reject_forged_provenance(self) -> None:
        result = apply_run_for_your_lives_trapped_other(other_request())
        with self.assertRaisesRegex(ValueError, "belong to the campaign"):
            CampaignTrappedOtherState("campaign:other", (result.cost,))
        with self.assertRaisesRegex(ValueError, "IDs must be unique"):
            CampaignTrappedOtherState(
                "campaign:1",
                (result.cost, result.cost),
            )
        with self.assertRaisesRegex(ValueError, "is stale"):
            replace(result, applied_rule_ids=())
        with self.assertRaisesRegex(ValueError, "is stale"):
            replace(
                result,
                cost=replace(
                    result.cost,
                    consequence_reference_ids=("escape-price:forged",),
                ),
            )

    def test_consumer_has_no_rng_or_universal_effect_inputs(self) -> None:
        result = apply_run_for_your_lives_trapped_other(other_request())

        self.assertIsInstance(result, RunForYourLivesTrappedOtherResult)
        self.assertIsInstance(result.cost, CampaignTrappedOtherCost)
        self.assertEqual(
            tuple(
                inspect.signature(
                    apply_run_for_your_lives_trapped_other
                ).parameters
            ),
            ("request",),
        )
        self.assertEqual(result.applied_rule_ids, (RUN_FOR_YOUR_LIVES_RULE_ID,))
        self.assertFalse(hasattr(result.cost, "effect_kind"))
        self.assertFalse(hasattr(result, "injury_state"))
        self.assertFalse(hasattr(result, "inventory_state"))


if __name__ == "__main__":
    unittest.main()
