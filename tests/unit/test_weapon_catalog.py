"""Literal book rows and typed catalogue boundaries; no simulator execution."""
from dataclasses import FrozenInstanceError, replace
import unittest

from towr.domain.ranged_weapon_profiles import RangedWeaponHands as H, RangedWeaponId, RangedWeaponRange as R
from towr.domain.test_models import Skill
from towr.domain.weapon_catalog import (
    MAGIC_WEAPON_KINDS, WEAPON_PROFILES, WeaponBook, WeaponDamageKind as D,
    WeaponGroup as G, WeaponKind as W, WeaponProfile, WeaponTrait as T,
    weapon_is_magical, weapon_is_physical, weapon_printed_damage, weapon_profile,
)


class WeaponCatalogTests(unittest.TestCase):
    def test_complete_book_inventory_has_fifty_unique_rows_in_source_order(self):
        self.assertEqual(len(W),50)
        self.assertEqual(len(WEAPON_PROFILES),50)
        self.assertEqual(len({profile.kind for profile in WEAPON_PROFILES}),50)
        self.assertEqual(set(profile.kind for profile in WEAPON_PROFILES),set(W))
        self.assertEqual(tuple(profile.kind for profile in WEAPON_PROFILES),tuple(W))
        self.assertEqual(sum(profile.source_book is WeaponBook.PLAYER_GUIDE for profile in WEAPON_PROFILES),40)
        self.assertEqual(len(MAGIC_WEAPON_KINDS),9)
        self.assertEqual(sum(profile.magical for profile in WEAPON_PROFILES),9)
        self.assertTrue({kind.value for kind in RangedWeaponId} <= {kind.value for kind in W})

    def test_twenty_pg_melee_rows_keep_printed_damage_hands_range_and_skill(self):
        # PG1.4 IV93, in the table's order. Values are the printed S offsets.
        rows=(
            (W.UNARMED,None,None,R.CLOSE,Skill.BRAWN),
            (W.KNUCKLEDUSTERS,-1,H.ONE_HANDED,R.CLOSE,Skill.BRAWN),
            (W.DAGGER,-1,H.ONE_HANDED,R.CLOSE,Skill.MELEE),
            (W.STAFF,0,H.ONE_HANDED,R.CLOSE,Skill.MELEE),
            (W.FOOT_SPEAR,0,H.ONE_HANDED,R.SHORT,Skill.MELEE),
            (W.CAVALRY_SPEAR,0,H.ONE_HANDED,R.SHORT,Skill.MELEE),
            (W.AXE,0,H.ONE_HANDED,R.CLOSE,Skill.MELEE),
            (W.PICKAXE,1,H.TWO_HANDED,R.CLOSE,Skill.MELEE),
            (W.SWORD,0,H.ONE_HANDED,R.CLOSE,Skill.MELEE),
            (W.WARHAMMER,0,H.ONE_HANDED,R.CLOSE,Skill.MELEE),
            (W.MORNING_STAR,1,H.ONE_HANDED,R.CLOSE,Skill.MELEE),
            (W.POLEARM,0,H.ONE_HANDED,R.SHORT,Skill.MELEE),
            (W.FLAIL,3,H.TWO_HANDED,R.CLOSE,Skill.MELEE),
            (W.BILLHOOK,2,H.TWO_HANDED,R.CLOSE,Skill.MELEE),
            (W.HALBERD,2,H.TWO_HANDED,R.CLOSE,Skill.MELEE),
            (W.GLAIVE,2,H.TWO_HANDED,R.CLOSE,Skill.MELEE),
            (W.GREATAXE,3,H.TWO_HANDED,R.CLOSE,Skill.MELEE),
            (W.GREATSWORD,3,H.TWO_HANDED,R.CLOSE,Skill.MELEE),
            (W.GREATHAMMER,3,H.TWO_HANDED,R.CLOSE,Skill.MELEE),
            (W.LANCE,1,H.ONE_HANDED,R.CLOSE,Skill.MELEE),
        )
        for kind,offset,hands,maximum,skill in rows:
            with self.subTest(kind=kind):
                profile=weapon_profile(kind)
                self.assertEqual((profile.group,profile.damage_value,profile.hands,profile.maximum_range,profile.skill),
                    (G.MELEE,offset,hands,maximum,skill))
                self.assertIs(profile.damage_kind,D.NONE if offset is None else D.STRENGTH)
                self.assertEqual((profile.optimum_range_min,profile.optimum_range_max),(None,None))
                self.assertEqual((profile.source_book,profile.source_chapter,profile.source_page),
                    (WeaponBook.PLAYER_GUIDE,'IV',93))

    def test_pg_shooting_table_preserves_sling_strength_and_printed_fixed_values(self):
        # PG1.4 IV95. None maximum is the PG94 GM-bound 2H range.
        rows=(
            (W.SLING,D.STRENGTH,0,H.ONE_HANDED,R.LONG,R.MEDIUM,R.MEDIUM),
            (W.SHORTBOW,D.FIXED,3,H.TWO_HANDED,None,R.SHORT,R.MEDIUM),
            (W.WARBOW,D.FIXED,3,H.TWO_HANDED,None,R.MEDIUM,R.LONG),
            (W.LONGBOW,D.FIXED,4,H.TWO_HANDED,None,R.MEDIUM,R.LONG),
            (W.CROSSBOW,D.FIXED,4,H.TWO_HANDED,None,R.SHORT,R.LONG),
            (W.PISTOL,D.FIXED,5,H.ONE_HANDED,R.LONG,R.CLOSE,R.SHORT),
            (W.HANDGUN,D.FIXED,5,H.TWO_HANDED,None,R.MEDIUM,R.LONG),
            (W.BLUNDERBUSS,D.FIXED,4,H.TWO_HANDED,R.MEDIUM,R.SHORT,R.SHORT),
            (W.HOCHLAND_LONG_RIFLE,D.FIXED,6,H.TWO_HANDED,None,R.MEDIUM,R.EXTREME),
            (W.REPEATER_HANDBOW,D.FIXED,4,H.ONE_HANDED,R.LONG,R.CLOSE,R.SHORT),
            (W.REPEATER_CROSSBOW,D.FIXED,4,H.TWO_HANDED,None,R.SHORT,R.MEDIUM),
            (W.REPEATER_PISTOL,D.FIXED,5,H.ONE_HANDED,R.LONG,R.CLOSE,R.SHORT),
            (W.REPEATER_HANDGUN,D.FIXED,5,H.TWO_HANDED,None,R.SHORT,R.LONG),
        )
        for kind,damage_kind,value,hands,maximum,low,high in rows:
            with self.subTest(kind=kind):
                profile=weapon_profile(kind)
                self.assertEqual((profile.group,profile.skill,profile.damage_kind,profile.damage_value,
                    profile.hands,profile.maximum_range,profile.optimum_range_min,profile.optimum_range_max),
                    (G.SHOOTING,Skill.SHOOTING,damage_kind,value,hands,maximum,low,high))
                self.assertEqual((profile.source_book,profile.source_chapter,profile.source_page),
                    (WeaponBook.PLAYER_GUIDE,'IV',95))

    def test_seven_throwing_rows_do_not_invent_a_fixed_maximum_or_rock_hands(self):
        rows=(
            (W.ROCK,None,None,R.SHORT,R.MEDIUM),
            (W.THROWING_SPEAR,0,H.ONE_HANDED,R.CLOSE,R.MEDIUM),
            (W.THROWING_AXE,1,H.ONE_HANDED,R.SHORT,R.SHORT),
            (W.WEIGHTED_NET,None,H.TWO_HANDED,R.CLOSE,R.SHORT),
            (W.THROWING_KNIVES,0,H.ONE_HANDED,R.SHORT,R.SHORT),
            (W.OIL_FLASK,None,H.ONE_HANDED,R.SHORT,R.MEDIUM),
            (W.BLASTING_CHARGE,None,H.ONE_HANDED,R.SHORT,R.MEDIUM),
        )
        for kind,offset,hands,low,high in rows:
            with self.subTest(kind=kind):
                profile=weapon_profile(kind)
                self.assertEqual((profile.group,profile.skill,profile.damage_value,profile.hands,
                    profile.optimum_range_min,profile.optimum_range_max),
                    (G.THROWING,Skill.THROWING,offset,hands,low,high))
                self.assertIsNone(profile.maximum_range)
                self.assertEqual((profile.source_book,profile.source_chapter,profile.source_page),
                    (WeaponBook.PLAYER_GUIDE,'IV',96))

    def test_nine_magic_items_retain_their_own_damage_and_actual_source_pages(self):
        rows=(
            (W.DRAGON_BOW,D.FIXED,6,H.TWO_HANDED,None,82),
            (W.DUELLIST_BLADES,D.STRENGTH,2,H.TWO_HANDED,R.CLOSE,83),
            (W.GROTARGGS_HAMMER,D.STRENGTH,3,H.TWO_HANDED,R.CLOSE,83),
            (W.HEADSMANS_AXE,D.STRENGTH,3,H.TWO_HANDED,R.CLOSE,83),
            (W.MORNING_STAR_OF_FRACASSE,D.STRENGTH,3,H.ONE_HANDED,R.CLOSE,83),
            (W.SCARAB_KNIFE,D.STRENGTH,1,H.ONE_HANDED,R.CLOSE,84),
            (W.TRICKSTER_BLADE,D.STRENGTH,1,H.ONE_HANDED,R.CLOSE,84),
            (W.UNWAVERING_SPEAR,D.STRENGTH,1,H.TWO_HANDED,R.SHORT,84),
            (W.SWORD_OF_JUSTICE,D.STRENGTH,1,H.ONE_HANDED,R.CLOSE,84),
        )
        for kind,damage_kind,value,hands,maximum,page in rows:
            with self.subTest(kind=kind):
                profile=weapon_profile(kind)
                self.assertTrue(weapon_is_physical(kind))
                self.assertTrue(weapon_is_magical(kind))
                self.assertEqual((profile.damage_kind,profile.damage_value,profile.hands,profile.maximum_range),
                    (damage_kind,value,hands,maximum))
                self.assertEqual((profile.source_book,profile.source_chapter,profile.source_page),
                    (WeaponBook.GAMEMASTER_GUIDE,'VI',page))
        dragon=weapon_profile(W.DRAGON_BOW)
        self.assertEqual((dragon.optimum_range_min,dragon.optimum_range_max),(R.MEDIUM,R.EXTREME))
        self.assertIn(T.CANNOT_ATTACK_UNSEEN_TARGET,dragon.trait_codes)
        self.assertIn(T.STUCK_RETRIEVAL_BRAWN_MINUS_TWO,weapon_profile(W.GROTARGGS_HAMMER).trait_codes)

    def test_ogre_pistol_has_its_own_optimum_and_is_not_a_magic_weapon(self):
        profile=weapon_profile(W.OGRE_PISTOL)
        self.assertEqual((profile.group,profile.skill,profile.hands,profile.damage_kind,profile.damage_value,
            profile.maximum_range,profile.optimum_range_min,profile.optimum_range_max),
            (G.SHOOTING,Skill.SHOOTING,H.ONE_HANDED,D.FIXED,5,R.LONG,R.CLOSE,R.MEDIUM))
        self.assertEqual((profile.source_book,profile.source_chapter,profile.source_page),
            (WeaponBook.GAMEMASTER_GUIDE,'VII',103))
        self.assertFalse(weapon_is_magical(W.OGRE_PISTOL))
        self.assertIn(T.RELOAD_THREE_SUCCESSES,profile.trait_codes)
        self.assertIn(T.IGNORES_ARMOUR,profile.trait_codes)

    def test_unarmed_is_not_an_inventory_item_and_no_damage_rows_remain_no_damage(self):
        self.assertFalse(weapon_is_physical(W.UNARMED))
        self.assertTrue(weapon_is_physical(W.ROCK))
        self.assertIsNone(weapon_profile(W.UNARMED).hands)
        self.assertIsNone(weapon_profile(W.ROCK).hands)
        self.assertEqual({profile.kind for profile in WEAPON_PROFILES if profile.damage_kind is D.NONE},
            {W.UNARMED,W.ROCK,W.WEIGHTED_NET,W.OIL_FLASK,W.BLASTING_CHARGE})
        for kind in (W.UNARMED,W.ROCK,W.WEIGHTED_NET,W.OIL_FLASK,W.BLASTING_CHARGE):
            self.assertIsNone(weapon_printed_damage(kind))
        self.assertIn(T.NO_DEFENCE,weapon_profile(W.KNUCKLEDUSTERS).trait_codes)

    def test_dual_wield_exclusions_do_not_leak_onto_fracasse(self):
        for profile in WEAPON_PROFILES:
            with self.subTest(kind=profile.kind):
                expected=(profile.group is G.MELEE and profile.hands is H.ONE_HANDED
                    and profile.kind not in (W.MORNING_STAR,W.LANCE))
                self.assertEqual(profile.dual_wield_allowed,expected)
        self.assertTrue(weapon_profile(W.MORNING_STAR_OF_FRACASSE).dual_wield_allowed)
        self.assertEqual((weapon_profile(W.DUELLIST_BLADES).hands,weapon_profile(W.DUELLIST_BLADES).physical),
            (H.TWO_HANDED,True))

    def test_magic_names_do_not_inherit_unprinted_mundane_traits(self):
        self.assertNotIn(T.READY_DEFENCE_PLUS_ONE_DIE,weapon_profile(W.SWORD_OF_JUSTICE).trait_codes)
        self.assertNotIn(T.CONCEALMENT_STEALTH_PLUS_ONE,weapon_profile(W.SCARAB_KNIFE).trait_codes)
        self.assertNotIn(T.ARMOURED_TARGET_DAMAGE_PLUS_ONE,weapon_profile(W.HEADSMANS_AXE).trait_codes)
        self.assertNotIn(T.MELEE_MINUS_ONE,weapon_profile(W.GROTARGGS_HAMMER).trait_codes)
        self.assertIn(T.READY_DEFENCE_PLUS_ONE_DIE,weapon_profile(W.TRICKSTER_BLADE).trait_codes)
        self.assertIn(T.WOUNDS_TABLE_PLUS_ONE_DIE,weapon_profile(W.SWORD_OF_JUSTICE).trait_codes)
        self.assertIn(T.HIT_DRAINED,weapon_profile(W.SCARAB_KNIFE).trait_codes)
        self.assertIn(T.PRONE_GRIM_WOUND_DECAPITATION,weapon_profile(W.HEADSMANS_AXE).trait_codes)

    def test_greatsword_preserves_the_printed_missing_d_without_reinterpreting_the_engine(self):
        profile=weapon_profile(W.GREATSWORD)
        self.assertIn(T.GREATSWORD_PRINTED_READY_DEFENCE_PLUS_ONE,profile.trait_codes)
        self.assertNotIn(T.READY_DEFENCE_PLUS_ONE_DIE,profile.trait_codes)

    def test_printed_damage_helper_only_adds_the_two_printed_variable_grip_bonuses(self):
        self.assertEqual(weapon_printed_damage(W.DAGGER,strength=1),0)
        self.assertEqual(weapon_printed_damage(W.FOOT_SPEAR,strength=4),4)
        self.assertEqual(weapon_printed_damage(W.FOOT_SPEAR,strength=4,two_handed=True),5)
        self.assertEqual(weapon_printed_damage(W.POLEARM,strength=4,two_handed=True),6)
        self.assertEqual(weapon_printed_damage(W.GREATSWORD,strength=4,two_handed=True),7)
        self.assertEqual(weapon_printed_damage(W.MORNING_STAR_OF_FRACASSE,strength=4),7)
        self.assertEqual(weapon_printed_damage(W.SLING,strength=5),5)
        self.assertEqual(weapon_printed_damage(W.PISTOL),5)
        with self.assertRaises(ValueError):weapon_printed_damage(W.SLING)
        with self.assertRaises(ValueError):weapon_printed_damage(W.SWORD,strength=4,two_handed=True)
        with self.assertRaises(TypeError):weapon_printed_damage(W.FOOT_SPEAR,strength=4,two_handed=1)
        for bad_strength in (True,False,0,-1,3.0,'3'):
            with self.subTest(strength=bad_strength),self.assertRaises(ValueError):
                weapon_printed_damage(W.SWORD,strength=bad_strength)

    def test_catalogue_profiles_are_immutable_and_lookup_does_not_coerce_wire_strings(self):
        profile=weapon_profile(W.SWORD)
        self.assertIs(type(profile),WeaponProfile)
        with self.assertRaises(FrozenInstanceError):profile.damage_value=99
        self.assertFalse(hasattr(profile,'__dict__'))
        for invalid in ('sword',None,True,RangedWeaponId.PISTOL):
            with self.subTest(kind=invalid),self.assertRaises(TypeError):weapon_profile(invalid)

    def test_scalar_and_trait_types_are_exact_and_source_metadata_is_required(self):
        profile=weapon_profile(W.SWORD)
        invalid=(dict(kind='sword'),dict(group='melee'),dict(skill='melee'),dict(hands='1h'),
            dict(physical=1),dict(variable_grip=0),dict(magical=0),dict(dual_wield_allowed=1),
            dict(damage_kind='strength'),dict(damage_value=True),dict(maximum_range='close'),
            dict(source_book='player-guide:1.4'),dict(trait_codes=[T.READY_DEFENCE_PLUS_ONE_DIE]),
            dict(trait_codes=('ready_defence_plus_one_die',)),dict(trait_codes=(T.NO_DEFENCE,T.NO_DEFENCE)))
        for change in invalid:
            with self.subTest(change=change),self.assertRaises(TypeError):replace(profile,**change)
        for change in (dict(source_chapter=''),dict(source_page=True),dict(source_page=0),
                dict(physical=False),dict(magical=True),dict(variable_grip=True),dict(dual_wield_allowed=False)):
            with self.subTest(change=change),self.assertRaises(ValueError):replace(profile,**change)


if __name__=='__main__':unittest.main()
