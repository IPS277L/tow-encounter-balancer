from __future__ import annotations

import inspect
import unittest
from dataclasses import replace

from towr.domain.campaign_consequence_models import (
    CampaignConsequenceState,
    RunForYourLivesCampaignApplicationRequest,
    RunForYourLivesConsequenceSpecification,
)
from towr.domain.campaign_delay_models import (
    CampaignDelayConsequence,
    CampaignDelayState,
)
from towr.domain.retreat_models import (
    RUN_FOR_YOUR_LIVES_RULE_ID,
    RetreatCoverKind,
    RunForYourLivesCampaignConsequenceRequest,
    RunForYourLivesOutcome,
)
from towr.domain.run_for_your_lives_lost_models import (
    RunForYourLivesLostRequest,
    RunForYourLivesLostResult,
)
from towr.rules.run_for_your_lives_campaign_resolution import (
    register_run_for_your_lives_campaign_consequence,
)
from towr.rules.run_for_your_lives_lost_resolution import (
    register_run_for_your_lives_lost,
)


def registered_outcome(
    outcome: RunForYourLivesOutcome = RunForYourLivesOutcome.LOST,
):
    table_total = 1 if outcome is RunForYourLivesOutcome.LOST else 4
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
            "territory:unknown-drakwald-track",
            "destination:ubersreik-home",
            "delay:return-from-drakwald",
            "enemy-opportunity:beastmen-act-unhindered",
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


def lost_request(
    *,
    state: CampaignDelayState | None = None,
) -> RunForYourLivesLostRequest:
    return RunForYourLivesLostRequest(
        id="lost:register:1",
        source_campaign=registered_outcome(),
        state=state or CampaignDelayState("campaign:1"),
        delay_consequence_id="delay-consequence:drakwald:1",
        unfamiliar_territory_reference_id="territory:unknown-drakwald-track",
        intended_destination_reference_id="destination:ubersreik-home",
        return_delay_reference_id="delay:return-from-drakwald",
        enemy_opportunity_reference_id="enemy-opportunity:beastmen-act-unhindered",
    )


class K1RunForYourLivesLostResolutionTests(unittest.TestCase):
    def test_registers_delay_consequence_with_closed_provenance(self) -> None:
        request = lost_request()

        result = register_run_for_your_lives_lost(request)

        self.assertEqual(result.previous_state, request.state)
        self.assertEqual(result.state.consequences, (result.consequence,))
        self.assertEqual(
            result.consequence.unfamiliar_territory_reference_id,
            "territory:unknown-drakwald-track",
        )
        self.assertEqual(
            result.consequence.intended_destination_reference_id,
            "destination:ubersreik-home",
        )
        self.assertEqual(
            result.consequence.affected_subject_reference_ids,
            ("actor:hero", "actor:ally"),
        )
        self.assertEqual(
            result.consequence.source_consequence_id,
            "consequence:lost:1",
        )

    def test_source_campaign_outcome_must_be_lost(self) -> None:
        request = lost_request()
        with self.assertRaisesRegex(ValueError, "not Lost"):
            replace(
                request,
                source_campaign=registered_outcome(RunForYourLivesOutcome.MOCKED),
            )

    def test_role_references_are_distinct_and_match_registered_order(self) -> None:
        request = lost_request()
        with self.assertRaisesRegex(ValueError, "exactly match"):
            replace(
                request,
                unfamiliar_territory_reference_id="territory:forged",
            )
        with self.assertRaisesRegex(ValueError, "exactly match"):
            replace(
                request,
                return_delay_reference_id=request.enemy_opportunity_reference_id,
                enemy_opportunity_reference_id=request.return_delay_reference_id,
            )
        with self.assertRaisesRegex(ValueError, "must be unique"):
            replace(
                request,
                intended_destination_reference_id=(
                    request.unfamiliar_territory_reference_id
                ),
            )

    def test_registration_is_campaign_bound_and_one_shot(self) -> None:
        request = lost_request()
        with self.assertRaisesRegex(ValueError, "another campaign"):
            replace(request, state=CampaignDelayState("campaign:2"))

        first = register_run_for_your_lives_lost(request)
        with self.assertRaisesRegex(ValueError, "already consumed"):
            lost_request(state=first.state)
        with self.assertRaisesRegex(ValueError, "already registered"):
            replace(
                lost_request(
                    state=CampaignDelayState(
                        "campaign:1",
                        (
                            replace(
                                first.consequence,
                                source_application_id="application:lost:old",
                                source_consequence_id="consequence:lost:old",
                                source_specification_id="specification:lost:old",
                            ),
                        ),
                    )
                ),
                delay_consequence_id=first.consequence.id,
            )

    def test_preserves_existing_delay_history(self) -> None:
        first = register_run_for_your_lives_lost(lost_request())
        existing = replace(
            first.consequence,
            id="delay-consequence:old",
            source_application_id="application:lost:old",
            source_consequence_id="consequence:lost:old",
            source_specification_id="specification:lost:old",
        )
        state = CampaignDelayState("campaign:1", (existing,))

        result = register_run_for_your_lives_lost(lost_request(state=state))

        self.assertEqual(
            result.state.consequences,
            (existing, result.consequence),
        )

    def test_state_and_result_reject_forged_provenance(self) -> None:
        result = register_run_for_your_lives_lost(lost_request())
        with self.assertRaisesRegex(ValueError, "belong to the campaign"):
            CampaignDelayState("campaign:2", (result.consequence,))
        with self.assertRaisesRegex(ValueError, "IDs must be unique"):
            CampaignDelayState(
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
                    enemy_opportunity_reference_id="enemy-opportunity:forged",
                ),
            )

    def test_consumer_has_no_rng_duration_route_or_calendar_inputs(self) -> None:
        result = register_run_for_your_lives_lost(lost_request())

        self.assertIsInstance(result, RunForYourLivesLostResult)
        self.assertIsInstance(result.consequence, CampaignDelayConsequence)
        self.assertEqual(
            tuple(inspect.signature(register_run_for_your_lives_lost).parameters),
            ("request",),
        )
        self.assertFalse(hasattr(result.consequence, "duration"))
        self.assertFalse(hasattr(result.consequence, "route"))
        self.assertFalse(hasattr(result.consequence, "calendar_state"))
        self.assertEqual(result.applied_rule_ids, (RUN_FOR_YOUR_LIVES_RULE_ID,))


if __name__ == "__main__":
    unittest.main()
