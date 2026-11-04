"""Representative current PC command paths; errors never expose worker causes."""
from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters.pc_melee_json_schema import validate_pc_melee_balance_document, validate_pc_melee_simulation_document
from towr.application import pc_melee_service as service
from towr.application.pc_melee_commands import PcMeleeCommandExecutionError


ROOT=Path(__file__).resolve().parents[2]


def invoke(command,raw,*,console=False,cwd=None):
    environment=os.environ.copy()
    environment['PYTHONPATH']=str(ROOT/'src')
    executable=Path(sys.executable).with_name('towr.exe' if os.name=='nt' else 'towr')
    args=[str(executable)] if console else [sys.executable,'-m','towr']
    payload=raw if isinstance(raw,bytes) else json.dumps(raw,ensure_ascii=False).encode('utf-8')
    return subprocess.run([*args,command,'-'],input=payload,capture_output=True,
        cwd=cwd or ROOT,env=environment,timeout=90)


class PcMeleeCliIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.simulation=document(party_size=2,mixed=True)
        cls.balance=document(balance=True,party_size=2,mixed=True)
        cls.sim_command=wire.parse_pc_melee_simulation_request(json.dumps(cls.simulation))
        cls.bal_command=wire.parse_pc_melee_balance_request(json.dumps(cls.balance))
        cls.summary=service.execute_pc_melee_simulation(cls.sim_command)
        cls.report=service.execute_pc_melee_balance(cls.bal_command)

    def test_module_console_and_external_cwd_preserve_full_sources_summary_and_report(self):
        expected={
            'simulate-pc-melee':wire.encode_pc_melee_simulation_result(self.sim_command,self.summary),
            'balance-pc-melee':wire.encode_pc_melee_balance_result(self.bal_command,self.report),
        }
        with tempfile.TemporaryDirectory(prefix='towr-m9-cli-') as outside:
            for command,raw,validator in (
                ('simulate-pc-melee',self.simulation,validate_pc_melee_simulation_document),
                ('balance-pc-melee',self.balance,validate_pc_melee_balance_document)):
                for console in (False,True):
                    with self.subTest(command=command,console=console):
                        completed=invoke(command,raw,console=console,cwd=outside)
                        self.assertEqual(completed.returncode,0,completed.stderr)
                        self.assertEqual(completed.stderr,b'')
                        self.assertEqual(completed.stdout.decode('utf-8'),expected[command])
                        output=json.loads(completed.stdout)
                        validator(output,'result')
                        self.assertEqual(output['request'],raw)
                        self.assertEqual(output['request'].get('scenario',output['request'].get('template'))['party'][0]['fate']['rating'],3)
                        enemies=output['request'].get('scenario',output['request'].get('template'))['enemies']
                        self.assertEqual(enemies[1]['definition']['injury_policy'],'brute')
                        self.assertEqual(enemies[1]['definition']['wound_limit'],3)

    def test_console_process_preserves_actual_simulation_summary_and_explicit_execution(self):
        raw=deepcopy(self.simulation)
        raw['execution']={'mode':'process','workers':2,'batch_size':3}
        completed=invoke('simulate-pc-melee',raw,console=True)
        self.assertEqual(completed.returncode,0,completed.stderr)
        self.assertEqual(completed.stderr,b'')
        output=json.loads(completed.stdout)
        validate_pc_melee_simulation_document(output,'result')
        expected=json.loads(wire.encode_pc_melee_simulation_result(self.sim_command,self.summary))
        self.assertEqual(output['summary'],expected['summary'])
        self.assertEqual(output['request'],raw)

    def test_input_errors_retain_command_family_and_lexical_errors_do_not_trust_id(self):
        for command,raw,validator in (
            ('simulate-pc-melee',self.balance,validate_pc_melee_simulation_document),
            ('balance-pc-melee',self.simulation,validate_pc_melee_balance_document)):
            with self.subTest(command=command):
                completed=invoke(command,raw)
                self.assertEqual(completed.returncode,2)
                output=json.loads(completed.stdout)
                validator(output,'error')
                self.assertEqual(output['request_id'],raw['request_id'])
                self.assertEqual(output['error']['phase'],'input')
                self.assertTrue(completed.stderr.startswith(b'towr: '))
        completed=invoke('simulate-pc-melee',b'{"request_id":"untrusted","schema_version":"1","n":1.0}')
        self.assertEqual(completed.returncode,2)
        self.assertIsNone(json.loads(completed.stdout)['request_id'])
        raw=deepcopy(self.simulation)
        raw['scenario']['party'][1]['pc']['weapon_skill']=True
        completed=invoke('simulate-pc-melee',raw)
        self.assertEqual(completed.returncode,2)
        error=json.loads(completed.stdout)
        self.assertEqual(error['request_id'],raw['request_id'])
        self.assertEqual(error['error']['path'],'/scenario/party/1/pc/weapon_skill')
        raw=deepcopy(self.simulation)
        raw['scenario']['enemies'][1]['definition']['wound_limit']=True
        completed=invoke('simulate-pc-melee',raw)
        self.assertEqual(completed.returncode,2)
        error=json.loads(completed.stdout)
        self.assertEqual(error['request_id'],raw['request_id'])
        self.assertEqual(error['error']['path'],'/scenario/enemies/1/definition/wound_limit')

    def test_runtime_worker_cause_is_private_and_family_phase_remains_precise(self):
        scripts={
            'simulate-pc-melee':"from unittest.mock import patch\nfrom towr.cli import main\nwith patch('towr.application.pc_melee_service.run_pc_melee_simulation', side_effect=RuntimeError('private-worker-token')):\n    raise SystemExit(main(['simulate-pc-melee','-']))\n",
            'balance-pc-melee':"from unittest.mock import patch\nfrom towr.cli import main\nwith patch('towr.application.pc_melee_service.run_pc_melee_simulation', side_effect=RuntimeError('private-worker-token')):\n    raise SystemExit(main(['balance-pc-melee','-']))\n",
        }
        environment=os.environ.copy()
        environment['PYTHONPATH']=str(ROOT/'src')
        for command,raw,phase,validator in (
            ('simulate-pc-melee',self.simulation,'simulation',validate_pc_melee_simulation_document),
            ('balance-pc-melee',self.balance,'evaluation',validate_pc_melee_balance_document)):
            with self.subTest(command=command):
                completed=subprocess.run([sys.executable,'-c',scripts[command]],input=json.dumps(raw).encode(),
                    cwd=ROOT,env=environment,capture_output=True,timeout=45)
                self.assertEqual(completed.returncode,3,completed.stderr)
                output=json.loads(completed.stdout)
                validator(output,'error')
                self.assertEqual(output['request_id'],raw['request_id'])
                self.assertEqual(output['error']['phase'],phase)
                self.assertNotIn(b'private-worker-token',completed.stdout+completed.stderr)
                self.assertNotIn(b'Traceback',completed.stdout+completed.stderr)
                self.assertNotIn('summary',output)
                self.assertNotIn('candidates',output)

    def test_backend_selection_never_falls_back_and_corrupt_command_stops_before_rng(self):
        command=replace(self.sim_command,execution=replace(self.sim_command.execution,
            mode=type(self.sim_command.execution.mode).PROCESS,workers=1,batch_size=2))
        with patch.object(service,'run_pc_melee_simulation') as sequential,\
                patch.object(service,'run_pc_melee_simulation_parallel',side_effect=RuntimeError('pool failure')) as parallel:
            with self.assertRaises(PcMeleeCommandExecutionError) as caught:
                service.execute_pc_melee_simulation(command)
            self.assertEqual(caught.exception.phase,'simulation')
            sequential.assert_not_called()
            parallel.assert_called_once()
        forged=deepcopy(self.sim_command)
        object.__setattr__(forged.request.scenario.party[1].pc,'armour_bonus',False)
        self.assertEqual(forged,self.sim_command)
        with patch.object(service,'run_pc_melee_simulation') as sequential,\
                patch.object(service,'run_pc_melee_simulation_parallel') as parallel:
            with self.assertRaises(PcMeleeCommandExecutionError):
                service.execute_pc_melee_simulation(forged)
            sequential.assert_not_called()
            parallel.assert_not_called()


if __name__=='__main__':
    unittest.main()
