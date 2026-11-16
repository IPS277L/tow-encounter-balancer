"""Current source, real generator/replay and one representative process path."""
from copy import deepcopy
from dataclasses import asdict,replace
import json
from pathlib import Path
import unittest

from tests.support.pc_magic_scenarios import magic_scenario
from towr.adapters.dynamic_encounter_json import (parse_dynamic_encounter_request,
    execute_dynamic_encounter,encode_dynamic_encounter_result)
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request,encode_pc_melee_simulation_result
from towr.application.dynamic_encounter import automatic_npc_search_space
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


class DynamicPcMagicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document=json.loads(Path('docs/examples/dynamic/elemental-mage.request.json').read_text(encoding='utf-8'))
        cls.document['search'].update(max_candidates=1,exploration_trials=1,finalist_trials=1,
            top_k=1,max_total_trials=2)
        cls.document['max_rounds']=3
        cls.document['npc_count']=dict(minimum=2,maximum=2)
        cls.command=parse_dynamic_encounter_request(json.dumps(cls.document))
        cls.result=execute_dynamic_encounter(cls.command)
        cls.report=json.loads(encode_dynamic_encounter_result(cls.command,cls.result))

    def test_generator_uses_real_caster_actions_and_preserves_all_source_facts(self):
        self.assertEqual(self.report['source_request'],self.document)
        self.assertEqual(self.report['total_trials'],2)
        for candidate in self.report['explored']+self.report['validations']:
            self.assertEqual(len(candidate['magic_counts']),1)
            self.assertGreater(candidate['magic_counts'][0]['casting_actions'],0)
            source=candidate['replay']['scenario']
            self.assertIs(source['facts']['daylight_confirmed'],True)
            self.assertEqual(source['party'][0]['wizard']['wizard_level'],4)
            self.assertEqual(source['party'][0]['wizard']['willpower'],6)

    def test_automatic_envelope_accounts_for_spell_power_without_overriding_manual_space(self):
        resolved=automatic_npc_search_space(self.command.request.party)
        self.assertIn(6,resolved.toughness)
        self.assertEqual(self.report['resolved_search_space']['toughness'],list(resolved.toughness))
        document=deepcopy(self.document)
        document['search_space']=deepcopy(self.report['resolved_search_space'])
        document['search_space']['toughness']=[2]
        self.assertEqual(parse_dynamic_encounter_request(json.dumps(document)).request.space.toughness,(2,))

    def test_executable_replay_reproduces_magic_costs_and_outcomes_in_current_wire(self):
        candidate=self.report['explored'][0]
        command=parse_pc_melee_simulation_request(json.dumps(candidate['replay']))
        summary=summarize_pc_melee_simulation(run_pc_melee_simulation(command.request))
        self.assertEqual(asdict(summary.outcome_counts),candidate['outcomes'])
        self.assertEqual([asdict(row) for row in summary.magic_counts],candidate['magic_counts'])
        encoded=json.loads(encode_pc_melee_simulation_result(command,summary))
        self.assertEqual(encoded['summary']['magic_counts'],candidate['magic_counts'])


class PcMagicProcessParityTests(unittest.TestCase):
    def test_actual_magic_journals_count_the_same_in_process_workers(self):
        request=PcMeleeSimulationRequest(magic_scenario(reason=3,willpower=6,level=4,rounds=2),42,2)
        sequential=run_pc_melee_simulation(request)
        parallel=run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(sequential,parallel)
        self.assertEqual(summarize_pc_melee_simulation(sequential),summarize_pc_melee_simulation(parallel))
        self.assertEqual(replace(parallel),parallel)
        self.assertGreater(sum(row.casting_actions for record in parallel.records for row in record.magic_counts),0)


if __name__=='__main__':
    unittest.main()
