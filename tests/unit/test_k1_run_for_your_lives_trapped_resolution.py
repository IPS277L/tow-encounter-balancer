from __future__ import annotations

import inspect
import unittest
from dataclasses import replace

from towr.domain.campaign_consequence_models import (
    CampaignConsequenceState,
    RunForYourLivesCampaignApplicationRequest,
    RunForYourLivesConsequenceSpecification,
)
from towr.domain.injury_models import DecisionOwner
from towr.domain.retreat_models import (
    RUN_FOR_YOUR_LIVES_RULE_ID,
    RetreatCoverKind,
    RunForYourLivesCampaignConsequenceRequest,
    RunForYourLivesOutcome,
)
from towr.domain.run_for_your_lives_trapped_models import (
    RunForYourLivesTrappedCostRequest,
    RunForYourLivesTrappedCostResult,
    TrappedCaptureCostApplicationRequest,
    TrappedEscapeCostDecision,
    TrappedEscapeCostKind,
    TrappedOtherCostApplicationRequest,
    TrappedWoundCostApplicationRequest,
)
from towr.rules.run_for_your_lives_campaign_resolution import (
    register_run_for_your_lives_campaign_consequence,
)
from towr.rules.run_for_your_lives_trapped_resolution import (
    resolve_run_for_your_lives_trapped_cost,
)


def registered_outcome(
    outcome: RunForYourLivesOutcome = RunForYourLivesOutcome.TRAPPED,
    *,
    cover_kind: RetreatCoverKind = RetreatCoverKind.FATE_REARGUARD,
):
    source = RunForYourLivesCampaignConsequenceRequest(
        id=f"campaign-follow-up:{outcome.value}:{cover_kind.value}",
        source_request_id="run-for-your-lives:1",
        battle_id="battle:1",
        retreat_id="retreat:battle:1:round:3",
        player_character_ids=("hero", "ally", "scout"),
        cover_kind=cover_kind,
        cover_proof_id=f"proof:{cover_kind.value}:1",
        rearguard_actor_id=(
            "hero" if cover_kind is RetreatCoverKind.FATE_REARGUARD else None
        ),
        failed_actor_ids=("hero", "ally", "scout"),
        complication_ids=(),
        table_total=25 if outcome is RunForYourLivesOutcome.TRAPPED else 19,
        outcome=outcome,
    )
    specification = RunForYourLivesConsequenceSpecification(
        id=f"specification:{outcome.value}:1",
        outcome=outcome,
        description_reference_id=f"gm-description:{outcome.value}:1",
        affected_subject_reference_ids=("actor:ally",),
        concrete_consequence_reference_ids=("cost:escape:ally",),
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


def trapped_request(
    *,
    source_campaign=None,
    consumed_consequence_ids: tuple[str, ...] = (),
) -> RunForYourLivesTrappedCostRequest:
    return RunForYourLivesTrappedCostRequest(
        id="trapped-cost:1",
        source_campaign=source_campaign or registered_outcome(),
        consumed_consequence_ids=consumed_consequence_ids,
    )


def decision(
    kind: TrappedEscapeCostKind = TrappedEscapeCostKind.WOUNDS,
    *,
    affected_actor_ids: tuple[str, ...] = ("ally",),
) -> TrappedEscapeCostDecision:
    return TrappedEscapeCostDecision(
        id=f"decision:trapped:{kind.value}",
        cost_kind=kind,
        affected_actor_ids=affected_actor_ids,
        consequence_reference_ids=("cost:escape:ally",),
    )


class K1RunForYourLivesTrappedResolutionTests(unittest.TestCase):
    def test_wound_cost_creates_bound_follow_up_without_applying_wounds(self) -> None:
        request = trapped_request()

        result = resolve_run_for_your_lives_trapped_cost(request, decision())

        self.assertIsInstance(
            result.application_request,
            TrappedWoundCostApplicationRequest,
        )
        self.assertEqual(result.proof.affected_actor_ids, ("ally",))
        self.assertEqual(result.proof.rearguard_actor_id, "hero")
        self.assertEqual(
            result.application_request.source_proof_id,
            result.proof.id,
        )
        self.assertFalse(hasattr(result.application_request, "injury_state"))

    def test_capture_and_other_costs_have_distinct_typed_follow_ups(self) -> None:
        cases = (
            (
                TrappedEscapeCostKind.CAPTURE,
                TrappedCaptureCostApplicationRequest,
            ),
            (TrappedEscapeCostKind.OTHER, TrappedOtherCostApplicationRequest),
        )
        for kind, expected_type in cases:
            with self.subTest(kind=kind):
                result = resolve_run_for_your_lives_trapped_cost(
                    trapped_request(),
                    decision(kind),
                )
                self.assertIsInstance(result.application_request, expected_type)

    def test_alternative_price_cover_does_not_infer_a_rearguard(self) -> None:
        source = registered_outcome(
            cover_kind=RetreatCoverKind.ALTERNATIVE_PRICE,
        )

        result = resolve_run_for_your_lives_trapped_cost(
            trapped_request(source_campaign=source),
            decision(affected_actor_ids=("ally",)),
        )

        self.assertIsNone(result.proof.rearguard_actor_id)
        self.assertEqual(result.proof.affected_actor_ids, ("ally",))

    def test_requires_trapped_source_and_gm_owned_decision(self) -> None:
        with self.assertRaisesRegex(ValueError, "not Trapped"):
            trapped_request(
                source_campaign=registered_outcome(RunForYourLivesOutcome.ROBBED)
            )
        with self.assertRaisesRegex(ValueError, "GM decides"):
            replace(decision(), decision_owner=DecisionOwner.ACTOR)

    def test_affected_actors_and_references_must_match_registered_context(self) -> None:
        request = trapped_request()
        with self.assertRaisesRegex(ValueError, "player group order"):
            resolve_run_for_your_lives_trapped_cost(
                request,
                decision(affected_actor_ids=("unknown",)),
            )
        with self.assertRaisesRegex(ValueError, "player group order"):
            resolve_run_for_your_lives_trapped_cost(
                request,
                decision(affected_actor_ids=("scout", "ally")),
            )
        with self.assertRaisesRegex(ValueError, "consequence references"):
            resolve_run_for_your_lives_trapped_cost(
                request,
                replace(
                    decision(),
                    consequence_reference_ids=("cost:forged",),
                ),
            )

    def test_consequence_is_one_shot_and_result_provenance_is_closed(self) -> None:
        request = trapped_request()
        consequence_id = request.source_campaign.consequence.id
        with self.assertRaisesRegex(ValueError, "already consumed"):
            trapped_request(consumed_consequence_ids=(consequence_id,))

        result = resolve_run_for_your_lives_trapped_cost(request, decision())
        self.assertEqual(result.consumed_consequence_ids, (consequence_id,))
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, applied_rule_ids=())
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, proof=replace(result.proof, battle_id="battle:forged"))

    def test_resolver_has_no_rng_and_preserves_campaign_trace(self) -> None:
        result = resolve_run_for_your_lives_trapped_cost(
            trapped_request(),
            decision(),
        )

        self.assertIsInstance(result, RunForYourLivesTrappedCostResult)
        self.assertEqual(
            tuple(
                inspect.signature(
                    resolve_run_for_your_lives_trapped_cost
                ).parameters
            ),
            ("request", "decision"),
        )
        self.assertEqual(result.applied_rule_ids, (RUN_FOR_YOUR_LIVES_RULE_ID,))


if __name__ == "__main__":
    unittest.main()
