"""Current source/wire round trips; no simulation or fabricated GM defaults."""
from copy import deepcopy
import json
from pathlib import Path
from random import Random
import unittest

from tests.support.oath_sources import context, honour, lady, source
from towr.adapters._oath_json import oath_context_document, generated_oath_sources_document
from towr.adapters._pc_melee_scenario_json import scenario_document, generated_components_document
from towr.adapters._talent_json import acquired_talents_document, talent_owner_facts_document
from towr.adapters.character_files import parse_character_file
from towr.adapters.dynamic_encounter_json import parse_dynamic_encounter_request, DynamicEncounterInputError
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.domain.talent_catalog import TalentId


def request_document():
    document=json.loads(Path('docs/examples/dynamic/talents.request.json').read_text(encoding='utf-8'))
    document['party']=document['party'][:1]
    member=document['party'][0]
    member['talents']=acquired_talents_document((honour(),lady()))
    member['oath_context']=oath_context_document(context())
    member['talent_facts']=talent_owner_facts_document(source().talent_facts)
    document['search_space']['allowed_talents']=[]
    document['search_space']['allowed_oath_sources']=generated_oath_sources_document((source(),))
    document['npc_count']={'minimum':1,'maximum':1}
    return document


class OathSourceJsonTests(unittest.TestCase):
    def test_dynamic_native_and_individual_files_retain_gm_context(self):
        raw=request_document()
        parsed=parse_dynamic_encounter_request(json.dumps(raw))
        self.assertEqual(parsed.request.party[0].oath_context,context())
        self.assertEqual(parsed.request.space.allowed_oath_sources,(source(),))
        npc=next(value for value in (parsed.request.space.sample(Random(seed)) for seed in range(20))
            if value.oath_context is not None)
        native=parsed.request.scenario((npc,),'oath-source')
        # Use the actual current native envelope from a shipped request.
        envelope=json.loads(Path('docs/examples/m70/pc-melee-simulation.request.json').read_text(encoding='utf-8'))
        envelope['scenario']=scenario_document(native)
        envelope['simulation']['trials']=1
        again=parse_pc_melee_simulation_request(json.dumps(envelope))
        scenario=again.request.scenario
        self.assertEqual(scenario.party[0].oath_context,context())
        self.assertEqual(scenario.enemies[0].definition.generated_components.oath_context,context())
        self.assertEqual(parse_character_file(json.dumps(raw['party'][0]),'player')['oath_context'],raw['party'][0]['oath_context'])
        npc_wire=generated_components_document(npc)
        self.assertEqual(parse_character_file(json.dumps(npc_wire),'npc')['oath_context'],npc_wire['oath_context'])

    def test_explicit_unmitigated_scope_survives_pc_and_generated_source_json(self):
        raw=request_document()
        raw['party'][0]['oath_context']['unmitigated_success_scope_confirmed']=True
        raw['search_space']['allowed_oath_sources'][0]['context']['unmitigated_success_scope_confirmed']=True
        parsed=parse_dynamic_encounter_request(json.dumps(raw))
        self.assertTrue(parsed.request.party[0].oath_context.unmitigated_success_scope_confirmed)
        self.assertTrue(parsed.request.space.allowed_oath_sources[0].context.unmitigated_success_scope_confirmed)
        npc=next(value for value in (parsed.request.space.sample(Random(seed)) for seed in range(20))
            if value.oath_context is not None)
        document=generated_components_document(npc)
        self.assertTrue(parse_character_file(json.dumps(document),'npc')['oath_context']['unmitigated_success_scope_confirmed'])
        raw['party'][0]['oath_context']['unmitigated_success_scope_confirmed']=1
        with self.assertRaises(DynamicEncounterInputError):
            parse_dynamic_encounter_request(json.dumps(raw))

    def test_bad_context_and_unapproved_oath_identity_fail_before_trials(self):
        for path,value in (('oath_id','wrong'),('gm_confirmation_id',''),('unknown',True),
                ('combat_tests_fulfil_oath_confirmed',1)):
            raw=request_document()
            raw['party'][0]['oath_context'][path]=value
            with self.subTest(path=path),self.assertRaises(DynamicEncounterInputError):
                parse_dynamic_encounter_request(json.dumps(raw))
        raw=request_document()
        del raw['party'][0]['oath_context']
        with self.assertRaises(DynamicEncounterInputError):
            parse_character_file(json.dumps(raw['party'][0]),'player')

    def test_bare_generated_oath_talent_is_not_an_implicit_gm_source(self):
        raw=request_document()
        raw['search_space']['allowed_talents']=['honour_bound']
        with self.assertRaises(DynamicEncounterInputError):
            parse_dynamic_encounter_request(json.dumps(raw))
        raw=request_document()
        raw['search_space']['allowed_oath_sources'][0]['context']['oath_id']='other'
        with self.assertRaises(DynamicEncounterInputError):
            parse_dynamic_encounter_request(json.dumps(raw))


if __name__=='__main__':
    unittest.main()
