"""Now You See Me grants opposition from its full source, never a free Skill override."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
from itertools import product
import unittest

from tests.unit.test_k1_protection_preparation import request
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.pc_npc_catalog import PcBookNpcProfile,create_pc_book_npc
from towr.domain.protection_models import (
    HalflingStealthProtectionPermission,NOW_YOU_SEE_ME_RULE_ID,
    ProtectionTestOption,UnopposedReason,
)
from towr.domain.test_models import DiceModifier,InlineProfile,Skill,TestRequest
from towr.rules.protection_preparation import prepare_protection
from towr.rules.test_resolution import resolve_test


def permission(actor='target'):
    return HalflingStealthProtectionPermission(actor,
        create_pc_book_npc(PcBookNpcProfile.HALFLING_THIEF_DAGGER,actor).definition)


def stealth_request(**changes):
    values=dict(selected_skill=Skill.STEALTH,
        options=(ProtectionTestOption('target',Skill.STEALTH,TestRequest('stealth',InlineProfile(3,5))),),
        halfling_stealth_permission=permission())
    values.update(changes)
    return request(**values)


class HalflingProtectionTests(unittest.TestCase):
    def test_aware_attacks_allow_stealth_independent_of_weapon_shield_and_range(self):
        for skill,armed,shield,close in product(
                (Skill.MELEE,Skill.BRAWN,Skill.THROWING,Skill.SHOOTING),(False,True),(False,True),(False,True)):
            with self.subTest(skill=skill,armed=armed,shield=shield,close=close):
                base=request().attack
                source=stealth_request(attack_skill=skill,defender_wields_weapon=armed,
                    defender_holds_shield=shield,attack=replace(base,is_close_range=close))
                result=prepare_protection(source)
                self.assertIn(Skill.STEALTH,result.eligible_skills)
                self.assertIs(result.attack.defender_test,source.options[0].test)
                self.assertEqual(result.applied_rule_ids[-1],NOW_YOU_SEE_ME_RULE_ID)
                self.assertEqual(result.applied_rule_ids.count(NOW_YOU_SEE_ME_RULE_ID),1)

    def test_unaware_and_defenceless_take_precedence_without_opposition_or_ability_trace(self):
        for aware,defenceless,reasons in ((False,False,(UnopposedReason.UNAWARE,)),
                (True,True,(UnopposedReason.DEFENCELESS,)),
                (False,True,(UnopposedReason.UNAWARE,UnopposedReason.DEFENCELESS))):
            result=prepare_protection(stealth_request(defender_is_aware=aware,
                defender_is_defenceless=defenceless,selected_skill=None,options=()))
            self.assertIsNone(result.attack.defender_test)
            self.assertEqual(result.unopposed_reasons,reasons)
            self.assertNotIn(NOW_YOU_SEE_ME_RULE_ID,result.applied_rule_ids)
            with self.assertRaises(ValueError):
                stealth_request(defender_is_aware=aware,defender_is_defenceless=defenceless)

    def test_stealth_representation_is_insufficient_without_exact_permission(self):
        for value in (None,True,NOW_YOU_SEE_ME_RULE_ID,permission('another')):
            with self.subTest(value=value),self.assertRaises((TypeError,ValueError)):
                stealth_request(halfling_stealth_permission=value)

    def test_other_npc_and_modified_or_renamed_full_sources_cannot_grant_ability(self):
        definition=permission().definition
        other=create_pc_book_npc(PcBookNpcProfile.FOOTPAD,'target').definition
        altered=replace(definition,attacks=(replace(definition.attacks[0],
            test_profile=InlineProfile(3,3)),))
        renamed=replace(definition,id='authored:thief',source_rule_id='authored:source')
        for value in (other,altered,renamed):
            with self.subTest(value=value.id),self.assertRaises((TypeError,ValueError)):
                HalflingStealthProtectionPermission('target',value)

    def test_numeric_base_is_bound_while_modifiers_remain_explicit(self):
        for profile in (InlineProfile(2,5),InlineProfile(3,4),InlineProfile(3,5,6)):
            with self.subTest(profile=profile),self.assertRaises(ValueError):
                stealth_request(options=(ProtectionTestOption('target',Skill.STEALTH,
                    TestRequest('stealth',profile)),))
        test=TestRequest('stealth',InlineProfile(3,5),(DiceModifier('explicit:penalty',-1),))
        result=prepare_protection(stealth_request(options=(ProtectionTestOption('target',Skill.STEALTH,test),)))
        self.assertIs(result.attack.defender_test,test)
        self.assertEqual(test.profile.maximum_dice,6)

    def test_permission_does_not_force_stealth_or_add_its_trace_to_another_skill(self):
        source=request(halfling_stealth_permission=permission())
        result=prepare_protection(source)
        self.assertIn(Skill.STEALTH,result.eligible_skills)
        self.assertIs(result.attack.defender_test,source.options[0].test)
        self.assertNotIn(NOW_YOU_SEE_ME_RULE_ID,result.applied_rule_ids)

    def test_stealth_uses_ordinary_cap_and_explicit_uncapped_bonus_without_extra_rolls(self):
        test=TestRequest('stealth',InlineProfile(3,5),(
            DiceModifier('ordinary:bonus',10),DiceModifier('explicit:help',1,True)))
        prepared=prepare_protection(stealth_request(options=(ProtectionTestOption('target',Skill.STEALTH,test),)))
        rng=ScriptedD10([1,2,3,4,5,6,7])
        result=resolve_test(prepared.attack.defender_test,rng)
        rng.assert_exhausted()
        self.assertEqual(result.trace.rolled_dice,7)
        self.assertEqual(result.successes,5)

    def test_cached_equal_aliases_and_retargeted_permission_are_readmitted(self):
        class Alias(str,Enum):
            TARGET='target'
        for value in (Alias.TARGET,'another'):
            source=deepcopy(stealth_request())
            object.__setattr__(source.halfling_stealth_permission,'defender_id',value)
            with self.subTest(value=value),self.assertRaises((TypeError,ValueError)):
                prepare_protection(source)
        source=deepcopy(stealth_request())
        object.__setattr__(source.halfling_stealth_permission.definition.resilience,'toughness',True)
        with self.assertRaises((TypeError,ValueError)):
            prepare_protection(source)

    def test_result_cannot_drop_the_applied_source_trace(self):
        result=prepare_protection(stealth_request())
        with self.assertRaises(ValueError):
            replace(result,applied_rule_ids=result.applied_rule_ids[:-1])
