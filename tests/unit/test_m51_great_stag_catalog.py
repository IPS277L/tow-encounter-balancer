"""Two complete natural profiles and the Great Stag's exact W2 band."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.condition_models import Condition
from towr.domain.injury_models import ProfileInjuryState, ProfileNpcType, ProfileStateChangeRequest
from towr.domain.npc_attack_preparation_models import NpcAttackProfile
from towr.domain.pc_npc_catalog import (
    PcBookNpcProfile, PcBookNpcWoundBand, create_pc_book_npc,
    get_pc_book_npc_entry, validate_pc_book_npc_definition,
)
from towr.domain.pc_npc_wound_models import pc_npc_drained_profile_wound_state
from towr.domain.pc_melee_models import validate_pc_melee_scenario_admission
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill


PROFILE = PcBookNpcProfile.GREAT_STAG
SOURCE = 'BOOK-GM-GUIDE:1.1:p176:great_stag'


def scene():
    return book_pc_scenario(great_stags=1, footpads=0, townsfolk=0, pc_count=1)


class GreatStagCatalogTests(unittest.TestCase):
    def test_full_book_identity_and_two_ordered_printed_attacks(self):
        entry = get_pc_book_npc_entry(PROFILE)
        definition = entry.definition
        self.assertEqual((entry.book_id, entry.version, entry.chapter, entry.page),
            ('BOOK-GM-GUIDE', '1.1', 'Allies and Antagonists', 176))
        self.assertEqual((definition.id, definition.source_rule_id, definition.injury_policy,
            definition.wound_limit, definition.resilience),
            ('pc-book-npc:great_stag', SOURCE, TargetInjuryPolicy.BRUTE, 3, ResilienceProfile(5)))
        first, second = definition.attacks
        for attack, name, skill, profile, damage in (
                (first, 'mighty_antlers', Skill.MELEE, InlineProfile(4, 3), 6),
                (second, 'trample', Skill.BRAWN, InlineProfile(5, 3), 5)):
            self.assertEqual((attack.id, attack.source_rule_id, attack.skill, attack.test_profile,
                attack.damage, attack.range_min, attack.range_max, attack.hands,
                attack.ignores_armour, attack.secondary_effects),
                (name, SOURCE+':'+name, skill, profile, DamageProfile(damage),
                 RangedWeaponRange.CLOSE, RangedWeaponRange.CLOSE, None, False, ()))
        self.assertEqual((first.test_profile.maximum_dice, second.test_profile.maximum_dice), (8, 10))
        protection, = definition.protection
        self.assertEqual((protection.source_rule_id, protection.skill, protection.test_profile),
            (SOURCE+':athletics', Skill.ATHLETICS, InlineProfile(5, 4)))
        self.assertEqual(protection.test_profile.maximum_dice, 10)
        validate_pc_book_npc_definition(definition)

    def test_fresh_snapshot_retains_both_attacks_without_weapon_or_shield(self):
        first = create_pc_book_npc(PROFILE, 'stag1')
        second = create_pc_book_npc(PROFILE, 'stag2')
        self.assertEqual((first.state.available_attack_ids, first.state.wields_weapon,
            first.state.holds_shield, first.state.current_resilience,
            first.state.injury.wounds, first.state.injury.wound_limit),
            (('mighty_antlers', 'trample'), False, False, ResilienceProfile(5), 0, 3))
        self.assertIsNot(first.definition, second.definition)
        self.assertIsNot(first.definition.attacks[1].test_profile, second.definition.attacks[1].test_profile)
        self.assertIsNot(first.state.injury, second.state.injury)
        object.__setattr__(first.definition.attacks[1].damage, 'base', 99)
        self.assertEqual(second.definition, get_pc_book_npc_entry(PROFILE).definition)

    def test_wound_bands_and_unselected_charge_rider_triggers_are_complete(self):
        entry = get_pc_book_npc_entry(PROFILE)
        self.assertEqual(entry.wound_bands, (PcBookNpcWoundBand(0, 'No effect'),
            PcBookNpcWoundBand(1, 'No effect'), PcBookNpcWoundBand(2, 'Drained'),
            PcBookNpcWoundBand(3, 'Defeated')))
        inactive = {ability.name:ability for ability in entry.inactive_abilities}
        self.assertEqual(set(inactive), {'Mighty Antlers on Charge', 'Fearsome',
            'Crown of Antlers (Give Ground)', 'Great Stag Knights'})
        self.assertIn('Charge', inactive['Mighty Antlers on Charge'].scope)
        self.assertIn('Give Ground', inactive['Crown of Antlers (Give Ground)'].scope)
        self.assertIn('mounted', inactive['Great Stag Knights'].scope)
        self.assertFalse(entry.unselected_attack_names)
        active = {ability.name:ability for ability in entry.active_abilities}
        self.assertIn('Trample', active)
        self.assertIn('same living Prone', active['Crown of Antlers (Trample)'].effect)
        self.assertFalse(entry.definition.attacks[0].secondary_effects)

    def test_only_actual_one_to_two_wound_ack_adds_drained(self):
        definition = get_pc_book_npc_entry(PROFILE).definition
        first = ProfileInjuryState(1, 3)
        first_change = ProfileStateChangeRequest(ProfileNpcType.BRUTE, 0, 1, False)
        self.assertIs(pc_npc_drained_profile_wound_state(definition, first, first_change), first)
        second = ProfileInjuryState(2, 3)
        second_change = ProfileStateChangeRequest(ProfileNpcType.BRUTE, 1, 2, False)
        actual = pc_npc_drained_profile_wound_state(definition, second, second_change)
        self.assertTrue(actual.conditions.has(Condition.DRAINED))
        self.assertEqual(actual.wounds, 2)
        with self.assertRaises(ValueError):
            pc_npc_drained_profile_wound_state(definition, first, second_change)
        defeated = replace(actual, wounds=3, defeated=True)
        third_change = ProfileStateChangeRequest(ProfileNpcType.BRUTE, 2, 3, True)
        self.assertIs(pc_npc_drained_profile_wound_state(definition, defeated, third_change), defeated)

    def test_secondary_cannot_be_missing_reordered_or_changed_to_melee_or_cap8(self):
        definition = get_pc_book_npc_entry(PROFILE).definition
        first, second = definition.attacks
        candidates = ((first,), (second, first),
            (first, replace(second, skill=Skill.MELEE)),
            (first, replace(second, test_profile=InlineProfile(5, 3, 8))),
            (first, replace(second, damage=DamageProfile(6))))
        for attacks in candidates:
            with self.subTest(attacks=attacks), self.assertRaises((ValueError, TypeError)):
                validate_pc_book_npc_definition(replace(definition, attacks=attacks))
        source = scene()
        enemy = source.enemies[0]
        with self.assertRaises(ValueError):
            replace(source, enemies=(replace(enemy, state=replace(enemy.state,
                available_attack_ids=('mighty_antlers',))),))

    def test_extra_actor_policy_admits_canonical_stag_and_keeps_exact_types(self):
        source = replace(scene(), npc_extra_attack_actor_ids=('great_stag1',))
        validate_pc_melee_scenario_admission(source)
        self.assertEqual(source.npc_extra_attack_actor_ids, ('great_stag1',))
        for field, value in (('skill', 'brawn'), ('range_max', 'close')):
            forged = deepcopy(source)
            object.__setattr__(forged.enemies[0].definition.attacks[1], field, value)
            self.assertEqual(forged, source)
            with self.subTest(field=field), self.assertRaises(TypeError):
                validate_pc_melee_scenario_admission(forged)
        forged = deepcopy(source)
        object.__setattr__(forged.enemies[0].definition.attacks[1].test_profile, 'dice', 5.0)
        with self.assertRaises(TypeError):
            validate_pc_melee_scenario_admission(forged)

    def test_other_sources_cannot_borrow_two_profiles_or_brawn(self):
        source = make_pc_melee_scenario()
        enemy = source.enemies[0]
        primary = enemy.definition.attacks[0]
        brawn = NpcAttackProfile('trample', 'authored:trample', Skill.BRAWN, InlineProfile(5, 3),
            DamageProfile(5), RangedWeaponRange.CLOSE, RangedWeaponRange.CLOSE, None)
        for attacks, armed in (((primary, brawn), True), ((brawn,), False)):
            definition = replace(enemy.definition, attacks=attacks)
            state = replace(enemy.state, available_attack_ids=tuple(p.id for p in attacks), wields_weapon=armed)
            with self.subTest(attacks=attacks), self.assertRaises((ValueError, TypeError)):
                replace(source, enemies=(replace(enemy, definition=definition, state=state),))

    def test_reserved_secondary_identity_survives_root_and_primary_renames(self):
        definition = get_pc_book_npc_entry(PROFILE).definition
        first, second = definition.attacks
        changed = replace(definition, id='authored:root', source_rule_id='authored:source',
            attacks=(replace(first, source_rule_id='authored:primary'), second),
            protection=(replace(definition.protection[0], source_rule_id='authored:protection'),))
        with self.assertRaises(ValueError):
            validate_pc_book_npc_definition(changed)


if __name__ == '__main__':
    unittest.main()
