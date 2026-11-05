"""GM1.1 pp96/107/109: three explicit loadouts and complete book provenance."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from enum import Enum
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.attack_models import DamageProfile, ResilienceProfile
from towr.domain.pc_melee_result_models import PcAttackProof
from towr.domain.pc_npc_catalog import (
    PcBookNpcProfile, PcBookNpcWoundBand, create_pc_book_npc, get_pc_book_npc_entry,
    validate_pc_book_npc_definition,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario


CASES=(
    (PcBookNpcProfile.ARTISAN,96,'Artisan','make_shift_weapons',2,2,2,3,2,0,1),
    (PcBookNpcProfile.BRETONNIAN_SQUIRE_SWORD,109,'Bretonnian Squire (Sword)',
        'sword',3,3,3,3,4,0,1),
    (PcBookNpcProfile.ELF_MERCHANT_JEWELLED_BLADE,107,'Elf Merchant (Jewelled Blade)',
        'jewelled_blade',4,3,3,4,3,1,2),
)


class PcCatalogChunkTests(unittest.TestCase):
    def test_three_printed_profiles_keep_attack_and_protection_independent(self):
        for profile,page,name,weapon,dice,threshold,damage,pdice,pthreshold,armour,limit in CASES:
            with self.subTest(profile=profile):
                entry=get_pc_book_npc_entry(profile)
                source=f'BOOK-GM-GUIDE:1.1:p{page}:{profile.value}'
                self.assertEqual((entry.profile_id,entry.book_id,entry.version,entry.chapter,entry.page,entry.name),
                    (profile,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',page,name))
                definition=entry.definition
                self.assertEqual((definition.id,definition.source_rule_id,definition.injury_policy,
                    definition.wound_limit,definition.resilience),
                    ('pc-book-npc:'+profile.value,source,
                     TargetInjuryPolicy.BRUTE if limit==2 else TargetInjuryPolicy.MINION,
                     limit,ResilienceProfile(3,armour)))
                attack,=definition.attacks
                self.assertEqual((attack.id,attack.source_rule_id,attack.skill,attack.test_profile,
                    attack.damage,attack.hands,attack.range_min,attack.range_max,
                    attack.ignores_armour,attack.secondary_effects),
                    (weapon,source+':'+weapon,Skill.MELEE,InlineProfile(dice,threshold),DamageProfile(damage),
                     RangedWeaponHands.ONE_HANDED,RangedWeaponRange.CLOSE,RangedWeaponRange.CLOSE,False,()))
                protection,=definition.protection
                self.assertEqual((protection.source_rule_id,protection.skill,protection.test_profile),
                    (source+':athletics',Skill.ATHLETICS,InlineProfile(pdice,pthreshold)))
                validate_pc_book_npc_definition(definition)

    def test_inactive_abilities_preserve_scopes_and_merchant_wound_bands(self):
        artisan=get_pc_book_npc_entry(PcBookNpcProfile.ARTISAN)
        squire=get_pc_book_npc_entry(PcBookNpcProfile.BRETONNIAN_SQUIRE_SWORD)
        merchant=get_pc_book_npc_entry(PcBookNpcProfile.ELF_MERCHANT_JEWELLED_BLADE)
        for entry in (artisan,squire,merchant):
            self.assertEqual(entry.active_abilities,())
            self.assertEqual(entry.unselected_protection,())
            self.assertEqual(len(entry.inactive_abilities),1)
        pride,=artisan.inactive_abilities
        self.assertEqual((pride.name,pride.effect),
            ('Professional Pride','+1d on the next Test using that trapping'))
        self.assertIn('extra Coin',pride.scope)
        self.assertIn('directly',pride.scope)
        self.assertIn('Artisan creator',pride.scope)
        service,=squire.inactive_abilities
        self.assertEqual((service.name,service.effect),('Noble Service','+2d on those Help Tests'))
        self.assertIn('knight the Squire serves',service.scope)
        self.assertEqual(squire.unselected_attack_names,('Longbow',))
        bargain,=merchant.inactive_abilities
        self.assertEqual((bargain.name,bargain.scope,bargain.effect),
            ('Hard Bargain','Tests to barter with an Elf Merchant','-1d on those Tests'))
        self.assertEqual(merchant.wound_bands,(PcBookNpcWoundBand(0,'No effect'),
            PcBookNpcWoundBand(1,'Staggered'),PcBookNpcWoundBand(2,'Defeated')))
        self.assertEqual((artisan.wound_bands,squire.wound_bands),((),()))
        self.assertEqual((artisan.unselected_attack_names,merchant.unselected_attack_names),((),()))
        with self.assertRaises(FrozenInstanceError):
            merchant.wound_bands[1].effect='Broken'

    def test_fresh_graphs_and_snapshots_are_independent_for_each_new_profile(self):
        for profile,*_ in CASES:
            with self.subTest(profile=profile):
                first=create_pc_book_npc(profile,'first')
                second=create_pc_book_npc(profile,'second')
                self.assertIsNot(first.definition,second.definition)
                self.assertIsNot(first.definition.protection[0],second.definition.protection[0])
                self.assertIsNot(first.state.injury,second.state.injury)
                self.assertIsNot(first.state.current_resilience,first.definition.resilience)
                self.assertEqual((first.state.injury.wounds,first.state.injury.defeated,
                    first.state.wields_weapon,first.state.holds_shield),(0,False,True,False))
                original=deepcopy(second.definition)
                object.__setattr__(first.definition.attacks[0].damage,'base',99)
                self.assertEqual(second.definition,original)
                self.assertEqual(get_pc_book_npc_entry(profile).definition,original)
                with self.assertRaises(ValueError):
                    validate_pc_book_npc_definition(first.definition)

    def test_root_and_each_nested_source_reserve_the_complete_selected_loadout(self):
        for profile,*_ in CASES:
            definition=get_pc_book_npc_entry(profile).definition
            attack,=definition.attacks
            protection,=definition.protection
            invalid=(replace(definition,attacks=(replace(attack,damage=DamageProfile(9)),)),
                replace(definition,protection=(replace(protection,skill=Skill.DEFENCE),)),
                replace(definition,resilience=ResilienceProfile(4)),
                replace(definition,id='authored:root',source_rule_id='authored:source'),
                replace(definition,id='authored:root',source_rule_id='authored:source',
                    attacks=(replace(attack,source_rule_id='authored:attack'),)))
            for candidate in invalid:
                with self.subTest(profile=profile,candidate=candidate),self.assertRaises(ValueError):
                    validate_pc_book_npc_definition(candidate)
            alias=deepcopy(definition)
            object.__setattr__(alias.attacks[0],'hands',Enum('Hands',{'ONE':'1h'},type=str).ONE)
            self.assertEqual(alias,definition)
            with self.assertRaises(TypeError):
                validate_pc_book_npc_definition(alias)

    def test_artisan_and_squire_native_protection_use_printed_athletics(self):
        for kwargs,threshold in (({'artisans':1},2),({'squires':1},4)):
            source=book_pc_scenario(**kwargs,footpads=0,townsfolk=0,pc_count=1,max_rounds=1)
            # The successful PC attack Wounds and defeats this Minion.
            rng=ScriptedD10([1,1,1]+[10]*3)
            result=run_pc_melee_scenario(source,rng)
            rng.assert_exhausted()
            proof=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof)
            self.assertIs(proof.protection.source_request.selected_skill,Skill.ATHLETICS)
            defender=proof.execution.resolution.attack.defender_test
            self.assertEqual((defender.trace.rolled_dice,defender.trace.threshold),(3,threshold))
            self.assertTrue(result.state.enemies[0].state.injury.defeated)

    def test_artisan_native_attack_uses_two_dice_despite_three_dice_protection(self):
        source=book_pc_scenario(artisans=1,footpads=0,townsfolk=0,pc_count=1,max_rounds=1)
        rng=ScriptedD10([10]*3+[1]*3+[1]*2+[10]*3+[1])
        result=run_pc_melee_scenario(source,rng)
        rng.assert_exhausted()
        proof=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='artisan1')
        attack=proof.execution.resolution.attack
        self.assertEqual((attack.attacker_test.trace.rolled_dice,attack.attacker_test.trace.threshold,
            attack.impact_spec.damage.base),(2,2,2))
        self.assertEqual(attack.impact_spec.damage_modifiers,())


if __name__=='__main__':
    unittest.main()
