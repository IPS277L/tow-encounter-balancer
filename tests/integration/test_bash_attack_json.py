"""Real seeded Bash observations through current JSON and independent spawn.

This fixed two-trial transport check is not a Monte Carlo accuracy sample.
Both backends use their ordinary indexed Random sources, without scripted RNG.
"""
import json
import unittest

from tests.unit.test_bash_attack_execution import pc_source
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json import (
    encode_pc_melee_simulation_result, parse_pc_melee_simulation_request,
)
from towr.simulation.pc_immediate_attack_statistics import PcImmediateAttackCount
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


class BashAttackJsonTests(unittest.TestCase):
    def test_actual_seeded_free_strikes_survive_current_json_and_spawn_without_action_inflation(self):
        source = pc_source()
        raw = dict(schema_version='1', kind='pc_melee_simulation', request_id='bash:spawn',
            ruleset='towr-pg1.4-gmg1.1', scenario=scenario_document(source),
            simulation=dict(master_seed='0', trials=2), execution=dict(mode='sequential'))
        sequential_command = parse_pc_melee_simulation_request(json.dumps(raw))
        raw['execution'] = dict(mode='process', workers=2, batch_size=1)
        process_command = parse_pc_melee_simulation_request(json.dumps(raw))
        self.assertEqual(sequential_command.request, process_command.request)
        self.assertEqual(process_command.request.scenario, source)

        sequential = run_pc_melee_simulation(sequential_command.request)
        execution = process_command.execution
        parallel = run_pc_melee_simulation_parallel(process_command.request,
            workers=execution.workers, batch_size=execution.batch_size)
        self.assertEqual(parallel, sequential)
        first = parallel.records[0]
        self.assertEqual(first.immediate_attack_counts, (PcImmediateAttackCount('pc', 1),))
        self.assertEqual(first.executed_actions, 2)
        for record in parallel.records:
            self.assertEqual(tuple(row.actor_id for row in record.immediate_attack_counts), ('pc',))
            self.assertLessEqual(record.executed_actions, 2)
            self.assertTrue(all(row.count == 0 for row in record.npc_extra_attack_counts))

        summary = summarize_pc_melee_simulation(parallel)
        self.assertEqual(summary, summarize_pc_melee_simulation(sequential))
        self.assertGreater(summary.total_immediate_attack_count, 0)
        self.assertEqual(summary.total_action_count, parallel.total_action_count)
        self.assertEqual(summary.total_immediate_attack_count, parallel.total_immediate_attack_count)
        document = json.loads(encode_pc_melee_simulation_result(process_command, summary))
        self.assertEqual(document['request']['scenario'], raw['scenario'])
        self.assertEqual(document['request']['execution'], raw['execution'])
        self.assertEqual(document['request']['scenario']['party'][0]['talents'][0]['id'], 'bash_attack')
        self.assertEqual(document['summary']['immediate_attack_counts'],
            [dict(actor_id='pc', count=summary.total_immediate_attack_count)])
        self.assertEqual(document['summary']['total_immediate_attack_count'], summary.total_immediate_attack_count)
        self.assertEqual(document['summary']['total_action_count'], summary.total_action_count)


if __name__ == '__main__':
    unittest.main()
