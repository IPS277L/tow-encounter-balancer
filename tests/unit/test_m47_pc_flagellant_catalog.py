"""GM122 printed Flagellant loadouts retain every Ability without PC weapon traits."""
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


CASES=(
    (PcBookNpcProfile.FLAGELLANT_FLAILS,'flails',6,RangedWeaponHands.TWO_HANDED),
    (PcBookNpcProfile.FLAGELLANT_HOOKS_CHAINS,'hooks_and_chains',3,RangedWeaponHands.ONE_HANDED),
)


class PcFlagellantCatalogTests(unittest.TestCase):
    def test_two_exact_printed_attacks_and_complete_source_identities(self):
        for profile,weapon,damage,hands in CASES:
            entry=get_pc_book_npc_entry(profile)
            definition=entry.definition
            source=f'BOOK-GM-GUIDE:1.1:p122:{profile.value}'
            with self.subTest(profile=profile):
                self.assertEqual((entry.profile_id,entry.book_id,entry.version,entry.chapter,entry.page),
                    (profile,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',122))
                self.assertEqual((definition.id,definition.source_rule_id,definition.injury_policy,
                    definition.wound_limit,definition.resilience),
                    (f'pc-book-npc:{profile.value}',source,TargetInjuryPolicy.BRUTE,2,ResilienceProfile(3,0)))
                attack,=definition.attacks
                self.assertEqual((attack.id,attack.source_rule_id,attack.skill,attack.test_profile,attack.damage,
                    attack.range_min,attack.range_max,attack.hands,attack.ignores_armour,attack.secondary_effects),
                    (weapon,source+':'+weapon,Skill.MELEE,InlineProfile(3,4),DamageProfile(damage),
                     RangedWeaponRange.CLOSE,RangedWeaponRange.CLOSE,hands,False,()))
                validate_pc_book_npc_definition(definition)

    def test_both_use_printed_athletics_without_explicit_caps_or_unselected_protection(self):
        for profile,_,_,_ in CASES:
            entry=get_pc_book_npc_entry(profile)
            protection,=entry.definition.protection
            self.assertEqual((protection.source_rule_id,protection.skill,protection.test_profile),
                (f'BOOK-GM-GUIDE:1.1:p122:{profile.value}:athletics',Skill.ATHLETICS,InlineProfile(3,3)))
            self.assertEqual((entry.definition.attacks[0].test_profile.maximum_dice,
                protection.test_profile.maximum_dice),(6,6))
            self.assertIsNone(entry.definition.attacks[0].test_profile.pool_cap)
            self.assertIsNone(protection.test_profile.pool_cap)
            self.assertEqual(entry.unselected_protection,())

    def test_fresh_instances_are_armed_healthy_and_unshielded_without_automatic_conditions(self):
        for profile,weapon,_,_ in CASES:
            snapshot=create_pc_book_npc(profile,'flagellant')
            self.assertEqual((snapshot.state.actor_id,snapshot.state.definition_id,
                snapshot.state.wields_weapon,snapshot.state.holds_shield,
                snapshot.state.current_resilience,snapshot.state.available_attack_ids),
                ('flagellant',f'pc-book-npc:{profile.value}',True,False,ResilienceProfile(3,0),(weapon,)))
            self.assertEqual((snapshot.state.injury.wounds,snapshot.state.injury.wound_limit,
                snapshot.state.injury.defeated,snapshot.state.injury.defeat_cause),(0,2,False,None))
            self.assertFalse(snapshot.state.injury.conditions.conditions)

    def test_unbreakable_is_direct_broken_immunity_not_general_psychological_immunity(self):
        for profile,_,_,_ in CASES:
            ability=get_pc_book_npc_entry(profile).active_abilities[0]
            self.assertEqual(ability.name,'Unbreakable')
            self.assertIn('Any source',ability.scope)
            self.assertIn('Broken condition itself',ability.effect)
            self.assertIn('independently',ability.effect)

    def test_feel_no_pain_preserves_optional_wound_and_automatic_recover_healing(self):
        for profile,_,_,_ in CASES:
            entry=get_pc_book_npc_entry(profile)
            ability=entry.active_abilities[1]
            self.assertEqual(ability.name,'Feel No Pain')
            self.assertIn('When Staggered',ability.scope)
            self.assertIn('Recover action',ability.scope)
            self.assertIn('May choose to be Wounded instead of Staggered',ability.effect)
            self.assertIn('automatically heals one Wound',ability.effect)
            self.assertEqual(entry.wound_bands,(
                PcBookNpcWoundBand(0,'May be Wounded instead of Staggered'),
                PcBookNpcWoundBand(1,'Remove Wound with Recover action'),PcBookNpcWoundBand(2,'Defeated')))

    def test_flails_alone_have_staggered_melee_penalty_and_other_weapon_is_unselected(self):
        flails=get_pc_book_npc_entry(PcBookNpcProfile.FLAGELLANT_FLAILS)
        hooks=get_pc_book_npc_entry(PcBookNpcProfile.FLAGELLANT_HOOKS_CHAINS)
        penalty=flails.active_abilities[2]
        self.assertEqual(penalty.name,'Flails')
        self.assertIn('Staggered',penalty.scope)
        self.assertIn('-2d Melee',penalty.effect)
        self.assertEqual(tuple(a.name for a in hooks.active_abilities),('Unbreakable','Feel No Pain'))
        self.assertEqual((flails.unselected_attack_names,hooks.unselected_attack_names),
            (('Hooks and Chains',),('Flails',)))
        self.assertEqual((flails.inactive_abilities,hooks.inactive_abilities),((),()))

    def test_changed_numbers_caps_hands_and_partial_source_renames_are_rejected(self):
        for profile,_,_,_ in CASES:
            definition=get_pc_book_npc_entry(profile).definition
            attack,=definition.attacks
            protection,=definition.protection
            other=RangedWeaponHands.ONE_HANDED if attack.hands is RangedWeaponHands.TWO_HANDED else RangedWeaponHands.TWO_HANDED
            for candidate in (replace(definition,attacks=(replace(attack,test_profile=InlineProfile(3,3)),)),
                    replace(definition,attacks=(replace(attack,test_profile=InlineProfile(3,4,6)),)),
                    replace(definition,attacks=(replace(attack,damage=DamageProfile(attack.damage.base+1)),)),
                    replace(definition,attacks=(replace(attack,hands=other),)),
                    replace(definition,protection=(replace(protection,test_profile=InlineProfile(3,4)),)),
                    replace(definition,resilience=ResilienceProfile(3,1)),
                    replace(definition,id='authored:root',source_rule_id='authored:root')):
                with self.subTest(profile=profile,candidate=candidate),self.assertRaises((TypeError,ValueError)):
                    validate_pc_book_npc_definition(candidate)

    def test_equal_cached_enum_float_and_bool_aliases_cannot_claim_canonical_types(self):
        for profile,_,_,_ in CASES:
            definition=get_pc_book_npc_entry(profile).definition
            for target,field,value in (('definition','injury_policy','brute'),('attack','skill','melee'),
                    ('profile','dice',3.0),('profile','threshold',4.0),('damage','success_multiplier',True)):
                forged=deepcopy(definition)
                subject={'definition':forged,'attack':forged.attacks[0],
                    'profile':forged.attacks[0].test_profile,'damage':forged.attacks[0].damage}[target]
                object.__setattr__(subject,field,value)
                self.assertEqual(forged,definition)
                with self.subTest(profile=profile,target=target,field=field),self.assertRaises(TypeError):
                    validate_pc_book_npc_definition(forged)

    def test_factory_definition_and_injury_graphs_remain_independent(self):
        for profile,_,_,_ in CASES:
            first=create_pc_book_npc(profile,'one')
            second=create_pc_book_npc(profile,'two')
            expected=deepcopy(second.definition)
            self.assertIsNot(first.definition,second.definition)
            self.assertIsNot(first.state.injury,second.state.injury)
            object.__setattr__(first.definition.attacks[0].test_profile,'threshold',1)
            self.assertEqual(second.definition,expected)
            self.assertEqual(get_pc_book_npc_entry(profile).definition,expected)
            with self.assertRaises(ValueError):validate_pc_book_npc_definition(first.definition)
