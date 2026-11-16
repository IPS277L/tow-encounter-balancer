"""Numeric PC magic encounters; no named-NPC capabilities or forced controller."""
from dataclasses import replace
from tests.support.pc_tactics_fixtures import automatic_source
from towr.domain.attack_models import ResilienceProfile,DamageProfile
from towr.domain.test_models import InlineProfile
from towr.domain.pc_magic_source_models import PcWizardProfile,PcSpellId


def magic_scenario(*, reason=2, willpower=1, level=1, rounds=1, enemies=2, pc_count=1,
                   spells=(PcSpellId.LIGHTNING_BLAST,PcSpellId.FIRE_BREATH), armour=0):
    source = automatic_source(pc_count=pc_count,enemy_count=enemies,rounds=rounds)
    mage = replace(source.party[0],wizard=PcWizardProfile('human',reason,willpower,level,
        ('elementalism',),spells,True),pc=replace(source.party[0].pc,
            weapon_skill=1,melee=1,toughness=10,armour_bonus=armour))
    opponents = []
    for enemy in source.enemies:
        definition = replace(enemy.definition,resilience=ResilienceProfile(100),
            protection=(replace(enemy.definition.protection[0],test_profile=InlineProfile(2,10)),),
            attacks=(replace(enemy.definition.attacks[0],test_profile=InlineProfile(1,1),damage=DamageProfile(1)),))
        opponents.append(replace(enemy,definition=definition,
            state=replace(enemy.state,current_resilience=definition.resilience)))
    return replace(source,party=(mage,*source.party[1:]),enemies=tuple(opponents),
        facts=replace(source.facts,outnumbering_bonus_approved=False,daylight_confirmed=True))
