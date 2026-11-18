"""Explicit initial weapon sources for healthy authored PC fixtures."""
from towr.domain.pc_combat_equipment_models import PcItemLocation,PcWeaponItem


def initial_weapon_items(weapon,grip,backup=None,*,initially_loaded=None):
    """Construct declared items; strict source validation handles missing facts."""
    return (PcWeaponItem('weapon',weapon,PcItemLocation.HELD,grip,initially_loaded=initially_loaded),
        *((PcWeaponItem('backup-weapon',backup.weapon,PcItemLocation.CARRIED,None),)
            if backup is not None else ()))
