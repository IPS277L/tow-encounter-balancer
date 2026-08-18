"""Domain definitions independent from battle execution and adapters."""

from towr.domain.actions import AttackAction, InlineRollSource, StatRollSource
from towr.domain.attack_models import (
    AttackRequest,
    ConditionImpactSpec,
    DamageImpactSpec,
    DamageProfile,
    HazardImpactSpec,
    NearbyTargetsStaggerSpec,
    ProneBeforeGiveGroundSpec,
    ResilienceProfile,
    SecondaryEffectSpec,
)
from towr.domain.combatants import CombatantDefinition, CombatantState, Side
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.encounters import EncounterDefinition
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.resolution_models import (
    HazardExposureRequest,
    HazardResolutionRequest,
    HazardResolutionResult,
    KernelAttackRequest,
    NearbyTargetsStaggerRequest,
    ResolutionResult,
)
from towr.domain.results import BattleOutcome, BattleResult
from towr.domain.stats import DicePool, StatBlock
from towr.domain.test_models import InlineProfile, Skill, TestProfile, TestRequest

__all__ = [
    "AttackAction",
    "AttackRequest",
    "BattleOutcome",
    "BattleResult",
    "CombatantDefinition",
    "CombatantState",
    "CharacterInjuryState",
    "Condition",
    "ConditionImpactSpec",
    "ConditionState",
    "DamageImpactSpec",
    "DamageProfile",
    "DicePool",
    "EncounterDefinition",
    "InlineRollSource",
    "InlineProfile",
    "HazardImpactSpec",
    "HazardExposureRequest",
    "HazardResolutionRequest",
    "HazardResolutionResult",
    "KernelAttackRequest",
    "NearbyTargetsStaggerRequest",
    "NearbyTargetsStaggerSpec",
    "ProfileInjuryState",
    "ProneBeforeGiveGroundSpec",
    "ResilienceProfile",
    "ResolutionResult",
    "SecondaryEffectSpec",
    "Side",
    "Skill",
    "StatBlock",
    "StatRollSource",
    "TestProfile",
    "TestRequest",
]
