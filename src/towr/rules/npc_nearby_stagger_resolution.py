from __future__ import annotations

from towr.domain.npc_nearby_stagger_models import NpcNearbyStaggerExecutionRequest, NpcNearbyStaggerExecutionResult
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.rules.dice import RandomSource
from towr.rules.secondary_target_resolution import resolve_nearby_targets_stagger
from towr.rules.stagger_impact_resolution import StaggerImpactDecisionProvider


def execute_npc_nearby_stagger(
    request: NpcNearbyStaggerExecutionRequest, rng: RandomSource,
    *, decisions: StaggerImpactDecisionProvider | None = None,
) -> NpcNearbyStaggerExecutionResult:
    """Resolve the supplied secondary Minions once, retaining target-scoped pending work."""
    if not isinstance(request, NpcNearbyStaggerExecutionRequest):
        raise TypeError("NPC nearby Stagger execution requires a typed request")
    resolution = resolve_nearby_targets_stagger(request.resolution, rng, decisions=decisions)
    return NpcNearbyStaggerExecutionResult(request, resolution)


def apply_npc_nearby_stagger(
    current: NpcRosterAttackState, result: NpcNearbyStaggerExecutionResult,
) -> NpcRosterAttackState:
    """Transfer completed injuries once to the exact roster/history that was resolved."""
    if not isinstance(current, NpcRosterAttackState) or not isinstance(result, NpcNearbyStaggerExecutionResult):
        raise TypeError("NPC nearby Stagger application requires typed current state and result")
    if result.source_request.resolution.source in current.consumed_nearby_stagger_sources:
        raise ValueError("NPC nearby Stagger source was already consumed")
    if current != result.source_request.state:
        raise ValueError("NPC nearby Stagger source differs from current roster/history")
    return result.state
