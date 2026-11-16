from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest
from jsonschema import ValidationError

from tests.support.pc_potion_scenarios import enhancement_source
from towr.adapters.dynamic_encounter_json import (parse_dynamic_encounter_request,
    execute_dynamic_encounter, encode_dynamic_encounter_result, validate_dynamic_encounter_document)
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request, encode_pc_melee_simulation_result
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


class DynamicPotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        document = json.loads(Path('docs/examples/dynamic/search.request.json').read_text(encoding='utf-8'))
        document['party'] = document['party'][:1]
        document['party'][0]['consumables'] = [
            dict(id='healing',kind='healing_potion',quantity=2,characteristic=None),
            dict(id='enhancement',kind='enhancement_potion',quantity=2,characteristic='weapon_skill')]
        document['npc_count'] = dict(minimum=2,maximum=2)
        document['max_rounds'] = 2
        document['targets']['started_rounds'] = dict(numerator=1,denominator=1)
        document['search'].update(max_candidates=1,exploration_trials=1,finalist_trials=1,top_k=1,max_total_trials=2)
        cls.document = document
        cls.command = parse_dynamic_encounter_request(json.dumps(document))
        cls.result = execute_dynamic_encounter(cls.command)
        cls.report = json.loads(encode_dynamic_encounter_result(cls.command,cls.result))

    def test_current_request_preserves_both_items_and_report_has_actual_ordered_counts(self):
        self.assertEqual(self.report['source_request'], self.document)
        self.assertEqual(len(self.command.request.party[0].consumables),2)
        candidate = self.report['explored'][0]
        actor = self.document['party'][0]['actor_id']
        self.assertEqual([(item['actor_id'],item['item_id']) for item in candidate['potion_use_counts']],
            [(actor,'healing'),(actor,'enhancement')])
        source = candidate['replay']['scenario']['party'][0]
        self.assertEqual(source['consumables'],self.document['party'][0]['consumables'])

    def test_downloaded_replay_reproduces_outcomes_and_consumption(self):
        candidate = self.report['explored'][0]
        command = parse_pc_melee_simulation_request(json.dumps(candidate['replay']))
        result = run_pc_melee_simulation(command.request)
        summary = summarize_pc_melee_simulation(result)
        self.assertEqual([dict(actor_id=item.actor_id,item_id=item.item_id,count=item.count)
            for item in summary.potion_use_counts], candidate['potion_use_counts'])
        encoded = json.loads(encode_pc_melee_simulation_result(command,summary))
        self.assertEqual(encoded['summary']['potion_use_counts'],candidate['potion_use_counts'])

    def test_result_cannot_omit_consumption_for_an_inventory_replay(self):
        invalid = deepcopy(self.report)
        del invalid['explored'][0]['potion_use_counts']
        with self.assertRaises(ValidationError):
            validate_dynamic_encounter_document(invalid,kind='result')


class PotionProcessParityTests(unittest.TestCase):
    def test_process_pickling_and_summary_preserve_real_potion_costs(self):
        source = enhancement_source(rounds=2)
        request = PcMeleeSimulationRequest(source,42,2)
        sequential = run_pc_melee_simulation(request)
        parallel = run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(sequential,parallel)
        self.assertEqual(summarize_pc_melee_simulation(sequential),summarize_pc_melee_simulation(parallel))
        self.assertEqual(replace(parallel),parallel)
        self.assertGreater(sum(item.count for record in sequential.records for item in record.potion_use_counts),0)


if __name__ == '__main__':
    unittest.main()
