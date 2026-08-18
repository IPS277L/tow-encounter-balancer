from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from towr.domain.attack_models import (
    AttackRequest,
    AttackResult,
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
from towr.domain.test_models import Skill


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
    rating: int
    avoidance_skill: Skill
    rule_id: str

    @classmethod
    def from_spec(
        cls,
        resolution_id: str,
        spec: HazardImpactSpec,
    ) -> HazardExposureRequest:
        return cls(
            resolution_id=resolution_id,
            rating=spec.rating,
            avoidance_skill=spec.avoidance_skill,
            rule_id=spec.rule_id,
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
    | ConsumeWoundNegationRequest
    | GiveGroundRequest
    | HazardExposureRequest
    | MonstrosityReactionRequest
    | WoundEnduranceTestRequest
    | WoundConsequenceRequest
    | WoundChoiceRequest
    | ProfileStateChangeRequest
)


TargetInjuryState = CharacterInjuryState | ProfileInjuryState


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


def _validate_bool(value: bool, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")
