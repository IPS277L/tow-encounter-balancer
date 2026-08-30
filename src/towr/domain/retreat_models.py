from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from towr.domain.injury_models import DecisionOwner
from towr.domain.test_models import (
    BasicOutcome,
    OpposedOutcome,
    OpposedSide,
    OpposedTestRequest,
    OpposedTestResult,
    Skill,
    TestRequest,
    TestResult,
)
from towr.domain.turn_models import CombatRoundState, CombatSide


RETREAT_RULE_ID = "RULE-COMBAT-016:group-retreat"
RETREAT_ALTERNATIVE_PRICE_RULE_ID = (
    "RULE-COMBAT-016:alternative-retreat-price"
)
RETREAT_PURSUIT_RULE_ID = "RULE-COMBAT-016:pursuit"
RUN_FOR_YOUR_LIVES_RULE_ID = "RULE-COMBAT-016:run-for-your-lives"


class RetreatTiming(str, Enum):
    START_OF_ROUND = "start_of_round"
    START_OF_PLAYERS_SIDE = "start_of_players_side"


class RetreatAlternativePrice(str, Enum):
    BLOOD = "blood"
    MATERIEL = "materiel"
    MISFORTUNE = "misfortune"


class RetreatCoverKind(str, Enum):
    FATE_REARGUARD = "fate_rearguard"
    ALTERNATIVE_PRICE = "alternative_price"


class RetreatEscapeMethod(str, Enum):
    ATHLETICS_TEST = "athletics_test"
    LORE_AUTOMATIC_SUCCESS = "lore_automatic_success"
    OPPOSED_ATHLETICS_TEST = "opposed_athletics_test"


class RetreatEscapeOutcome(str, Enum):
    AUTOMATIC_SUCCESS = "automatic_success"
    SUCCESS = "success"
    FAILURE = "failure"


class RetreatMarginalChoice(str, Enum):
    CONTINUE_WITHOUT_COMPLICATION = "continue_without_complication"
    ACCEPT_COMPLICATION = "accept_complication"
    CHOOSE_FAILURE = "choose_failure"


class RunForYourLivesComplicationRollChoice(str, Enum):
    ROLL = "roll"
    DO_NOT_ROLL = "do_not_roll"


class RunForYourLivesRollReason(str, Enum):
    FAILED_ESCAPE = "failed_escape"
    MULTIPLE_COMPLICATIONS = "multiple_complications"


class RunForYourLivesOutcome(str, Enum):
    LOST = "lost"
    MOCKED = "mocked"
    INDEBTED = "indebted"
    MARKED = "marked"
    EXPOSED = "exposed"
    HUNTED = "hunted"
    ROBBED = "robbed"
    SURROUNDED = "surrounded"
    TRAPPED = "trapped"


@dataclass(frozen=True, slots=True)
class RetreatMarginalDecision:
    choice: RetreatMarginalChoice
    complication_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.choice, RetreatMarginalChoice):
            raise TypeError("choice must be a RetreatMarginalChoice")
        if self.choice is RetreatMarginalChoice.ACCEPT_COMPLICATION:
            _validate_non_empty_string(
                self.complication_id,
                "retreat complication_id",
            )
        elif self.complication_id is not None:
            raise ValueError(
                "only an accepted Retreat Complication may have an ID"
            )


@dataclass(frozen=True, slots=True)
class GroupRetreatDeclaration:
    id: str
    battle_id: str
    initiator_actor_id: str
    player_character_ids: tuple[str, ...]
    consenting_player_character_ids: tuple[str, ...]
    round_state: CombatRoundState
    rule_id: str = RETREAT_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "retreat declaration id")
        _validate_non_empty_string(self.battle_id, "retreat battle_id")
        _validate_non_empty_string(
            self.initiator_actor_id,
            "retreat initiator_actor_id",
        )
        player_ids = _validate_unique_ids(
            self.player_character_ids,
            "retreat player_character_ids",
        )
        consent_ids = _validate_unique_ids(
            self.consenting_player_character_ids,
            "retreat consenting_player_character_ids",
        )
        if self.initiator_actor_id not in player_ids:
            raise ValueError("retreat initiator must be a player character")
        if set(consent_ids) != set(player_ids):
            raise ValueError("group Retreat requires unanimous player consent")
        if not isinstance(self.round_state, CombatRoundState):
            raise TypeError("round_state must be a CombatRoundState")
        for actor_id in player_ids:
            participant = self.round_state.participant_for(actor_id)
            if participant.side is not CombatSide.PLAYERS_AND_ALLIES:
                raise ValueError(
                    "retreat player characters must belong to the players side"
                )
        if self.round_state.active_turn is not None:
            raise ValueError("Retreat must be declared before a turn starts")
        _validate_retreat_timing(self.round_state)
        _validate_non_empty_string(self.rule_id, "retreat rule_id")
        if self.rule_id != RETREAT_RULE_ID:
            raise ValueError("group Retreat requires its canonical rule")
        object.__setattr__(self, "player_character_ids", player_ids)
        object.__setattr__(
            self,
            "consenting_player_character_ids",
            consent_ids,
        )

    @property
    def timing(self) -> RetreatTiming:
        if not self.round_state.completed_turn_entity_ids:
            return RetreatTiming.START_OF_ROUND
        return RetreatTiming.START_OF_PLAYERS_SIDE


@dataclass(frozen=True, slots=True)
class RetreatRearGuardResult:
    request_id: str
    source_request: GroupRetreatDeclaration
    rearguard_actor_id: str
    fate_proof_id: str
    source_spend_id: str
    covered_player_character_ids: tuple[str, ...]
    pursuit_decision_required: bool
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "retreat rearguard result request_id",
        )
        if not isinstance(self.source_request, GroupRetreatDeclaration):
            raise TypeError("source_request must be a GroupRetreatDeclaration")
        _validate_non_empty_string(
            self.rearguard_actor_id,
            "retreat rearguard_actor_id",
        )
        if self.rearguard_actor_id not in self.source_request.player_character_ids:
            raise ValueError("retreat rearguard must be a player character")
        _validate_non_empty_string(self.fate_proof_id, "retreat fate_proof_id")
        _validate_non_empty_string(
            self.source_spend_id,
            "retreat source_spend_id",
        )
        covered = _validate_unique_ids(
            self.covered_player_character_ids,
            "covered_player_character_ids",
        )
        if covered != self.source_request.player_character_ids:
            raise ValueError("retreat rearguard must cover the declared group")
        if self.request_id != self.source_request.id:
            raise ValueError("retreat result belongs to another declaration")
        if self.pursuit_decision_required is not True:
            raise ValueError(
                "covered Retreat must preserve the enemy pursuit decision"
            )
        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        if not rule_ids or rule_ids[0] != RETREAT_RULE_ID:
            raise ValueError("retreat rearguard rule trace is incomplete")
        object.__setattr__(self, "covered_player_character_ids", covered)
        object.__setattr__(self, "applied_rule_ids", rule_ids)


@dataclass(frozen=True, slots=True)
class RetreatAlternativePriceRequest:
    id: str
    source_retreat: GroupRetreatDeclaration
    exhausted_fate_actor_ids: tuple[str, ...]
    possible_prices: tuple[RetreatAlternativePrice, ...] = (
        RetreatAlternativePrice.BLOOD,
        RetreatAlternativePrice.MATERIEL,
        RetreatAlternativePrice.MISFORTUNE,
    )
    decision_owner: DecisionOwner = DecisionOwner.GM
    rule_id: str = RETREAT_ALTERNATIVE_PRICE_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "retreat price request id")
        if not isinstance(self.source_retreat, GroupRetreatDeclaration):
            raise TypeError("source_retreat must be a GroupRetreatDeclaration")
        exhausted = _validate_unique_ids(
            self.exhausted_fate_actor_ids,
            "exhausted_fate_actor_ids",
        )
        if set(exhausted) != set(self.source_retreat.player_character_ids):
            raise ValueError(
                "retreat price requires exhausted Fate for every player character"
            )
        prices = tuple(self.possible_prices)
        if prices != (
            RetreatAlternativePrice.BLOOD,
            RetreatAlternativePrice.MATERIEL,
            RetreatAlternativePrice.MISFORTUNE,
        ):
            raise ValueError("retreat price must expose all book-defined options")
        if self.decision_owner is not DecisionOwner.GM:
            raise ValueError("the GM chooses the alternative Retreat price")
        _validate_non_empty_string(self.rule_id, "retreat price rule_id")
        if self.rule_id != RETREAT_ALTERNATIVE_PRICE_RULE_ID:
            raise ValueError("retreat price requires its canonical rule")
        object.__setattr__(self, "exhausted_fate_actor_ids", exhausted)
        object.__setattr__(self, "possible_prices", prices)


@dataclass(frozen=True, slots=True)
class RetreatAlternativePriceDecision:
    id: str
    price: RetreatAlternativePrice
    decision_owner: DecisionOwner = DecisionOwner.GM

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Retreat price decision id")
        if not isinstance(self.price, RetreatAlternativePrice):
            raise TypeError("price must be a RetreatAlternativePrice")
        if self.decision_owner is not DecisionOwner.GM:
            raise ValueError("the GM chooses the alternative Retreat price")


@dataclass(frozen=True, slots=True)
class RetreatAlternativePriceProof:
    id: str
    source_request_id: str
    decision_id: str
    retreat_id: str
    battle_id: str
    player_character_ids: tuple[str, ...]
    price: RetreatAlternativePrice
    rule_id: str = RETREAT_ALTERNATIVE_PRICE_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Retreat price proof id")
        _validate_non_empty_string(
            self.source_request_id,
            "Retreat price proof source_request_id",
        )
        _validate_non_empty_string(self.decision_id, "Retreat price proof decision_id")
        _validate_non_empty_string(self.retreat_id, "Retreat price proof retreat_id")
        _validate_non_empty_string(self.battle_id, "Retreat price proof battle_id")
        player_ids = _validate_unique_ids(
            self.player_character_ids,
            "Retreat price proof player_character_ids",
        )
        if not isinstance(self.price, RetreatAlternativePrice):
            raise TypeError("price must be a RetreatAlternativePrice")
        _validate_non_empty_string(self.rule_id, "Retreat price proof rule_id")
        if self.rule_id != RETREAT_ALTERNATIVE_PRICE_RULE_ID:
            raise ValueError("Retreat price proof uses an unknown rule")
        object.__setattr__(self, "player_character_ids", player_ids)


@dataclass(frozen=True, slots=True)
class RetreatBloodPriceApplicationRequest:
    id: str
    source_proof_id: str
    battle_id: str
    retreat_id: str
    possible_target_actor_ids: tuple[str, ...]
    wound_count: int = 1
    decision_owner: DecisionOwner = DecisionOwner.GM
    rule_id: str = RETREAT_ALTERNATIVE_PRICE_RULE_ID

    def __post_init__(self) -> None:
        _validate_price_application_context(self)
        targets = _validate_unique_ids(
            self.possible_target_actor_ids,
            "Retreat blood price possible_target_actor_ids",
        )
        if self.wound_count != 1:
            raise ValueError("the blood price inflicts exactly one Wound")
        object.__setattr__(self, "possible_target_actor_ids", targets)


@dataclass(frozen=True, slots=True)
class RetreatMaterielPriceApplicationRequest:
    id: str
    source_proof_id: str
    battle_id: str
    retreat_id: str
    possible_owner_actor_ids: tuple[str, ...]
    trapping_count: int = 1
    valuable_trapping_required: bool = True
    decision_owner: DecisionOwner = DecisionOwner.GM
    rule_id: str = RETREAT_ALTERNATIVE_PRICE_RULE_ID

    def __post_init__(self) -> None:
        _validate_price_application_context(self)
        owners = _validate_unique_ids(
            self.possible_owner_actor_ids,
            "Retreat materiel price possible_owner_actor_ids",
        )
        if self.trapping_count != 1 or self.valuable_trapping_required is not True:
            raise ValueError("the materiel price drops one valuable trapping")
        object.__setattr__(self, "possible_owner_actor_ids", owners)


@dataclass(frozen=True, slots=True)
class RetreatMisfortunePriceApplicationRequest:
    id: str
    source_proof_id: str
    battle_id: str
    retreat_id: str
    beneficiary_enemy_ids: tuple[str, ...]
    golden_opportunity_count: int = 1
    decision_owner: DecisionOwner = DecisionOwner.GM
    rule_id: str = RETREAT_ALTERNATIVE_PRICE_RULE_ID

    def __post_init__(self) -> None:
        _validate_price_application_context(self)
        enemies = _validate_unique_ids(
            self.beneficiary_enemy_ids,
            "Retreat misfortune beneficiary_enemy_ids",
        )
        if self.golden_opportunity_count != 1:
            raise ValueError(
                "the misfortune price confers exactly one golden opportunity"
            )
        object.__setattr__(self, "beneficiary_enemy_ids", enemies)


RetreatAlternativePriceApplicationRequest = (
    RetreatBloodPriceApplicationRequest
    | RetreatMaterielPriceApplicationRequest
    | RetreatMisfortunePriceApplicationRequest
)


@dataclass(frozen=True, slots=True)
class RetreatAlternativePriceResolutionResult:
    request_id: str
    source_request: RetreatAlternativePriceRequest
    decision: RetreatAlternativePriceDecision
    proof: RetreatAlternativePriceProof
    application_request: RetreatAlternativePriceApplicationRequest
    covered_player_character_ids: tuple[str, ...]
    pursuit_decision_required: bool
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Retreat price result request_id",
        )
        if not isinstance(self.source_request, RetreatAlternativePriceRequest):
            raise TypeError(
                "source_request must be a RetreatAlternativePriceRequest"
            )
        if not isinstance(self.decision, RetreatAlternativePriceDecision):
            raise TypeError("decision must be a RetreatAlternativePriceDecision")
        expected_proof = _retreat_alternative_price_proof(
            self.source_request,
            self.decision,
        )
        expected_application = _retreat_alternative_price_application(
            self.source_request,
            expected_proof,
        )
        covered = tuple(self.covered_player_character_ids)
        expected_covered = self.source_request.source_retreat.player_character_ids
        expected_rules = (
            self.source_request.source_retreat.rule_id,
            self.source_request.rule_id,
        )
        if (
            self.request_id != self.source_request.id
            or self.decision.price not in self.source_request.possible_prices
            or self.proof != expected_proof
            or self.application_request != expected_application
            or covered != expected_covered
            or self.pursuit_decision_required is not True
            or self.applied_rule_ids != expected_rules
        ):
            raise ValueError("Retreat alternative price result has stale provenance")
        object.__setattr__(self, "covered_player_character_ids", covered)


RetreatCoverResult = (
    RetreatRearGuardResult | RetreatAlternativePriceResolutionResult
)


RetreatEscapeTestRequest = TestRequest | OpposedTestRequest
RetreatEscapeTestResult = TestResult | OpposedTestResult


@dataclass(frozen=True, slots=True)
class RetreatEscapeAttempt:
    actor_id: str
    method: RetreatEscapeMethod
    test: RetreatEscapeTestRequest | None = None
    test_skill: Skill | None = None
    opposing_enemy_id: str | None = None
    lore_id: str | None = None
    automatic_success_approval_id: str | None = None

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.actor_id, "Retreat escape actor_id")
        if not isinstance(self.method, RetreatEscapeMethod):
            raise TypeError("method must be a RetreatEscapeMethod")
        if self.method is RetreatEscapeMethod.ATHLETICS_TEST:
            if not isinstance(self.test, TestRequest):
                raise TypeError("basic Retreat escape requires a TestRequest")
            if self.test_skill is not Skill.ATHLETICS:
                raise ValueError("basic Retreat escape must use Athletics")
            if (
                self.opposing_enemy_id is not None
                or self.lore_id is not None
                or self.automatic_success_approval_id is not None
            ):
                raise ValueError("basic Retreat escape cannot name Lore or opponent")
            return
        if self.method is RetreatEscapeMethod.OPPOSED_ATHLETICS_TEST:
            if not isinstance(self.test, OpposedTestRequest):
                raise TypeError("opposed Retreat escape requires OpposedTestRequest")
            if self.test_skill is not Skill.ATHLETICS:
                raise ValueError("opposed Retreat escape must use Athletics")
            _validate_non_empty_string(
                self.opposing_enemy_id,
                "Retreat opposing_enemy_id",
            )
            if (
                self.lore_id is not None
                or self.automatic_success_approval_id is not None
            ):
                raise ValueError("opposed Retreat escape cannot name Lore")
            if self.test.initiator.id == self.test.opponent.id:
                raise ValueError("opposed Retreat Test sides require distinct IDs")
            return
        if self.test is not None or self.test_skill is not None:
            raise ValueError("Lore automatic success does not roll a Test")
        if self.opposing_enemy_id is not None:
            raise ValueError("Lore automatic success cannot name an opponent")
        _validate_non_empty_string(self.lore_id, "Retreat automatic-success Lore ID")
        _validate_non_empty_string(
            self.automatic_success_approval_id,
            "Retreat automatic-success approval ID",
        )


@dataclass(frozen=True, slots=True)
class RetreatPursuitResolutionRequest:
    id: str
    source_cover: RetreatCoverResult
    pursuing_enemy_ids: tuple[str, ...]
    attempts: tuple[RetreatEscapeAttempt, ...]
    decision_owner: DecisionOwner = DecisionOwner.GM
    rule_id: str = RETREAT_PURSUIT_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Retreat pursuit request id")
        if not isinstance(
            self.source_cover,
            (RetreatRearGuardResult, RetreatAlternativePriceResolutionResult),
        ):
            raise TypeError("source_cover must be a supported Retreat cover result")
        source_retreat = _retreat_from_cover(self.source_cover)
        enemy_ids = tuple(self.pursuing_enemy_ids)
        for enemy_id in enemy_ids:
            _validate_non_empty_string(enemy_id, "pursuing enemy ID")
            participant = source_retreat.round_state.participant_for(enemy_id)
            if participant.side is not CombatSide.OPPOSITION:
                raise ValueError("Retreat pursuers must belong to the opposition")
        if len(set(enemy_ids)) != len(enemy_ids):
            raise ValueError("Retreat pursuing enemy IDs must be unique")

        attempts = tuple(self.attempts)
        if not all(isinstance(item, RetreatEscapeAttempt) for item in attempts):
            raise TypeError("attempts must contain RetreatEscapeAttempt values")
        expected_actor_ids = self.source_cover.covered_player_character_ids
        actual_actor_ids = tuple(item.actor_id for item in attempts)
        if enemy_ids:
            if actual_actor_ids != expected_actor_ids:
                raise ValueError(
                    "pursued Retreat requires one ordered attempt for every PC"
                )
        elif attempts:
            raise ValueError("an unpursued Retreat cannot contain escape attempts")
        for attempt in attempts:
            if (
                attempt.method is RetreatEscapeMethod.OPPOSED_ATHLETICS_TEST
                and attempt.opposing_enemy_id not in enemy_ids
            ):
                raise ValueError(
                    "opposed Retreat Test requires a selected pursuing enemy"
                )
        test_ids = tuple(
            test_id
            for attempt in attempts
            for test_id in _escape_attempt_test_ids(attempt)
        )
        if len(set(test_ids)) != len(test_ids):
            raise ValueError("Retreat Test request IDs must be unique")
        approval_ids = tuple(
            item.automatic_success_approval_id
            for item in attempts
            if item.automatic_success_approval_id is not None
        )
        if len(set(approval_ids)) != len(approval_ids):
            raise ValueError("Retreat Lore approval IDs must be unique")
        if self.decision_owner is not DecisionOwner.GM:
            raise ValueError("the GM decides whether enemies pursue")
        _validate_non_empty_string(self.rule_id, "Retreat pursuit rule_id")
        object.__setattr__(self, "pursuing_enemy_ids", enemy_ids)
        object.__setattr__(self, "attempts", attempts)

    @property
    def is_pursued(self) -> bool:
        return bool(self.pursuing_enemy_ids)


@dataclass(frozen=True, slots=True)
class RetreatEscapeResult:
    attempt: RetreatEscapeAttempt
    test_result: RetreatEscapeTestResult | None
    marginal_decision: RetreatMarginalDecision | None
    outcome: RetreatEscapeOutcome

    def __post_init__(self) -> None:
        if not isinstance(self.attempt, RetreatEscapeAttempt):
            raise TypeError("attempt must be a RetreatEscapeAttempt")
        if not isinstance(self.outcome, RetreatEscapeOutcome):
            raise TypeError("outcome must be a RetreatEscapeOutcome")
        if self.attempt.method is RetreatEscapeMethod.LORE_AUTOMATIC_SUCCESS:
            if self.test_result is not None or self.marginal_decision is not None:
                raise ValueError("Lore automatic success has no Test or Complication")
            if self.outcome is not RetreatEscapeOutcome.AUTOMATIC_SUCCESS:
                raise ValueError("Lore must produce automatic Retreat success")
            return
        _validate_escape_test_result(self.attempt, self.test_result)
        assert self.test_result is not None
        raw_succeeded = _escape_test_succeeded(self.test_result)
        marginal = raw_succeeded and _escape_test_is_marginal(self.test_result)
        if marginal != (self.marginal_decision is not None):
            raise ValueError(
                "a marginal Retreat success requires exactly one explicit decision"
            )
        chose_failure = (
            self.marginal_decision is not None
            and self.marginal_decision.choice is RetreatMarginalChoice.CHOOSE_FAILURE
        )
        expected_outcome = (
            RetreatEscapeOutcome.SUCCESS
            if raw_succeeded and not chose_failure
            else RetreatEscapeOutcome.FAILURE
        )
        if self.outcome is not expected_outcome:
            raise ValueError("Retreat escape outcome disagrees with its Test")

    @property
    def succeeded(self) -> bool:
        return self.outcome is not RetreatEscapeOutcome.FAILURE

    @property
    def complication_id(self) -> str | None:
        decision = self.marginal_decision
        if (
            decision is not None
            and decision.choice is RetreatMarginalChoice.ACCEPT_COMPLICATION
        ):
            return decision.complication_id
        return None


@dataclass(frozen=True, slots=True)
class RetreatPursuitResolutionResult:
    request_id: str
    rule_id: str
    source_request: RetreatPursuitResolutionRequest
    was_pursued: bool
    escape_results: tuple[RetreatEscapeResult, ...]
    failed_actor_ids: tuple[str, ...]
    complication_actor_ids: tuple[str, ...]
    complication_ids: tuple[str, ...]
    mandatory_table_roll_count: int
    complication_table_roll_option_available: bool
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Retreat pursuit result request_id")
        _validate_non_empty_string(self.rule_id, "Retreat pursuit result rule_id")
        if not isinstance(self.source_request, RetreatPursuitResolutionRequest):
            raise TypeError("source_request must be a Retreat pursuit request")
        results = tuple(self.escape_results)
        if not all(isinstance(item, RetreatEscapeResult) for item in results):
            raise TypeError("escape_results must contain RetreatEscapeResult values")
        expected_results_attempts = tuple(item.attempt for item in results)
        expected_failed = tuple(
            item.attempt.actor_id for item in results if not item.succeeded
        )
        expected_complications = tuple(
            item.attempt.actor_id
            for item in results
            if item.complication_id is not None
        )
        expected_complication_ids = tuple(
            item.complication_id
            for item in results
            if item.complication_id is not None
        )
        if len(set(expected_complication_ids)) != len(expected_complication_ids):
            raise ValueError("Retreat Complication IDs must be unique")
        expected_option = not expected_failed and len(expected_complications) >= 2
        expected_rules = _pursuit_rule_ids(self.source_request, results)
        if (
            self.request_id != self.source_request.id
            or self.rule_id != self.source_request.rule_id
            or self.was_pursued is not self.source_request.is_pursued
            or expected_results_attempts != self.source_request.attempts
            or self.failed_actor_ids != expected_failed
            or self.complication_actor_ids != expected_complications
            or self.complication_ids != expected_complication_ids
            or self.mandatory_table_roll_count != len(expected_failed)
            or self.complication_table_roll_option_available is not expected_option
            or self.applied_rule_ids != expected_rules
        ):
            raise ValueError("Retreat pursuit result has stale provenance")
        if self.was_pursued != bool(results):
            raise ValueError("Retreat pursuit result has an invalid result count")
        object.__setattr__(self, "escape_results", results)


@dataclass(frozen=True, slots=True)
class RunForYourLivesComplicationRollDecision:
    id: str
    choice: RunForYourLivesComplicationRollChoice
    decision_owner: DecisionOwner = DecisionOwner.GM

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.id,
            "Run For Your Lives Complication decision id",
        )
        if not isinstance(
            self.choice,
            RunForYourLivesComplicationRollChoice,
        ):
            raise TypeError(
                "choice must be a RunForYourLivesComplicationRollChoice"
            )
        if self.decision_owner is not DecisionOwner.GM:
            raise ValueError(
                "the GM decides whether multiple Complications cause a roll"
            )


@dataclass(frozen=True, slots=True)
class RunForYourLivesResolutionRequest:
    id: str
    source_pursuit: RetreatPursuitResolutionResult
    complication_roll_decision: (
        RunForYourLivesComplicationRollDecision | None
    ) = None
    rule_id: str = RUN_FOR_YOUR_LIVES_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Run For Your Lives request id")
        if not isinstance(
            self.source_pursuit,
            RetreatPursuitResolutionResult,
        ):
            raise TypeError(
                "source_pursuit must be a RetreatPursuitResolutionResult"
            )
        decision = self.complication_roll_decision
        option_available = (
            self.source_pursuit.complication_table_roll_option_available
        )
        if option_available and not isinstance(
            decision,
            RunForYourLivesComplicationRollDecision,
        ):
            raise ValueError(
                "the available multiple-Complications roll requires an "
                "explicit GM decision"
            )
        if not option_available and decision is not None:
            raise ValueError(
                "a Complication roll decision is not available for this pursuit"
            )
        _validate_non_empty_string(self.rule_id, "Run For Your Lives rule_id")
        if self.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
            raise ValueError("Run For Your Lives requires its canonical rule")

    @property
    def include_complication_roll(self) -> bool:
        decision = self.complication_roll_decision
        return (
            decision is not None
            and decision.choice
            is RunForYourLivesComplicationRollChoice.ROLL
        )


@dataclass(frozen=True, slots=True)
class RunForYourLivesRoll:
    reason: RunForYourLivesRollReason
    value: int
    failed_actor_id: str | None = None
    source_complication_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.reason, RunForYourLivesRollReason):
            raise TypeError("reason must be a RunForYourLivesRollReason")
        if not isinstance(self.value, int) or isinstance(self.value, bool):
            raise TypeError("Run For Your Lives roll value must be an integer")
        if not 1 <= self.value <= 10:
            raise ValueError("Run For Your Lives uses a d10")
        complication_ids = tuple(self.source_complication_ids)
        if self.reason is RunForYourLivesRollReason.FAILED_ESCAPE:
            _validate_non_empty_string(
                self.failed_actor_id,
                "Run For Your Lives failed_actor_id",
            )
            if complication_ids:
                raise ValueError(
                    "a failed-escape roll cannot cite Complications"
                )
        else:
            if self.failed_actor_id is not None:
                raise ValueError(
                    "a multiple-Complications roll cannot name a failed actor"
                )
            complication_ids = _validate_unique_ids(
                complication_ids,
                "Run For Your Lives source_complication_ids",
            )
            if len(complication_ids) < 2:
                raise ValueError(
                    "a multiple-Complications roll requires at least two IDs"
                )
        object.__setattr__(self, "source_complication_ids", complication_ids)


@dataclass(frozen=True, slots=True)
class RunForYourLivesCampaignConsequenceRequest:
    id: str
    source_request_id: str
    battle_id: str
    retreat_id: str
    player_character_ids: tuple[str, ...]
    cover_kind: RetreatCoverKind
    cover_proof_id: str
    rearguard_actor_id: str | None
    failed_actor_ids: tuple[str, ...]
    complication_ids: tuple[str, ...]
    table_total: int
    outcome: RunForYourLivesOutcome
    decision_owner: DecisionOwner = DecisionOwner.GM
    rule_id: str = RUN_FOR_YOUR_LIVES_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "campaign consequence request id")
        _validate_non_empty_string(
            self.source_request_id,
            "campaign consequence source_request_id",
        )
        _validate_non_empty_string(self.battle_id, "campaign consequence battle_id")
        _validate_non_empty_string(self.retreat_id, "campaign consequence retreat_id")
        player_ids = _validate_unique_ids(
            self.player_character_ids,
            "campaign consequence player_character_ids",
        )
        if not isinstance(self.cover_kind, RetreatCoverKind):
            raise TypeError("cover_kind must be a RetreatCoverKind")
        _validate_non_empty_string(
            self.cover_proof_id,
            "campaign consequence cover_proof_id",
        )
        if self.cover_kind is RetreatCoverKind.FATE_REARGUARD:
            _validate_non_empty_string(
                self.rearguard_actor_id,
                "campaign consequence rearguard_actor_id",
            )
            if self.rearguard_actor_id not in player_ids:
                raise ValueError("Retreat rearguard must belong to the player group")
        elif self.rearguard_actor_id is not None:
            raise ValueError("an alternative Retreat price has no rearguard actor")
        failed_ids = tuple(self.failed_actor_ids)
        if any(actor_id not in player_ids for actor_id in failed_ids):
            raise ValueError("failed Retreat actors must belong to the player group")
        if len(set(failed_ids)) != len(failed_ids):
            raise ValueError("failed Retreat actor IDs must be unique")
        complication_ids = tuple(self.complication_ids)
        for complication_id in complication_ids:
            _validate_non_empty_string(
                complication_id,
                "campaign consequence Complication ID",
            )
        if len(set(complication_ids)) != len(complication_ids):
            raise ValueError("campaign consequence Complication IDs must be unique")
        if not isinstance(self.table_total, int) or isinstance(
            self.table_total,
            bool,
        ):
            raise TypeError("Run For Your Lives table_total must be an integer")
        if self.table_total < 1:
            raise ValueError("campaign consequence requires a positive table total")
        if not isinstance(self.outcome, RunForYourLivesOutcome):
            raise TypeError("outcome must be a RunForYourLivesOutcome")
        if self.outcome is not classify_run_for_your_lives(self.table_total):
            raise ValueError(
                "campaign consequence outcome disagrees with its table total"
            )
        if self.decision_owner is not DecisionOwner.GM:
            raise ValueError("the GM applies Run For Your Lives consequences")
        _validate_non_empty_string(self.rule_id, "campaign consequence rule_id")
        if self.rule_id != RUN_FOR_YOUR_LIVES_RULE_ID:
            raise ValueError("campaign consequence uses an unknown rule")
        object.__setattr__(self, "player_character_ids", player_ids)
        object.__setattr__(self, "failed_actor_ids", failed_ids)
        object.__setattr__(self, "complication_ids", complication_ids)


@dataclass(frozen=True, slots=True)
class RunForYourLivesResolutionResult:
    request_id: str
    rule_id: str
    source_request: RunForYourLivesResolutionRequest
    rolls: tuple[RunForYourLivesRoll, ...]
    table_total: int
    outcome: RunForYourLivesOutcome | None
    campaign_consequence: RunForYourLivesCampaignConsequenceRequest | None
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Run For Your Lives request_id")
        _validate_non_empty_string(self.rule_id, "Run For Your Lives result rule_id")
        if not isinstance(self.source_request, RunForYourLivesResolutionRequest):
            raise TypeError(
                "source_request must be a RunForYourLivesResolutionRequest"
            )
        rolls = tuple(self.rolls)
        if not all(isinstance(item, RunForYourLivesRoll) for item in rolls):
            raise TypeError("rolls must contain RunForYourLivesRoll values")
        expected_failed = self.source_request.source_pursuit.failed_actor_ids
        failed_rolls = tuple(
            item.failed_actor_id
            for item in rolls
            if item.reason is RunForYourLivesRollReason.FAILED_ESCAPE
        )
        complication_rolls = tuple(
            item
            for item in rolls
            if item.reason
            is RunForYourLivesRollReason.MULTIPLE_COMPLICATIONS
        )
        expected_complication_roll_count = int(
            self.source_request.include_complication_roll
        )
        if failed_rolls != expected_failed:
            raise ValueError("Run For Your Lives failed rolls are out of order")
        if len(complication_rolls) != expected_complication_roll_count:
            raise ValueError("Run For Your Lives Complication roll count is invalid")
        if complication_rolls and (
            complication_rolls[0].source_complication_ids
            != self.source_request.source_pursuit.complication_ids
        ):
            raise ValueError("Run For Your Lives Complication provenance is stale")
        expected_reason_order = (
            (RunForYourLivesRollReason.FAILED_ESCAPE,) * len(expected_failed)
            + (RunForYourLivesRollReason.MULTIPLE_COMPLICATIONS,)
            * expected_complication_roll_count
        )
        if tuple(item.reason for item in rolls) != expected_reason_order:
            raise ValueError("Run For Your Lives rolls are out of order")
        expected_total = sum(item.value for item in rolls)
        expected_outcome = (
            classify_run_for_your_lives(expected_total) if rolls else None
        )
        expected_consequence = _run_for_your_lives_campaign_consequence(
            self.source_request,
            expected_total,
            expected_outcome,
        )
        expected_rules = tuple(
            dict.fromkeys(
                (
                    *self.source_request.source_pursuit.applied_rule_ids,
                    self.source_request.rule_id,
                )
            )
        )
        if (
            self.request_id != self.source_request.id
            or self.rule_id != self.source_request.rule_id
            or self.table_total != expected_total
            or self.outcome is not expected_outcome
            or self.campaign_consequence != expected_consequence
            or self.applied_rule_ids != expected_rules
        ):
            raise ValueError("Run For Your Lives result has stale provenance")
        object.__setattr__(self, "rolls", rolls)


def classify_run_for_your_lives(total: int) -> RunForYourLivesOutcome:
    if not isinstance(total, int) or isinstance(total, bool):
        raise TypeError("Run For Your Lives total must be an integer")
    if total < 1:
        raise ValueError("Run For Your Lives total must be positive")
    if total <= 3:
        return RunForYourLivesOutcome.LOST
    if total <= 6:
        return RunForYourLivesOutcome.MOCKED
    if total <= 9:
        return RunForYourLivesOutcome.INDEBTED
    if total <= 12:
        return RunForYourLivesOutcome.MARKED
    if total <= 15:
        return RunForYourLivesOutcome.EXPOSED
    if total <= 18:
        return RunForYourLivesOutcome.HUNTED
    if total <= 21:
        return RunForYourLivesOutcome.ROBBED
    if total <= 24:
        return RunForYourLivesOutcome.SURROUNDED
    return RunForYourLivesOutcome.TRAPPED


def _run_for_your_lives_campaign_consequence(
    request: RunForYourLivesResolutionRequest,
    table_total: int,
    outcome: RunForYourLivesOutcome | None,
) -> RunForYourLivesCampaignConsequenceRequest | None:
    if outcome is None:
        return None
    pursuit = request.source_pursuit
    cover = pursuit.source_request.source_cover
    retreat = _retreat_from_cover(cover)
    return RunForYourLivesCampaignConsequenceRequest(
        id=f"{request.id}:campaign-consequence",
        source_request_id=request.id,
        battle_id=retreat.battle_id,
        retreat_id=retreat.id,
        player_character_ids=retreat.player_character_ids,
        cover_kind=_retreat_cover_kind(cover),
        cover_proof_id=_retreat_cover_proof_id(cover),
        rearguard_actor_id=(
            cover.rearguard_actor_id
            if isinstance(cover, RetreatRearGuardResult)
            else None
        ),
        failed_actor_ids=pursuit.failed_actor_ids,
        complication_ids=pursuit.complication_ids,
        table_total=table_total,
        outcome=outcome,
    )


def _escape_attempt_test_ids(attempt: RetreatEscapeAttempt) -> tuple[str, ...]:
    test = attempt.test
    if isinstance(test, TestRequest):
        return (test.id,)
    if isinstance(test, OpposedTestRequest):
        return (test.id, test.initiator.id, test.opponent.id)
    return ()


def _validate_escape_test_result(
    attempt: RetreatEscapeAttempt,
    result: RetreatEscapeTestResult | None,
) -> None:
    test = attempt.test
    if isinstance(test, TestRequest):
        if not isinstance(result, TestResult):
            raise TypeError("basic Retreat escape requires a TestResult")
        if result.trace.request_id != test.id:
            raise ValueError("Retreat Test result belongs to another request")
        return
    if not isinstance(test, OpposedTestRequest):
        raise TypeError("Retreat escape attempt has no Test request")
    if not isinstance(result, OpposedTestResult):
        raise TypeError("opposed Retreat escape requires OpposedTestResult")
    if (
        result.request_id != test.id
        or result.initiator.trace.request_id != test.initiator.id
        or result.opponent.trace.request_id != test.opponent.id
    ):
        raise ValueError("Retreat Opposed Test result belongs elsewhere")
    _validate_opposed_result(test, result)


def _validate_opposed_result(
    request: OpposedTestRequest,
    result: OpposedTestResult,
) -> None:
    initiator = result.initiator.successes
    opponent = result.opponent.successes
    if initiator == 0 and opponent == 0:
        expected = (
            OpposedOutcome.BOTH_FAIL,
            None,
            0,
            None,
            False,
            None,
        )
    elif initiator == opponent:
        winner = request.tie_break.winner
        expected = (
            (
                OpposedOutcome.INITIATOR_WINS
                if winner is OpposedSide.INITIATOR
                else OpposedOutcome.OPPONENT_WINS
            ),
            winner,
            0,
            BasicOutcome.MARGINAL_SUCCESS,
            True,
            request.tie_break.rule_id,
        )
    else:
        winner = (
            OpposedSide.INITIATOR
            if initiator > opponent
            else OpposedSide.OPPONENT
        )
        margin = abs(initiator - opponent)
        expected = (
            (
                OpposedOutcome.INITIATOR_WINS
                if winner is OpposedSide.INITIATOR
                else OpposedOutcome.OPPONENT_WINS
            ),
            winner,
            margin,
            _basic_outcome(margin),
            False,
            None,
        )
    actual = (
        result.outcome,
        result.winner,
        result.success_margin,
        result.consequence,
        result.tie_break_applied,
        result.tie_break_rule_id,
    )
    if actual != expected:
        raise ValueError("Retreat Opposed Test result is internally inconsistent")


def _escape_test_succeeded(result: RetreatEscapeTestResult) -> bool:
    if isinstance(result, TestResult):
        return result.succeeded
    return result.winner is OpposedSide.INITIATOR


def _escape_test_is_marginal(result: RetreatEscapeTestResult) -> bool:
    if isinstance(result, TestResult):
        return result.successes == 1
    return (
        result.winner is OpposedSide.INITIATOR
        and result.consequence is BasicOutcome.MARGINAL_SUCCESS
    )


def _pursuit_rule_ids(
    request: RetreatPursuitResolutionRequest,
    results: tuple[RetreatEscapeResult, ...],
) -> tuple[str, ...]:
    test_rule_ids = tuple(
        rule_id
        for result in results
        for rule_id in _escape_test_rule_ids(result.test_result)
    )
    return tuple(
        dict.fromkeys(
            (
                *request.source_cover.applied_rule_ids,
                *test_rule_ids,
                request.rule_id,
            )
        )
    )


def _escape_test_rule_ids(
    result: RetreatEscapeTestResult | None,
) -> tuple[str, ...]:
    if result is None:
        return ()
    if isinstance(result, TestResult):
        return result.trace.applied_rule_ids
    tie_rules = (
        (result.tie_break_rule_id,)
        if result.tie_break_applied and result.tie_break_rule_id is not None
        else ()
    )
    return tuple(
        dict.fromkeys(
            (
                *result.initiator.trace.applied_rule_ids,
                *result.opponent.trace.applied_rule_ids,
                *tie_rules,
            )
        )
    )


def _basic_outcome(successes: int) -> BasicOutcome:
    if successes == 1:
        return BasicOutcome.MARGINAL_SUCCESS
    if successes == 2:
        return BasicOutcome.SUCCESS
    return BasicOutcome.TOTAL_SUCCESS


def _retreat_alternative_price_proof(
    request: RetreatAlternativePriceRequest,
    decision: RetreatAlternativePriceDecision,
) -> RetreatAlternativePriceProof:
    retreat = request.source_retreat
    return RetreatAlternativePriceProof(
        id=f"{request.id}:proof",
        source_request_id=request.id,
        decision_id=decision.id,
        retreat_id=retreat.id,
        battle_id=retreat.battle_id,
        player_character_ids=retreat.player_character_ids,
        price=decision.price,
    )


def _retreat_alternative_price_application(
    request: RetreatAlternativePriceRequest,
    proof: RetreatAlternativePriceProof,
) -> RetreatAlternativePriceApplicationRequest:
    retreat = request.source_retreat
    common = {
        "id": f"{request.id}:application",
        "source_proof_id": proof.id,
        "battle_id": retreat.battle_id,
        "retreat_id": retreat.id,
    }
    if proof.price is RetreatAlternativePrice.BLOOD:
        return RetreatBloodPriceApplicationRequest(
            **common,
            possible_target_actor_ids=retreat.player_character_ids,
        )
    if proof.price is RetreatAlternativePrice.MATERIEL:
        return RetreatMaterielPriceApplicationRequest(
            **common,
            possible_owner_actor_ids=retreat.player_character_ids,
        )
    enemy_ids = tuple(
        participant.entity_id
        for participant in retreat.round_state.participants
        if participant.side is CombatSide.OPPOSITION
    )
    return RetreatMisfortunePriceApplicationRequest(
        **common,
        beneficiary_enemy_ids=enemy_ids,
    )


def _validate_price_application_context(
    request: RetreatAlternativePriceApplicationRequest,
) -> None:
    _validate_non_empty_string(request.id, "Retreat price application id")
    _validate_non_empty_string(
        request.source_proof_id,
        "Retreat price application source_proof_id",
    )
    _validate_non_empty_string(request.battle_id, "Retreat price application battle_id")
    _validate_non_empty_string(request.retreat_id, "Retreat price application retreat_id")
    if request.decision_owner is not DecisionOwner.GM:
        raise ValueError("the GM applies the alternative Retreat price")
    _validate_non_empty_string(request.rule_id, "Retreat price application rule_id")
    if request.rule_id != RETREAT_ALTERNATIVE_PRICE_RULE_ID:
        raise ValueError("Retreat price application uses an unknown rule")


def _retreat_from_cover(source: RetreatCoverResult) -> GroupRetreatDeclaration:
    if isinstance(source, RetreatRearGuardResult):
        return source.source_request
    return source.source_request.source_retreat


def _retreat_cover_kind(source: RetreatCoverResult) -> RetreatCoverKind:
    if isinstance(source, RetreatRearGuardResult):
        return RetreatCoverKind.FATE_REARGUARD
    return RetreatCoverKind.ALTERNATIVE_PRICE


def _retreat_cover_proof_id(source: RetreatCoverResult) -> str:
    if isinstance(source, RetreatRearGuardResult):
        return source.fate_proof_id
    return source.proof.id


def _validate_retreat_timing(state: CombatRoundState) -> None:
    completed = set(state.completed_turn_entity_ids)
    if not completed:
        if state.side_order[0] is CombatSide.PLAYERS_AND_ALLIES:
            return
        raise ValueError(
            "Retreat waits for the players side when enemies act first"
        )
    if state.side_order[0] is not CombatSide.OPPOSITION:
        raise ValueError("Retreat is no longer at the start of the round")
    opposition_ids = {
        item.entity_id
        for item in state.participants
        if item.side is CombatSide.OPPOSITION
    }
    if completed != opposition_ids or state.next_side is not CombatSide.PLAYERS_AND_ALLIES:
        raise ValueError(
            "Retreat after enemy actions requires the start of the players side"
        )


def _validate_unique_ids(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    ids = tuple(values)
    if not ids:
        raise ValueError(f"{name} must not be empty")
    for value in ids:
        _validate_non_empty_string(value, name)
    if len(set(ids)) != len(ids):
        raise ValueError(f"{name} must be unique")
    return ids


def _validate_rule_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    rule_ids = tuple(values)
    if not rule_ids:
        raise ValueError("applied_rule_ids must not be empty")
    for rule_id in rule_ids:
        _validate_non_empty_string(rule_id, "applied Rule ID")
    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError("applied_rule_ids must be unique")
    return rule_ids


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
