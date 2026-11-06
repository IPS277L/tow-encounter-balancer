"""Caller-owned, named PC focus for the canonical Miner's encounter grudge."""
from dataclasses import dataclass,replace

from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition


MINER_DEFINITION_ID='pc-book-npc:dwarf_miner_pickaxe'
GRUDGES_TO_SETTLE_RULE_ID='RULE-PROFILE-PEOPLES-004:grudges-to-settle'


@dataclass(frozen=True,slots=True)
class PcNpcGrudgePolicy:
    actor_id: str
    focus_actor_id: str

    def __post_init__(self):
        for value in (self.actor_id,self.focus_actor_id):
            if type(value) is not str or not value.strip():
                raise TypeError('NPC grudge actor and focus IDs must be exact nonempty strings')
        if self.actor_id==self.focus_actor_id:
            raise ValueError('NPC cannot select itself as its PC grudge focus')


def validate_pc_npc_grudge_policies(source) -> None:
    if type(source.npc_grudge_policies) is not tuple:
        raise TypeError('NPC grudge policies require a canonical tuple')
    actors=[]
    for policy in source.npc_grudge_policies:
        if type(policy) is not PcNpcGrudgePolicy:
            raise TypeError('NPC grudge policy must be its exact typed pair')
        replace(policy)
        if policy.actor_id not in source.enemy_activation_order:
            raise ValueError('NPC grudge actor must belong to the source opposition')
        definition=source.enemy(policy.actor_id).definition
        validate_pc_book_npc_definition(definition)
        if definition.id!=MINER_DEFINITION_ID:
            raise ValueError('NPC grudge requires the canonical Dwarf Miner Pickaxe')
        if policy.focus_actor_id not in source.pc_activation_order:
            raise ValueError('NPC grudge focus must belong to the source PC party')
        actors.append(policy.actor_id)
    if len(set(actors))!=len(actors):
        raise ValueError('each Miner requires at most one named grudge focus')
