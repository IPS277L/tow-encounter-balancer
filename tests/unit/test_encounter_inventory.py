from dataclasses import replace
import unittest

from towr.application.encounter_inventory import (
    EncounterEquipment, WeaponItem, ArmourItem, ArmourItemKind as Armour,
    ItemLocation as Location, ConsumableItem, ConsumableKind,
)
from towr.domain.pc_melee_models import PcMeleeWeapon as Weapon, PcWeaponHand


class EncounterInventoryTests(unittest.TestCase):
    def test_body_helmet_and_shield_compile_without_inventing_helmet_bonus(self):
        inventory = EncounterEquipment((WeaponItem('sword', Weapon.SWORD, Location.RIGHT),), (
            ArmourItem('body', Armour.LIGHT, Location.WORN),
            ArmourItem('helmet', Armour.HELMET, Location.WORN),
            ArmourItem('shield', Armour.SHIELD, Location.LEFT)))
        loadout = inventory.combat_loadout(3)
        self.assertEqual(loadout['armour'].value, 'light')
        self.assertTrue(loadout['shield'])
        self.assertIs(loadout['weapon_hand'], PcWeaponHand.RIGHT)
        self.assertIsNone(loadout['backup_weapon_policy'])

    def test_two_swords_and_carried_glaive_are_facts_but_not_silently_reduced(self):
        inventory = EncounterEquipment((WeaponItem('left', Weapon.SWORD, Location.LEFT),
            WeaponItem('right', Weapon.SWORD, Location.RIGHT),
            WeaponItem('back', Weapon.GLAIVE, Location.CARRIED)), ())
        self.assertEqual(len(inventory.weapons), 3)
        with self.assertRaisesRegex(ValueError, 'двумя оружиями'):
            inventory.combat_loadout(3)

    def test_existing_two_hand_to_one_hand_backup_is_compiled(self):
        inventory = EncounterEquipment((WeaponItem('glaive', Weapon.GLAIVE, Location.BOTH),
            WeaponItem('sword', Weapon.SWORD, Location.CARRIED)), ())
        backup = inventory.combat_loadout(3)['backup_weapon_policy']
        self.assertIs(backup.weapon, Weapon.SWORD)
        self.assertIs(backup.preferred_hand, PcWeaponHand.RIGHT)

    def test_hands_carrying_and_unsupported_armour_are_checked_before_battle(self):
        sword = WeaponItem('sword', Weapon.SWORD, Location.RIGHT)
        for equipment in (
                EncounterEquipment((sword,), (ArmourItem('shield', Armour.SHIELD, Location.RIGHT),)),
                EncounterEquipment((replace(sword, weapon=Weapon.GLAIVE),), ()),
                EncounterEquipment((sword,), (ArmourItem('heavy', Armour.HEAVY, Location.WORN),)),
                EncounterEquipment((sword,), (ArmourItem('spare', Armour.SHIELD, Location.CARRIED),)),
                EncounterEquipment((sword, replace(sword,id='two',location=Location.CARRIED)), ())):
            with self.subTest(equipment=equipment), self.assertRaises(ValueError):
                equipment.combat_loadout(1)

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
