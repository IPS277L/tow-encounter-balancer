from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from towr.domain.attack_models import (
    AttackRequest,
    AttackResult,
    ConditionAfterGiveGroundSpec,
    HazardImpactSpec,
)
from towr.domain.condition_models import Condition, StaggerResult
from towr.domain.injury_models import (
    AdditionalProfileWound,
    CharacterInjuryState,
    CharacterWoundResult,
    MonstrosityImpactResult,
    ProfileInjuryState,
    ProfileStateChangeRequest,
    ProfileWoundResult,
    WoundChoiceRequest,
    WoundConsequenceRequest,
    WoundDiceModifier,
    WoundEffectResult,
    WoundEnduranceTestRequest,
    WoundNegationOption,
)
from towr.domain.test_models import Skill, TestResult


class TargetInjuryPolicy(str, Enum):
    PLAYER = "player"
    CHAMPION = "champion"
    MINION = "minion"
    BRUTE = "brute"
    MONSTROSITY = "monstrosity"


@dataclass(frozen=True, slots=True)
class AttackerStaggerRequest:
    attack_id: str
    rule_id: str = "RULE-COMBAT-007:close-miss"


@dataclass(frozen=True, slots=True)
class GiveGroundRequest:
    resolution_id: str
    rule_id: str = "RULE-HEALTH-003:give-ground"


@dataclass(frozen=True, slots=True)
class ConditionAfterGiveGroundRequest:
    resolution_id: str
    condition: Condition
    rule_id: str

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.resolution_id, "resolution_id")
        if not isinstance(self.condition, Condition):
            raise TypeError("condition must be a Condition")
        if self.condition is Condition.STAGGERED:
            raise ValueError(
                "Staggered after Give Ground requires the Stagger impact policy"
            )
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class NearbyTargetsStaggerRequest:
    """Stagger every other creature that was near the primary target on hit."""

    resolution_id: str
    rule_id: str

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.resolution_id, "resolution_id")
        _validate_non_empty_string(self.rule_id, "rule_id")


@dataclass(frozen=True, slots=True)
class MonstrosityReactionRequest:
    resolution_id: str
    reaction_rule_id: str


@dataclass(frozen=True, slots=True)
class ConsumeWoundNegationRequest:
    resolution_id: str
    rule_id: str


@dataclass(frozen=True, slots=True)
class HazardExposureRequest:
    resolution_id: str
    test_id: str
    rating: int
    avoidance_skill: Skill
    rule_id: str
    inflicts_wound: bool
    failure_conditions: tuple[Condition, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.resolution_id, "resolution_id")
        _validate_non_empty_string(self.test_id, "test_id")
        if not isinstance(self.rating, int) or isinstance(self.rating, bool):
            raise TypeError("rating must be an integer")
        if self.rating < 1:
            raise ValueError("rating must be positive")
        if not isinstance(self.avoidance_skill, Skill):
            raise TypeError("avoidance_skill must be a Skill")
        _validate_non_empty_string(self.rule_id, "rule_id")
        _validate_bool(self.inflicts_wound, "inflicts_wound")
        conditions = tuple(self.failure_conditions)
        if not all(isinstance(item, Condition) for item in conditions):
            raise TypeError("failure_conditions must contain Condition values")
        if len(set(conditions)) != len(conditions):
            raise ValueError("failure_conditions must be unique")
        if not self.inflicts_wound and not conditions:
            raise ValueError(
                "a Hazard must inflict a Wound or at least one Condition"
            )
        object.__setattr__(self, "failure_conditions", conditions)

    @classmethod
    def from_spec(
        cls,
        resolution_id: str,
        spec: HazardImpactSpec,
    ) -> HazardExposureRequest:
        return cls(
            resolution_id=resolution_id,
            test_id=f"{resolution_id}:hazard",
            rating=spec.rating,
            avoidance_skill=spec.avoidance_skill,
            rule_id=spec.rule_id,
            inflicts_wound=spec.inflicts_wound,
            failure_conditions=spec.failure_conditions,
        )


@dataclass(frozen=True, slots=True)
class ConditionImpactResult:
    condition: Condition
    was_already_present: bool
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HazardImpactResult:
    exposure: HazardExposureRequest


ReplacementImpactResult = ConditionImpactResult | HazardImpactResult


FollowUpRequest = (
    AttackerStaggerRequest
    | ConditionAfterGiveGroundRequest
    | ConsumeWoundNegationRequest
    | GiveGroundRequest
    | HazardExposureRequest
    | MonstrosityReactionRequest
    | NearbyTargetsStaggerRequest
    | WoundEnduranceTestRequest
    | WoundConsequenceRequest
    | WoundChoiceRequest
    | ProfileStateChangeRequest
)


TargetInjuryState = CharacterInjuryState | ProfileInjuryState


@dataclass(frozen=True, slots=True)
class StaggerImpactRequest:
    id: str
    target_policy: TargetInjuryPolicy
    target_state: TargetInjuryState
    can_target_leave_zone: bool
    target_has_given_ground_this_round: bool
    wound_dice_modifiers: tuple[WoundDiceModifier, ...] = field(
        default_factory=tuple
    )
    wound_negation_options: tuple[WoundNegationOption, ...] = field(
        default_factory=tuple
    )
    additional_profile_wounds: tuple[AdditionalProfileWound, ...] = field(
        default_factory=tuple
    )
    after_give_ground_effects: tuple[ConditionAfterGiveGroundSpec, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Stagger impact request id")
        if not isinstance(self.target_policy, TargetInjuryPolicy):
            raise TypeError("target_policy must be a TargetInjuryPolicy")
        _validate_bool(self.can_target_leave_zone, "can_target_leave_zone")
        _validate_bool(
            self.target_has_given_ground_this_round,
            "target_has_given_ground_this_round",
        )
        object.__setattr__(
            self,
            "wound_dice_modifiers",
            tuple(self.wound_dice_modifiers),
        )
        object.__setattr__(
            self,
            "wound_negation_options",
            tuple(self.wound_negation_options),
        )
        object.__setattr__(
            self,
            "additional_profile_wounds",
            tuple(self.additional_profile_wounds),
        )
        effects = tuple(self.after_give_ground_effects)
        if not all(
            isinstance(item, ConditionAfterGiveGroundSpec) for item in effects
        ):
            raise TypeError(
                "after_give_ground_effects must contain "
                "ConditionAfterGiveGroundSpec values"
            )
        rule_ids = tuple(item.rule_id for item in effects)
        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError("after-Give-Ground effect rule_ids must be unique")
        object.__setattr__(self, "after_give_ground_effects", effects)
        _validate_target_policy_state(
            self.target_policy,
            self.target_state,
        )
        _validate_injury_options(
            self.target_policy,
            self.wound_dice_modifiers,
            self.wound_negation_options,
            self.additional_profile_wounds,
        )


@dataclass(frozen=True, slots=True)
class StaggerImpactResult:
    request_id: str
    state: TargetInjuryState
    stagger: StaggerResult
    character_wound: CharacterWoundResult | None
    wound_effect: WoundEffectResult | None
    profile_wound: ProfileWoundResult | None
    follow_ups: tuple[FollowUpRequest, ...]
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConditionAfterGiveGroundResult:
    resolution_id: str
    state: TargetInjuryState
    condition: Condition
    was_already_present: bool
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IdentifiedStaggerTarget:
    target_id: str
    impact: StaggerImpactRequest

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.target_id, "target_id")
        if not isinstance(self.impact, StaggerImpactRequest):
            raise TypeError("impact must be a StaggerImpactRequest")


@dataclass(frozen=True, slots=True)
class NearbyTargetsStaggerResolutionRequest:
    id: str
    source: NearbyTargetsStaggerRequest
    primary_target_id: str
    targets: tuple[IdentifiedStaggerTarget, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "nearby Stagger resolution id")
        if not isinstance(self.source, NearbyTargetsStaggerRequest):
            raise TypeError("source must be a NearbyTargetsStaggerRequest")
        _validate_non_empty_string(self.primary_target_id, "primary_target_id")
        targets = tuple(self.targets)
        if not all(isinstance(item, IdentifiedStaggerTarget) for item in targets):
            raise TypeError("targets must contain IdentifiedStaggerTarget values")
        target_ids = tuple(item.target_id for item in targets)
        if self.primary_target_id in target_ids:
            raise ValueError("the primary target cannot be a secondary target")
        if len(set(target_ids)) != len(target_ids):
            raise ValueError("secondary target_ids must be unique")
        impact_ids = tuple(item.impact.id for item in targets)
        if len(set(impact_ids)) != len(impact_ids):
            raise ValueError("secondary Stagger impact ids must be unique")
        object.__setattr__(self, "targets", targets)


@dataclass(frozen=True, slots=True)
class NearbyTargetStaggerResult:
    target_id: str
    impact: StaggerImpactResult


@dataclass(frozen=True, slots=True)
class NearbyTargetsStaggerResolutionResult:
    request_id: str
    source_resolution_id: str
    targets: tuple[NearbyTargetStaggerResult, ...]
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HazardResolutionRequest:
    id: str
    exposure: HazardExposureRequest
    avoidance_test: TestResult
    target_policy: TargetInjuryPolicy
    target_state: TargetInjuryState
    wound_dice_modifiers: tuple[WoundDiceModifier, ...] = field(
        default_factory=tuple
    )
    wound_negation_options: tuple[WoundNegationOption, ...] = field(
        default_factory=tuple
    )
    additional_profile_wounds: tuple[AdditionalProfileWound, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Hazard resolution request id")
        if not isinstance(self.exposure, HazardExposureRequest):
            raise TypeError("exposure must be a HazardExposureRequest")
        if not isinstance(self.avoidance_test, TestResult):
            raise TypeError("avoidance_test must be a TestResult")
        if self.avoidance_test.trace.request_id != self.exposure.test_id:
            raise ValueError("avoidance Test result does not match the exposure")
        if not isinstance(self.target_policy, TargetInjuryPolicy):
            raise TypeError("target_policy must be a TargetInjuryPolicy")
        object.__setattr__(
            self,
            "wound_dice_modifiers",
            tuple(self.wound_dice_modifiers),
        )
        object.__setattr__(
            self,
            "wound_negation_options",
            tuple(self.wound_negation_options),
        )
        object.__setattr__(
            self,
            "additional_profile_wounds",
            tuple(self.additional_profile_wounds),
        )
        self._validate_target()
        self._validate_options()

    def _validate_target(self) -> None:
        character_policy = self.target_policy in {
            TargetInjuryPolicy.PLAYER,
            TargetInjuryPolicy.CHAMPION,
        }
        if character_policy and not isinstance(
            self.target_state,
            CharacterInjuryState,
        ):
            raise TypeError("Player/Champion requires CharacterInjuryState")
        if not character_policy and not isinstance(
            self.target_state,
            ProfileInjuryState,
        ):
            raise TypeError("profile NPC requires ProfileInjuryState")
        if (
            self.target_policy is TargetInjuryPolicy.MINION
            and isinstance(self.target_state, ProfileInjuryState)
            and self.target_state.wound_limit != 1
        ):
            raise ValueError("Minion requires a wound_limit of 1")

    def _validate_options(self) -> None:
        if not all(
            isinstance(item, WoundDiceModifier)
            for item in self.wound_dice_modifiers
        ):
            raise TypeError(
                "wound_dice_modifiers must contain WoundDiceModifier values"
            )
        if not all(
            isinstance(item, WoundNegationOption)
            for item in self.wound_negation_options
        ):
            raise TypeError(
                "wound_negation_options must contain WoundNegationOption values"
            )
        if not all(
            isinstance(item, AdditionalProfileWound)
            for item in self.additional_profile_wounds
        ):
            raise TypeError(
                "additional_profile_wounds must contain AdditionalProfileWound values"
            )
        character_policy = self.target_policy in {
            TargetInjuryPolicy.PLAYER,
            TargetInjuryPolicy.CHAMPION,
        }
        if character_policy and self.additional_profile_wounds:
            raise ValueError(
                "Player/Champion uses Wounds Table dice, not profile wounds"
            )
        if not character_policy and (
            self.wound_dice_modifiers or self.wound_negation_options
        ):
            raise ValueError(
                "profile NPCs use additional_profile_wounds, not table options"
            )


@dataclass(frozen=True, slots=True)
class HazardResolutionResult:
    request_id: str
    state: TargetInjuryState
    avoided: bool
    successes: int
    rating: int
    shortfall: int
    character_wound: CharacterWoundResult | None
    wound_effect: WoundEffectResult | None
    profile_wound: ProfileWoundResult | None
    failure_conditions: tuple[Condition, ...]
    follow_ups: tuple[FollowUpRequest, ...]
    applied_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class KernelAttackRequest:
    id: str
    attack: AttackRequest
    target_policy: TargetInjuryPolicy
    target_state: TargetInjuryState
    can_target_leave_zone: bool
    target_has_given_ground_this_round: bool
    wound_dice_modifiers: tuple[WoundDiceModifier, ...] = field(
        default_factory=tuple
    )
    wound_negation_options: tuple[WoundNegationOption, ...] = field(
        default_factory=tuple
    )
    additional_profile_wounds: tuple[AdditionalProfileWound, ...] = field(
        default_factory=tuple
    )
    monstrosity_reaction_rule_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str):
            raise TypeError("kernel attack request id must be a string")
        if not self.id.strip():
            raise ValueError("kernel attack request id must not be empty")
        if not isinstance(self.attack, AttackRequest):
            raise TypeError("attack must be an AttackRequest")
        if not isinstance(self.target_policy, TargetInjuryPolicy):
            raise TypeError("target_policy must be a TargetInjuryPolicy")
        _validate_bool(self.can_target_leave_zone, "can_target_leave_zone")
        _validate_bool(
            self.target_has_given_ground_this_round,
            "target_has_given_ground_this_round",
        )
        object.__setattr__(
            self,
            "wound_dice_modifiers",
            tuple(self.wound_dice_modifiers),
        )
        object.__setattr__(
            self,
            "wound_negation_options",
            tuple(self.wound_negation_options),
        )
        object.__setattr__(
            self,
            "additional_profile_wounds",
            tuple(self.additional_profile_wounds),
        )
        self._validate_policy_state()
        self._validate_policy_options()

    def _validate_policy_state(self) -> None:
        character_policy = self.target_policy in {
            TargetInjuryPolicy.PLAYER,
            TargetInjuryPolicy.CHAMPION,
        }
        if character_policy and not isinstance(
            self.target_state, CharacterInjuryState
        ):
            raise TypeError("Player/Champion requires CharacterInjuryState")
        if not character_policy and not isinstance(
            self.target_state, ProfileInjuryState
        ):
            raise TypeError("profile NPC requires ProfileInjuryState")
        if (
            self.target_policy is TargetInjuryPolicy.MINION
            and isinstance(self.target_state, ProfileInjuryState)
            and self.target_state.wound_limit != 1
        ):
            raise ValueError("Minion requires a wound_limit of 1")

    def _validate_policy_options(self) -> None:
        if not all(
            isinstance(item, WoundDiceModifier)
            for item in self.wound_dice_modifiers
        ):
            raise TypeError(
                "wound_dice_modifiers must contain WoundDiceModifier values"
            )
        if not all(
            isinstance(item, WoundNegationOption)
            for item in self.wound_negation_options
        ):
            raise TypeError(
                "wound_negation_options must contain WoundNegationOption values"
            )
        if not all(
            isinstance(item, AdditionalProfileWound)
            for item in self.additional_profile_wounds
        ):
            raise TypeError(
                "additional_profile_wounds must contain AdditionalProfileWound values"
            )
        character_policy = self.target_policy in {
            TargetInjuryPolicy.PLAYER,
            TargetInjuryPolicy.CHAMPION,
        }
        if not character_policy and (
            self.wound_dice_modifiers or self.wound_negation_options
        ):
            raise ValueError(
                "profile NPCs use additional_profile_wounds, not table options"
            )
        if character_policy and self.additional_profile_wounds:
            raise ValueError(
                "Player/Champion uses Wounds Table dice, not profile wounds"
            )
        if self.target_policy is TargetInjuryPolicy.MONSTROSITY:
            if (
                not isinstance(self.monstrosity_reaction_rule_id, str)
                or not self.monstrosity_reaction_rule_id.strip()
            ):
                raise ValueError(
                    "Monstrosity requires monstrosity_reaction_rule_id"
                )
        elif self.monstrosity_reaction_rule_id is not None:
            raise ValueError(
                "monstrosity_reaction_rule_id is only valid for Monstrosity"
            )


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    request_id: str
    attack: AttackResult
    replacement_impact: ReplacementImpactResult | None
    target_state: TargetInjuryState
    stagger: StaggerResult | None
    character_wound: CharacterWoundResult | None
    wound_effect: WoundEffectResult | None
    profile_wound: ProfileWoundResult | None
    monstrosity_impact: MonstrosityImpactResult | None
    follow_ups: tuple[FollowUpRequest, ...]
    applied_secondary_rule_ids: tuple[str, ...] = field(default_factory=tuple)


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _validate_target_policy_state(
    policy: TargetInjuryPolicy,
    state: TargetInjuryState,
) -> None:
    character_policy = policy in {
        TargetInjuryPolicy.PLAYER,
        TargetInjuryPolicy.CHAMPION,
    }
    if character_policy and not isinstance(state, CharacterInjuryState):
        raise TypeError("Player/Champion requires CharacterInjuryState")
    if not character_policy and not isinstance(state, ProfileInjuryState):
        raise TypeError("profile NPC requires ProfileInjuryState")
    if (
        policy is TargetInjuryPolicy.MINION
        and isinstance(state, ProfileInjuryState)
        and state.wound_limit != 1
    ):
        raise ValueError("Minion requires a wound_limit of 1")


def _validate_injury_options(
    policy: TargetInjuryPolicy,
    wound_dice_modifiers: tuple[WoundDiceModifier, ...],
    wound_negation_options: tuple[WoundNegationOption, ...],
    additional_profile_wounds: tuple[AdditionalProfileWound, ...],
) -> None:
    if not all(
        isinstance(item, WoundDiceModifier) for item in wound_dice_modifiers
    ):
        raise TypeError(
            "wound_dice_modifiers must contain WoundDiceModifier values"
        )
    if not all(
        isinstance(item, WoundNegationOption)
        for item in wound_negation_options
    ):
        raise TypeError(
            "wound_negation_options must contain WoundNegationOption values"
        )
    if not all(
        isinstance(item, AdditionalProfileWound)
        for item in additional_profile_wounds
    ):
        raise TypeError(
            "additional_profile_wounds must contain AdditionalProfileWound values"
        )
    character_policy = policy in {
        TargetInjuryPolicy.PLAYER,
        TargetInjuryPolicy.CHAMPION,
    }
    if character_policy and additional_profile_wounds:
        raise ValueError(
            "Player/Champion uses Wounds Table dice, not profile wounds"
        )
    if not character_policy and (
        wound_dice_modifiers or wound_negation_options
    ):
        raise ValueError(
            "profile NPCs use additional_profile_wounds, not table options"
        )
