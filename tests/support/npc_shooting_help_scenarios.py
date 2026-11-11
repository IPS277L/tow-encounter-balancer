"""Fresh canonical helpers and one firearm receiver, with explicit pair order."""
from dataclasses import replace

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy
from towr.domain.pc_npc_net_policy_models import PcNpcNetMode, PcNpcNetPolicy
from towr.domain.pc_npc_pistol_source_models import PcNpcPistolPolicy, PcNpcPistolReloadHandPolicy


def make_npc_shooting_help_scenario(*,
        helpers=(PcBookNpcProfile.FREE_COMPANY_MILITIA_BLADES,),
        shooter=PcBookNpcProfile.IMPERIAL_OGRE_PISTOL, max_rounds=3):
    source = make_pc_melee_scenario(enemy_count=len(helpers)+1, max_rounds=max_rounds)
    profiles = (*helpers, shooter)
    enemies = tuple(create_pc_book_npc(profile, actor)
        for profile, actor in zip(profiles, source.enemy_activation_order, strict=True))
    receiver = source.enemy_activation_order[-1]
    return replace(source, enemies=enemies,
        facts=replace(source.facts, outnumbering_bonus_approved=False),
        npc_help_policies=tuple(PcNpcHelpPolicy(actor, receiver)
            for actor in source.enemy_activation_order[:-1]),
        npc_pistol_policies=(PcNpcPistolPolicy(receiver, True, True, True, True,
            PcNpcPistolReloadHandPolicy.TWO_AVAILABLE_HANDS),),
        npc_net_policies=tuple(PcNpcNetPolicy(actor, 1, PcNpcNetMode.THROW_ONCE_THEN_SPEAR)
            for profile, actor in zip(profiles, source.enemy_activation_order, strict=True)
            if profile is PcBookNpcProfile.NIGHT_GOBLIN_NET_SPEAR))
