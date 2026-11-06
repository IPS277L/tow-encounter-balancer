"""Two shield loadouts keep complete canonical sources through current PC JSON1."""
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
from towr.adapters.pc_melee_json_schema import validate_pc_melee_simulation_document,validate_pc_melee_balance_document
from towr.application.pc_melee_service import execute_pc_melee_balance
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.test_models import Skill
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def chunk_document(*,balance=False):
    source=book_pc_scenario(shield_gors=2 if balance else 1,shield_knights=1,
        footpads=0,townsfolk=0,pc_count=2,max_rounds=2)
    source=replace(source,party=tuple(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.AXE))
        for member in source.party))
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            dict(group_id='shield_gors',actor_ids=['shield_gor1','shield_gor2'],minimum_count=1,maximum_count=2),
            dict(group_id='shield_knights',actor_ids=['shield_knight1'],minimum_count=0,maximum_count=1)],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':4}
        raw['evaluation'].update(trials_per_candidate=1,max_total_trials=4,top_k=2)
    else:
        raw['simulation']['trials']=2
    return raw


class PcShieldChunkIntegrationTests(unittest.TestCase):
    def test_current_json_keeps_both_printed_shields_and_distinct_protection_skills(self):
        for balance in (False,True):
            raw=chunk_document(balance=balance)
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source),raw['template' if balance else 'scenario'])
            self.assertEqual(raw['schema_version'],'1')
            for enemy in source.enemies:
                validate_pc_book_npc_definition(enemy.definition)
                knight=enemy.state.actor_id=='shield_knight1'
                attack,=enemy.definition.attacks
                protection,=enemy.definition.protection
                self.assertTrue(enemy.state.holds_shield)
                self.assertTrue(enemy.state.wields_weapon)
                self.assertEqual((attack.test_profile.dice,attack.test_profile.threshold,attack.damage.base),
                    (4,4,4) if knight else (4,3,3))
                self.assertEqual((enemy.definition.resilience.toughness,enemy.definition.resilience.total),
                    (3,6) if knight else (4,5))
                self.assertEqual((protection.skill,protection.test_profile.dice,protection.test_profile.threshold),
                    (Skill.DEFENCE,4,4) if knight else (Skill.ATHLETICS,4,3))
                self.assertEqual(source.npc_extra_attack_actor_ids,())

    def test_missing_shield_dual_damage_or_mounted_resilience_cannot_change_canonical_source(self):
        for index,field,value in ((0,'shield',False),(1,'shield',False),
                                  (0,'damage',4),(1,'armour',4),(1,'skill','athletics')):
            raw=chunk_document()
            enemy=raw['scenario']['enemies'][index]
            if field=='shield':enemy['holds_shield']=value
            elif field=='damage':enemy['definition']['attack']['damage']['base']=value
            elif field=='armour':enemy['definition']['resilience']['bonus']=value
            else:enemy['definition']['protection']['skill']=value
            with self.subTest(index=index,field=field),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_real_trials_and_result_echo_keep_actual_source_and_existing_metrics(self):
        raw=chunk_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        summary=summarize_pc_melee_simulation(run_pc_melee_simulation(command.request))
        self.assertEqual(summary.trials,2)
        self.assertGreater(summary.total_action_count,0)
        self.assertEqual(summary.total_npc_extra_attack_count,0)
        self.assertEqual(tuple((item.actor_id,item.count) for item in summary.npc_extra_attack_counts),
            (('shield_gor1',0),('shield_knight1',0)))
        output=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        validate_pc_melee_simulation_document(output,'result')
        self.assertEqual(output['request'],raw)

    def test_four_count_compositions_keep_canonical_sources_and_source_ordered_costs(self):
        raw=chunk_document(balance=True)
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        report=execute_pc_melee_balance(command)
        self.assertEqual((len(report.candidates),report.total_trials),(4,4))
        self.assertEqual(tuple(candidate.counts for candidate in report.candidates),tuple(product((1,2),(0,1))))
        for candidate in report.candidates:
            order=tuple(enemy.state.actor_id for enemy in candidate.source_request.scenario.enemies)
            self.assertEqual(tuple(item.actor_id for item in candidate.summary.npc_help_action_counts),order)
            self.assertEqual(tuple(item.actor_id for item in candidate.summary.npc_extra_attack_counts),order)
            self.assertEqual(candidate.summary.total_npc_extra_attack_count,0)
        output=json.loads(wire.encode_pc_melee_balance_result(command,report))
        validate_pc_melee_balance_document(output,'result')
        self.assertEqual(output['request'],raw)

    def test_cached_equal_shield_alias_cannot_reach_trial_rng_or_execution(self):
        command=wire.parse_pc_melee_simulation_request(json.dumps(chunk_document()))
        forged=deepcopy(command.request)
        object.__setattr__(forged.scenario.enemies[0].state,'holds_shield',1)
        self.assertEqual(forged,command.request)
        rng=Mock(side_effect=AssertionError('invalid shield source must not construct RNG'))
        runner=Mock(side_effect=AssertionError('invalid shield source must not execute'))
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',runner):
            with self.assertRaises(TypeError):
                run_pc_melee_trial(forged,0,rng_factory=rng)
        rng.assert_not_called()
        runner.assert_not_called()


if __name__=='__main__':
    unittest.main()
