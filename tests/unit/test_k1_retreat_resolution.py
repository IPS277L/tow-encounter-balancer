from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
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
    RETREAT_PURSUIT_RULE_ID,
    RETREAT_RULE_ID,
    RUN_FOR_YOUR_LIVES_RULE_ID,
    GroupRetreatDeclaration,
    RetreatAlternativePrice,
    RetreatAlternativePriceDecision,
    RetreatBloodPriceApplicationRequest,
    RetreatCoverKind,
    RetreatEscapeAttempt,
    RetreatEscapeMethod,
    RetreatEscapeOutcome,
    RetreatMarginalChoice,
    RetreatMarginalDecision,
    RetreatMaterielPriceApplicationRequest,
    RetreatMisfortunePriceApplicationRequest,
    RetreatPursuitResolutionRequest,
    RetreatTiming,
    RunForYourLivesComplicationRollChoice,
    RunForYourLivesComplicationRollDecision,
    RunForYourLivesOutcome,
    RunForYourLivesResolutionRequest,
    RunForYourLivesRoll,
    RunForYourLivesRollReason,
    classify_run_for_your_lives,
)
from towr.domain.turn_models import (
    CombatRoundState,
    CombatSide,
    CombatTurnParticipant,
)
from towr.domain.test_models import (
    OpposedSide,
    OpposedTestRequest,
    Skill,
    TestProfile,
    TestRequest,
    TieBreak,
)
from towr.rules.fate_resolution import (
    spend_fate_for_glorious,
    spend_fate_for_tactical_retreat,
)
from towr.rules.retreat_resolution import (
    InvalidRetreatMarginalDecisionError,
    MissingRetreatMarginalDecisionError,
    resolve_retreat_alternative_price,
    resolve_retreat_pursuit,
    resolve_run_for_your_lives,
    secure_group_retreat,
)


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


def secured_retreat():
    return spend_fate_for_tactical_retreat(
        FateTacticalRetreatSpendRequest(
            id="spend:retreat:secured",
            state=fate_state("hero"),
            retreat=retreat_declaration(),
        )
    ).retreat_result


def alternative_price_cover(
    price: RetreatAlternativePrice = RetreatAlternativePrice.BLOOD,
):
    request = prepare_retreat_alternative_price(
        request_id=f"retreat:price:{price.value}",
        retreat=retreat_declaration(),
        fate_states=(
            fate_state("ally", remaining=0),
            fate_state("hero", remaining=0),
        ),
    )
    return resolve_retreat_alternative_price(
        request,
        RetreatAlternativePriceDecision(
            id=f"decision:retreat-price:{price.value}",
            price=price,
        ),
    )


def athletics_attempt(
    actor_id: str,
    *,
    test_id: str | None = None,
) -> RetreatEscapeAttempt:
    return RetreatEscapeAttempt(
        actor_id=actor_id,
        method=RetreatEscapeMethod.ATHLETICS_TEST,
        test=TestRequest(test_id or f"test:escape:{actor_id}", TestProfile(2, 5)),
        test_skill=Skill.ATHLETICS,
    )


def lore_attempt(actor_id: str) -> RetreatEscapeAttempt:
    return RetreatEscapeAttempt(
        actor_id=actor_id,
        method=RetreatEscapeMethod.LORE_AUTOMATIC_SUCCESS,
        lore_id=f"lore:escape:{actor_id}",
        automatic_success_approval_id=f"approval:escape:{actor_id}",
    )


def opposed_attempt(
    actor_id: str,
    *,
    enemy_id: str = "enemy:1",
    request_id: str | None = None,
) -> RetreatEscapeAttempt:
    suffix = request_id or actor_id
    return RetreatEscapeAttempt(
        actor_id=actor_id,
        method=RetreatEscapeMethod.OPPOSED_ATHLETICS_TEST,
        test=OpposedTestRequest(
            id=f"opposed:escape:{suffix}",
            initiator=TestRequest(
                f"test:escape:{suffix}:pc",
                TestProfile(1, 5),
            ),
            opponent=TestRequest(
                f"test:escape:{suffix}:enemy",
                TestProfile(1, 5),
            ),
            tie_break=TieBreak("RULE-TEST:escape-tie", OpposedSide.INITIATOR),
        ),
        test_skill=Skill.ATHLETICS,
        opposing_enemy_id=enemy_id,
    )


class FixedMarginalDecisions:
    def __init__(self, decisions: dict[int, RetreatMarginalDecision]) -> None:
        self.decisions = decisions
        self.calls: list[int] = []

    def choose_marginal_outcome(
        self,
        *,
        request: RetreatPursuitResolutionRequest,
        attempt_index: int,
        test_result: object,
    ) -> RetreatMarginalDecision:
        del request, test_result
        self.calls.append(attempt_index)
        return self.decisions[attempt_index]


class InvalidMarginalDecisions:
    def choose_marginal_outcome(
        self,
        *,
        request: RetreatPursuitResolutionRequest,
        attempt_index: int,
        test_result: object,
    ) -> object:
        del request, attempt_index, test_result
        return object()


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

    def test_blood_price_creates_one_wound_follow_up_without_target(self) -> None:
        result = alternative_price_cover(RetreatAlternativePrice.BLOOD)

        self.assertIs(result.decision.price, RetreatAlternativePrice.BLOOD)
        self.assertEqual(result.proof.price, RetreatAlternativePrice.BLOOD)
        self.assertEqual(result.proof.battle_id, "battle:1")
        self.assertEqual(result.proof.player_character_ids, ("hero", "ally"))
        self.assertEqual(result.covered_player_character_ids, ("hero", "ally"))
        self.assertTrue(result.pursuit_decision_required)
        self.assertIsInstance(
            result.application_request,
            RetreatBloodPriceApplicationRequest,
        )
        application = result.application_request
        assert isinstance(application, RetreatBloodPriceApplicationRequest)
        self.assertEqual(
            application.possible_target_actor_ids,
            ("hero", "ally"),
        )
        self.assertEqual(application.wound_count, 1)
        self.assertIs(application.decision_owner, DecisionOwner.GM)

    def test_materiel_price_defers_owner_and_valuable_trapping(self) -> None:
        result = alternative_price_cover(RetreatAlternativePrice.MATERIEL)

        application = result.application_request
        self.assertIsInstance(
            application,
            RetreatMaterielPriceApplicationRequest,
        )
        assert isinstance(application, RetreatMaterielPriceApplicationRequest)
        self.assertEqual(application.possible_owner_actor_ids, ("hero", "ally"))
        self.assertEqual(application.trapping_count, 1)
        self.assertTrue(application.valuable_trapping_required)

    def test_misfortune_price_defers_one_enemy_golden_opportunity(self) -> None:
        result = alternative_price_cover(RetreatAlternativePrice.MISFORTUNE)

        application = result.application_request
        self.assertIsInstance(
            application,
            RetreatMisfortunePriceApplicationRequest,
        )
        assert isinstance(application, RetreatMisfortunePriceApplicationRequest)
        self.assertEqual(
            application.beneficiary_enemy_ids,
            ("enemy:1", "enemy:2"),
        )
        self.assertEqual(application.golden_opportunity_count, 1)

    def test_price_decision_and_result_provenance_are_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "GM chooses"):
            RetreatAlternativePriceDecision(
                id="decision:actor",
                price=RetreatAlternativePrice.BLOOD,
                decision_owner=DecisionOwner.ACTOR,
            )

        result = alternative_price_cover(RetreatAlternativePrice.BLOOD)
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(
                result,
                proof=replace(result.proof, decision_id="decision:forged"),
            )
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(
                result,
                application_request=replace(
                    result.application_request,
                    source_proof_id="proof:forged",
                ),
            )


class K1RetreatPursuitRequestTests(unittest.TestCase):
    def test_no_pursuit_requires_no_escape_attempts(self) -> None:
        request = RetreatPursuitResolutionRequest(
            id="pursuit:none",
            source_cover=secured_retreat(),
            pursuing_enemy_ids=(),
            attempts=(),
        )

        self.assertFalse(request.is_pursued)
        result = resolve_retreat_pursuit(request, SequenceRandom([]))
        self.assertFalse(result.was_pursued)
        self.assertEqual(result.escape_results, ())
        self.assertEqual(result.failed_actor_ids, ())
        self.assertEqual(result.mandatory_table_roll_count, 0)
        self.assertFalse(result.complication_table_roll_option_available)

    def test_alternative_price_proof_uses_the_same_pursuit_boundary(self) -> None:
        cover = alternative_price_cover(RetreatAlternativePrice.MISFORTUNE)
        request = RetreatPursuitResolutionRequest(
            id="pursuit:alternative-price",
            source_cover=cover,
            pursuing_enemy_ids=("enemy:1",),
            attempts=(athletics_attempt("hero"), lore_attempt("ally")),
        )

        result = resolve_retreat_pursuit(
            request,
            SequenceRandom([9, 9]),
        )

        self.assertEqual(result.failed_actor_ids, ("hero",))
        self.assertIn(
            RETREAT_ALTERNATIVE_PRICE_RULE_ID,
            result.applied_rule_ids,
        )
        self.assertEqual(result.applied_rule_ids[-1], RETREAT_PURSUIT_RULE_ID)

    def test_pursuit_requires_one_attempt_per_pc_in_group_order(self) -> None:
        rearguard = secured_retreat()
        with self.assertRaisesRegex(ValueError, "one ordered attempt"):
            RetreatPursuitResolutionRequest(
                id="pursuit:partial",
                source_cover=rearguard,
                pursuing_enemy_ids=("enemy:1",),
                attempts=(athletics_attempt("hero"),),
            )
        with self.assertRaisesRegex(ValueError, "one ordered attempt"):
            RetreatPursuitResolutionRequest(
                id="pursuit:reordered",
                source_cover=rearguard,
                pursuing_enemy_ids=("enemy:1",),
                attempts=(lore_attempt("ally"), athletics_attempt("hero")),
            )
        with self.assertRaisesRegex(ValueError, "opposition"):
            RetreatPursuitResolutionRequest(
                id="pursuit:ally",
                source_cover=rearguard,
                pursuing_enemy_ids=("ally",),
                attempts=(athletics_attempt("hero"), lore_attempt("ally")),
            )

    def test_attempt_modes_require_exact_book_context(self) -> None:
        with self.assertRaisesRegex(ValueError, "Athletics"):
            replace(athletics_attempt("hero"), test_skill=Skill.STEALTH)
        with self.assertRaisesRegex(ValueError, "does not roll"):
            replace(
                lore_attempt("hero"),
                test=TestRequest("test:forged", TestProfile(1, 5)),
            )
        with self.assertRaisesRegex(ValueError, "selected pursuing enemy"):
            RetreatPursuitResolutionRequest(
                id="pursuit:wrong-opponent",
                source_cover=secured_retreat(),
                pursuing_enemy_ids=("enemy:1",),
                attempts=(
                    opposed_attempt("hero", enemy_id="enemy:2"),
                    lore_attempt("ally"),
                ),
            )

    def test_all_test_request_and_lore_approval_ids_are_unique(self) -> None:
        with self.assertRaisesRegex(ValueError, "Test request IDs"):
            RetreatPursuitResolutionRequest(
                id="pursuit:duplicate-tests",
                source_cover=secured_retreat(),
                pursuing_enemy_ids=("enemy:1",),
                attempts=(
                    athletics_attempt("hero", test_id="test:duplicate"),
                    athletics_attempt("ally", test_id="test:duplicate"),
                ),
            )
        with self.assertRaisesRegex(ValueError, "approval IDs"):
            RetreatPursuitResolutionRequest(
                id="pursuit:duplicate-approvals",
                source_cover=secured_retreat(),
                pursuing_enemy_ids=("enemy:1",),
                attempts=(
                    lore_attempt("hero"),
                    replace(
                        lore_attempt("ally"),
                        automatic_success_approval_id="approval:escape:hero",
                    ),
                ),
            )


class K1RetreatPursuitResolutionTests(unittest.TestCase):
    def test_basic_and_lore_attempts_resolve_in_group_order(self) -> None:
        request = RetreatPursuitResolutionRequest(
            id="pursuit:basic-lore",
            source_cover=secured_retreat(),
            pursuing_enemy_ids=("enemy:1",),
            attempts=(athletics_attempt("hero"), lore_attempt("ally")),
        )

        result = resolve_retreat_pursuit(request, SequenceRandom([1, 2]))

        self.assertTrue(result.was_pursued)
        self.assertEqual(
            tuple(item.attempt.actor_id for item in result.escape_results),
            ("hero", "ally"),
        )
        self.assertIs(
            result.escape_results[0].outcome,
            RetreatEscapeOutcome.SUCCESS,
        )
        self.assertIs(
            result.escape_results[1].outcome,
            RetreatEscapeOutcome.AUTOMATIC_SUCCESS,
        )
        self.assertEqual(result.failed_actor_ids, ())
        self.assertEqual(result.applied_rule_ids[-1], RETREAT_PURSUIT_RULE_ID)

    def test_opposed_attempt_uses_contextual_tie_break(self) -> None:
        provider = FixedMarginalDecisions(
            {
                0: RetreatMarginalDecision(
                    RetreatMarginalChoice.CONTINUE_WITHOUT_COMPLICATION
                )
            }
        )
        request = RetreatPursuitResolutionRequest(
            id="pursuit:opposed",
            source_cover=secured_retreat(),
            pursuing_enemy_ids=("enemy:1",),
            attempts=(opposed_attempt("hero"), lore_attempt("ally")),
        )

        result = resolve_retreat_pursuit(
            request,
            SequenceRandom([2, 2]),
            marginal_decisions=provider,
        )

        opposed = result.escape_results[0]
        self.assertTrue(opposed.succeeded)
        self.assertTrue(opposed.test_result.tie_break_applied)
        self.assertEqual(provider.calls, [0])
        self.assertEqual(result.failed_actor_ids, ())

    def test_marginal_success_requires_a_valid_explicit_decision(self) -> None:
        request = RetreatPursuitResolutionRequest(
            id="pursuit:marginal",
            source_cover=secured_retreat(),
            pursuing_enemy_ids=("enemy:1",),
            attempts=(athletics_attempt("hero"), lore_attempt("ally")),
        )
        with self.assertRaises(MissingRetreatMarginalDecisionError):
            resolve_retreat_pursuit(request, SequenceRandom([1, 9]))
        with self.assertRaises(InvalidRetreatMarginalDecisionError):
            resolve_retreat_pursuit(
                request,
                SequenceRandom([1, 9]),
                marginal_decisions=InvalidMarginalDecisions(),
            )

    def test_multiple_accepted_complications_enable_optional_table_roll(self) -> None:
        decisions = FixedMarginalDecisions(
            {
                0: RetreatMarginalDecision(
                    RetreatMarginalChoice.ACCEPT_COMPLICATION,
                    complication_id="complication:hero",
                ),
                1: RetreatMarginalDecision(
                    RetreatMarginalChoice.ACCEPT_COMPLICATION,
                    complication_id="complication:ally",
                ),
            }
        )
        request = RetreatPursuitResolutionRequest(
            id="pursuit:complications",
            source_cover=secured_retreat(),
            pursuing_enemy_ids=("enemy:1",),
            attempts=(athletics_attempt("hero"), athletics_attempt("ally")),
        )

        result = resolve_retreat_pursuit(
            request,
            SequenceRandom([1, 9, 2, 9]),
            marginal_decisions=decisions,
        )

        self.assertEqual(result.failed_actor_ids, ())
        self.assertEqual(result.complication_actor_ids, ("hero", "ally"))
        self.assertEqual(
            result.complication_ids,
            ("complication:hero", "complication:ally"),
        )
        self.assertEqual(result.mandatory_table_roll_count, 0)
        self.assertTrue(result.complication_table_roll_option_available)

    def test_player_may_reject_complication_and_choose_failure(self) -> None:
        decisions = FixedMarginalDecisions(
            {
                0: RetreatMarginalDecision(
                    RetreatMarginalChoice.CHOOSE_FAILURE
                )
            }
        )
        request = RetreatPursuitResolutionRequest(
            id="pursuit:chosen-failure",
            source_cover=secured_retreat(),
            pursuing_enemy_ids=("enemy:1",),
            attempts=(athletics_attempt("hero"), lore_attempt("ally")),
        )

        result = resolve_retreat_pursuit(
            request,
            SequenceRandom([1, 9]),
            marginal_decisions=decisions,
        )

        self.assertIs(
            result.escape_results[0].outcome,
            RetreatEscapeOutcome.FAILURE,
        )
        self.assertEqual(result.failed_actor_ids, ("hero",))
        self.assertEqual(result.complication_actor_ids, ())
        self.assertEqual(result.mandatory_table_roll_count, 1)

    def test_accepted_complications_require_unique_stable_ids(self) -> None:
        decisions = FixedMarginalDecisions(
            {
                0: RetreatMarginalDecision(
                    RetreatMarginalChoice.ACCEPT_COMPLICATION,
                    complication_id="complication:duplicate",
                ),
                1: RetreatMarginalDecision(
                    RetreatMarginalChoice.ACCEPT_COMPLICATION,
                    complication_id="complication:duplicate",
                ),
            }
        )
        request = RetreatPursuitResolutionRequest(
            id="pursuit:duplicate-complications",
            source_cover=secured_retreat(),
            pursuing_enemy_ids=("enemy:1",),
            attempts=(athletics_attempt("hero"), athletics_attempt("ally")),
        )

        with self.assertRaisesRegex(ValueError, "Complication IDs"):
            resolve_retreat_pursuit(
                request,
                SequenceRandom([1, 9, 2, 9]),
                marginal_decisions=decisions,
            )

    def test_raw_failures_create_one_mandatory_roll_each(self) -> None:
        request = RetreatPursuitResolutionRequest(
            id="pursuit:failures",
            source_cover=secured_retreat(),
            pursuing_enemy_ids=("enemy:1",),
            attempts=(athletics_attempt("hero"), athletics_attempt("ally")),
        )

        result = resolve_retreat_pursuit(
            request,
            SequenceRandom([9, 9, 8, 10]),
        )

        self.assertEqual(result.failed_actor_ids, ("hero", "ally"))
        self.assertEqual(result.mandatory_table_roll_count, 2)
        self.assertFalse(result.complication_table_roll_option_available)

    def test_unknown_rule_and_forged_result_are_rejected(self) -> None:
        request = RetreatPursuitResolutionRequest(
            id="pursuit:unknown",
            source_cover=secured_retreat(),
            pursuing_enemy_ids=(),
            attempts=(),
            rule_id="RULE-UNKNOWN",
        )
        with self.assertRaisesRegex(ValueError, "unknown rule"):
            resolve_retreat_pursuit(request, SequenceRandom([]))

        valid = replace(request, rule_id=RETREAT_PURSUIT_RULE_ID)
        result = resolve_retreat_pursuit(valid, SequenceRandom([]))
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, mandatory_table_roll_count=1)
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, applied_rule_ids=(RETREAT_PURSUIT_RULE_ID,))


class K1RunForYourLivesResolutionTests(unittest.TestCase):
    @staticmethod
    def failed_pursuit():
        request = RetreatPursuitResolutionRequest(
            id="pursuit:table-failures",
            source_cover=secured_retreat(),
            pursuing_enemy_ids=("enemy:1",),
            attempts=(athletics_attempt("hero"), athletics_attempt("ally")),
        )
        return resolve_retreat_pursuit(
            request,
            SequenceRandom([9, 9, 8, 10]),
        )

    @staticmethod
    def complication_pursuit():
        decisions = FixedMarginalDecisions(
            {
                0: RetreatMarginalDecision(
                    RetreatMarginalChoice.ACCEPT_COMPLICATION,
                    complication_id="complication:hero",
                ),
                1: RetreatMarginalDecision(
                    RetreatMarginalChoice.ACCEPT_COMPLICATION,
                    complication_id="complication:ally",
                ),
            }
        )
        request = RetreatPursuitResolutionRequest(
            id="pursuit:table-complications",
            source_cover=secured_retreat(),
            pursuing_enemy_ids=("enemy:1",),
            attempts=(athletics_attempt("hero"), athletics_attempt("ally")),
        )
        return resolve_retreat_pursuit(
            request,
            SequenceRandom([1, 9, 2, 9]),
            marginal_decisions=decisions,
        )

    def test_failed_pcs_roll_once_each_in_group_order_and_sum(self) -> None:
        pursuit = self.failed_pursuit()
        request = RunForYourLivesResolutionRequest(
            id="run-for-your-lives:failures",
            source_pursuit=pursuit,
        )

        result = resolve_run_for_your_lives(
            request,
            SequenceRandom([7, 8]),
        )

        self.assertEqual(
            tuple(item.reason for item in result.rolls),
            (
                RunForYourLivesRollReason.FAILED_ESCAPE,
                RunForYourLivesRollReason.FAILED_ESCAPE,
            ),
        )
        self.assertEqual(
            tuple(item.failed_actor_id for item in result.rolls),
            ("hero", "ally"),
        )
        self.assertEqual(tuple(item.value for item in result.rolls), (7, 8))
        self.assertEqual(result.table_total, 15)
        self.assertIs(result.outcome, RunForYourLivesOutcome.EXPOSED)
        self.assertEqual(result.applied_rule_ids[-1], RUN_FOR_YOUR_LIVES_RULE_ID)

        consequence = result.campaign_consequence
        self.assertIsNotNone(consequence)
        assert consequence is not None
        self.assertEqual(consequence.battle_id, "battle:1")
        self.assertEqual(consequence.retreat_id, "retreat:battle:1:round:3")
        self.assertEqual(consequence.player_character_ids, ("hero", "ally"))
        self.assertEqual(consequence.rearguard_actor_id, "hero")
        self.assertEqual(consequence.failed_actor_ids, ("hero", "ally"))
        self.assertEqual(consequence.table_total, 15)
        self.assertIs(consequence.outcome, RunForYourLivesOutcome.EXPOSED)
        self.assertIs(consequence.decision_owner, DecisionOwner.GM)

    def test_multiple_complications_require_an_explicit_gm_decision(self) -> None:
        pursuit = self.complication_pursuit()
        with self.assertRaisesRegex(ValueError, "explicit GM decision"):
            RunForYourLivesResolutionRequest(
                id="run-for-your-lives:missing-decision",
                source_pursuit=pursuit,
            )
        with self.assertRaisesRegex(ValueError, "GM decides"):
            RunForYourLivesComplicationRollDecision(
                id="decision:wrong-owner",
                choice=RunForYourLivesComplicationRollChoice.ROLL,
                decision_owner=DecisionOwner.ACTOR,
            )

    def test_gm_may_decline_the_optional_complication_roll(self) -> None:
        request = RunForYourLivesResolutionRequest(
            id="run-for-your-lives:declined",
            source_pursuit=self.complication_pursuit(),
            complication_roll_decision=(
                RunForYourLivesComplicationRollDecision(
                    id="decision:no-table-roll",
                    choice=RunForYourLivesComplicationRollChoice.DO_NOT_ROLL,
                )
            ),
        )

        result = resolve_run_for_your_lives(request, SequenceRandom([]))

        self.assertEqual(result.rolls, ())
        self.assertEqual(result.table_total, 0)
        self.assertIsNone(result.outcome)
        self.assertIsNone(result.campaign_consequence)

    def test_gm_may_add_exactly_one_roll_for_multiple_complications(self) -> None:
        request = RunForYourLivesResolutionRequest(
            id="run-for-your-lives:complications",
            source_pursuit=self.complication_pursuit(),
            complication_roll_decision=(
                RunForYourLivesComplicationRollDecision(
                    id="decision:table-roll",
                    choice=RunForYourLivesComplicationRollChoice.ROLL,
                )
            ),
        )

        result = resolve_run_for_your_lives(request, SequenceRandom([10]))

        self.assertEqual(len(result.rolls), 1)
        roll = result.rolls[0]
        self.assertIs(
            roll.reason,
            RunForYourLivesRollReason.MULTIPLE_COMPLICATIONS,
        )
        self.assertIsNone(roll.failed_actor_id)
        self.assertEqual(
            roll.source_complication_ids,
            ("complication:hero", "complication:ally"),
        )
        self.assertEqual(result.table_total, 10)
        self.assertIs(result.outcome, RunForYourLivesOutcome.MARKED)
        assert result.campaign_consequence is not None
        self.assertEqual(
            result.campaign_consequence.complication_ids,
            ("complication:hero", "complication:ally"),
        )

    def test_no_pursuit_has_no_table_roll_or_campaign_follow_up(self) -> None:
        pursuit = resolve_retreat_pursuit(
            RetreatPursuitResolutionRequest(
                id="pursuit:no-table",
                source_cover=secured_retreat(),
                pursuing_enemy_ids=(),
                attempts=(),
            ),
            SequenceRandom([]),
        )
        request = RunForYourLivesResolutionRequest(
            id="run-for-your-lives:none",
            source_pursuit=pursuit,
        )

        result = resolve_run_for_your_lives(request, SequenceRandom([]))

        self.assertEqual(result.rolls, ())
        self.assertEqual(result.table_total, 0)
        self.assertIsNone(result.outcome)
        self.assertIsNone(result.campaign_consequence)

    def test_campaign_follow_up_preserves_alternative_cover_proof(self) -> None:
        cover = alternative_price_cover(RetreatAlternativePrice.BLOOD)
        pursuit = resolve_retreat_pursuit(
            RetreatPursuitResolutionRequest(
                id="pursuit:alternative-table",
                source_cover=cover,
                pursuing_enemy_ids=("enemy:1",),
                attempts=(athletics_attempt("hero"), lore_attempt("ally")),
            ),
            SequenceRandom([9, 9]),
        )
        result = resolve_run_for_your_lives(
            RunForYourLivesResolutionRequest(
                id="run-for-your-lives:alternative-cover",
                source_pursuit=pursuit,
            ),
            SequenceRandom([4]),
        )

        consequence = result.campaign_consequence
        self.assertIsNotNone(consequence)
        assert consequence is not None
        self.assertIs(consequence.cover_kind, RetreatCoverKind.ALTERNATIVE_PRICE)
        self.assertEqual(consequence.cover_proof_id, cover.proof.id)
        self.assertIsNone(consequence.rearguard_actor_id)

    def test_complication_decision_is_forbidden_when_option_is_unavailable(self) -> None:
        with self.assertRaisesRegex(ValueError, "not available"):
            RunForYourLivesResolutionRequest(
                id="run-for-your-lives:forged-option",
                source_pursuit=self.failed_pursuit(),
                complication_roll_decision=(
                    RunForYourLivesComplicationRollDecision(
                        id="decision:forged",
                        choice=RunForYourLivesComplicationRollChoice.ROLL,
                    )
                ),
            )

    def test_all_book_table_bands_have_exact_boundaries(self) -> None:
        cases = (
            (1, RunForYourLivesOutcome.LOST),
            (3, RunForYourLivesOutcome.LOST),
            (4, RunForYourLivesOutcome.MOCKED),
            (6, RunForYourLivesOutcome.MOCKED),
            (7, RunForYourLivesOutcome.INDEBTED),
            (9, RunForYourLivesOutcome.INDEBTED),
            (10, RunForYourLivesOutcome.MARKED),
            (12, RunForYourLivesOutcome.MARKED),
            (13, RunForYourLivesOutcome.EXPOSED),
            (15, RunForYourLivesOutcome.EXPOSED),
            (16, RunForYourLivesOutcome.HUNTED),
            (18, RunForYourLivesOutcome.HUNTED),
            (19, RunForYourLivesOutcome.ROBBED),
            (21, RunForYourLivesOutcome.ROBBED),
            (22, RunForYourLivesOutcome.SURROUNDED),
            (24, RunForYourLivesOutcome.SURROUNDED),
            (25, RunForYourLivesOutcome.TRAPPED),
            (100, RunForYourLivesOutcome.TRAPPED),
        )
        for total, expected in cases:
            with self.subTest(total=total):
                self.assertIs(classify_run_for_your_lives(total), expected)
        with self.assertRaisesRegex(ValueError, "positive"):
            classify_run_for_your_lives(0)

    def test_invalid_d10_and_forged_result_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "d10"):
            RunForYourLivesRoll(
                reason=RunForYourLivesRollReason.FAILED_ESCAPE,
                failed_actor_id="hero",
                value=11,
            )

        request = RunForYourLivesResolutionRequest(
            id="run-for-your-lives:provenance",
            source_pursuit=self.failed_pursuit(),
        )
        result = resolve_run_for_your_lives(
            request,
            SequenceRandom([2, 3]),
        )
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(result, table_total=6)
        with self.assertRaisesRegex(ValueError, "out of order"):
            replace(result, rolls=tuple(reversed(result.rolls)))


if __name__ == "__main__":
    unittest.main()
