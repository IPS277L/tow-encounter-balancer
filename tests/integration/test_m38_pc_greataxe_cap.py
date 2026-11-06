"""Only the canonical Minotaur Greataxe carries pool_cap8 through PC JSON1."""
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
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.ranged_weapon_profiles import RangedWeaponHands
from towr.domain.test_models import Skill
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def greataxe_document(*,balance=False):
    source=book_pc_scenario(minotaur_greataxes=2 if balance else 1,razorgors=1,
        footpads=0,townsfolk=0,pc_count=2,max_rounds=2)
    source=replace(source,party=tuple(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.AXE))
        for member in source.party))
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            {'group_id':'minotaur_greataxes','actor_ids':['minotaur_greataxe1','minotaur_greataxe2'],
             'minimum_count':1,'maximum_count':2},
            {'group_id':'razorgors','actor_ids':['razorgor1'],'minimum_count':0,'maximum_count':1}],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':4}
        raw['evaluation'].update(trials_per_candidate=1,max_total_trials=4,top_k=2)
    else:
        raw['simulation']['trials']=2
    return raw


class PcGreataxeCapIntegrationTests(unittest.TestCase):
    def test_current_requests_retain_canonical_attack_cap8_and_ordinary_protection_null(self):
        for balance in (False,True):
            raw=greataxe_document(balance=balance)
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source),raw[key])
            self.assertEqual(raw['schema_version'],'1')
            for enemy,encoded in zip(source.enemies,raw[key]['enemies'],strict=True):
                validate_pc_book_npc_definition(enemy.definition)
                attack,=enemy.definition.attacks
                protection,=enemy.definition.protection
                self.assertIsNone(protection.test_profile.pool_cap)
                self.assertIs(protection.skill,Skill.ATHLETICS)
                self.assertEqual((enemy.definition.wound_limit,enemy.definition.resilience.toughness,
                    enemy.definition.resilience.total),(3,5,6))
                if enemy.state.actor_id.startswith('minotaur_greataxe'):
                    self.assertEqual((attack.test_profile.dice,attack.test_profile.threshold,
                        attack.test_profile.pool_cap,attack.damage.base),(3,5,8,8))
                    self.assertIs(attack.hands,RangedWeaponHands.TWO_HANDED)
                    self.assertEqual(encoded['definition']['attack']['test_profile']['pool_cap'],8)
                else:
                    self.assertIsNone(attack.test_profile.pool_cap)
                self.assertIs(enemy.state.holds_shield,False)

    def test_malformed_missing_and_noncanonical_attack_caps_are_rejected_at_both_entries(self):
        for balance in (False,True):
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            validate=validate_pc_melee_balance_document if balance else validate_pc_melee_simulation_document
            error=PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            for cap in (None,6,7,9,True,False,8.0,'8',{},[]):
                raw=greataxe_document(balance=balance)
                raw[key]['enemies'][0]['definition']['attack']['test_profile']['pool_cap']=cap
                with self.subTest(balance=balance,cap=cap):
                    # JSON Schema numeric equality admits8.0 as8; exact source
                    # admission must still reject a float and reject null here.
                    if cap is None or type(cap) is float:
                        validate(raw)
                    else:
                        with self.assertRaises(ValidationError):validate(raw)
                    with self.assertRaises(error):parse(json.dumps(raw))
            raw=greataxe_document(balance=balance)
            del raw[key]['enemies'][0]['definition']['attack']['test_profile']['pool_cap']
            with self.assertRaises(ValidationError):validate(raw)
            with self.assertRaises(error):parse(json.dumps(raw))

    def test_schema_cap8_does_not_authorize_authored_or_other_book_attacks_or_protection(self):
        for balance in (False,True):
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            validate=validate_pc_melee_balance_document if balance else validate_pc_melee_simulation_document
            error=PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            authored=document(balance=balance)
            authored[key]['enemies'][0]['definition']['attack']['test_profile']['pool_cap']=8
            validate(authored)
            with self.assertRaises(error):parse(json.dumps(authored))
            for index,branch in ((0,'protection'),(-1,'attack')):
                raw=greataxe_document(balance=balance)
                raw[key]['enemies'][index]['definition'][branch]['test_profile']['pool_cap']=8
                validate(raw)
                with self.subTest(balance=balance,index=index,branch=branch),self.assertRaises(error):
                    parse(json.dumps(raw))

    def test_actual_trials_and_summary_echo_keep_cap8_without_new_metrics_or_journals(self):
        raw=greataxe_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        result=run_pc_melee_simulation(command.request)
        summary=summarize_pc_melee_simulation(result)
        self.assertEqual(summary.trials,2)
        self.assertEqual(summary.total_action_count,sum(record.executed_actions for record in result.records))
        self.assertEqual((summary.npc_help_action_trial_count,summary.total_npc_help_action_count),(0,0))
        for record in result.records:
            self.assertEqual(record.source_scenario,command.request.scenario)
            self.assertEqual(record.source_scenario.enemy('minotaur_greataxe1').definition.
                attacks[0].test_profile.pool_cap,8)
            self.assertFalse(hasattr(record,'steps'))
        encoded=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        validate_pc_melee_simulation_document(encoded,'result')
        self.assertEqual(encoded['request'],raw)
        self.assertEqual(encoded['summary']['total_action_count'],summary.total_action_count)
        self.assertFalse(hasattr(summary,'records'))

    def test_four_candidate_prefixes_retain_cap8_in_full_sources_and_result_echoes(self):
        raw=greataxe_document(balance=True)
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        report=execute_pc_melee_balance(command)
        self.assertEqual((len(report.candidates),report.total_trials),(4,4))
        self.assertEqual(tuple(candidate.counts for candidate in report.candidates),tuple(product((1,2),(0,1))))
        template=command.request.template
        originals={enemy.state.actor_id:enemy for enemy in template.enemies}
        for candidate in report.candidates:
            source=candidate.source_request.scenario
            retained=tuple(enemy.state.actor_id for enemy in source.enemies)
            self.assertEqual(source.enemy_activation_order,retained)
            for member,original in zip(source.party,template.party,strict=True):
                self.assertEqual(member.target_priority,tuple(actor for actor in original.target_priority if actor in retained))
            for enemy in source.enemies:
                self.assertEqual(enemy,originals[enemy.state.actor_id])
                expected=8 if enemy.state.actor_id.startswith('minotaur_greataxe') else None
                self.assertEqual(enemy.definition.attacks[0].test_profile.pool_cap,expected)
            self.assertFalse(hasattr(candidate.summary,'records'))
        encoded=json.loads(wire.encode_pc_melee_balance_result(command,report))
        validate_pc_melee_balance_document(encoded,'result')
        self.assertEqual(encoded['request'],raw)
        for item,candidate in zip(encoded['candidates'],report.candidates,strict=True):
            self.assertEqual(item['request']['scenario'],scenario_document(candidate.source_request.scenario))

    def test_partial_source_renames_and_cached_numeric_aliases_cannot_bypass_the_cap_gate(self):
        raw=greataxe_document()
        definition=raw['scenario']['enemies'][0]['definition']
        definition.update(id='authored:renamed',source_rule_id='authored:source')
        with self.assertRaises(PcMeleeSimulationInputError):
            wire.parse_pc_melee_simulation_request(json.dumps(raw))
        command=wire.parse_pc_melee_simulation_request(json.dumps(greataxe_document()))
        for branch,field,value in (('test_profile','pool_cap',8.0),
                ('damage','success_multiplier',True),('state','wields_weapon',1)):
            forged=deepcopy(command.request)
            enemy=forged.scenario.enemy('minotaur_greataxe1')
            target=enemy.state if branch=='state' else getattr(enemy.definition.attacks[0],branch)
            object.__setattr__(target,field,value)
            self.assertEqual(forged,command.request)
            rng=Mock(side_effect=AssertionError('malformed source cannot consume RNG'))
            runner=Mock(side_effect=AssertionError('malformed source cannot become an observation'))
            with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',runner):
                with self.subTest(branch=branch,field=field),self.assertRaises(TypeError):
                    run_pc_melee_trial(forged,0,rng_factory=rng)
            rng.assert_not_called()
            runner.assert_not_called()


if __name__=='__main__':
    unittest.main()
