"""GM138's alternative Bear loadout and its closed pre-Stagger source."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.domain.attack_models import DamageProfile, ProneBeforeGiveGroundSpec, ResilienceProfile
from towr.domain.pc_melee_models import validate_pc_melee_scenario_admission
from towr.domain.pc_npc_catalog import (
    PcBookNpcProfile, create_pc_book_npc, get_pc_book_npc_entry, validate_pc_book_npc_definition,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill


PROFILE = PcBookNpcProfile.BEAR_CRUSHING_WEIGHT
SOURCE = 'BOOK-GM-GUIDE:1.1:p138:bear_crushing_weight'
RULE = 'RULE-PROFILE-CREATURE-010:crushing-weight-prone'


class PcCrushingWeightCatalogTests(unittest.TestCase):
    def test_full_printed_attack_keeps_three_dice_cap_eight_natural_and_damage_seven(self):
        entry = get_pc_book_npc_entry(PROFILE)
        definition = entry.definition
        self.assertEqual((entry.book_id, entry.version, entry.chapter, entry.page),
            ('BOOK-GM-GUIDE', '1.1', 'Allies and Antagonists', 138))
        self.assertEqual((definition.id, definition.source_rule_id, definition.injury_policy,
            definition.wound_limit, definition.resilience),
            ('pc-book-npc:bear_crushing_weight', SOURCE, TargetInjuryPolicy.BRUTE, 3, ResilienceProfile(5, 1)))
        attack, = definition.attacks
        self.assertEqual((attack.id, attack.source_rule_id, attack.skill, attack.test_profile,
            attack.damage, attack.range_min, attack.range_max, attack.hands,
            attack.ignores_armour, attack.secondary_effects),
            ('crushing_weight', SOURCE+':crushing_weight', Skill.MELEE, InlineProfile(3, 3, 8),
             DamageProfile(7), RangedWeaponRange.CLOSE, RangedWeaponRange.CLOSE, None, False,
             (ProneBeforeGiveGroundSpec(RULE, True),)))
        protection, = definition.protection
        self.assertEqual((protection.source_rule_id, protection.skill, protection.test_profile),
            (SOURCE+':athletics', Skill.ATHLETICS, InlineProfile(3, 3)))

    def test_wound_bands_and_both_abilities_keep_their_full_triggers(self):
        entry = get_pc_book_npc_entry(PROFILE)
        self.assertEqual(tuple(b.wounds for b in entry.wound_bands), (0, 1, 2, 3))
        self.assertIn('Drained', entry.wound_bands[1].effect)
        self.assertIn('Drained', entry.wound_bands[2].effect)
        self.assertEqual(entry.wound_bands[-1].effect, 'Defeated')
        abilities = {a.name:a for a in (*entry.active_abilities, *entry.inactive_abilities)}
        self.assertIn('Enduring Strength', abilities)
        self.assertIn('different', abilities['Enduring Strength'].effect)
        self.assertIn('Fearsome', abilities)
        self.assertIn('Give', abilities['Fearsome'].scope)
        self.assertEqual(entry.unselected_attack_names, ('Sweeping Claws',))
        old = get_pc_book_npc_entry(PcBookNpcProfile.BEAR_SWEEPING_CLAWS)
        self.assertEqual(old.definition.attacks[0].test_profile, InlineProfile(4, 3))
        self.assertEqual(old.definition.attacks[0].secondary_effects, ())
        self.assertEqual(old.unselected_attack_names, ('Crushing Weight',))

    def test_factory_is_healthy_unarmed_unshielded_and_does_not_share_nested_graphs(self):
        first = create_pc_book_npc(PROFILE, 'first')
        second = create_pc_book_npc(PROFILE, 'second')
        self.assertEqual((first.state.wields_weapon, first.state.holds_shield,
            first.state.available_attack_ids, first.state.injury.wounds, first.state.injury.wound_limit),
            (False, False, ('crushing_weight',), 0, 3))
        self.assertIsNot(first.definition.attacks[0].test_profile, second.definition.attacks[0].test_profile)
        object.__setattr__(first.definition.attacks[0].secondary_effects[0], 'affects_monstrosities', False)
        self.assertEqual(second.definition, get_pc_book_npc_entry(PROFILE).definition)

    def test_cap_and_effect_cannot_be_changed_or_dropped_under_the_book_identity(self):
        definition = get_pc_book_npc_entry(PROFILE).definition
        attack, = definition.attacks
        for profile in (InlineProfile(3, 3), InlineProfile(3, 3, 6), InlineProfile(2, 3, 8), InlineProfile(4, 3, 8)):
            with self.subTest(profile=profile), self.assertRaises((TypeError, ValueError)):
                validate_pc_book_npc_definition(replace(definition, attacks=(replace(attack, test_profile=profile),)))
        for effects in ((), (ProneBeforeGiveGroundSpec(RULE, False),),
                (ProneBeforeGiveGroundSpec('authored:prone', True),)):
            with self.subTest(effects=effects), self.assertRaises((TypeError, ValueError)):
                validate_pc_book_npc_definition(replace(definition, attacks=(replace(attack, secondary_effects=effects),)))

    def test_authored_and_other_book_sources_cannot_borrow_pre_stagger_prone(self):
        sources = (make_pc_melee_scenario(), book_pc_scenario(bears=1, footpads=0, townsfolk=0, pc_count=1))
        for source in sources:
            enemy = source.enemies[0]
            attack, = enemy.definition.attacks
            altered = replace(enemy.definition, attacks=(replace(attack,
                secondary_effects=(ProneBeforeGiveGroundSpec(RULE, True),)),))
            with self.subTest(definition=altered.id), self.assertRaises((TypeError, ValueError)):
                replace(source, enemies=(replace(enemy, definition=altered),))

    def test_partial_identity_and_equal_cached_types_do_not_bypass_admission(self):
        definition = get_pc_book_npc_entry(PROFILE).definition
        for altered in (replace(definition, id='authored:bear'), replace(definition, source_rule_id='authored:bear')):
            with self.assertRaises((TypeError, ValueError)):
                validate_pc_book_npc_definition(altered)
        for field, value in (('pool_cap', 8.0), ('dice', 3.0)):
            altered = deepcopy(definition)
            object.__setattr__(altered.attacks[0].test_profile, field, value)
            self.assertEqual(altered, definition)
            with self.assertRaises(TypeError):
                validate_pc_book_npc_definition(altered)
        altered = deepcopy(definition)
        object.__setattr__(altered.attacks[0].secondary_effects[0], 'affects_monstrosities', 1)
        self.assertEqual(altered, definition)
        with self.assertRaises(TypeError):
            validate_pc_book_npc_definition(altered)

    def test_existing_extra_attack_list_admits_both_bears_but_not_other_creatures(self):
        source = book_pc_scenario(crushing_bears=1, bears=1, footpads=0, townsfolk=0)
        source = replace(source, npc_extra_attack_actor_ids=('crushing_bear1', 'bear1'))
        validate_pc_melee_scenario_admission(source)
        self.assertEqual(source.npc_extra_attack_actor_ids, ('crushing_bear1', 'bear1'))
        other = book_pc_scenario(ogres=1, footpads=0, townsfolk=0)
        with self.assertRaises(ValueError):
            replace(other, npc_extra_attack_actor_ids=('ogre1',))


if __name__ == '__main__':
    unittest.main()
