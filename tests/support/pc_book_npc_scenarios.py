"""Fresh PC party and exact printed book combat profiles, with explicit awareness."""
from dataclasses import replace

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
from towr.domain.pc_npc_catalog import PcBookNpcProfile,create_pc_book_npc


def book_pc_scenario(*,footpads=2,townsfolk=1,brigands=0,pc_count=2,max_rounds=3):
    source=make_pc_melee_party_scenario(pc_count=pc_count,enemy_count=brigands+footpads+townsfolk,max_rounds=max_rounds)
    entries=tuple((PcBookNpcProfile.BRIGAND_AXE,f'brigand{i+1}') for i in range(brigands))+tuple(
        (PcBookNpcProfile.FOOTPAD,f'footpad{i+1}') for i in range(footpads))+tuple(
        (PcBookNpcProfile.EMPIRE_TOWNSFOLK,f'townsfolk{i+1}') for i in range(townsfolk))
    enemies=tuple(create_pc_book_npc(profile,actor) for profile,actor in entries)
    targets=tuple(actor for _,actor in entries)
    party=tuple(replace(member,target_priority=targets,
        defeat_decisions=tuple(replace(decision,target_id=target)
            for decision,target in zip(member.defeat_decisions,targets,strict=True))) for member in source.party)
    return replace(source,party=party,enemies=enemies,enemy_activation_order=targets)
