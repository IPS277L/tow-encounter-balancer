from __future__ import annotations

import inspect
import unittest
from dataclasses import replace

from towr.domain.campaign_consequence_models import (
    CampaignConsequenceState,
    RunForYourLivesCampaignApplicationRequest,
    RunForYourLivesConsequenceSpecification,
)
from towr.domain.inventory_models import CarriedInventoryState, TrappingSnapshot
from towr.domain.retreat_models import (
    RUN_FOR_YOUR_LIVES_RULE_ID,
    RetreatCoverKind,
    RunForYourLivesCampaignConsequenceRequest,
    RunForYourLivesOutcome,
)
from towr.domain.run_for_your_lives_robbed_models import (
    RobbedTrappingLossSelection,
    RunForYourLivesRobbedInventoryRequest,
    RunForYourLivesRobbedInventoryResult,
)
from towr.rules.run_for_your_lives_campaign_resolution import (
    register_run_for_your_lives_campaign_consequence,
)
from towr.rules.run_for_your_lives_robbed_resolution import (
    apply_run_for_your_lives_robbed,
)


def registered_outcome(
    outcome: RunForYourLivesOutcome = RunForYourLivesOutcome.ROBBED,
):
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
        table_total=19 if outcome is RunForYourLivesOutcome.ROBBED else 4,
        outcome=outcome,
    )
    specification = RunForYourLivesConsequenceSpecification(
        id=f"specification:{outcome.value}:1",
        outcome=outcome,
        description_reference_id=f"gm-description:{outcome.value}:1",
        affected_subject_reference_ids=("actor:hero", "actor:ally"),
        concrete_consequence_reference_ids=("loss:hero", "loss:ally"),
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


def trapping(owner: str, trapping_id: str) -> TrappingSnapshot:
    return TrappingSnapshot(
        id=trapping_id,
        definition_id=f"equipment:{trapping_id}",
        owner_actor_id=owner,
        is_valuable=False,
    )


def inventories() -> tuple[CarriedInventoryState, ...]:
    return (
        CarriedInventoryState(
            "hero",
            (
                trapping("hero", "greatsword"),
                trapping("hero", "bedroll"),
                trapping("hero", "rope"),
            ),
        ),
        CarriedInventoryState(
            "ally",
            (
                trapping("ally", "mail-shirt"),
                trapping("ally", "coins"),
            ),
        ),
    )


def selections() -> tuple[RobbedTrappingLossSelection, ...]:
    return (
        RobbedTrappingLossSelection(
            owner_actor_id="hero",
            trapping_ids=("greatsword", "bedroll"),
            consequence_reference_id="loss:hero",
        ),
        RobbedTrappingLossSelection(
            owner_actor_id="ally",
            trapping_ids=("mail-shirt",),
            consequence_reference_id="loss:ally",
        ),
    )


def robbed_request(
    *,
    carried: tuple[CarriedInventoryState, ...] | None = None,
    losses: tuple[RobbedTrappingLossSelection, ...] | None = None,
    consumed_consequence_ids: tuple[str, ...] = (),
) -> RunForYourLivesRobbedInventoryRequest:
    return RunForYourLivesRobbedInventoryRequest(
        id="robbed:apply:1",
        source_campaign=registered_outcome(),
        inventories=carried or inventories(),
        selections=losses or selections(),
        consumed_consequence_ids=consumed_consequence_ids,
    )


class K1RunForYourLivesRobbedResolutionTests(unittest.TestCase):
    def test_drops_explicit_trappings_for_every_pc_without_hidden_choice(self) -> None:
        request = robbed_request()

        result = apply_run_for_your_lives_robbed(request)

        self.assertEqual(
            tuple(transition.owner_actor_id for transition in result.transitions),
            ("hero", "ally"),
        )
        self.assertEqual(
            tuple(item.id for item in result.transitions[0].dropped_trappings),
            ("greatsword", "bedroll"),
        )
        self.assertEqual(
            tuple(item.id for item in result.transitions[0].inventory.trappings),
            ("rope",),
        )
        self.assertEqual(
            tuple(item.id for item in result.transitions[1].inventory.trappings),
            ("coins",),
        )
        self.assertEqual(request.inventories, inventories())

    def test_source_campaign_outcome_must_be_robbed(self) -> None:
        request = robbed_request()
        with self.assertRaisesRegex(ValueError, "not Robbed"):
            replace(
                request,
                source_campaign=registered_outcome(RunForYourLivesOutcome.MOCKED),
            )

    def test_inventories_and_selections_must_cover_ordered_pc_group(self) -> None:
        request = robbed_request()
        with self.assertRaisesRegex(ValueError, "ordered player group"):
            replace(request, inventories=tuple(reversed(request.inventories)))
        with self.assertRaisesRegex(ValueError, "cover the ordered player group"):
            replace(request, selections=request.selections[:1])

    def test_each_pc_must_have_explicit_carried_loss(self) -> None:
        request = robbed_request()
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            replace(request.selections[0], trapping_ids=())
        with self.assertRaisesRegex(ValueError, "not carried"):
            replace(
                request,
                selections=(
                    replace(
                        request.selections[0],
                        trapping_ids=("missing",),
                    ),
                    request.selections[1],
                ),
            )

    def test_loss_references_must_match_registered_specification(self) -> None:
        request = robbed_request()
        with self.assertRaisesRegex(ValueError, "consequence references"):
            replace(
                request,
                selections=(
                    replace(
                        request.selections[0],
                        consequence_reference_id="loss:forged",
                    ),
                    request.selections[1],
                ),
            )

    def test_consequence_is_one_shot_and_result_provenance_is_closed(self) -> None:
        request = robbed_request()
        consequence_id = request.source_campaign.consequence.id
        with self.assertRaisesRegex(ValueError, "already consumed"):
            replace(request, consumed_consequence_ids=(consequence_id,))

        result = apply_run_for_your_lives_robbed(request)
        self.assertEqual(result.consumed_consequence_ids, (consequence_id,))
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, applied_rule_ids=())
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, transitions=tuple(reversed(result.transitions)))

    def test_consumer_has_no_rng_and_preserves_registered_trace(self) -> None:
        result = apply_run_for_your_lives_robbed(robbed_request())

        self.assertIsInstance(result, RunForYourLivesRobbedInventoryResult)
        self.assertEqual(
            tuple(inspect.signature(apply_run_for_your_lives_robbed).parameters),
            ("request",),
        )
        self.assertEqual(result.applied_rule_ids, (RUN_FOR_YOUR_LIVES_RULE_ID,))
        self.assertEqual(
            result.transitions[0].consequence_reference_id,
            "loss:hero",
        )


if __name__ == "__main__":
    unittest.main()
