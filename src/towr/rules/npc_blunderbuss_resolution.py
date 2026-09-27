from __future__ import annotations

from towr.domain.npc_blunderbuss_models import (
    NpcBlunderbussAttackExecutionRequest, NpcBlunderbussAttackExecutionResult, validate_npc_blunderbuss_attack,
)
from towr.domain.npc_round_models import NpcRoundRequest
from towr.domain.reload_models import ReloadableWeaponState
from towr.rules.dice import RandomSource
from towr.rules.kernel import ResolutionDecisionProvider
from towr.rules.prepared_ranged_weapon_attack_resolution import execute_prepared_ranged_weapon_attack


def execute_npc_blunderbuss_attack(
    request: NpcBlunderbussAttackExecutionRequest, rng: RandomSource,
    *, decisions: ResolutionDecisionProvider | None = None,
) -> NpcBlunderbussAttackExecutionResult:
    if not isinstance(request, NpcBlunderbussAttackExecutionRequest):
        raise TypeError("NPC Blunderbuss execution requires its typed request")
    validate_npc_blunderbuss_attack(request)
    executed = execute_prepared_ranged_weapon_attack(request.prepared_request, rng, decisions=decisions)
    return NpcBlunderbussAttackExecutionResult(request, executed)


def apply_npc_blunderbuss_attack(
    current: NpcRoundRequest, weapon_state: ReloadableWeaponState, result: NpcBlunderbussAttackExecutionResult,
) -> tuple[NpcRoundRequest, ReloadableWeaponState]:
    if (not isinstance(current, NpcRoundRequest) or not isinstance(weapon_state, ReloadableWeaponState)
            or not isinstance(result, NpcBlunderbussAttackExecutionResult)):
        raise TypeError("NPC Blunderbuss application requires typed current round, weapon and result")
    if result.primary_attack.attack.request_id in current.state.consumed_execution_ids:
        raise ValueError("NPC Blunderbuss Attack was already consumed")
    if current != result.source_request.current or weapon_state != result.source_request.weapon_state:
        raise ValueError("NPC Blunderbuss source differs from current round/roster/history/weapon")
    return result.continuation, result.weapon_state
