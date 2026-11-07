"""Explicit finite Weighted Net stock and caller-owned weapon selection."""
from dataclasses import dataclass, replace
from enum import Enum


NET_DEFINITION_ID = 'pc-book-npc:night_goblin_net_spear'
NET_RULE_ID = 'RULE-EQUIPMENT-005:weighted-net-burdened'


class PcNpcNetMode(str, Enum):
    THROW_ONCE_THEN_SPEAR = 'throw_once_then_spear'
    SPEAR_ONLY = 'spear_only'


@dataclass(frozen=True, slots=True)
class PcNpcNetPolicy:
    actor_id: str
    initial_count: int
    mode: PcNpcNetMode

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('Net policy actor must be an exact nonempty string')
        if type(self.initial_count) is not int:
            raise TypeError('Net initial count must be an exact integer')
        if self.initial_count != 1:
            raise ValueError('the fixed Net loadout carries exactly one Net')
        if type(self.mode) is not PcNpcNetMode:
            raise TypeError('Net mode must retain its exact PcNpcNetMode enum')


def validate_pc_npc_net_policies(policies, enemies) -> None:
    if type(policies) is not tuple:
        raise TypeError('Net policies require an exact ordered tuple')
    for policy in policies:
        if type(policy) is not PcNpcNetPolicy:
            raise TypeError('Net policy must retain its exact type')
        replace(policy)
    expected = tuple(enemy.state.actor_id for enemy in enemies
        if enemy.definition.id == NET_DEFINITION_ID)
    if tuple(policy.actor_id for policy in policies) != expected:
        raise ValueError('each canonical Net loadout requires exactly one policy in source order')
