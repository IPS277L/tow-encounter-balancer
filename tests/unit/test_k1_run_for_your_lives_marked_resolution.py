from __future__ import annotations

import inspect
import unittest
from dataclasses import replace

from towr.domain.campaign_consequence_models import (
    CampaignConsequenceState,
    RunForYourLivesCampaignApplicationRequest,
    RunForYourLivesConsequenceSpecification,
)
from towr.domain.campaign_enemy_readiness_models import (
    CampaignEnemyReadiness,
    CampaignEnemyReadinessActivation,
    CampaignEnemyReadinessState,
)
from towr.domain.retreat_models import (
    RUN_FOR_YOUR_LIVES_RULE_ID,
    RetreatCoverKind,
    RunForYourLivesCampaignConsequenceRequest,
    RunForYourLivesOutcome,
)
from towr.domain.run_for_your_lives_marked_models import (
    RunForYourLivesMarkedActivationRequest,
    RunForYourLivesMarkedActivationResult,
    RunForYourLivesMarkedRegistrationRequest,
)
from towr.rules.run_for_your_lives_campaign_resolution import (
    register_run_for_your_lives_campaign_consequence,
)
from towr.rules.run_for_your_lives_marked_resolution import (
    activate_run_for_your_lives_marked,
    register_run_for_your_lives_marked,
)


def registered_outcome(
    outcome: RunForYourLivesOutcome = RunForYourLivesOutcome.MARKED,
):
    table_total = 10 if outcome is RunForYourLivesOutcome.MARKED else 13
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
            "enemy:black-orc-warband",
            "intelligence:stolen-march-plans",
            "trigger:party-moves-against-orcs",
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
    state: CampaignEnemyReadinessState | None = None,
) -> RunForYourLivesMarkedRegistrationRequest:
    return RunForYourLivesMarkedRegistrationRequest(
        id="marked:register:1",
        source_campaign=registered_outcome(),
        state=state or CampaignEnemyReadinessState("campaign:1"),
        readiness_id="enemy-readiness:black-orc-warband:1",
        enemy_reference_id="enemy:black-orc-warband",
        acquired_intelligence_reference_id="intelligence:stolen-march-plans",
        next_action_trigger_reference_id="trigger:party-moves-against-orcs",
    )


def registered_readiness():
    return register_run_for_your_lives_marked(registration_request())


def activation_request(
    *,
    state: CampaignEnemyReadinessState | None = None,
    readiness_id: str = "enemy-readiness:black-orc-warband:1",
    activation_id: str = "enemy-readiness-activation:black-orcs:1",
) -> RunForYourLivesMarkedActivationRequest:
    return RunForYourLivesMarkedActivationRequest(
        id=f"marked:activate:{activation_id}",
        state=state or registered_readiness().state,
        readiness_id=readiness_id,
        activation_id=activation_id,
        enemy_reference_id="enemy:black-orc-warband",
        next_action_trigger_reference_id="trigger:party-moves-against-orcs",
        action_event_reference_id="action:raid-black-orc-camp:day-15",
    )


class K1RunForYourLivesMarkedResolutionTests(unittest.TestCase):
    def test_registers_pending_readiness_with_closed_provenance(self) -> None:
        request = registration_request()

        result = register_run_for_your_lives_marked(request)

        self.assertEqual(result.previous_state, request.state)
        self.assertEqual(result.state.readiness_records, (result.readiness,))
        self.assertEqual(result.state.activations, ())
        self.assertFalse(result.state.is_activated(result.readiness.id))
        self.assertEqual(
            result.readiness.acquired_intelligence_reference_id,
            "intelligence:stolen-march-plans",
        )
        self.assertEqual(
            result.readiness.source_consequence_id,
            "consequence:marked:1",
        )

    def test_registration_requires_marked_and_exact_distinct_references(self) -> None:
        request = registration_request()
        with self.assertRaisesRegex(ValueError, "not Marked"):
            replace(
                request,
                source_campaign=registered_outcome(RunForYourLivesOutcome.EXPOSED),
            )
        with self.assertRaisesRegex(ValueError, "exactly match"):
            replace(request, enemy_reference_id="enemy:forged")
        with self.assertRaisesRegex(ValueError, "exactly match"):
            replace(
                request,
                acquired_intelligence_reference_id=(
                    request.next_action_trigger_reference_id
                ),
                next_action_trigger_reference_id=(
                    request.acquired_intelligence_reference_id
                ),
            )
        with self.assertRaisesRegex(ValueError, "must be unique"):
            replace(
                request,
                acquired_intelligence_reference_id=request.enemy_reference_id,
            )

    def test_registration_is_campaign_bound_one_shot_and_preserves_history(self) -> None:
        request = registration_request()
        with self.assertRaisesRegex(ValueError, "another campaign"):
            replace(request, state=CampaignEnemyReadinessState("campaign:2"))

        first = register_run_for_your_lives_marked(request)
        with self.assertRaisesRegex(ValueError, "already consumed"):
            registration_request(state=first.state)

        existing = replace(
            first.readiness,
            id="enemy-readiness:old",
            source_application_id="application:marked:old",
            source_consequence_id="consequence:marked:old",
            source_specification_id="specification:marked:old",
        )
        state = CampaignEnemyReadinessState("campaign:1", (existing,))
        result = register_run_for_your_lives_marked(registration_request(state=state))
        self.assertEqual(
            result.state.readiness_records,
            (existing, result.readiness),
        )

    def test_state_rejects_orphan_cross_campaign_and_forged_linkage(self) -> None:
        readiness = registered_readiness().readiness
        activation = CampaignEnemyReadinessActivation(
            id="enemy-readiness-activation:1",
            campaign_id="campaign:1",
            readiness_id=readiness.id,
            enemy_reference_id=readiness.enemy_reference_id,
            next_action_trigger_reference_id=(
                readiness.next_action_trigger_reference_id
            ),
            action_event_reference_id="action:raid:1",
            rule_id=readiness.rule_id,
        )
        with self.assertRaisesRegex(ValueError, "no registered readiness"):
            CampaignEnemyReadinessState("campaign:1", activations=(activation,))
        with self.assertRaisesRegex(ValueError, "belong to the campaign"):
            CampaignEnemyReadinessState("campaign:2", (readiness,))
        with self.assertRaisesRegex(ValueError, "disagrees with enemy"):
            CampaignEnemyReadinessState(
                "campaign:1",
                (readiness,),
                (replace(activation, enemy_reference_id="enemy:forged"),),
            )
        with self.assertRaisesRegex(ValueError, "disagrees with trigger"):
            CampaignEnemyReadinessState(
                "campaign:1",
                (readiness,),
                (
                    replace(
                        activation,
                        next_action_trigger_reference_id="trigger:forged",
                    ),
                ),
            )

    def test_explicit_action_event_activates_matching_readiness(self) -> None:
        request = activation_request()

        result = activate_run_for_your_lives_marked(request)

        self.assertEqual(result.previous_state, request.state)
        self.assertEqual(result.state.readiness_records, request.state.readiness_records)
        self.assertEqual(result.state.activations, (result.activation,))
        self.assertTrue(result.state.is_activated(request.readiness_id))
        self.assertEqual(
            result.activation.action_event_reference_id,
            "action:raid-black-orc-camp:day-15",
        )

    def test_activation_requires_registered_unspent_matching_readiness(self) -> None:
        request = activation_request()
        with self.assertRaisesRegex(ValueError, "not registered"):
            replace(request, readiness_id="enemy-readiness:missing")
        with self.assertRaisesRegex(ValueError, "registered enemy"):
            replace(request, enemy_reference_id="enemy:forged")
        with self.assertRaisesRegex(ValueError, "registered trigger"):
            replace(
                request,
                next_action_trigger_reference_id="trigger:forged",
            )
        with self.assertRaisesRegex(ValueError, "must be distinct"):
            replace(
                request,
                action_event_reference_id=request.next_action_trigger_reference_id,
            )
        active = activate_run_for_your_lives_marked(request)
        with self.assertRaisesRegex(ValueError, "already activated"):
            replace(request, state=active.state)

    def test_one_action_event_can_activate_multiple_distinct_readiness_records(self) -> None:
        first = registered_readiness().readiness
        second = replace(
            first,
            id="enemy-readiness:black-orc-scouts:2",
            source_application_id="application:marked:2",
            source_consequence_id="consequence:marked:2",
            source_specification_id="specification:marked:2",
        )
        state = CampaignEnemyReadinessState("campaign:1", (first, second))
        first_result = activate_run_for_your_lives_marked(
            activation_request(state=state)
        )
        second_result = activate_run_for_your_lives_marked(
            activation_request(
                state=first_result.state,
                readiness_id=second.id,
                activation_id="enemy-readiness-activation:black-orc-scouts:2",
            )
        )
        self.assertEqual(len(second_result.state.activations), 2)
        self.assertTrue(second_result.state.is_activated(first.id))
        self.assertTrue(second_result.state.is_activated(second.id))

    def test_registration_and_activation_results_reject_forgery(self) -> None:
        registration = registered_readiness()
        with self.assertRaisesRegex(ValueError, "stale"):
            replace(registration, applied_rule_ids=())

        activation = activate_run_for_your_lives_marked(
            activation_request(state=registration.state)
        )
        self.assertIsInstance(activation, RunForYourLivesMarkedActivationResult)
        with self.assertRaisesRegex(ValueError, "stale"):
            replace(
                activation,
                activation=replace(
                    activation.activation,
                    action_event_reference_id="action:forged",
                ),
            )

    def test_consumers_have_no_rng_bonus_ambush_or_encounter_inputs(self) -> None:
        registration = registered_readiness()
        activation = activate_run_for_your_lives_marked(
            activation_request(state=registration.state)
        )

        self.assertIsInstance(registration.readiness, CampaignEnemyReadiness)
        self.assertEqual(
            tuple(inspect.signature(register_run_for_your_lives_marked).parameters),
            ("request",),
        )
        self.assertEqual(
            tuple(inspect.signature(activate_run_for_your_lives_marked).parameters),
            ("request",),
        )
        self.assertFalse(hasattr(activation, "bonus"))
        self.assertFalse(hasattr(activation, "encounter"))
        self.assertEqual(activation.applied_rule_ids, (RUN_FOR_YOUR_LIVES_RULE_ID,))


if __name__ == "__main__":
    unittest.main()
