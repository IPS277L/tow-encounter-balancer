"""Real Armour Bane source through current JSON, generated search and spawn."""
from dataclasses import replace
import json
from random import Random
import unittest

from tests.integration.test_generated_talents_json import talent_request
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.talent_sources import paid_talent
from tests.unit.test_talent_armour_bane_execution import pc_source
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.dynamic_encounter_json import (
    parse_dynamic_encounter_request,execute_dynamic_encounter,encode_dynamic_encounter_result,
)
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request,encode_pc_melee_simulation_result
from towr.domain.talent_catalog import TalentId
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def armour_bane_dice(seed):
    return ScriptedD10([1,10,10]+[10]*7+[1,10,10]+[10]*2)


class ArmourBaneJsonTests(unittest.TestCase):
    def test_actual_source_and_two_independent_trials_match_real_spawn(self):
        source=pc_source()
        raw=dict(schema_version='1',kind='pc_melee_simulation',request_id='bane:wire',
            ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(source),
            simulation=dict(master_seed='42',trials=2),execution=dict(mode='sequential'))
        command=parse_pc_melee_simulation_request(json.dumps(raw))
        self.assertEqual(command.request.scenario,source)
        sequential=run_pc_melee_simulation(command.request,rng_factory=armour_bane_dice)
        parallel=run_pc_melee_simulation_parallel(command.request,workers=2,batch_size=1,
            rng_factory=armour_bane_dice)
        self.assertEqual(parallel,sequential)
        summary=summarize_pc_melee_simulation(parallel)
        encoded=json.loads(encode_pc_melee_simulation_result(command,summary))
        self.assertEqual(encoded['request']['scenario'],raw['scenario'])
        self.assertEqual(tuple(member.talents for member in source.party),
            ((paid_talent(TalentId.ARMOUR_BANE),),))

    def test_current_dynamic_pool_and_report_preserve_generated_and_pc_acquisitions(self):
        raw=talent_request()
        raw['search_space'].update(weapon=['axe'],allowed_talents=['armour_bane'])
        raw['party'][0]['talents']=[dict(id='armour_bane',acquisitions=[dict(
            phase='advancement',funding='xp')])]
        command=parse_dynamic_encounter_request(json.dumps(raw))
        npc=replace(command.request.space.sample(Random(0)),talents=(paid_talent(TalentId.ARMOUR_BANE),))
        native=command.request.scenario((npc,),'bane:generated')
        self.assertEqual(native.enemies[0].definition.talents,npc.talents)
        self.assertEqual(native.party[0].talents,(paid_talent(TalentId.ARMOUR_BANE),))
        result=execute_dynamic_encounter(command)
        report=json.loads(encode_dynamic_encounter_result(command,result))
        self.assertEqual(report['source_request'],raw)
        self.assertEqual(report['total_trials'],2)
        for candidate in report['explored']+report['validations']:
            self.assertTrue(all(entry['id']=='armour_bane'
                for generated in candidate['npcs'] for entry in generated['talents']))
            parsed=parse_pc_melee_simulation_request(json.dumps(candidate['replay']))
            self.assertEqual(parsed.request.scenario.party[0].talents,native.party[0].talents)


if __name__=='__main__':
    unittest.main()
