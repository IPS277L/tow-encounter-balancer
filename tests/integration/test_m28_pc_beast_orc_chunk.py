"""Fixed beast/orc loadouts survive JSON1, native trials and prefix count search."""
from copy import deepcopy
from dataclasses import replace
from itertools import product
import json
from random import Random
import unittest
from unittest.mock import Mock, patch

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document, validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_service import execute_pc_melee_balance
from towr.domain.attack_models import DamageModifier
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_result_models import PcAttackProof
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.test_models import DiceModifier, Skill
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation, run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def chunk_document(*,balance=False):
    source=book_pc_scenario(gors=2 if balance else 1,warhounds=1,orcs=1,
        footpads=0,townsfolk=0,pc_count=2,max_rounds=3)
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            {'group_id':'gors','actor_ids':['gor1','gor2'],'minimum_count':1,'maximum_count':2},
            {'group_id':'warhounds','actor_ids':['warhound1'],'minimum_count':0,'maximum_count':1},
            {'group_id':'orcs','actor_ids':['orc1'],'minimum_count':0,'maximum_count':1}],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':8}
        raw['evaluation'].update(trials_per_candidate=2,max_total_trials=16,top_k=2)
    else:
        raw['simulation']['trials']=2
    return raw


class BeastOrcChunkIntegrationTests(unittest.TestCase):
    def test_current_json_keeps_fixed_hands_protection_and_shield_free_resilience(self):
        for balance in (False,True):
            raw=chunk_document(balance=balance)
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw))
            source=command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source),raw[key])
            by_actor={enemy.state.actor_id:enemy for enemy in source.enemies}
            for actor,hands,skill,toughness,bonus in (
                    ('gor1','1h',Skill.ATHLETICS,4,0),
                    ('warhound1',None,Skill.ATHLETICS,3,0),
                    ('orc1','2h',Skill.DEFENCE,4,1)):
                enemy=by_actor[actor]
                attack=enemy.definition.attacks[0]
                self.assertEqual(None if attack.hands is None else attack.hands.value,hands)
                self.assertIs(enemy.state.wields_weapon,hands is not None)
                self.assertIs(enemy.state.holds_shield,False)
                self.assertIs(enemy.definition.protection[0].skill,skill)
                self.assertEqual((enemy.definition.resilience.toughness,enemy.definition.resilience.bonus),
                    (toughness,bonus))
                validate_pc_book_npc_definition(enemy.definition)
            self.assertEqual(by_actor['gor1'].definition.attacks[0].damage.base,3)
            self.assertEqual(raw['schema_version'],'1')

    def test_printed_shield_resilience_and_gor_defence_rewrites_are_refused(self):
        for actor,bonus in (('gor1',1),('orc1',2)):
            raw=chunk_document()
            definition=next(enemy['definition'] for enemy in raw['scenario']['enemies'] if enemy['actor_id']==actor)
            definition['resilience']['bonus']=bonus
            with self.subTest(actor=actor),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))
        raw=chunk_document()
        raw['scenario']['enemies'][0]['definition']['protection']['skill']='defence'
        with self.assertRaises(PcMeleeSimulationInputError):
            wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_actual_trials_and_json_preserve_full_profiles_and_source_ordered_counts(self):
        raw=chunk_document()
        command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        simulation=run_pc_melee_simulation(command.request)
        summary=summarize_pc_melee_simulation(simulation)
        self.assertEqual(summary.source_request,command.request)
        self.assertEqual(summary.trials,2)
        self.assertEqual(tuple((item.actor_id,item.count) for item in summary.npc_exit_counts),
            (('gor1',0),('warhound1',0),('orc1',0)))
        for record in simulation.records:
            self.assertEqual(record.source_scenario,command.request.scenario)
        result=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        validate_pc_melee_simulation_document(result,'result')
        self.assertEqual(result['request'],raw)
        self.assertEqual(result['schema_version'],'1')
        self.assertFalse(hasattr(summary,'records'))

    def test_count_search_preserves_eight_fixed_prefixes_and_aggregate_only_candidates(self):
        raw=chunk_document(balance=True)
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        report=execute_pc_melee_balance(command)
        self.assertEqual((len(report.candidates),report.total_trials),(8,16))
        self.assertEqual(tuple(candidate.counts for candidate in report.candidates),tuple(product((1,2),(0,1),(0,1))))
        template=command.request.template
        original={enemy.state.actor_id:enemy.definition for enemy in template.enemies}
        for candidate in report.candidates:
            gors,warhounds,orcs=candidate.counts
            expected=tuple(f'gor{index+1}' for index in range(gors))+(
                ('warhound1',) if warhounds else ())+ (('orc1',) if orcs else ())
            source=candidate.source_request.scenario
            self.assertEqual(tuple(enemy.state.actor_id for enemy in source.enemies),expected)
            self.assertEqual(source.enemy_activation_order,expected)
            for member,previous in zip(source.party,template.party,strict=True):
                self.assertEqual(member.target_priority,expected)
                self.assertEqual(tuple(decision.target_id for decision in member.defeat_decisions),expected)
                self.assertEqual(replace(member,target_priority=previous.target_priority,
                    defeat_decisions=previous.defeat_decisions),previous)
            for enemy in source.enemies:
                self.assertEqual(enemy.definition,original[enemy.state.actor_id])
                self.assertIs(enemy.state.holds_shield,False)
                validate_pc_book_npc_definition(enemy.definition)
            self.assertEqual(tuple(item.actor_id for item in candidate.summary.npc_exit_counts),expected)
            self.assertFalse(hasattr(candidate.summary,'records'))
        result=json.loads(wire.encode_pc_melee_balance_result(command,report))
        validate_pc_melee_balance_document(result,'result')
        self.assertEqual(result['request'],raw)
        for candidate,typed in zip(result['candidates'],report.candidates,strict=True):
            self.assertEqual(candidate['request']['scenario'],scenario_document(typed.source_request.scenario))

    def test_cached_equal_resilience_and_weapon_aliases_are_refused_before_rng(self):
        command=wire.parse_pc_melee_simulation_request(json.dumps(chunk_document()))
        for actor,field,value in (('gor1','bonus',False),('orc1','bonus',True),('warhound1','wields_weapon',0)):
            forged=deepcopy(command.request)
            enemy=forged.scenario.enemy(actor)
            target=enemy.state if field=='wields_weapon' else enemy.definition.resilience
            object.__setattr__(target,field,value)
            self.assertEqual(forged,command.request)
            runner=Mock(side_effect=AssertionError('cached wrong source must not become an observation'))
            rng=Mock(side_effect=AssertionError('cached wrong source must not consume RNG'))
            with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',runner):
                with self.subTest(actor=actor),self.assertRaises(TypeError):
                    run_pc_melee_trial(forged,0,rng_factory=rng)
            runner.assert_not_called()
            rng.assert_not_called()

    def test_process_matches_sequential_including_actual_gor_dual_damage_and_primal_rage(self):
        request=replace(wire.parse_pc_melee_simulation_request(json.dumps(chunk_document())).request,
            master_seed=44)
        sequential=run_pc_melee_simulation(request)
        dual_attacks=rage_attacks=0
        for record in sequential.records:
            native=run_pc_melee_scenario(request.scenario,Random(record.seed))
            for step in native.steps:
                if not isinstance(step.proof,PcAttackProof) or step.proof.request.actor_id!='gor1':
                    continue
                attack=step.proof.protection.source_request.attack
                self.assertEqual(attack.impact_spec.damage.base,3)
                modifiers=attack.impact_spec.damage_modifiers
                self.assertEqual(modifiers,(DamageModifier('RULE-PROFILE-BEASTMEN-002:dual-axes-damage',1),))
                dual_attacks+=1
                staggered=step.source.enemy('gor1').state.injury.conditions.has(Condition.STAGGERED)
                primal=tuple(item for item in attack.attacker_test.dice_modifiers
                    if item.rule_id=='RULE-PROFILE-BEASTMEN-002:primal-rage')
                self.assertEqual(primal,(DiceModifier('RULE-PROFILE-BEASTMEN-002:primal-rage',1),) if staggered else ())
                if staggered:
                    rage_attacks+=1
        self.assertGreater(dual_attacks,0)
        self.assertGreater(rage_attacks,0,'representative process source must exercise a living Staggered Gor attack')
        process=run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(process,sequential)
        self.assertEqual(summarize_pc_melee_simulation(process),summarize_pc_melee_simulation(sequential))


if __name__=='__main__':
    unittest.main()
