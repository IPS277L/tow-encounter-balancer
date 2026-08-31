from __future__ import annotations

import inspect
import unittest
from dataclasses import replace

from towr.domain.campaign_opportunity_models import (
    CampaignGoldenOpportunity,
    CampaignGoldenOpportunityState,
)
from towr.domain.fate_models import FateSessionState, prepare_retreat_alternative_price
from towr.domain.retreat_misfortune_price_models import (
    RetreatMisfortunePriceApplicationResult,
    RetreatMisfortunePriceCampaignRequest,
)
from towr.domain.retreat_models import (
    RETREAT_ALTERNATIVE_PRICE_RULE_ID,
    GroupRetreatDeclaration,
    RetreatAlternativePrice,
    RetreatAlternativePriceDecision,
)
from towr.domain.turn_models import (
    CombatRoundState,
    CombatSide,
    CombatTurnParticipant,
)
from towr.rules.retreat_misfortune_price_resolution import (
    apply_retreat_misfortune_price,
)
from towr.rules.retreat_resolution import resolve_retreat_alternative_price


def alternative_price_cover(
    price: RetreatAlternativePrice = RetreatAlternativePrice.MISFORTUNE,
):
    retreat = GroupRetreatDeclaration(
        id="retreat:battle:1:round:3",
        battle_id="battle:1",
        initiator_actor_id="ally",
        player_character_ids=("hero", "ally"),
        consenting_player_character_ids=("ally", "hero"),
        round_state=CombatRoundState(
            round_number=3,
            participants=(
                CombatTurnParticipant("hero", CombatSide.PLAYERS_AND_ALLIES),
                CombatTurnParticipant("ally", CombatSide.PLAYERS_AND_ALLIES),
                CombatTurnParticipant("enemy", CombatSide.OPPOSITION),
                CombatTurnParticipant("enemy-2", CombatSide.OPPOSITION),
            ),
            side_order=(
                CombatSide.PLAYERS_AND_ALLIES,
                CombatSide.OPPOSITION,
            ),
        ),
    )
    request = prepare_retreat_alternative_price(
        request_id=f"retreat:price:{price.value}",
        retreat=retreat,
        fate_states=(
            FateSessionState("session:1", "hero", 1, 0),
            FateSessionState("session:1", "ally", 1, 0),
        ),
    )
    return resolve_retreat_alternative_price(
        request,
        RetreatAlternativePriceDecision(
            id=f"decision:retreat-price:{price.value}",
            price=price,
        ),
    )


def misfortune_request(
    *,
    campaign_state: CampaignGoldenOpportunityState | None = None,
) -> RetreatMisfortunePriceCampaignRequest:
    return RetreatMisfortunePriceCampaignRequest(
        id="retreat:misfortune:apply:1",
        source_price=alternative_price_cover(),
        campaign_state=campaign_state
        or CampaignGoldenOpportunityState(campaign_id="campaign:1"),
        beneficiary_enemy_id="enemy",
        golden_opportunity_id="opportunity:enemy:ambush",
        description_reference_id="gm-opportunity:enemy-ambush-after-retreat",
    )


class K1RetreatMisfortunePriceResolutionTests(unittest.TestCase):
    def test_registers_one_explicit_opportunity_without_executing_it(self) -> None:
        request = misfortune_request()

        result = apply_retreat_misfortune_price(request)

        self.assertEqual(result.previous_state, request.campaign_state)
        self.assertEqual(result.state.opportunities, (result.opportunity,))
        self.assertEqual(result.opportunity.beneficiary_enemy_id, "enemy")
        self.assertEqual(
            result.opportunity.description_reference_id,
            "gm-opportunity:enemy-ambush-after-retreat",
        )
        self.assertFalse(hasattr(result.opportunity, "executed"))
        self.assertEqual(request.campaign_state.opportunities, ())

    def test_price_proof_must_be_misfortune(self) -> None:
        source = misfortune_request()
        with self.assertRaisesRegex(ValueError, "not misfortune"):
            replace(
                source,
                source_price=alternative_price_cover(
                    RetreatAlternativePrice.MATERIEL
                ),
            )

    def test_beneficiary_must_belong_to_opposition_snapshot(self) -> None:
        source = misfortune_request()
        with self.assertRaisesRegex(ValueError, "eligible enemy"):
            replace(source, beneficiary_enemy_id="unknown-enemy")

    def test_campaign_state_rejects_cross_campaign_and_duplicate_facts(self) -> None:
        result = apply_retreat_misfortune_price(misfortune_request())
        opportunity = result.opportunity
        with self.assertRaisesRegex(ValueError, "belong to the campaign"):
            CampaignGoldenOpportunityState(
                campaign_id="campaign:2",
                opportunities=(opportunity,),
            )
        with self.assertRaisesRegex(ValueError, "IDs must be unique"):
            CampaignGoldenOpportunityState(
                campaign_id="campaign:1",
                opportunities=(opportunity, opportunity),
            )

    def test_application_is_one_shot_in_campaign_state(self) -> None:
        first = apply_retreat_misfortune_price(misfortune_request())
        with self.assertRaisesRegex(ValueError, "already consumed"):
            misfortune_request(campaign_state=first.state)

    def test_result_provenance_state_and_trace_are_closed(self) -> None:
        result = apply_retreat_misfortune_price(misfortune_request())
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, applied_rule_ids=())
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(
                result,
                opportunity=replace(
                    result.opportunity,
                    beneficiary_enemy_id="enemy-2",
                ),
            )

    def test_contract_has_no_rng_or_narrative_execution_input(self) -> None:
        request = misfortune_request()
        result = apply_retreat_misfortune_price(request)

        self.assertIsInstance(result, RetreatMisfortunePriceApplicationResult)
        self.assertEqual(
            tuple(inspect.signature(apply_retreat_misfortune_price).parameters),
            ("request",),
        )
        self.assertEqual(result.opportunity.battle_id, "battle:1")
        self.assertEqual(
            result.opportunity.source_application_id,
            request.source_price.application_request.id,
        )
        self.assertIn(RETREAT_ALTERNATIVE_PRICE_RULE_ID, result.applied_rule_ids)


if __name__ == "__main__":
    unittest.main()
