"""Three Empire loadouts use current PC JSON1, native trials and prefix search."""
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
from towr.adapters.pc_melee_json_errors import PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document,validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_service import execute_pc_melee_balance
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.test_models import Skill
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def chunk_document(*,balance=False):
    source=book_pc_scenario(peasants=2 if balance else 1,watch=1,militia=1,
        footpads=0,townsfolk=0,pc_count=2,max_rounds=3)
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            {'group_id':'peasants','actor_ids':['peasant1','peasant2'],'minimum_count':1,'maximum_count':2},
            {'group_id':'watch','actor_ids':['watch1'],'minimum_count':0,'maximum_count':1},
            {'group_id':'militia','actor_ids':['militia1'],'minimum_count':0,'maximum_count':1}],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':8}
        raw['evaluation'].update(trials_per_candidate=2,max_total_trials=16,top_k=2)
    else:
        raw['simulation']['trials']=2
    return raw


class PcEmpireChunkIntegrationTests(unittest.TestCase):
    def test_current_full_source_roundtrip_keeps_three_printed_loadouts_and_gear(self):
        for balance in (False,True):
            raw=chunk_document(balance=balance)
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source),raw['template' if balance else 'scenario'])
            self.assertEqual(raw['schema_version'],'1')
            for enemy in source.enemies:
                validate_pc_book_npc_definition(enemy.definition)
                self.assertFalse(enemy.state.holds_shield)
                self.assertIs(enemy.definition.protection[0].skill,Skill.ATHLETICS)
                attack=enemy.definition.attacks[0]
                self.assertEqual(attack.secondary_effects,())
                self.assertEqual(attack.range_max.value,'short' if enemy.state.actor_id=='watch1' else 'close')
                self.assertEqual(attack.hands.value,'2h' if enemy.state.actor_id=='watch1' else '1h')

    def test_full_source_rejects_changed_weapon_protection_range_and_shield_before_execution(self):
        for actor,field,value in (('peasant1','damage',3),('watch1','damage',7),('militia1','damage',4),
                ('watch1','range_max','close'),('peasant1','holds_shield',True),('militia1','skill','defence')):
            raw=chunk_document()
            enemy=next(e for e in raw['scenario']['enemies'] if e['actor_id']==actor)
            if field=='holds_shield':enemy[field]=value
            elif field=='skill':enemy['definition']['protection'][field]=value
            elif field=='damage':enemy['definition']['attack']['damage']['base']=value
            else:enemy['definition']['attack'][field]=value
            with self.subTest(actor=actor,field=field),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_actual_trials_and_summary_preserve_full_echo_and_original_actor_order(self):
        raw=chunk_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        result=run_pc_melee_simulation(command.request)
        summary=summarize_pc_melee_simulation(result)
        self.assertEqual((summary.source_request,summary.trials),(command.request,2))
        for record in result.records:
            self.assertEqual(record.source_scenario,command.request.scenario)
        self.assertEqual(tuple((c.actor_id,c.count) for c in summary.npc_exit_counts),
            (('peasant1',0),('watch1',0),('militia1',0)))
        output=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        validate_pc_melee_simulation_document(output,'result')
        self.assertEqual(output['request'],raw)
        self.assertFalse(hasattr(summary,'records'))

    def test_eight_count_candidates_keep_complete_definitions_priorities_and_gm_choices(self):
        raw=chunk_document(balance=True)
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        report=execute_pc_melee_balance(command)
        self.assertEqual((len(report.candidates),report.total_trials),(8,16))
        self.assertEqual(tuple(c.counts for c in report.candidates),tuple(product((1,2),(0,1),(0,1))))
        template=command.request.template
        originals={e.state.actor_id:e for e in template.enemies}
        for candidate in report.candidates:
            peasants,watch,militia=candidate.counts
            expected=tuple(f'peasant{i+1}' for i in range(peasants))+(('watch1',) if watch else ())+(
                ('militia1',) if militia else ())
            source=candidate.source_request.scenario
            self.assertEqual(tuple(e.state.actor_id for e in source.enemies),expected)
            self.assertEqual(source.enemy_activation_order,expected)
            for member,old in zip(source.party,template.party,strict=True):
                self.assertEqual(member.target_priority,expected)
                self.assertEqual(tuple(d.target_id for d in member.defeat_decisions),expected)
                self.assertEqual(replace(member,target_priority=old.target_priority,
                    defeat_decisions=old.defeat_decisions),old)
            for enemy in source.enemies:
                self.assertEqual(enemy,originals[enemy.state.actor_id])
                validate_pc_book_npc_definition(enemy.definition)
            self.assertFalse(hasattr(candidate.summary,'records'))
        output=json.loads(wire.encode_pc_melee_balance_result(command,report))
        validate_pc_melee_balance_document(output,'result')
        self.assertEqual(output['request'],raw)
        for candidate,typed in zip(output['candidates'],report.candidates,strict=True):
            self.assertEqual(candidate['request']['scenario'],scenario_document(typed.source_request.scenario))

    def test_cached_equal_shield_and_range_aliases_fail_full_readmission_before_rng(self):
        command=wire.parse_pc_melee_simulation_request(json.dumps(chunk_document()))
        for actor,field,value in (('peasant1','holds_shield',0),('watch1','range_max','short'),
                ('militia1','holds_shield',0)):
            forged=deepcopy(command.request)
            enemy=forged.scenario.enemy(actor)
            target=enemy.state if field=='holds_shield' else enemy.definition.attacks[0]
            object.__setattr__(target,field,value)
            self.assertEqual(forged,command.request)
            rng=Mock(side_effect=AssertionError('malformed source must not consume RNG'))
            runner=Mock(side_effect=AssertionError('malformed source must not become an observation'))
            with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',runner):
                with self.subTest(actor=actor),self.assertRaises(TypeError):
                    run_pc_melee_trial(forged,0,rng_factory=rng)
            rng.assert_not_called()
            runner.assert_not_called()


if __name__=='__main__':
    unittest.main()
