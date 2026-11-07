"""Strict, immutable shield source admission without execution or RNG."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from enum import Enum
import pickle
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_shield_scenarios import make_pc_shield_scenario, shield_loadout
from towr.domain.pc_melee_models import (
    PcBackupWeaponPolicy, PcMeleeParticipant, PcMeleeWeapon, PcShieldHandConflictPolicy,
    PcShieldLoadout, PcShieldRecoveryPolicy, PcTwoHandedGrip, PcWeaponHand,
    validate_pc_melee_scenario_admission,
)


class ShieldSourceTests(unittest.TestCase):
    def test_all_six_one_handed_loadouts_admit_both_opposite_hands(self):
        for weapon in (PcMeleeWeapon.DAGGER, PcMeleeWeapon.STAFF, PcMeleeWeapon.AXE,
                PcMeleeWeapon.SWORD, PcMeleeWeapon.WARHAMMER, PcMeleeWeapon.MORNING_STAR):
            for hand in PcWeaponHand:
                source = make_pc_shield_scenario(weapon=weapon, weapon_hand=hand, armour_bonus=2)
                validate_pc_melee_scenario_admission(source)
                self.assertIsNot(source.party[0].shield.initial_hand, hand)
                self.assertEqual(source.party[0].pc.armour_bonus, 2)
                self.assertEqual(source.party[0].pc.resilience.bonus, 2)

    def test_absence_is_optional_keyword_only_and_items_are_immutable_pickleable(self):
        source = make_pc_melee_scenario()
        self.assertIsNone(source.party[0].shield)
        field = next(item for item in fields(PcMeleeParticipant) if item.name == 'shield')
        self.assertTrue(field.kw_only)
        self.assertIsNone(field.default)
        value = shield_loadout()
        self.assertEqual(pickle.loads(pickle.dumps(value)), value)
        with self.assertRaises(FrozenInstanceError):
            value.initial_hand = PcWeaponHand.RIGHT

    def test_exact_enums_and_loadout_type_are_required(self):
        class Alias(str, Enum):
            LEFT = 'left'
            WEAPON_FIRST = 'weapon_first'
            RESTORE = 'restore_before_attack'
        valid = shield_loadout()
        for name, values in (
                ('initial_hand', ('left', Alias.LEFT, None, True, PcTwoHandedGrip.BOTH)),
                ('hand_conflict_policy', ('weapon_first', Alias.WEAPON_FIRST, None, True)),
                ('recovery_policy', ('restore_before_attack', Alias.RESTORE, None, True))):
            for value in values:
                with self.subTest(field=name, value=value), self.assertRaises(TypeError):
                    replace(valid, **{name: value})
        member = make_pc_melee_scenario().party[0]
        for value in ({}, True, 'shield', PcWeaponHand.RIGHT):
            with self.subTest(value=value), self.assertRaises(TypeError):
                replace(member, shield=value)

    def test_same_hand_two_handed_primary_and_backup_are_rejected(self):
        member = make_pc_shield_scenario().party[0]
        with self.assertRaises(ValueError):
            replace(member, shield=shield_loadout(member.initial_weapon_hand))
        for weapon in (PcMeleeWeapon.PICKAXE, PcMeleeWeapon.FLAIL, PcMeleeWeapon.BILLHOOK,
                PcMeleeWeapon.HALBERD, PcMeleeWeapon.GLAIVE, PcMeleeWeapon.GREATAXE,
                PcMeleeWeapon.GREATHAMMER):
            source = make_pc_melee_scenario(weapon=weapon)
            with self.subTest(weapon=weapon), self.assertRaises(ValueError):
                replace(source.party[0], shield=shield_loadout())
        with self.assertRaises(ValueError):
            replace(member, backup_weapon_policy=PcBackupWeaponPolicy(PcMeleeWeapon.DAGGER, PcWeaponHand.LEFT))

    def test_nested_forgery_is_readmitted_before_execution(self):
        original = make_pc_shield_scenario()
        for field, value in (('initial_hand', 'left'),
                ('hand_conflict_policy', 'weapon_first'), ('recovery_policy', 'restore_before_attack'),
                ('initial_hand', PcWeaponHand.RIGHT)):
            source = deepcopy(original)
            object.__setattr__(source.party[0].shield, field, value)
            with self.subTest(field=field, value=value), self.assertRaises((TypeError, ValueError)):
                validate_pc_melee_scenario_admission(source)

    def test_authored_identifiers_still_require_exact_nonempty_strings(self):
        member = make_pc_shield_scenario().party[0]
        for invalid in ('', ' ', None, True, 1):
            with self.subTest(value=invalid), self.assertRaises((TypeError, ValueError)):
                replace(member, actor_id=invalid)
