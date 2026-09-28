from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.npc_round_weapon_models import NpcRoundWeaponState
from towr.domain.resolution_models import FollowUpRequest, TargetInjuryPolicy
from towr.domain.turn_models import ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatRoundState

if TYPE_CHECKING:
    from towr.domain.npc_attack_selection_models import NpcAttackSelectionRequest


@dataclass(frozen=True, slots=True)
class NpcRoundRequest:
    id: str
    state: NpcRosterAttackState
    round_state: CombatRoundState
    actor_order: tuple[str, ...]
    pending_follow_ups: tuple[FollowUpRequest, ...]
    weapons: tuple[NpcRoundWeaponState, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("NPC round request requires a non-empty string id")
        if not isinstance(self.state, NpcRosterAttackState) or not isinstance(self.round_state, CombatRoundState):
            raise TypeError("NPC round requires typed roster and round snapshots")
        weapons = tuple(self.weapons)
        if not all(isinstance(item, NpcRoundWeaponState) for item in weapons):
            raise TypeError("round weapons must be typed")
        if len({item.weapon_state.weapon_instance_id for item in weapons}) != len(weapons):
            raise ValueError("round weapon instance IDs must be unique")
        if len({(item.actor_id, item.attack_profile_id) for item in weapons}) != len(weapons):
            raise ValueError("round weapon actor/profile bindings must be unique")
        for item in weapons:
            actor = self.state.roster.participant(item.actor_id)
            if item.attack_profile_id not in {p.id for p in actor.definition.attacks}:
                raise ValueError("round weapon profile is absent from its actor")
        object.__setattr__(self, "weapons", weapons)
        order = tuple(self.actor_order)
        if not all(isinstance(actor, str) and actor.strip() for actor in order):
            raise ValueError("actor order requires non-empty string IDs")
        if len(set(order)) != len(order) or set(order) != {p.entity_id for p in self.round_state.participants}:
            raise ValueError("actor order must contain every round participant exactly once")
        for member in self.round_state.participants:
            participant = self.state.roster.participant(member.entity_id)
            if participant.turn_participant != member:
                raise ValueError("round participant side differs from roster")
            if participant.definition.injury_policy is not TargetInjuryPolicy.MINION:
                raise ValueError("NPC round currently supports Minion participants only")
            if (member.entity_id in self.round_state.excluded_turn_entity_ids
                    and not participant.state.injury.defeated):
                raise ValueError("excluded NPC round participant must be defeated")
        pending = tuple(self.pending_follow_ups)
        if not all(isinstance(item, FollowUpRequest) for item in pending):
            raise TypeError("pending follow-ups must be typed")
        turn = self.round_state.active_turn
        if turn is not None:
            if len(turn.action_slots) > 1 or any(
                slot.declaration != CombatActionDeclaration(CombatActionKind.ATTACK)
                or slot.grant is not ActionSlotGrant.STANDARD for slot in turn.action_slots
            ):
                raise ValueError("NPC round accepts only one standard Attack slot")
            if turn.action_slots and turn.action_slots[0].executed:
                receipt = turn.action_slots[0].execution
                if (receipt.id not in self.state.consumed_execution_ids
                        or receipt.executor_rule_id != "RULE-COMBAT-004:attack-action-execution"):
                    raise ValueError("executed Attack receipt requires matching consumed roster history")
        object.__setattr__(self, "actor_order", order)
        object.__setattr__(self, "pending_follow_ups", pending)

    def actor_prefix(self, actor_id: str) -> str:
        return f"{self.id}:round:{self.round_state.round_number}:actor:{actor_id}"

    def next_actor(self, round_state: CombatRoundState) -> str | None:
        if round_state.active_turn is not None:
            return round_state.active_turn.actor_id
        return next((actor for actor in self.actor_order
                     if actor not in round_state.completed_turn_entity_ids
                     and actor not in round_state.excluded_turn_entity_ids
                     and round_state.participant_for(actor).side is round_state.next_side), None)

    def selection_context(self, state: NpcRosterAttackState, round_state: CombatRoundState) -> NpcAttackSelectionRequest:
        from towr.domain.npc_attack_selection_models import NpcAttackSelectionRequest

        actor_id = round_state.active_turn.actor_id
        return NpcAttackSelectionRequest(self.actor_prefix(actor_id) + ":selection", state, round_state,
                                        actor_id, 1, (), (),
                                        replace(self, state=state, round_state=round_state) if self.weapons else None)

