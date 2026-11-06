"""GM136/149/175: two natural creatures and a shielded Centigor Spear loadout."""
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
    (PcBookNpcProfile.DEMIGRYPH,175,'wicked_claws',4,5,None,RangedWeaponRange.CLOSE,4,0,3,3,False),
    (PcBookNpcProfile.CENTIGOR_SPEAR,149,'jagged_spear',4,4,RangedWeaponHands.ONE_HANDED,
        RangedWeaponRange.SHORT,4,1,2,3,True),
    (PcBookNpcProfile.WHITE_WOLF_RENDING_CLAWS,136,'rending_claws',3,6,None,
        RangedWeaponRange.CLOSE,5,0,2,4,False),
)


class PcCreatureCatalogTests(unittest.TestCase):
    def test_three_exact_printed_attacks_protection_and_book_identities(self):
        for profile,page,attack_id,dice,damage,hands,maximum,toughness,bonus,limit,pthreshold,_ in CASES:
            with self.subTest(profile=profile):
                entry=get_pc_book_npc_entry(profile)
                definition=entry.definition
                source=f'BOOK-GM-GUIDE:1.1:p{page}:{profile.value}'
                self.assertEqual((entry.profile_id,entry.book_id,entry.version,entry.chapter,entry.page),
                    (profile,'BOOK-GM-GUIDE','1.1','Allies and Antagonists',page))
                self.assertEqual((definition.id,definition.source_rule_id,definition.injury_policy,
                    definition.wound_limit,definition.resilience),
                    ('pc-book-npc:'+profile.value,source,TargetInjuryPolicy.BRUTE,limit,
                     ResilienceProfile(toughness,bonus)))
                attack,=definition.attacks
                self.assertEqual((attack.id,attack.source_rule_id,attack.skill,attack.test_profile,
                    attack.damage,attack.range_min,attack.range_max,attack.hands,
                    attack.ignores_armour,attack.secondary_effects),
                    (attack_id,source+':'+attack_id,Skill.MELEE,InlineProfile(dice,4),DamageProfile(damage),
                     RangedWeaponRange.CLOSE,maximum,hands,False,()))
                protection,=definition.protection
                self.assertEqual((protection.source_rule_id,protection.skill,protection.test_profile),
                    (source+':athletics',Skill.ATHLETICS,InlineProfile(4,pthreshold)))
                self.assertIsNone(attack.test_profile.pool_cap)
                self.assertIsNone(protection.test_profile.pool_cap)
                self.assertEqual(entry.unselected_protection,())
                validate_pc_book_npc_definition(definition)

    def test_fresh_natural_and_shielded_loadouts_preserve_exact_equipment_and_armour(self):
        for profile,_,attack_id,_,_,hands,_,toughness,bonus,limit,_,shield in CASES:
            with self.subTest(profile=profile):
                snapshot=create_pc_book_npc(profile,'creature')
                self.assertEqual((snapshot.state.actor_id,snapshot.state.definition_id,
                    snapshot.state.wields_weapon,snapshot.state.holds_shield,snapshot.state.current_resilience,
                    snapshot.state.available_attack_ids),
                    ('creature','pc-book-npc:'+profile.value,hands is not None,shield,
                     ResilienceProfile(toughness,bonus),(attack_id,)))
                self.assertIs(snapshot.state.holds_shield,shield)
                self.assertIs(snapshot.state.current_resilience.is_armoured,shield)
                self.assertEqual((snapshot.state.injury.wounds,snapshot.state.injury.wound_limit,
                    snapshot.state.injury.defeated,snapshot.state.injury.defeat_cause),(0,limit,False,None))
                self.assertFalse(snapshot.state.injury.conditions.conditions)

    def test_each_profile_keeps_its_own_drained_or_prone_wound_bands(self):
        for profile,expected in (
                (PcBookNpcProfile.DEMIGRYPH,((0,'No effect'),(1,'Drained'),(2,'Drained'),(3,'Defeated'))),
                (PcBookNpcProfile.CENTIGOR_SPEAR,((0,'No effect'),(1,'Prone'),(2,'Defeated'))),
                (PcBookNpcProfile.WHITE_WOLF_RENDING_CLAWS,((0,'No effect'),(1,'Drained'),(2,'Defeated')))):
            with self.subTest(profile=profile):
                self.assertEqual(get_pc_book_npc_entry(profile).wound_bands,
                    tuple(PcBookNpcWoundBand(number,effect) for number,effect in expected))

    def test_demigryph_rider_double_attack_is_not_a_standalone_extra_action(self):
        entry=get_pc_book_npc_entry(PcBookNpcProfile.DEMIGRYPH)
        self.assertIn('unmounted',entry.name)
        self.assertEqual(entry.active_abilities,())
        fear,rider=entry.inactive_abilities
        self.assertEqual((fear.name,fear.scope,fear.effect),
            ('Fearsome','An enemy Gives Ground from a Demigryph attack','That enemy suffers Broken'))
        self.assertEqual((rider.name,rider.scope),('Demigryph Knights','A Human mounted on a Demigryph'))
        for detail in ('+2 Resilience','Fast Speed','Fearsome','Agility penalties',
                'heavy or full plate armour','rider takes the Attack action','one rider attack',
                'second attack using Wicked Claws','one of those attacks chosen to be Grim'):
            self.assertIn(detail,rider.effect)
        self.assertEqual(entry.unselected_attack_names,())

    def test_centigor_charge_and_rampage_preserve_before_attack_and_every_creature_scope(self):
        entry=get_pc_book_npc_entry(PcBookNpcProfile.CENTIGOR_SPEAR)
        self.assertEqual(entry.active_abilities,())
        forest,charge,rampage=entry.inactive_abilities
        self.assertEqual((forest.name,forest.scope),('Child of the Forest','Movement through woodland Difficult Terrain'))
        self.assertEqual(forest.effect,'Ignore the effects of woodland Difficult Terrain')
        self.assertEqual((charge.name,charge.scope,charge.effect),
            ('Jagged Spear on Charge','An attack as part of a Charge','+1d Melee'))
        self.assertEqual((rampage.name,rampage.scope,rampage.effect),
            ('Drunken Rampage','A Centigor Charges, before making its attack',
             'Every creature in Close Range suffers Staggered unless it is already Staggered'))
        self.assertEqual(entry.unselected_attack_names,('Javelin',))

    def test_white_wolf_claws_do_not_claim_clamping_ban_or_unconditional_second_attack(self):
        entry=get_pc_book_npc_entry(PcBookNpcProfile.WHITE_WOLF_RENDING_CLAWS)
        self.assertEqual(entry.active_abilities,())
        self.assertEqual(entry.unselected_attack_names,('Clamping Jaws',))
        pin,fear=entry.inactive_abilities
        self.assertEqual((pin.name,pin.scope,pin.effect),
            ('Pin and Tear','A successful Clamping Jaws attack as part of a Charge',
             'May take a second action to attack the same target with Rending Claws'))
        self.assertEqual((fear.name,fear.scope,fear.effect),
            ('Fearsome','An enemy Gives Ground from a White Wolf attack','The enemy suffers Broken'))
        old=get_pc_book_npc_entry(PcBookNpcProfile.WHITE_WOLF_CLAMPING_JAWS)
        self.assertEqual(old.unselected_attack_names,('Rending Claws',))
        self.assertEqual(tuple(ability.name for ability in old.active_abilities),('Clamping Jaws',))
        self.assertEqual(old.definition.attacks[0].damage.base,5)
        self.assertNotEqual(old.definition.id,entry.definition.id)

    def test_partial_source_and_printed_damage_armour_or_protection_forgery_is_rejected(self):
        for profile,*_ in CASES:
            definition=get_pc_book_npc_entry(profile).definition
            attack,=definition.attacks
            protection,=definition.protection
            candidates=(
                replace(definition,resilience=ResilienceProfile(definition.resilience.toughness,
                    definition.resilience.bonus+1)),
                replace(definition,attacks=(replace(attack,damage=DamageProfile(9)),)),
                replace(definition,attacks=(replace(attack,range_max=RangedWeaponRange.MEDIUM),)),
                replace(definition,protection=(replace(protection,skill=Skill.DEFENCE),)),
                replace(definition,id='authored:root',source_rule_id='authored:source'),
                replace(definition,id='authored:root',source_rule_id='authored:source',
                    attacks=(replace(attack,source_rule_id='authored:attack'),)),
                replace(definition,id='authored:root',source_rule_id='authored:source',
                    protection=(replace(protection,source_rule_id='authored:protection'),)),
            )
            for candidate in candidates:
                with self.subTest(profile=profile,candidate=candidate),self.assertRaises((TypeError,ValueError)):
                    validate_pc_book_npc_definition(candidate)

    def test_equal_string_enums_and_boolean_damage_aliases_are_not_canonical_book_types(self):
        for profile,*_ in CASES:
            definition=get_pc_book_npc_entry(profile).definition
            for target,name,value in (('definition','injury_policy','brute'),('attack','skill','melee'),
                    ('attack','range_max',definition.attacks[0].range_max.value),
                    ('damage','success_multiplier',True)):
                forged=deepcopy(definition)
                subject={'definition':forged,'attack':forged.attacks[0],'damage':forged.attacks[0].damage}[target]
                object.__setattr__(subject,name,value)
                self.assertEqual(forged,definition)
                with self.subTest(profile=profile,target=target,name=name),self.assertRaises(TypeError):
                    validate_pc_book_npc_definition(forged)
            with self.assertRaises(TypeError):
                get_pc_book_npc_entry(profile.value)

    def test_each_factory_call_has_independent_definition_and_injury_graphs(self):
        for profile,*_ in CASES:
            with self.subTest(profile=profile):
                first=create_pc_book_npc(profile,'first')
                second=create_pc_book_npc(profile,'second')
                expected=deepcopy(second.definition)
                self.assertIsNot(first.definition,second.definition)
                self.assertIsNot(first.state.injury,second.state.injury)
                object.__setattr__(first.definition.attacks[0].damage,'base',99)
                self.assertEqual(second.definition,expected)
                self.assertEqual(get_pc_book_npc_entry(profile).definition,expected)
                with self.assertRaises(ValueError):
                    validate_pc_book_npc_definition(first.definition)


if __name__=='__main__':
    unittest.main()
