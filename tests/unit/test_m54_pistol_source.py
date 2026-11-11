"""Strict complete Pistol sources, lawful opposition and nested re-admission."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from enum import Enum
import pickle
import unittest
from unittest.mock import patch

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_pistol_scenarios import make_pc_pistol_scenario, pistol_profile
from tests.support.pc_shield_scenarios import shield_loadout
from towr.domain.pc_melee_models import (
    PcAllyRecoverPolicy, PcBackupWeaponPolicy, PcFatePolicy, PcGloriousPolicy,
    PcHelpPolicy, PcHelpTarget, PcMeleeDefinition, PcMeleePolicy, PcMeleeWeapon,
    PcRangedProfile, PcRangedReloadHandPolicy, PcTwoHandedGrip, PcWeaponHand,
    validate_pc_melee_scenario_admission,
)
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc
from towr.domain.test_models import Skill, TestProfile
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


class PistolSourceTests(unittest.TestCase):
    def test_profile_uses_actual_bs_and_initiative_and_is_immutable(self):
        profile = pistol_profile(ballistic_skill=2, shooting=7, initiative=5, dexterity=6)
        self.assertEqual(profile.shooting_profile, TestProfile(2, 7))
        self.assertEqual(profile.dexterity_profile, TestProfile(5, 6))
        self.assertEqual(profile.shooting_profile.maximum_dice, 4)
        self.assertEqual(profile.dexterity_profile.maximum_dice, 10)
        self.assertEqual(pickle.loads(pickle.dumps(profile)), profile)
        with self.assertRaises(FrozenInstanceError):
            profile.shooting = 9

    def test_source_is_conditional_optional_keyword_only_without_inferred_profiles(self):
        field = next(item for item in fields(PcMeleeDefinition) if item.name == 'ranged')
        self.assertTrue(field.kw_only)
        self.assertIsNone(field.default)
        ordinary = make_pc_melee_scenario().party[0].pc
        self.assertIsNone(ordinary.ranged)
        with self.assertRaises(TypeError):
            replace(ordinary, weapon=PcMeleeWeapon.PISTOL)
        with self.assertRaises(ValueError):
            replace(ordinary, ranged=pistol_profile())
        source = make_pc_pistol_scenario(ballistic_skill=2, initiative=5)
        self.assertEqual(source.party[0].pc.weapon_skill, 3)
        self.assertEqual(source.party[0].pc.agility, 3)
        self.assertEqual(source.party[0].pc.ranged.shooting_profile, TestProfile(2, 4))
        self.assertEqual(source.party[0].pc.ranged.dexterity_profile, TestProfile(5, 4))

    def test_profile_rejects_inexact_scalars_false_facts_and_foreign_enums(self):
        class Number(int):
            pass
        class Alias(str, Enum):
            HANDS = 'two_available_hands'
        profile = pistol_profile()
        for name in ('ballistic_skill', 'shooting', 'initiative', 'dexterity'):
            for invalid in (True, 3.0, '3', None, Number(3), 0, -1):
                with self.subTest(name=name, invalid=invalid), self.assertRaises((TypeError, ValueError)):
                    replace(make_pc_pistol_scenario().party[0].pc, ranged=replace(profile, **{name: invalid}))
        for name in ('shooting', 'dexterity'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                replace(profile, **{name: 11})
        for name in ('has_blackpowder_lore', 'has_blackpowder_kit',
                'ammunition_supply_confirmed', 'initially_loaded'):
            for invalid in (False, 1, 'true', None):
                with self.subTest(name=name, invalid=invalid), self.assertRaises((TypeError, ValueError)):
                    replace(make_pc_pistol_scenario().party[0].pc, ranged=replace(profile, **{name: invalid}))
        for invalid in ('two_available_hands', Alias.HANDS, True, None):
            with self.subTest(invalid=invalid), self.assertRaises(TypeError):
                replace(profile, reload_hand_policy=invalid)
        self.assertIs(profile.reload_hand_policy, PcRangedReloadHandPolicy.TWO_AVAILABLE_HANDS)

    def test_same_hand_shield_overcarry_backup_help_and_two_handed_grip_are_prohibited(self):
        member = make_pc_pistol_scenario().party[0]
        changes = ({'shield': shield_loadout(PcWeaponHand.LEFT)},
            {'pc': replace(member.pc,strength=1),
                'backup_weapon_policy': PcBackupWeaponPolicy(PcMeleeWeapon.SWORD, PcWeaponHand.RIGHT)},
            {'initial_weapon_hand': PcTwoHandedGrip.BOTH},
            {'policy': PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
                'help_policy': PcHelpPolicy('ally', PcHelpTarget.MELEE_ATTACK, None)},
            {'policy': PcMeleePolicy.RECOVER_ALLY_OR_ATTACK_OR_RECOVER_SELF,
                'ally_recover_policy': PcAllyRecoverPolicy('ally')})
        for change in changes:
            with self.subTest(change=change), self.assertRaises((TypeError, ValueError)):
                replace(member, **change)
        with self.assertRaises(ValueError):
            PcBackupWeaponPolicy(PcMeleeWeapon.PISTOL, PcWeaponHand.RIGHT)

    def test_full_party_can_mix_pistol_and_melee_shield_with_glorious_skills(self):
        source = make_pc_pistol_scenario(pc_count=2)
        first, second = source.party
        second = replace(second, pc=replace(second.pc, weapon=PcMeleeWeapon.SWORD, ranged=None),
            shield=shield_loadout(PcWeaponHand.RIGHT))
        first = replace(first, fate_policy=PcFatePolicy.CONFIGURED,
            glorious_policy=PcGloriousPolicy((Skill.SHOOTING, Skill.DEXTERITY), 1, 0))
        validate_pc_melee_scenario_admission(replace(source, party=(first, second)))

    def test_all_future_targets_require_lawful_chosen_shooting_protection(self):
        source = make_pc_pistol_scenario(enemy_count=2)
        for profile, admitted in ((PcBookNpcProfile.FOOTPAD, True),
                (PcBookNpcProfile.GOBLIN_WARRIOR_SPEAR, True),
                (PcBookNpcProfile.EMPIRE_STATE_TROOPER_HALBERD, False),
                (PcBookNpcProfile.HALFLING_THIEF_DAGGER, True)):
            enemy = create_pc_book_npc(profile, 'minion2')
            if admitted:
                validate_pc_melee_scenario_admission(replace(source, enemies=(source.enemies[0], enemy)))
            else:
                with self.subTest(profile=profile), self.assertRaisesRegex(ValueError, 'ranged opponents'):
                    replace(source, enemies=(source.enemies[0], enemy))
        self.assertEqual(len(PcBookNpcProfile), 59)

    def test_nested_forgery_rejected_before_rng_factory(self):
        request = PcMeleeSimulationRequest(make_pc_pistol_scenario(), 42, 1)
        changes = (('ballistic_skill', True), ('shooting', 11), ('initiative', 0),
            ('has_blackpowder_kit', False), ('initially_loaded', False),
            ('reload_hand_policy', 'two_available_hands'))
        for name, value in changes:
            forged = deepcopy(request)
            object.__setattr__(forged.scenario.party[0].pc.ranged, name, value)
            with patch('towr.simulation.pc_melee_simulation.Random') as rng:
                with self.subTest(name=name), self.assertRaises((TypeError, ValueError)):
                    run_pc_melee_trial(forged, 0, rng_factory=rng)
                rng.assert_not_called()

    def test_unshielded_defence_forgery_rejected_before_rng(self):
        source = make_pc_pistol_scenario(enemy_count=2)
        forged = deepcopy(PcMeleeSimulationRequest(source, 42, 1))
        for enemy in forged.scenario.enemies:
            object.__setattr__(enemy.definition.protection[0], 'skill', Skill.DEFENCE)
        with patch('towr.simulation.pc_melee_simulation.Random') as rng:
            with self.assertRaisesRegex(ValueError, 'ranged opponents'):
                run_pc_melee_trial(forged, 0, rng_factory=rng)
            rng.assert_not_called()
