from __future__ import annotations

import inspect
import unittest
from dataclasses import replace

from towr.domain.campaign_captivity_models import (
    CampaignCaptivityRecord,
    CampaignCaptivityState,
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
from towr.domain.run_for_your_lives_trapped_capture_models import (
    RunForYourLivesTrappedCaptureRequest,
    RunForYourLivesTrappedCaptureResult,
    TrappedCaptureAssignment,
)
from towr.domain.run_for_your_lives_trapped_models import (
    RunForYourLivesTrappedCostRequest,
    TrappedEscapeCostDecision,
    TrappedEscapeCostKind,
)
from towr.rules.run_for_your_lives_campaign_resolution import (
    register_run_for_your_lives_campaign_consequence,
)
from towr.rules.run_for_your_lives_trapped_capture_resolution import (
    apply_run_for_your_lives_trapped_capture,
)
from towr.rules.run_for_your_lives_trapped_resolution import (
    resolve_run_for_your_lives_trapped_cost,
)


def trapped_cost(
    kind: TrappedEscapeCostKind = TrappedEscapeCostKind.CAPTURE,
    *,
    affected_actor_ids: tuple[str, ...] = ("hero", "ally"),
):
    consequence_references = tuple(
        f"capture:{actor_id}" for actor_id in affected_actor_ids
    )
    source = RunForYourLivesCampaignConsequenceRequest(
        id="campaign-follow-up:trapped:1",
        source_request_id="run-for-your-lives:1",
        battle_id="battle:1",
        retreat_id="retreat:battle:1:round:3",
        player_character_ids=("hero", "ally", "scout"),
        cover_kind=RetreatCoverKind.FATE_REARGUARD,
        cover_proof_id="proof:fate-rearguard:1",
        rearguard_actor_id="hero",
        failed_actor_ids=("hero", "ally", "scout"),
        complication_ids=(),
        table_total=25,
        outcome=RunForYourLivesOutcome.TRAPPED,
    )
    registered = register_run_for_your_lives_campaign_consequence(
        RunForYourLivesCampaignApplicationRequest(
            id="application:trapped:1",
            source_consequence=source,
            campaign_state=CampaignConsequenceState("campaign:1"),
            consequence_id="consequence:trapped:1",
            specification=RunForYourLivesConsequenceSpecification(
                id="specification:trapped:1",
                outcome=RunForYourLivesOutcome.TRAPPED,
                description_reference_id="gm-description:trapped:1",
                affected_subject_reference_ids=tuple(
                    f"actor:{actor_id}" for actor_id in affected_actor_ids
                ),
                concrete_consequence_reference_ids=consequence_references,
            ),
        )
    )
    return resolve_run_for_your_lives_trapped_cost(
        RunForYourLivesTrappedCostRequest(
            id="trapped-cost:1",
            source_campaign=registered,
        ),
        TrappedEscapeCostDecision(
            id=f"decision:trapped:{kind.value}",
            cost_kind=kind,
            affected_actor_ids=affected_actor_ids,
            consequence_reference_ids=consequence_references,
        ),
    )


def assignments() -> tuple[TrappedCaptureAssignment, ...]:
    return (
        TrappedCaptureAssignment(
            capture_id="captivity:hero:1",
            captive_actor_id="hero",
            captor_reference_id="enemy-warband:iron-claws",
            consequence_reference_id="capture:hero",
        ),
        TrappedCaptureAssignment(
            capture_id="captivity:ally:1",
            captive_actor_id="ally",
            captor_reference_id="enemy-warband:iron-claws",
            consequence_reference_id="capture:ally",
        ),
    )


def capture_request(
    *,
    source_cost=None,
    state: CampaignCaptivityState | None = None,
    selected: tuple[TrappedCaptureAssignment, ...] | None = None,
) -> RunForYourLivesTrappedCaptureRequest:
    return RunForYourLivesTrappedCaptureRequest(
        id="trapped-capture:1",
        source_cost=source_cost or trapped_cost(),
        state=state or CampaignCaptivityState("campaign:1"),
        assignments=selected or assignments(),
    )


def existing_capture(
    actor_id: str = "scout",
    *,
    record_id: str = "captivity:existing:1",
) -> CampaignCaptivityRecord:
    return CampaignCaptivityRecord(
        id=record_id,
        campaign_id="campaign:1",
        captive_actor_id=actor_id,
        captor_reference_id="enemy:old-captor",
        consequence_reference_id="capture:old",
        source_application_id="application:old",
        source_proof_id="proof:old",
        source_consequence_id="consequence:old",
        battle_id="battle:old",
        retreat_id="retreat:old",
        rule_id="RULE-CAMPAIGN:OLD-CAPTURE",
    )


class K1RunForYourLivesTrappedCaptureResolutionTests(unittest.TestCase):
    def test_registers_ordered_captures_with_explicit_captor_references(self) -> None:
        request = capture_request()

        result = apply_run_for_your_lives_trapped_capture(request)

        self.assertEqual(
            tuple(item.captive_actor_id for item in result.captures),
            ("hero", "ally"),
        )
        self.assertEqual(
            tuple(item.captor_reference_id for item in result.captures),
            (
                "enemy-warband:iron-claws",
                "enemy-warband:iron-claws",
            ),
        )
        self.assertEqual(result.previous_state, request.state)
        self.assertEqual(result.state.captures, result.captures)
        self.assertEqual(
            result.captures[0].source_proof_id,
            request.source_cost.proof.id,
        )
        self.assertEqual(
            result.captures[0].source_consequence_id,
            request.source_cost.proof.source_consequence_id,
        )

    def test_preserves_existing_captures_and_rejects_active_captive(self) -> None:
        existing = existing_capture()
        request = capture_request(
            state=CampaignCaptivityState("campaign:1", (existing,))
        )

        result = apply_run_for_your_lives_trapped_capture(request)

        self.assertEqual(result.state.captures[0], existing)
        self.assertEqual(len(result.state.captures), 3)
        with self.assertRaisesRegex(ValueError, "already captive"):
            capture_request(
                state=CampaignCaptivityState(
                    "campaign:1",
                    (existing_capture("hero"),),
                )
            )

    def test_requires_capture_branch(self) -> None:
        with self.assertRaisesRegex(ValueError, "not capture"):
            capture_request(
                source_cost=trapped_cost(TrappedEscapeCostKind.WOUNDS)
            )

    def test_assignments_must_match_actor_and_consequence_order(self) -> None:
        selected = assignments()
        with self.assertRaisesRegex(ValueError, "affected PC group order"):
            capture_request(selected=tuple(reversed(selected)))
        with self.assertRaisesRegex(ValueError, "consequence references"):
            capture_request(
                selected=(
                    replace(
                        selected[0],
                        consequence_reference_id="capture:forged",
                    ),
                    selected[1],
                )
            )
        with self.assertRaisesRegex(ValueError, "must be unique"):
            capture_request(
                selected=(
                    selected[0],
                    replace(selected[1], capture_id=selected[0].capture_id),
                )
            )

    def test_campaign_and_source_application_are_one_shot(self) -> None:
        request = capture_request()
        with self.assertRaisesRegex(ValueError, "another campaign"):
            replace(request, state=CampaignCaptivityState("campaign:other"))

        result = apply_run_for_your_lives_trapped_capture(request)
        with self.assertRaisesRegex(ValueError, "already consumed"):
            replace(request, state=result.state)

    def test_result_provenance_is_closed(self) -> None:
        result = apply_run_for_your_lives_trapped_capture(capture_request())

        with self.assertRaisesRegex(ValueError, "is stale"):
            replace(result, captures=tuple(reversed(result.captures)))
        with self.assertRaisesRegex(ValueError, "is stale"):
            replace(result, applied_rule_ids=())
        with self.assertRaisesRegex(ValueError, "is stale"):
            replace(
                result,
                state=replace(
                    result.state,
                    captures=(
                        *result.state.captures[:-1],
                        replace(
                            result.state.captures[-1],
                            captor_reference_id="enemy:forged",
                        ),
                    ),
                ),
            )

    def test_consumer_has_no_rng_or_unrelated_state(self) -> None:
        result = apply_run_for_your_lives_trapped_capture(capture_request())

        self.assertIsInstance(result, RunForYourLivesTrappedCaptureResult)
        self.assertEqual(
            tuple(
                inspect.signature(
                    apply_run_for_your_lives_trapped_capture
                ).parameters
            ),
            ("request",),
        )
        self.assertEqual(result.applied_rule_ids, (RUN_FOR_YOUR_LIVES_RULE_ID,))
        self.assertFalse(hasattr(result, "injury_state"))
        self.assertFalse(hasattr(result, "inventory_state"))


if __name__ == "__main__":
    unittest.main()
