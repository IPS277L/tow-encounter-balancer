"""Current component source, strict native replay and the real generator boundary."""
from copy import deepcopy
import json
from pathlib import Path
from random import Random
import unittest

from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.character_files import parse_character_file
from towr.adapters.dynamic_encounter_json import (
    DynamicEncounterInputError, parse_dynamic_encounter_request,
    execute_dynamic_encounter, encode_dynamic_encounter_result,
)
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.adapters.pc_melee_json_errors import PcMeleeInputError
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def equipment_request():
    document=json.loads(Path('docs/examples/dynamic/search.request.json').read_text(encoding='utf-8'))
    document['party']=document['party'][:1]
    document['npc_count']=dict(minimum=1,maximum=1)
    document['max_rounds']=1
    document['targets']['started_rounds']=dict(numerator=1,denominator=1)
    document['search'].update(max_candidates=1,exploration_trials=1,finalist_trials=1,
        top_k=1,max_total_trials=2)
    document['search_space']=dict(weapon_skill=[2],strength=[3],toughness=[3],agility=[3],
        melee=[4],defence=[6],athletics=[2],weapon=['sword'],light_armour=[False],
        shield=[True],abilities=[[]],allowed_talents=[])
    return document


class GeneratedEquipmentJsonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document=equipment_request()
        cls.command=parse_dynamic_encounter_request(json.dumps(cls.document))
        cls.result=execute_dynamic_encounter(cls.command)
        cls.report=json.loads(encode_dynamic_encounter_result(cls.command,cls.result))
        cls.replay=cls.report['explored'][0]['replay']

    def test_real_generator_preserves_components_both_protections_and_replay(self):
        self.assertEqual(self.report['total_trials'],2)
        self.assertEqual(self.report['source_request'],self.document)
        for candidate in self.report['explored']+self.report['validations']:
            npc=candidate['npcs'][0]
            self.assertEqual((npc['weapon'],npc['defence'],npc['shield']),('sword',6,True))
            enemy=candidate['replay']['scenario']['enemies'][0]
            definition=enemy['definition']
            self.assertEqual(definition['generated_components'],npc)
            self.assertEqual(definition['protection']['skill'],'defence')
            self.assertEqual(definition['alternate_protection']['skill'],'athletics')
            self.assertEqual(definition['resilience'],dict(toughness=3,bonus=1))
            self.assertIs(enemy['holds_shield'],True)
            parsed=parse_pc_melee_simulation_request(json.dumps(candidate['replay']))
            self.assertEqual(scenario_document(parsed.request.scenario),candidate['replay']['scenario'])
            self.assertEqual(parse_character_file(json.dumps(npc),'npc'),npc)

    def test_replay_rejects_forged_components_and_protection_bindings(self):
        def change(name,value):
            raw=deepcopy(self.replay)
            raw['scenario']['enemies'][0]['definition'][name]=value
            return raw
        original=self.replay['scenario']['enemies'][0]['definition']
        variants=[change('generated_components',dict(original['generated_components'],defence=5)),
            change('generated_components',dict(original['generated_components'],shield=False)),
            change('alternate_protection',dict(original['alternate_protection'],skill='defence')),
            change('protection',dict(original['protection'],source_rule_id='forged'))]
        for removed in ('generated_components','alternate_protection'):
            raw=deepcopy(self.replay)
            del raw['scenario']['enemies'][0]['definition'][removed]
            variants.append(raw)
        for raw in variants:
            with self.subTest(definition=raw['scenario']['enemies'][0]['definition']),self.assertRaises(PcMeleeInputError):
                parse_pc_melee_simulation_request(json.dumps(raw))

    def test_new_source_fields_are_required_and_typed_before_simulation(self):
        for field in ('defence','shield'):
            raw=deepcopy(self.document)
            del raw['search_space'][field]
            with self.subTest(missing=field),self.assertRaises(DynamicEncounterInputError):
                parse_dynamic_encounter_request(json.dumps(raw))
        for changes in (dict(defence=[True]),dict(defence=[7]),dict(shield=[1]),
                dict(weapon=['greatsword'])):
            raw=deepcopy(self.document)
            raw['search_space'].update(changes)
            with self.subTest(changes=changes),self.assertRaises(DynamicEncounterInputError):
                parse_dynamic_encounter_request(json.dumps(raw))

    def test_helmet_armour_fact_belongs_to_every_pc_including_nonwizard(self):
        for wizard in (False,True):
            raw=deepcopy(self.document)
            member=raw['party'][0]
            member['equipment']['armour']=[dict(id='helmet',kind='helmet',location='worn')]
            if wizard:
                mage=json.loads(Path('docs/examples/dynamic/elemental-mage.request.json').read_text(encoding='utf-8'))['party'][0]
                for key in ('talents','magic','characteristics','skills'):
                    member[key]=deepcopy(mage[key])
            with self.subTest(wizard=wizard):
                command=parse_dynamic_encounter_request(json.dumps(raw))
                pc=command.request.party[0]
                self.assertIs(pc.armour_worn,True)
                self.assertEqual(pc.pc.armour_bonus,0)
                scenario=command.request.scenario((command.request.space.sample(Random(0)),),'helmet')
                wire=scenario_document(scenario)
                self.assertIs(wire['party'][0]['armour_worn'],True)
                if wizard:
                    self.assertNotIn('armour_worn',wire['party'][0]['wizard'])

    def test_current_noncomponent_sources_cannot_gain_alternate_protection(self):
        from tests.support.pc_tactics_fixtures import automatic_source
        raw=deepcopy(self.replay)
        raw['scenario']=scenario_document(automatic_source(pc_count=1,enemy_count=1))
        definition=raw['scenario']['enemies'][0]['definition']
        definition['alternate_protection']=deepcopy(definition['protection'])
        with self.assertRaises(PcMeleeInputError):
            parse_pc_melee_simulation_request(json.dumps(raw))


class GeneratedEquipmentProcessParityTests(unittest.TestCase):
    def test_generated_sword_shield_and_both_protections_survive_workers(self):
        command=parse_dynamic_encounter_request(json.dumps(equipment_request()))
        npc=command.request.space.sample(Random(0))
        scenario=command.request.scenario((npc,),'generated-equipment-process')
        request=PcMeleeSimulationRequest(scenario,42,2)
        sequential=run_pc_melee_simulation(request)
        parallel=run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(sequential,parallel)
        self.assertEqual(summarize_pc_melee_simulation(sequential),summarize_pc_melee_simulation(parallel))
        enemy=parallel.source_request.scenario.enemies[0]
        self.assertEqual(enemy.definition.generated_components,npc)
        self.assertTrue(enemy.state.holds_shield)
        self.assertEqual(len(enemy.definition.protection),2)


if __name__=='__main__':
    unittest.main()
