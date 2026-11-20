"""PG74: a held Short melee weapon supports an ally's actual Charge defence."""
from dataclasses import dataclass,replace

from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import AcquiredTalent
from towr.domain.test_models import DiceModifier,Skill
from towr.domain.weapon_catalog import WeaponGroup,weapon_profile
from towr.domain.weapon_inventory_models import WeaponItemLocation
from towr.domain.weapon_use_models import WeaponUse,build_weapon_use


DEEP_FORMATION_RULE_ID='RULE-TALENT-002:deep-formation'


@dataclass(frozen=True,slots=True)
class PcDeepFormationSupport:
    holder_id:str
    defender_id:str
    zone_id:str
    acquisition:AcquiredTalent
    weapon_use:WeaponUse

    def __post_init__(self):
        if any(type(value) is not str or not value.strip()
                for value in (self.holder_id,self.defender_id,self.zone_id)):
            raise TypeError('Deep Formation needs exact actor and actual Zone identifiers')
        if self.holder_id==self.defender_id:
            raise ValueError('Deep Formation supports an ally, not its holder')
        if type(self.acquisition) is not AcquiredTalent or self.acquisition.id is not TalentId.DEEP_FORMATION:
            raise TypeError('Deep Formation needs its actual acquisition source')
        replace(self.acquisition)
        if type(self.weapon_use) is not WeaponUse or self.weapon_use.actor_id!=self.holder_id:
            raise TypeError('Deep Formation needs its holder-owned actual weapon use')
        replace(self.weapon_use)
        profile=weapon_profile(self.weapon_use.kind)
        if profile.group is not WeaponGroup.MELEE or profile.maximum_range is not RangedWeaponRange.SHORT:
            raise ValueError('Deep Formation needs a held Short melee weapon')

    @property
    def modifier(self):
        return DiceModifier(DEEP_FORMATION_RULE_ID+':'+self.holder_id,1)


def deep_formation_supports(state,defender_id,attacker_id,attack_skill):
    """One bonus per real holder; repeated queries spend no action or resource."""
    if attack_skill is not Skill.MELEE or state.battlefield is None:return ()
    from towr.domain.pc_battlefield_manoeuvre_models import current_pc_charge
    charge=current_pc_charge(state,attacker_id)
    if charge is None or charge.target_id!=defender_id:return ()
    from towr.domain.pc_actor_models import pc_actor_side,pc_active_actor_ids,pc_actor_inventory
    side=pc_actor_side(state,defender_id)
    if pc_actor_side(state,attacker_id) is side:return ()
    spatial=state.battlefield.spatial
    zone=spatial.placement_for(defender_id).zone_id
    from towr.domain.talent_actor_models import actor_acquired_talents
    supports=[]
    for holder in pc_active_actor_ids(state,side):
        if holder==defender_id or spatial.placement_for(holder).zone_id!=zone:continue
        acquisition=next((source for source in actor_acquired_talents(state,holder)
            if source.id is TalentId.DEEP_FORMATION),None)
        if acquisition is None:continue
        inventory=pc_actor_inventory(state,holder)
        if inventory is None:continue
        if holder in state.source.pc_activation_order:
            from towr.domain.pc_medical_models import medical_effective_body
            from towr.domain.pc_weapon_inventory import _usable_pc_grips
            hands=_usable_pc_grips(medical_effective_body(state,holder))
        else:
            from towr.domain.pc_npc_weapon_inventory import _usable_npc_grips
            hands=_usable_npc_grips(state,state.enemy(holder))
        for item in inventory.items:
            profile=weapon_profile(item.kind)
            if (item.location is not WeaponItemLocation.HELD or profile.group is not WeaponGroup.MELEE
                    or profile.maximum_range is not RangedWeaponRange.SHORT):continue
            try:use=build_weapon_use(holder,inventory,item.id,usable_hands=hands)
            except ValueError:continue
            supports.append(PcDeepFormationSupport(holder,defender_id,zone,acquisition,use))
            break
    return tuple(supports)


def deep_formation_modifiers(state,defender_id,attacker_id,attack_skill):
    return tuple(source.modifier for source in deep_formation_supports(state,defender_id,attacker_id,attack_skill))
