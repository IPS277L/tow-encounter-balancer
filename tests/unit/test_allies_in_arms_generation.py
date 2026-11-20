"""Real Fellowship prerequisite facts through generation and current source JSON."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from random import Random
import unittest

from tests.support.talent_sources import free_talent,paid_talent
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.dynamic_encounter_json import DynamicEncounterInputError,parse_dynamic_encounter_request
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.application.dynamic_encounter import NpcSearchSpace
from towr.domain.generated_npc_models import GeneratedWeapon,generated_talent_requirements_met
from towr.domain.talent_catalog import TalentId,TalentOrigin
from towr.domain.talent_models import TalentLoreFact,TalentOwnerFacts


class FirstChoices:
    def choice(self,values):
        return values[0]

    def randrange(self,stop):
        if stop!=2:
            raise AssertionError('the explicit source requires only binary Talent selections')
        return 1


def space(**changes):
    values=dict(weapon_skill=(3,),strength=(3,),toughness=(3,),agility=(3,),melee=(4,),
        athletics=(4,),defence=(4,),brawn=(4,),endurance=(4,),weapon_count=(1,),
        weapon=(GeneratedWeapon.SWORD,),armour=(None,),shield=(None,),abilities=((),),
        allowed_talents=())
    values.update(changes)
    return NpcSearchSpace(**values)


def document():
    raw=json.loads(Path('docs/examples/dynamic/talents.request.json').read_text(encoding='utf-8'))
    raw['party']=raw['party'][:1]
    raw['npc_count']=dict(minimum=1,maximum=1)
    raw['search_space']['allowed_talents']=[]
    return raw


class AlliesInArmsGenerationTests(unittest.TestCase):
    def test_paid_requirement_uses_fellowship_at_four_and_never_coerces_bad_facts(self):
        for value,expected in ((None,False),(3,False),(4,True),(5,True),(True,False),(0,False),('4',False)):
            with self.subTest(fellowship=value):
                self.assertIs(generated_talent_requirements_met(TalentId.ALLIES_IN_ARMS,
                    weapon_skill=3,strength=3,fellowship=value),expected)

    def test_sampling_creates_one_authoritative_fact_before_selecting_paid_talent(self):
        for value in (3,4):
            search=space(fellowship=(value,),allowed_talents=(TalentId.ALLIES_IN_ARMS,))
            npc=search.sample(FirstChoices())
            self.assertEqual(npc.talent_facts,TalentOwnerFacts(fellowship=value))
            self.assertEqual(npc.talents,(paid_talent(TalentId.ALLIES_IN_ARMS),) if value>=4 else ())
            self.assertTrue(search.contains(npc))
            self.assertEqual(npc.participant('npc').definition.talent_facts,npc.talent_facts)
            self.assertIsNone(npc.fellowship)

    def test_unused_ranges_leave_previous_sample_mutation_and_numeric_rng_paths_identical(self):
        left=space(fellowship=(1,2),allowed_talents=(TalentId.MAGIC_RESISTANCE,))
        right=replace(left,fellowship=(8,9))
        a,b=Random(42),Random(42)
        first,second=left.sample(a),right.sample(b)
        self.assertEqual(first,second)
        self.assertEqual(a.getstate(),b.getstate())
        self.assertIsNone(first.talent_facts)
        self.assertEqual(left.mutate(first,a),right.mutate(second,b))
        self.assertEqual(a.getstate(),b.getstate())
        self.assertEqual(left.resample_numeric((first,),a),right.resample_numeric((second,),b))
        self.assertEqual(a.getstate(),b.getstate())

    def test_existing_full_facts_survive_weapon_mutation_and_only_fellowship_is_resampled(self):
        search=space(weapon=(GeneratedWeapon.SWORD,GeneratedWeapon.DAGGER),fellowship=(2,3,4))
        original=search.sample(FirstChoices())
        facts=TalentOwnerFacts(fellowship=3,reason=6,origin=TalentOrigin.HUMAN,
            lores=(TalentLoreFact('anatomy'),))
        original=replace(original,talent_facts=facts)
        mutated=search.mutate(original,FirstChoices())
        self.assertNotEqual(mutated.weapons,original.weapons)
        self.assertEqual(mutated.talent_facts,facts)
        resampled=search.resample_numeric((original,),FirstChoices()).composition[0]
        self.assertEqual(resampled.talent_facts.fellowship,2)
        self.assertEqual(replace(resampled.talent_facts,fellowship=3),facts)

    def test_paid_mutation_and_numeric_sampling_cannot_keep_talent_below_four(self):
        fixed=space(fellowship=(4,),allowed_talents=(TalentId.ALLIES_IN_ARMS,))
        member=fixed.sample(FirstChoices())
        search=replace(fixed,fellowship=(3,4,5))
        with self.assertRaises(ValueError):
            replace(member,talent_facts=replace(member.talent_facts,fellowship=3))
        for seed in range(8):
            mutated=search.mutate(member,Random(seed))
            self.assertTrue(search.contains(mutated))
            if mutated.talents:
                self.assertGreaterEqual(mutated.talent_facts.fellowship,4)
            numeric=search.resample_numeric((member,),Random(seed)).composition[0]
            self.assertEqual(numeric.talents,member.talents)
            self.assertGreaterEqual(numeric.talent_facts.fellowship,4)

    def test_explicit_creation_free_acquisition_keeps_its_waiver_during_mutation(self):
        search=space(fellowship=(2,3,4),allowed_talents=(TalentId.ALLIES_IN_ARMS,))
        base=space(fellowship=(3,)).sample(FirstChoices())
        member=replace(base,talents=(free_talent(TalentId.ALLIES_IN_ARMS),),
            talent_facts=TalentOwnerFacts(fellowship=3))
        self.assertTrue(search.contains(member))
        mutated=search.mutate(member,FirstChoices())
        self.assertEqual(mutated.talent_facts.fellowship,2)
        self.assertEqual(mutated.talents,member.talents)
        numeric=search.resample_numeric((member,),FirstChoices()).composition[0]
        self.assertEqual(numeric.talent_facts.fellowship,2)
        self.assertEqual(numeric.talents,member.talents)

    def test_contains_and_range_admission_reject_outside_or_cached_boolean_facts(self):
        search=space(fellowship=(3,4))
        npc=replace(search.sample(FirstChoices()),talent_facts=TalentOwnerFacts(fellowship=5))
        self.assertFalse(search.contains(npc))
        corrupt=deepcopy(npc)
        object.__setattr__(corrupt.talent_facts,'fellowship',True)
        self.assertFalse(search.contains(corrupt))
        for invalid in ((),[],(True,4),(0,4),(3,3),('4',)):
            with self.subTest(fellowship=invalid),self.assertRaises((TypeError,ValueError)):
                space(fellowship=invalid)

    def test_current_dynamic_wire_has_optional_range_and_keeps_pc_fellowship_in_facts(self):
        raw=document()
        raw['search_space']['fellowship']=[4,5]
        raw['party'][0]['talent_facts']={'fellowship':5}
        parsed=parse_dynamic_encounter_request(json.dumps(raw))
        self.assertEqual(parsed.request.space.fellowship,(4,5))
        self.assertEqual(parsed.request.party[0].talent_facts.fellowship,5)
        raw['search_space']=None
        automatic=parse_dynamic_encounter_request(json.dumps(raw))
        self.assertEqual(automatic.request.space.fellowship,(4,5,6))
        raw=document()
        raw['search_space'].pop('fellowship',None)
        self.assertEqual(parse_dynamic_encounter_request(json.dumps(raw)).request.space.fellowship,(2,3,4))

    def test_generated_fellowship_and_acquisition_survive_current_native_source_roundtrip(self):
        raw=document()
        raw['search_space'].update(fellowship=[4],allowed_talents=['allies_in_arms'])
        parsed=parse_dynamic_encounter_request(json.dumps(raw))
        npc=parsed.request.space.sample(FirstChoices())
        self.assertEqual(npc.talents,(paid_talent(TalentId.ALLIES_IN_ARMS),))
        source=parsed.request.scenario((npc,),'allies-source')
        request=dict(schema_version='1',kind='pc_melee_simulation',request_id='allies:wire',
            ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(source),
            simulation=dict(master_seed='42',trials=1),execution=dict(mode='sequential'))
        replay=parse_pc_melee_simulation_request(json.dumps(request))
        self.assertEqual(replay.request.scenario,source)
        self.assertEqual(replay.request.scenario.enemies[0].definition.talent_facts,TalentOwnerFacts(fellowship=4))


if __name__=='__main__':
    unittest.main()
