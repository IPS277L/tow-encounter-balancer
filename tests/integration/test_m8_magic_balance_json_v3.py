"""Actual balance3 variable reserves, Wound continuations, staged spawn and CLI."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from functools import partial
import json
from multiprocessing import active_children
import os
import random
import subprocess
import sys
import unittest
from unittest.mock import patch

from tests.integration.test_m8_magic_cli import ROOT, environment, invoke
from tests.integration import test_m8_stationary_wound_generation as native
from tests.unit.test_m8_magic_balance_json_v3 import document, POLICY
from tests.unit.test_m8_magic_candidate_generation import collapse_request
from tests.unit.test_m8_magic_json_v3 import document as simulation_document
from tests.unit.test_m8_miscast_continuation_policy import continuation_policy
from tests.unit.test_m8_npc_magic_scenario_runner import Dice
from towr.adapters.magic_balance_json import (
    _request_document, parse_magic_balance_request as parse, encode_magic_balance_result as encode,
)
from towr.adapters.magic_json_schema import validate_magic_balance_document as validate
from towr.application import magic_evaluation_service as evaluation
from towr.application import magic_candidate_generation as generation
from towr.application.magic_balance_errors import MagicBalanceGenerationError
from towr.application.magic_balance_models import MagicBalanceCommand
from towr.application.magic_balance_service import execute_magic_balance
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.balance.magic_staged_evaluation_models import MagicStagedEvaluationStatus
from towr.domain.condition_models import Condition
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome
from towr.domain.npc_roster_leg_spasm_models import NpcRosterLegSpasmStandResult
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.simulation.npc_magic_models import NpcMagicOutcomeCounts


def native_command(*, stationary=True, miscast=False, source=None):
    source = native.family(stationary=stationary, miscast=miscast) if source is None else source
    definitions = tuple(dict.fromkeys(p.definition.id for p in source.template_scenario.initial.roster.participants))
    return MagicBalanceCommand('balance3:variable', source, Options(Mode.SEQUENTIAL), definitions, '3')


def parsed_command(*, stationary=True, miscast=False):
    command = native_command(stationary=stationary, miscast=miscast)
    restored = parse(json.dumps(_request_document(command)))
    assert restored == command
    return restored


class M8MagicBalanceJsonV3IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.rng_before = random.getstate()
        self.children_before = {p.pid for p in active_children()}

    def tearDown(self):
        self.assertEqual(random.getstate(), self.rng_before)
        self.assertEqual({p.pid for p in active_children()}, self.children_before)

    def assert_sources(self, result, command):
        generated, report = result.generation_result, result.evaluation_result
        self.assertIs(generated.source_request, command.generation_request)
        self.assertIs(report.source_request, generated.evaluation_request)
        catalog = {c.candidate_id: c.scenario for c in generated.evaluation_request.candidates}
        self.assertEqual(tuple(len(s.initial.roster.participants) for s in catalog.values()), (3, 4))
        for stage in report.stage_reports:
            for row in stage.candidates:
                source = row.assessment.source_request
                self.assertIs(source.scenario, catalog[row.candidate_id])
                self.assertIs(row.assessment.summary.source_request, source)
                self.assertIs(source.scenario.stationary_wound_continuation, command.generation_request.stationary_wound_continuation)
                self.assertEqual(source.scenario.miscast_continuation, command.generation_request.miscast_continuation)

    def test_parsed_variable_subsets_execute_actual_leg_spasm_and_six_expiry(self):
        command = parsed_command(miscast=True)
        before = deepcopy(command)
        generated = generation.generate_magic_candidates(command.generation_request)
        for candidate in generated.evaluation_request.candidates:
            count = len(candidate.scenario.initial.roster.participants)
            dice = Dice(native.script(count, stationary=True))
            trace = run_npc_magic_scenario(candidate.scenario, dice)
            dice.exhausted()
            self.assertEqual(dice.calls, 48 if count == 3 else 66)
            self.assertIs(trace.source, candidate.scenario)
            self.assertIs(trace.outcome, Outcome.ROUND_LIMIT_REACHED)
            self.assertEqual(sum(isinstance(s.result, NpcRosterLegSpasmStandResult) for s in trace.steps), 1)
            injury = trace.current.roster.participant('wizard').state.injury
            self.assertEqual(tuple(w.table_total for w in injury.wounds), (9, 6))
            self.assertFalse(injury.conditions.has(Condition.DRAINED))
            self.assertEqual(len(injury.active_wound_effects), 1)
            self.assertFalse(trace.current.wound_expiries)
            self.assertEqual(sum(len(r.expired_sources) for r in trace.current.wound_turn_end_receipts), 1)
        self.assertEqual(command, before)

    def test_default_seeded_native_and_cli_reports_match_for_four_policies_and_both_backends(self):
        for stationary in (False, True):
            for miscast in (False, True):
                base = parsed_command(stationary=stationary, miscast=miscast)
                base = replace(base, request_id='подбор-рана-雪')
                before = deepcopy(base)
                results = []
                for options in (Options(Mode.SEQUENTIAL), Options(Mode.PROCESS, 1, 2)):
                    command = replace(base, execution=options)
                    result = execute_magic_balance(command)
                    self.assert_sources(result, command)
                    expected = json.loads(encode(command, result))
                    validate(expected, 'result', schema_version='3')
                    wire = _request_document(command)
                    completed = invoke('balance-magic', '-', data=json.dumps(wire, ensure_ascii=False).encode('utf-8'))
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    self.assertEqual(completed.stderr, b'')
                    self.assertIn('подбор-рана-雪'.encode(), completed.stdout)
                    actual = json.loads(completed.stdout)
                    self.assertEqual(actual, expected)
                    self.assertEqual(actual['request'], wire)
                    self.assertEqual(parse(json.dumps(actual['request'])), command)
                    self.assertEqual([c['counts'] for c in actual['candidates']], [[1], [2]])
                    self.assertEqual(actual['total_trials'], result.evaluation_result.total_trials)
                    self.assertLessEqual(actual['total_trials'], actual['planned_trials'])
                    results.append(result)
                self.assertEqual(results[0], results[1])
                self.assertEqual(base, before)

    def test_parsed_scripted_stages_keep_unsupported_denominator_and_full_repeat_prefix(self):
        sequential_runner = evaluation.run_npc_magic_simulation
        process_runner = evaluation.run_npc_magic_simulation_parallel
        cases = [(s, m, True) for s in (False, True) for m in (False, True)] + [(True, True, False)]
        for stationary, miscast, mixed in cases:
            command = parsed_command(stationary=stationary, miscast=miscast)
            before = deepcopy(command)
            captures = []

            def factory(source, process=False):
                return partial(native.generated_rng, actor_count=len(source.scenario.activation_order), stationary=stationary,
                    seeds=tuple(source.seed_for(i) for i in range(source.trials)), mixed=mixed,
                    parent_pid=os.getpid() if process else None)

            def sequential(source):
                result = sequential_runner(source, rng_factory=factory(source))
                captures.append(result)
                return result

            with patch.object(evaluation, 'run_npc_magic_simulation', side_effect=sequential), \
                    patch.object(evaluation, 'run_npc_magic_simulation_parallel', side_effect=lambda source, **kw:
                        process_runner(source, rng_factory=factory(source, True), **kw)):
                seq = execute_magic_balance(command)
                process_command = replace(command, execution=Options(Mode.PROCESS, 1, 2))
                proc = execute_magic_balance(process_command)
            self.assertEqual(seq, proc)
            self.assert_sources(seq, command)
            self.assert_sources(proc, process_command)
            report = seq.evaluation_result
            self.assertEqual((report.total_trials, report.planned_trials), (4 if mixed else 8, 8))
            for stage in report.stage_reports:
                for row in stage.candidates:
                    assessment = row.assessment
                    n = assessment.source_request.trials
                    self.assertEqual(assessment.summary.trials, n)
                    if mixed:
                        self.assertEqual(assessment.summary.outcome_counts,
                            NpcMagicOutcomeCounts(0, 0, int(stationary), 2 - int(stationary)))
                        self.assertEqual(assessment.unsupported_path_rate, Fraction(1, 2) if stationary else Fraction(1))
                        self.assertIsNone(assessment.window_match)
                    else:
                        self.assertEqual(assessment.summary.outcome_counts, NpcMagicOutcomeCounts(0, 0, n, 0))
            if mixed:
                self.assertIs(report.status, MagicStagedEvaluationStatus.NO_ELIGIBLE_CANDIDATES)
                self.assertEqual(len(report.stage_reports), 1)
            else:
                self.assertEqual([r.source_request.trials for r in captures], [2, 2, 4])
                first = next(r for r in captures[:2] if r.source_request.scenario is captures[-1].source_request.scenario)
                self.assertEqual(tuple(t.seed for t in first.trials), tuple(t.seed for t in captures[-1].trials[:2]))
            wire = json.loads(encode(command, seq))
            self.assertEqual(wire['request'], _request_document(command))
            self.assertEqual(command, before)

    def test_actual_late_projection_failure_preserves_second_counts_without_partial_output(self):
        source = collapse_request(conflict_actor='far-blocker')
        policy = continuation_policy()
        source = replace(source, template_scenario=replace(source.template_scenario,
            stationary_wound_continuation=POLICY, miscast_continuation=policy),
            stationary_wound_continuation=POLICY, miscast_continuation=policy)
        original = native_command(source=source)
        wire = _request_document(original)
        command = parse(json.dumps(wire))
        self.assertEqual(command, original)
        with patch.object(generation, '_project_candidate', wraps=generation._project_candidate) as projection, \
                patch('towr.application.magic_balance_service.evaluate_magic_candidates_staged') as evaluate:
            with self.assertRaises(MagicBalanceGenerationError) as caught:
                execute_magic_balance(command)
        self.assertEqual(projection.call_count, 2)
        evaluate.assert_not_called()
        self.assertEqual(caught.exception.counts, (1, 1))
        completed = invoke('balance-magic', '-', data=json.dumps(wire).encode())
        self.assertEqual(completed.returncode, 3, completed.stderr)
        output = json.loads(completed.stdout)
        validate(output, 'error', schema_version='3')
        self.assertEqual((output['schema_version'], output['request_id']), ('3', command.request_id))
        self.assertEqual(output['error']['counts'], [1, 1])
        self.assertEqual(output['error']['candidate_id'], caught.exception.candidate_id)
        self.assertEqual(output['error']['code'], 'generation_failed')
        self.assertIsNone(output['error']['stage_index'])
        self.assertNotIn('candidates', output)
        self.assertNotIn('stage_reports', output)

    def test_cli_late_stage_failure_after_real_first_stage_keeps_context_and_privacy(self):
        command = parsed_command(miscast=True)
        script = '''
from functools import partial
from unittest.mock import patch
from tests.integration.test_m8_stationary_wound_generation import generated_rng
from towr.application import magic_evaluation_service as evaluation
from towr.cli import main
original = evaluation.run_npc_magic_simulation
calls = 0
def run(source):
    global calls
    calls += 1
    if calls == 3:
        error = OSError('private late evaluation failure')
        error.add_note('private note')
        raise error
    return original(source, rng_factory=partial(generated_rng,
        actor_count=len(source.scenario.activation_order), stationary=True,
        seeds=tuple(source.seed_for(i) for i in range(source.trials)), mixed=False))
with patch.object(evaluation, 'run_npc_magic_simulation', side_effect=run):
    status = main(['balance-magic', '-'])
assert calls == 3
raise SystemExit(status)
'''
        completed = subprocess.run([sys.executable, '-c', script], input=json.dumps(_request_document(command)).encode(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT, env=environment(), timeout=45)
        self.assertEqual(completed.returncode, 3, completed.stderr)
        output = json.loads(completed.stdout)
        validate(output, 'error', schema_version='3')
        self.assertEqual((output['schema_version'], output['request_id']), ('3', command.request_id))
        self.assertEqual(output['error']['code'], 'evaluation_failed')
        self.assertEqual(output['error']['stage_index'], 1)
        self.assertEqual(output['error']['candidate_id'], command.generation_request.candidate_id_prefix + ':counts:1')
        self.assertIsNone(output['error']['counts'])
        self.assertNotIn('stage_reports', output)
        self.assertNotIn(b'private', completed.stdout + completed.stderr)
        self.assertNotIn(b'Traceback', completed.stderr)

    def test_cli_trusted_v3_input_errors_and_lexical_fallback_remain_separate(self):
        mismatch = document()
        mismatch['generation']['stationary_wound_continuation'] = None
        missing = document()
        del missing['generation']['stationary_wound_continuation']
        cases = ((b'{"schema_version":"3","request_id":"seen","x":1e0}', '1', None, 'invalid_input'),
            (b'{"schema_version":"3","request_id":"seen","x":1,"x":2}', '1', None, 'invalid_json'),
            (json.dumps(mismatch).encode(), '3', mismatch['request_id'], 'invalid_input'),
            (json.dumps(missing).encode(), '3', missing['request_id'], 'invalid_input'),
            (json.dumps(dict(document(), schema_version='5')).encode(), '1', document()['request_id'], 'unsupported_version'))
        for raw, version, request_id, code in cases:
            completed = invoke('balance-magic', '-', data=raw)
            self.assertEqual(completed.returncode, 2, completed.stderr)
            output = json.loads(completed.stdout)
            validate(output, 'error', schema_version=version)
            self.assertEqual((output['schema_version'], output['request_id'], output['error']['code']),
                             (version, request_id, code))
            self.assertTrue(all(output['error'][key] is None for key in ('candidate_id', 'counts', 'stage_index')))
            self.assertNotIn('stage_reports', output)

    def test_six_old_routes_reject_v3_while_simulation_v3_remains_admitted(self):
        cases = (('simulate', 'm4/ranged-v1.request.json'), ('balance', 'm5/json/balance-v1.request.json'),
            ('simulate-melee', 'm6/json/melee-simulation-v1.request.json'), ('balance-melee', 'm6/json/melee-balance-v1.request.json'),
            ('simulate-mixed', 'm7/json/mixed-simulation-v1.request.json'), ('balance-mixed', 'm7/json/mixed-balance-v1.request.json'))
        for route, relative in cases:
            wire = json.loads((ROOT / 'docs/examples' / relative).read_bytes())
            wire['schema_version'] = '3'
            completed = invoke(route, '-', data=json.dumps(wire).encode())
            self.assertEqual(completed.returncode, 2, completed.stderr)
            output = json.loads(completed.stdout)
            self.assertEqual((output['schema_version'], output['error']['code']), ('1', 'unsupported_version'))
            self.assertEqual(output['error']['path'], '/schema_version')
        simulation = simulation_document()
        simulation['simulation']['trials'] = 1
        completed = invoke('simulate-magic', '-', data=json.dumps(simulation).encode())
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)['schema_version'], '3')

    def test_public_v3_file_matches_native_and_saved_evidence_preserves_full_request(self):
        path = ROOT / 'docs/examples/m8/json/magic-balance-v3.request.json'
        data = json.loads(path.read_bytes())
        command = parse(path.read_bytes())
        before = deepcopy(command)
        self.assertEqual(command.schema_version, '3')
        self.assertIsNotNone(command.generation_request.stationary_wound_continuation)
        self.assertIsNotNone(command.generation_request.miscast_continuation)
        expected = json.loads(encode(command, execute_magic_balance(command)))
        completed = invoke('balance-magic', str(path))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, b'')
        actual = json.loads(completed.stdout)
        validate(actual, 'result', schema_version='3')
        self.assertEqual(actual, expected)
        self.assertEqual(actual['request'], data)
        self.assertEqual(parse(json.dumps(actual['request'])), command)
        self.assertEqual(command, before)
        # Historical aggregate values belong to their declared runtime; avoid
        # treating saved Monte Carlo observations as a cross-version oracle.
        saved = json.loads(path.with_name('magic-balance-v3.result.json').read_bytes())
        validate(saved, 'result', schema_version='3')
        self.assertEqual(saved['request'], data)
        self.assertEqual(parse(json.dumps(saved['request'])), command)
        self.assertEqual(saved['candidate_count'], command.generation_request.candidate_count)
        self.assertEqual(saved['planned_trials'], command.generation_request.planned_trials)
        self.assertLessEqual(saved['total_trials'], saved['planned_trials'])
        for report in saved['stage_reports']:
            self.assertEqual(report['total_trials'], sum(c['summary']['trials'] for c in report['candidates']))
            for candidate in report['candidates']:
                self.assertEqual(sum(candidate['summary']['outcome_counts'].values()), candidate['summary']['trials'])
        for value in saved['runtime'].values():
            self.assertIsInstance(value, str)
            self.assertTrue(value)


if __name__ == '__main__':
    unittest.main()
