"""Fresh PC party and exact printed book combat profiles, with explicit awareness."""
from dataclasses import replace

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
from towr.domain.pc_npc_catalog import PcBookNpcProfile,create_pc_book_npc


def book_pc_scenario(*,footpads=2,townsfolk=1,brigands=0,officials=0,troopers=0,
                     artisans=0,squires=0,merchants=0,horses=0,wolves=0,boars=0,
                     gors=0,warhounds=0,orcs=0,spiders=0,white_wolves=0,
                     empire_knights=0,wolf_knights=0,big_uns=0,pc_count=2,max_rounds=3):
    source=make_pc_melee_party_scenario(pc_count=pc_count,
        enemy_count=officials+brigands+footpads+townsfolk+troopers+artisans+squires+merchants+horses+wolves+boars+gors+warhounds+orcs+spiders+white_wolves+empire_knights+wolf_knights+big_uns,max_rounds=max_rounds)
    entries=tuple((PcBookNpcProfile.EMPIRE_KNIGHT_LANCE,f'empire_knight{i+1}') for i in range(empire_knights))+tuple(
        (PcBookNpcProfile.KNIGHT_WHITE_WOLF_HAMMER,f'wolf_knight{i+1}') for i in range(wolf_knights))+tuple(
        (PcBookNpcProfile.BIG_UN_CHOPPAS,f'big_un{i+1}') for i in range(big_uns))+tuple(
        (PcBookNpcProfile.GIANT_SPIDER,f'spider{i+1}') for i in range(spiders))+tuple(
        (PcBookNpcProfile.WHITE_WOLF_CLAMPING_JAWS,f'white_wolf{i+1}') for i in range(white_wolves))+tuple(
        (PcBookNpcProfile.GOR_DUAL_AXES,f'gor{i+1}') for i in range(gors))+tuple(
        (PcBookNpcProfile.CHAOS_WARHOUND,f'warhound{i+1}') for i in range(warhounds))+tuple(
        (PcBookNpcProfile.ORC_BOY_CHOPPAS,f'orc{i+1}') for i in range(orcs))+tuple(
        (PcBookNpcProfile.HORSE,f'horse{i+1}') for i in range(horses))+tuple(
        (PcBookNpcProfile.GIANT_WOLF,f'wolf{i+1}') for i in range(wolves))+tuple(
        (PcBookNpcProfile.GIANT_BOAR,f'boar{i+1}') for i in range(boars))+tuple(
        (PcBookNpcProfile.ELF_MERCHANT_JEWELLED_BLADE,f'merchant{i+1}') for i in range(merchants))+tuple(
        (PcBookNpcProfile.ARTISAN,f'artisan{i+1}') for i in range(artisans))+tuple(
        (PcBookNpcProfile.BRETONNIAN_SQUIRE_SWORD,f'squire{i+1}') for i in range(squires))+tuple(
        (PcBookNpcProfile.EMPIRE_STATE_TROOPER_HALBERD,f'trooper{i+1}') for i in range(troopers))+tuple(
        (PcBookNpcProfile.EMPIRE_OFFICIAL_DAGGER,f'official{i+1}') for i in range(officials))+tuple(
        (PcBookNpcProfile.BRIGAND_AXE,f'brigand{i+1}') for i in range(brigands))+tuple(
        (PcBookNpcProfile.FOOTPAD,f'footpad{i+1}') for i in range(footpads))+tuple(
        (PcBookNpcProfile.EMPIRE_TOWNSFOLK,f'townsfolk{i+1}') for i in range(townsfolk))
    enemies=tuple(create_pc_book_npc(profile,actor) for profile,actor in entries)
    targets=tuple(actor for _,actor in entries)
    party=tuple(replace(member,target_priority=targets,
        defeat_decisions=tuple(replace(decision,target_id=target)
            for decision,target in zip(member.defeat_decisions,targets,strict=True))) for member in source.party)
    return replace(source,party=party,enemies=enemies,enemy_activation_order=targets)
