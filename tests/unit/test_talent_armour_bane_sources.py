"""PG73 item qualification and accepted C5 ward interaction."""
from copy import deepcopy
from dataclasses import replace
import pickle
import unittest

from tests.support.talent_sources import paid_talent
from towr.domain.attack_models import ResilienceProfile
from towr.domain.ranged_weapon_profiles import RangedWeaponHands
from towr.domain.talent_armour_bane_models import (
    ArmourBaneApplication,armour_bane_weapon_sources,armour_bane_eligible_sources,lower_armour_bane_resilience,
)
from towr.domain.talent_catalog import TalentId
from towr.domain.weapon_catalog import WeaponKind as W,WEAPON_PROFILES,weapon_profile
from towr.domain.weapon_inventory_models import (
    WeaponGrip as G,WeaponItemLocation as L,WeaponItemSource,
    initial_weapon_inventory,weapon_reload_target,
)
from towr.domain.weapon_use_models import WeaponUse


QUALIFYING=frozenset((W.AXE,W.HALBERD,W.GREATAXE,W.CROSSBOW,W.THROWING_AXE,
    W.PISTOL,W.HANDGUN,W.HOCHLAND_LONG_RIFLE,W.REPEATER_PISTOL,W.REPEATER_HANDGUN,W.OGRE_PISTOL))


def item(identifier,kind,grip=None,*,carried=False):
    if grip is None and not carried:
        grip=G.BOTH if weapon_profile(kind).hands is RangedWeaponHands.TWO_HANDED else G.LEFT
    return WeaponItemSource(identifier,kind,L.CARRIED if carried else L.HELD,
        None if carried else grip,
        initially_loaded=True if weapon_reload_target(kind) is not None else None,
        gm_fit_confirmed=True if kind is W.OGRE_PISTOL else None)


def use(*items,contributors=()):
    inventory=initial_weapon_inventory('actor',items)
    identifiers={unit.source.id:unit.id for unit in inventory.items}
    return WeaponUse('actor',inventory,identifiers[items[0].id],
        tuple(identifiers[identifier] for identifier in contributors))


class ArmourBaneSourceTests(unittest.TestCase):
    def test_all_physical_book_profiles_have_exactly_eleven_intrinsic_qualifiers(self):
        found=set()
        for profile in WEAPON_PROFILES:
            if not profile.physical:
                continue
            with self.subTest(weapon=profile.kind):
                actual=use(item('actual',profile.kind))
                sources=armour_bane_weapon_sources(actual)
                if profile.kind in QUALIFYING:
                    self.assertEqual(len(sources),1)
                    self.assertEqual((sources[0].item_id,sources[0].kind),(actual.primary_item_id,profile.kind))
                    found.add(profile.kind)
                else:
                    self.assertEqual(sources,())
        self.assertEqual(found,QUALIFYING)

    def test_carried_weapons_and_names_do_not_contribute_a_trait(self):
        for primary in (W.PICKAXE,W.POLEARM,W.HEADSMANS_AXE,W.SWORD,W.BLUNDERBUSS,W.REPEATER_CROSSBOW):
            actual=use(item('held',primary),item('carried',W.AXE,carried=True))
            self.assertEqual(armour_bane_weapon_sources(actual),())

    def test_dual_wield_retains_both_actual_sources_but_lowers_only_one_point(self):
        actual=use(item('left',W.AXE,G.LEFT),item('right',W.AXE,G.RIGHT),contributors=('right',))
        sources=armour_bane_weapon_sources(actual)
        effect=ArmourBaneApplication('attack','actor','target',paid_talent(TalentId.ARMOUR_BANE),
            actual,sources,ResilienceProfile(3,3))
        self.assertEqual(tuple(source.item_id for source in effect.sources),actual.item_ids)
        self.assertEqual(effect.reduction,1)
        self.assertEqual(effect.after.total,5)
        self.assertEqual(effect.before.total,6)
        self.assertEqual(pickle.loads(pickle.dumps(effect)),effect)

    def test_a_magical_primary_does_not_reclassify_an_ordinary_offhand_axe(self):
        actual=use(item('magic',W.TRICKSTER_BLADE,G.LEFT),item('axe',W.AXE,G.RIGHT),contributors=('axe',))
        source,=armour_bane_weapon_sources(actual)
        self.assertTrue(actual.primary_profile.magical)
        self.assertEqual(source.item_id,actual.contributor_item_ids[0])
        self.assertFalse(source.magical)

    def test_bounded_operator_keeps_toughness_ward_and_actual_before_source(self):
        for bonus in (0,1,2,7):
            before=ResilienceProfile(4,bonus,armoured=True,mundane_armour_ward=True)
            saved=deepcopy(before)
            after=lower_armour_bane_resilience(before)
            self.assertEqual(after.toughness,4)
            self.assertEqual(after.total,4+max(0,bonus-1))
            self.assertEqual(after.is_armoured,bonus>1)
            self.assertTrue(after.mundane_armour_ward)
            self.assertEqual(before,saved)

    def test_meteoric_ward_cancels_each_ordinary_qualifier_including_magic_primary_offhand(self):
        ward=ResilienceProfile(3,3,mundane_armour_ward=True)
        for kind in QUALIFYING:
            with self.subTest(kind=kind):
                actual=use(item('weapon',kind))
                self.assertEqual(armour_bane_eligible_sources(actual,ward),())
                self.assertEqual(armour_bane_eligible_sources(actual,replace(ward,mundane_armour_ward=False)),
                    armour_bane_weapon_sources(actual))
                with self.assertRaises(ValueError):
                    ArmourBaneApplication('attack','actor','target',paid_talent(TalentId.ARMOUR_BANE),
                        actual,armour_bane_weapon_sources(actual),ward)
        actual=use(item('magic',W.TRICKSTER_BLADE,G.LEFT),item('axe',W.AXE,G.RIGHT),contributors=('axe',))
        self.assertEqual(armour_bane_eligible_sources(actual,ward),())

    def test_an_already_unarmoured_floor_cannot_create_a_fictitious_application(self):
        actual=use(item('axe',W.AXE))
        with self.assertRaises(ValueError):
            ArmourBaneApplication('attack','actor','target',paid_talent(TalentId.ARMOUR_BANE),
                actual,armour_bane_weapon_sources(actual),ResilienceProfile(3))

    def test_foreign_duplicate_untyped_and_forged_item_sources_are_not_repaired(self):
        actual=use(item('left',W.AXE,G.LEFT),item('right',W.AXE,G.RIGHT),contributors=('right',))
        sources=armour_bane_weapon_sources(actual)
        effect=ArmourBaneApplication('attack','actor','target',paid_talent(TalentId.ARMOUR_BANE),
            actual,sources,ResilienceProfile(4,2))
        for bad in ((),sources[:1],sources*2,sources[::-1],list(sources)):
            with self.subTest(bad=bad),self.assertRaises((TypeError,ValueError)):
                replace(effect,sources=bad)
        for changes in (dict(actor_id='other'),dict(target_id='actor'),
                dict(talent=paid_talent(TalentId.HARDY))):
            with self.subTest(changes=changes),self.assertRaises((TypeError,ValueError)):
                replace(effect,**changes)
        bad=deepcopy(sources[0])
        object.__setattr__(bad,'magical',True)
        with self.assertRaises(ValueError):
            replace(effect,sources=(bad,sources[1]))
        object.__setattr__(bad,'magical',1)
        with self.assertRaises(TypeError):
            replace(effect,sources=(bad,sources[1]))


if __name__=='__main__':
    unittest.main()
