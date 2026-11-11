"""Complete GM144 Bestigor card data; runtime choices belong to the PC owner."""
from copy import deepcopy
from dataclasses import replace
import unittest

from towr.domain.attack_models import DamageProfile,ResilienceProfile
from towr.domain.pc_npc_catalog import (
    PcBookNpcProfile,PcBookNpcWoundBand,create_pc_book_npc,get_pc_book_npc_entry,
    validate_pc_book_npc_definition,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands,RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile,Skill


PROFILE=PcBookNpcProfile.BESTIGOR_MASSIVE_AXE
SOURCE='BOOK-GM-GUIDE:1.1:p144:bestigor_massive_axe'


class PcBestigorCatalogTests(unittest.TestCase):
    def test_exact_massive_axe_damage_armour_and_source(self):
        entry=get_pc_book_npc_entry(PROFILE)
        definition=entry.definition
        self.assertEqual((entry.profile_id,entry.book_id,entry.version,entry.chapter,entry.page),
            (PROFILE,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',144))
        self.assertEqual((definition.id,definition.source_rule_id,definition.injury_policy,
            definition.wound_limit,definition.resilience),
            ('pc-book-npc:bestigor_massive_axe',SOURCE,TargetInjuryPolicy.BRUTE,2,ResilienceProfile(4,2)))
        attack,=definition.attacks
        self.assertEqual((attack.id,attack.source_rule_id,attack.skill,attack.test_profile,
            attack.damage,attack.range_min,attack.range_max,attack.hands,
            attack.ignores_armour,attack.secondary_effects),
            ('massive_axe',SOURCE+':massive_axe',Skill.MELEE,InlineProfile(3,4,8),
             DamageProfile(7),RangedWeaponRange.CLOSE,RangedWeaponRange.CLOSE,
             RangedWeaponHands.TWO_HANDED,False,()))
        validate_pc_book_npc_definition(definition)

    def test_printed_defence_and_alternate_athletics_keep_distinct_caps(self):
        entry=get_pc_book_npc_entry(PROFILE)
        protection,=entry.definition.protection
        alternative,=entry.unselected_protection
        self.assertEqual((protection.source_rule_id,protection.skill,protection.test_profile),
            (SOURCE+':defence',Skill.DEFENCE,InlineProfile(4,3)))
        self.assertEqual((alternative.source_rule_id,alternative.skill,alternative.test_profile),
            (SOURCE+':athletics',Skill.ATHLETICS,InlineProfile(3,3,8)))
        self.assertEqual((entry.definition.attacks[0].test_profile.maximum_dice,
            protection.test_profile.maximum_dice,alternative.test_profile.maximum_dice),(8,8,8))
        self.assertIsNone(protection.test_profile.pool_cap)
        self.assertEqual(alternative.test_profile.pool_cap,8)

    def test_fresh_bestigor_has_no_shield_or_automatic_staggered(self):
        snapshot=create_pc_book_npc(PROFILE,'bestigor')
        self.assertEqual((snapshot.state.actor_id,snapshot.state.definition_id,
            snapshot.state.wields_weapon,snapshot.state.holds_shield,
            snapshot.state.available_attack_ids,snapshot.state.current_resilience),
            ('bestigor','pc-book-npc:bestigor_massive_axe',True,False,('massive_axe',),ResilienceProfile(4,2)))
        self.assertEqual((snapshot.state.injury.wounds,snapshot.state.injury.wound_limit,
            snapshot.state.injury.defeated,snapshot.state.injury.defeat_cause),(0,2,False,None))
        self.assertFalse(snapshot.state.injury.conditions.conditions)

    def test_full_rage_and_forest_ability_conditions_are_preserved(self):
        entry=get_pc_book_npc_entry(PROFILE)
        forest,=entry.inactive_abilities
        rage,=entry.active_abilities
        self.assertEqual((forest.name,forest.scope,forest.effect),('Child of the Forest',
            'Movement through woodland Difficult Terrain','Ignore the effects of woodland Difficult Terrain'))
        self.assertEqual(rage.name,'Blood Rage')
        self.assertIn('makes an attack',rage.scope)
        self.assertIn('May choose to gain Staggered if not already Staggered',rage.effect)
        self.assertIn('Staggered Bestigors gain +1d to Melee attacks',rage.effect)
        self.assertEqual(entry.unselected_attack_names,())
        self.assertEqual(entry.unselected_variant_names,())

    def test_wound_bands_preserve_choice_restriction_next_attack_and_defeat(self):
        entry=get_pc_book_npc_entry(PROFILE)
        self.assertEqual(entry.wound_bands,(
            PcBookNpcWoundBand(0,'Cannot choose to Give Ground or fall Prone'),
            PcBookNpcWoundBand(1,"Bestigor's next attack is Glorious"),
            PcBookNpcWoundBand(2,'Defeated')))

    def test_changed_caps_profiles_gear_and_partial_source_renames_cannot_claim_bestigor(self):
        definition=get_pc_book_npc_entry(PROFILE).definition
        attack,=definition.attacks
        protection,=definition.protection
        for candidate in (replace(definition,attacks=(replace(attack,test_profile=InlineProfile(3,4)),)),
                replace(definition,attacks=(replace(attack,test_profile=InlineProfile(3,4,6)),)),
                replace(definition,attacks=(replace(attack,damage=DamageProfile(8)),)),
                replace(definition,attacks=(replace(attack,hands=RangedWeaponHands.ONE_HANDED),)),
                replace(definition,protection=(replace(protection,test_profile=InlineProfile(4,3,8)),)),
                replace(definition,resilience=ResilienceProfile(4,3)),
                replace(definition,id='authored:root',source_rule_id='authored:root'),
                replace(definition,id='authored:root',source_rule_id='authored:root',
                    attacks=(replace(attack,source_rule_id='authored:attack'),))):
            with self.subTest(candidate=candidate),self.assertRaises((TypeError,ValueError)):
                validate_pc_book_npc_definition(candidate)

    def test_equal_cached_types_do_not_replace_canonical_nested_values(self):
        definition=get_pc_book_npc_entry(PROFILE).definition
        for target,field,value in (('definition','injury_policy','brute'),
                ('attack','skill','melee'),('attack','hands','2h'),
                ('profile','dice',3.0),('profile','pool_cap',8.0),
                ('damage','success_multiplier',True)):
            forged=deepcopy(definition)
            subject={'definition':forged,'attack':forged.attacks[0],
                'profile':forged.attacks[0].test_profile,'damage':forged.attacks[0].damage}[target]
            object.__setattr__(subject,field,value)
            self.assertEqual(forged,definition)
            with self.subTest(target=target,field=field),self.assertRaises(TypeError):
                validate_pc_book_npc_definition(forged)
        with self.assertRaises(TypeError):get_pc_book_npc_entry(PROFILE.value)

    def test_factory_definition_and_injury_graphs_are_independent(self):
        first=create_pc_book_npc(PROFILE,'one')
        second=create_pc_book_npc(PROFILE,'two')
        expected=deepcopy(second.definition)
        self.assertIsNot(first.definition,second.definition)
        self.assertIsNot(first.state.injury,second.state.injury)
        object.__setattr__(first.definition.attacks[0].test_profile,'pool_cap',6)
        self.assertEqual(second.definition,expected)
        self.assertEqual(get_pc_book_npc_entry(PROFILE).definition,expected)
        with self.assertRaises(ValueError):validate_pc_book_npc_definition(first.definition)


if __name__=='__main__':
    unittest.main()
