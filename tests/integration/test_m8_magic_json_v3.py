"""Current Magic JSON contract: deterministic admission and source guards."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from functools import partial
import json
from multiprocessing import active_children
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.integration.test_m8_magic_cli import ROOT, environment, invoke
from tests.unit.test_m8_magic_json import summary as arithmetic_summary
from tests.unit.test_m8_magic_json_v3 import document
from tests.unit.test_m8_npc_magic_scenario_runner import Dice
from towr.adapters.magic_json_schema import validate_magic_simulation_document as validate
from towr.adapters.magic_simulation_json import parse_magic_simulation_request as parse, encode_magic_simulation_result as encode
from towr.application.magic_simulation_models import MagicSimulationCommand
from towr.application.magic_simulation_service import execute_magic_simulation
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.balance.magic_assessment import assess_magic_candidate
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.condition_models import Condition
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome, NpcMagicUnsupportedReason as Reason
from towr.domain.npc_roster_leg_spasm_models import NpcRosterLegSpasmStandResult
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest, NpcMagicOutcomeCounts
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation as summarize


HIT = (1, 2, 3, 10, 10, 10)
FULL_CHAIN = (*HIT, 9, *((10,) * 9), *HIT, 1, 5, *((10,) * 24))


def scripted_rng(seed, *, seeds, stationary):
    scripts = (FULL_CHAIN if stationary else (*HIT, 9), (*HIT, 10))
    return Dice(scripts[seeds.index(seed)])


def actual_command(*, stationary, miscast):
    with patch.object(sys, 'path', [str(ROOT / 'docs/examples/m8'), *sys.path]):
        from stationary_wound_runner import authored_input
        source = authored_input(stationary=stationary, miscast=miscast)
    command = MagicSimulationCommand('parsed:stationary', NpcMagicSimulationRequest(source, 42, 2),
        Options(Mode.SEQUENTIAL), tuple(dict.fromkeys(p.definition.id for p in source.initial.roster.participants)), '6')
    # v3 now represents this complete native source directly. No permission is
    # removed and no temporary legacy input is fabricated for old encoders.
    wire = json.loads(encode(command, arithmetic_summary(command)))['request']
    restored = parse(json.dumps(wire))
    assert restored == command
    return restored


class M8MagicJsonV3IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.rng_before = random.getstate()
        self.children_before = {p.pid for p in active_children()}

    def tearDown(self):
        self.assertEqual(random.getstate(), self.rng_before)
        self.assertEqual({p.pid for p in active_children()}, self.children_before)

    def test_four_permissions_keep_default_seeded_records_and_full_sources_across_spawn(self):
        for stationary in (False, True):
            for miscast in (False, True):
                data = document(stationary=stationary, miscast=miscast)
                data['simulation']['trials'] = 2
                command = parse(json.dumps(data))
                before = deepcopy(command)
                sequential = run_npc_magic_simulation(command.request)
                spawned = run_npc_magic_simulation_parallel(command.request, workers=1, batch_size=1)
                self.assertEqual(sequential, spawned)
                self.assertIs(spawned.source_request, command.request)
                self.assertTrue(all(t.source_scenario is command.request.scenario for t in spawned.trials))
                output = json.loads(encode(command, summarize(spawned)))
                self.assertEqual(output['request'], data)
                self.assertEqual(parse(json.dumps(output['request'])), command)
                self.assertEqual(sum(output['summary']['outcome_counts'].values()), 2)
                self.assertEqual(command, before)

    def test_parsed_v3_actual_leg_spasm_six_expiry_and_none_controls_keep_denominator(self):
        for stationary in (False, True):
            for miscast in (False, True):
                command = actual_command(stationary=stationary, miscast=miscast)
                before = deepcopy(command)
                dice = Dice(FULL_CHAIN if stationary else (*HIT, 9))
                trace = run_npc_magic_scenario(command.request.scenario, dice)
                dice.exhausted()
                self.assertEqual(dice.calls, 48 if stationary else 7)
                if stationary:
                    self.assertIs(trace.outcome, Outcome.ROUND_LIMIT_REACHED)
                    self.assertEqual(sum(isinstance(s.result, NpcRosterLegSpasmStandResult) for s in trace.steps), 1)
                    injury = trace.current.roster.participant('wizard').state.injury
                    self.assertEqual(tuple(w.table_total for w in injury.wounds), (9, 6))
                    self.assertFalse(injury.conditions.has(Condition.DRAINED))
                    self.assertFalse(trace.current.wound_expiries)
                    self.assertEqual(len(injury.active_wound_effects), 1)
                    self.assertEqual(sum(len(r.expired_sources) for r in trace.current.wound_turn_end_receipts), 1)
                else:
                    self.assertIs(trace.unsupported.reason, Reason.ACTOR_INJURY)
                seeds = tuple(command.request.seed_for(i) for i in range(2))
                factory = partial(scripted_rng, seeds=seeds, stationary=stationary)
                sequential = run_npc_magic_simulation(command.request, rng_factory=factory)
                spawned = run_npc_magic_simulation_parallel(command.request, workers=1, batch_size=1, rng_factory=factory)
                self.assertEqual(sequential, spawned)
                self.assertEqual(spawned.outcome_counts, NpcMagicOutcomeCounts(0, 0, int(stationary), 2-int(stationary)))
                self.assertTrue(all(t.source_scenario is command.request.scenario for t in spawned.trials))
                summary = summarize(spawned)
                a = assess_magic_candidate(command.request, summary,
                    ObjectiveRateWindow(Fraction(0), Fraction(1, 2), Fraction(1)))
                self.assertEqual(summary.trials, 2)
                self.assertEqual(a.unsupported_path_rate, Fraction(1, 2) if stationary else Fraction(1))
                self.assertIsNone(a.window_match)
                output = json.loads(encode(command, summary))
                validate(output, 'result', schema_version='6')
                self.assertEqual(parse(json.dumps(output['request'])), command)
                self.assertEqual(command, before)


    def test_cli_relative_file_v3_null_stays_v3_from_external_cwd(self):
        data = document(stationary=False, miscast=False)
        data['simulation']['trials'] = 1
        command = parse(json.dumps(data))
        expected = json.loads(encode(command, execute_magic_simulation(command)))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'request.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            completed = invoke('simulate-magic', path.name, cwd=directory)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, b'')
        self.assertEqual(json.loads(completed.stdout), expected)


    def test_cli_v3_decode_failures_keep_trusted_version_only_after_full_lexical_decode(self):
        invalid = document()
        invalid['scenario']['stationary_wound_continuation'] = False
        missing = document()
        del missing['scenario']['stationary_wound_continuation']
        cases = ((b'{"schema_version":"6","request_id":"seen","x":1e0}', '6', None, 'invalid_input'),
            (b'{"schema_version":"6","request_id":"seen","x":1,"x":2}', '6', None, 'invalid_json'),
            (json.dumps(invalid).encode(), '6', invalid['request_id'], 'invalid_input'),
            (json.dumps(missing).encode(), '6', missing['request_id'], 'invalid_input'),
            (json.dumps(dict(document(), schema_version='7')).encode(), '6', document()['request_id'], 'unsupported_version'))
        for raw, version, request_id, code in cases:
            completed = invoke('simulate-magic', '-', data=raw)
            self.assertEqual(completed.returncode, 2, completed.stderr)
            output = json.loads(completed.stdout)
            validate(output, 'error', schema_version=version)
            self.assertEqual((output['schema_version'], output['request_id'], output['error']['code']),
                             (version, request_id, code))
            self.assertNotIn(b'Traceback', completed.stderr)
            self.assertNotIn('summary', output)

    def test_cli_runtime_failure_uses_v3_command_and_hides_private_cause(self):
        script = (
            "from unittest.mock import patch\nfrom towr.cli import main\n"
            "from towr.application.magic_simulation_errors import MagicSimulationExecutionError\n"
            "cause = MagicSimulationExecutionError('foreign-private-id', schema_version='6')\n"
            "cause.add_note('private-worker-note')\n"
            "with patch('towr.simulation.npc_magic_parallel.ProcessPoolExecutor', side_effect=cause):\n"
            "    raise SystemExit(main(['simulate-magic', '-']))\n")
        data = document()
        data['execution'] = {'mode': 'process', 'workers': 1, 'batch_size': 1}
        completed = subprocess.run([sys.executable, '-c', script], input=json.dumps(data).encode(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT, env=environment(), timeout=45)
        self.assertEqual(completed.returncode, 3, completed.stderr)
        output = json.loads(completed.stdout)
        validate(output, 'error', schema_version='6')
        self.assertEqual((output['schema_version'], output['request_id'], output['error']['code']),
                         ('6', data['request_id'], 'simulation_failed'))
        self.assertNotIn(b'private', completed.stdout + completed.stderr)
        self.assertNotIn(b'Traceback', completed.stderr)


    def test_cli_usage_and_v3_output_failure_emit_no_second_json_document(self):
        usage = invoke('simulate-magic', '-', '--workers', '6', data=b'')
        self.assertEqual(usage.returncode, 2)
        self.assertEqual(usage.stdout, b'')
        raw = json.dumps(dict(document(), kind='wrong')).encode()
        with subprocess.Popen([sys.executable, '-m', 'towr', 'simulate-magic', '-'], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT, env=environment()) as process:
            process.stdout.close()
            process.stdout = None
            _, stderr = process.communicate(raw, timeout=45)
        self.assertEqual(process.returncode, 4, stderr)
        self.assertIn(b'output I/O error', stderr)
        self.assertNotIn(b'Traceback', stderr)
        self.assertNotIn(b'Exception ignored', stderr)


if __name__ == '__main__':
    unittest.main()
