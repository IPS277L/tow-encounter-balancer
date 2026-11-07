"""Warped Form source facts and end-phase metrics across current PC JSON1."""
from copy import deepcopy
from dataclasses import fields,replace
from enum import Enum
import json
import unittest
from unittest.mock import Mock,patch

from jsonschema import ValidationError
from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_fixtures import (zero_npc_exit_counts,zero_npc_help_counts,
    zero_npc_extra_attack_counts,zero_npc_recover_counts,zero_npc_warped_form_counts)
from tests.unit.test_m9_pc_melee_json import document,aggregate
from tests.unit.test_m9_pc_melee_balance import request as balance_request
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError,PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import validate_pc_melee_balance_document,validate_pc_melee_simulation_document
from towr.application.pc_melee_balance_models import PcMeleeCompositionGroup,project_pc_melee_candidate
from towr.domain.minion_defeat_models import MinionDefeatDecision,NpcDefeatDisposition
from towr.domain.pc_flagellant_policy_models import PcFlagellantPolicy,PcFeelNoPainPolicy
from towr.domain.pc_melee_models import PcMeleeScenario
from towr.domain.pc_melee_result_models import PcMeleeOutcome
from towr.domain.pc_warped_form_policy_models import PcWarpedFormPolicy
from towr.simulation.pc_melee_models import (PcMeleeSimulationRequest,PcMeleeSimulationResult,
    PcMeleeTrialRecord,PcNpcWarpedFormCount,PcNpcRecoverActionCount,PcNearMissBurnCount,
    PcGloriousSpendCount,PcHelpActionCount,PcAllyRecoverActionCount)
from towr.simulation.pc_melee_simulation import run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def scene(*,wolves=1,flagellants=1,pc_count=2):
    source=book_pc_scenario(skin_wolves=wolves,flagellant_flails=flagellants,
        footpads=0,townsfolk=0,pc_count=pc_count,max_rounds=2)
    policies=[]
    for index in range(wolves):
        actor=f'skin_wolf{index+1}'
        close=tuple(m.actor_id for m in source.party)+tuple(
            e.state.actor_id for e in source.enemies if e.state.actor_id!=actor)
        policies.append(PcWarpedFormPolicy(actor,close,tuple(
            MinionDefeatDecision(actor,target,NpcDefeatDisposition.KILLED,True)
            for target in close if target not in source.pc_activation_order)))
    return replace(source,npc_warped_form_policies=tuple(policies),
        npc_flagellant_policies=tuple(PcFlagellantPolicy(f'flagellant_flails{i+1}',
            PcFeelNoPainPolicy.WOUND_AT_ZERO,True) for i in range(flagellants)))


def warped_document(*,balance=False):
    source=scene(wolves=2 if balance else 1,flagellants=2 if balance else 1)
    raw=document(balance=balance)
    raw['template' if balance else 'scenario']=scenario_document(source)
    if balance:
        raw['generation']={'groups':[
            dict(group_id='wolves',actor_ids=['skin_wolf1','skin_wolf2'],minimum_count=0,maximum_count=2),
            dict(group_id='flagellants',actor_ids=['flagellant_flails1','flagellant_flails2'],minimum_count=0,maximum_count=2)],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':8}
        raw['evaluation'].update(trials_per_candidate=1,max_total_trials=8,top_k=2)
    return raw


def compact_record(source,*,activations=1,actions=6,recover=1):
    return PcMeleeTrialRecord(source,0,42,PcMeleeOutcome.UNSUPPORTED_PATH,actions,1,0,(),
        tuple(PcNearMissBurnCount(m.actor_id,0) for m in source.party),
        tuple(PcGloriousSpendCount(m.actor_id,0) for m in source.party),
        tuple(PcHelpActionCount(m.actor_id,0) for m in source.party),
        tuple(PcAllyRecoverActionCount(m.actor_id,0) for m in source.party),
        zero_npc_exit_counts(source),zero_npc_help_counts(source),zero_npc_extra_attack_counts(source),
        tuple(PcNpcRecoverActionCount(e.state.actor_id,recover if e.state.actor_id.startswith('flagellant') else 0)
            for e in source.enemies),
        tuple(PcNpcWarpedFormCount(e.state.actor_id,activations if e.state.actor_id=='skin_wolf1' else 0)
            for e in source.enemies))


class PcWarpedFormJsonTests(unittest.TestCase):
    def test_full_required_policy_and_source_order_roundtrip_both_families(self):
        for balance in (False,True):
            raw=warped_document(balance=balance)
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command=parse(json.dumps(raw));source=command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source),raw['template' if balance else 'scenario'])
            self.assertEqual(raw['schema_version'],'1')
            for policy in source.npc_warped_form_policies:
                self.assertEqual(tuple(d.attacker_id for d in policy.npc_defeat_decisions),
                    (policy.actor_id,)*len(policy.npc_defeat_decisions))
                self.assertTrue(set(source.pc_activation_order)<=set(policy.close_actor_ids))
            raw['template' if balance else 'scenario']['npc_warped_form_policies']=[]
            self.assertFalse((parse(json.dumps(raw)).request.template if balance else
                parse(json.dumps(raw)).request.scenario).npc_warped_form_policies)

    def test_missing_closed_malformed_or_incomplete_close_facts_fail_before_rng(self):
        malformed=[None,{},True,'skin_wolf1',[{}],
            [dict(actor_id='skin_wolf1',close_actor_ids=['pc1','pc2'])],
            [dict(actor_id='skin_wolf1',close_actor_ids=['pc1','pc2'],npc_defeat_decisions=[],extra=1)]]
        for balance in (False,True):
            key='template' if balance else 'scenario'
            parse=wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            validate=validate_pc_melee_balance_document if balance else validate_pc_melee_simulation_document
            error=PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            for value in malformed:
                raw=warped_document(balance=balance);raw[key]['npc_warped_form_policies']=value
                with self.subTest(balance=balance,value=value):
                    with self.assertRaises(ValidationError):validate(raw)
                    with self.assertRaises(error):parse(json.dumps(raw))
            raw=warped_document(balance=balance);del raw[key]['npc_warped_form_policies']
            with self.assertRaises(error):parse(json.dumps(raw))
            for close in (['pc1'],['pc1','pc2','skin_wolf1'],['pc1','pc2','unknown']):
                raw=warped_document(balance=balance);raw[key]['npc_warped_form_policies'][0]['close_actor_ids']=close
                with self.assertRaises(error):parse(json.dumps(raw))
        source=scene()
        args={f.name:getattr(source,f.name) for f in fields(source) if f.name!='npc_warped_form_policies'}
        with self.assertRaises(TypeError):PcMeleeScenario(**args)

    def test_count_search_filters_caster_and_same_side_targets_without_changing_party(self):
        raw=warped_document(balance=True)
        command=wire.parse_pc_melee_balance_request(json.dumps(raw))
        source=command.request.template
        for counts in ((0,1),(1,0),(1,1),(2,1),(2,2)):
            projected=project_pc_melee_candidate(command.request,counts).scenario
            keep=set(projected.enemy_activation_order)
            self.assertEqual(projected.pc_activation_order,source.pc_activation_order)
            self.assertEqual(projected.npc_warped_form_policies,tuple(replace(policy,
                close_actor_ids=tuple(actor for actor in policy.close_actor_ids
                    if actor in keep or actor in source.pc_activation_order),
                npc_defeat_decisions=tuple(d for d in policy.npc_defeat_decisions if d.target_id in keep))
                for policy in source.npc_warped_form_policies if policy.actor_id in keep))
            self.assertEqual(scenario_document(projected)['npc_warped_form_policies'],[
                {'actor_id':p.actor_id,'close_actor_ids':list(p.close_actor_ids),
                 'npc_defeat_decisions':[dict(attacker_id=d.attacker_id,target_id=d.target_id,
                    disposition=d.disposition.value,gm_approved=True) for d in p.npc_defeat_decisions]}
                for p in projected.npc_warped_form_policies])

    def test_compact_activations_are_not_actions_or_recover_and_keep_zero_rows(self):
        source=scene(flagellants=4,pc_count=1)
        record=compact_record(source)
        summary=summarize_pc_melee_simulation(PcMeleeSimulationResult(PcMeleeSimulationRequest(source,0,1),(replace(record,seed=PcMeleeSimulationRequest(source,0,1).seed_for(0)),)))
        self.assertEqual((summary.total_action_count,summary.total_npc_recover_action_count,
            summary.npc_warped_form_trial_count,summary.total_npc_warped_form_count),(6,4,1,1))
        self.assertEqual(summary.npc_warped_form_counts,(PcNpcWarpedFormCount('skin_wolf1',1),)+tuple(
            PcNpcWarpedFormCount(f'flagellant_flails{i+1}',0) for i in range(4)))
        self.assertFalse(hasattr(record,'steps'))
        with self.assertRaises(ValueError):replace(record,npc_warped_form_counts=zero_npc_warped_form_counts(source))
        with self.assertRaises(ValueError):replace(summary,npc_warped_form_trial_count=0)
        with self.assertRaises(ValueError):replace(record,executed_actions=5,npc_warped_form_counts=tuple(
            PcNpcWarpedFormCount(row.actor_id,3 if row.actor_id=='skin_wolf1' else 0) for row in record.npc_warped_form_counts))

    def test_counter_roles_order_exact_types_and_ordinary_action_budget_remain_strict(self):
        source=scene();record=compact_record(source,actions=3)
        for value in (True,1.0,-1):
            with self.assertRaises((TypeError,ValueError)):PcNpcWarpedFormCount('skin_wolf1',value)
        with self.assertRaises(ValueError):replace(record,npc_warped_form_counts=tuple(reversed(record.npc_warped_form_counts)))
        with self.assertRaises(ValueError):replace(record,npc_warped_form_counts=(
            PcNpcWarpedFormCount('skin_wolf1',0),PcNpcWarpedFormCount('flagellant_flails1',1)))
        with self.assertRaises(ValueError):replace(record,executed_actions=5)
        with self.assertRaises(TypeError):replace(record,npc_warped_form_counts=list(record.npc_warped_form_counts))
        changed=deepcopy(record);object.__setattr__(changed.npc_warped_form_counts[0],'count',1.0)
        with self.assertRaises(TypeError):replace(changed)

    def test_new_summary_fields_required_in_current_result_without_raw_wave_journal(self):
        raw=warped_document();command=wire.parse_pc_melee_simulation_request(json.dumps(raw))
        summary=aggregate(command.request)
        encoded=json.loads(wire.encode_pc_melee_simulation_result(command,summary))
        self.assertEqual(encoded['request'],raw)
        for field in ('npc_warped_form_trial_count','npc_warped_form_counts','total_npc_warped_form_count'):
            self.assertIn(field,encoded['summary'])
            forged=deepcopy(encoded);del forged['summary'][field]
            with self.assertRaises(ValidationError):validate_pc_melee_simulation_document(forged,'result')
        self.assertNotIn('steps',encoded['summary'])
        self.assertTrue(all(row['count']==0 for row in encoded['summary']['npc_warped_form_counts']))

    def test_cached_equal_policy_aliases_are_rejected_before_runner_or_rng(self):
        class Alias(str,Enum):
            ACTOR='skin_wolf1'
        source=scene();forged=deepcopy(source)
        object.__setattr__(forged.npc_warped_form_policies[0],'actor_id',Alias.ACTOR)
        self.assertEqual(forged,source)
        rng=Mock(side_effect=AssertionError('source cannot consume RNG'))
        runner=Mock(side_effect=AssertionError('source cannot enter runner'))
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',runner):
            with self.assertRaises(TypeError):run_pc_melee_trial(PcMeleeSimulationRequest(forged,42,1),0,rng_factory=rng)
        rng.assert_not_called();runner.assert_not_called()
