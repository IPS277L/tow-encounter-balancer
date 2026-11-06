"""Goblin shields and printed maximum Melee ranges survive current PC JSON1."""
from copy import deepcopy
from dataclasses import replace
from itertools import product
import json
import unittest
from unittest.mock import Mock,patch

from jsonschema import ValidationError

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
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.test_models import Skill
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def chunk_document(*,balance=False):
    source=book_pc_scenario(goblins=2 if balance else 1,skulkers=1,night_goblins=1,
        footpads=0,townsfolk=0,pc_count=2,max_rounds=3)
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            {'group_id':'goblins','actor_ids':['goblin1','goblin2'],'minimum_count':1,'maximum_count':2},
            {'group_id':'skulkers','actor_ids':['skulker1'],'minimum_count':0,'maximum_count':1},
            {'group_id':'night_goblins','actor_ids':['night_goblin1'],'minimum_count':0,'maximum_count':1}],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':8}
        raw['evaluation'].update(trials_per_candidate=2,max_total_trials=16,top_k=2)
    else:
        raw['simulation']['trials']=2
    return raw


class PcGoblinChunkIntegrationTests(unittest.TestCase):
    def test_current_source_roundtrip_keeps_actual_shields_and_printed_maximum_ranges(self):
        for balance in (False,True):
            raw=chunk_document(balance=balance)
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source),raw[key])
            self.assertEqual(raw['schema_version'],'1')
            for enemy,encoded in zip(source.enemies,raw[key]['enemies'],strict=True):
                validate_pc_book_npc_definition(enemy.definition)
                skulker=enemy.state.actor_id=='skulker1'
                self.assertIs(enemy.state.holds_shield,not skulker)
                self.assertIs(encoded['holds_shield'],not skulker)
                attack=enemy.definition.attacks[0]
                self.assertIs(attack.range_min,RangedWeaponRange.CLOSE)
                self.assertIs(attack.range_max,RangedWeaponRange.CLOSE if skulker else RangedWeaponRange.SHORT)
                self.assertEqual(encoded['definition']['attack']['range_max'],'close' if skulker else 'short')
                self.assertEqual(attack.secondary_effects,())
                self.assertIs(enemy.definition.protection[0].skill,Skill.DEFENCE if skulker else Skill.ATHLETICS)

    def test_new_fields_are_required_and_exact_at_both_public_entries(self):
        for balance in (False,True):
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            validate=validate_pc_melee_balance_document if balance else validate_pc_melee_simulation_document
            error=PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            for field,values in (('holds_shield',(None,0,1,'true',[])),
                    ('range_max',(None,False,1,'medium','long','SHORT',[]))):
                for value in values:
                    raw=chunk_document(balance=balance)
                    enemy=raw[key]['enemies'][0]
                    target=enemy if field=='holds_shield' else enemy['definition']['attack']
                    target[field]=value
                    with self.subTest(balance=balance,field=field,value=value):
                        with self.assertRaises(ValidationError):
                            validate(raw)
                        with self.assertRaises(error):
                            parse(json.dumps(raw))
                raw=chunk_document(balance=balance)
                enemy=raw[key]['enemies'][0]
                target=enemy if field=='holds_shield' else enemy['definition']['attack']
                del target[field]
                with self.subTest(balance=balance,missing=field),self.assertRaises(error):
                    parse(json.dumps(raw))

    def test_canonical_profiles_refuse_shield_removal_range_truncation_and_extra_resilience(self):
        for actor,field,value in (('goblin1','holds_shield',False),
                ('night_goblin1','holds_shield',False),('skulker1','holds_shield',True),
                ('goblin1','range_max','close'),('night_goblin1','range_max','close'),
                ('skulker1','range_max','short'),('goblin1','bonus',3),('night_goblin1','bonus',2)):
            raw=chunk_document()
            enemy=next(item for item in raw['scenario']['enemies'] if item['actor_id']==actor)
            if field=='holds_shield':target=enemy
            elif field=='range_max':target=enemy['definition']['attack']
            else:target=enemy['definition']['resilience']
            target[field]=value
            with self.subTest(actor=actor,field=field,value=value),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_actual_trials_and_current_result_echo_preserve_complete_sources(self):
        raw=chunk_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        result=run_pc_melee_simulation(command.request)
        summary=summarize_pc_melee_simulation(result)
        self.assertEqual(summary.source_request,command.request)
        self.assertEqual(summary.trials,2)
        for record in result.records:
            self.assertEqual(record.source_scenario,command.request.scenario)
        self.assertEqual(tuple((c.actor_id,c.count) for c in summary.npc_exit_counts),
            (('goblin1',0),('skulker1',0),('night_goblin1',0)))
        output=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        validate_pc_melee_simulation_document(output,'result')
        self.assertEqual(output['request'],raw)
        self.assertFalse(hasattr(summary,'records'))

    def test_eight_candidate_prefixes_keep_shields_ranges_and_per_actor_policies(self):
        raw=chunk_document(balance=True)
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        report=execute_pc_melee_balance(command)
        self.assertEqual((len(report.candidates),report.total_trials),(8,16))
        self.assertEqual(tuple(c.counts for c in report.candidates),tuple(product((1,2),(0,1),(0,1))))
        template=command.request.template
        originals={e.state.actor_id:e for e in template.enemies}
        for candidate in report.candidates:
            goblins,skulkers,night_goblins=candidate.counts
            expected=tuple(f'goblin{i+1}' for i in range(goblins))+(('skulker1',) if skulkers else ())+(
                ('night_goblin1',) if night_goblins else ())
            source=candidate.source_request.scenario
            self.assertEqual(tuple(e.state.actor_id for e in source.enemies),expected)
            self.assertEqual(source.enemy_activation_order,expected)
            for member,original in zip(source.party,template.party,strict=True):
                self.assertEqual(member.target_priority,expected)
                self.assertEqual(tuple(d.target_id for d in member.defeat_decisions),expected)
                self.assertEqual(replace(member,target_priority=original.target_priority,
                    defeat_decisions=original.defeat_decisions),original)
            for enemy in source.enemies:
                self.assertEqual(enemy,originals[enemy.state.actor_id])
                validate_pc_book_npc_definition(enemy.definition)
            self.assertFalse(hasattr(candidate.summary,'records'))
        output=json.loads(wire.encode_pc_melee_balance_result(command,report))
        validate_pc_melee_balance_document(output,'result')
        self.assertEqual(output['request'],raw)
        for candidate,typed in zip(output['candidates'],report.candidates,strict=True):
            self.assertEqual(candidate['request']['scenario'],scenario_document(typed.source_request.scenario))

    def test_cached_equal_shield_and_range_aliases_fail_before_rng_and_native_execution(self):
        command=wire.parse_pc_melee_simulation_request(json.dumps(chunk_document()))
        for actor,field,value in (('goblin1','holds_shield',1),('skulker1','holds_shield',0),
                ('night_goblin1','range_max','short'),('skulker1','range_max','close')):
            forged=deepcopy(command.request)
            enemy=forged.scenario.enemy(actor)
            target=enemy.state if field=='holds_shield' else enemy.definition.attacks[0]
            object.__setattr__(target,field,value)
            self.assertEqual(forged,command.request)
            rng=Mock(side_effect=AssertionError('malformed source cannot consume RNG'))
            runner=Mock(side_effect=AssertionError('malformed source cannot become an observation'))
            with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',runner):
                with self.subTest(actor=actor,field=field),self.assertRaises(TypeError):
                    run_pc_melee_trial(forged,0,rng_factory=rng)
            rng.assert_not_called()
            runner.assert_not_called()


if __name__=='__main__':
    unittest.main()
