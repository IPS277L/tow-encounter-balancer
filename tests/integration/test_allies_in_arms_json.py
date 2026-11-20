"""Actual ordinary NPC Help through trial accounting, JSON and real spawn."""
import json
import unittest

from tests.integration.test_generated_talents_json import talent_request
from tests.unit.test_allies_in_arms_npc_execution import npc_source
from tests.support.pc_melee_scripted import ScriptedD10
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request,encode_pc_melee_simulation_result
from towr.adapters.dynamic_encounter_json import (
    parse_dynamic_encounter_request,execute_dynamic_encounter,encode_dynamic_encounter_result,
)
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def literal_help_dice(seed):
    return ScriptedD10([1]*6+[10]*12)


class AlliesInArmsJsonTests(unittest.TestCase):
    def test_actual_ordinary_npc_help_counts_survive_current_json_and_independent_spawn(self):
        source=npc_source()
        raw=dict(schema_version='1',kind='pc_melee_simulation',request_id='allies:wire',
            ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(source),
            simulation=dict(master_seed='42',trials=2),execution=dict(mode='sequential'))
        command=parse_pc_melee_simulation_request(json.dumps(raw))
        self.assertEqual(command.request.scenario,source)
        sequential=run_pc_melee_simulation(command.request,rng_factory=literal_help_dice)
        parallel=run_pc_melee_simulation_parallel(command.request,workers=2,batch_size=1,
            rng_factory=literal_help_dice)
        self.assertEqual(parallel,sequential)
        summary=summarize_pc_melee_simulation(parallel)
        self.assertEqual(tuple(row.count for row in summary.npc_help_action_counts),(2,0))
        self.assertEqual(summary.total_action_count,6)
        document=json.loads(encode_pc_melee_simulation_result(command,summary))
        self.assertEqual(document['request']['scenario'],raw['scenario'])
        self.assertEqual(document['summary']['total_npc_help_action_count'],2)

    def test_small_dynamic_search_uses_real_fellowship_and_current_talent_source(self):
        raw=talent_request()
        raw['npc_count']=dict(minimum=2,maximum=2)
        raw['search_space'].update(weapon_skill=[1],strength=[1],toughness=[20],agility=[1],
            melee=[2],defence=[2],athletics=[2],weapon=['staff'],shield=[None],
            allowed_talents=['allies_in_arms'],fellowship=[4])
        command=parse_dynamic_encounter_request(json.dumps(raw))
        result=execute_dynamic_encounter(command)
        document=json.loads(encode_dynamic_encounter_result(command,result))
        self.assertEqual(document['source_request'],raw)
        self.assertEqual(document['total_trials'],2)
        for candidate in document['explored']+document['validations']:
            for npc in candidate['npcs']:
                self.assertEqual(npc['talent_facts']['fellowship'],4)
                self.assertTrue(all(talent['id']=='allies_in_arms' for talent in npc['talents']))
            replay=parse_pc_melee_simulation_request(json.dumps(candidate['replay']))
            self.assertEqual(tuple(enemy.definition.generated_components.talent_facts.fellowship
                for enemy in replay.request.scenario.enemies),(4,4))


if __name__=='__main__':unittest.main()
