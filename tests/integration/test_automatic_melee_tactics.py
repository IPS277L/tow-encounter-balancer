from dataclasses import replace
import unittest

from tests.support.pc_tactics_fixtures import weak_helper_source
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
import json


class AutomaticMeleeIntegrationTests(unittest.TestCase):
    def test_current_replay_roundtrip_and_process_seed_parity(self):
        source = weak_helper_source()
        document = dict(schema_version='1',kind='pc_melee_simulation',request_id='automatic-replay',
            ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(source),
            simulation=dict(master_seed='42',trials=2),execution=dict(mode='sequential'))
        command = parse_pc_melee_simulation_request(json.dumps(document))
        self.assertEqual(command.request.scenario,source)
        sequential = run_pc_melee_simulation(command.request)
        parallel = run_pc_melee_simulation_parallel(command.request,workers=2,batch_size=1)
        self.assertEqual(parallel,sequential)
        self.assertEqual(summarize_pc_melee_simulation(parallel),summarize_pc_melee_simulation(sequential))
        self.assertEqual(replace(parallel),parallel)


if __name__ == '__main__':
    unittest.main()
