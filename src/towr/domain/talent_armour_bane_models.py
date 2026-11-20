"""Armour Bane's real item sources and bounded reduction, PG1.4 III73.

The reduction never retroactively changes the Attack's Damage/Wound comparison
and never destroys a physical armour item or its independent Traits.
"""
from dataclasses import dataclass,replace

from towr.domain.attack_models import ResilienceProfile
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import AcquiredTalent
from towr.domain.weapon_catalog import WeaponKind,WeaponTrait,weapon_profile
from towr.domain.weapon_use_models import WeaponUse


ARMOUR_BANE_RULE_ID='RULE-TALENT-002:armour-bane'


@dataclass(frozen=True,slots=True)
class ArmourBaneWeaponSource:
    item_id:str
    kind:WeaponKind
    bonus_against_armour:bool
    ignores_armour:bool
    magical:bool

    def __post_init__(self):
        if type(self.item_id) is not str or not self.item_id.strip():
            raise TypeError('Armour Bane requires its actual physical item identifier')
        if type(self.kind) is not WeaponKind:
            raise TypeError('Armour Bane requires its exact weapon kind')
        for value in (self.bonus_against_armour,self.ignores_armour,self.magical):
            if type(value) is not bool:
                raise TypeError('Armour Bane Traits require exact booleans')
        profile=weapon_profile(self.kind)
        expected=(WeaponTrait.ARMOURED_TARGET_DAMAGE_PLUS_ONE in profile.trait_codes,
            WeaponTrait.IGNORES_ARMOUR in profile.trait_codes,profile.magical)
        if (self.bonus_against_armour,self.ignores_armour,self.magical)!=expected or not any(expected[:2]):
            raise ValueError('Armour Bane qualification differs from the actual weapon Traits')


def armour_bane_weapon_sources(use:WeaponUse)->tuple[ArmourBaneWeaponSource,...]:
    """Read intrinsic Traits of the selected primary and real contributors.

    This does not claim that a ward permits a Trait or that an Attack hit. A
    carried Axe and a magical primary's provenance cannot change another unit.
    """
    if type(use) is not WeaponUse:
        raise TypeError('Armour Bane requires the full actual selected WeaponUse')
    replace(use)
    result=[]
    for identifier in use.item_ids:
        item=use.inventory.item(identifier)
        profile=weapon_profile(item.kind)
        bonus=WeaponTrait.ARMOURED_TARGET_DAMAGE_PLUS_ONE in profile.trait_codes
        ignore=WeaponTrait.IGNORES_ARMOUR in profile.trait_codes
        if bonus or ignore:
            result.append(ArmourBaneWeaponSource(identifier,item.kind,bonus,ignore,profile.magical))
    return tuple(result)


def lower_armour_bane_resilience(before:ResilienceProfile)->ResilienceProfile:
    """Apply one already-authorised reduction with the actual Toughness floor.

    The zero-bonus armoured flag (e.g. Helmet) follows PG73's specific rule.
    Ward metadata stays: the Talent does not remove the worn item's Traits.
    """
    if type(before) is not ResilienceProfile:
        raise TypeError('Armour Bane requires the actual target ResilienceProfile')
    replace(before)
    bonus=max(0,before.bonus-1)
    return replace(before,bonus=bonus,armoured=False if bonus==0 else before.armoured)


def armour_bane_eligible_sources(use:WeaponUse,
        before:ResilienceProfile)->tuple[ArmourBaneWeaponSource,...]:
    """C5: cancelled mundane Traits cannot authorise the Talent.

    A magical primary never changes an ordinary contributor's provenance.
    """
    if type(before) is not ResilienceProfile:
        raise TypeError('Armour Bane qualification requires its actual target Resilience')
    replace(before)
    return tuple(source for source in armour_bane_weapon_sources(use)
        if source.magical or not before.mundane_armour_ward)


@dataclass(frozen=True,slots=True)
class ArmourBaneApplication:
    attack_id:str
    actor_id:str
    target_id:str
    talent:AcquiredTalent
    weapon_use:WeaponUse
    sources:tuple[ArmourBaneWeaponSource,...]
    before:ResilienceProfile

    def __post_init__(self):
        for value in (self.attack_id,self.actor_id,self.target_id):
            if type(value) is not str or not value.strip():
                raise TypeError('Armour Bane must retain exact Attack and actor identifiers')
        if self.actor_id==self.target_id:
            raise ValueError('Armour Bane cannot lower its own attacker')
        if type(self.talent) is not AcquiredTalent:
            raise TypeError('Armour Bane requires the actual acquired Talent')
        replace(self.talent)
        if self.talent.id is not TalentId.ARMOUR_BANE:
            raise ValueError('another Talent cannot authorise Armour Bane')
        eligible=armour_bane_eligible_sources(self.weapon_use,self.before)
        if self.weapon_use.actor_id!=self.actor_id:
            raise ValueError('Armour Bane item sources belong to another actor')
        if (type(self.sources) is not tuple or not self.sources
                or any(type(source) is not ArmourBaneWeaponSource for source in self.sources)):
            raise TypeError('Armour Bane requires its exact nonempty qualifying source tuple')
        for source in self.sources:
            replace(source)
        if self.sources!=eligible:
            raise ValueError('Armour Bane must preserve every actually qualifying item source')
        if self.before.bonus==0 and not self.before.is_armoured:
            raise ValueError('Armour Bane cannot invent a reduction on an already unarmoured target')

    @property
    def reduction(self)->int:
        return min(1,self.before.bonus)

    @property
    def after(self)->ResilienceProfile:
        return lower_armour_bane_resilience(self.before)
