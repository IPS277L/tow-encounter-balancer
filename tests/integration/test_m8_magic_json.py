"""Public magic wire -> existing simulator -> native aggregate, without services."""
import json
from multiprocessing import active_children
import random
import unittest

from tests.unit.test_m8_magic_json import document
from towr.adapters.magic_json_schema import validate_magic_simulation_document
from towr.adapters.magic_simulation_json import (
    parse_magic_simulation_request as parse, encode_magic_simulation_result as encode,
)
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation


class M8MagicJsonIntegrationTests(unittest.TestCase):
    def test_fixture_through_existing_simulator_and_native_summary_to_wire(self):
        data = document()
        command = parse(json.dumps(data))
        result = run_npc_magic_simulation(command.request)
        summary = summarize_npc_magic_simulation(result)
        encoded = json.loads(encode(command, summary))
        validate_magic_simulation_document(encoded, 'result')
        self.assertEqual(encoded['request'], data)
        for name in ('total_action_count', 'total_started_round_count', 'total_completed_round_count'):
            self.assertEqual(encoded['summary'][name], getattr(summary, name))
        self.assertEqual(set(encoded['summary']['outcome_counts']), {
            'objective_achieved', 'perspective_defeated', 'round_limit_reached', 'unsupported_path'})
        self.assertEqual(sum(encoded['summary']['outcome_counts'].values()), command.request.trials)
        self.assertEqual(parse(json.dumps(encoded['request'])), command)
        self.assertNotIn('trials', encoded)

    def test_sequential_and_spawn_have_identical_full_results_and_native_wire(self):
        data = document()
        data['scenario']['activation_order'].reverse()
        command = parse(json.dumps(data))
        before, children = random.getstate(), {c.pid for c in active_children()}
        sequential = run_npc_magic_simulation(command.request)
        data['execution'] = {'mode': 'process', 'workers': 2, 'batch_size': 3}
        parallel_command = parse(json.dumps(data))
        process = run_npc_magic_simulation_parallel(parallel_command.request,
            workers=parallel_command.execution.workers, batch_size=parallel_command.execution.batch_size)
        self.assertEqual(process, sequential)
        expected = json.loads(encode(command, summarize_npc_magic_simulation(sequential)))
        actual = json.loads(encode(parallel_command, summarize_npc_magic_simulation(process)))
        self.assertEqual(actual['summary'], expected['summary'])
        self.assertEqual(actual['request'], data)
        self.assertEqual(parse(json.dumps(actual['request'])), parallel_command)
        self.assertEqual(random.getstate(), before)
        self.assertEqual({c.pid for c in active_children()}, children)
