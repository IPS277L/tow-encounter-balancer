"""Brewguard focus consequences remain native work behind the current PC JSON1."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import Mock,patch

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError,PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document,validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_service import execute_pc_melee_balance
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_melee_result_models import PcAttackProof,PcRecoverProof
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.ranged_weapon_profiles import RangedWeaponHands
from towr.domain.test_models import Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def brewguard_document(*,balance=False):
    source=book_pc_scenario(brewguards=2 if balance else 1,footpads=1,
        townsfolk=0,pc_count=2,max_rounds=2)
    source=replace(source,party=tuple(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.AXE))
        for member in source.party))
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            dict(group_id='brewguards',actor_ids=['brewguard1','brewguard2'],minimum_count=0,maximum_count=2),
            dict(group_id='footpads',actor_ids=['footpad1'],minimum_count=1,maximum_count=1)],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':3}
        raw['evaluation'].update(master_seed='42',trials_per_candidate=1,max_total_trials=3,top_k=2)
    else:
        raw['simulation'].update(master_seed='42',trials=2)
    return raw


class PcBrewguardJsonTests(unittest.TestCase):
    def test_current_requests_roundtrip_exact_printed_brewguard_without_new_source_fields(self):
        for balance in (False,True):
            raw=brewguard_document(balance=balance)
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source),raw[key])
            self.assertEqual(set(raw[key]),set(document(balance=balance)[key]))
            self.assertEqual(raw['schema_version'],'1')
            self.assertEqual(source.npc_extra_attack_actor_ids,())
            self.assertEqual(source.npc_help_policies,())
            for enemy in source.enemies:
                validate_pc_book_npc_definition(enemy.definition)
                if not enemy.state.actor_id.startswith('brewguard'):
                    continue
                definition=enemy.definition
                attack,=definition.attacks
                protection,=definition.protection
                self.assertEqual(definition.id,'pc-book-npc:dwarf_brewguard_warhammer')
                self.assertEqual(definition.source_rule_id,
                    'BOOK-GM-GUIDE:1.1:p104:dwarf_brewguard_warhammer')
                self.assertEqual((attack.test_profile.dice,attack.test_profile.threshold,attack.damage.base),(4,3,3))
                self.assertIs(attack.hands,RangedWeaponHands.ONE_HANDED)
                self.assertEqual((protection.skill,protection.test_profile.dice,protection.test_profile.threshold),
                    (Skill.DEFENCE,4,3))
                self.assertEqual((definition.wound_limit,definition.resilience.toughness,
                    definition.resilience.bonus,definition.resilience.total),(2,4,1,5))
                self.assertIs(enemy.state.holds_shield,False)
                self.assertIs(enemy.state.wields_weapon,True)
                self.assertFalse(enemy.state.injury.conditions.has(Condition.DISTRACTED))

    def test_changed_gear_printed_profiles_and_partial_source_renames_are_rejected(self):
        paths=(('holds_shield',True),('wields_weapon',False),
            ('definition.attack.hands','2h'),('definition.attack.range_max','short'),
            ('definition.attack.damage.base',4),('definition.attack.test_profile.dice',3),
            ('definition.protection.skill','athletics'),('definition.resilience.bonus',2),
            ('definition.wound_limit',3),('definition.id','authored:renamed'),
            ('definition.source_rule_id','authored:source'))
        for balance in (False,True):
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            error=PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            for path,value in paths:
                raw=brewguard_document(balance=balance)
                target=raw[key]['enemies'][0]
                parts=path.split('.')
                for part in parts[:-1]:
                    target=target[part]
                target[parts[-1]]=value
                with self.subTest(balance=balance,path=path),self.assertRaises(error):
                    parse(json.dumps(raw))

    def test_schema_equal_numeric_values_do_not_weaken_exact_printed_source_admission(self):
        for balance in (False,True):
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            validate=validate_pc_melee_balance_document if balance else validate_pc_melee_simulation_document
            error=PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            for branch,field,value in (('attack','dice',4.0),('attack','threshold',3.0),
                                       ('protection','dice',4.0)):
                raw=brewguard_document(balance=balance)
                raw[key]['enemies'][0]['definition'][branch]['test_profile'][field]=value
                validate(raw)
                with self.subTest(balance=balance,branch=branch,field=field),self.assertRaises(error):
                    parse(json.dumps(raw))

    def test_native_consequences_reach_trials_and_summary_without_effect_action_costs(self):
        raw=brewguard_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        native=[]

        def observe(source,rng):
            result=run_pc_melee_scenario(source,rng)
            native.append(result)
            return result

        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',side_effect=observe):
            result=run_pc_melee_simulation(command.request)
        summary=summarize_pc_melee_simulation(result)
        self.assertEqual((len(native),len(result.records),summary.trials),(2,2,2))
        self.assertTrue(any(step.state.enemy('brewguard1').state.injury.conditions.has(Condition.DISTRACTED)
            for battle in native for step in battle.steps),'the fixed seed must exercise the first-Wound effect')
        for battle,record in zip(native,result.records,strict=True):
            self.assertEqual(battle.source,command.request.scenario)
            self.assertEqual(record.source_scenario,battle.source)
            self.assertEqual(record.outcome,battle.outcome)
            self.assertEqual(record.executed_actions,battle.executed_actions)
            self.assertEqual(record.executed_actions,
                sum(type(step.proof) in (PcAttackProof,PcRecoverProof) for step in battle.steps))
            self.assertLessEqual(record.executed_actions,4*record.started_rounds)
            self.assertEqual(tuple((item.actor_id,item.count) for item in record.npc_extra_attack_counts),
                (('brewguard1',0),('footpad1',0)))
            self.assertFalse(hasattr(record,'steps'))
        self.assertEqual(summary.total_action_count,sum(record.executed_actions for record in result.records))
        self.assertEqual((summary.total_npc_extra_attack_count,summary.total_npc_help_action_count),(0,0))
        encoded=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        validate_pc_melee_simulation_document(encoded,'result')
        self.assertEqual(encoded['request'],raw)
        self.assertEqual(encoded['summary']['total_action_count'],summary.total_action_count)
        self.assertFalse(hasattr(summary,'records'))

    def test_three_count_compositions_keep_canonical_sources_and_source_ordered_zero_extras(self):
        raw=brewguard_document(balance=True)
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        report=execute_pc_melee_balance(command)
        self.assertEqual((len(report.candidates),report.total_trials),(3,3))
        self.assertEqual(tuple(candidate.counts for candidate in report.candidates),((0,1),(1,1),(2,1)))
        originals={enemy.state.actor_id:enemy for enemy in command.request.template.enemies}
        for candidate in report.candidates:
            source=candidate.source_request.scenario
            retained=tuple(enemy.state.actor_id for enemy in source.enemies)
            self.assertEqual(source.enemy_activation_order,retained)
            self.assertEqual(source.npc_extra_attack_actor_ids,())
            for enemy in source.enemies:
                self.assertEqual(enemy,originals[enemy.state.actor_id])
            self.assertEqual(tuple((item.actor_id,item.count) for item in candidate.summary.npc_extra_attack_counts),
                tuple((actor,0) for actor in retained))
            self.assertEqual(tuple(item.actor_id for item in candidate.summary.npc_help_action_counts),retained)
            self.assertEqual(candidate.summary.total_npc_extra_attack_count,0)
        encoded=json.loads(wire.encode_pc_melee_balance_result(command,report))
        validate_pc_melee_balance_document(encoded,'result')
        self.assertEqual(encoded['request'],raw)
        for item,candidate in zip(encoded['candidates'],report.candidates,strict=True):
            self.assertEqual(item['request']['scenario'],scenario_document(candidate.source_request.scenario))

    def test_cached_equal_printed_and_gear_aliases_fail_before_trial_rng_and_execution(self):
        command=wire.parse_pc_melee_simulation_request(json.dumps(brewguard_document()))
        for branch,field,value in (('attack','threshold',3.0),('resilience','bonus',True),
                                   ('state','wields_weapon',1)):
            forged=deepcopy(command.request)
            enemy=forged.scenario.enemy('brewguard1')
            target=(enemy.definition.attacks[0].test_profile if branch=='attack' else
                enemy.definition.resilience if branch=='resilience' else enemy.state)
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
