"""GM96/97/113: three compatible printed Minions with complete dormant triggers."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.attack_models import DamageProfile,ResilienceProfile
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_result_models import PcAttackProof,PcRecoverProof,PcMeleeOutcome
from towr.domain.pc_npc_catalog import (
    PcBookNpcProfile,create_pc_book_npc,get_pc_book_npc_entry,validate_pc_book_npc_definition,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands,RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile,Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario


CASES=(
    (PcBookNpcProfile.EMPIRE_PEASANT,'peasants','peasant1',96,'make_shift_weapons',2,2,2,
     RangedWeaponHands.ONE_HANDED,RangedWeaponRange.CLOSE,0,2),
    (PcBookNpcProfile.TOWN_WATCH_POLEARM,'watch','watch1',97,'polearm',3,3,5,
     RangedWeaponHands.TWO_HANDED,RangedWeaponRange.SHORT,1,3),
    (PcBookNpcProfile.FREE_COMPANY_MILITIA_BLADES,'militia','militia1',113,'improvised_blades',3,3,3,
     RangedWeaponHands.ONE_HANDED,RangedWeaponRange.CLOSE,0,3),
)


def source(keyword,*,rounds=1):
    return book_pc_scenario(**{keyword:1},footpads=0,townsfolk=0,pc_count=1,max_rounds=rounds)


def execute(scene,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(scene,rng)
    rng.assert_exhausted()
    return result


class PcEmpireCatalogTests(unittest.TestCase):
    def test_printed_definitions_snapshots_and_full_book_sources(self):
        for profile,keyword,actor,page,weapon,dice,threshold,damage,hands,maximum,armour,pthreshold in CASES:
            with self.subTest(profile=profile):
                entry=get_pc_book_npc_entry(profile)
                definition=entry.definition
                book=f'BOOK-GM-GUIDE:1.1:p{page}:{profile.value}'
                self.assertEqual((entry.book_id,entry.version,entry.chapter,entry.page),
                    ('BOOK-GM-GUIDE','1.1','Allies and Antagonists',page))
                self.assertEqual((definition.id,definition.source_rule_id,definition.injury_policy,
                    definition.wound_limit,definition.resilience),
                    ('pc-book-npc:'+profile.value,book,TargetInjuryPolicy.MINION,1,ResilienceProfile(3,armour)))
                attack,=definition.attacks
                self.assertEqual((attack.id,attack.source_rule_id,attack.skill,attack.test_profile,
                    attack.damage,attack.hands,attack.range_min,attack.range_max,
                    attack.secondary_effects,attack.ignores_armour),
                    (weapon,book+':'+weapon,Skill.MELEE,InlineProfile(dice,threshold),DamageProfile(damage),
                     hands,RangedWeaponRange.CLOSE,maximum,(),False))
                protection,=definition.protection
                self.assertEqual((protection.source_rule_id,protection.skill,protection.test_profile),
                    (book+':athletics',Skill.ATHLETICS,InlineProfile(3,pthreshold)))
                snapshot=create_pc_book_npc(profile,actor)
                self.assertEqual(snapshot,source(keyword).enemies[0])
                self.assertEqual((snapshot.state.wields_weapon,snapshot.state.holds_shield,
                    snapshot.state.current_resilience,snapshot.state.available_attack_ids),
                    (True,False,ResilienceProfile(3,armour),(weapon,)))
                self.assertEqual((snapshot.state.injury.wounds,snapshot.state.injury.defeated,
                    snapshot.state.injury.defeat_cause),(0,False,None))
                validate_pc_book_npc_definition(definition)

    def test_help_and_reinforcement_metadata_keeps_exact_eligibility_and_timing(self):
        peasant=get_pc_book_npc_entry(PcBookNpcProfile.EMPIRE_PEASANT)
        watch=get_pc_book_npc_entry(PcBookNpcProfile.TOWN_WATCH_POLEARM)
        militia=get_pc_book_npc_entry(PcBookNpcProfile.FREE_COMPANY_MILITIA_BLADES)
        self.assertEqual(peasant.unselected_attack_names,('Hunting Bow',))
        self.assertEqual(militia.unselected_attack_names,('Assorted Projectiles',))
        self.assertEqual(watch.unselected_attack_names,())
        peasant_help,=peasant.active_abilities
        self.assertEqual(peasant_help.name,'Torches and Pitchforks')
        self.assertIn('Melee attack',peasant_help.scope)
        self.assertIn('Do not Test',peasant_help.effect)
        self.assertIn('exceed',peasant_help.effect)
        whistle,=watch.inactive_abilities
        self.assertEqual(whistle.name,'Whistleblower')
        self.assertIn('chooses',whistle.scope)
        self.assertIn('Recover action',whistle.scope)
        self.assertEqual(whistle.effect,'More Town Watch arrive next turn; Athletics Tests to Retreat from them are Grim')
        numbers,=militia.active_abilities
        detachment,=militia.inactive_abilities
        self.assertEqual(numbers.name,'Strength in Numbers')
        self.assertIn('ally in Medium Range',numbers.scope)
        self.assertNotIn('Melee',numbers.scope)
        self.assertIn('+1d',numbers.effect)
        self.assertIn('exceed',numbers.effect)
        for scope in ('moves into Close Range of a State Trooper','Free Company Militia or State Trooper',
                'adjacent Zone','not in Close Range of an enemy'):
            self.assertIn(scope,detachment.scope)
        self.assertIn('immediately Charges or makes a ranged attack',detachment.effect)
        for entry in (peasant,watch,militia):
            self.assertEqual((entry.wound_bands,entry.unselected_protection), ((),()))
        self.assertEqual(watch.active_abilities,())

    def test_book_sources_cannot_change_printed_damage_protection_range_or_identity(self):
        for profile,_,_,_,_,_,_,damage,_,maximum,*_ in CASES:
            definition=get_pc_book_npc_entry(profile).definition
            attack,=definition.attacks
            protection,=definition.protection
            for forged in (replace(definition,attacks=(replace(attack,damage=DamageProfile(damage+1)),)),
                    replace(definition,attacks=(replace(attack,range_max=(RangedWeaponRange.CLOSE
                        if maximum is RangedWeaponRange.SHORT else RangedWeaponRange.SHORT)),)),
                    replace(definition,protection=(replace(protection,test_profile=InlineProfile(2,2)),)),
                    replace(definition,id='authored:renamed',source_rule_id='authored:source'),
                    replace(definition,id='authored:renamed',source_rule_id='authored:source',
                        attacks=(replace(attack,source_rule_id='authored:attack'),))):
                with self.subTest(profile=profile),self.assertRaises((TypeError,ValueError)):
                    validate_pc_book_npc_definition(forged)

    def test_fresh_graphs_and_equal_scalar_aliases_do_not_bypass_validation(self):
        for profile,*_ in CASES:
            first=create_pc_book_npc(profile,'first')
            second=create_pc_book_npc(profile,'second')
            self.assertIsNot(first.definition,second.definition)
            self.assertIsNot(first.state.injury,second.state.injury)
            object.__setattr__(first.definition.attacks[0].damage,'base',99)
            self.assertEqual(second.definition,get_pc_book_npc_entry(profile).definition)
            with self.assertRaises(ValueError):
                validate_pc_book_npc_definition(first.definition)
        definition=get_pc_book_npc_entry(PcBookNpcProfile.TOWN_WATCH_POLEARM).definition
        forged=deepcopy(definition)
        object.__setattr__(forged.resilience,'bonus',True)
        self.assertEqual(forged,definition)
        with self.assertRaises(TypeError):
            validate_pc_book_npc_definition(forged)

    def test_native_protection_preserves_printed_athletics_and_unshielded_equipment(self):
        for profile,keyword,actor,*_ in CASES:
            with self.subTest(profile=profile):
                result=execute(source(keyword),[1]*3+[10]*3)
                proof=next(s.proof for s in result.steps if type(s.proof) is PcAttackProof)
                self.assertIs(proof.protection.source_request.selected_skill,Skill.ATHLETICS)
                self.assertFalse(proof.protection.source_request.defender_holds_shield)
                self.assertEqual(proof.execution.resolution.attack.defender_test.trace.rolled_dice,3)
                self.assertTrue(result.state.enemy(actor).state.injury.defeated)
                self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)

    def test_actual_incoming_damage_does_not_gain_pc_weapon_traits_or_help_bonuses(self):
        for profile,keyword,actor,_,_,dice,_,damage,*_ in CASES:
            with self.subTest(profile=profile):
                result=execute(source(keyword),[10]*3+[1]*3+[10]*dice+[1]*3)
                proof=next(s.proof for s in result.steps if type(s.proof) is PcAttackProof
                    and s.proof.request.actor_id==actor)
                attack=proof.execution.resolution.attack
                self.assertEqual((attack.impact_spec.damage.base,attack.impact_spec.damage_modifiers),(damage,()))
                self.assertEqual(attack.attacker_test.trace.rolled_dice,dice)
                self.assertTrue(result.state.enemy(actor).state.injury.conditions.has(Condition.STAGGERED))
                self.assertIsNone(result.unsupported)

    def test_staggered_watch_still_attacks_without_recover_signal_or_spawn(self):
        result=execute(source('watch',rounds=2),([10]*3+[1]*3)*4)
        self.assertEqual(sum(type(s.proof) is PcAttackProof and
            s.proof.request.actor_id=='watch1' for s in result.steps),2)
        self.assertFalse(any(type(s.proof) is PcRecoverProof for s in result.steps))
        self.assertEqual(tuple(e.state.actor_id for e in result.state.enemies),('watch1',))
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
        self.assertIsNone(result.unsupported)


if __name__=='__main__':
    unittest.main()
