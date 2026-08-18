"""Domain definitions independent from battle execution and adapters."""

from towr.domain.actions import AttackAction, InlineRollSource, StatRollSource
from towr.domain.attack_models import AttackRequest, DamageProfile, ResilienceProfile
from towr.domain.combatants import CombatantDefinition, CombatantState, Side
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.encounters import EncounterDefinition
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.resolution_models import KernelAttackRequest, ResolutionResult
from towr.domain.results import BattleOutcome, BattleResult
from towr.domain.stats import DicePool, StatBlock
from towr.domain.test_models import InlineProfile, TestProfile, TestRequest

__all__ = [
    "AttackAction",
    "AttackRequest",
    "BattleOutcome",
    "BattleResult",
    "CombatantDefinition",
    "CombatantState",
    "CharacterInjuryState",
    "Condition",
    "ConditionState",
    "DicePool",
    "DamageProfile",
    "EncounterDefinition",
    "InlineRollSource",
    "InlineProfile",
    "KernelAttackRequest",
    "ProfileInjuryState",
    "ResolutionResult",
    "Side",
    "ResilienceProfile",
    "StatBlock",
    "StatRollSource",
    "TestProfile",
    "TestRequest",
]
