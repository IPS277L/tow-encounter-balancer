from __future__ import annotations

import unittest
from dataclasses import replace

from towr.domain.fate_models import (
    FATE_SESSION_RULE_ID,
    FATE_TACTICAL_RETREAT_RULE_ID,
    FateGloriousSpendRequest,
    FateSessionState,
    FateSpendKind,
    FateTacticalRetreatSpendRequest,
    prepare_retreat_alternative_price,
)
from towr.domain.injury_models import DecisionOwner
from towr.domain.retreat_models import (
    RETREAT_ALTERNATIVE_PRICE_RULE_ID,
    RETREAT_RULE_ID,
    GroupRetreatDeclaration,
    RetreatAlternativePrice,
    RetreatTiming,
)
from towr.domain.turn_models import (
    CombatRoundState,
    CombatSide,
    CombatTurnParticipant,
)
from towr.domain.test_models import TestProfile, TestRequest
from towr.rules.fate_resolution import (
    spend_fate_for_glorious,
    spend_fate_for_tactical_retreat,
)
from towr.rules.retreat_resolution import secure_group_retreat


def round_state(
    *,
    enemies_first: bool = False,
    completed: tuple[str, ...] = (),
) -> CombatRoundState:
    return CombatRoundState(
        round_number=3,
        participants=(
            CombatTurnParticipant("hero", CombatSide.PLAYERS_AND_ALLIES),
            CombatTurnParticipant("ally", CombatSide.PLAYERS_AND_ALLIES),
            CombatTurnParticipant("escort", CombatSide.PLAYERS_AND_ALLIES),
            CombatTurnParticipant("enemy:1", CombatSide.OPPOSITION),
            CombatTurnParticipant("enemy:2", CombatSide.OPPOSITION),
        ),
        side_order=(
            (CombatSide.OPPOSITION, CombatSide.PLAYERS_AND_ALLIES)
            if enemies_first
            else (CombatSide.PLAYERS_AND_ALLIES, CombatSide.OPPOSITION)
        ),
        completed_turn_entity_ids=completed,
    )


def retreat_declaration(
    *,
    state: CombatRoundState | None = None,
) -> GroupRetreatDeclaration:
    return GroupRetreatDeclaration(
        id="retreat:battle:1:round:3",
        battle_id="battle:1",
        initiator_actor_id="ally",
        player_character_ids=("hero", "ally"),
        consenting_player_character_ids=("ally", "hero"),
        round_state=state or round_state(),
    )


def fate_state(actor_id: str, *, remaining: int = 1) -> FateSessionState:
    return FateSessionState(
        session_id="session:1",
        actor_id=actor_id,
        rating=1,
        session_spend_limit=remaining,
    )


class K1GroupRetreatDeclarationTests(unittest.TestCase):
    def test_unanimous_group_can_retreat_at_start_of_round(self) -> None:
        retreat = retreat_declaration()

        self.assertIs(retreat.timing, RetreatTiming.START_OF_ROUND)
        self.assertEqual(retreat.player_character_ids, ("hero", "ally"))
        self.assertNotIn("escort", retreat.player_character_ids)
        self.assertEqual(retreat.rule_id, RETREAT_RULE_ID)

    def test_group_can_retreat_when_players_side_starts_after_enemies(self) -> None:
        retreat = retreat_declaration(
            state=round_state(
                enemies_first=True,
                completed=("enemy:1", "enemy:2"),
            )
        )

        self.assertIs(retreat.timing, RetreatTiming.START_OF_PLAYERS_SIDE)

    def test_non_unanimous_or_late_retreat_is_rejected(self) -> None:
        source = retreat_declaration()
        with self.assertRaisesRegex(ValueError, "unanimous"):
            replace(source, consenting_player_character_ids=("hero",))
        with self.assertRaisesRegex(ValueError, "start of the round"):
            replace(
                source,
                round_state=round_state(completed=("hero",)),
            )
        with self.assertRaisesRegex(ValueError, "start of the players side"):
            replace(
                source,
                round_state=round_state(
                    enemies_first=True,
                    completed=("enemy:1",),
                ),
            )
        with self.assertRaisesRegex(ValueError, "when enemies act first"):
            replace(
                source,
                round_state=round_state(enemies_first=True),
            )

    def test_group_and_initiator_must_be_known_player_side_members(self) -> None:
        source = retreat_declaration()
        with self.assertRaisesRegex(ValueError, "initiator"):
            replace(source, initiator_actor_id="escort")
        with self.assertRaisesRegex(ValueError, "players side"):
            replace(
                source,
                initiator_actor_id="hero",
                player_character_ids=("hero", "enemy:1"),
                consenting_player_character_ids=("hero", "enemy:1"),
            )


class K1FateTacticalRetreatTests(unittest.TestCase):
    def test_spend_binds_one_group_member_as_rearguard(self) -> None:
        retreat = retreat_declaration()
        source_state = fate_state("hero")

        result = spend_fate_for_tactical_retreat(
            FateTacticalRetreatSpendRequest(
                id="spend:retreat:hero",
                state=source_state,
                retreat=retreat,
            )
        )

        self.assertEqual(source_state.remaining_spends, 1)
        self.assertEqual(result.state.remaining_spends, 0)
        self.assertIs(result.spend.kind, FateSpendKind.TACTICAL_RETREAT)
        self.assertEqual(result.spend.subject_id, retreat.id)
        self.assertEqual(result.proof.actor_id, "hero")
        self.assertEqual(result.proof.retreat_id, retreat.id)
        self.assertEqual(result.proof.battle_id, retreat.battle_id)
        self.assertEqual(
            result.proof.player_character_ids,
            retreat.player_character_ids,
        )
        self.assertEqual(result.retreat_result.rearguard_actor_id, "hero")
        self.assertEqual(
            result.retreat_result.covered_player_character_ids,
            ("hero", "ally"),
        )
        self.assertTrue(result.retreat_result.pursuit_decision_required)
        self.assertEqual(
            result.applied_rule_ids,
            (
                FATE_SESSION_RULE_ID,
                RETREAT_RULE_ID,
                FATE_TACTICAL_RETREAT_RULE_ID,
            ),
        )

    def test_non_group_actor_and_duplicate_retreat_spend_are_rejected(self) -> None:
        retreat = retreat_declaration()
        with self.assertRaisesRegex(ValueError, "does not belong"):
            FateTacticalRetreatSpendRequest(
                id="spend:escort",
                state=fate_state("escort"),
                retreat=retreat,
            )

        first = spend_fate_for_tactical_retreat(
            FateTacticalRetreatSpendRequest(
                id="spend:first",
                state=FateSessionState("session:1", "hero", 2, 2),
                retreat=retreat,
            )
        )
        with self.assertRaisesRegex(ValueError, "already spent"):
            FateTacticalRetreatSpendRequest(
                id="spend:second",
                state=first.state,
                retreat=retreat,
            )

    def test_retreat_shares_the_session_pool_with_glorious(self) -> None:
        glorious = spend_fate_for_glorious(
            FateGloriousSpendRequest(
                id="spend:glorious",
                state=FateSessionState("session:1", "hero", 2, 2),
                test=TestRequest("test:hero", TestProfile(2, 5)),
            )
        )
        retreat = spend_fate_for_tactical_retreat(
            FateTacticalRetreatSpendRequest(
                id="spend:retreat",
                state=glorious.state,
                retreat=retreat_declaration(),
            )
        )

        self.assertEqual(retreat.state.remaining_spends, 0)
        self.assertEqual(
            tuple(item.kind for item in retreat.state.spends),
            (
                FateSpendKind.GLORIOUS_TEST,
                FateSpendKind.TACTICAL_RETREAT,
            ),
        )

    def test_retreat_cannot_be_secured_with_mismatched_or_forged_proof(self) -> None:
        result = spend_fate_for_tactical_retreat(
            FateTacticalRetreatSpendRequest(
                id="spend:retreat",
                state=fate_state("hero"),
                retreat=retreat_declaration(),
            )
        )
        with self.assertRaisesRegex(ValueError, "another group Retreat"):
            secure_group_retreat(
                replace(result.source_request.retreat, battle_id="battle:2"),
                fate_proof=result.proof,
            )
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, state=result.previous_state)
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(
                result,
                retreat_result=replace(
                    result.retreat_result,
                    fate_proof_id="proof:forged",
                ),
            )

    def test_unknown_rule_is_rejected_before_spend_result(self) -> None:
        request = FateTacticalRetreatSpendRequest(
            id="spend:unknown",
            state=fate_state("hero"),
            retreat=retreat_declaration(),
            rule_id="RULE-UNKNOWN",
        )
        with self.assertRaisesRegex(ValueError, "unknown rule"):
            spend_fate_for_tactical_retreat(request)


class K1RetreatAlternativePriceTests(unittest.TestCase):
    def test_exhausted_group_produces_gm_owned_price_request(self) -> None:
        request = prepare_retreat_alternative_price(
            request_id="retreat:price:1",
            retreat=retreat_declaration(),
            fate_states=(
                fate_state("ally", remaining=0),
                fate_state("hero", remaining=0),
            ),
        )

        self.assertIs(request.decision_owner, DecisionOwner.GM)
        self.assertEqual(
            request.possible_prices,
            (
                RetreatAlternativePrice.BLOOD,
                RetreatAlternativePrice.MATERIEL,
                RetreatAlternativePrice.MISFORTUNE,
            ),
        )
        self.assertEqual(request.rule_id, RETREAT_ALTERNATIVE_PRICE_RULE_ID)

    def test_price_requires_full_group_and_no_remaining_fate(self) -> None:
        retreat = retreat_declaration()
        with self.assertRaisesRegex(ValueError, "full group"):
            prepare_retreat_alternative_price(
                request_id="retreat:price:partial",
                retreat=retreat,
                fate_states=(fate_state("hero", remaining=0),),
            )
        with self.assertRaisesRegex(ValueError, "exhausted"):
            prepare_retreat_alternative_price(
                request_id="retreat:price:available",
                retreat=retreat,
                fate_states=(
                    fate_state("hero", remaining=0),
                    fate_state("ally", remaining=1),
                ),
            )


if __name__ == "__main__":
    unittest.main()
