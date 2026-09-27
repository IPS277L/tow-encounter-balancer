from __future__ import annotations

from dataclasses import replace

from towr.domain.npc_nearby_consequence_models import (
    NpcNearbyConsequenceChain, NpcNearbyConsequenceStep, validate_nearby_consequence_context,
)
from towr.domain.npc_nearby_defeat_models import NpcNearbyDefeatAcknowledgementResult
from towr.domain.npc_nearby_give_ground_models import NpcNearbyGiveGroundConsumptionResult
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.spatial_models import SpatialBattleState
from towr.rules.npc_nearby_defeat_resolution import apply_npc_nearby_defeat
from towr.rules.npc_nearby_give_ground_resolution import apply_npc_nearby_give_ground


def apply_npc_nearby_consequence(
    current: NpcRosterAttackState, spatial_state: SpatialBattleState,
    chain: NpcNearbyConsequenceChain, result: NpcNearbyConsequenceStep,
) -> NpcNearbyConsequenceChain:
    """Validate both caller snapshots, apply one completed consequence and retain its full source."""
    if (not isinstance(current, NpcRosterAttackState) or not isinstance(spatial_state, SpatialBattleState)
            or not isinstance(chain, NpcNearbyConsequenceChain)):
        raise TypeError("nearby consequence application requires typed current snapshots and chain")
    validate_nearby_consequence_context(chain, current, chain.batch, spatial_state)
    updated = replace(chain, steps=(*chain.steps, result))
    if isinstance(result, NpcNearbyDefeatAcknowledgementResult):
        apply_npc_nearby_defeat(current, result)
    elif isinstance(result, NpcNearbyGiveGroundConsumptionResult):
        apply_npc_nearby_give_ground(current, spatial_state, result)
    return updated
