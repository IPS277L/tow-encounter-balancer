from dataclasses import replace
import unittest

from towr.application.encounter_inventory import (
    EncounterEquipment, WeaponItem, ArmourItem, ArmourItemKind as Armour,
    ItemLocation as Location, ConsumableItem, ConsumableKind,
)
from towr.domain.pc_melee_models import PcMeleeWeapon as Weapon, PcWeaponHand
from towr.domain.pc_melee_models import PcMeleePolicy
from towr.domain.armour_models import BodyArmour, HelmetKind, ShieldKind
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.domain.pc_weapon_inventory import initial_pc_weapon_inventory
from towr.domain.weapon_inventory_models import WEAPON_COUNT_BURDEN_RULE_ID,carrying_burden_rule_ids


class EncounterInventoryTests(unittest.TestCase):
    def test_body_helmet_and_shield_compile_without_inventing_helmet_bonus(self):
        inventory = EncounterEquipment((WeaponItem('sword', Weapon.SWORD, Location.RIGHT),), (
            ArmourItem('body', Armour.LIGHT, Location.WORN),
            ArmourItem('helmet', Armour.HELMET, Location.WORN),
            ArmourItem('shield', Armour.SHIELD, Location.LEFT)))
        loadout = inventory.combat_loadout(3)
        self.assertEqual(loadout['armour'].body, (BodyArmour.LIGHT,))
        self.assertIs(loadout['armour'].benefit, BodyArmour.LIGHT)
        self.assertIs(loadout['armour'].helmet, HelmetKind.HELMET)
        self.assertIs(loadout['armour'].shield, ShieldKind.SHIELD)
        self.assertTrue(loadout['shield'])
        self.assertIs(loadout['weapon_hand'], PcWeaponHand.RIGHT)
        self.assertIsNone(loadout['backup_weapon_policy'])

    def test_two_swords_and_carried_glaive_are_facts_but_not_silently_reduced(self):
        inventory = EncounterEquipment((WeaponItem('left', Weapon.SWORD, Location.LEFT),
            WeaponItem('right', Weapon.SWORD, Location.RIGHT),
            WeaponItem('back', Weapon.GLAIVE, Location.CARRIED)), ())
        self.assertEqual(len(inventory.weapons), 3)
        loadout=inventory.combat_loadout(3)
        self.assertEqual(tuple(item.id for item in loadout['combat_equipment']),('left','right','back'))
        self.assertEqual(tuple(item.location.value for item in loadout['combat_equipment']),('held','held','carried'))
        self.assertIsNone(loadout['backup_weapon_policy'])

    def test_existing_two_hand_to_one_hand_backup_is_compiled(self):
        inventory = EncounterEquipment((WeaponItem('glaive', Weapon.GLAIVE, Location.BOTH),
            WeaponItem('sword', Weapon.SWORD, Location.CARRIED)), ())
        loadout=inventory.combat_loadout(3)
        self.assertIsNone(loadout['backup_weapon_policy'])
        self.assertEqual(tuple(item.weapon for item in loadout['combat_equipment']),(Weapon.GLAIVE,Weapon.SWORD))
        self.assertEqual(tuple(item.location.value for item in loadout['combat_equipment']),('held','carried'))

    def test_hands_carrying_and_unsupported_armour_are_checked_before_battle(self):
        sword = WeaponItem('sword', Weapon.SWORD, Location.RIGHT)
        for equipment in (
                EncounterEquipment((sword,), (ArmourItem('shield', Armour.SHIELD, Location.RIGHT),)),
                EncounterEquipment((replace(sword, weapon=Weapon.GLAIVE),), ())):
            with self.subTest(equipment=equipment), self.assertRaises(ValueError):
                equipment.combat_loadout(1)

    def test_over_capacity_is_legal_and_retains_an_independent_carrying_cause(self):
        inventory=EncounterEquipment((WeaponItem('sword',Weapon.SWORD,Location.RIGHT),
            WeaponItem('spare',Weapon.DAGGER,Location.CARRIED)),())
        loadout=inventory.combat_loadout(1)
        base=make_pc_melee_scenario().party[0]
        source=replace(base,pc=replace(base.pc,weapon=Weapon.SWORD,strength=1),
            policy=PcMeleePolicy.AUTOMATIC_COMBAT,initial_weapon_hand=PcWeaponHand.RIGHT,
            combat_equipment=loadout['combat_equipment'])
        current=initial_pc_weapon_inventory(source)
        self.assertEqual(len(current.items),2)
        self.assertEqual(carrying_burden_rule_ids(current,1),(WEAPON_COUNT_BURDEN_RULE_ID,))

    def test_heavy_armour_and_carried_shield_are_admitted_as_distinct_facts(self):
        sword = WeaponItem('sword', Weapon.SWORD, Location.RIGHT)
        inventory = EncounterEquipment((sword,), (
            ArmourItem('heavy', Armour.HEAVY, Location.WORN),
            ArmourItem('spare', Armour.SHIELD, Location.CARRIED)))
        loadout = inventory.combat_loadout(1)
        self.assertIs(loadout['armour'].benefit, BodyArmour.HEAVY)
        self.assertIsNone(loadout['armour'].shield)
        self.assertFalse(loadout['shield'])
        self.assertEqual(inventory.armour[1].id, 'spare')

    def test_duplicate_ids_and_invalid_physical_locations_are_rejected(self):
        with self.assertRaises(ValueError):
            EncounterEquipment((WeaponItem('same',Weapon.SWORD,Location.RIGHT),),
                (ArmourItem('same',Armour.HELMET,Location.WORN),))
        for kind, location in ((Armour.SHIELD,Location.WORN),(Armour.HELMET,Location.LEFT)):
            with self.assertRaises(ValueError):
                ArmourItem('invalid', kind, location)
        forged = WeaponItem('weapon', Weapon.SWORD, Location.RIGHT)
        object.__setattr__(forged, 'location', 'right_hand')
        with self.assertRaises(TypeError):
            EncounterEquipment((forged,), ())

    def test_potion_facts_require_count_and_matching_characteristic(self):
        self.assertEqual(ConsumableItem('healing', ConsumableKind.HEALING, 2, None).quantity, 2)
        self.assertEqual(ConsumableItem('enhancement', ConsumableKind.ENHANCEMENT, 1, 'strength').characteristic, 'strength')
        for kind, count, characteristic in ((ConsumableKind.HEALING,0,None),
                (ConsumableKind.HEALING,True,None),(ConsumableKind.HEALING,1,'strength'),
                (ConsumableKind.ENHANCEMENT,1,None),(ConsumableKind.ENHANCEMENT,1,'unknown')):
            with self.subTest(kind=kind,count=count), self.assertRaises(ValueError):
                ConsumableItem('invalid',kind,count,characteristic)


if __name__ == '__main__':
    unittest.main()
