import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.integration.test_m4_cli import environment, invoke, ROOT
from tests.unit.test_m7_mixed_balance_json import document
from towr.adapters.mixed_json_schema import validate_mixed_balance_document as validate


def small_document():
    data=document()
    data['evaluation']['stages']=[dict(trials_per_candidate=1,keep=1),dict(trials_per_candidate=2,keep=1)]
    data['evaluation']['max_total_trials']=6
    return data


class M7MixedBalanceCliIntegrationTests(unittest.TestCase):
    def test_each_command_keeps_its_error_family_for_malformed_json(self):
        for command, kind in (('simulate', 'simulation_error'), ('balance', 'balance_error'),
                              ('simulate-melee', 'melee_simulation_error'), ('balance-melee', 'melee_balance_error'),
                              ('simulate-mixed', 'mixed_simulation_error'), ('balance-mixed', 'mixed_balance_error')):
            completed = invoke(command, '-', data=b'{')
            self.assertEqual(completed.returncode, 2, completed.stderr)
            self.assertEqual(json.loads(completed.stdout)['kind'], kind)

    def test_commands_reject_cross_family_requests(self):
        from tests.unit.test_m5_ranged_balance_json import document as ranged_balance
        from tests.unit.test_m7_mixed_json import document as mixed_simulation
        from tests.unit.test_m6_melee_balance_json import document as melee_balance
        for command, data, kind in (
            ('balance-mixed', ranged_balance(), 'mixed_balance_error'),
            ('balance-mixed', melee_balance(), 'mixed_balance_error'),
            ('balance-melee', document(), 'melee_balance_error'),
            ('balance-mixed', mixed_simulation(), 'mixed_balance_error'),
            ('balance', document(), 'balance_error'),
            ('simulate-mixed', document(), 'mixed_simulation_error'),
        ):
            with self.subTest(command=command):
                completed = invoke(command, '-', data=json.dumps(data).encode())
                self.assertEqual(completed.returncode, 2, completed.stderr)
                actual = json.loads(completed.stdout)
                self.assertEqual(actual['kind'], kind)
                self.assertEqual(actual['error']['code'], 'invalid_input')

    def test_materialization_failure_has_generation_status_and_context(self):
        data = small_document()
        data['generation']['groups'][0]['minimum_count'] = 0
        data['generation']['max_candidates'] = 5
        data['evaluation']['max_total_trials'] = 7
        completed = invoke('balance-mixed', '-', data=json.dumps(data).encode())
        self.assertEqual(completed.returncode, 3, completed.stderr)
        actual = json.loads(completed.stdout); validate(actual, 'error')
        self.assertEqual(actual['request_id'], data['request_id'])
        self.assertEqual(actual['error']['code'], 'generation_failed')
        self.assertEqual(actual['error']['counts'], [0, 1])
        self.assertEqual(actual['error']['candidate_id'], 'mixed:counts:0,1')
        self.assertIsNone(actual['error']['stage_index'])
        self.assertNotIn(b'private', completed.stdout + completed.stderr)
        self.assertNotIn(b'Traceback', completed.stderr)

    def test_file_from_unrelated_cwd_returns_complete_source_bound_report(self):
        data=small_document()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'request.json'; path.write_text(json.dumps(data),encoding='utf-8')
            completed=invoke('balance-mixed','request.json',cwd=directory)
        self.assertEqual(completed.returncode,0,completed.stderr)
        self.assertEqual(completed.stderr,b'')
        self.assertTrue(completed.stdout.endswith(b'\n'))
        actual=json.loads(completed.stdout); validate(actual,'result')
        self.assertEqual(actual['request'],data)
        self.assertEqual(actual['candidate_count'],4)
        self.assertLessEqual(actual['total_trials'],6)
        self.assertNotIn('trial_index',completed.stdout.decode('utf-8'))

    def test_unicode_stdin_and_real_spawn_have_equal_aggregates(self):
        data=small_document(); data['request_id']='подбор-雪'
        outputs=[]
        for execution in ({'mode':'sequential'},{'mode':'process','workers':2,'batch_size':1}):
            data['execution']=execution
            completed=invoke('balance-mixed','-',data=json.dumps(data,ensure_ascii=False).encode('utf-8'))
            self.assertEqual(completed.returncode,0,completed.stderr)
            self.assertEqual(completed.stderr,b'')
            self.assertIn('подбор-雪'.encode('utf-8'),completed.stdout)
            actual=json.loads(completed.stdout); validate(actual,'result')
            self.assertEqual(actual['request'],data)
            actual['request'].pop('execution'); outputs.append(actual)
        self.assertEqual(outputs[0],outputs[1])

    def test_input_failures_return_only_error_envelopes(self):
        bad=document(); bad['evaluation']['max_total_trials']=15
        wrong_kind=document(); wrong_kind['kind']='npc_mixed_simulation'
        for raw,code in ((b'{','invalid_json'),(b'\xff','invalid_json'),
                         (json.dumps(dict(document(),schema_version='2')).encode(),'unsupported_version'),
                         (json.dumps(bad).encode(),'invalid_input'),(json.dumps(wrong_kind).encode(),'invalid_input')):
            completed=invoke('balance-mixed','-',data=raw)
            self.assertEqual(completed.returncode,2,completed.stderr)
            actual=json.loads(completed.stdout); validate(actual,'error')
            self.assertEqual(actual['error']['code'],code)
            self.assertEqual(set(actual),{'schema_version','kind','request_id','error'})
            self.assertIn(code.encode(),completed.stderr)
            self.assertNotIn(b'Traceback',completed.stderr)

    def test_help_usage_and_missing_input_files(self):
        completed=invoke('balance-mixed','--help')
        self.assertEqual(completed.returncode,0)
        self.assertIn(b'INPUT',completed.stdout)
        for args in (('balance-mixed',),('balance-mixed','-','--workers','2')):
            completed=invoke(*args,data=b'')
            self.assertEqual(completed.returncode,2)
            self.assertEqual(completed.stdout,b'')
            self.assertIn(b'usage:',completed.stderr)
        with tempfile.TemporaryDirectory() as directory:
            for path in (Path(directory),Path(directory)/'missing.json'):
                completed=invoke('balance-mixed',str(path))
                self.assertEqual(completed.returncode,4)
                self.assertEqual(completed.stdout,b'')
                self.assertIn(b'input I/O error',completed.stderr)

    def test_closed_output_or_diagnostic_pipe_preserves_exit_four(self):
        for name in ('stdout','stderr'):
            with subprocess.Popen([sys.executable,'-m','towr','balance-mixed','-'],stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=ROOT,env=environment()) as process:
                getattr(process,name).close(); setattr(process,name,None)
                stdout,stderr=process.communicate(b'{',timeout=45)
            self.assertEqual(process.returncode,4,stderr)
            if name=='stdout':
                self.assertIn(b'output I/O error',stderr)
                self.assertNotIn(b'Traceback',stderr); self.assertNotIn(b'Exception ignored',stderr)
            else:
                self.assertEqual(json.loads(stdout)['error']['code'],'invalid_json')

    def test_pool_failure_is_execution_error_with_stage_and_candidate(self):
        script=("from unittest.mock import patch\nfrom towr.cli import main\n"
                "with patch('towr.simulation.npc_mixed_parallel.ProcessPoolExecutor', side_effect=OSError('private pool failure')):\n"
                "    raise SystemExit(main(['balance-mixed','-']))\n")
        data=small_document(); data['execution']={'mode':'process','workers':2,'batch_size':1}
        completed=subprocess.run([sys.executable,'-c',script],input=json.dumps(data).encode(),capture_output=True,
                                 cwd=ROOT,env=environment(),timeout=45)
        self.assertEqual(completed.returncode,3,completed.stderr)
        actual=json.loads(completed.stdout); validate(actual,'error')
        self.assertEqual(actual['error']['code'],'execution_failed')
        self.assertEqual(actual['error']['stage_index'],0)
        self.assertEqual(actual['error']['candidate_id'],'mixed:counts:1,0')
        self.assertNotIn(b'private',completed.stderr); self.assertNotIn(b'Traceback',completed.stderr)
