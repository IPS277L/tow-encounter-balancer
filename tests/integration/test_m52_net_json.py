"""Conditional full Net source and policies in current PC JSON1."""
from copy import deepcopy
import json
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError,PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import validate_pc_melee_balance_document,validate_pc_melee_simulation_document
from towr.application.pc_melee_balance_models import project_pc_melee_candidate
from towr.application.pc_melee_service import execute_pc_melee_balance,execute_pc_melee_simulation
from towr.domain.pc_npc_net_policy_models import PcNpcNetMode


def net_document(*,balance=False):
    raw = document(balance=balance)
    source = book_pc_scenario(net_goblins=2 if balance else 1,footpads=1,townsfolk=0,max_rounds=2)
    raw['template' if balance else 'scenario'] = scenario_document(source)
    if balance:
        raw['generation'] = {'groups':[
            dict(group_id='nets',actor_ids=['net_goblin1','net_goblin2'],minimum_count=0,maximum_count=2),
            dict(group_id='footpads',actor_ids=['footpad1'],minimum_count=1,maximum_count=1)],
            'facts':deepcopy(raw['template']['facts']),'max_candidates':3}
        raw['evaluation'].update(trials_per_candidate=1,max_total_trials=3,top_k=2)
    return raw


class NetJsonTests(unittest.TestCase):
    def test_result_root_and_candidate_echoes_keep_complete_source_and_actor_stock(self):
        for balance in (False,True):
            raw = net_document(balance=balance)
            if balance:
                command = wire.parse_pc_melee_balance_request(json.dumps(raw))
                report = execute_pc_melee_balance(command)
                encoded = json.loads(wire.encode_pc_melee_balance_result(command,report))
                validate_pc_melee_balance_document(encoded,'result')
                originals = {enemy['actor_id']:enemy for enemy in raw['template']['enemies']}
                for row,candidate in zip(encoded['candidates'],report.candidates,strict=True):
                    self.assertEqual(row['request']['scenario'],scenario_document(candidate.source_request.scenario))
                    for enemy in row['request']['scenario']['enemies']:
                        self.assertEqual(enemy,originals[enemy['actor_id']])
            else:
                command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
                encoded = json.loads(wire.encode_pc_melee_simulation_result(command,execute_pc_melee_simulation(command)))
                validate_pc_melee_simulation_document(encoded,'result')
            self.assertEqual(encoded['request'],raw)

    def test_both_families_roundtrip_complete_source_and_conditional_stock(self):
        for balance in (False,True):
            raw = net_document(balance=balance)
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command = parse(json.dumps(raw))
            source = command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source),raw[key])
            self.assertEqual(raw['schema_version'],'1')
            net,old = raw[key]['enemies'][0],raw[key]['enemies'][-1]
            self.assertEqual(net['net_policy'],{'initial_count':1,'mode':'throw_once_then_spear'})
            self.assertEqual(net['definition']['resilience'],{'toughness':3,'bonus':0,'armoured':True})
            self.assertEqual(net['definition']['net_attack']['impact'],{'kind':'condition',
                'condition':'burdened','rule_id':'RULE-EQUIPMENT-005:weighted-net-burdened',
                'classification':'unclassified'})
            self.assertNotIn('damage',net['definition']['net_attack'])
            self.assertNotIn('net_policy',old)
            self.assertNotIn('net_attack',old['definition'])
            self.assertNotIn('armoured',old['definition']['resilience'])
            self.assertNotIn('npc_net_policies',raw[key])

    def test_required_fields_are_never_defaulted_and_closed_objects_reject_unknowns(self):
        for balance in (False,True):
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            error = PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            base = net_document(balance=balance)
            paths = [('net_policy',),('net_policy','initial_count'),('net_policy','mode'),
                ('definition','net_attack'),('definition','resilience','armoured')]
            attack = base[key]['enemies'][0]['definition']['net_attack']
            paths += [('definition','net_attack',field) for field in attack]
            paths += [('definition','net_attack','impact',field) for field in attack['impact']]
            for path in paths:
                raw = deepcopy(base);obj=raw[key]['enemies'][0]
                for field in path[:-1]:obj=obj[field]
                del obj[path[-1]]
                with self.subTest(balance=balance,path=path),self.assertRaises(error):parse(json.dumps(raw))
            for path in (('net_policy',),('definition','net_attack'),('definition','net_attack','impact')):
                raw = deepcopy(base);obj=raw[key]['enemies'][0]
                for field in path:obj=obj[field]
                obj['unknown']=True
                with self.subTest(balance=balance,path=path),self.assertRaises(error):parse(json.dumps(raw))

    def test_full_canonical_profile_rejects_numeric_condition_and_identity_aliases(self):
        for path,value in ((('net_policy','initial_count'),True),(('net_policy','initial_count'),2),
                (('net_policy','mode'),'automatic'),(('definition','resilience','armoured'),False),
                (('definition','net_attack','skill'),'melee'),(('definition','net_attack','damage'),{'base':0}),
                (('definition','net_attack','test_profile','dice'),3),
                (('definition','net_attack','test_profile','dice'),2.0),
                (('definition','net_attack','test_profile','threshold'),3.0),
                (('definition','net_attack','test_profile','pool_cap'),4),
                (('definition','net_attack','test_profile','pool_cap'),6.0),
                (('definition','net_attack','source_rule_id'),'authored:net'),
                (('definition','net_attack','impact','condition'),'drained'),
                (('definition','net_attack','impact','classification'),'magical'),
                (('definition','net_attack','impact','rule_id'),'authored:burdened')):
            raw = net_document();obj=raw['scenario']['enemies'][0]
            for field in path[:-1]:obj=obj[field]
            obj[path[-1]]=value
            with self.subTest(path=path,value=value),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_conditional_fields_cannot_be_attached_to_old_or_renamed_actor(self):
        base = net_document()
        for field in ('net_policy','net_attack','armoured'):
            raw = deepcopy(base);new,old=raw['scenario']['enemies']
            if field=='net_policy':old[field]=deepcopy(new[field])
            elif field=='net_attack':old['definition'][field]=deepcopy(new['definition'][field])
            else:old['definition']['resilience'][field]=True
            with self.subTest(field=field),self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))
        raw=deepcopy(base);raw['scenario']['enemies'][0]['definition']['id']='authored:net'
        with self.assertRaises(PcMeleeSimulationInputError):wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_subset_projection_preserves_mode_stock_order_and_removes_omitted_actor_policy(self):
        raw = net_document(balance=True)
        raw['template']['enemies'][1]['net_policy']['mode']='spear_only'
        command = wire.parse_pc_melee_balance_request(json.dumps(raw))
        for count in range(3):
            scenario = project_pc_melee_candidate(command.request,(count,1)).scenario
            self.assertEqual(tuple(policy.actor_id for policy in scenario.npc_net_policies),
                tuple(f'net_goblin{i+1}' for i in range(count)))
            if count==2:self.assertIs(scenario.npc_net_policies[1].mode,PcNpcNetMode.SPEAR_ONLY)
            for policy in scenario.npc_net_policies:self.assertEqual(policy.initial_count,1)
            self.assertEqual([enemy['net_policy']['mode'] for enemy in scenario_document(scenario)['enemies']
                if 'net_policy' in enemy],['throw_once_then_spear','spear_only'][:count])
