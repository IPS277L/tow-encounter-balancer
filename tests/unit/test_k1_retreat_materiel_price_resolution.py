from __future__ import annotations

import unittest
from dataclasses import replace

from towr.domain.fate_models import FateSessionState, prepare_retreat_alternative_price
from towr.domain.inventory_models import CarriedInventoryState, TrappingSnapshot
from towr.domain.retreat_materiel_price_models import (
    RetreatMaterielPriceApplicationResult,
    RetreatMaterielPriceInventoryRequest,
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
from towr.rules.retreat_materiel_price_resolution import (
    apply_retreat_materiel_price,
)
from towr.rules.retreat_resolution import resolve_retreat_alternative_price


def alternative_price_cover(
    price: RetreatAlternativePrice = RetreatAlternativePrice.MATERIEL,
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


def trapping(
    trapping_id: str,
    *,
    owner_actor_id: str = "hero",
    valuable: bool = True,
) -> TrappingSnapshot:
    return TrappingSnapshot(
        id=trapping_id,
        definition_id=f"equipment:{trapping_id}",
        owner_actor_id=owner_actor_id,
        is_valuable=valuable,
    )


def inventory() -> CarriedInventoryState:
    return CarriedInventoryState(
        owner_actor_id="hero",
        trappings=(
            trapping("rope", valuable=False),
            trapping("silver-sword"),
            trapping("treasure-map"),
        ),
    )


def materiel_request(
    *,
    carried: CarriedInventoryState | None = None,
    consumed_application_ids: tuple[str, ...] = (),
) -> RetreatMaterielPriceInventoryRequest:
    return RetreatMaterielPriceInventoryRequest(
        id="retreat:materiel:apply:1",
        source_price=alternative_price_cover(),
        owner_actor_id="hero",
        selected_trapping_id="silver-sword",
        inventory=carried or inventory(),
        consumed_application_ids=consumed_application_ids,
    )


class K1RetreatMaterielPriceResolutionTests(unittest.TestCase):
    def test_explicit_valuable_trapping_is_removed_without_hidden_choice(
        self,
    ) -> None:
        request = materiel_request()

        result = apply_retreat_materiel_price(request)

        self.assertEqual(result.owner_actor_id, "hero")
        self.assertEqual(result.dropped_trapping.id, "silver-sword")
        self.assertEqual(result.previous_inventory, request.inventory)
        self.assertEqual(
            tuple(item.id for item in result.inventory.trappings),
            ("rope", "treasure-map"),
        )
        self.assertEqual(
            result.consumed_application_ids,
            (request.source_price.application_request.id,),
        )
        self.assertIn(
            RETREAT_ALTERNATIVE_PRICE_RULE_ID,
            result.applied_rule_ids,
        )
        self.assertEqual(
            tuple(item.id for item in request.inventory.trappings),
            ("rope", "silver-sword", "treasure-map"),
        )

    def test_owner_and_price_proof_must_match_the_retreat(self) -> None:
        source = materiel_request()
        with self.assertRaisesRegex(ValueError, "eligible PC"):
            replace(source, owner_actor_id="enemy")
        with self.assertRaisesRegex(ValueError, "another actor"):
            replace(source, owner_actor_id="ally")
        with self.assertRaisesRegex(ValueError, "not materiel"):
            replace(
                source,
                source_price=alternative_price_cover(
                    RetreatAlternativePrice.BLOOD
                ),
            )

    def test_selected_item_must_be_carried_and_valuable(self) -> None:
        source = materiel_request()
        with self.assertRaisesRegex(ValueError, "not carried"):
            replace(source, selected_trapping_id="missing")
        with self.assertRaisesRegex(ValueError, "valuable trapping"):
            replace(source, selected_trapping_id="rope")

    def test_inventory_snapshot_rejects_wrong_owner_and_duplicate_ids(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValueError, "inventory owner"):
            CarriedInventoryState(
                owner_actor_id="hero",
                trappings=(trapping("ally-item", owner_actor_id="ally"),),
            )
        item = trapping("duplicate")
        with self.assertRaisesRegex(ValueError, "must be unique"):
            CarriedInventoryState(
                owner_actor_id="hero",
                trappings=(item, item),
            )

    def test_application_is_one_shot(self) -> None:
        source = materiel_request()
        application_id = source.source_price.application_request.id
        with self.assertRaisesRegex(ValueError, "already consumed"):
            replace(
                source,
                consumed_application_ids=(application_id,),
            )

    def test_result_provenance_inventory_and_trace_are_closed(self) -> None:
        result = apply_retreat_materiel_price(materiel_request())
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, owner_actor_id="ally")
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(
                result,
                inventory=CarriedInventoryState(
                    owner_actor_id="hero",
                    trappings=(),
                ),
            )
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, applied_rule_ids=())

    def test_result_type_requires_exact_application_request(self) -> None:
        result = apply_retreat_materiel_price(materiel_request())
        self.assertIsInstance(result, RetreatMaterielPriceApplicationResult)
        with self.assertRaisesRegex(ValueError, "unknown rule"):
            replace(result.source_request, rule_id="RULE-UNKNOWN")


if __name__ == "__main__":
    unittest.main()
