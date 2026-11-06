"""Fresh PC party and exact printed book combat profiles, with explicit awareness."""
from dataclasses import replace

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
from towr.domain.pc_npc_catalog import PcBookNpcProfile,create_pc_book_npc


def book_pc_scenario(*,footpads=2,townsfolk=1,brigands=0,officials=0,troopers=0,
                     artisans=0,squires=0,merchants=0,horses=0,wolves=0,boars=0,
                     gors=0,warhounds=0,orcs=0,spiders=0,white_wolves=0,
                     empire_knights=0,wolf_knights=0,big_uns=0,
                     goblins=0,skulkers=0,night_goblins=0,
                     peasants=0,watch=0,militia=0,cultists=0,elf_militia=0,ungors=0,
                     spear_troopers=0,spear_orcs=0,spear_big_uns=0,
                     razorgors=0,minotaurs=0,minotaur_dual_axes=0,
                     minotaur_greataxes=0,bears=0,demigryphs=0,centigors=0,white_wolf_claws=0,
                     shield_gors=0,shield_knights=0,brewguards=0,miners=0,thieves=0,sharpshooters=0,single_gors=0,unshielded_orcs=0,unshielded_big_uns=0,bestigors=0,flagellant_flails=0,flagellant_hooks=0,pc_count=2,max_rounds=3):
    source=make_pc_melee_party_scenario(pc_count=pc_count,
        enemy_count=officials+brigands+footpads+townsfolk+troopers+artisans+squires+merchants+horses+wolves+boars+gors+warhounds+orcs+spiders+white_wolves+empire_knights+wolf_knights+big_uns+goblins+skulkers+night_goblins+peasants+watch+militia+cultists+elf_militia+ungors+spear_troopers+spear_orcs+spear_big_uns+razorgors+minotaurs+minotaur_dual_axes+minotaur_greataxes+bears+demigryphs+centigors+white_wolf_claws+shield_gors+shield_knights+brewguards+miners+thieves+sharpshooters+single_gors+unshielded_orcs+unshielded_big_uns+bestigors+flagellant_flails+flagellant_hooks,max_rounds=max_rounds)
    entries=tuple((PcBookNpcProfile.FLAGELLANT_FLAILS,f'flagellant_flails{i+1}') for i in range(flagellant_flails))+tuple(
        (PcBookNpcProfile.FLAGELLANT_HOOKS_CHAINS,f'flagellant_hooks{i+1}') for i in range(flagellant_hooks))+tuple(
        (PcBookNpcProfile.BESTIGOR_MASSIVE_AXE,f'bestigor{i+1}') for i in range(bestigors))+tuple(
        (PcBookNpcProfile.ORC_BOY_SPEAR,f'unshielded_orc{i+1}') for i in range(unshielded_orcs))+tuple(
        (PcBookNpcProfile.BIG_UN_SPEAR,f'unshielded_big_un{i+1}') for i in range(unshielded_big_uns))+tuple(
        (PcBookNpcProfile.GOR_AXE,f'single_gor{i+1}') for i in range(single_gors))+tuple(
        (PcBookNpcProfile.HOCHLAND_SHARPSHOOTER_AXE,f'sharpshooter{i+1}') for i in range(sharpshooters))+tuple(
        (PcBookNpcProfile.HALFLING_THIEF_DAGGER,f'thief{i+1}') for i in range(thieves))+tuple(
        (PcBookNpcProfile.DWARF_MINER_PICKAXE,f'miner{i+1}') for i in range(miners))+tuple(
        (PcBookNpcProfile.DWARF_BREWGUARD_WARHAMMER,f'brewguard{i+1}') for i in range(brewguards))+tuple(
        (PcBookNpcProfile.GOR_AXE_SHIELD,f'shield_gor{i+1}') for i in range(shield_gors))+tuple(
        (PcBookNpcProfile.EMPIRE_KNIGHT_LANCE_SHIELD,f'shield_knight{i+1}') for i in range(shield_knights))+tuple(
        (PcBookNpcProfile.DEMIGRYPH,f'demigryph{i+1}') for i in range(demigryphs))+tuple(
        (PcBookNpcProfile.CENTIGOR_SPEAR,f'centigor{i+1}') for i in range(centigors))+tuple(
        (PcBookNpcProfile.WHITE_WOLF_RENDING_CLAWS,f'white_wolf_claws{i+1}') for i in range(white_wolf_claws))+tuple(
        (PcBookNpcProfile.BEAR_SWEEPING_CLAWS,f'bear{i+1}') for i in range(bears))+tuple(
        (PcBookNpcProfile.MINOTAUR_GREATAXE,f'minotaur_greataxe{i+1}') for i in range(minotaur_greataxes))+tuple(
        (PcBookNpcProfile.RAZORGOR,f'razorgor{i+1}') for i in range(razorgors))+tuple(
        (PcBookNpcProfile.MINOTAUR_AXE,f'minotaur{i+1}') for i in range(minotaurs))+tuple(
        (PcBookNpcProfile.MINOTAUR_DUAL_AXES,f'minotaur_dual{i+1}') for i in range(minotaur_dual_axes))+tuple(
        (PcBookNpcProfile.EMPIRE_STATE_TROOPER_SPEAR,f'spear_trooper{i+1}') for i in range(spear_troopers))+tuple(
        (PcBookNpcProfile.ORC_BOY_SPEAR_SHIELD,f'spear_orc{i+1}') for i in range(spear_orcs))+tuple(
        (PcBookNpcProfile.BIG_UN_SPEAR_SHIELD,f'spear_big_un{i+1}') for i in range(spear_big_uns))+tuple(
        (PcBookNpcProfile.SIGMARITE_CULTIST_WARHAMMER,f'cultist{i+1}') for i in range(cultists))+tuple(
        (PcBookNpcProfile.ELF_MILITIA_SPEAR,f'elf_militia{i+1}') for i in range(elf_militia))+tuple(
        (PcBookNpcProfile.UNGOR_SPEAR,f'ungor{i+1}') for i in range(ungors))+tuple(
        (PcBookNpcProfile.EMPIRE_PEASANT,f'peasant{i+1}') for i in range(peasants))+tuple(
        (PcBookNpcProfile.TOWN_WATCH_POLEARM,f'watch{i+1}') for i in range(watch))+tuple(
        (PcBookNpcProfile.FREE_COMPANY_MILITIA_BLADES,f'militia{i+1}') for i in range(militia))+tuple(
        (PcBookNpcProfile.GOBLIN_WARRIOR_SPEAR,f'goblin{i+1}') for i in range(goblins))+tuple(
        (PcBookNpcProfile.NASTY_SKULKER,f'skulker{i+1}') for i in range(skulkers))+tuple(
        (PcBookNpcProfile.NIGHT_GOBLIN_SPEAR,f'night_goblin{i+1}') for i in range(night_goblins))+tuple(
        (PcBookNpcProfile.EMPIRE_KNIGHT_LANCE,f'empire_knight{i+1}') for i in range(empire_knights))+tuple(
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
