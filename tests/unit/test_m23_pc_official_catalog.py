"""GM1.1 p98 Official's Dagger loadout and descriptive Brute wound bands."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from enum import Enum
import unittest

from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.pc_npc_catalog import (
    PcBookNpcAbility, PcBookNpcProfile, PcBookNpcWoundBand, create_pc_book_npc,
    get_pc_book_npc_entry, validate_pc_book_npc_definition,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill
from towr.domain.turn_models import CombatSide


OFFICIAL=PcBookNpcProfile.EMPIRE_OFFICIAL_DAGGER
SOURCE='BOOK-GM-GUIDE:1.1:p98:empire_official_dagger'


class OfficialCatalogTests(unittest.TestCase):
    def test_printed_attack_and_protection_keep_independent_dice_and_brute_limit(self):
        entry=get_pc_book_npc_entry(OFFICIAL)
        self.assertEqual((entry.profile_id,entry.book_id,entry.version,entry.chapter,entry.page,entry.name),
            (OFFICIAL,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',98,'Empire Official (Dagger)'))
        definition=entry.definition
        self.assertEqual((definition.id,definition.source_rule_id),
            ('pc-book-npc:empire_official_dagger',SOURCE))
        self.assertIs(definition.injury_policy,TargetInjuryPolicy.BRUTE)
        self.assertIs(type(definition.wound_limit),int)
        self.assertEqual((definition.wound_limit,definition.resilience),(2,ResilienceProfile(3)))
        attack,=definition.attacks
        self.assertEqual((attack.id,attack.source_rule_id,attack.skill,attack.test_profile,attack.damage,
            attack.range_min,attack.range_max,attack.hands,attack.ignores_armour,attack.secondary_effects),
            ('dagger',SOURCE+':dagger',Skill.MELEE,InlineProfile(2,3),DamageProfile(2),
             RangedWeaponRange.CLOSE,RangedWeaponRange.CLOSE,RangedWeaponHands.ONE_HANDED,False,()))
        protection,=definition.protection
        self.assertEqual((protection.source_rule_id,protection.skill,protection.test_profile),
            (SOURCE+':athletics',Skill.ATHLETICS,InlineProfile(3,3)))
        self.assertIsNone(validate_pc_book_npc_definition(definition))

    def test_wound_bands_and_inactive_ability_record_printed_effects_without_pistol(self):
        entry=get_pc_book_npc_entry(OFFICIAL)
        self.assertEqual(entry.wound_bands,(PcBookNpcWoundBand(0,'No effect'),
            PcBookNpcWoundBand(1,'Broken'),PcBookNpcWoundBand(2,'Defeated')))
        self.assertIs(type(entry.wound_bands),tuple)
        for band in entry.wound_bands:
            self.assertIs(type(band),PcBookNpcWoundBand)
            self.assertIs(type(band.wounds),int)
            self.assertIs(type(band.effect),str)
        self.assertEqual(entry.active_abilities,())
        self.assertEqual(entry.inactive_abilities,(PcBookNpcAbility('Heard It All Before',
            'Persuade or Distract attempts against the Official unless they include a bribe',
            'Grim Persuade or Distract Test'),))
        self.assertEqual(entry.unselected_attack_names,('Pistol',))
        self.assertEqual(tuple(attack.id for attack in entry.definition.attacks),('dagger',))
        with self.assertRaises(FrozenInstanceError):
            entry.wound_bands[1].effect='no Broken'

    def test_prior_three_profiles_have_no_required_wound_band_metadata(self):
        for profile in (PcBookNpcProfile.FOOTPAD,PcBookNpcProfile.EMPIRE_TOWNSFOLK,PcBookNpcProfile.BRIGAND_AXE):
            entry=get_pc_book_npc_entry(profile)
            self.assertEqual(entry.wound_bands,())
            snapshot=create_pc_book_npc(profile,profile.value+'1')
            self.assertEqual((snapshot.state.injury.wounds,snapshot.state.injury.wound_limit),(0,1))

    def test_factory_returns_fresh_healthy_brute_state_and_complete_graphs(self):
        first=create_pc_book_npc(OFFICIAL,'official1')
        second=create_pc_book_npc(OFFICIAL,'official2')
        self.assertEqual((first.state.actor_id,first.state.definition_id,first.state.side),
            ('official1','pc-book-npc:empire_official_dagger',CombatSide.OPPOSITION))
        self.assertEqual((first.state.injury.wounds,first.state.injury.wound_limit,first.state.injury.defeated),
            (0,2,False))
        self.assertEqual(first.state.injury.conditions.conditions,frozenset())
        self.assertEqual((first.state.available_attack_ids,first.state.current_resilience,
            first.state.wields_weapon,first.state.holds_shield),(('dagger',),ResilienceProfile(3),True,False))
        for left,right in ((first.definition,second.definition),(first.state,second.state),
                (first.state.injury,second.state.injury),(first.state.current_resilience,second.state.current_resilience),
                (first.definition.resilience,second.definition.resilience),
                (first.definition.attacks[0],second.definition.attacks[0]),
                (first.definition.attacks[0].test_profile,second.definition.attacks[0].test_profile),
                (first.definition.attacks[0].damage,second.definition.attacks[0].damage),
                (first.definition.protection[0],second.definition.protection[0]),
                (first.definition.protection[0].test_profile,second.definition.protection[0].test_profile)):
            self.assertIsNot(left,right)
        object.__setattr__(first.definition.protection[0].test_profile,'dice',2)
        self.assertEqual(second.definition.protection[0].test_profile,InlineProfile(3,3))
        self.assertEqual(get_pc_book_npc_entry(OFFICIAL).definition.protection[0].test_profile,InlineProfile(3,3))
        with self.assertRaises(ValueError):
            validate_pc_book_npc_definition(first.definition)
        left,right=get_pc_book_npc_entry(OFFICIAL),get_pc_book_npc_entry(OFFICIAL)
        self.assertEqual(left,right)
        self.assertIsNot(left.inactive_abilities[0],right.inactive_abilities[0])
        for a,b in zip(left.wound_bands,right.wound_bands):
            self.assertIsNot(a,b)

    def test_root_and_every_nested_official_source_reserve_complete_printed_profile(self):
        definition=get_pc_book_npc_entry(OFFICIAL).definition
        attack,=definition.attacks
        protection,=definition.protection
        invalid=(replace(definition,wound_limit=3),
            replace(definition,injury_policy=TargetInjuryPolicy.MINION,wound_limit=1),
            replace(definition,resilience=ResilienceProfile(3,1)),
            replace(definition,attacks=(replace(attack,test_profile=InlineProfile(3,3)),)),
            replace(definition,protection=(replace(protection,test_profile=InlineProfile(2,3)),)),
            replace(definition,id='authored:changed-root'),
            replace(definition,source_rule_id='authored:changed-source'))
        for candidate in invalid:
            with self.subTest(candidate=candidate),self.assertRaises(ValueError):
                validate_pc_book_npc_definition(candidate)
        for claimed in ('root','attack','protection'):
            candidate=replace(definition,id='authored:renamed',
                source_rule_id=SOURCE if claimed=='root' else 'authored:source',
                attacks=(replace(attack,source_rule_id=SOURCE+':dagger' if claimed=='attack' else 'authored:dagger'),),
                protection=(replace(protection,source_rule_id=SOURCE+':athletics' if claimed=='protection' else 'authored:athletics'),))
            with self.subTest(claimed=claimed),self.assertRaises(ValueError):
                validate_pc_book_npc_definition(candidate)

    def test_equal_aliases_bools_and_containers_cannot_bypass_canonical_types(self):
        definition=get_pc_book_npc_entry(OFFICIAL).definition
        alias=Enum('ForeignSkill',{'ATHLETICS':'athletics'},type=str).ATHLETICS
        for value in ('athletics',alias):
            forged=deepcopy(definition)
            object.__setattr__(forged.protection[0],'skill',value)
            with self.subTest(value=value),self.assertRaises(TypeError):
                validate_pc_book_npc_definition(forged)
        for field,value in (('injury_policy','brute'),('attacks',list(definition.attacks))):
            forged=deepcopy(definition)
            object.__setattr__(forged,field,value)
            with self.subTest(field=field),self.assertRaises(TypeError):
                validate_pc_book_npc_definition(forged)
        forged=deepcopy(definition)
        object.__setattr__(forged.resilience,'bonus',False)
        with self.assertRaises(TypeError):
            validate_pc_book_npc_definition(forged)


if __name__=='__main__':
    unittest.main()
