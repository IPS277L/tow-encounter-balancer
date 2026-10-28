"""ADR-0044 death continuation through trials, spawn and unchanged magic JSON."""
from copy import deepcopy
from dataclasses import replace
from functools import partial
from multiprocessing import active_children
import json
import os
from pathlib import Path
from random import Random, getstate
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tests.unit.test_m8_dead_champion_journal import lethal_scenario, lethal_values
from tests.unit.test_m8_npc_magic_scenario import PLAYERS, OPPOSITION
from tests.unit.test_m8_npc_magic_scenario_runner import Dice
from towr.adapters.magic_json_schema import validate_magic_simulation_document
from towr.adapters.magic_simulation_json import (
    encode_magic_simulation_result as encode, parse_magic_simulation_request as parse,
)
from towr.application.magic_simulation_models import MagicSimulationCommand
from towr.application.magic_simulation_service import execute_magic_simulation
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.npc_roster_dead_champion_models import NpcRosterDeadChampionExclusionResult
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest, NpcMagicOutcomeCounts
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel
from towr.simulation.npc_magic_simulation import run_npc_magic_trial, run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation as summarize


def death_rng(seed, *, seeds, scripts, parent_pid=None):
    """Importable factory; a process test must actually execute in a child."""
    if parent_pid is not None and os.getpid() == parent_pid:
        raise AssertionError('death propagation trial ran in parent instead of spawn child')
    return Dice(scripts[seeds.index(seed)])


def factory(request, scripts, *, child=False):
    return partial(death_rng, seeds=tuple(request.seed_for(i) for i in range(request.trials)),
        scripts=tuple(scripts), parent_pid=os.getpid() if child else None)


def perspective(source, side):
    return replace(source, perspective_side=side, objective=NpcDefeatObjective(tuple(
        p.state.actor_id for p in source.initial.roster.participants if p.state.side is not side)))


def command(request):
    definitions = tuple(dict.fromkeys(p.definition.id for p in request.scenario.initial.roster.participants))
    return MagicSimulationCommand('wire:death-continuation', request,
        SimulationExecutionOptions(SimulationExecutionMode.SEQUENTIAL), definitions)


class DeadChampionPropagationTests(unittest.TestCase):
    def setUp(self):
        self.global_rng = getstate()
        self.children = {child.pid for child in active_children()}

    def tearDown(self):
        self.assertEqual(getstate(), self.global_rng)
        self.assertEqual({child.pid for child in active_children()}, self.children)

    def assert_source_and_counters(self, request, actual, expected):
        self.assertEqual(actual, expected)
        self.assertIs(actual.source_request, request)
        self.assertEqual(tuple(r.trial_index for r in actual.trials), tuple(range(request.trials)))
        self.assertEqual(tuple(r.seed for r in actual.trials),
                         tuple(request.seed_for(i) for i in range(request.trials)))
        self.assertTrue(all(r.source_scenario is request.scenario for r in actual.trials))
        self.assertEqual(summarize(actual), summarize(expected))
        self.assertIs(summarize(actual).source_request, request)

    def test_direct_trial_projects_lethal_continuation_for_both_sides_and_perspectives(self):
        for wizard_side in (PLAYERS, OPPOSITION):
            for side in (PLAYERS, OPPOSITION):
                with self.subTest(wizard_side=wizard_side, perspective=side):
                    source = perspective(lethal_scenario(wizard_side=wizard_side), side)
                    request = NpcMagicSimulationRequest(source, 42, 2)
                    before = deepcopy(request)
                    streams, seeds = [], []

                    def fresh(seed):
                        seeds.append(seed)
                        stream = Dice(lethal_values(wizard_side=wizard_side))
                        streams.append(stream)
                        return stream

                    record = run_npc_magic_trial(request, 1, rng_factory=fresh)
                    self.assertEqual(seeds, [request.seed_for(1)])
                    streams[0].exhausted()
                    self.assertEqual(streams[0].calls, 33 if wizard_side is PLAYERS else 30)
                    self.assertIs(record.source_scenario, source)
                    self.assertIs(record.outcome, Outcome.ROUND_LIMIT_REACHED)
                    self.assertEqual((record.executed_action_count, record.started_round_count,
                                      record.completed_round_count), (5 if wizard_side is PLAYERS else 4, 1, 1))
                    self.assertEqual(request, before)

    def test_real_spawn_preserves_full_death_records_for_both_sides_and_perspectives(self):
        for wizard_side in (PLAYERS, OPPOSITION):
            for side in (PLAYERS, OPPOSITION):
                with self.subTest(wizard_side=wizard_side, perspective=side):
                    request = NpcMagicSimulationRequest(
                        perspective(lethal_scenario(wizard_side=wizard_side), side), 20261028, 3)
                    before = deepcopy(request)
                    scripts = (lethal_values(wizard_side=wizard_side),) * request.trials
                    sequential = run_npc_magic_simulation(request, rng_factory=factory(request, scripts))
                    parallel = run_npc_magic_simulation_parallel(request, workers=2, batch_size=2,
                        rng_factory=factory(request, scripts, child=True))
                    self.assert_source_and_counters(request, parallel, sequential)
                    summary = summarize(parallel)
                    self.assertEqual(summary.outcome_counts, NpcMagicOutcomeCounts(0, 0, 3, 0))
                    self.assertEqual((summary.total_action_count, summary.total_started_round_count,
                                      summary.total_completed_round_count), (15 if wizard_side is PLAYERS else 12, 3, 3))
                    self.assertEqual(request, before)

    def test_missing_post_death_frame_stays_unsupported_in_every_trial(self):
        for wizard_side, budget, counters in ((OPPOSITION, 1, (3, 1, 0)), (PLAYERS, 2, (5, 2, 1))):
            with self.subTest(wizard_side=wizard_side):
                scenario = lethal_scenario(wizard_side=wizard_side, max_rounds=budget, post_death_frame=False)
                request = NpcMagicSimulationRequest(scenario, 42, 2)
                before = deepcopy(request)
                values = lethal_values(wizard_side=wizard_side)
                if wizard_side is OPPOSITION:
                    values = values[:-6]
                scripts = (values,) * request.trials
                sequential = run_npc_magic_simulation(request, rng_factory=factory(request, scripts))
                parallel = run_npc_magic_simulation_parallel(request, workers=1, batch_size=3,
                    rng_factory=factory(request, scripts, child=True))
                self.assert_source_and_counters(request, parallel, sequential)
                self.assertEqual(tuple(r.outcome for r in parallel.trials), (Outcome.UNSUPPORTED_PATH,) * 2)
                self.assertEqual(tuple((r.executed_action_count, r.started_round_count,
                                       r.completed_round_count) for r in parallel.trials), (counters,) * 2)
                self.assertEqual(summarize(parallel).outcome_counts, NpcMagicOutcomeCounts(0, 0, 0, 2))
                self.assertEqual(summarize(parallel).trials, 2)
                self.assertEqual(request, before)

    def test_mandatory_stops_remain_in_mixed_batch_denominator_and_expanded_prefix(self):
        request = NpcMagicSimulationRequest(lethal_scenario(), 42, 3)
        scripts = (lethal_values(), (1, 2, 3, 10, 10, 10, 4), (10,) * 18 + (9, 9, 9))
        sequential = run_npc_magic_simulation(request, rng_factory=factory(request, scripts))
        parallel = run_npc_magic_simulation_parallel(request, workers=2, batch_size=2,
            rng_factory=factory(request, scripts, child=True))
        self.assert_source_and_counters(request, parallel, sequential)
        self.assertEqual(tuple((r.outcome, r.executed_action_count, r.started_round_count,
                                r.completed_round_count) for r in parallel.trials), (
            (Outcome.ROUND_LIMIT_REACHED, 4, 1, 1), (Outcome.UNSUPPORTED_PATH, 1, 1, 0),
            (Outcome.UNSUPPORTED_PATH, 4, 1, 0)))
        self.assertEqual(summarize(parallel).outcome_counts, NpcMagicOutcomeCounts(0, 0, 1, 2))
        self.assertEqual((parallel.total_action_count, parallel.total_started_round_count,
                          parallel.total_completed_round_count), (9, 3, 1))
        expanded = replace(request, trials=4)
        expanded_scripts = (*scripts, lethal_values())
        larger = run_npc_magic_simulation_parallel(expanded, workers=1, batch_size=3,
            rng_factory=factory(expanded, expanded_scripts, child=True))
        self.assertEqual(larger.trials[:3], parallel.trials)
        self.assertEqual(summarize(larger).outcome_counts, NpcMagicOutcomeCounts(0, 0, 2, 2))

    def test_public_json_request_reconstructs_full_death_source_before_real_execution(self):
        for future_frame in (True, False):
            with self.subTest(post_death_frame=future_frame):
                scenario = lethal_scenario(post_death_frame=future_frame)
                request = NpcMagicSimulationRequest(scenario, 42, 2)
                values = lethal_values() if future_frame else lethal_values()[:-6]
                scripts = (values,) * 2
                expected = run_npc_magic_simulation(request, rng_factory=factory(request, scripts))
                initial = json.loads(encode(command(request), summarize(expected)))
                # Feed the public request JSON back through strict parsing and
                # execute the parsed input, rather than asserting command-only parity.
                document = initial['request']
                before = deepcopy(document)
                parsed = parse(json.dumps(document))
                self.assertEqual(parsed.request, request)
                self.assertEqual(parsed.request.scenario.scene_frames, scenario.scene_frames)
                sequential = run_npc_magic_simulation(parsed.request,
                    rng_factory=factory(parsed.request, scripts))
                process_document = deepcopy(document)
                process_document['execution'] = {'mode': 'process', 'workers': 2, 'batch_size': 3}
                process = parse(json.dumps(process_document))
                parallel = run_npc_magic_simulation_parallel(process.request, workers=2, batch_size=3,
                    rng_factory=factory(process.request, scripts, child=True))
                self.assert_source_and_counters(process.request, parallel, expected)
                self.assertEqual(sequential, expected)
                wire = json.loads(encode(process, summarize(parallel)))
                validate_magic_simulation_document(wire, 'result')
                self.assertEqual(wire['request'], process_document)
                self.assertEqual(parse(json.dumps(wire['request'])), process)
                self.assertEqual(wire['summary'], initial['summary'])
                self.assertEqual(wire['summary']['trials'], 2)
                self.assertEqual(wire['summary']['outcome_counts']['unsupported_path'], 0 if future_frame else 2)
                self.assertNotIn('trials', wire)
                self.assertEqual(document, before)

    def test_death_summary_cannot_be_rebound_to_same_id_without_future_scene(self):
        request = NpcMagicSimulationRequest(lethal_scenario(), 42, 2)
        result = run_npc_magic_simulation(request, rng_factory=factory(request, (lethal_values(),) * 2))
        changed = replace(request.scenario, scene_frames=(request.scenario.initial_frame,))
        self.assertEqual(changed.id, request.scenario.id)
        changed_command = command(replace(request, scenario=changed))
        with self.assertRaises(ValueError):
            encode(changed_command, summarize(result))

    def test_saved_standard_rng_death_witness_reaches_service_and_external_cli(self):
        # A selected finite seed/profile witness, not an estimated probability.
        root = Path(__file__).resolve().parents[2]
        fixture = root / 'docs/examples/m8/json/dead-champion-v1.request.json'
        original = fixture.read_bytes()
        document = json.loads(original)
        saved = json.loads(fixture.with_name('dead-champion-v1.result.json').read_bytes())
        parsed = parse(original)
        before = deepcopy(parsed.request)
        battle = run_npc_magic_scenario(parsed.request.scenario, Random(parsed.request.seed_for(0)))
        self.assertIs(battle.outcome, Outcome.ROUND_LIMIT_REACHED)
        self.assertIsNone(battle.unsupported)
        self.assertEqual(tuple(w.table_total for w in battle.current.roster.participant('wizard').state.injury.wounds),
                         (3, 2, 25))
        phases = tuple(s for s in battle.steps if isinstance(s.result, NpcRosterDeadChampionExclusionResult))
        self.assertEqual(len(phases), 1)
        self.assertEqual(phases[0].after.round_state.excluded_turn_entity_ids, ('wizard',))
        self.assertEqual((battle.executed_actions, battle.started_rounds, battle.completed_rounds), (4, 1, 1))
        self.assertEqual(saved['request'], document)
        with TemporaryDirectory() as directory:
            for execution in ({'mode': 'sequential'}, {'mode': 'process', 'workers': 2, 'batch_size': 1}):
                with self.subTest(execution=execution):
                    wire_request = deepcopy(document)
                    wire_request['execution'] = execution
                    command = parse(json.dumps(wire_request))
                    summary = execute_magic_simulation(command)
                    encoded = json.loads(encode(command, summary))
                    self.assertEqual(encoded['request'], wire_request)
                    self.assertEqual(encoded['summary'], saved['summary'])
                    path = Path(directory) / 'death-request.json'
                    path.write_text(json.dumps(wire_request), encoding='utf-8')
                    completed = subprocess.run([sys.executable, '-m', 'towr', 'simulate-magic', str(path)],
                        cwd=directory, env=dict(os.environ, PYTHONPATH=str(root / 'src'), PYTHONNOUSERSITE='1'),
                        capture_output=True, check=True, timeout=45)
                    self.assertEqual(completed.stderr, b'')
                    output = json.loads(completed.stdout)
                    validate_magic_simulation_document(output, 'result')
                    # Runtime comes from the actual interpreter, not the fixture.
                    self.assertEqual(output, encoded)
        self.assertEqual(parsed.request, before)
        self.assertEqual(fixture.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
