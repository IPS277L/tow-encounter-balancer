"""Initial Reason facts, never derived Aim bonuses, drive Careful Aim sources."""
from copy import deepcopy
from dataclasses import replace
import json
from random import Random
import unittest

from tests.support.oath_sources import context, honour
from tests.support.talent_sources import free_talent, paid_talent
from tests.unit.test_allies_in_arms_generation import space, FirstChoices, document
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.dynamic_encounter_json import parse_dynamic_encounter_request, DynamicEncounterInputError
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.application.generated_oath_sources import GeneratedOathSource
from towr.domain.generated_npc_models import generated_talent_requirements_met
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import TalentOwnerFacts


class CarefulAimGenerationTests(unittest.TestCase):
    def test_paid_purchase_requires_an_actual_initial_reason_of_four(self):
        for reason,expected in ((None,False),(3,False),(4,True),(5,True),(True,False),(0,False),('4',False)):
            with self.subTest(reason=reason):
                self.assertIs(generated_talent_requirements_met(TalentId.CAREFUL_AIM,
                    weapon_skill=3,strength=3,reason=reason),expected)

    def test_sample_stores_the_single_initial_fact_before_paid_selection(self):
        for reason in (3,4):
            search=space(reason=(reason,),allowed_talents=(TalentId.CAREFUL_AIM,))
            npc=search.sample(FirstChoices())
            self.assertEqual(npc.talent_facts,TalentOwnerFacts(reason=reason))
            self.assertEqual(npc.talents,(paid_talent(TalentId.CAREFUL_AIM),) if reason>=4 else ())
            self.assertFalse(hasattr(npc,'reason'))
            self.assertEqual(npc.participant('npc').definition.talent_facts,npc.talent_facts)
            self.assertTrue(search.contains(npc))

    def test_unused_reason_pool_does_not_change_existing_rng_consumption(self):
        left=space(reason=(1,2),allowed_talents=(TalentId.MAGIC_RESISTANCE,))
        right=replace(left,reason=(8,9))
        a,b=Random(42),Random(42)
        first,second=left.sample(a),right.sample(b)
        self.assertEqual(first,second)
        self.assertIsNone(first.talent_facts)
        self.assertEqual(a.getstate(),b.getstate())
        self.assertEqual(left.mutate(first,a),right.mutate(second,b))
        self.assertEqual(a.getstate(),b.getstate())
        self.assertEqual(left.resample_numeric((first,),a),right.resample_numeric((second,),b))
        self.assertEqual(a.getstate(),b.getstate())

    def test_mutation_and_numeric_resampling_readmit_paid_prerequisite(self):
        member=space(reason=(4,),allowed_talents=(TalentId.CAREFUL_AIM,)).sample(FirstChoices())
        search=space(reason=(3,4,5),allowed_talents=(TalentId.CAREFUL_AIM,))
        with self.assertRaises(ValueError):
            replace(member,talent_facts=TalentOwnerFacts(reason=3))
        for seed in range(4):
            changed=search.mutate(member,Random(seed))
            self.assertTrue(search.contains(changed))
            if changed.talents:
                self.assertGreaterEqual(changed.talent_facts.reason,4)
            numeric=search.resample_numeric((member,),Random(seed)).composition[0]
            self.assertEqual(numeric.talents,member.talents)
            self.assertGreaterEqual(numeric.talent_facts.reason,4)
            self.assertTrue(search.contains(numeric))

    def test_creation_free_waiver_and_other_initial_facts_survive_resampling(self):
        search=space(reason=(2,3,4),fellowship=(3,),allowed_talents=(TalentId.CAREFUL_AIM,))
        member=replace(space().sample(FirstChoices()),talents=(free_talent(TalentId.CAREFUL_AIM),),
            talent_facts=TalentOwnerFacts(reason=3,fellowship=3))
        changed=search.mutate(member,FirstChoices())
        self.assertEqual(changed.talents,member.talents)
        self.assertEqual(changed.talent_facts.reason,2)
        numeric=search.resample_numeric((member,),FirstChoices()).composition[0]
        self.assertEqual(numeric.talents,member.talents)
        self.assertEqual(numeric.talent_facts.reason,2)
        self.assertEqual(numeric.talent_facts.fellowship,3)

    def test_reason_pool_and_contains_reject_invalid_or_outside_facts(self):
        search=space(reason=(3,4))
        npc=replace(search.sample(FirstChoices()),talent_facts=TalentOwnerFacts(reason=5))
        self.assertFalse(search.contains(npc))
        corrupt=deepcopy(npc)
        object.__setattr__(corrupt.talent_facts,'reason',True)
        self.assertFalse(search.contains(corrupt))
        for invalid in ((),[],(True,4),(0,4),(3,3),('4',)):
            with self.subTest(reason=invalid),self.assertRaises((TypeError,ValueError)):
                space(reason=invalid)

    def test_declared_oath_reason_is_not_resampled_outside_its_actual_bundle(self):
        oath=GeneratedOathSource((honour(),),context(),TalentOwnerFacts(reason=4))
        search=space(reason=(3,4,5),allowed_oath_sources=(oath,))
        member=replace(search.sample(FirstChoices()),talents=oath.talents,
            oath_context=oath.context,talent_facts=oath.talent_facts)
        self.assertTrue(search.contains(member))
        numeric=search.resample_numeric((member,),FirstChoices()).composition[0]
        self.assertEqual(numeric,member)
        self.assertTrue(search.contains(numeric))

    def test_optional_current_json_range_default_and_automatic_envelope(self):
        raw=document()
        raw['search_space']['reason']=[4,5]
        raw['party'][0]['talent_facts']={'reason':6}
        parsed=parse_dynamic_encounter_request(json.dumps(raw))
        self.assertEqual(parsed.request.space.reason,(4,5))
        self.assertEqual(parsed.request.party[0].talent_facts.reason,6)
        raw['search_space']=None
        automatic=parse_dynamic_encounter_request(json.dumps(raw))
        self.assertEqual(automatic.request.space.reason,(5,6,7))
        raw=document()
        raw['search_space'].pop('reason',None)
        self.assertEqual(parse_dynamic_encounter_request(json.dumps(raw)).request.space.reason,(3,4,5))
        raw['search_space']['reason']=[True]
        with self.assertRaises(DynamicEncounterInputError):
            parse_dynamic_encounter_request(json.dumps(raw))

    def test_generated_initial_reason_and_purchase_roundtrip_current_native_json(self):
        raw=document()
        raw['search_space'].update(reason=[4],allowed_talents=['careful_aim'])
        parsed=parse_dynamic_encounter_request(json.dumps(raw))
        npc=parsed.request.space.sample(FirstChoices())
        self.assertEqual(npc.talents,(paid_talent(TalentId.CAREFUL_AIM),))
        source=parsed.request.scenario((npc,),'careful:source')
        request=dict(schema_version='1',kind='pc_melee_simulation',request_id='careful:wire',
            ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(source),
            simulation=dict(master_seed='42',trials=1),execution=dict(mode='sequential'))
        restored=parse_pc_melee_simulation_request(json.dumps(request)).request.scenario
        self.assertEqual(restored,source)
        self.assertEqual(restored.enemies[0].definition.talent_facts,TalentOwnerFacts(reason=4))


if __name__=='__main__':unittest.main()
