"""Initial PC weapon facts, compiled to the shared physical unit inventory.

These role-specific rows are immutable authoring source, never runtime items.
The common inventory owns actual locations, grips and complete K1 resources.
"""
from __future__ import annotations

from dataclasses import dataclass,field,replace
from enum import Enum
from typing import TYPE_CHECKING

from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_inventory_models import WeaponGrip,WeaponInventoryState,WeaponItemSource,weapon_reload_target

if TYPE_CHECKING:
    from towr.domain.pc_melee_models import PcMeleeWeapon,PcWeaponHand,PcTwoHandedGrip


from towr.domain.weapon_inventory_models import WeaponItemLocation as PcItemLocation


def _identifier(value):
    if type(value) is not str or not value.strip():
        raise TypeError('weapon inventory needs exact nonempty identifiers')


@dataclass(frozen=True,slots=True)
class PcWeaponItem:
    id: str
    weapon: PcMeleeWeapon
    location: PcItemLocation
    hand: PcWeaponHand | PcTwoHandedGrip | None
    initially_loaded: bool | None = field(default=None,kw_only=True)
    quantity: int = field(default=1,kw_only=True)
    initial_charges: int = field(default=0,kw_only=True)
    gm_fit_confirmed: bool | None = field(default=None,kw_only=True)

    def __post_init__(self):
        from towr.domain.pc_melee_models import PcMeleeWeapon,PcWeaponHand,PcTwoHandedGrip
        from towr.domain.pc_weapon_models import pc_weapon_requires_two_hands, pc_weapon_supports_variable_grip
        _identifier(self.id)
        if type(self.weapon) is not PcMeleeWeapon or type(self.location) is not PcItemLocation:
            raise TypeError('weapon item needs its exact weapon and location enums')
        if self.weapon is PcMeleeWeapon.UNARMED:
            raise ValueError('Unarmed is an attack mode, never a physical inventory item')
        if self.location not in (PcItemLocation.HELD,PcItemLocation.CARRIED):
            raise ValueError('an initial weapon item begins held or carried')
        if self.location is not PcItemLocation.HELD:
            if self.hand is not None:
                raise ValueError('a carried initial weapon has no held hand')
        elif (pc_weapon_requires_two_hands(self.weapon)
                or pc_weapon_supports_variable_grip(self.weapon) and self.hand is PcTwoHandedGrip.BOTH):
            if self.hand is not PcTwoHandedGrip.BOTH:
                raise ValueError('a held two-handed weapon needs its actual two-handed grip')
        elif type(self.hand) is not PcWeaponHand:
            raise TypeError('a held one-handed weapon needs its exact hand')
        if self.initially_loaded is not None and type(self.initially_loaded) is not bool:
            raise TypeError('initial item charge must be an exact bool or None')
        if weapon_reload_target(self.weapon) is not None:
            if self.initially_loaded is None:
                raise ValueError('each Exacting item requires its explicit initial loaded bool')
        elif self.initially_loaded is not None:
            raise ValueError('only an Exacting weapon has an initial loaded flag')
        WeaponItemSource(self.id,self.weapon,self.location,
            None if self.hand is None else WeaponGrip(self.hand.value),
            quantity=self.quantity,initially_loaded=self.initially_loaded,
            initial_charges=self.initial_charges,gm_fit_confirmed=self.gm_fit_confirmed)


def pc_initial_weapon_kinds(participant):
    """Initial physical capabilities, independently of the first selected item."""
    items=participant.combat_equipment
    if items is None:
        return (participant.pc.weapon,*(
            () if participant.backup_weapon_policy is None else (participant.backup_weapon_policy.weapon,)))
    if type(items) is not tuple or any(type(item) is not PcWeaponItem for item in items):
        raise TypeError('initial weapon kinds require the exact ordered item sources')
    return tuple(item.weapon for item in items)


def validate_pc_combat_equipment(participant):
    """Re-admit complete initial inventory against the executable loadout."""
    from towr.domain.pc_melee_models import (
        PcMeleeParticipant,PcMeleePolicy,PC_RANGED_WEAPONS,PC_THROWING_WEAPONS,
        PC_EXECUTABLE_WEAPONS,PcRangedReloadHandPolicy,PcRangedProfile,PcRepeaterBonusPolicy,
    )
    from towr.domain.weapon_capability_models import weapon_ranged_requirements
    if type(participant) is not PcMeleeParticipant:
        raise TypeError('combat equipment requires its exact participant source')
    items=getattr(participant,'combat_equipment',None)
    if items is None:
        if participant.pc.weapon is WeaponKind.UNARMED:
            raise ValueError('Unarmed needs an explicit physical inventory, including an empty tuple')
        if participant.pc.ranged is not None or participant.pc.weapon in PC_RANGED_WEAPONS:
            raise ValueError('Shooting facts require the complete concrete source weapon items')
        return
    if type(items) is not tuple or any(type(item) is not PcWeaponItem for item in items):
        raise TypeError('combat equipment needs an ordered typed tuple')
    for item in items:
        replace(item)
        if item.weapon not in PC_EXECUTABLE_WEAPONS:
            raise ValueError('this item requires its unfinished encounter effect owner')
        if item.weapon in PC_THROWING_WEAPONS:
            participant.pc.throwing_profile
        if item.weapon in (WeaponKind.KNUCKLEDUSTERS,WeaponKind.GROTARGGS_HAMMER):
            participant.pc.brawn_profile
    if len({item.id for item in items})!=len(items):
        raise ValueError('initial combat equipment needs distinct item IDs')
    held=tuple(item for item in items if item.location is PcItemLocation.HELD)
    if not held:
        if participant.pc.weapon is not WeaponKind.UNARMED or participant.initial_weapon_hand is not None:
            raise ValueError('an inventory without held weapons requires explicit Unarmed/Brawn')
        participant.pc.brawn_profile
    else:
        primary=held[0]
        if (primary.weapon is not participant.pc.weapon or primary.hand is not participant.initial_weapon_hand):
            raise ValueError('initial primary item differs from its complete weapon/grip source')
    requirements=weapon_ranged_requirements(tuple(item.weapon for item in items))
    facts=participant.pc.ranged
    if requirements is None:
        if facts is not None:
            raise ValueError('Shooting facts require an actual Shooting inventory item')
    else:
        if type(facts) is not PcRangedProfile:
            raise TypeError('every Shooting item requires the exact actor preparation facts')
        replace(facts)
        for name in ('has_blackpowder_lore','has_blackpowder_kit'):
            if getattr(facts,name) is not (True if requirements.firearm else None):
                raise ValueError('Blackpowder Lore and Kit must match the whole firearm inventory')
        if requirements.exacting:
            participant.pc.dexterity_profile
            if facts.reload_hand_policy is not PcRangedReloadHandPolicy.TWO_AVAILABLE_HANDS:
                raise ValueError('Exacting items require their actual Reload hand policy')
        elif facts.reload_hand_policy is not None:
            raise ValueError('a free-reload-only inventory has no Exacting preparation')
        if requirements.requires_aim:
            participant.pc.awareness_profile
        if requirements.repeater:
            if type(facts.repeater_bonus_policy) is not PcRepeaterBonusPolicy:
                raise TypeError('Repeater items require their actual bonus policy')
            if (participant.policy is PcMeleePolicy.AUTOMATIC_COMBAT
                    and facts.repeater_bonus_policy is not PcRepeaterBonusPolicy.AUTOMATIC):
                raise ValueError('automatic combat requires automatic Repeater decisions')
        elif facts.repeater_bonus_policy is not None:
            raise ValueError('a non-Repeater inventory has no Repeater bonus policy')
    if (participant.backup_weapon_policy is not None and participant.policy is not PcMeleePolicy.AUTOMATIC_COMBAT):
        backup=tuple(item for item in items if item.weapon is participant.backup_weapon_policy.weapon
            and item.location is PcItemLocation.CARRIED)
        if len(backup)!=1:
            raise ValueError('fixed backup policy requires one unambiguous matching carried item')
    # The shared compiler proves actual hand occupancy, including two held
    # 1H implements and the Shield. It deliberately does not call this validator.
    from towr.domain.pc_weapon_inventory import initial_pc_weapon_inventory
    inventory=initial_pc_weapon_inventory(participant)
    if type(inventory) is not WeaponInventoryState:
        raise TypeError('initial PC equipment must compile to the common inventory')
    replace(inventory)


def validate_pc_weapon_inventory(member,participant):
    """Check immutable source membership; chronological changes belong to proofs."""
    from towr.domain.pc_melee_models import PcMeleeParticipant
    from towr.domain.pc_weapon_inventory import initial_pc_weapon_inventory
    from towr.domain.pc_shield_models import PcShieldLocation,PcShieldState
    if type(participant) is not PcMeleeParticipant:
        raise TypeError('runtime equipment requires its exact participant source')
    inventory=getattr(member,'weapon_inventory',None)
    if member.actor_id!=participant.actor_id:
        raise ValueError('weapon inventory belongs to another source actor')
    if type(inventory) is not WeaponInventoryState:
        raise TypeError('runtime weapon inventory must retain its exact common state')
    replace(inventory)
    initial=initial_pc_weapon_inventory(participant)
    if type(initial) is not WeaponInventoryState:
        raise TypeError('initial PC equipment must compile to the common inventory')
    source_key=lambda item:(item.id,item.source,item.initial_actor_id,item.source_item_id,item.unit_index)
    if tuple(map(source_key,inventory.items))!=tuple(map(source_key,initial.items)):
        raise ValueError('runtime inventory changed its complete initial source membership or origin')
    shield=getattr(member,'shield',None)
    if (participant.shield is None)!=(shield is None):
        raise ValueError('runtime Shield must retain its actual initial item source')
    hand=None
    if shield is not None:
        if type(shield) is not PcShieldState:
            raise TypeError('runtime Shield requires its actual typed state')
        replace(shield)
        if shield.location in (PcShieldLocation.HELD,PcShieldLocation.UNAVAILABLE):
            hand=WeaponGrip(shield.hand.value)
    if inventory.shield_hand is not hand:
        raise ValueError('common inventory Shield hand differs from its actual physical state')
