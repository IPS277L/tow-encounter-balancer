"""Persistent profile-NPC state for a rider's own physical mount.

The battle owner derives the complete mount profile from its admitted source
and validates detach/remount receipts. This row neither creates a new mount
nor gives it a turn or its rider's Fate, Talents or injury state.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.condition_models import ConditionState
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.npc_roster_models import (
    NpcDefinition, NpcParticipantSnapshot, NpcParticipantState, NpcProtectionProfile,
)
from towr.domain.pc_companion_usage_models import PcMountCompanionSpatialUsage
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile
from towr.domain.turn_models import CombatSide
from towr.domain.weapon_inventory_models import WeaponInventoryState


def _actor_id(value: str) -> None:
    if type(value) is not str or not value.strip():
        raise TypeError('mount companion requires an exact nonempty actor identifier')


def mount_companion_actor_id(rider_id: str) -> str:
    """Stable identity only; the encounter owner admits the actual mount source."""
    _actor_id(rider_id)
    return rider_id + ':mount'


def _readmit_npc_snapshot(snapshot: NpcParticipantSnapshot) -> None:
    """Reject malformed cached nested values without repairing source facts."""
    if type(snapshot) is not NpcParticipantSnapshot:
        raise TypeError('NPC actor requires its exact participant snapshot')
    definition, state = snapshot.definition, snapshot.state
    if type(definition) is not NpcDefinition or type(state) is not NpcParticipantState:
        raise TypeError('NPC actor requires exact definition and state sources')
    if type(state.side) is not CombatSide:
        raise TypeError('NPC actor side must retain its exact CombatSide')
    if type(definition.injury_policy) is not TargetInjuryPolicy:
        raise TypeError('NPC actor injury policy must retain its exact type')
    if type(definition.resilience) is not ResilienceProfile or type(state.current_resilience) is not ResilienceProfile:
        raise TypeError('NPC actor Resilience must retain its exact profile')
    replace(definition.resilience)
    replace(state.current_resilience)
    if type(definition.attacks) is not tuple or any(type(row) is not NpcAttackProfile for row in definition.attacks):
        raise TypeError('NPC actor requires exact ordered attack profiles')
    if type(definition.protection) is not tuple or any(type(row) is not NpcProtectionProfile for row in definition.protection):
        raise TypeError('NPC actor requires exact ordered Protection profiles')
    for row in (*definition.attacks, *definition.protection):
        if type(row.test_profile) is not InlineProfile:
            raise TypeError('NPC actor requires an exact inline Test profile')
        replace(row.test_profile)
        replace(row)
    for row in definition.attacks:
        if row.damage is not None:
            if type(row.damage) is not DamageProfile:
                raise TypeError('NPC actor requires its exact Damage profile')
            replace(row.damage)
    if type(state.available_attack_ids) is not tuple:
        raise TypeError('NPC actor must retain its ordered available attack IDs')
    if state.weapon_inventory is not None:
        if type(state.weapon_inventory) is not WeaponInventoryState:
            raise TypeError('NPC actor inventory must retain its exact typed source')
        replace(state.weapon_inventory)
    if type(state.injury) not in (CharacterInjuryState, ProfileInjuryState):
        raise TypeError('NPC actor requires its exact typed injury state')
    if type(state.injury.conditions) is not ConditionState:
        raise TypeError('NPC actor Conditions must retain their exact typed state')
    replace(state.injury.conditions)
    replace(state.injury)
    replace(definition)
    replace(state)
    replace(snapshot)


@dataclass(frozen=True, slots=True)
class PcMountCompanionState:
    rider_id: str
    snapshot: NpcParticipantSnapshot
    retained_since_round: int | None = None
    stored_spatial_usage: PcMountCompanionSpatialUsage | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        _actor_id(self.rider_id)
        _readmit_npc_snapshot(self.snapshot)
        definition, state = self.snapshot.definition, self.snapshot.state
        if state.actor_id != mount_companion_actor_id(self.rider_id):
            raise ValueError('mount companion identity must be bound to its actual rider')
        if definition.injury_policy not in (TargetInjuryPolicy.MINION, TargetInjuryPolicy.BRUTE):
            raise ValueError('mount companion requires its actual profile NPC injury policy')
        if type(state.injury) is not ProfileInjuryState:
            raise TypeError('mount companion requires its own exact ProfileInjuryState')
        if self.retained_since_round is not None:
            if type(self.retained_since_round) is not int:
                raise TypeError('retained mount round must be an exact integer or None')
            if self.retained_since_round < 1:
                raise ValueError('retained mount round must be positive')
        if self.stored_spatial_usage is not None:
            if type(self.stored_spatial_usage) is not PcMountCompanionSpatialUsage:
                raise TypeError('stored companion spatial usage requires its exact typed source')
            replace(self.stored_spatial_usage)
            if self.stored_spatial_usage.actor_id != state.actor_id:
                raise ValueError('stored spatial usage belongs to another mount companion')
