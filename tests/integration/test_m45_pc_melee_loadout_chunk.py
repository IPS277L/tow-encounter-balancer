"""Four compatible melee loadouts share one current JSON/trial/search path."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import json
import unittest
from unittest.mock import Mock,patch

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import validate_pc_melee_simulation_document,validate_pc_melee_balance_document
from towr.application.pc_melee_service import execute_pc_melee_balance
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def chunk_document(*,balance=False):
    source=book_pc_scenario(sharpshooters=2 if balance else 1,single_gors=1,
        unshielded_orcs=1,unshielded_big_uns=1,footpads=0,townsfolk=0,pc_count=2,max_rounds=2)
    priority=('unshielded_big_un1','single_gor1','unshielded_orc1','sharpshooter1')
    if balance:priority=(*priority,'sharpshooter2')
    source=replace(source,npc_help_policies=(PcNpcHelpPolicy('unshielded_orc1','unshielded_big_un1'),),
        party=tuple(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.AXE),
            target_priority=priority,defeat_decisions=tuple(member.defeat_decision(actor) for actor in priority))
            for member in source.party))
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            dict(group_id='sharpshooters',actor_ids=['sharpshooter1','sharpshooter2'],minimum_count=1,maximum_count=2),
            dict(group_id='single_gors',actor_ids=['single_gor1'],minimum_count=0,maximum_count=1),
            dict(group_id='unshielded_orcs',actor_ids=['unshielded_orc1'],minimum_count=0,maximum_count=1),
            dict(group_id='unshielded_big_uns',actor_ids=['unshielded_big_un1'],minimum_count=0,maximum_count=1)],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':16}
        raw['evaluation'].update(master_seed='42',trials_per_candidate=1,max_total_trials=16,top_k=2)
    else:
        raw['simulation'].update(master_seed='42',trials=2)
    return raw


class PcMeleeLoadoutChunkTests(unittest.TestCase):
    def test_full_source_roundtrips_four_loadouts_and_no_new_wire_fields(self):
        for balance in (False,True):
            raw=chunk_document(balance=balance)
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source),raw['template' if balance else 'scenario'])
            self.assertEqual(raw['schema_version'],'1')
            self.assertTrue(all(not enemy.state.holds_shield for enemy in source.enemies))
            self.assertEqual(tuple(e.definition.resilience.total for e in source.enemies),
                (5,5,4,5,5) if balance else (5,5,4,5))
            self.assertEqual(source.npc_grudge_policies,())
            self.assertEqual(source.npc_extra_attack_actor_ids,())

    def test_changed_canonical_gear_damage_sources_and_numeric_profiles_are_rejected(self):
        for index,path,value in ((0,'holds_shield',True),(1,'holds_shield',True),(2,'holds_shield',True),
                (0,'definition.attack.damage.base',4),(2,'definition.attack.damage.base',4),
                (3,'definition.attack.test_profile.dice',4),(3,'definition.protection.test_profile.threshold',3),
                (3,'definition.source_rule_id','authored:source')):
            raw=chunk_document();target=raw['scenario']['enemies'][index]
            parts=path.split('.')
            for part in parts[:-1]:target=target[part]
            target[parts[-1]]=value
            with self.subTest(index=index,path=path),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_trials_summary_and_result_keep_full_sources_and_existing_costs(self):
        raw=chunk_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        result=run_pc_melee_simulation(command.request)
        summary=summarize_pc_melee_simulation(result)
        self.assertEqual(len(result.records),2)
        self.assertTrue(all(r.source_scenario==command.request.scenario for r in result.records))
        self.assertEqual(summary.total_action_count,sum(r.executed_actions for r in result.records))
        self.assertEqual(summary.total_npc_help_action_count,
            sum(item.count for r in result.records for item in r.npc_help_action_counts))
        self.assertTrue(all(not hasattr(r,'steps') for r in result.records))
        encoded=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        validate_pc_melee_simulation_document(encoded,'result')
        self.assertEqual(encoded['request'],raw)

    def test_sixteen_count_compositions_filter_help_without_reassignment_or_source_changes(self):
        raw=chunk_document(balance=True)
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        report=execute_pc_melee_balance(command)
        self.assertEqual((len(report.candidates),report.total_trials),(16,16))
        encoded=json.loads(wire.encode_pc_melee_balance_result(command,report))
        validate_pc_melee_balance_document(encoded,'result')
        self.assertEqual(encoded['request'],raw)
        original={e['actor_id']:e['definition'] for e in raw['template']['enemies']}
        for item,candidate in zip(encoded['candidates'],report.candidates,strict=True):
            source=candidate.source_request.scenario
            retained=source.enemy_activation_order
            self.assertEqual(source.npc_help_policies,command.request.template.npc_help_policies
                if 'unshielded_orc1' in retained and 'unshielded_big_un1' in retained else ())
            self.assertEqual(item['request']['scenario'],scenario_document(source))
            for enemy in item['request']['scenario']['enemies']:
                self.assertEqual(enemy['definition'],original[enemy['actor_id']])

    def test_big_un_spear_can_also_be_selected_as_helper_without_new_policy(self):
        raw=chunk_document()
        source=raw['scenario']
        source['npc_help_policies']=[{'helper_id':'unshielded_big_un1','beneficiary_id':'sharpshooter1'}]
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        self.assertEqual(command.request.scenario.npc_help_policies,
            (PcNpcHelpPolicy('unshielded_big_un1','sharpshooter1'),))

    def test_equal_cached_aliases_cannot_reach_rng_or_runner(self):
        class Alias(str,Enum):
            SOURCE='BOOK-GM-GUIDE:1.1:p114:hochland_sharpshooter_axe'
        command=wire.parse_pc_melee_simulation_request(json.dumps(chunk_document()))
        forged=deepcopy(command.request)
        object.__setattr__(forged.scenario.enemy('sharpshooter1').definition,'source_rule_id',Alias.SOURCE)
        self.assertEqual(forged,command.request)
        rng=Mock(side_effect=AssertionError('malformed source cannot consume RNG'))
        runner=Mock(side_effect=AssertionError('malformed source cannot enter runner'))
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',runner):
            with self.assertRaises(TypeError):run_pc_melee_trial(forged,0,rng_factory=rng)
        rng.assert_not_called();runner.assert_not_called()
