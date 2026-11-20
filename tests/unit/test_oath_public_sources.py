"""C19 ownership, one current codec and finite explicit Oath source generation.

Generation tests temporarily admit the two identities to isolate sampling
from the separate native execution cap. They do not assert combat execution.
"""
from dataclasses import replace
from random import Random
import unittest

from towr.adapters._oath_json import (
    parse_oath_context, oath_context_document, parse_generated_oath_sources, generated_oath_sources_document,
)
from towr.adapters.dynamic_encounter_json import DynamicEncounterInputError
from towr.application.dynamic_encounter import NpcSearchSpace
from towr.application.generated_oath_sources import GeneratedOathSource, merge_oath_facts
from towr.domain.generated_npc_models import GeneratedWeapon
from towr.domain.oath_context_models import OathBattleContext, validate_oath_context
from towr.domain.ranged_weapon_profiles import RangedWeaponHands
from towr.domain.talent_catalog import TalentId, TalentOrigin
from towr.domain.talent_models import (
    AcquiredTalent, OathChoice, TalentAcquisition, TalentAcquisitionPhase, TalentFunding,
    TalentLoreFact, TalentOwnerFacts,
)
from towr.domain.test_models import Skill


from tests.support.oath_sources import honour, lady, context, source

def fixed_space(sources):
    return NpcSearchSpace(weapon_skill=(3,), strength=(3,), toughness=(3,), agility=(3,),
        melee=(4,), athletics=(4,), defence=(4,), weapon=(GeneratedWeapon.DAGGER,), weapon_count=(1,),
        armour=(None,), shield=(None,), allowed_talents=(), allowed_oath_sources=sources,
        ballistic_skill=(3,), shooting=(4,), initiative=(3,), fellowship=(3,), leadership=(4,),
        dexterity=(4,), awareness=(4,), throwing=(4,), brawn=(4,), endurance=(4,),
        weapon_grip=(RangedWeaponHands.ONE_HANDED,))


class OathContextSourceTests(unittest.TestCase):
    def test_exact_context_and_matching_full_ownership(self):
        acquired=(honour(), lady())
        validate_oath_context(acquired, context())
        for changes in ({'oath_id':'different'}, {'oath_id':None}):
            with self.assertRaises(ValueError):
                validate_oath_context(acquired, replace(context(), **changes))
        with self.assertRaises(ValueError):
            validate_oath_context(acquired, None)
        with self.assertRaises(ValueError):
            validate_oath_context((), context())
        for field in ('in_good_standing_confirmed','combat_tests_fulfil_oath_confirmed',
                'fleeing_breaks_oath','lady_prayer_before_battle_confirmed','honour_bound_used_this_session','unmitigated_success_scope_confirmed'):
            with self.subTest(field=field), self.assertRaises(TypeError):
                replace(context(), **{field:1})

    def test_free_lady_does_not_invent_missing_honour_bound_or_session_use(self):
        acquired=(lady(free=True),)
        actual=OathBattleContext('gm:lady', True, lady_prayer_before_battle_confirmed=True)
        validate_oath_context(acquired, actual)
        for change in ({'oath_id':'invented'}, {'honour_bound_used_this_session':True},
                {'unmitigated_success_scope_confirmed':True}):
            with self.assertRaises(ValueError):
                validate_oath_context(acquired,replace(actual,**change))
        with self.assertRaises(ValueError):
            validate_oath_context((honour(),),context(lady_prayer_before_battle_confirmed=True))

    def test_restrictions_and_bad_prebattle_source_are_rejected(self):
        for skills in ((Skill.MELEE, Skill.MELEE),(Skill.LEADERSHIP,),('shooting',),[Skill.MELEE]):
            with self.subTest(skills=skills), self.assertRaises(ValueError):
                replace(context(),forbidden_attack_skills=skills)
        with self.assertRaises(ValueError):
            OathBattleContext('gm:barred',False,lady_prayer_before_battle_confirmed=True)

    def test_closed_context_codec_round_trips_without_coercing_confirmations(self):
        expected=context(honour_bound_used_this_session=True,unmitigated_success_scope_confirmed=True)
        document=oath_context_document(expected)
        self.assertEqual(parse_oath_context(document,path='/oath_context',error_type=DynamicEncounterInputError),expected)
        for changes in ({'unknown':True},{'in_good_standing_confirmed':1},
                {'forbidden_attack_skills':['willpower']},{'gm_confirmation_id':''}):
            with self.subTest(changes=changes), self.assertRaises(DynamicEncounterInputError):
                parse_oath_context(document|changes,path='/oath_context',error_type=DynamicEncounterInputError)

    def test_explicit_source_validates_requirements_and_round_trips(self):
        expected=source()
        wire=generated_oath_sources_document((expected,))
        self.assertEqual(parse_generated_oath_sources(wire,path='/sources',error_type=DynamicEncounterInputError),(expected,))
        with self.assertRaises(ValueError):
            replace(expected,talent_facts=TalentOwnerFacts())
        with self.assertRaises(TypeError):
            replace(expected,talents=(AcquiredTalent(TalentId.WILD_ATTACK,(TalentAcquisition(
                TalentAcquisitionPhase.CREATION,TalentFunding.FREE),)),))
        with self.assertRaises(ValueError):
            replace(expected,context=replace(expected.context,oath_id='other'))

    def test_unmitigated_scope_requires_an_independent_explicit_confirmation(self):
        ordinary=context()
        self.assertTrue(ordinary.combat_tests_fulfil_oath_confirmed)
        self.assertFalse(ordinary.unmitigated_success_scope_confirmed)
        document=oath_context_document(ordinary)
        del document['unmitigated_success_scope_confirmed']
        parsed=parse_oath_context(document,path='/context',error_type=DynamicEncounterInputError)
        self.assertFalse(parsed.unmitigated_success_scope_confirmed)
        self.assertFalse(ordinary.unmitigated_success_scope_confirmed)
        with self.assertRaises(DynamicEncounterInputError):
            parse_oath_context(document|{'unmitigated_success_scope_confirmed':1},
                path='/context',error_type=DynamicEncounterInputError)
        allowed=replace(source(),context=replace(source().context,unmitigated_success_scope_confirmed=True))
        wire=generated_oath_sources_document((allowed,))
        again=parse_generated_oath_sources(wire,path='/sources',error_type=DynamicEncounterInputError)
        self.assertTrue(again[0].context.unmitigated_success_scope_confirmed)
        self.assertFalse(source().context.unmitigated_success_scope_confirmed)

    def test_merging_never_reclassifies_a_declared_lore(self):
        existing=TalentOwnerFacts(lores=(TalentLoreFact('music'),),fellowship=3)
        merged=merge_oath_facts(existing,source().talent_facts)
        self.assertEqual(merged.lores,(TalentLoreFact('music'),TalentLoreFact('high_society')))
        self.assertEqual(existing.lores,(TalentLoreFact('music'),))
        with self.assertRaises(ValueError):
            merge_oath_facts(existing,TalentOwnerFacts(lores=(TalentLoreFact('music',True),)))
        with self.assertRaises(ValueError):
            merge_oath_facts(existing,TalentOwnerFacts(fellowship=4))


class OathGenerationTests(unittest.TestCase):

    def test_no_source_means_no_arbitrary_oath_or_confirmation(self):
        space=fixed_space(())
        for seed in range(5):
            npc=space.sample(Random(seed))
            self.assertIsNone(npc.oath_context)
            self.assertEqual(npc.talents,())
        with self.assertRaises(ValueError):
            replace(space,allowed_talents=(TalentId.HONOUR_BOUND,))

    def test_sampling_and_mutation_use_whole_explicit_sources(self):
        declared=source()
        space=fixed_space((declared,))
        samples=[space.sample(Random(seed)) for seed in range(16)]
        self.assertTrue(any(npc.oath_context is None for npc in samples))
        self.assertTrue(any(npc.oath_context is not None for npc in samples))
        for npc in samples:
            self.assertTrue(space.contains(npc))
            if npc.oath_context is not None:
                self.assertEqual(npc.talents,declared.talents)
                self.assertEqual(npc.oath_context,declared.context)
                self.assertEqual(npc.talent_facts,declared.talent_facts)
        owned=next(npc for npc in samples if npc.oath_context is not None)
        removed=space.mutate(owned,Random(3))
        self.assertIsNone(removed.oath_context)
        self.assertEqual(removed.talents,())
        restored=space.mutate(removed,Random(3))
        self.assertEqual(restored.oath_context,declared.context)
        self.assertEqual(restored.talents,declared.talents)
        self.assertFalse(replace(space,allowed_oath_sources=()).contains(owned))

    def test_declared_characteristics_remain_bound_to_the_allowed_source(self):
        declared=replace(source(full=False),talent_facts=TalentOwnerFacts(weapon_skill=3))
        space=replace(fixed_space((declared,)),weapon_skill=(2,3))
        for seed in range(12):
            npc=space.sample(Random(seed))
            if npc.oath_context is not None:
                self.assertEqual(npc.weapon_skill,3)
                self.assertFalse(space.contains(replace(npc,talent_facts=replace(npc.talent_facts,weapon_skill=None))))
        with self.assertRaises(ValueError):
            replace(space,weapon_skill=(2,))


if __name__=='__main__':
    unittest.main()
