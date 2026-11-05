"""A closed on-hit Drained descriptor and its actual native causes survive PC JSON1."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
from itertools import product
import json
from random import Random
import unittest
from unittest.mock import Mock, patch

from jsonschema import ValidationError

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import parse_scenario, scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError, PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document, validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_service import execute_pc_melee_balance
from towr.domain.attack_models import AttackOutcome, ConditionOnHitSpec
from towr.domain.condition_models import Condition, EffectClassification
from towr.domain.pc_melee_result_models import PcAttackProof
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation, run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


SPIDER_DRAINED_RULE_ID='RULE-PROFILE-CREATURE-007:poisonous-fangs-drained'
DESCRIPTOR={'kind':'condition_on_hit','condition':'drained',
    'rule_id':SPIDER_DRAINED_RULE_ID,'classification':'unclassified'}


def chunk_document(*,balance=False):
    source=book_pc_scenario(spiders=2 if balance else 1,white_wolves=1,
        footpads=0,townsfolk=0,pc_count=2,max_rounds=3)
    priority=('white_wolf1','spider1','spider2') if balance else ('white_wolf1','spider1')
    source=replace(source,party=tuple(replace(member,target_priority=priority,
        defeat_decisions=tuple(member.defeat_decision(actor) for actor in priority)) for member in source.party))
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            {'group_id':'spiders','actor_ids':['spider1','spider2'],'minimum_count':1,'maximum_count':2},
            {'group_id':'white_wolves','actor_ids':['white_wolf1'],'minimum_count':0,'maximum_count':1}],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':4}
        raw['evaluation'].update(trials_per_candidate=2,max_total_trials=8,top_k=2)
    else:
        raw['simulation']['trials']=2
    return raw


class PcDrainedChunkIntegrationTests(unittest.TestCase):
    def test_current_json_preserves_full_effect_descriptor_empty_array_and_null_hands(self):
        for balance in (False,True):
            raw=chunk_document(balance=balance)
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source),raw[key])
            self.assertEqual(raw['schema_version'],'1')
            self.assertEqual(source.party[0].target_priority,
                ('white_wolf1','spider1','spider2') if balance else ('white_wolf1','spider1'))
            for enemy,raw_enemy in zip(source.enemies,raw[key]['enemies'],strict=True):
                attack=enemy.definition.attacks[0]
                self.assertIsNone(attack.hands)
                self.assertIsNone(raw_enemy['definition']['attack']['hands'])
                self.assertIs(enemy.state.wields_weapon,False)
                expected=[DESCRIPTOR] if enemy.state.actor_id.startswith('spider') else []
                self.assertEqual(raw_enemy['definition']['attack']['secondary_effects'],expected)
                if expected:
                    self.assertEqual(attack.secondary_effects,(ConditionOnHitSpec(
                        Condition.DRAINED,SPIDER_DRAINED_RULE_ID,EffectClassification.UNCLASSIFIED),))
                else:
                    self.assertEqual(attack.secondary_effects,())
                validate_pc_book_npc_definition(enemy.definition)

    def test_required_closed_descriptor_rejects_unknown_types_effects_psyche_and_duplicates(self):
        invalid=(None,False,{},'condition_on_hit',
            [dict(DESCRIPTOR,kind='condition_on_wound')],
            [dict(DESCRIPTOR,kind='repeated_condition_replacement')],
            [dict(DESCRIPTOR,condition='ablaze')],[dict(DESCRIPTOR,condition='DRAINED')],
            [dict(DESCRIPTOR,condition=None)],[dict(DESCRIPTOR,classification='psychological')],
            [dict(DESCRIPTOR,classification='physical')],[dict(DESCRIPTOR,classification=False)],
            [dict(DESCRIPTOR,rule_id='')],[dict(DESCRIPTOR,rule_id=True)],
            [dict(DESCRIPTOR,extra=True)],[DESCRIPTOR,DESCRIPTOR],
            *([{key:value for key,value in DESCRIPTOR.items() if key!=missing}] for missing in DESCRIPTOR))
        for balance in (False,True):
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            validate=validate_pc_melee_balance_document if balance else validate_pc_melee_simulation_document
            error=PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            for value in invalid:
                raw=chunk_document(balance=balance)
                raw[key]['enemies'][0]['definition']['attack']['secondary_effects']=value
                with self.subTest(balance=balance,value=value):
                    with self.assertRaises(ValidationError):
                        validate(raw)
                    with self.assertRaises(error):
                        parse(json.dumps(raw))
            for index in range(len(raw[key]['enemies'])):
                raw=chunk_document(balance=balance)
                del raw[key]['enemies'][index]['definition']['attack']['secondary_effects']
                with self.subTest(balance=balance,missing_index=index),self.assertRaises(error):
                    parse(json.dumps(raw))
            raw=chunk_document(balance=balance)
            raw[key]['enemies'][0]['definition']['attack']['secondary_effects']=[]
            with self.assertRaises(error):
                parse(json.dumps(raw))

    def test_scenario_codec_preserves_then_rejects_extra_descriptor_source_fields(self):
        raw=chunk_document()['scenario']
        raw['enemies'][0]['definition']['attack']['secondary_effects'][0]['extra']='unrepresentable source'
        with self.assertRaises(PcMeleeSimulationInputError):
            parse_scenario(raw,path_prefix='/scenario',error_type=PcMeleeSimulationInputError)

    def test_actual_trials_and_current_result_echo_keep_full_sources_and_aggregate_counts(self):
        raw=chunk_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        simulation=run_pc_melee_simulation(command.request)
        summary=summarize_pc_melee_simulation(simulation)
        self.assertEqual(summary.source_request,command.request)
        self.assertEqual(summary.trials,2)
        self.assertEqual(tuple((item.actor_id,item.count) for item in summary.npc_exit_counts),
            (('spider1',0),('white_wolf1',0)))
        for record in simulation.records:
            self.assertEqual(record.source_scenario,command.request.scenario)
        result=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        validate_pc_melee_simulation_document(result,'result')
        self.assertEqual(result['request'],raw)
        self.assertEqual(result['schema_version'],'1')
        self.assertFalse(hasattr(summary,'records'))

    def test_four_candidate_prefixes_keep_descriptor_and_empty_array_without_journals(self):
        raw=chunk_document(balance=True)
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        report=execute_pc_melee_balance(command)
        self.assertEqual((len(report.candidates),report.total_trials),(4,8))
        self.assertEqual(tuple(candidate.counts for candidate in report.candidates),tuple(product((1,2),(0,1))))
        originals={enemy.state.actor_id:enemy.definition for enemy in command.request.template.enemies}
        for candidate in report.candidates:
            spiders,wolves=candidate.counts
            expected=tuple(f'spider{index+1}' for index in range(spiders))+(('white_wolf1',) if wolves else ())
            source=candidate.source_request.scenario
            self.assertEqual(tuple(enemy.state.actor_id for enemy in source.enemies),expected)
            self.assertEqual(source.enemy_activation_order,expected)
            for member,original in zip(source.party,command.request.template.party,strict=True):
                priority=tuple(actor for actor in original.target_priority if actor in expected)
                self.assertEqual(member.target_priority,priority)
                self.assertEqual(tuple(decision.target_id for decision in member.defeat_decisions),priority)
            for enemy in source.enemies:
                self.assertEqual(enemy.definition,originals[enemy.state.actor_id])
                validate_pc_book_npc_definition(enemy.definition)
            self.assertEqual(tuple(item.actor_id for item in candidate.summary.npc_exit_counts),expected)
            self.assertFalse(hasattr(candidate.summary,'records'))
        result=json.loads(wire.encode_pc_melee_balance_result(command,report))
        validate_pc_melee_balance_document(result,'result')
        self.assertEqual(result['request'],raw)
        for candidate,typed in zip(result['candidates'],report.candidates,strict=True):
            self.assertEqual(candidate['request']['scenario'],scenario_document(typed.source_request.scenario))
        for candidate in result['candidates']:
            for enemy in candidate['request']['scenario']['enemies']:
                attack=enemy['definition']['attack']
                self.assertIsNone(attack['hands'])
                self.assertEqual(attack['secondary_effects'],[DESCRIPTOR] if enemy['actor_id'].startswith('spider') else [])

    def test_equal_cached_condition_and_classification_types_are_refused_before_rng(self):
        class ForeignCondition(str,Enum):
            DRAINED='drained'

        class ForeignClassification(str,Enum):
            UNCLASSIFIED='unclassified'

        command=wire.parse_pc_melee_simulation_request(json.dumps(chunk_document()))
        for field,value in (('condition','drained'),('condition',ForeignCondition.DRAINED),
                ('classification','unclassified'),('classification',ForeignClassification.UNCLASSIFIED)):
            forged=deepcopy(command.request)
            object.__setattr__(forged.scenario.enemies[0].definition.attacks[0].secondary_effects[0],field,value)
            self.assertEqual(forged,command.request)
            runner=Mock(side_effect=AssertionError('cached descriptor must not become an observation'))
            rng=Mock(side_effect=AssertionError('cached descriptor must not consume RNG'))
            with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',runner):
                with self.subTest(field=field,value=value),self.assertRaises(TypeError):
                    run_pc_melee_trial(forged,0,rng_factory=rng)
            runner.assert_not_called()
            rng.assert_not_called()

    def test_process_matches_sequential_with_actual_on_hit_drained_and_bound_sources(self):
        request=wire.parse_pc_melee_simulation_request(json.dumps(chunk_document())).request
        sequential=run_pc_melee_simulation(request)
        observed=0
        for record in sequential.records:
            native=run_pc_melee_scenario(request.scenario,Random(record.seed))
            hit_ids={step.proof.request.id for step in native.steps if isinstance(step.proof,PcAttackProof)
                and step.proof.request.actor_id=='spider1'
                and step.proof.execution.resolution.attack.outcome is AttackOutcome.HIT}
            for actor in native.state.party:
                for cause in actor.hit_condition_sources:
                    observed+=1
                    self.assertIn(cause.attack_id,hit_ids)
                    self.assertEqual((cause.attacker_id,cause.target_id,cause.rule_id),
                        ('spider1',actor.actor_id,SPIDER_DRAINED_RULE_ID))
                    self.assertIs(cause.condition,Condition.DRAINED)
                    self.assertTrue(cause.application_id.strip())
                    self.assertTrue(actor.injury.conditions.has(Condition.DRAINED))
        self.assertGreater(observed,0,'representative process source must contain a real on-hit Drained cause')
        process=run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(process,sequential)
        self.assertEqual(summarize_pc_melee_simulation(process),summarize_pc_melee_simulation(sequential))


if __name__=='__main__':
    unittest.main()
