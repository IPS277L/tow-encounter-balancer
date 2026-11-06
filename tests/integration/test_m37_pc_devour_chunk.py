"""Three Devour the Fallen Brute loadouts retain full sources in current PC JSON1."""
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
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.ranged_weapon_profiles import RangedWeaponHands,RangedWeaponRange
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.test_models import Skill
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def chunk_document(*,balance=False):
    source=book_pc_scenario(razorgors=2 if balance else 1,minotaurs=1,minotaur_dual_axes=1,
        footpads=0,townsfolk=0,pc_count=2,max_rounds=2)
    source=replace(source,party=tuple(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.AXE))
        for member in source.party))
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            {'group_id':'razorgors','actor_ids':['razorgor1','razorgor2'],'minimum_count':1,'maximum_count':2},
            {'group_id':'minotaurs','actor_ids':['minotaur1'],'minimum_count':0,'maximum_count':1},
            {'group_id':'minotaur_dual_axes','actor_ids':['minotaur_dual1'],'minimum_count':0,'maximum_count':1}],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':8}
        raw['evaluation'].update(trials_per_candidate=1,max_total_trials=8,top_k=2)
    else:
        raw['simulation']['trials']=2
    return raw


class PcDevourChunkIntegrationTests(unittest.TestCase):
    def test_current_json_roundtrip_preserves_natural_and_armed_three_wound_brutes(self):
        for balance in (False,True):
            raw=chunk_document(balance=balance)
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source),raw[key])
            self.assertEqual(raw['schema_version'],'1')
            self.assertEqual(source.npc_help_policies,())
            for enemy,encoded in zip(source.enemies,raw[key]['enemies'],strict=True):
                validate_pc_book_npc_definition(enemy.definition)
                attack,=enemy.definition.attacks
                protection,=enemy.definition.protection
                natural=enemy.state.actor_id.startswith('razorgor')
                self.assertIs(enemy.definition.injury_policy,TargetInjuryPolicy.BRUTE)
                self.assertEqual((enemy.definition.wound_limit,enemy.definition.resilience.toughness,
                    enemy.definition.resilience.total),(3,5,6))
                self.assertTrue(enemy.definition.resilience.is_armoured)
                self.assertIs(enemy.state.holds_shield,False)
                self.assertIs(enemy.state.wields_weapon,not natural)
                self.assertIs(attack.hands,None if natural else RangedWeaponHands.ONE_HANDED)
                self.assertEqual(encoded['definition']['attack']['hands'],None if natural else '1h')
                self.assertIs(attack.range_min,RangedWeaponRange.CLOSE)
                self.assertIs(attack.range_max,RangedWeaponRange.CLOSE)
                self.assertIs(protection.skill,Skill.ATHLETICS)
                self.assertEqual((attack.test_profile.dice,attack.test_profile.threshold,
                    protection.test_profile.dice,protection.test_profile.threshold),
                    (3,4,3,3) if natural else (4,5,4,4))
                self.assertEqual((attack.damage.base,attack.damage.success_multiplier),(5,1))
                self.assertEqual(attack.secondary_effects,())

    def test_actual_trials_preserve_costs_and_zero_help_counts_without_journals(self):
        raw=chunk_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        result=run_pc_melee_simulation(command.request)
        summary=summarize_pc_melee_simulation(result)
        self.assertEqual(summary.source_request,command.request)
        self.assertEqual(summary.trials,2)
        self.assertEqual(summary.total_action_count,sum(record.executed_actions for record in result.records))
        self.assertEqual((summary.npc_help_action_trial_count,summary.total_npc_help_action_count),(0,0))
        for record in result.records:
            self.assertEqual(record.source_scenario,command.request.scenario)
            self.assertEqual(tuple((item.actor_id,item.count) for item in record.npc_help_action_counts),
                (('razorgor1',0),('minotaur1',0),('minotaur_dual1',0)))
            self.assertFalse(hasattr(record,'state'))
            self.assertFalse(hasattr(record,'steps'))
        encoded=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        validate_pc_melee_simulation_document(encoded,'result')
        self.assertEqual(encoded['request'],raw)
        self.assertEqual(encoded['summary']['total_action_count'],summary.total_action_count)
        self.assertEqual(encoded['summary']['pc_defeat_counts'],
            [{'actor_id':item.actor_id,'count':item.count} for item in summary.pc_defeat_counts])
        self.assertFalse(hasattr(summary,'records'))

    def test_eight_candidate_prefixes_preserve_three_distinct_full_definitions(self):
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
            self.assertEqual(source.enemy_activation_order,retained)
            self.assertEqual(source.npc_help_policies,())
            self.assertEqual(tuple(item.actor_id for item in candidate.summary.npc_help_action_counts),retained)
            self.assertEqual(candidate.summary.total_npc_help_action_count,0)
            for member,original in zip(source.party,template.party,strict=True):
                self.assertEqual(member.target_priority,tuple(actor for actor in original.target_priority if actor in retained))
                self.assertEqual(tuple(item.target_id for item in member.defeat_decisions),member.target_priority)
            for enemy in source.enemies:
                self.assertEqual(enemy,originals[enemy.state.actor_id])
                validate_pc_book_npc_definition(enemy.definition)
            self.assertFalse(hasattr(candidate.summary,'records'))
        encoded=json.loads(wire.encode_pc_melee_balance_result(command,report))
        validate_pc_melee_balance_document(encoded,'result')
        self.assertEqual(encoded['request'],raw)
        for item,candidate in zip(encoded['candidates'],report.candidates,strict=True):
            self.assertEqual(item['request']['scenario'],scenario_document(candidate.source_request.scenario))

    def test_public_entries_refuse_baked_in_dual_damage_shields_and_changed_wound_limits(self):
        changes=(('razorgor1','hands','1h'),('razorgor1','holds_shield',True),
            ('minotaur1','damage',6),('minotaur_dual1','damage',6),
            ('minotaur_dual1','holds_shield',True),('minotaur_dual1','hands','2h'),
            ('razorgor1','wound_limit',2),('minotaur1','wound_limit',2),
            ('minotaur_dual1','bonus',0),('minotaur1','protection_skill','defence'))
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
                elif field=='wound_limit':enemy['definition'][field]=value
                elif field=='protection_skill':enemy['definition']['protection']['skill']=value
                else:enemy['definition']['attack'][field]=value
                with self.subTest(balance=balance,actor=actor,field=field),self.assertRaises(error):
                    parse(json.dumps(raw))

    def test_partial_source_rename_cannot_drop_intrinsic_book_abilities(self):
        for actor in ('razorgor1','minotaur1','minotaur_dual1'):
            raw=chunk_document()
            definition=next(item['definition'] for item in raw['scenario']['enemies'] if item['actor_id']==actor)
            definition.update(id='authored:renamed',source_rule_id='authored:source')
            with self.subTest(actor=actor),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_cached_equal_aliases_are_rejected_before_rng_and_native_execution(self):
        command=wire.parse_pc_melee_simulation_request(json.dumps(chunk_document()))
        for actor,field,value in (('razorgor1','wields_weapon',0),
                ('minotaur1','wields_weapon',1),('minotaur_dual1','range_max','close'),
                ('minotaur_dual1','success_multiplier',True),('razorgor1','wounds',False)):
            forged=deepcopy(command.request)
            enemy=forged.scenario.enemy(actor)
            if field=='wields_weapon':target=enemy.state
            elif field=='wounds':target=enemy.state.injury
            elif field=='success_multiplier':target=enemy.definition.attacks[0].damage
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
