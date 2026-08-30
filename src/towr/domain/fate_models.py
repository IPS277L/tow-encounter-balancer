from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum

from towr.domain.injury_models import DecisionOwner
from towr.domain.lucky_models import LUCKY_RULE_ID
from towr.domain.retreat_models import (
    RETREAT_ALTERNATIVE_PRICE_RULE_ID,
    RETREAT_RULE_ID,
    GroupRetreatDeclaration,
    RetreatAlternativePriceRequest,
    RetreatRearGuardResult,
)
from towr.domain.resolution_models import ConsumeWoundNegationRequest
from towr.domain.test_models import (
    BasicOutcome,
    FATE_GLORIOUS_RULE_ID,
    FateGloriousProof,
    InitialTestRoll,
    QualityModifier,
    QualityModifierSource,
    TestQuality,
    TestRequest,
)
from towr.domain.turn_models import (
    ACTION_BUDGET_RULE_ID,
    ActionSlotGrant,
    CombatActionDeclaration,
    CombatActionSlotRequest,
    CombatActionSlotResult,
)


FATE_SESSION_RULE_ID = "RULE-FATE-001:session-resource"
FATE_REFRESH_RULE_ID = "RULE-FATE-001:refresh"
FATE_SECOND_ACTION_RULE_ID = "RULE-FATE-002:second-action"
FATE_TACTICAL_RETREAT_RULE_ID = "RULE-FATE-002:tactical-retreat"
FATE_LUCKY_RULE_ID = LUCKY_RULE_ID
FATE_BURN_RULE_ID = "RULE-FATE-003:burn"
FATE_UNMITIGATED_SUCCESS_RULE_ID = "RULE-FATE-003:unmitigated-success"
FATE_NEAR_MISS_RULE_ID = "RULE-FATE-003:near-miss"
FATE_LAST_STAND_RULE_ID = "RULE-FATE-003:last-stand"


class FateSpendKind(str, Enum):
    GLORIOUS_TEST = "glorious_test"
    SECOND_ACTION = "second_action"
    TACTICAL_RETREAT = "tactical_retreat"


class FateSpendFunding(str, Enum):
    SESSION_POOL = "session_pool"
    LUCKY_FREE = "lucky_free"


class FateBurnKind(str, Enum):
    UNMITIGATED_SUCCESS = "unmitigated_success"
    NEAR_MISS = "near_miss"
    LAST_STAND = "last_stand"


@dataclass(frozen=True, slots=True)
class FateSpendRecord:
    id: str
    session_id: str
    actor_id: str
    kind: FateSpendKind
    subject_id: str
    rule_id: str
    funding: FateSpendFunding = FateSpendFunding.SESSION_POOL

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Fate spend id")
        _validate_non_empty_string(self.session_id, "Fate spend session_id")
        _validate_non_empty_string(self.actor_id, "Fate spend actor_id")
        if not isinstance(self.kind, FateSpendKind):
            raise TypeError("kind must be a FateSpendKind")
        _validate_non_empty_string(self.subject_id, "Fate spend subject_id")
        _validate_non_empty_string(self.rule_id, "Fate spend rule_id")
        if not isinstance(self.funding, FateSpendFunding):
            raise TypeError("funding must be a FateSpendFunding")
        if (
            self.kind is FateSpendKind.GLORIOUS_TEST
            and self.rule_id != FATE_GLORIOUS_RULE_ID
        ):
            raise ValueError("Glorious Test spend requires its canonical rule")
        if (
            self.kind is FateSpendKind.SECOND_ACTION
            and self.rule_id != FATE_SECOND_ACTION_RULE_ID
        ):
            raise ValueError("second action spend requires its canonical rule")
        if (
            self.kind is FateSpendKind.TACTICAL_RETREAT
            and self.rule_id != FATE_TACTICAL_RETREAT_RULE_ID
        ):
            raise ValueError("Tactical Retreat spend requires its canonical rule")

    @property
    def session_cost(self) -> int:
        return int(self.funding is FateSpendFunding.SESSION_POOL)


@dataclass(frozen=True, slots=True)
class FateRefreshRecord:
    id: str
    session_id: str
    actor_id: str
    mid_session_break_id: str
    gm_approval_id: str
    previous_spend_limit: int
    restored_spends: int
    new_spend_limit: int
    rule_id: str = FATE_REFRESH_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Fate refresh id")
        _validate_non_empty_string(self.session_id, "Fate refresh session_id")
        _validate_non_empty_string(self.actor_id, "Fate refresh actor_id")
        _validate_non_empty_string(
            self.mid_session_break_id,
            "Fate refresh mid_session_break_id",
        )
        _validate_non_empty_string(
            self.gm_approval_id,
            "Fate refresh gm_approval_id",
        )
        _validate_non_negative_int(
            self.previous_spend_limit,
            "Fate refresh previous_spend_limit",
        )
        _validate_positive_int(self.restored_spends, "Fate restored_spends")
        _validate_non_negative_int(
            self.new_spend_limit,
            "Fate refresh new_spend_limit",
        )
        if self.new_spend_limit != (
            self.previous_spend_limit + self.restored_spends
        ):
            raise ValueError("Fate refresh limits do not match restored spends")
        _validate_non_empty_string(self.rule_id, "Fate refresh rule_id")
        if self.rule_id != FATE_REFRESH_RULE_ID:
            raise ValueError("Fate refresh requires its canonical rule")


@dataclass(frozen=True, slots=True)
class FateBurnRecord:
    id: str
    session_id: str
    actor_id: str
    kind: FateBurnKind
    subject_id: str
    previous_rating: int
    new_rating: int
    previous_spend_limit: int
    new_spend_limit: int
    current_session_allowance_reduced: bool
    rule_id: str = FATE_BURN_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Fate burn id")
        _validate_non_empty_string(self.session_id, "Fate burn session_id")
        _validate_non_empty_string(self.actor_id, "Fate burn actor_id")
        if not isinstance(self.kind, FateBurnKind):
            raise TypeError("kind must be a FateBurnKind")
        _validate_non_empty_string(self.subject_id, "Fate burn subject_id")
        _validate_positive_int(self.previous_rating, "Fate burn previous_rating")
        _validate_non_negative_int(self.new_rating, "Fate burn new_rating")
        if self.new_rating != self.previous_rating - 1:
            raise ValueError("burn must permanently reduce Fate rating by one")
        _validate_non_negative_int(
            self.previous_spend_limit,
            "Fate burn previous_spend_limit",
        )
        _validate_non_negative_int(
            self.new_spend_limit,
            "Fate burn new_spend_limit",
        )
        if not isinstance(self.current_session_allowance_reduced, bool):
            raise TypeError("current_session_allowance_reduced must be a bool")
        expected_limit = self.previous_spend_limit - int(
            self.current_session_allowance_reduced
        )
        if self.new_spend_limit != expected_limit:
            raise ValueError("Fate burn allowance transition is invalid")
        _validate_non_empty_string(self.rule_id, "Fate burn rule_id")
        if self.rule_id != FATE_BURN_RULE_ID:
            raise ValueError("Fate burn requires its canonical rule")


@dataclass(frozen=True, slots=True)
class FateSessionState:
    session_id: str
    actor_id: str
    rating: int
    session_spend_limit: int
    spends: tuple[FateSpendRecord, ...] = field(default_factory=tuple)
    has_lucky: bool = False
    refreshes: tuple[FateRefreshRecord, ...] = field(default_factory=tuple)
    burns: tuple[FateBurnRecord, ...] = field(default_factory=tuple)
    resource_event_ids: tuple[str, ...] = field(default_factory=tuple)
    rule_id: str = FATE_SESSION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.session_id, "Fate session_id")
        _validate_non_empty_string(self.actor_id, "Fate actor_id")
        _validate_non_negative_int(self.rating, "Fate rating")
        _validate_non_negative_int(
            self.session_spend_limit,
            "Fate session_spend_limit",
        )
        _validate_non_empty_string(self.rule_id, "Fate session rule_id")
        if self.rule_id != FATE_SESSION_RULE_ID:
            raise ValueError("Fate session state requires its canonical rule")
        spends = tuple(self.spends)
        if not all(isinstance(item, FateSpendRecord) for item in spends):
            raise TypeError("spends must contain FateSpendRecord values")
        if not isinstance(self.has_lucky, bool):
            raise TypeError("has_lucky must be a bool")
        paid_spends = sum(item.session_cost for item in spends)
        if paid_spends > self.session_spend_limit:
            raise ValueError("Fate spends cannot exceed the session limit")
        spend_ids = tuple(item.id for item in spends)
        if len(set(spend_ids)) != len(spend_ids):
            raise ValueError("Fate spend IDs must be unique")
        if any(
            item.session_id != self.session_id
            or item.actor_id != self.actor_id
            for item in spends
        ):
            raise ValueError("Fate spend belongs to another session or actor")
        lucky_indices = tuple(
            index
            for index, item in enumerate(spends)
            if item.funding is FateSpendFunding.LUCKY_FREE
        )
        if lucky_indices and (not self.has_lucky or lucky_indices != (0,)):
            raise ValueError("only a Lucky actor's first Fate spend can be free")
        if self.has_lucky and spends and spends[0].funding is not FateSpendFunding.LUCKY_FREE:
            raise ValueError("a Lucky actor's first Fate spend must be free")
        glorious_test_ids = tuple(
            item.subject_id
            for item in spends
            if item.kind is FateSpendKind.GLORIOUS_TEST
        )
        if len(set(glorious_test_ids)) != len(glorious_test_ids):
            raise ValueError("Fate cannot make the same Test Glorious twice")
        second_action_ids = tuple(
            item.subject_id
            for item in spends
            if item.kind is FateSpendKind.SECOND_ACTION
        )
        if len(set(second_action_ids)) != len(second_action_ids):
            raise ValueError("Fate cannot grant the same second action twice")
        tactical_retreat_ids = tuple(
            item.subject_id
            for item in spends
            if item.kind is FateSpendKind.TACTICAL_RETREAT
        )
        if len(set(tactical_retreat_ids)) != len(tactical_retreat_ids):
            raise ValueError("Fate cannot fund the same Retreat twice")

        refreshes = tuple(self.refreshes)
        if not all(isinstance(item, FateRefreshRecord) for item in refreshes):
            raise TypeError("refreshes must contain FateRefreshRecord values")
        refresh_ids = tuple(item.id for item in refreshes)
        break_ids = tuple(item.mid_session_break_id for item in refreshes)
        approval_ids = tuple(item.gm_approval_id for item in refreshes)
        if (
            len(set(refresh_ids)) != len(refresh_ids)
            or len(set(break_ids)) != len(break_ids)
            or len(set(approval_ids)) != len(approval_ids)
        ):
            raise ValueError("Fate refresh IDs, breaks, and approvals must be unique")
        if any(
            item.session_id != self.session_id
            or item.actor_id != self.actor_id
            for item in refreshes
        ):
            raise ValueError("Fate refresh belongs to another session or actor")

        burns = tuple(self.burns)
        if not all(isinstance(item, FateBurnRecord) for item in burns):
            raise TypeError("burns must contain FateBurnRecord values")
        burn_ids = tuple(item.id for item in burns)
        burn_subjects = tuple((item.kind, item.subject_id) for item in burns)
        if len(set(burn_ids)) != len(burn_ids):
            raise ValueError("Fate burn IDs must be unique")
        if len(set(burn_subjects)) != len(burn_subjects):
            raise ValueError("Fate cannot burn twice for the same subject and kind")
        if any(
            item.session_id != self.session_id
            or item.actor_id != self.actor_id
            for item in burns
        ):
            raise ValueError("Fate burn belongs to another session or actor")

        resource_event_ids = tuple(self.resource_event_ids)
        for event_id in resource_event_ids:
            _validate_non_empty_string(event_id, "Fate resource event ID")
        if len(set(resource_event_ids)) != len(resource_event_ids):
            raise ValueError("Fate resource event IDs must be unique")
        records_by_id = {
            item.id: item
            for item in (*refreshes, *burns)
        }
        if (
            len(records_by_id) != len(refreshes) + len(burns)
            or set(resource_event_ids) != set(records_by_id)
        ):
            raise ValueError(
                "Fate resource event order must contain every refresh and burn once"
            )
        if set(spend_ids) & set(resource_event_ids):
            raise ValueError("Fate spend and resource event IDs must be distinct")
        if resource_event_ids:
            rating = self.rating + len(burns)
            spend_limit = records_by_id[
                resource_event_ids[0]
            ].previous_spend_limit
            for event_id in resource_event_ids:
                event = records_by_id[event_id]
                if event.previous_spend_limit != spend_limit:
                    raise ValueError("Fate resource event history is not contiguous")
                if isinstance(event, FateBurnRecord):
                    if event.previous_rating != rating:
                        raise ValueError("Fate burn rating history is not contiguous")
                    rating = event.new_rating
                spend_limit = event.new_spend_limit
            if rating != self.rating or spend_limit != self.session_spend_limit:
                raise ValueError("Fate resource history disagrees with session state")
        object.__setattr__(self, "spends", spends)
        object.__setattr__(self, "refreshes", refreshes)
        object.__setattr__(self, "burns", burns)
        object.__setattr__(self, "resource_event_ids", resource_event_ids)

    @property
    def remaining_spends(self) -> int:
        return self.session_spend_limit - sum(
            item.session_cost for item in self.spends
        )

    @property
    def lucky_free_spend_available(self) -> bool:
        return self.has_lucky and not self.spends

    @property
    def session_refresh_rating(self) -> int:
        deferred_burns = sum(
            not item.current_session_allowance_reduced
            for item in self.burns
        )
        return self.rating + deferred_burns

    @property
    def can_spend(self) -> bool:
        return self.lucky_free_spend_available or self.remaining_spends > 0


@dataclass(frozen=True, slots=True)
class FateRefreshRequest:
    id: str
    state: FateSessionState
    mid_session_break_id: str
    gm_approval_id: str
    decision_owner: DecisionOwner = DecisionOwner.GM
    rule_id: str = FATE_REFRESH_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Fate refresh request id")
        if not isinstance(self.state, FateSessionState):
            raise TypeError("state must be a FateSessionState")
        _validate_non_empty_string(
            self.mid_session_break_id,
            "Fate refresh request mid_session_break_id",
        )
        _validate_non_empty_string(
            self.gm_approval_id,
            "Fate refresh request gm_approval_id",
        )
        if self.decision_owner is not DecisionOwner.GM:
            raise ValueError("only the GM may allow a mid-session Fate refresh")
        if self.state.session_refresh_rating < 1:
            raise ValueError("zero Fate rating cannot restore session spends")
        if self.state.remaining_spends >= self.state.session_refresh_rating:
            raise ValueError("Fate is already refreshed to its rating")
        if self.id in {
            *(item.id for item in self.state.spends),
            *self.state.resource_event_ids,
        }:
            raise ValueError("Fate refresh request was already consumed")
        if self.mid_session_break_id in {
            item.mid_session_break_id for item in self.state.refreshes
        }:
            raise ValueError("this mid-session break already refreshed Fate")
        if self.gm_approval_id in {
            item.gm_approval_id for item in self.state.refreshes
        }:
            raise ValueError("this GM approval already refreshed Fate")
        _validate_non_empty_string(self.rule_id, "Fate refresh request rule_id")


@dataclass(frozen=True, slots=True)
class FateRefreshResult:
    request_id: str
    rule_id: str
    source_request: FateRefreshRequest
    previous_state: FateSessionState
    state: FateSessionState
    refresh: FateRefreshRecord
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Fate refresh result request_id")
        _validate_non_empty_string(self.rule_id, "Fate refresh result rule_id")
        if not isinstance(self.source_request, FateRefreshRequest):
            raise TypeError("source_request must be a FateRefreshRequest")
        if not isinstance(self.previous_state, FateSessionState):
            raise TypeError("previous_state must be a FateSessionState")
        if not isinstance(self.state, FateSessionState):
            raise TypeError("state must be a FateSessionState")
        if not isinstance(self.refresh, FateRefreshRecord):
            raise TypeError("refresh must be a FateRefreshRecord")
        expected_refresh, expected_state = _expected_fate_refresh(
            self.source_request
        )
        expected_rules = (FATE_SESSION_RULE_ID, FATE_REFRESH_RULE_ID)
        if (
            self.request_id != self.source_request.id
            or self.rule_id != self.source_request.rule_id
            or self.previous_state != self.source_request.state
            or self.refresh != expected_refresh
            or self.state != expected_state
            or self.applied_rule_ids != expected_rules
        ):
            raise ValueError("Fate refresh result has stale provenance")


@dataclass(frozen=True, slots=True)
class FateUnmitigatedSuccessBurnRequest:
    id: str
    state: FateSessionState
    test: TestRequest
    initial_roll: InitialTestRoll | None = None
    gm_scope_agreement_id: str | None = None
    decision_owner: DecisionOwner = DecisionOwner.ACTOR
    rule_id: str = FATE_UNMITIGATED_SUCCESS_RULE_ID

    def __post_init__(self) -> None:
        if not isinstance(self.test, TestRequest):
            raise TypeError("test must be a TestRequest")
        if self.initial_roll is not None:
            if not isinstance(self.initial_roll, InitialTestRoll):
                raise TypeError("initial_roll must be an InitialTestRoll or None")
            if self.initial_roll.request != self.test:
                raise ValueError("initial_roll belongs to another Test")
        if self.gm_scope_agreement_id is not None:
            _validate_non_empty_string(
                self.gm_scope_agreement_id,
                "Unmitigated Success gm_scope_agreement_id",
            )
        _validate_fate_burn_request(
            self.id,
            self.state,
            FateBurnKind.UNMITIGATED_SUCCESS,
            self.test.id,
            self.decision_owner,
            self.rule_id,
            FATE_UNMITIGATED_SUCCESS_RULE_ID,
        )

    @property
    def kind(self) -> FateBurnKind:
        return FateBurnKind.UNMITIGATED_SUCCESS

    @property
    def subject_id(self) -> str:
        return self.test.id


@dataclass(frozen=True, slots=True)
class FateNearMissBurnRequest:
    id: str
    state: FateSessionState
    wound_negation: ConsumeWoundNegationRequest
    decision_owner: DecisionOwner = DecisionOwner.ACTOR
    rule_id: str = FATE_NEAR_MISS_RULE_ID

    def __post_init__(self) -> None:
        if not isinstance(self.wound_negation, ConsumeWoundNegationRequest):
            raise TypeError(
                "wound_negation must be a ConsumeWoundNegationRequest"
            )
        _validate_non_empty_string(
            self.wound_negation.resolution_id,
            "Near Miss wound resolution_id",
        )
        if self.wound_negation.rule_id != FATE_NEAR_MISS_RULE_ID:
            raise ValueError("Near Miss wound negation requires its canonical rule")
        _validate_fate_burn_request(
            self.id,
            self.state,
            FateBurnKind.NEAR_MISS,
            self.wound_negation.resolution_id,
            self.decision_owner,
            self.rule_id,
            FATE_NEAR_MISS_RULE_ID,
        )

    @property
    def kind(self) -> FateBurnKind:
        return FateBurnKind.NEAR_MISS

    @property
    def subject_id(self) -> str:
        return self.wound_negation.resolution_id


@dataclass(frozen=True, slots=True)
class FateLastStandBurnRequest:
    id: str
    state: FateSessionState
    battle_id: str
    feat_id: str
    desperate_battle_approval_id: str
    has_suffered_wound: bool
    decision_owner: DecisionOwner = DecisionOwner.ACTOR
    rule_id: str = FATE_LAST_STAND_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.battle_id, "Last Stand battle_id")
        _validate_non_empty_string(self.feat_id, "Last Stand feat_id")
        _validate_non_empty_string(
            self.desperate_battle_approval_id,
            "Last Stand desperate_battle_approval_id",
        )
        if not isinstance(self.has_suffered_wound, bool):
            raise TypeError("has_suffered_wound must be a bool")
        if not self.has_suffered_wound:
            raise ValueError("Last Stand requires the actor to have suffered a Wound")
        _validate_fate_burn_request(
            self.id,
            self.state,
            FateBurnKind.LAST_STAND,
            self.battle_id,
            self.decision_owner,
            self.rule_id,
            FATE_LAST_STAND_RULE_ID,
        )

    @property
    def kind(self) -> FateBurnKind:
        return FateBurnKind.LAST_STAND

    @property
    def subject_id(self) -> str:
        return self.battle_id


FateBurnRequest = (
    FateUnmitigatedSuccessBurnRequest
    | FateNearMissBurnRequest
    | FateLastStandBurnRequest
)


@dataclass(frozen=True, slots=True)
class FateUnmitigatedSuccessEffectRequest:
    id: str
    source_proof_id: str
    session_id: str
    actor_id: str
    test: TestRequest
    initial_roll: InitialTestRoll | None
    gm_scope_agreement_id: str | None
    minimum_outcome: BasicOutcome = BasicOutcome.TOTAL_SUCCESS
    usual_outcome_superseded: bool = True
    requires_realistically_possible_outcome: bool = True
    may_not_kill_multiple_enemies: bool = True
    maximum_wounds_inflicted: int = 1
    rule_id: str = FATE_UNMITIGATED_SUCCESS_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Unmitigated Success effect id")
        _validate_non_empty_string(
            self.source_proof_id,
            "Unmitigated Success source_proof_id",
        )
        _validate_non_empty_string(self.session_id, "Fate session_id")
        _validate_non_empty_string(self.actor_id, "Fate actor_id")
        if not isinstance(self.test, TestRequest):
            raise TypeError("test must be a TestRequest")
        if self.initial_roll is not None:
            if not isinstance(self.initial_roll, InitialTestRoll):
                raise TypeError("initial_roll must be an InitialTestRoll or None")
            if self.initial_roll.request != self.test:
                raise ValueError("initial_roll belongs to another Test")
        if self.gm_scope_agreement_id is not None:
            _validate_non_empty_string(
                self.gm_scope_agreement_id,
                "Unmitigated Success gm_scope_agreement_id",
            )
        if self.minimum_outcome is not BasicOutcome.TOTAL_SUCCESS:
            raise ValueError("Unmitigated Success guarantees Total Success")
        if not all(
            value is True
            for value in (
                self.usual_outcome_superseded,
                self.requires_realistically_possible_outcome,
                self.may_not_kill_multiple_enemies,
            )
        ):
            raise ValueError("Unmitigated Success constraints must be preserved")
        if self.maximum_wounds_inflicted != 1:
            raise ValueError("Unmitigated Success can inflict at most one Wound")
        if self.rule_id != FATE_UNMITIGATED_SUCCESS_RULE_ID:
            raise ValueError("Unmitigated Success effect requires its canonical rule")


@dataclass(frozen=True, slots=True)
class FateNearMissEffectRequest:
    id: str
    source_proof_id: str
    session_id: str
    actor_id: str
    wound_negation: ConsumeWoundNegationRequest
    negates_just_suffered_wound: bool = True
    does_not_increase_future_wound_dice: bool = True
    preserves_pre_wound_staggered: bool = True
    rule_id: str = FATE_NEAR_MISS_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Near Miss effect id")
        _validate_non_empty_string(self.source_proof_id, "Near Miss source_proof_id")
        _validate_non_empty_string(self.session_id, "Fate session_id")
        _validate_non_empty_string(self.actor_id, "Fate actor_id")
        if not isinstance(self.wound_negation, ConsumeWoundNegationRequest):
            raise TypeError(
                "wound_negation must be a ConsumeWoundNegationRequest"
            )
        _validate_non_empty_string(
            self.wound_negation.resolution_id,
            "Near Miss wound resolution_id",
        )
        if self.wound_negation.rule_id != FATE_NEAR_MISS_RULE_ID:
            raise ValueError("Near Miss wound negation requires its canonical rule")
        if (
            self.negates_just_suffered_wound is not True
            or self.does_not_increase_future_wound_dice is not True
            or self.preserves_pre_wound_staggered is not True
        ):
            raise ValueError("Near Miss effect constraints must be preserved")
        if self.rule_id != FATE_NEAR_MISS_RULE_ID:
            raise ValueError("Near Miss effect requires its canonical rule")


@dataclass(frozen=True, slots=True)
class FateLastStandEffectRequest:
    id: str
    source_proof_id: str
    session_id: str
    actor_id: str
    battle_id: str
    feat_id: str
    desperate_battle_approval_id: str
    test_required: bool = False
    actor_dies_after_feat: bool = True
    gm_may_adjust_scope: bool = True
    rule_id: str = FATE_LAST_STAND_RULE_ID

    def __post_init__(self) -> None:
        for value, name in (
            (self.id, "Last Stand effect id"),
            (self.source_proof_id, "Last Stand source_proof_id"),
            (self.session_id, "Fate session_id"),
            (self.actor_id, "Fate actor_id"),
            (self.battle_id, "Last Stand battle_id"),
            (self.feat_id, "Last Stand feat_id"),
            (
                self.desperate_battle_approval_id,
                "Last Stand desperate_battle_approval_id",
            ),
        ):
            _validate_non_empty_string(value, name)
        if self.test_required is not False:
            raise ValueError("Last Stand feat does not require a Test")
        if (
            self.actor_dies_after_feat is not True
            or self.gm_may_adjust_scope is not True
        ):
            raise ValueError("Last Stand effect constraints must be preserved")
        if self.rule_id != FATE_LAST_STAND_RULE_ID:
            raise ValueError("Last Stand effect requires its canonical rule")


FateBurnEffectRequest = (
    FateUnmitigatedSuccessEffectRequest
    | FateNearMissEffectRequest
    | FateLastStandEffectRequest
)


@dataclass(frozen=True, slots=True)
class FateBurnProof:
    id: str
    session_id: str
    actor_id: str
    source_burn_id: str
    kind: FateBurnKind
    subject_id: str
    previous_rating: int
    new_rating: int
    rule_id: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.id, "Fate burn proof id"),
            (self.session_id, "Fate session_id"),
            (self.actor_id, "Fate actor_id"),
            (self.source_burn_id, "Fate burn source_burn_id"),
            (self.subject_id, "Fate burn subject_id"),
            (self.rule_id, "Fate burn proof rule_id"),
        ):
            _validate_non_empty_string(value, name)
        if not isinstance(self.kind, FateBurnKind):
            raise TypeError("kind must be a FateBurnKind")
        _validate_positive_int(self.previous_rating, "previous Fate rating")
        _validate_non_negative_int(self.new_rating, "new Fate rating")
        if self.new_rating != self.previous_rating - 1:
            raise ValueError("Fate burn proof must reduce rating by one")
        if self.rule_id not in {
            FATE_UNMITIGATED_SUCCESS_RULE_ID,
            FATE_NEAR_MISS_RULE_ID,
            FATE_LAST_STAND_RULE_ID,
        }:
            raise ValueError("Fate burn proof requires a burn-kind rule")
        expected_rule_id = {
            FateBurnKind.UNMITIGATED_SUCCESS: FATE_UNMITIGATED_SUCCESS_RULE_ID,
            FateBurnKind.NEAR_MISS: FATE_NEAR_MISS_RULE_ID,
            FateBurnKind.LAST_STAND: FATE_LAST_STAND_RULE_ID,
        }[self.kind]
        if self.rule_id != expected_rule_id:
            raise ValueError("Fate burn proof kind and rule disagree")


@dataclass(frozen=True, slots=True)
class FateBurnResult:
    request_id: str
    rule_id: str
    source_request: FateBurnRequest
    previous_state: FateSessionState
    state: FateSessionState
    burn: FateBurnRecord
    proof: FateBurnProof
    effect_request: FateBurnEffectRequest
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.request_id, "Fate burn result request_id")
        _validate_non_empty_string(self.rule_id, "Fate burn result rule_id")
        if not isinstance(
            self.source_request,
            (
                FateUnmitigatedSuccessBurnRequest,
                FateNearMissBurnRequest,
                FateLastStandBurnRequest,
            ),
        ):
            raise TypeError("source_request must be a Fate burn request")
        if not isinstance(self.previous_state, FateSessionState):
            raise TypeError("previous_state must be a FateSessionState")
        if not isinstance(self.state, FateSessionState):
            raise TypeError("state must be a FateSessionState")
        if not isinstance(self.burn, FateBurnRecord):
            raise TypeError("burn must be a FateBurnRecord")
        if not isinstance(self.proof, FateBurnProof):
            raise TypeError("proof must be a FateBurnProof")
        if not isinstance(
            self.effect_request,
            (
                FateUnmitigatedSuccessEffectRequest,
                FateNearMissEffectRequest,
                FateLastStandEffectRequest,
            ),
        ):
            raise TypeError("effect_request must be a Fate burn effect request")
        expected_burn, expected_proof, expected_state, expected_effect = (
            _expected_fate_burn(self.source_request)
        )
        expected_rules = (
            FATE_SESSION_RULE_ID,
            FATE_BURN_RULE_ID,
            self.source_request.rule_id,
        )
        if (
            self.request_id != self.source_request.id
            or self.rule_id != self.source_request.rule_id
            or self.previous_state != self.source_request.state
            or self.burn != expected_burn
            or self.proof != expected_proof
            or self.state != expected_state
            or self.effect_request != expected_effect
            or self.applied_rule_ids != expected_rules
        ):
            raise ValueError("Fate burn result has stale provenance")


@dataclass(frozen=True, slots=True)
class FateGloriousSpendRequest:
    id: str
    state: FateSessionState
    test: TestRequest
    initial_roll: InitialTestRoll | None = None
    rule_id: str = FATE_GLORIOUS_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Fate Glorious request id")
        if not isinstance(self.state, FateSessionState):
            raise TypeError("state must be a FateSessionState")
        if not isinstance(self.test, TestRequest):
            raise TypeError("test must be a TestRequest")
        if self.initial_roll is not None:
            if not isinstance(self.initial_roll, InitialTestRoll):
                raise TypeError("initial_roll must be an InitialTestRoll")
            if self.initial_roll.request != self.test:
                raise ValueError("initial roll belongs to another Test request")
        _validate_non_empty_string(self.rule_id, "Fate Glorious rule_id")
        if not self.state.can_spend:
            raise ValueError("no Fate spends remain in this session")
        if self.id in {item.id for item in self.state.spends}:
            raise ValueError("Fate spend request was already consumed")
        if any(
            item.kind is FateSpendKind.GLORIOUS_TEST
            and item.subject_id == self.test.id
            for item in self.state.spends
        ):
            raise ValueError("Fate was already spent on this Test")
        if any(
            item.quality is TestQuality.GLORIOUS
            for item in self.test.quality_modifiers
        ):
            raise ValueError("Fate cannot be spent on an already Glorious Test")


@dataclass(frozen=True, slots=True)
class FateGloriousSpendResult:
    request_id: str
    rule_id: str
    source_request: FateGloriousSpendRequest
    previous_state: FateSessionState
    state: FateSessionState
    spend: FateSpendRecord
    proof: FateGloriousProof
    test: TestRequest
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Fate Glorious result request_id",
        )
        _validate_non_empty_string(self.rule_id, "Fate Glorious result rule_id")
        if not isinstance(self.source_request, FateGloriousSpendRequest):
            raise TypeError("source_request must be a Fate Glorious request")
        if not isinstance(self.previous_state, FateSessionState):
            raise TypeError("previous_state must be a FateSessionState")
        if not isinstance(self.state, FateSessionState):
            raise TypeError("state must be a FateSessionState")
        if not isinstance(self.spend, FateSpendRecord):
            raise TypeError("spend must be a FateSpendRecord")
        if not isinstance(self.proof, FateGloriousProof):
            raise TypeError("proof must be a FateGloriousProof")
        if not isinstance(self.test, TestRequest):
            raise TypeError("test must be a TestRequest")

        expected_spend, expected_proof, expected_state, expected_test = (
            _expected_fate_glorious_spend(self.source_request)
        )
        if (
            self.request_id != self.source_request.id
            or self.rule_id != self.source_request.rule_id
            or self.previous_state != self.source_request.state
            or self.spend != expected_spend
            or self.proof != expected_proof
            or self.state != expected_state
            or self.test != expected_test
        ):
            raise ValueError("Fate Glorious result has stale provenance")

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        expected_rule_ids = _fate_spend_rule_ids(
            self.source_request.state,
            self.rule_id,
        )
        if rule_ids != expected_rule_ids:
            raise ValueError("Fate Glorious rule trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


@dataclass(frozen=True, slots=True)
class FateSecondActionProof:
    id: str
    session_id: str
    actor_id: str
    slot_request_id: str
    round_number: int
    slot_index: int
    declaration: CombatActionDeclaration
    source_spend_id: str
    rule_id: str = FATE_SECOND_ACTION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Fate second action proof id")
        _validate_non_empty_string(
            self.session_id,
            "Fate second action proof session_id",
        )
        _validate_non_empty_string(
            self.actor_id,
            "Fate second action proof actor_id",
        )
        _validate_non_empty_string(
            self.slot_request_id,
            "Fate second action proof slot_request_id",
        )
        _validate_positive_int(
            self.round_number,
            "Fate second action proof round_number",
        )
        _validate_positive_int(
            self.slot_index,
            "Fate second action proof slot_index",
        )
        if self.slot_index != 2:
            raise ValueError("Fate second action proof requires slot 2")
        if not isinstance(self.declaration, CombatActionDeclaration):
            raise TypeError("declaration must be a CombatActionDeclaration")
        _validate_non_empty_string(
            self.source_spend_id,
            "Fate second action proof source_spend_id",
        )
        _validate_non_empty_string(self.rule_id, "Fate second action rule_id")
        if self.rule_id != FATE_SECOND_ACTION_RULE_ID:
            raise ValueError("Fate second action proof requires its canonical rule")


@dataclass(frozen=True, slots=True)
class FateSecondActionSpendRequest:
    id: str
    state: FateSessionState
    slot_request: CombatActionSlotRequest
    rule_id: str = FATE_SECOND_ACTION_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Fate second action request id")
        if not isinstance(self.state, FateSessionState):
            raise TypeError("state must be a FateSessionState")
        if not isinstance(self.slot_request, CombatActionSlotRequest):
            raise TypeError("slot_request must be a CombatActionSlotRequest")
        _validate_non_empty_string(self.rule_id, "Fate second action rule_id")
        if not self.state.can_spend:
            raise ValueError("no Fate spends remain in this session")
        if self.state.actor_id != self.slot_request.actor_id:
            raise ValueError("Fate state belongs to another action actor")
        if self.slot_request.grant is not ActionSlotGrant.FATE:
            raise ValueError("second action slot request must use a Fate grant")
        if self.id in {item.id for item in self.state.spends}:
            raise ValueError("Fate spend request was already consumed")
        if any(
            item.kind is FateSpendKind.SECOND_ACTION
            and item.subject_id == self.slot_request.id
            for item in self.state.spends
        ):
            raise ValueError("Fate was already spent on this second action")


@dataclass(frozen=True, slots=True)
class FateSecondActionSpendResult:
    request_id: str
    rule_id: str
    source_request: FateSecondActionSpendRequest
    previous_state: FateSessionState
    state: FateSessionState
    spend: FateSpendRecord
    proof: FateSecondActionProof
    slot_result: CombatActionSlotResult
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Fate second action result request_id",
        )
        _validate_non_empty_string(self.rule_id, "Fate second action rule_id")
        if not isinstance(self.source_request, FateSecondActionSpendRequest):
            raise TypeError("source_request must be a Fate second action request")
        if not isinstance(self.previous_state, FateSessionState):
            raise TypeError("previous_state must be a FateSessionState")
        if not isinstance(self.state, FateSessionState):
            raise TypeError("state must be a FateSessionState")
        if not isinstance(self.spend, FateSpendRecord):
            raise TypeError("spend must be a FateSpendRecord")
        if not isinstance(self.proof, FateSecondActionProof):
            raise TypeError("proof must be a FateSecondActionProof")
        if not isinstance(self.slot_result, CombatActionSlotResult):
            raise TypeError("slot_result must be a CombatActionSlotResult")

        expected_spend, expected_proof, expected_state = (
            _expected_fate_second_action_spend(self.source_request)
        )
        slot_request = self.source_request.slot_request
        slot = self.slot_result.slot
        source_turn = slot_request.state.active_turn
        if source_turn is None:
            raise ValueError("Fate second action result has no source turn")
        expected_turn = replace(
            source_turn,
            action_slots=(*source_turn.action_slots, slot),
        )
        expected_round_state = replace(
            slot_request.state,
            active_turn=expected_turn,
        )
        if (
            self.request_id != self.source_request.id
            or self.rule_id != self.source_request.rule_id
            or self.previous_state != self.source_request.state
            or self.spend != expected_spend
            or self.proof != expected_proof
            or self.state != expected_state
            or self.slot_result.request_id != slot_request.id
            or slot.index != 2
            or slot.declaration != slot_request.declaration
            or slot.grant is not ActionSlotGrant.FATE
            or slot.execution is not None
            or self.slot_result.state != expected_round_state
            or self.slot_result.applied_rule_ids
            != (ACTION_BUDGET_RULE_ID, self.rule_id)
        ):
            raise ValueError("Fate second action result has stale provenance")

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        expected_rule_ids = _fate_spend_rule_ids(
            self.source_request.state,
            *self.slot_result.applied_rule_ids,
        )
        if rule_ids != expected_rule_ids or self.rule_id not in rule_ids:
            raise ValueError("Fate second action rule trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


@dataclass(frozen=True, slots=True)
class FateTacticalRetreatProof:
    id: str
    session_id: str
    actor_id: str
    retreat_id: str
    battle_id: str
    player_character_ids: tuple[str, ...]
    source_spend_id: str
    rule_id: str = FATE_TACTICAL_RETREAT_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Fate Retreat proof id")
        _validate_non_empty_string(
            self.session_id,
            "Fate Retreat proof session_id",
        )
        _validate_non_empty_string(self.actor_id, "Fate Retreat proof actor_id")
        _validate_non_empty_string(self.retreat_id, "Fate Retreat proof retreat_id")
        _validate_non_empty_string(self.battle_id, "Fate Retreat proof battle_id")
        player_ids = tuple(self.player_character_ids)
        if not player_ids:
            raise ValueError("Fate Retreat proof requires player characters")
        for player_id in player_ids:
            _validate_non_empty_string(player_id, "Fate Retreat player ID")
        if len(set(player_ids)) != len(player_ids):
            raise ValueError("Fate Retreat player character IDs must be unique")
        if self.actor_id not in player_ids:
            raise ValueError("Fate Retreat rearguard must belong to the group")
        _validate_non_empty_string(
            self.source_spend_id,
            "Fate Retreat proof source_spend_id",
        )
        _validate_non_empty_string(self.rule_id, "Fate Retreat rule_id")
        if self.rule_id != FATE_TACTICAL_RETREAT_RULE_ID:
            raise ValueError("Fate Retreat proof requires its canonical rule")
        object.__setattr__(self, "player_character_ids", player_ids)


@dataclass(frozen=True, slots=True)
class FateTacticalRetreatSpendRequest:
    id: str
    state: FateSessionState
    retreat: GroupRetreatDeclaration
    rule_id: str = FATE_TACTICAL_RETREAT_RULE_ID

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Fate Retreat request id")
        if not isinstance(self.state, FateSessionState):
            raise TypeError("state must be a FateSessionState")
        if not isinstance(self.retreat, GroupRetreatDeclaration):
            raise TypeError("retreat must be a GroupRetreatDeclaration")
        _validate_non_empty_string(self.rule_id, "Fate Retreat rule_id")
        if not self.state.can_spend:
            raise ValueError("no Fate spends remain in this session")
        if self.state.actor_id not in self.retreat.player_character_ids:
            raise ValueError("Fate rearguard does not belong to the retreating group")
        if self.id in {item.id for item in self.state.spends}:
            raise ValueError("Fate spend request was already consumed")
        if any(
            item.kind is FateSpendKind.TACTICAL_RETREAT
            and item.subject_id == self.retreat.id
            for item in self.state.spends
        ):
            raise ValueError("Fate was already spent on this Retreat")


@dataclass(frozen=True, slots=True)
class FateTacticalRetreatSpendResult:
    request_id: str
    rule_id: str
    source_request: FateTacticalRetreatSpendRequest
    previous_state: FateSessionState
    state: FateSessionState
    spend: FateSpendRecord
    proof: FateTacticalRetreatProof
    retreat_result: RetreatRearGuardResult
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.request_id,
            "Fate Retreat result request_id",
        )
        _validate_non_empty_string(self.rule_id, "Fate Retreat result rule_id")
        if not isinstance(self.source_request, FateTacticalRetreatSpendRequest):
            raise TypeError("source_request must be a Fate Retreat request")
        if not isinstance(self.previous_state, FateSessionState):
            raise TypeError("previous_state must be a FateSessionState")
        if not isinstance(self.state, FateSessionState):
            raise TypeError("state must be a FateSessionState")
        if not isinstance(self.spend, FateSpendRecord):
            raise TypeError("spend must be a FateSpendRecord")
        if not isinstance(self.proof, FateTacticalRetreatProof):
            raise TypeError("proof must be a FateTacticalRetreatProof")
        if not isinstance(self.retreat_result, RetreatRearGuardResult):
            raise TypeError("retreat_result must be a RetreatRearGuardResult")

        expected_spend, expected_proof, expected_state = (
            _expected_fate_tactical_retreat_spend(self.source_request)
        )
        expected_retreat_result = RetreatRearGuardResult(
            request_id=self.source_request.retreat.id,
            source_request=self.source_request.retreat,
            rearguard_actor_id=expected_proof.actor_id,
            fate_proof_id=expected_proof.id,
            source_spend_id=expected_spend.id,
            covered_player_character_ids=(
                self.source_request.retreat.player_character_ids
            ),
            pursuit_decision_required=True,
            applied_rule_ids=(RETREAT_RULE_ID, self.source_request.rule_id),
        )
        if (
            self.request_id != self.source_request.id
            or self.rule_id != self.source_request.rule_id
            or self.previous_state != self.source_request.state
            or self.spend != expected_spend
            or self.proof != expected_proof
            or self.state != expected_state
            or self.retreat_result != expected_retreat_result
        ):
            raise ValueError("Fate Retreat result has stale provenance")

        rule_ids = _validate_rule_ids(self.applied_rule_ids)
        expected_rule_ids = _fate_spend_rule_ids(
            self.source_request.state,
            *self.retreat_result.applied_rule_ids,
        )
        if rule_ids != expected_rule_ids:
            raise ValueError("Fate Retreat rule trace is incomplete")
        object.__setattr__(self, "applied_rule_ids", rule_ids)


def prepare_retreat_alternative_price(
    *,
    request_id: str,
    retreat: GroupRetreatDeclaration,
    fate_states: tuple[FateSessionState, ...],
) -> RetreatAlternativePriceRequest:
    """Expose the GM-owned price only when every group Fate pool is empty."""
    _validate_non_empty_string(request_id, "retreat price request id")
    if not isinstance(retreat, GroupRetreatDeclaration):
        raise TypeError("retreat must be a GroupRetreatDeclaration")
    states = tuple(fate_states)
    if not states or not all(isinstance(item, FateSessionState) for item in states):
        raise TypeError("fate_states must contain FateSessionState values")
    actor_ids = tuple(item.actor_id for item in states)
    if len(set(actor_ids)) != len(actor_ids):
        raise ValueError("retreat Fate states must have unique actors")
    if set(actor_ids) != set(retreat.player_character_ids):
        raise ValueError("retreat price requires Fate state for the full group")
    if len({item.session_id for item in states}) != 1:
        raise ValueError("retreat Fate states must belong to one session")
    if any(item.can_spend for item in states):
        raise ValueError("alternative Retreat price requires exhausted group Fate")
    return RetreatAlternativePriceRequest(
        id=request_id,
        source_retreat=retreat,
        exhausted_fate_actor_ids=actor_ids,
        rule_id=RETREAT_ALTERNATIVE_PRICE_RULE_ID,
    )


def _validate_fate_burn_request(
    request_id: str,
    state: FateSessionState,
    kind: FateBurnKind,
    subject_id: str,
    decision_owner: DecisionOwner,
    rule_id: str,
    expected_rule_id: str,
) -> None:
    _validate_non_empty_string(request_id, "Fate burn request id")
    if not isinstance(state, FateSessionState):
        raise TypeError("state must be a FateSessionState")
    if state.rating < 1:
        raise ValueError("Fate cannot be burned at zero rating")
    if decision_owner is not DecisionOwner.ACTOR:
        raise ValueError("only the actor may choose to burn their Fate")
    if rule_id != expected_rule_id:
        raise ValueError("Fate burn request requires its canonical kind rule")
    if request_id in {
        *(item.id for item in state.spends),
        *state.resource_event_ids,
    }:
        raise ValueError("Fate burn request ID was already consumed")
    if (kind, subject_id) in {
        (item.kind, item.subject_id)
        for item in state.burns
    }:
        raise ValueError("Fate was already burned for this subject and kind")


def _expected_fate_burn(
    request: FateBurnRequest,
) -> tuple[
    FateBurnRecord,
    FateBurnProof,
    FateSessionState,
    FateBurnEffectRequest,
]:
    reduce_current_allowance = request.state.remaining_spends > 0
    new_rating = request.state.rating - 1
    new_spend_limit = request.state.session_spend_limit - int(
        reduce_current_allowance
    )
    burn = FateBurnRecord(
        id=request.id,
        session_id=request.state.session_id,
        actor_id=request.state.actor_id,
        kind=request.kind,
        subject_id=request.subject_id,
        previous_rating=request.state.rating,
        new_rating=new_rating,
        previous_spend_limit=request.state.session_spend_limit,
        new_spend_limit=new_spend_limit,
        current_session_allowance_reduced=reduce_current_allowance,
    )
    proof = FateBurnProof(
        id=f"{request.id}:proof",
        session_id=request.state.session_id,
        actor_id=request.state.actor_id,
        source_burn_id=burn.id,
        kind=request.kind,
        subject_id=request.subject_id,
        previous_rating=request.state.rating,
        new_rating=new_rating,
        rule_id=request.rule_id,
    )
    state = replace(
        request.state,
        rating=new_rating,
        session_spend_limit=new_spend_limit,
        burns=(*request.state.burns, burn),
        resource_event_ids=(*request.state.resource_event_ids, burn.id),
    )
    if isinstance(request, FateUnmitigatedSuccessBurnRequest):
        effect: FateBurnEffectRequest = FateUnmitigatedSuccessEffectRequest(
            id=f"{request.id}:effect",
            source_proof_id=proof.id,
            session_id=request.state.session_id,
            actor_id=request.state.actor_id,
            test=request.test,
            initial_roll=request.initial_roll,
            gm_scope_agreement_id=request.gm_scope_agreement_id,
        )
    elif isinstance(request, FateNearMissBurnRequest):
        effect = FateNearMissEffectRequest(
            id=f"{request.id}:effect",
            source_proof_id=proof.id,
            session_id=request.state.session_id,
            actor_id=request.state.actor_id,
            wound_negation=request.wound_negation,
        )
    else:
        effect = FateLastStandEffectRequest(
            id=f"{request.id}:effect",
            source_proof_id=proof.id,
            session_id=request.state.session_id,
            actor_id=request.state.actor_id,
            battle_id=request.battle_id,
            feat_id=request.feat_id,
            desperate_battle_approval_id=request.desperate_battle_approval_id,
        )
    return burn, proof, state, effect


def _expected_fate_glorious_spend(
    request: FateGloriousSpendRequest,
) -> tuple[
    FateSpendRecord,
    FateGloriousProof,
    FateSessionState,
    TestRequest,
]:
    proof_id = f"{request.id}:proof"
    spend = FateSpendRecord(
        id=request.id,
        session_id=request.state.session_id,
        actor_id=request.state.actor_id,
        kind=FateSpendKind.GLORIOUS_TEST,
        subject_id=request.test.id,
        rule_id=request.rule_id,
        funding=_fate_spend_funding(request.state),
    )
    proof = FateGloriousProof(
        id=proof_id,
        session_id=request.state.session_id,
        actor_id=request.state.actor_id,
        test_id=request.test.id,
        source_spend_id=spend.id,
        rule_id=request.rule_id,
    )
    state = replace(
        request.state,
        spends=(*request.state.spends, spend),
    )
    test = replace(
        request.test,
        quality_modifiers=(
            *request.test.quality_modifiers,
            QualityModifier(
                rule_id=request.rule_id,
                quality=TestQuality.GLORIOUS,
                source=QualityModifierSource.FATE,
                source_id=proof.id,
            ),
        ),
    )
    return spend, proof, state, test


def _expected_fate_second_action_spend(
    request: FateSecondActionSpendRequest,
) -> tuple[FateSpendRecord, FateSecondActionProof, FateSessionState]:
    slot_request = request.slot_request
    spend = FateSpendRecord(
        id=request.id,
        session_id=request.state.session_id,
        actor_id=request.state.actor_id,
        kind=FateSpendKind.SECOND_ACTION,
        subject_id=slot_request.id,
        rule_id=request.rule_id,
        funding=_fate_spend_funding(request.state),
    )
    proof = FateSecondActionProof(
        id=f"{request.id}:proof",
        session_id=request.state.session_id,
        actor_id=request.state.actor_id,
        slot_request_id=slot_request.id,
        round_number=slot_request.state.round_number,
        slot_index=2,
        declaration=slot_request.declaration,
        source_spend_id=spend.id,
        rule_id=request.rule_id,
    )
    state = replace(request.state, spends=(*request.state.spends, spend))
    return spend, proof, state


def _expected_fate_tactical_retreat_spend(
    request: FateTacticalRetreatSpendRequest,
) -> tuple[FateSpendRecord, FateTacticalRetreatProof, FateSessionState]:
    spend = FateSpendRecord(
        id=request.id,
        session_id=request.state.session_id,
        actor_id=request.state.actor_id,
        kind=FateSpendKind.TACTICAL_RETREAT,
        subject_id=request.retreat.id,
        rule_id=request.rule_id,
        funding=_fate_spend_funding(request.state),
    )
    proof = FateTacticalRetreatProof(
        id=f"{request.id}:proof",
        session_id=request.state.session_id,
        actor_id=request.state.actor_id,
        retreat_id=request.retreat.id,
        battle_id=request.retreat.battle_id,
        player_character_ids=request.retreat.player_character_ids,
        source_spend_id=spend.id,
        rule_id=request.rule_id,
    )
    state = replace(request.state, spends=(*request.state.spends, spend))
    return spend, proof, state


def _expected_fate_refresh(
    request: FateRefreshRequest,
) -> tuple[FateRefreshRecord, FateSessionState]:
    restored_spends = (
        request.state.session_refresh_rating - request.state.remaining_spends
    )
    new_limit = request.state.session_spend_limit + restored_spends
    refresh = FateRefreshRecord(
        id=request.id,
        session_id=request.state.session_id,
        actor_id=request.state.actor_id,
        mid_session_break_id=request.mid_session_break_id,
        gm_approval_id=request.gm_approval_id,
        previous_spend_limit=request.state.session_spend_limit,
        restored_spends=restored_spends,
        new_spend_limit=new_limit,
        rule_id=request.rule_id,
    )
    state = replace(
        request.state,
        session_spend_limit=new_limit,
        refreshes=(*request.state.refreshes, refresh),
        resource_event_ids=(*request.state.resource_event_ids, refresh.id),
    )
    return refresh, state


def _fate_spend_funding(state: FateSessionState) -> FateSpendFunding:
    if state.lucky_free_spend_available:
        return FateSpendFunding.LUCKY_FREE
    return FateSpendFunding.SESSION_POOL


def _fate_spend_rule_ids(
    state: FateSessionState,
    *rule_ids: str,
) -> tuple[str, ...]:
    funding_rules = (
        (FATE_LUCKY_RULE_ID,)
        if state.lucky_free_spend_available
        else ()
    )
    return tuple(
        dict.fromkeys(
            (
                FATE_SESSION_RULE_ID,
                *funding_rules,
                *rule_ids,
            )
        )
    )


def _validate_rule_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    rule_ids = tuple(values)
    if not rule_ids:
        raise ValueError("applied_rule_ids must not be empty")
    for rule_id in rule_ids:
        _validate_non_empty_string(rule_id, "applied Rule ID")
    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError("applied_rule_ids must be unique")
    return rule_ids


def _validate_non_negative_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must not be negative")


def _validate_positive_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if value < 1:
        raise ValueError(f"{name} must be positive")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
