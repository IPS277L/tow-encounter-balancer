"""Magic balance subprocess boundary, real spawn and late failure semantics."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.integration.test_m4_cli import environment, invoke, ROOT
from tests.unit.test_m8_magic_balance_json import document
from towr.adapters.magic_json_schema import validate_magic_balance_document as validate


def small_document():
    data=document()
    data['evaluation']['stages']=[dict(trials_per_candidate=1,keep=1),dict(trials_per_candidate=2,keep=1)]
    data['evaluation']['max_total_trials']=6
    return data


class M8MagicBalanceCliIntegrationTests(unittest.TestCase):
    def test_each_command_keeps_its_error_family_for_malformed_json(self):
        for command,kind in (('simulate','simulation_error'),('balance','balance_error'),
                ('simulate-melee','melee_simulation_error'),('balance-melee','melee_balance_error'),
                ('simulate-mixed','mixed_simulation_error'),('balance-mixed','mixed_balance_error'),
                ('simulate-magic','magic_simulation_error'),('balance-magic','magic_balance_error')):
            with self.subTest(command=command):
                completed=invoke(command,'-',data=b'{')
                self.assertEqual(completed.returncode,2,completed.stderr)
                self.assertEqual(json.loads(completed.stdout)['kind'],kind)

    def test_all_seven_previous_commands_and_magic_balance_reject_cross_family_requests(self):
        examples=ROOT/'docs/examples'
        cases=(('simulate','simulation_error','m4/ranged-v1.request.json'),
            ('balance','balance_error','m5/json/balance-v1.request.json'),
            ('simulate-melee','melee_simulation_error','m6/json/melee-simulation-v1.request.json'),
            ('balance-melee','melee_balance_error','m6/json/melee-balance-v1.request.json'),
            ('simulate-mixed','mixed_simulation_error','m7/json/mixed-simulation-v1.request.json'),
            ('balance-mixed','mixed_balance_error','m7/json/mixed-balance-v1.request.json'),
            ('simulate-magic','magic_simulation_error','m8/json/magic-simulation-v1.request.json'))
        for command,kind,path in cases:
            with self.subTest(command=command):
                rejected=invoke(command,'-',data=json.dumps(document()).encode())
                self.assertEqual(rejected.returncode,2,rejected.stderr)
                self.assertEqual(json.loads(rejected.stdout)['kind'],kind)
                rejected=invoke('balance-magic','-',data=(examples/path).read_bytes())
                self.assertEqual(rejected.returncode,2,rejected.stderr)
                actual=json.loads(rejected.stdout)
                self.assertEqual(actual['kind'],'magic_balance_error')
                self.assertEqual(actual['error']['code'],'invalid_input')

    def test_materialization_failure_after_successful_preflight_has_generation_context(self):
        from tests.unit.test_m8_magic_balance_json import generation_failure_document
        from towr.adapters.magic_balance_json import parse_magic_balance_request
        data=generation_failure_document()
        source=parse_magic_balance_request(json.dumps(data)).generation_request
        self.assertEqual((source.candidate_count,source.planned_trials),(4,16))
        completed=invoke('balance-magic','-',data=json.dumps(data).encode())
        self.assertEqual(completed.returncode,3,completed.stderr)
        actual=json.loads(completed.stdout);validate(actual,'error')
        self.assertEqual(actual['request_id'],data['request_id'])
        self.assertEqual(actual['error']['code'],'generation_failed')
        self.assertEqual(actual['error']['path'],'/generation')
        self.assertEqual(actual['error']['counts'],[1,0])
        self.assertEqual(actual['error']['candidate_id'],'magic:counts:1,0')
        self.assertIsNone(actual['error']['stage_index'])
        self.assertNotIn('stage_reports',actual)
        self.assertNotIn(b'Traceback',completed.stderr)

    def test_file_from_unrelated_cwd_returns_complete_source_bound_report(self):
        data=small_document()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'request.json'; path.write_text(json.dumps(data),encoding='utf-8')
            completed=invoke('balance-magic','request.json',cwd=directory)
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
            completed=invoke('balance-magic','-',data=json.dumps(data,ensure_ascii=False).encode('utf-8'))
            self.assertEqual(completed.returncode,0,completed.stderr)
            self.assertEqual(completed.stderr,b'')
            self.assertIn('подбор-雪'.encode('utf-8'),completed.stdout)
            actual=json.loads(completed.stdout); validate(actual,'result')
            self.assertEqual(actual['request'],data)
            actual['request'].pop('execution'); outputs.append(actual)
        self.assertEqual(outputs[0],outputs[1])

    def test_input_failures_return_only_error_envelopes(self):
        bad=document(); bad['evaluation']['max_total_trials']=15
        wrong_kind=document(); wrong_kind['kind']='npc_magic_simulation'
        for raw,code in ((b'{','invalid_json'),(b'\xff','invalid_json'),
                         (json.dumps(dict(document(),schema_version='2')).encode(),'unsupported_version'),
                         (json.dumps(bad).encode(),'invalid_input'),(json.dumps(wrong_kind).encode(),'invalid_input')):
            completed=invoke('balance-magic','-',data=raw)
            self.assertEqual(completed.returncode,2,completed.stderr)
            actual=json.loads(completed.stdout); validate(actual,'error')
            self.assertEqual(actual['error']['code'],code)
            self.assertEqual(set(actual),{'schema_version','kind','request_id','error'})
            self.assertIn(code.encode(),completed.stderr)
            self.assertNotIn(b'Traceback',completed.stderr)

    def test_help_usage_and_missing_input_files(self):
        completed=invoke('balance-magic','--help')
        self.assertEqual(completed.returncode,0)
        self.assertIn(b'INPUT',completed.stdout)
        for args in (('balance-magic',),('balance-magic','-','--workers','2')):
            completed=invoke(*args,data=b'')
            self.assertEqual(completed.returncode,2)
            self.assertEqual(completed.stdout,b'')
            self.assertIn(b'usage:',completed.stderr)
        with tempfile.TemporaryDirectory() as directory:
            for path in (Path(directory),Path(directory)/'missing.json'):
                completed=invoke('balance-magic',str(path))
                self.assertEqual(completed.returncode,4)
                self.assertEqual(completed.stdout,b'')
                self.assertIn(b'input I/O error',completed.stderr)

    def test_closed_output_or_diagnostic_pipe_preserves_exit_four(self):
        for name in ('stdout','stderr'):
            with subprocess.Popen([sys.executable,'-m','towr','balance-magic','-'],stdin=subprocess.PIPE,
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
                "with patch('towr.simulation.npc_magic_parallel.ProcessPoolExecutor', side_effect=OSError('private pool failure')):\n"
                "    raise SystemExit(main(['balance-magic','-']))\n")
        data=small_document(); data['execution']={'mode':'process','workers':2,'batch_size':1}
        completed=subprocess.run([sys.executable,'-c',script],input=json.dumps(data).encode(),capture_output=True,
                                 cwd=ROOT,env=environment(),timeout=45)
        self.assertEqual(completed.returncode,3,completed.stderr)
        actual=json.loads(completed.stdout); validate(actual,'error')
        self.assertEqual(actual['error']['code'],'evaluation_failed')
        self.assertEqual(actual['error']['stage_index'],0)
        self.assertEqual(actual['error']['path'],'/evaluation')
        self.assertIsNone(actual['error']['counts'])
        self.assertEqual(actual['error']['candidate_id'],'magic:counts:1,0')
        self.assertNotIn(b'private',completed.stderr); self.assertNotIn(b'Traceback',completed.stderr)


    def test_late_real_candidate_failure_has_no_partial_reports_or_fallback(self):
        script="""
from multiprocessing import active_children
from random import getstate
from unittest.mock import patch
from towr.cli import main
from towr.simulation import npc_magic_simulation as simulation
before,children=getstate(),{c.pid for c in active_children()}
original=simulation.run_npc_magic_trial
completed=[]
calls=0
error=RuntimeError('private late candidate failure')
error.add_note('private worker note')
def trial(request,index,**kwargs):
    global calls
    calls+=1
    if calls==3:
        raise error
    record=original(request,index,**kwargs)
    completed.append(record)
    return record
with patch.object(simulation,'run_npc_magic_trial',side_effect=trial) as called, \
     patch('towr.application.magic_evaluation_service.run_npc_magic_simulation_parallel',side_effect=AssertionError('backend fallback')) as process:
    status=main(['balance-magic','-'])
    assert status==3 and called.call_count==3 and [r.trial_index for r in completed]==[0,1]
    assert completed[0].source_scenario==completed[1].source_scenario
    process.assert_not_called()
    assert getstate()==before and {c.pid for c in active_children()}==children
    raise SystemExit(status)
"""
        data=document()
        completed=subprocess.run([sys.executable,'-c',script],input=json.dumps(data).encode(),capture_output=True,
            cwd=ROOT,env=environment(),timeout=45)
        self.assertEqual(completed.returncode,3,completed.stderr)
        actual=json.loads(completed.stdout);validate(actual,'error')
        self.assertEqual(actual['request_id'],data['request_id'])
        self.assertEqual(actual['error']['code'],'evaluation_failed')
        self.assertEqual(actual['error']['path'],'/evaluation')
        self.assertEqual(actual['error']['stage_index'],0)
        self.assertEqual(actual['error']['candidate_id'],'magic:counts:1,1')
        self.assertIsNone(actual['error']['counts'])
        self.assertNotIn('stage_reports',actual)
        self.assertNotIn('candidates',actual)
        self.assertNotIn(b'private',completed.stdout+completed.stderr)
        self.assertNotIn(b'Traceback',completed.stderr)
