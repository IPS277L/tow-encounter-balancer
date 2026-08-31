from __future__ import annotations

import inspect
import unittest
from dataclasses import replace

from towr.domain.campaign_consequence_models import (
    CampaignConsequenceState,
    RunForYourLivesCampaignApplicationRequest,
    RunForYourLivesConsequenceSpecification,
)
from towr.domain.campaign_hunt_models import (
    CampaignHuntActivation,
    CampaignHuntState,
    CampaignHuntThreat,
)
from towr.domain.retreat_models import (
    RUN_FOR_YOUR_LIVES_RULE_ID,
    RetreatCoverKind,
    RunForYourLivesCampaignConsequenceRequest,
    RunForYourLivesOutcome,
)
from towr.domain.run_for_your_lives_hunted_models import (
    RunForYourLivesHuntedActivationRequest,
    RunForYourLivesHuntedActivationResult,
    RunForYourLivesHuntedRegistrationRequest,
    RunForYourLivesHuntedRegistrationResult,
)
from towr.rules.run_for_your_lives_campaign_resolution import (
    register_run_for_your_lives_campaign_consequence,
)
from towr.rules.run_for_your_lives_hunted_resolution import (
    activate_run_for_your_lives_hunted,
    register_run_for_your_lives_hunted,
)


def registered_outcome(
    outcome: RunForYourLivesOutcome = RunForYourLivesOutcome.HUNTED,
):
    table_total = 16 if outcome is RunForYourLivesOutcome.HUNTED else 19
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
            "pursuer:black-orc-warband",
            "trigger:party-leaves-safehouse",
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


def registration_request(
    *,
    state: CampaignHuntState | None = None,
) -> RunForYourLivesHuntedRegistrationRequest:
    return RunForYourLivesHuntedRegistrationRequest(
        id="hunted:register:1",
        source_campaign=registered_outcome(),
        state=state or CampaignHuntState("campaign:1"),
        threat_id="hunt:orc-warband:1",
        pursuer_reference_id="pursuer:black-orc-warband",
        activation_trigger_reference_id="trigger:party-leaves-safehouse",
    )


def registered_hunt() -> RunForYourLivesHuntedRegistrationResult:
    return register_run_for_your_lives_hunted(registration_request())


def activation_request(
    *,
    state: CampaignHuntState | None = None,
    threat_id: str = "hunt:orc-warband:1",
    activation_id: str = "hunt-activation:orc-warband:1",
) -> RunForYourLivesHuntedActivationRequest:
    return RunForYourLivesHuntedActivationRequest(
        id=f"hunted:activate:{activation_id}",
        state=state or registered_hunt().state,
        threat_id=threat_id,
        activation_id=activation_id,
        activation_trigger_reference_id="trigger:party-leaves-safehouse",
        movement_event_reference_id="movement:party-leaves-safehouse:day-12",
    )


class K1RunForYourLivesHuntedResolutionTests(unittest.TestCase):
    def test_registers_inactive_threat_with_closed_provenance(self) -> None:
        request = registration_request()

        result = register_run_for_your_lives_hunted(request)

        self.assertEqual(result.previous_state, request.state)
        self.assertEqual(result.state.threats, (result.threat,))
        self.assertEqual(result.state.activations, ())
        self.assertFalse(result.state.is_active(result.threat.id))
        self.assertEqual(
            result.threat.affected_subject_reference_ids,
            ("actor:hero", "actor:ally"),
        )
        self.assertEqual(result.threat.source_consequence_id, "consequence:hunted:1")

    def test_registration_requires_hunted_and_exact_role_references(self) -> None:
        request = registration_request()
        with self.assertRaisesRegex(ValueError, "not Hunted"):
            replace(
                request,
                source_campaign=registered_outcome(RunForYourLivesOutcome.ROBBED),
            )
        with self.assertRaisesRegex(ValueError, "exactly match"):
            replace(request, pursuer_reference_id="pursuer:forged")
        with self.assertRaisesRegex(ValueError, "exactly match"):
            replace(
                request,
                pursuer_reference_id=request.activation_trigger_reference_id,
                activation_trigger_reference_id=request.pursuer_reference_id,
            )
        with self.assertRaisesRegex(ValueError, "must be distinct"):
            replace(
                request,
                activation_trigger_reference_id=request.pursuer_reference_id,
            )

    def test_registration_is_campaign_bound_and_one_shot(self) -> None:
        request = registration_request()
        with self.assertRaisesRegex(ValueError, "another campaign"):
            replace(request, state=CampaignHuntState("campaign:2"))

        first = register_run_for_your_lives_hunted(request)
        with self.assertRaisesRegex(ValueError, "already consumed"):
            registration_request(state=first.state)
        with self.assertRaisesRegex(ValueError, "already registered"):
            replace(
                registration_request(
                    state=CampaignHuntState(
                        "campaign:1",
                        threats=(
                            replace(
                                first.threat,
                                source_consequence_id="consequence:hunted:old",
                            ),
                        ),
                    )
                ),
                threat_id=first.threat.id,
            )

    def test_state_rejects_orphan_cross_campaign_and_trigger_forgery(self) -> None:
        threat = registered_hunt().threat
        activation = CampaignHuntActivation(
            id="hunt-activation:1",
            campaign_id="campaign:1",
            threat_id=threat.id,
            activation_trigger_reference_id=threat.activation_trigger_reference_id,
            movement_event_reference_id="movement:1",
            rule_id=threat.rule_id,
        )
        with self.assertRaisesRegex(ValueError, "no registered threat"):
            CampaignHuntState("campaign:1", activations=(activation,))
        with self.assertRaisesRegex(ValueError, "belong to the campaign"):
            CampaignHuntState("campaign:2", threats=(threat,))
        with self.assertRaisesRegex(ValueError, "disagrees with threat trigger"):
            CampaignHuntState(
                "campaign:1",
                threats=(threat,),
                activations=(
                    replace(
                        activation,
                        activation_trigger_reference_id="trigger:forged",
                    ),
                ),
            )

    def test_explicit_movement_event_activates_registered_threat(self) -> None:
        request = activation_request()

        result = activate_run_for_your_lives_hunted(request)

        self.assertEqual(result.previous_state, request.state)
        self.assertEqual(result.state.threats, request.state.threats)
        self.assertEqual(result.state.activations, (result.activation,))
        self.assertTrue(result.state.is_active(request.threat_id))
        self.assertEqual(
            result.activation.movement_event_reference_id,
            "movement:party-leaves-safehouse:day-12",
        )

    def test_activation_requires_registered_inactive_matching_threat(self) -> None:
        request = activation_request()
        with self.assertRaisesRegex(ValueError, "not registered"):
            replace(request, threat_id="hunt:missing")
        with self.assertRaisesRegex(ValueError, "does not match"):
            replace(
                request,
                activation_trigger_reference_id="trigger:forged",
            )
        with self.assertRaisesRegex(ValueError, "must be distinct"):
            replace(
                request,
                movement_event_reference_id=request.activation_trigger_reference_id,
            )
        active = activate_run_for_your_lives_hunted(request)
        with self.assertRaisesRegex(ValueError, "already active"):
            replace(request, state=active.state)

    def test_one_movement_event_can_activate_multiple_distinct_threats(self) -> None:
        first = registered_hunt().threat
        second = replace(
            first,
            id="hunt:beastmen:2",
            pursuer_reference_id="pursuer:beastmen",
            source_application_id="application:hunted:2",
            source_consequence_id="consequence:hunted:2",
            source_specification_id="specification:hunted:2",
        )
        state = CampaignHuntState("campaign:1", threats=(first, second))
        first_result = activate_run_for_your_lives_hunted(
            activation_request(state=state)
        )
        second_result = activate_run_for_your_lives_hunted(
            activation_request(
                state=first_result.state,
                threat_id=second.id,
                activation_id="hunt-activation:beastmen:2",
            )
        )
        self.assertEqual(len(second_result.state.activations), 2)
        self.assertTrue(second_result.state.is_active(first.id))
        self.assertTrue(second_result.state.is_active(second.id))

    def test_registration_and_activation_results_reject_forgery(self) -> None:
        registration = registered_hunt()
        with self.assertRaisesRegex(ValueError, "stale"):
            replace(registration, applied_rule_ids=())

        activation = activate_run_for_your_lives_hunted(
            activation_request(state=registration.state)
        )
        self.assertIsInstance(activation, RunForYourLivesHuntedActivationResult)
        with self.assertRaisesRegex(ValueError, "stale"):
            replace(
                activation,
                activation=replace(
                    activation.activation,
                    movement_event_reference_id="movement:forged",
                ),
            )

    def test_both_consumers_have_no_rng_or_pursuit_inputs(self) -> None:
        registration = registered_hunt()
        activation = activate_run_for_your_lives_hunted(
            activation_request(state=registration.state)
        )

        self.assertIsInstance(registration.threat, CampaignHuntThreat)
        self.assertEqual(
            tuple(inspect.signature(register_run_for_your_lives_hunted).parameters),
            ("request",),
        )
        self.assertEqual(
            tuple(inspect.signature(activate_run_for_your_lives_hunted).parameters),
            ("request",),
        )
        self.assertFalse(hasattr(activation, "pursuit_result"))
        self.assertEqual(activation.applied_rule_ids, (RUN_FOR_YOUR_LIVES_RULE_ID,))


if __name__ == "__main__":
    unittest.main()
