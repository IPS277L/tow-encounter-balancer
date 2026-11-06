"""Canonical Stealth passes current PC JSON1, compact trials and count search."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import json
import unittest
from unittest.mock import Mock,patch

from jsonschema import ValidationError

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError,PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document,validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_service import execute_pc_melee_balance
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_melee_result_models import PcAttackProof
from towr.domain.protection_models import NOW_YOU_SEE_ME_RULE_ID
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def thief_document(*,balance=False):
    source=book_pc_scenario(thieves=2 if balance else 1,footpads=1,townsfolk=0,
        pc_count=2,max_rounds=2)
    source=replace(source,party=tuple(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.AXE))
        for member in source.party))
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            dict(group_id='thieves',actor_ids=['thief1','thief2'],minimum_count=0,maximum_count=2),
            dict(group_id='footpads',actor_ids=['footpad1'],minimum_count=1,maximum_count=1)],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':3}
        raw['evaluation'].update(master_seed='42',trials_per_candidate=1,max_total_trials=3,top_k=2)
    else:
        raw['simulation'].update(master_seed='42',trials=2)
    return raw


class PcHalflingJsonTests(unittest.TestCase):
    def test_complete_canonical_source_roundtrips_both_current_requests_without_new_fields(self):
        for balance in (False,True):
            raw=thief_document(balance=balance)
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source),raw['template' if balance else 'scenario'])
            self.assertEqual(raw['schema_version'],'1')
            self.assertIs(source.enemies[0].definition.protection[0].skill,Skill.STEALTH)
            self.assertEqual(source.enemy_target_priority,('pc1','pc2'))
            self.assertEqual(source.npc_grudge_policies,())
            self.assertNotIn('halfling_stealth_permission',raw['template' if balance else 'scenario'])

    def test_schema_limits_stealth_to_canonical_identity_source_and_numeric_profile(self):
        changes=(('id','authored:thief'),('source_rule_id','authored:source'),
            ('protection.source_rule_id','authored:stealth'),('protection.test_profile.dice',2),
            ('protection.test_profile.threshold',4),('protection.test_profile.pool_cap',6))
        for balance in (False,True):
            key='template' if balance else 'scenario'
            validate=validate_pc_melee_balance_document if balance else validate_pc_melee_simulation_document
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            error=PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            for path,value in changes:
                raw=thief_document(balance=balance)
                target=raw[key]['enemies'][0]['definition']
                parts=path.split('.')
                for part in parts[:-1]:target=target[part]
                target[parts[-1]]=value
                with self.subTest(balance=balance,path=path):
                    with self.assertRaises(ValidationError):validate(raw)
                    with self.assertRaises(error):parse(json.dumps(raw))
            raw=thief_document(balance=balance)
            raw[key]['enemies'][-1]['definition']['protection']['skill']='stealth'
            with self.assertRaises(ValidationError):validate(raw)

    def test_full_native_admission_still_rejects_other_forged_canonical_fields(self):
        for path,value in (('attack.test_profile.dice',3),('attack.damage.base_damage',2),
                ('resilience.toughness',3),('protection.skill','athletics')):
            raw=thief_document()
            target=raw['scenario']['enemies'][0]['definition']
            parts=path.split('.')
            for part in parts[:-1]:target=target[part]
            target[parts[-1]]=value
            with self.subTest(path=path),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_real_trials_keep_stealth_proofs_out_of_compact_records_and_preserve_costs(self):
        raw=thief_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        native=[]
        def observe(source,rng):
            result=run_pc_melee_scenario(source,rng)
            native.append(result)
            return result
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',side_effect=observe):
            result=run_pc_melee_simulation(command.request)
        summary=summarize_pc_melee_simulation(result)
        for battle,record in zip(native,result.records,strict=True):
            proofs=tuple(s.proof for s in battle.steps if type(s.proof) is PcAttackProof
                and s.proof.request.target_id=='thief1')
            self.assertTrue(proofs)
            self.assertTrue(all(NOW_YOU_SEE_ME_RULE_ID in p.protection.applied_rule_ids for p in proofs))
            self.assertEqual(record.executed_actions,battle.executed_actions)
            self.assertEqual(record.source_scenario,command.request.scenario)
            self.assertFalse(hasattr(record,'steps'))
        self.assertEqual(summary.total_action_count,sum(r.executed_actions for r in result.records))
        encoded=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        validate_pc_melee_simulation_document(encoded,'result')
        self.assertEqual(encoded['request'],raw)

    def test_count_search_and_every_result_source_keep_exact_stealth_profile(self):
        raw=thief_document(balance=True)
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        report=execute_pc_melee_balance(command)
        self.assertEqual((len(report.candidates),report.total_trials),(3,3))
        self.assertEqual(tuple(c.counts for c in report.candidates),((0,1),(1,1),(2,1)))
        encoded=json.loads(wire.encode_pc_melee_balance_result(command,report))
        validate_pc_melee_balance_document(encoded,'result')
        self.assertEqual(encoded['request'],raw)
        for item,candidate in zip(encoded['candidates'],report.candidates,strict=True):
            self.assertEqual(item['request']['scenario'],scenario_document(candidate.source_request.scenario))
            for enemy in item['request']['scenario']['enemies']:
                if enemy['actor_id'].startswith('thief'):
                    self.assertEqual(enemy['definition'],raw['template']['enemies'][0]['definition'])
        forged=deepcopy(encoded)
        source=next(c['request']['scenario'] for c in forged['candidates']
            if any(e['actor_id']=='thief1' for e in c['request']['scenario']['enemies']))
        source['enemies'][0]['definition']['source_rule_id']='authored:source'
        with self.assertRaises(ValidationError):validate_pc_melee_balance_document(forged,'result')

    def test_cached_equal_skill_alias_cannot_reach_rng_or_trial(self):
        class Alias(str,Enum):
            STEALTH='stealth'
        command=wire.parse_pc_melee_simulation_request(json.dumps(thief_document()))
        forged=deepcopy(command.request)
        object.__setattr__(forged.scenario.enemies[0].definition.protection[0],'skill',Alias.STEALTH)
        self.assertEqual(forged,command.request)
        rng=Mock(side_effect=AssertionError('malformed source cannot consume RNG'))
        runner=Mock(side_effect=AssertionError('malformed source cannot enter runner'))
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',runner):
            with self.assertRaises(TypeError):run_pc_melee_trial(forged,0,rng_factory=rng)
        rng.assert_not_called()
        runner.assert_not_called()
