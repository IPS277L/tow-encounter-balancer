"""GM82–84/103 item facts, complete source admission and finite proposals."""
from dataclasses import replace
from random import Random
import unittest

from towr.application.dynamic_encounter import NpcSearchSpace, automatic_npc_search_space
from towr.application.encounter_inventory import WeaponItem, ItemLocation
from towr.adapters._pc_melee_scenario_json import generated_components_document, parse_generated_components
from towr.adapters.pc_melee_json_errors import PcMeleeInputError
from towr.domain.armour_models import ShieldKind
from towr.domain.generated_npc_models import (
    GeneratedWeapon, GENERATED_EXPLICIT_WEAPONS, GENERATED_ORDINARY_WEAPONS,
    GENERATED_CLOSE_WEAPONS, generated_npc_profiles, generated_initial_weapon_inventory,
)
from towr.domain.pc_combat_equipment_models import PcWeaponItem
from towr.domain.pc_melee_models import PC_EXECUTABLE_WEAPONS
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as R, RangedWeaponHands as H
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.weapon_catalog import WeaponKind as W
from towr.domain.weapon_inventory_models import WeaponGrip as G, WeaponHand as Hand, WeaponItemLocation as L


KINDS=(W.DRAGON_BOW,W.DUELLIST_BLADES,W.GROTARGGS_HAMMER,W.HEADSMANS_AXE,
    W.MORNING_STAR_OF_FRACASSE,W.SCARAB_KNIFE,W.TRICKSTER_BLADE,
    W.UNWAVERING_SPEAR,W.SWORD_OF_JUSTICE,W.OGRE_PISTOL)


def space(kind, **kwargs):
    return NpcSearchSpace(weapon=(GeneratedWeapon(kind.value),),weapon_count=(1,),
        weapon_skill=(2,),strength=(3,),toughness=(4,),agility=(2,),melee=(6,),
        athletics=(3,),defence=(4,),brawn=(4,),endurance=(3,),armour=(None,),shield=(None,),
        ballistic_skill=(5,),shooting=(3,),initiative=(2,),dexterity=(4,),awareness=(5,),
        allowed_talents=(),ogre_fit_confirmed=True if kind is W.OGRE_PISTOL else None,**kwargs)


class MagicWeaponSourceTests(unittest.TestCase):
    def test_full_fifty_catalogue_admission_and_ordinary_defaults_are_separate(self):
        self.assertEqual(set(PC_EXECUTABLE_WEAPONS),set(W))
        self.assertEqual({kind.value for kind in GeneratedWeapon},{kind.value for kind in W})
        self.assertEqual({kind.value for kind in GENERATED_EXPLICIT_WEAPONS},{kind.value for kind in KINDS})
        self.assertEqual(len(GENERATED_ORDINARY_WEAPONS),39)
        self.assertFalse(set(GENERATED_EXPLICIT_WEAPONS)&set(NpcSearchSpace().weapon))
        self.assertFalse(set(GENERATED_EXPLICIT_WEAPONS)&set(GENERATED_CLOSE_WEAPONS))

    def test_literal_magic_stats_and_actual_owners_skills(self):
        # Literal GM table values, deliberately distinct WS/BS/Strength/rating.
        expected={W.DRAGON_BOW:(6,H.TWO_HANDED,R.MEDIUM,R.EXTREME),
            W.DUELLIST_BLADES:(5,H.TWO_HANDED,R.CLOSE,R.CLOSE),
            W.GROTARGGS_HAMMER:(6,H.TWO_HANDED,R.CLOSE,R.CLOSE),
            W.HEADSMANS_AXE:(6,H.TWO_HANDED,R.CLOSE,R.CLOSE),
            W.MORNING_STAR_OF_FRACASSE:(6,H.ONE_HANDED,R.CLOSE,R.CLOSE),
            W.SCARAB_KNIFE:(4,H.ONE_HANDED,R.CLOSE,R.CLOSE),
            W.TRICKSTER_BLADE:(4,H.ONE_HANDED,R.CLOSE,R.CLOSE),
            W.UNWAVERING_SPEAR:(4,H.TWO_HANDED,R.CLOSE,R.SHORT),
            W.SWORD_OF_JUSTICE:(4,H.ONE_HANDED,R.CLOSE,R.CLOSE),
            W.OGRE_PISTOL:(5,H.ONE_HANDED,R.CLOSE,R.MEDIUM)}
        for kind,(damage,hands,low,high) in expected.items():
            with self.subTest(kind=kind):
                source=space(kind).sample(Random(2))
                profile=generated_npc_profiles(source)[1][0]
                ranged=kind in (W.DRAGON_BOW,W.OGRE_PISTOL)
                self.assertIs(profile.skill,Skill.SHOOTING if ranged else Skill.MELEE)
                self.assertEqual(profile.test_profile,InlineProfile(5,3) if ranged else InlineProfile(2,6))
                self.assertEqual((profile.damage.base,profile.hands,profile.range_min,profile.range_max),
                    (damage,hands,low,high))
                self.assertIs(profile.ignores_armour,kind is W.OGRE_PISTOL)
                self.assertEqual(profile.secondary_effects,())
                self.assertEqual(source.abilities,())

    def test_scarab_initial_charge_belongs_to_each_exact_instance(self):
        source=space(W.SCARAB_KNIFE,scarab_initial_charges=(4,)).sample(Random(1))
        second=replace(source.weapons[0],id='other',initial_location=L.CARRIED,initial_grip=None,initial_charges=1)
        source=replace(source,weapons=source.weapons+(second,))
        inventory=generated_initial_weapon_inventory(source,'npc')
        self.assertEqual(tuple(item.charges for item in inventory.items),(4,1))
        self.assertEqual(tuple(item.source.initial_charges for item in inventory.items),(4,1))
        with self.assertRaises(ValueError):replace(source.weapons[0],kind=W.SWORD)
        for bad in (True,-1,1.5):
            with self.subTest(bad=bad),self.assertRaises((ValueError,TypeError)):
                replace(source.weapons[0],initial_charges=bad)

    def test_ogre_permission_is_exact_and_no_ogre_profile_or_abilities_are_inherited(self):
        for bad in (None,False,1,'true'):
            with self.subTest(bad=bad),self.assertRaises((ValueError,TypeError)):
                NpcSearchSpace(weapon=(GeneratedWeapon.OGRE_PISTOL,),ogre_fit_confirmed=bad)
        source=space(W.OGRE_PISTOL).sample(Random(1))
        item=source.weapons[0]
        self.assertIs(item.gm_fit_confirmed,True)
        self.assertIs(item.initially_loaded,True)
        profile=generated_npc_profiles(source)[1][0]
        self.assertEqual(profile.test_profile,InlineProfile(5,3))
        self.assertEqual(source.abilities,())
        for bad in (None,False,1):
            with self.subTest(bad=bad),self.assertRaises((ValueError,TypeError)):
                replace(item,gm_fit_confirmed=bad)
        with self.assertRaises(ValueError):replace(item,kind=W.PISTOL)

    def test_pc_source_rows_preserve_initial_charge_and_explicit_fit(self):
        knife=WeaponItem('scarab',W.SCARAB_KNIFE,ItemLocation.LEFT,initial_charges=5)
        native=PcWeaponItem('scarab',W.SCARAB_KNIFE,L.HELD,Hand.LEFT,initial_charges=5)
        self.assertEqual((knife.initial_charges,native.initial_charges),(5,5))
        for cls,loc,extra in ((WeaponItem,ItemLocation.LEFT,()),(PcWeaponItem,L.HELD,(Hand.LEFT,))):
            with self.assertRaises(ValueError):cls('ogre',W.OGRE_PISTOL,loc,*extra,initially_loaded=True)
            item=cls('ogre',W.OGRE_PISTOL,loc,*extra,initially_loaded=False,gm_fit_confirmed=True)
            self.assertIs(item.gm_fit_confirmed,True)
            with self.assertRaises(ValueError):replace(item,initial_charges=3)

    def test_mutation_numeric_resampling_and_native_source_roundtrip_preserve_facts(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                allowed=space(kind,scarab_initial_charges=(0,3))
                source=allowed.sample(Random(3))
                for member in (source,allowed.mutate(source,Random(5)),
                        allowed.resample_numeric((source,),Random(8)).composition[0]):
                    self.assertTrue(allowed.contains(member))
                    document=generated_components_document(member)
                    restored=parse_generated_components(document,path_prefix='/npc',error_type=PcMeleeInputError)
                    self.assertEqual(restored,member)
                numeric=allowed.resample_numeric((source,),Random(9)).composition[0]
                self.assertEqual(numeric.weapons,source.weapons)
        knife=space(W.SCARAB_KNIFE,scarab_initial_charges=(0,3)).sample(Random(0))
        self.assertFalse(space(W.SCARAB_KNIFE,scarab_initial_charges=(0,)).contains(
            replace(knife,weapons=(replace(knife.weapons[0],initial_charges=3),))))

