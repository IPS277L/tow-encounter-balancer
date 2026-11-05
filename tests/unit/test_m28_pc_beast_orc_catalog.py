"""GM93/143/145/158: exact shield-free fixed loadouts, without implicit PC traits."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.attack_models import DamageProfile,ResilienceProfile
from towr.domain.pc_melee_result_models import PcAttackProof
from towr.domain.pc_npc_catalog import (
    PcBookNpcProfile,create_pc_book_npc,get_pc_book_npc_entry,validate_pc_book_npc_definition,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands,RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile,Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario


CASES=(
    (PcBookNpcProfile.GOR_DUAL_AXES,'gors','gor1',143,'crude_axes',4,3,3,
        RangedWeaponHands.ONE_HANDED,4,0,4,3,Skill.ATHLETICS),
    (PcBookNpcProfile.CHAOS_WARHOUND,'warhounds','warhound1',145,'pinning_claws',3,3,3,
        None,3,0,4,3,Skill.ATHLETICS),
    (PcBookNpcProfile.ORC_BOY_CHOPPAS,'orcs','orc1',158,'choppas',3,4,4,
        RangedWeaponHands.TWO_HANDED,4,1,3,4,Skill.DEFENCE),
)


class PcBeastOrcCatalogTests(unittest.TestCase):
    def test_printed_attack_and_protection_and_adjusted_shield_free_resilience(self):
        for profile,keyword,actor,page,attack_id,dice,threshold,damage,hands,toughness,armour,pdice,pthreshold,skill in CASES:
            with self.subTest(profile=profile):
                entry=get_pc_book_npc_entry(profile)
                definition=entry.definition
                source=f'BOOK-GM-GUIDE:1.1:p{page}:{profile.value}'
                self.assertEqual((entry.book_id,entry.version,entry.chapter,entry.page),
                    ('BOOK-GM-GUIDE','1.1','Allies and Antagonists',page))
                self.assertEqual((definition.id,definition.source_rule_id,definition.injury_policy,
                    definition.wound_limit,definition.resilience),
                    ('pc-book-npc:'+profile.value,source,TargetInjuryPolicy.MINION,1,
                     ResilienceProfile(toughness,armour)))
                attack,=definition.attacks
                self.assertEqual((attack.id,attack.source_rule_id,attack.skill,attack.test_profile,
                    attack.damage,attack.hands,attack.range_min,attack.range_max,
                    attack.ignores_armour,attack.secondary_effects),
                    (attack_id,source+':'+attack_id,Skill.MELEE,InlineProfile(dice,threshold),
                     DamageProfile(damage),hands,RangedWeaponRange.CLOSE,RangedWeaponRange.CLOSE,False,()))
                protection,=definition.protection
                self.assertEqual((protection.source_rule_id,protection.skill,protection.test_profile),
                    (source+':'+skill.value,skill,InlineProfile(pdice,pthreshold)))
                snapshot=create_pc_book_npc(profile,actor)
                self.assertEqual((snapshot.state.wields_weapon,snapshot.state.holds_shield,
                    snapshot.state.current_resilience,snapshot.state.available_attack_ids),
                    (hands is not None,False,ResilienceProfile(toughness,armour),(attack_id,)))
                validate_pc_book_npc_definition(definition)

    def test_fixed_two_axe_mode_preserves_distinct_printed_hand_notations(self):
        gor=get_pc_book_npc_entry(PcBookNpcProfile.GOR_DUAL_AXES)
        orc=get_pc_book_npc_entry(PcBookNpcProfile.ORC_BOY_CHOPPAS)
        self.assertEqual(tuple(a.name for a in gor.active_abilities),
            ('Primal Rage','Dual-wielded Crude Axes'))
        self.assertIn('Gor itself is Staggered',gor.active_abilities[0].scope)
        self.assertIn('both hands',gor.active_abilities[1].scope)
        self.assertIn('shield is not carried',gor.active_abilities[1].scope)
        self.assertIs(gor.definition.attacks[0].hands,RangedWeaponHands.ONE_HANDED)
        self.assertIs(orc.definition.attacks[0].hands,RangedWeaponHands.TWO_HANDED)
        self.assertFalse(gor.definition.resilience.is_armoured)
        self.assertTrue(orc.definition.resilience.is_armoured)

    def test_latent_terrain_charge_help_and_unused_orc_protection_remain_explicit(self):
        gor=get_pc_book_npc_entry(PcBookNpcProfile.GOR_DUAL_AXES)
        hound=get_pc_book_npc_entry(PcBookNpcProfile.CHAOS_WARHOUND)
        orc=get_pc_book_npc_entry(PcBookNpcProfile.ORC_BOY_CHOPPAS)
        for entry in (gor,hound):
            self.assertEqual(entry.inactive_abilities[0].name,'Child of the Forest')
            self.assertIn('woodland',entry.inactive_abilities[0].effect)
        self.assertEqual(hound.active_abilities[0].effect,'Target cannot Give Ground')
        self.assertEqual(orc.unselected_attack_names,('Jagged Spear','Warbow'))
        alternative,=orc.unselected_protection
        self.assertEqual((alternative.skill,alternative.test_profile),(Skill.ATHLETICS,InlineProfile(3,3)))
        self.assertEqual(tuple(a.name for a in orc.inactive_abilities),
            ('Choppas on Charge','Power of the Waaagh!'))
        self.assertIn('1 free success',orc.inactive_abilities[1].effect)
        self.assertIn('Do not Test',orc.inactive_abilities[1].effect)

    def test_known_identity_rejects_restored_shield_bonus_and_other_loadouts(self):
        for profile,keyword,actor,page,attack_id,dice,threshold,damage,hands,toughness,armour,pdice,pthreshold,skill in CASES:
            definition=get_pc_book_npc_entry(profile).definition
            attack,=definition.attacks
            protection,=definition.protection
            invalid=(replace(definition,resilience=ResilienceProfile(toughness,armour+1)),
                replace(definition,attacks=(replace(attack,damage=DamageProfile(9)),)),
                replace(definition,protection=(replace(protection,test_profile=InlineProfile(2,2)),)),
                replace(definition,id='authored:root',source_rule_id='authored:source'),
                replace(definition,id='authored:root',source_rule_id='authored:source',
                    attacks=(replace(attack,source_rule_id='authored:attack'),)))
            for candidate in invalid:
                with self.subTest(profile=profile),self.assertRaises((TypeError,ValueError)):
                    validate_pc_book_npc_definition(candidate)
        orc=get_pc_book_npc_entry(PcBookNpcProfile.ORC_BOY_CHOPPAS)
        with self.assertRaises(ValueError):
            validate_pc_book_npc_definition(replace(orc.definition,protection=orc.unselected_protection))

    def test_graphs_and_unused_protection_do_not_share_bypass_mutations(self):
        for profile,*_ in CASES:
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
        entry=get_pc_book_npc_entry(PcBookNpcProfile.ORC_BOY_CHOPPAS)
        object.__setattr__(entry.unselected_protection[0].test_profile,'dice',9)
        self.assertEqual(get_pc_book_npc_entry(PcBookNpcProfile.ORC_BOY_CHOPPAS).
            unselected_protection[0].test_profile,InlineProfile(3,3))

    def test_native_protection_keeps_printed_dice_and_skill_after_shield_removal(self):
        for profile,keyword,actor,page,attack_id,dice,threshold,damage,hands,toughness,armour,pdice,pthreshold,skill in CASES:
            with self.subTest(profile=profile):
                source=book_pc_scenario(**{keyword:1},footpads=0,townsfolk=0,pc_count=1,max_rounds=1)
                rng=ScriptedD10([1]*3+[10]*pdice)
                result=run_pc_melee_scenario(source,rng)
                rng.assert_exhausted()
                proof=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof)
                self.assertIs(proof.protection.source_request.selected_skill,skill)
                self.assertFalse(proof.protection.source_request.defender_holds_shield)
                defender=proof.execution.resolution.attack.defender_test
                self.assertEqual((defender.trace.rolled_dice,defender.trace.threshold),(pdice,pthreshold))
                self.assertTrue(result.state.enemy(actor).state.injury.defeated)


if __name__=='__main__':
    unittest.main()
