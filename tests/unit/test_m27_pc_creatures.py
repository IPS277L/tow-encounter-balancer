"""GM135–137 and PG97: real natural attacks, Protection and armour semantics."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.attack_models import DamageProfile,ResilienceProfile
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_melee_result_models import PcAttackProof,PcMeleeStep
from towr.domain.pc_npc_catalog import (
    PcBookNpcProfile,create_pc_book_npc,get_pc_book_npc_entry,validate_pc_book_npc_definition,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import InlineProfile,Skill
from towr.engine.pc_melee_runner import apply_pc_melee_step,run_pc_melee_scenario


CASES=(
    (PcBookNpcProfile.HORSE,'horses','horse1',135,'hooves',3,4,4,0),
    (PcBookNpcProfile.GIANT_WOLF,'wolves','wolf1',136,'clamping_jaws',3,4,4,0),
    (PcBookNpcProfile.GIANT_BOAR,'boars','boar1',137,'goring_tusks',4,3,3,2),
)


def scene(keyword):
    return book_pc_scenario(**{keyword:1},footpads=0,townsfolk=0,pc_count=1,max_rounds=1)


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


class PcCreatureTests(unittest.TestCase):
    def test_printed_natural_profiles_and_fresh_state_have_no_fictitious_weapon(self):
        for profile,keyword,actor,page,attack_id,threshold,pdice,pthreshold,armour in CASES:
            with self.subTest(profile=profile):
                entry=get_pc_book_npc_entry(profile)
                definition=entry.definition
                source=f'BOOK-GM-GUIDE:1.1:p{page}:{profile.value}'
                self.assertEqual((entry.book_id,entry.version,entry.chapter,entry.page),
                    ('BOOK-GM-GUIDE','1.1','Allies and Antagonists',page))
                self.assertEqual((definition.id,definition.source_rule_id,definition.injury_policy,
                    definition.wound_limit,definition.resilience),
                    ('pc-book-npc:'+profile.value,source,TargetInjuryPolicy.MINION,1,ResilienceProfile(3,armour)))
                attack,=definition.attacks
                self.assertEqual((attack.id,attack.source_rule_id,attack.skill,attack.test_profile,
                    attack.damage,attack.hands,attack.ignores_armour,attack.secondary_effects),
                    (attack_id,source+':'+attack_id,Skill.MELEE,InlineProfile(3,threshold),
                     DamageProfile(3),None,False,()))
                protection,=definition.protection
                self.assertEqual((protection.skill,protection.test_profile),
                    (Skill.ATHLETICS,InlineProfile(pdice,pthreshold)))
                snapshot=create_pc_book_npc(profile,actor)
                self.assertEqual((snapshot.state.wields_weapon,snapshot.state.holds_shield,
                    snapshot.state.available_attack_ids,snapshot.state.injury.wounds),
                    (False,False,(attack_id,),0))
                validate_pc_book_npc_definition(definition)
                self.assertEqual(scene(keyword).enemies[0],snapshot)

    def test_mount_variants_and_charge_conditions_are_explicitly_outside_the_chunk(self):
        horse=get_pc_book_npc_entry(PcBookNpcProfile.HORSE)
        wolf=get_pc_book_npc_entry(PcBookNpcProfile.GIANT_WOLF)
        boar=get_pc_book_npc_entry(PcBookNpcProfile.GIANT_BOAR)
        self.assertEqual(horse.unselected_variant_names,
            ('Bretonnian Warhorse','Elven Steed','Skeletal Steed'))
        self.assertEqual(horse.active_abilities,())
        self.assertEqual(horse.inactive_abilities[0].name,'Noble Steed')
        self.assertIn('non-Monstrosity',horse.inactive_abilities[0].effect)
        self.assertEqual(wolf.active_abilities[0].name,'Clamping Jaws')
        self.assertEqual(wolf.active_abilities[0].effect,'Target cannot Give Ground')
        self.assertEqual(wolf.inactive_abilities[0].name,'Goblin Wolf Rider')
        self.assertEqual(boar.active_abilities,())
        self.assertEqual(tuple(ability.name for ability in boar.inactive_abilities),
            ('Goring Tusks on Charge','Orc Boar Boyz'))
        self.assertIn('+1d Melee and +1 Damage',boar.inactive_abilities[0].effect)
        for entry in (wolf,boar):
            self.assertEqual(entry.unselected_variant_names,())

    def test_actual_athletics_protection_sees_unarmed_natural_target(self):
        for profile,keyword,actor,page,attack_id,threshold,pdice,pthreshold,armour in CASES:
            with self.subTest(profile=profile):
                result=execute(scene(keyword),[1]*3+[10]*pdice)
                proof=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof)
                request=proof.protection.source_request
                self.assertIs(request.selected_skill,Skill.ATHLETICS)
                self.assertFalse(request.defender_wields_weapon)
                self.assertFalse(request.defender_holds_shield)
                defender=proof.execution.resolution.attack.defender_test
                self.assertEqual((defender.trace.rolled_dice,defender.trace.threshold),(pdice,pthreshold))
                self.assertTrue(result.state.enemy(actor).state.injury.defeated)

    def test_armed_pc_uses_defence_against_printed_natural_melee_without_charge_bonus(self):
        for profile,keyword,actor,page,attack_id,threshold,pdice,pthreshold,armour in CASES:
            with self.subTest(profile=profile):
                result=execute(scene(keyword),[10]*3+[1]*pdice+[1]*3+[10]*3+[1])
                proof=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof
                    and step.proof.request.actor_id==actor)
                self.assertIs(proof.protection.source_request.attack_skill,Skill.MELEE)
                self.assertIs(proof.protection.source_request.selected_skill,Skill.DEFENCE)
                self.assertTrue(proof.protection.source_request.defender_wields_weapon)
                attack=proof.execution.resolution.attack
                self.assertEqual((attack.attacker_test.trace.rolled_dice,attack.attacker_test.trace.threshold,
                    attack.impact_spec.damage.base,attack.impact_spec.damage_modifiers),(3,threshold,3,()))

    def test_wolf_ban_changes_actual_kernel_only_when_wolf_attacks(self):
        for profile,keyword,actor,page,attack_id,threshold,pdice,pthreshold,armour in CASES:
            with self.subTest(profile=profile):
                source=scene(keyword)
                source=replace(source,facts=replace(source.facts,can_leave_zone=True))
                result=execute(source,[10]*3+[1]*pdice+[10]*3+[1]*3)
                attacks=tuple(step for step in result.steps if type(step.proof) is PcAttackProof)
                self.assertTrue(attacks[0].proof.request.kernel_request.can_target_leave_zone)
                incoming=attacks[1]
                self.assertEqual(incoming.proof.request.kernel_request.can_target_leave_zone,
                    profile is not PcBookNpcProfile.GIANT_WOLF)
                if profile is PcBookNpcProfile.GIANT_WOLF:
                    forged=replace(incoming.proof,request=replace(incoming.proof.request,
                        kernel_request=replace(incoming.proof.request.kernel_request,can_target_leave_zone=True)))
                    with self.assertRaises(ValueError):
                        apply_pc_melee_step(PcMeleeStep(incoming.source,forged))

    def test_boar_natural_armour_receives_normal_pc_axe_bonus(self):
        source=scene('boars')
        member=source.party[0]
        source=replace(source,party=(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.AXE)),))
        result=execute(source,[1]*3+[1,10,10])
        proof=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof)
        attack=proof.execution.resolution.attack
        self.assertEqual((attack.damage,attack.effective_resilience),(6,5))
        self.assertEqual(len(attack.impact_spec.damage_modifiers),1)
        self.assertEqual(attack.impact_spec.damage_modifiers[0].amount,1)
        self.assertFalse(attack.impact_spec.ignores_armour)
        self.assertTrue(result.state.enemy('boar1').state.injury.defeated)

    def test_book_identity_cannot_be_relabelled_as_a_held_weapon_or_different_protection(self):
        for profile,*_ in CASES:
            definition=get_pc_book_npc_entry(profile).definition
            attack,=definition.attacks
            protection,=definition.protection
            invalid=(replace(definition,attacks=(replace(attack,hands=RangedWeaponHands.ONE_HANDED),)),
                replace(definition,protection=(replace(protection,skill=Skill.DEFENCE),)),
                replace(definition,id='authored:fake',source_rule_id='authored:fake'),
                replace(definition,id='authored:fake',source_rule_id='authored:fake',
                    attacks=(replace(attack,source_rule_id='authored:attack'),)))
            for candidate in invalid:
                with self.subTest(profile=profile),self.assertRaises((TypeError,ValueError)):
                    validate_pc_book_npc_definition(candidate)
            forged=deepcopy(definition)
            object.__setattr__(forged.resilience,'bonus',bool(forged.resilience.bonus))
            if forged==definition:
                with self.assertRaises(TypeError):
                    validate_pc_book_npc_definition(forged)

    def test_fresh_creature_graphs_do_not_share_bypass_mutations(self):
        for profile,*_ in CASES:
            first=create_pc_book_npc(profile,'first')
            second=create_pc_book_npc(profile,'second')
            self.assertIsNot(first.definition,second.definition)
            self.assertIsNot(first.state.injury,second.state.injury)
            object.__setattr__(first.definition.attacks[0].damage,'base',99)
            self.assertEqual(second.definition.attacks[0].damage,DamageProfile(3))
            self.assertEqual(get_pc_book_npc_entry(profile).definition.attacks[0].damage,DamageProfile(3))
            with self.assertRaises(ValueError):
                validate_pc_book_npc_definition(first.definition)


if __name__=='__main__':
    unittest.main()
