"""Three printed Brutes share current PC JSON1 and bounded count-search execution."""
from copy import deepcopy
from dataclasses import replace
from itertools import product
import json
import unittest
from unittest.mock import Mock,patch

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeSimulationInputError,PcMeleeBalanceInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document,validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_service import execute_pc_melee_balance
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.test_models import Skill
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def chunk_document(*,balance=False):
    source=book_pc_scenario(empire_knights=2 if balance else 1,wolf_knights=1,big_uns=1,
        footpads=0,townsfolk=0,pc_count=2,max_rounds=3)
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            {'group_id':'empire_knights','actor_ids':['empire_knight1','empire_knight2'],
             'minimum_count':1,'maximum_count':2},
            {'group_id':'wolf_knights','actor_ids':['wolf_knight1'],'minimum_count':0,'maximum_count':1},
            {'group_id':'big_uns','actor_ids':['big_un1'],'minimum_count':0,'maximum_count':1}],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':8}
        raw['evaluation'].update(trials_per_candidate=2,max_total_trials=16,top_k=2)
    else:
        raw['simulation']['trials']=2
    return raw


class PcBruteChunkIntegrationTests(unittest.TestCase):
    def test_current_full_source_roundtrip_keeps_three_exact_armoured_shield_free_brutes(self):
        for balance in (False,True):
            raw=chunk_document(balance=balance)
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source),raw[key])
            self.assertEqual(raw['schema_version'],'1')
            for enemy in source.enemies:
                validate_pc_book_npc_definition(enemy.definition)
                self.assertEqual((enemy.definition.wound_limit,enemy.definition.resilience.total),(2,5))
                self.assertIs(enemy.definition.protection[0].skill,Skill.DEFENCE)
                self.assertEqual(enemy.definition.attacks[0].secondary_effects,())
                self.assertIs(enemy.state.wields_weapon,True)
                self.assertIs(enemy.state.holds_shield,False)

    def test_restored_shield_mount_and_wrong_big_un_damage_are_rejected_at_both_entries(self):
        for balance in (False,True):
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            error=PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            for actor,field,value in (('empire_knight1','bonus',3),('wolf_knight1','bonus',3),
                    ('big_un1','bonus',2),('big_un1','damage',4),('big_un1','damage',6)):
                raw=chunk_document(balance=balance)
                definition=next(e['definition'] for e in raw[key]['enemies'] if e['actor_id']==actor)
                if field=='bonus':
                    definition['resilience']['bonus']=value
                else:
                    definition['attack']['damage']['base']=value
                with self.subTest(balance=balance,actor=actor,field=field,value=value),self.assertRaises(error):
                    parse(json.dumps(raw))

    def test_native_trials_and_result_echo_preserve_all_profiles_and_aggregate_only_summary(self):
        raw=chunk_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        result=run_pc_melee_simulation(command.request)
        summary=summarize_pc_melee_simulation(result)
        self.assertEqual(summary.source_request,command.request)
        self.assertEqual(summary.trials,2)
        for record in result.records:
            self.assertEqual(record.source_scenario,command.request.scenario)
        self.assertEqual(tuple((c.actor_id,c.count) for c in summary.npc_exit_counts),
            (('empire_knight1',0),('wolf_knight1',0),('big_un1',0)))
        output=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        validate_pc_melee_simulation_document(output,'result')
        self.assertEqual(output['request'],raw)
        self.assertFalse(hasattr(summary,'records'))

    def test_eight_candidate_compositions_preserve_full_sources_priorities_and_defeat_decisions(self):
        raw=chunk_document(balance=True)
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        report=execute_pc_melee_balance(command)
        self.assertEqual((len(report.candidates),report.total_trials),(8,16))
        self.assertEqual(tuple(c.counts for c in report.candidates),tuple(product((1,2),(0,1),(0,1))))
        template=command.request.template
        originals={e.state.actor_id:e.definition for e in template.enemies}
        for candidate in report.candidates:
            knights,wolves,orcs=candidate.counts
            expected=tuple(f'empire_knight{i+1}' for i in range(knights))+(('wolf_knight1',) if wolves else ())+(
                ('big_un1',) if orcs else ())
            source=candidate.source_request.scenario
            self.assertEqual(tuple(e.state.actor_id for e in source.enemies),expected)
            self.assertEqual(source.enemy_activation_order,expected)
            for member,original in zip(source.party,template.party,strict=True):
                self.assertEqual(member.target_priority,expected)
                self.assertEqual(tuple(d.target_id for d in member.defeat_decisions),expected)
                self.assertEqual(replace(member,target_priority=original.target_priority,
                    defeat_decisions=original.defeat_decisions),original)
            for enemy in source.enemies:
                self.assertEqual(enemy.definition,originals[enemy.state.actor_id])
                validate_pc_book_npc_definition(enemy.definition)
            self.assertFalse(hasattr(candidate.summary,'records'))
        output=json.loads(wire.encode_pc_melee_balance_result(command,report))
        validate_pc_melee_balance_document(output,'result')
        self.assertEqual(output['request'],raw)
        for candidate,typed in zip(output['candidates'],report.candidates,strict=True):
            self.assertEqual(candidate['request']['scenario'],scenario_document(typed.source_request.scenario))

    def test_cached_equal_aliases_are_rejected_before_rng_and_native_execution(self):
        command=wire.parse_pc_melee_simulation_request(json.dumps(chunk_document()))
        for actor,value in (('empire_knight1',1),('wolf_knight1',1),('big_un1',1)):
            forged=deepcopy(command.request)
            object.__setattr__(forged.scenario.enemy(actor).state,'wields_weapon',value)
            self.assertEqual(forged,command.request)
            rng=Mock(side_effect=AssertionError('malformed source cannot consume RNG'))
            runner=Mock(side_effect=AssertionError('malformed source cannot become an observation'))
            with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',runner):
                with self.subTest(actor=actor),self.assertRaises(TypeError):
                    run_pc_melee_trial(forged,0,rng_factory=rng)
            rng.assert_not_called()
            runner.assert_not_called()


if __name__=='__main__':
    unittest.main()
