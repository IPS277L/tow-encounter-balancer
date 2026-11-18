"""Current generated talent facts, constrained input and executable source wire."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from random import Random
import unittest
from unittest.mock import patch
from tests.support.armour_fixtures import armour_document

from towr.adapters.character_files import parse_character_file
from towr.adapters.dynamic_encounter_json import (
    DynamicEncounterInputError, parse_dynamic_encounter_request,
    execute_dynamic_encounter, encode_dynamic_encounter_result,
)
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.adapters.pc_melee_json_errors import PcMeleeInputError
from towr.domain.generated_npc_models import GeneratedTalent
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def talent_request():
    raw=json.loads(Path('docs/examples/dynamic/talents.request.json').read_text(encoding='utf-8'))
    raw['party']=raw['party'][:1]
    raw['npc_count']=dict(minimum=1,maximum=1)
    raw['max_rounds']=1
    raw['targets']['started_rounds']=dict(numerator=1,denominator=1)
    raw['search'].update(max_candidates=1,exploration_trials=1,finalist_trials=1,top_k=1,max_total_trials=2)
    raw['search_space'].update(weapon_count=[1],weapon_skill=[3],strength=[4],toughness=[5],agility=[2],
        melee=[3],defence=[4],athletics=[3],weapon=['sword'],shield=['shield'],armour=[None])
    return raw


def source_with_all_talents():
    command=parse_dynamic_encounter_request(json.dumps(talent_request()))
    npc=replace(command.request.space.sample(Random(0)),talents=tuple(GeneratedTalent))
    return command.request.scenario((npc,),'generated-all-talents'),npc


class GeneratedTalentJsonTests(unittest.TestCase):
    def test_permitted_talents_are_a_pool_and_empty_disables_talent_generation(self):
        raw=talent_request()
        command=parse_dynamic_encounter_request(json.dumps(raw))
        self.assertEqual(command.request.space.allowed_talents,tuple(GeneratedTalent))
        raw['search_space']['allowed_talents']=[]
        empty=parse_dynamic_encounter_request(json.dumps(raw)).request.space
        self.assertEqual(empty.allowed_talents,())
        self.assertEqual(empty.sample(Random(0)).talents,())
        raw['search_space']=None
        self.assertEqual(parse_dynamic_encounter_request(json.dumps(raw)).request.space.allowed_talents,
            tuple(GeneratedTalent))

    def test_permitted_talents_are_required_typed_unique_and_closed_before_rng(self):
        for values in (None,[True],['unknown'],['wild_attack','wild_attack'],[['wild_attack']]):
            raw=talent_request()
            if values is None:
                del raw['search_space']['allowed_talents']
            else:
                raw['search_space']['allowed_talents']=values
            with self.subTest(values=values),patch('towr.application.dynamic_encounter.Random.randint') as roll:
                with self.assertRaises(DynamicEncounterInputError):
                    parse_dynamic_encounter_request(json.dumps(raw))
                roll.assert_not_called()

    def test_character_file_preserves_selected_talents_and_enforces_requirements(self):
        _,npc=source_with_all_talents()
        raw=dict(weapon_skill=npc.weapon_skill,strength=npc.strength,toughness=npc.toughness,
            agility=npc.agility,melee=npc.melee,defence=npc.defence,athletics=npc.athletics,
            weapons=[dict(id='weapon',weapon=npc.weapon.value,location='held',hand='left')],armour=armour_document(
                body=tuple(piece.value for piece in npc.armour.body),
                benefit=None if npc.armour.benefit is None else npc.armour.benefit.value,
                helmet=None if npc.armour.helmet is None else npc.armour.helmet.value,
                shield=None if npc.armour.shield is None else npc.armour.shield.value,barding=npc.armour.barding),
            abilities=[],talents=[talent.value for talent in npc.talents],
            mount=None,rider_kind=None,agilulf_code_confirmed=None,
            throwing=None,brawn=npc.brawn,ballistic_skill=None)
        self.assertEqual(parse_character_file(json.dumps(raw),'npc'),raw)
        for changes in (dict(weapon_skill=2),dict(strength=3),dict(talents=['wild_attack']*2),
                dict(talents=['unknown']),dict(talents=[dict(id='wild_attack',rank=1)])):
            with self.subTest(changes=changes),self.assertRaises(DynamicEncounterInputError):
                parse_character_file(json.dumps(dict(raw,**changes)),'npc')
        raw['talents']=[]
        raw.update(weapon_skill=2,strength=3)
        self.assertEqual(parse_character_file(json.dumps(raw),'npc'),raw)

    def test_native_replay_retains_the_full_selected_source_and_rejects_false_requirements(self):
        scenario,_=source_with_all_talents()
        raw=dict(schema_version='1',kind='pc_melee_simulation',request_id='talents',
            ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(scenario),
            simulation=dict(master_seed='42',trials=1),execution=dict(mode='sequential'))
        self.assertEqual(raw['scenario']['enemies'][0]['definition']['generated_components']['talents'],
            [talent.value for talent in GeneratedTalent])
        self.assertEqual(parse_pc_melee_simulation_request(json.dumps(raw)).request.scenario,scenario)
        for changes in (dict(weapon_skill=2),dict(strength=3),dict(talents=['unknown'])):
            changed=deepcopy(raw)
            changed['scenario']['enemies'][0]['definition']['generated_components'].update(changes)
            with self.subTest(changes=changes),self.assertRaises(PcMeleeInputError):
                parse_pc_melee_simulation_request(json.dumps(changed))
        changed=deepcopy(raw)
        del changed['scenario']['enemies'][0]['definition']['generated_components']['talents']
        with self.assertRaises(PcMeleeInputError):
            parse_pc_melee_simulation_request(json.dumps(changed))

    def test_real_generator_echoes_the_talent_pool_and_valid_selected_subsets(self):
        raw=talent_request()
        command=parse_dynamic_encounter_request(json.dumps(raw))
        result=execute_dynamic_encounter(command)
        report=json.loads(encode_dynamic_encounter_result(command,result))
        self.assertEqual(report['source_request'],raw)
        self.assertEqual(report['total_trials'],2)
        for candidate in report['explored']+report['validations']:
            npc=candidate['npcs'][0]
            self.assertTrue(set(npc['talents'])<=set(raw['search_space']['allowed_talents']))
            self.assertEqual(candidate['replay']['scenario']['enemies'][0]['definition']['generated_components'],npc)
            self.assertEqual(parse_character_file(json.dumps(npc),'npc'),npc)


class GeneratedTalentProcessParityTests(unittest.TestCase):
    def test_selected_talents_and_native_receipts_survive_process_transport(self):
        scenario,npc=source_with_all_talents()
        request=PcMeleeSimulationRequest(scenario,42,2)
        sequential=run_pc_melee_simulation(request)
        parallel=run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(sequential,parallel)
        self.assertEqual(summarize_pc_melee_simulation(sequential),summarize_pc_melee_simulation(parallel))
        self.assertEqual(parallel.source_request.scenario.enemies[0].definition.generated_components,npc)


if __name__=='__main__':
    unittest.main()
