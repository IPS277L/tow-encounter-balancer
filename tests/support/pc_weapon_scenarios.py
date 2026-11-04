"""Fresh 1H mixed party and authored armoured numeric foes, not bestiary stats."""
from dataclasses import replace

from tests.support.pc_melee_fixtures import make_pc_melee_mixed_scenario,make_pc_melee_scenario
from towr.domain.attack_models import DamageProfile,ResilienceProfile
from towr.domain.pc_melee_models import (
    PcAllyRecoverPolicy,PcFatePolicy,PcGloriousPolicy,PcMeleePolicy,PcMeleeWeapon,PcNearMissPolicy,PcTwoHandedGrip,
)
from towr.domain.test_models import InlineProfile,Skill


def varied_weapon_source(*,max_rounds=3):
    source=make_pc_melee_mixed_scenario(pc_count=4,minion_count=1,brute_count=1,
        brute_wound_limit=3,max_rounds=max_rounds)
    weapons=(PcMeleeWeapon.AXE,PcMeleeWeapon.WARHAMMER,PcMeleeWeapon.MORNING_STAR,PcMeleeWeapon.DAGGER)
    party=[]
    for member,weapon in zip(source.party,weapons,strict=True):
        priority=tuple(reversed(member.target_priority))
        party.append(replace(member,pc=replace(member.pc,weapon=weapon),target_priority=priority,
            defeat_decisions=tuple(member.defeat_decision(target) for target in priority),
            fate_policy=PcFatePolicy.CONFIGURED,near_miss_policy=PcNearMissPolicy(14,1),
            glorious_policy=PcGloriousPolicy((Skill.MELEE,Skill.DEFENCE,Skill.ATHLETICS,Skill.ENDURANCE),1,1)))
    party[-1]=replace(party[-1],policy=PcMeleePolicy.RECOVER_ALLY_OR_ATTACK_OR_RECOVER_SELF,
        ally_recover_policy=PcAllyRecoverPolicy(party[2].actor_id))
    enemies=[]
    for enemy in source.enemies:
        brute=enemy.state.actor_id=='brute1'
        resilience=ResilienceProfile(4 if brute else 3,2 if brute else 1)
        definition=replace(enemy.definition,resilience=resilience,
            attacks=(replace(enemy.definition.attacks[0],test_profile=InlineProfile(3 if brute else 2,5),
                damage=DamageProfile(4 if brute else 3)),),
            protection=(replace(enemy.definition.protection[0],test_profile=InlineProfile(3 if brute else 2,5)),))
        enemies.append(replace(enemy,definition=definition,state=replace(enemy.state,current_resilience=resilience)))
    return replace(source,party=tuple(party),enemies=tuple(enemies),
        enemy_target_priority=('pc3','pc1','pc2','pc4'))


def two_handed_weapon_source(*,max_rounds=3):
    source=varied_weapon_source(max_rounds=max_rounds)
    weapons=(PcMeleeWeapon.GREATAXE,PcMeleeWeapon.GREATHAMMER,PcMeleeWeapon.FLAIL,PcMeleeWeapon.GLAIVE)
    return replace(source,party=tuple(replace(member,pc=replace(member.pc,weapon=weapon),
        initial_weapon_hand=PcTwoHandedGrip.BOTH)
        for member,weapon in zip(source.party,weapons,strict=True)))


def two_handed_stop_source():
    """Weak PC versus authored strong Minions; no probabilistic expectations."""
    source=make_pc_melee_scenario(weapon=PcMeleeWeapon.PICKAXE,enemy_count=3,max_rounds=4)
    member=source.party[0]
    member=replace(member,pc=replace(member.pc,weapon_skill=1,strength=1,toughness=2,
        agility=1,melee=1,defence=1,athletics=1,endurance=1))
    enemies=[]
    for enemy in source.enemies:
        resilience=ResilienceProfile(8,2)
        definition=replace(enemy.definition,resilience=resilience,
            attacks=(replace(enemy.definition.attacks[0],test_profile=InlineProfile(4,10),damage=DamageProfile(8)),),
            protection=(replace(enemy.definition.protection[0],test_profile=InlineProfile(4,10)),))
        enemies.append(replace(enemy,definition=definition,state=replace(enemy.state,current_resilience=resilience)))
    return replace(source,party=(member,),enemies=tuple(enemies))
