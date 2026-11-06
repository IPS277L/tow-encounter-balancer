"""Shielded spear loadouts preserve printed sources and free-success Help in PC JSON1."""
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
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy
from towr.domain.ranged_weapon_profiles import RangedWeaponHands,RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import Skill
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def chunk_document(*,balance=False):
    source=book_pc_scenario(spear_troopers=2 if balance else 1,spear_orcs=1,spear_big_uns=1,
        footpads=0,townsfolk=0,pc_count=1,max_rounds=2)
    troopers=('spear_trooper1','spear_trooper2') if balance else ('spear_trooper1',)
    priority=('spear_big_un1',*troopers,'spear_orc1')
    source=replace(source,npc_help_policies=(PcNpcHelpPolicy('spear_orc1','spear_big_un1'),),
        party=tuple(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.AXE),
            target_priority=priority,
            defeat_decisions=tuple(member.defeat_decision(actor) for actor in priority))
            for member in source.party))
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            {'group_id':'spear_troopers','actor_ids':['spear_trooper1','spear_trooper2'],
             'minimum_count':1,'maximum_count':2},
            {'group_id':'spear_orcs','actor_ids':['spear_orc1'],'minimum_count':0,'maximum_count':1},
            {'group_id':'spear_big_uns','actor_ids':['spear_big_un1'],'minimum_count':0,'maximum_count':1}],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':8}
        raw['evaluation'].update(trials_per_candidate=1,max_total_trials=8,top_k=2)
    else:
        raw['simulation']['trials']=2
    return raw


class PcSpearChunkIntegrationTests(unittest.TestCase):
    def test_current_source_roundtrip_keeps_three_printed_one_handed_spears_and_shields(self):
        for balance in (False,True):
            raw=chunk_document(balance=balance)
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source),raw[key])
            self.assertEqual(raw['schema_version'],'1')
            self.assertIs(source.party[0].pc.weapon,PcMeleeWeapon.AXE)
            for enemy in source.enemies:
                validate_pc_book_npc_definition(enemy.definition)
                actor=enemy.state.actor_id
                attack,=enemy.definition.attacks
                protection,=enemy.definition.protection
                self.assertIs(attack.hands,RangedWeaponHands.ONE_HANDED)
                self.assertIs(attack.range_min,RangedWeaponRange.CLOSE)
                self.assertIs(attack.range_max,RangedWeaponRange.SHORT)
                self.assertEqual((attack.test_profile.dice,protection.test_profile.dice,
                    protection.test_profile.threshold),(3,3,4))
                self.assertIs(protection.skill,Skill.DEFENCE)
                self.assertEqual(attack.secondary_effects,())
                trooper=actor.startswith('spear_trooper')
                brute=actor=='spear_big_un1'
                self.assertEqual((attack.test_profile.threshold,attack.damage.base,
                    enemy.definition.resilience.toughness,enemy.definition.resilience.total),
                    (3 if trooper else 4,4 if brute else 3,3 if trooper else 4,4 if trooper else 6))
                self.assertIs(enemy.state.holds_shield,not trooper)
                self.assertIs(enemy.definition.injury_policy,
                    TargetInjuryPolicy.BRUTE if brute else TargetInjuryPolicy.MINION)
                self.assertEqual(enemy.definition.wound_limit,2 if brute else 1)

    def test_each_new_orc_loadout_can_be_an_explicit_free_success_helper(self):
        for helper,beneficiary,order in (
                ('spear_orc1','spear_big_un1',('spear_trooper1','spear_orc1','spear_big_un1')),
                ('spear_big_un1','spear_trooper1',('spear_big_un1','spear_orc1','spear_trooper1'))):
            raw=chunk_document()
            raw['scenario']['enemy_activation_order']=list(order)
            raw['scenario']['npc_help_policies']=[{'helper_id':helper,'beneficiary_id':beneficiary}]
            command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
            with self.subTest(helper=helper):
                self.assertEqual(command.request.scenario.npc_help_policies,
                    (PcNpcHelpPolicy(helper,beneficiary),))
                self.assertEqual(scenario_document(command.request.scenario),raw['scenario'])

    def test_actual_trials_keep_free_success_help_costs_and_full_source_echo(self):
        raw=chunk_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        result=run_pc_melee_simulation(command.request)
        summary=summarize_pc_melee_simulation(result)
        self.assertEqual(summary.source_request,command.request)
        self.assertEqual(summary.npc_help_action_trial_count,
            sum(any(item.count for item in record.npc_help_action_counts) for record in result.records))
        self.assertGreater(summary.total_npc_help_action_count,0)
        for record in result.records:
            self.assertEqual(record.source_scenario,command.request.scenario)
            self.assertEqual(tuple(item.actor_id for item in record.npc_help_action_counts),
                ('spear_trooper1','spear_orc1','spear_big_un1'))
            self.assertEqual((record.npc_help_action_counts[0].count,record.npc_help_action_counts[2].count),(0,0))
            self.assertLessEqual(sum(item.count for item in record.npc_help_action_counts),record.executed_actions)
            self.assertFalse(hasattr(record,'steps'))
        encoded=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        validate_pc_melee_simulation_document(encoded,'result')
        self.assertEqual(encoded['request'],raw)
        self.assertEqual(encoded['summary']['npc_help_action_counts'],
            [{'actor_id':item.actor_id,'count':item.count} for item in summary.npc_help_action_counts])
        self.assertFalse(hasattr(summary,'records'))

    def test_eight_candidate_prefixes_filter_both_help_endpoints_and_preserve_source_order(self):
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
            self.assertEqual(tuple(item.actor_id for item in candidate.summary.npc_help_action_counts),retained)
            for enemy in source.enemies:
                self.assertEqual(enemy,originals[enemy.state.actor_id])
            if 'spear_orc1' not in retained or 'spear_big_un1' not in retained:
                self.assertEqual(source.npc_help_policies,())
                self.assertEqual(candidate.summary.total_npc_help_action_count,0)
            self.assertFalse(hasattr(candidate.summary,'records'))
        encoded=json.loads(wire.encode_pc_melee_balance_result(command,report))
        validate_pc_melee_balance_document(encoded,'result')
        self.assertEqual(encoded['request'],raw)
        for item,candidate in zip(encoded['candidates'],report.candidates,strict=True):
            self.assertEqual(item['request']['scenario'],scenario_document(candidate.source_request.scenario))

    def test_canonical_shield_range_resilience_and_printed_damage_cannot_be_rewritten(self):
        changes=(('spear_trooper1','holds_shield',True),('spear_trooper1','damage',5),
            ('spear_orc1','holds_shield',False),('spear_orc1','damage',4),
            ('spear_big_un1','holds_shield',False),('spear_big_un1','damage',5),
            ('spear_big_un1','bonus',3),('spear_orc1','range_max','close'))
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
                else:enemy['definition']['attack'][field]=value
                with self.subTest(balance=balance,actor=actor,field=field),self.assertRaises(error):
                    parse(json.dumps(raw))

    def test_cached_equal_aliases_are_rejected_before_rng_and_native_execution(self):
        class Alias(str,Enum):
            ORC='spear_orc1'
        command=wire.parse_pc_melee_simulation_request(json.dumps(chunk_document()))
        for actor,field,value in (('spear_orc1','helper_id',Alias.ORC),
                ('spear_orc1','holds_shield',1),('spear_big_un1','holds_shield',1),
                ('spear_trooper1','range_max','short')):
            forged=deepcopy(command.request)
            enemy=forged.scenario.enemy(actor)
            if field=='helper_id':target=forged.scenario.npc_help_policies[0]
            elif field=='holds_shield':target=enemy.state
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


if __name__=='__main__':
    unittest.main()
