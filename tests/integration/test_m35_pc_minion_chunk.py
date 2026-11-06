"""Three printed Minions retain gear, named Help and exact sources through PC JSON1."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
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
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy
from towr.domain.ranged_weapon_profiles import RangedWeaponHands,RangedWeaponRange
from towr.domain.test_models import Skill
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def chunk_document(*,balance=False):
    source=book_pc_scenario(cultists=2 if balance else 1,elf_militia=1,ungors=1,
        footpads=0,townsfolk=0,pc_count=1,max_rounds=2)
    cultists=('cultist1','cultist2') if balance else ('cultist1',)
    priority=('ungor1','elf_militia1',*cultists)
    source=replace(source,npc_help_policies=tuple(PcNpcHelpPolicy(actor,'ungor1') for actor in cultists),
        party=tuple(replace(member,target_priority=priority,
            defeat_decisions=tuple(member.defeat_decision(actor) for actor in priority))
            for member in source.party))
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            {'group_id':'cultists','actor_ids':['cultist1','cultist2'],'minimum_count':1,'maximum_count':2},
            {'group_id':'elf_militia','actor_ids':['elf_militia1'],'minimum_count':0,'maximum_count':1},
            {'group_id':'ungors','actor_ids':['ungor1'],'minimum_count':0,'maximum_count':1}],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':8}
        raw['evaluation'].update(trials_per_candidate=1,max_total_trials=8,top_k=2)
    else:
        raw['simulation']['trials']=2
    return raw


class PcMinionChunkIntegrationTests(unittest.TestCase):
    def test_current_json_roundtrip_preserves_three_printed_gear_and_range_profiles(self):
        for balance in (False,True):
            raw=chunk_document(balance=balance)
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source),raw[key])
            self.assertEqual(raw['schema_version'],'1')
            for enemy in source.enemies:
                actor=enemy.state.actor_id
                attack,=enemy.definition.attacks
                validate_pc_book_npc_definition(enemy.definition)
                self.assertIs(enemy.definition.protection[0].skill,Skill.ATHLETICS)
                self.assertEqual(attack.secondary_effects,())
                if actor.startswith('cultist'):
                    self.assertEqual((attack.test_profile.dice,attack.test_profile.threshold,
                        attack.damage.base,enemy.definition.resilience.total),(3,3,3,3))
                    self.assertIs(attack.hands,RangedWeaponHands.ONE_HANDED)
                    self.assertIs(attack.range_max,RangedWeaponRange.CLOSE)
                    self.assertIs(enemy.state.holds_shield,False)
                elif actor=='elf_militia1':
                    self.assertEqual((attack.test_profile.dice,attack.test_profile.threshold,
                        attack.damage.base,enemy.definition.resilience.total),(4,3,4,4))
                    self.assertIs(attack.hands,RangedWeaponHands.TWO_HANDED)
                    self.assertIs(attack.range_max,RangedWeaponRange.SHORT)
                    self.assertTrue(enemy.definition.resilience.is_armoured)
                    self.assertIs(enemy.state.holds_shield,False)
                else:
                    self.assertEqual(actor,'ungor1')
                    self.assertEqual((attack.test_profile.dice,attack.test_profile.threshold,
                        attack.damage.base,enemy.definition.resilience.total),(3,3,3,4))
                    self.assertIs(attack.hands,RangedWeaponHands.ONE_HANDED)
                    self.assertIs(attack.range_max,RangedWeaponRange.SHORT)
                    self.assertIs(enemy.state.holds_shield,True)

    def test_native_trials_and_encoded_summary_keep_full_source_and_actual_help_costs(self):
        raw=chunk_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        result=run_pc_melee_simulation(command.request)
        summary=summarize_pc_melee_simulation(result)
        self.assertEqual(summary.source_request,command.request)
        self.assertEqual(summary.trials,2)
        self.assertEqual(summary.npc_help_action_trial_count,
            sum(any(item.count for item in record.npc_help_action_counts) for record in result.records))
        self.assertEqual(summary.total_npc_help_action_count,
            sum(item.count for record in result.records for item in record.npc_help_action_counts))
        for record in result.records:
            self.assertEqual(record.source_scenario,command.request.scenario)
            self.assertEqual(tuple(item.actor_id for item in record.npc_help_action_counts),
                ('cultist1','elf_militia1','ungor1'))
            self.assertEqual(tuple(item.count for item in record.npc_help_action_counts[1:]),(0,0))
            self.assertLessEqual(sum(item.count for item in record.npc_help_action_counts),record.executed_actions)
            self.assertFalse(hasattr(record,'steps'))
        encoded=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        validate_pc_melee_simulation_document(encoded,'result')
        self.assertEqual(encoded['request'],raw)
        self.assertEqual(encoded['summary']['npc_help_action_counts'],
            [{'actor_id':item.actor_id,'count':item.count} for item in summary.npc_help_action_counts])
        self.assertFalse(hasattr(summary,'records'))

    def test_eight_candidate_prefixes_keep_sources_and_remove_each_missing_help_endpoint(self):
        raw=chunk_document(balance=True)
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        report=execute_pc_melee_balance(command)
        self.assertEqual((len(report.candidates),report.total_trials),(8,8))
        self.assertEqual(tuple(candidate.counts for candidate in report.candidates),
            tuple(product((1,2),(0,1),(0,1))))
        template=command.request.template
        originals={enemy.state.actor_id:enemy for enemy in template.enemies}
        for candidate in report.candidates:
            source=candidate.source_request.scenario
            retained=tuple(enemy.state.actor_id for enemy in source.enemies)
            self.assertEqual(source.npc_help_policies,tuple(policy for policy in template.npc_help_policies
                if policy.helper_id in retained and policy.beneficiary_id in retained))
            self.assertEqual(source.enemy_activation_order,
                tuple(actor for actor in template.enemy_activation_order if actor in retained))
            self.assertEqual(source.party[0].target_priority,
                tuple(actor for actor in template.party[0].target_priority if actor in retained))
            self.assertEqual(tuple(item.target_id for item in source.party[0].defeat_decisions),
                source.party[0].target_priority)
            self.assertEqual(tuple(item.actor_id for item in candidate.summary.npc_help_action_counts),retained)
            for enemy in source.enemies:
                self.assertEqual(enemy,originals[enemy.state.actor_id])
                validate_pc_book_npc_definition(enemy.definition)
            if 'ungor1' not in retained:
                self.assertEqual(source.npc_help_policies,())
                self.assertEqual(candidate.summary.total_npc_help_action_count,0)
            self.assertFalse(hasattr(candidate.summary,'records'))
        encoded=json.loads(wire.encode_pc_melee_balance_result(command,report))
        validate_pc_melee_balance_document(encoded,'result')
        self.assertEqual(encoded['request'],raw)
        for item,candidate in zip(encoded['candidates'],report.candidates,strict=True):
            self.assertEqual(item['request']['scenario'],scenario_document(candidate.source_request.scenario))

    def test_public_entries_reject_altered_printed_damage_shield_range_and_protection(self):
        changes=(('cultist1','damage',4),('cultist1','hands','2h'),
            ('elf_militia1','range_max','close'),('elf_militia1','bonus',0),
            ('ungor1','holds_shield',False),('ungor1','range_max','close'),
            ('ungor1','protection_skill','defence'))
        for balance in (False,True):
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            error=PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            for actor,field,value in changes:
                raw=chunk_document(balance=balance)
                enemy=next(item for item in raw[key]['enemies'] if item['actor_id']==actor)
                if field=='holds_shield':enemy[field]=value
                elif field=='damage':enemy['definition']['attack']['damage']['base']=value
                elif field=='bonus':enemy['definition']['resilience'][field]=value
                elif field=='protection_skill':enemy['definition']['protection']['skill']=value
                else:enemy['definition']['attack'][field]=value
                with self.subTest(balance=balance,actor=actor,field=field),self.assertRaises(error):
                    parse(json.dumps(raw))
            raw=chunk_document(balance=balance)
            raw[key]['npc_help_policies']=[{'helper_id':'elf_militia1','beneficiary_id':'ungor1'}]
            with self.assertRaises(error):parse(json.dumps(raw))

    def test_cached_equal_source_aliases_fail_before_rng_or_native_execution(self):
        class Alias(str,Enum):
            CULTIST='cultist1'
        command=wire.parse_pc_melee_simulation_request(json.dumps(chunk_document()))
        for actor,field,value in (('cultist1','helper_id',Alias.CULTIST),
                ('elf_militia1','range_max','short'),('elf_militia1','bonus',True),
                ('ungor1','holds_shield',1)):
            forged=deepcopy(command.request)
            enemy=forged.scenario.enemy(actor)
            if field=='helper_id':target=forged.scenario.npc_help_policies[0]
            elif field=='holds_shield':target=enemy.state
            elif field=='bonus':target=enemy.definition.resilience
            else:target=enemy.definition.attacks[0]
            object.__setattr__(target,field,value)
            self.assertEqual(forged,command.request)
            rng=Mock(side_effect=AssertionError('malformed source cannot consume RNG'))
            runner=Mock(side_effect=AssertionError('malformed source cannot become an observation'))
            with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',runner):
                with self.subTest(actor=actor,field=field),self.assertRaises(TypeError):
                    run_pc_melee_trial(forged,0,rng_factory=rng)
            rng.assert_not_called()
            runner.assert_not_called()

    def test_explicit_empty_help_policy_keeps_cultist_on_existing_attack_strategy(self):
        raw=chunk_document()
        raw['scenario']['npc_help_policies']=[]
        raw['scenario']['max_rounds']=1
        raw['simulation']['trials']=1
        request=wire.parse_pc_melee_simulation_request(json.dumps(raw)).request
        summary=summarize_pc_melee_simulation(run_pc_melee_simulation(request))
        self.assertEqual((summary.npc_help_action_trial_count,summary.total_npc_help_action_count),(0,0))
        self.assertEqual(tuple((item.actor_id,item.count) for item in summary.npc_help_action_counts),
            (('cultist1',0),('elf_militia1',0),('ungor1',0)))


if __name__=='__main__':
    unittest.main()
