"""Ordinary Brawn/Melee source admission without invented physical Unarmed items."""
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.application.encounter_character import EncounterCharacter
from towr.application.encounter_inventory import (
    ArmourItem, ArmourItemKind, EncounterEquipment, ItemLocation, WeaponItem,
)
from towr.domain.armour_models import ArmourLoadout, ShieldKind
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import (
    GeneratedAbility, GeneratedNpc, GeneratedWeapon, GENERATED_PHYSICAL_WEAPONS,
    generated_initial_weapon_inventory, generated_npc_profiles,
    generated_unarmed_attack_profile, generated_weapon_attack_profile,
)
from towr.domain.pc_combat_equipment_models import PcItemLocation, PcWeaponItem
from towr.domain.pc_melee_models import PcMeleeDefinition, PcMeleeWeapon, PcWeaponHand
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_inventory_models import WeaponGrip, WeaponItemLocation, WeaponItemSource


def generated(*, weapons=(), brawn=4, endurance=None, armour=None):
    return GeneratedNpc(3,4,5,2,3,2,weapons,armour or ArmourLoadout(),
        defence=3,brawn=brawn,endurance=endurance)


def pc_definition(kind=PcMeleeWeapon.UNARMED, *, brawn=4):
    return PcMeleeDefinition('pc-source',3,4,3,3,4,4,4,4,kind,0,brawn=brawn)


class BrawnWeaponSourceTests(unittest.TestCase):
    def test_unarmed_generated_has_a_real_brawn_profile_and_no_physical_unit(self):
        npc=generated()
        self.assertIs(npc.weapon,GeneratedWeapon.UNARMED)
        self.assertIsNone(npc.weapon_grip)
        inventory=generated_initial_weapon_inventory(npc,'npc')
        self.assertEqual(inventory.items,())
        self.assertIsNone(inventory.active_item_id)
        attack,=generated_npc_profiles(npc)[1]
        self.assertEqual(attack,generated_unarmed_attack_profile(npc))
        self.assertEqual(attack.id,'generated:unarmed')
        self.assertIs(attack.skill,Skill.BRAWN)
        self.assertEqual(attack.test_profile,InlineProfile(4,4))
        self.assertIsNone(attack.hands)
        self.assertIsNone(attack.damage)
        self.assertIs(attack.condition_impact.condition,Condition.STAGGERED)
        self.assertEqual((attack.range_min,attack.range_max),(RangedWeaponRange.CLOSE,)*2)
        participant=npc.participant('npc')
        self.assertFalse(participant.state.wields_weapon)
        self.assertEqual(participant.state.available_attack_ids,('generated:unarmed',))

    def test_all_carried_sources_preserve_their_items_and_begin_unarmed(self):
        carried=WeaponItemSource('back',WeaponKind.SWORD,WeaponItemLocation.CARRIED,None)
        npc=generated(weapons=(carried,))
        self.assertIs(npc.weapon,GeneratedWeapon.UNARMED)
        inventory=generated_initial_weapon_inventory(npc,'npc')
        self.assertIsNone(inventory.active_item_id)
        self.assertEqual(inventory.items[0].source,carried)
        self.assertIs(inventory.items[0].location,WeaponItemLocation.CARRIED)
        profiles=generated_npc_profiles(npc)[1]
        self.assertEqual(len(profiles),3)
        self.assertEqual(profiles[-1].id,'generated:unarmed')

    def test_unarmed_without_known_brawn_is_rejected_instead_of_assuming_a_rating(self):
        with self.assertRaises(ValueError):generated(brawn=None)
        with self.assertRaises(ValueError):pc_definition(brawn=None)
        with self.assertRaises(ValueError):
            generated(weapons=(WeaponItemSource('back',WeaponKind.SWORD,WeaponItemLocation.CARRIED,None),),brawn=None)

    def test_unarmed_is_never_a_physical_inventory_item_or_sampler_kind(self):
        self.assertNotIn(GeneratedWeapon.UNARMED,GENERATED_PHYSICAL_WEAPONS)
        with self.assertRaises(ValueError):
            WeaponItemSource('fist',WeaponKind.UNARMED,WeaponItemLocation.HELD,WeaponGrip.LEFT)
        with self.assertRaises(ValueError):
            PcWeaponItem('fist',PcMeleeWeapon.UNARMED,PcItemLocation.HELD,PcWeaponHand.LEFT)
        with self.assertRaises(ValueError):
            WeaponItem('fist',PcMeleeWeapon.UNARMED,ItemLocation.LEFT)

    def test_generated_endurance_is_optional_and_uses_its_actual_characteristic(self):
        self.assertEqual(tuple(profile.skill for profile in generated_npc_profiles(generated())[2]),
            (Skill.DEFENCE,Skill.ATHLETICS))
        profiles=generated_npc_profiles(generated(endurance=6))[2]
        self.assertEqual(tuple(profile.skill for profile in profiles),
            (Skill.DEFENCE,Skill.ATHLETICS,Skill.ENDURANCE))
        self.assertEqual(profiles[-1].test_profile,InlineProfile(5,6))
        for value in (True,1,7,3.0):
            with self.subTest(value=value),self.assertRaises(ValueError):
                generated(endurance=value)

    def test_knuckledusters_keep_an_actual_hand_and_strength_brawn_damage_profile(self):
        item=WeaponItemSource('knuckles',WeaponKind.KNUCKLEDUSTERS,
            WeaponItemLocation.HELD,WeaponGrip.RIGHT)
        npc=generated(weapons=(item,))
        profile=generated_weapon_attack_profile(npc,'knuckles',WeaponGrip.RIGHT)
        self.assertIs(profile.skill,Skill.BRAWN)
        self.assertEqual(profile.test_profile,InlineProfile(4,4))
        self.assertIs(profile.hands,RangedWeaponHands.ONE_HANDED)
        self.assertEqual(profile.damage.base,3)
        self.assertIsNone(profile.condition_impact)
        self.assertTrue(npc.participant('npc').state.wields_weapon)
        with self.assertRaises(ValueError):generated(weapons=(item,),brawn=None)
        with self.assertRaises(ValueError):pc_definition(PcMeleeWeapon.KNUCKLEDUSTERS,brawn=None)

    def test_cavalry_spear_and_lance_profiles_keep_printed_damage_and_range(self):
        for kind,maximum,damage in ((WeaponKind.CAVALRY_SPEAR,RangedWeaponRange.SHORT,4),
                (WeaponKind.LANCE,RangedWeaponRange.CLOSE,5)):
            with self.subTest(kind=kind):
                item=WeaponItemSource('weapon',kind,WeaponItemLocation.HELD,WeaponGrip.LEFT)
                npc=generated(weapons=(item,),brawn=None)
                profile=generated_weapon_attack_profile(npc,'weapon',WeaponGrip.LEFT)
                self.assertEqual(profile.test_profile,InlineProfile(3,3))
                self.assertIs(profile.skill,Skill.MELEE)
                self.assertEqual(profile.damage.base,damage)
                self.assertIs(profile.range_max,maximum)
                self.assertEqual(len(generated_npc_profiles(npc)[1]),2)
                pc_definition(PcMeleeWeapon(kind.value),brawn=None)

    def test_unarmed_shield_occupies_a_real_free_hand(self):
        npc=generated(armour=ArmourLoadout(shield=ShieldKind.SHIELD))
        inventory=generated_initial_weapon_inventory(npc,'npc')
        self.assertEqual(inventory.items,())
        self.assertIs(inventory.shield_hand,WeaponGrip.RIGHT)
        self.assertFalse(npc.participant('npc').state.wields_weapon)
        self.assertTrue(npc.participant('npc').state.holds_shield)

    def test_unarmed_cannot_silently_discard_an_authored_on_hit_ability(self):
        npc=generated()
        with self.assertRaisesRegex(ValueError,'numeric-Damage'):
            replace(npc,abilities=(GeneratedAbility.DRAINED_ON_HIT,))
        sword=WeaponItemSource('sword',WeaponKind.SWORD,WeaponItemLocation.HELD,WeaponGrip.LEFT)
        mixed=replace(npc,weapons=(sword,),abilities=(GeneratedAbility.DRAINED_ON_HIT,))
        attacks=generated_npc_profiles(mixed)[1]
        self.assertEqual(tuple(effect.condition for effect in attacks[0].secondary_effects),(Condition.DRAINED,))
        self.assertEqual(attacks[-1].secondary_effects,())

    def test_empty_player_inventory_compiles_mode_without_creating_an_item(self):
        source=make_pc_melee_scenario()
        member=replace(source.party[0],pc=pc_definition(),initial_weapon_hand=None,combat_equipment=())
        self.assertEqual(member.combat_equipment,())
        from towr.domain.pc_weapon_inventory import initial_pc_weapon_inventory
        inventory=initial_pc_weapon_inventory(member)
        self.assertEqual(inventory.items,())
        self.assertIsNone(inventory.active_item_id)
        with self.assertRaises(ValueError):replace(member,initial_weapon_hand=PcWeaponHand.LEFT)
        with self.assertRaises(ValueError):replace(member,combat_equipment=None)

    def test_player_character_preserves_unarmed_shield_hand_from_inventory(self):
        for location,hand in ((ItemLocation.LEFT,PcWeaponHand.LEFT),(ItemLocation.RIGHT,PcWeaponHand.RIGHT)):
            with self.subTest(location=location):
                equipment=EncounterEquipment((),(ArmourItem('shield',ArmourItemKind.SHIELD,location),))
                loadout=equipment.combat_loadout(4)
                self.assertEqual(loadout['combat_equipment'],())
                self.assertIs(loadout['weapon'],PcMeleeWeapon.UNARMED)
                self.assertIsNone(loadout['weapon_hand'])
                self.assertIs(loadout['shield_hand'],hand)
                character=EncounterCharacter('pc',3,4,3,3,4,4,4,4,
                    talents=(),fate=3,brawn=4,**loadout)
                from towr.domain.minion_defeat_models import NpcDefeatDisposition
                participant=character.participant('session',NpcDefeatDisposition.KILLED)
                self.assertIsNone(participant.initial_weapon_hand)
                self.assertIs(participant.shield.initial_hand,hand)

    def test_pc_knuckledusters_reject_a_target_with_no_lawful_protection_profile(self):
        source=make_pc_melee_scenario()
        member=replace(source.party[0],pc=replace(source.party[0].pc,
            weapon=PcMeleeWeapon.KNUCKLEDUSTERS,brawn=4))
        with self.assertRaisesRegex(ValueError,'Brawn opponents'):
            replace(source,party=(member,))
        npc=generated().participant(source.enemy_activation_order[0])
        admitted=replace(source,party=(member,),enemies=(npc,))
        self.assertEqual(admitted.enemies,(npc,))


if __name__=='__main__':
    unittest.main()
