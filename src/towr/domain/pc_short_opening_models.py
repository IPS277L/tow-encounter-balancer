"""The declared single-Zone Short opening and one incidental NPC approach."""
from __future__ import annotations

from towr.domain.injury_models import injury_is_defeated
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition
from towr.domain.pc_melee_models import PcShortRangeOpening
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.turn_models import CombatRoundState

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcMeleeState


def _ids(value: tuple[str, ...]) -> None:
    if type(value) is not tuple or any(type(item) is not str or not item.strip() for item in value):
        raise TypeError('opening actor IDs require their exact ordered tuple')
    if len(set(value)) != len(value):
        raise ValueError('opening actor IDs cannot repeat')


@dataclass(frozen=True, slots=True)
class PcNpcApproachProof:
    actor_id: str
    action_id: str
    source_round: CombatRoundState
    opening: PcShortRangeOpening
    previous_approached_npc_ids: tuple[str, ...]
    party_actor_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if any(type(value) is not str or not value.strip() for value in (self.actor_id,self.action_id)):
            raise TypeError('approach requires exact actor/action IDs')
        if type(self.source_round) is not CombatRoundState or type(self.opening) is not PcShortRangeOpening:
            raise TypeError('approach requires its actual typed round and opening source')
        replace(self.opening)
        turn = self.source_round.active_turn
        if turn is None or turn.actor_id != self.actor_id or turn.action_slots:
            raise ValueError('approach belongs to its own unreserved turn')
        _ids(self.previous_approached_npc_ids)
        _ids(self.party_actor_ids)
        if (self.actor_id in self.previous_approached_npc_ids or not self.party_actor_ids
                or self.actor_id in self.party_actor_ids):
            raise ValueError('approach requires a new NPC and the actual living party')


@dataclass(frozen=True, slots=True)
class PcRangedCloseUnsupported:
    actor_id: str
    source_id: str
    close_enemy_ids: tuple[str, ...]
    round_number: int
    reason: str = 'ranged_close_enemy'

    def __post_init__(self) -> None:
        if any(type(value) is not str or not value.strip() for value in (self.actor_id,self.source_id)):
            raise TypeError('blocked ranged weapon requires its exact actor/source')
        _ids(self.close_enemy_ids)
        if (not self.close_enemy_ids or type(self.round_number) is not int or self.round_number < 1
                or type(self.reason) is not str or self.reason != 'ranged_close_enemy'):
            raise ValueError('blocked ranged weapon requires its actual Close enemy and own turn')


def pc_enemy_range(state: PcMeleeState, actor: str, target: str) -> RangedWeaponRange:
    if state.source.battlefield is not None:
        from towr.domain.pc_battlefield_models import battlefield_range
        if state.battlefield is None:
            raise ValueError('configured battlefield requires its actual spatial state')
        return battlefield_range(state.battlefield,actor,target)
    from towr.domain.pc_actor_models import pc_actor_side
    from towr.domain.turn_models import CombatSide
    first,second=pc_actor_side(state,actor),pc_actor_side(state,target)
    if first is second:raise ValueError('opening range requires actual opposing actors')
    npc=actor if first is CombatSide.OPPOSITION else target
    return (RangedWeaponRange.CLOSE if state.source.short_range_opening is None
        or npc in state.approached_npc_ids else RangedWeaponRange.SHORT)


def pc_has_close_enemy(state: PcMeleeState, actor: str) -> bool:
    from towr.domain.pc_actor_models import pc_opponent_ids
    return any(pc_enemy_range(state,actor,target) is RangedWeaponRange.CLOSE
        for target in pc_opponent_ids(state,actor))


def expected_pc_npc_approach(state: PcMeleeState) -> PcNpcApproachProof | None:
    if (state.source.short_range_opening is None or state.pending or state.pending_wound is not None
            or not state.live_party or not state.live_enemies):
        return None
    turn = state.round_state.active_turn
    if (turn is None or turn.action_slots or turn.actor_id not in state.source.npc_activation_order
            or turn.actor_id in state.approached_npc_ids):
        return None
    actor = turn.actor_id
    enemy = state.enemy(actor)
    if injury_is_defeated(enemy.state.injury) or enemy.state.injury.conditions.has(Condition.DEFENCELESS):
        return None
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    from towr.domain.pc_actor_models import pc_actor_side
    from towr.domain.turn_models import CombatSide
    if pc_actor_side(state,actor) is not CombatSide.OPPOSITION:return None
    from towr.domain.pc_actor_models import pc_opponent_ids
    return PcNpcApproachProof(actor,pc_melee_action_id(state,actor)+':approach',state.round_state,
        state.source.short_range_opening,state.approached_npc_ids,
        pc_opponent_ids(state,actor))


def validate_pc_approaches(state: PcMeleeState) -> None:
    _ids(state.approached_npc_ids)
    proofs = tuple(proof for proof in state.history if type(proof) is PcNpcApproachProof)
    if (state.approached_npc_ids != tuple(proof.actor_id for proof in proofs)
            or not set(state.approached_npc_ids) <= set(state.source.npc_activation_order)
            or proofs and state.source.short_range_opening is None):
        raise ValueError('proximity must preserve its actual one-time approach history')
    previous: tuple[str, ...] = ()
    for proof in proofs:
        replace(proof)
        if (proof.previous_approached_npc_ids != previous or proof.opening != state.source.short_range_opening
                or not set(proof.party_actor_ids) <= set(state.source.player_activation_order)):
            raise ValueError('approach changed its opening source, party or previous proximity')
        previous = (*previous,proof.actor_id)
