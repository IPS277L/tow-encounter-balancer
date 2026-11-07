"""Both new canonical Brutes use the unchanged PC JSON1/trial/count-search path."""
from copy import deepcopy
import json
import unittest
from unittest.mock import Mock, patch

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_simulation_document, validate_pc_melee_balance_document,
)
from towr.application.pc_melee_service import execute_pc_melee_balance
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation, run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def chunk_document(*, balance=False):
    source = book_pc_scenario(ogres=2 if balance else 1, pegasi=1,
        footpads=0, townsfolk=0, pc_count=2, max_rounds=2)
    raw = document(balance=balance)
    raw['template' if balance else 'scenario'] = scenario_document(source)
    if balance:
        raw['generation'] = {'groups':[
            dict(group_id='ogres', actor_ids=['ogre1', 'ogre2'], minimum_count=1, maximum_count=2),
            dict(group_id='pegasi', actor_ids=['pegasus1'], minimum_count=0, maximum_count=1)],
            'facts':deepcopy(raw['template']['facts']), 'max_candidates':4}
        raw['evaluation'].update(master_seed='42', trials_per_candidate=1, max_total_trials=4, top_k=2)
    else:
        raw['simulation'].update(master_seed='42', trials=2)
    return raw


class PcOgrePegasusJsonTests(unittest.TestCase):
    def test_both_families_roundtrip_exact_full_sources_without_new_fields(self):
        for balance in (False, True):
            raw = chunk_document(balance=balance)
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command = parse(json.dumps(raw))
            source = command.request.template if balance else command.request.scenario
            key = 'template' if balance else 'scenario'
            self.assertEqual(scenario_document(source), raw[key])
            self.assertEqual(raw['schema_version'], '1')
            old = document(balance=balance)[key]
            self.assertEqual(set(raw[key]), set(old))
            for enemy in raw[key]['enemies']:
                cap = enemy['definition']['attack']['test_profile']['pool_cap']
                self.assertEqual(cap, 6 if enemy['actor_id'].startswith('ogre') else None)
                self.assertIsNone(enemy['definition']['protection']['test_profile']['pool_cap'])

    def test_missing_wrong_or_equal_float_ogre_cap_and_wrong_gear_are_rejected(self):
        for cap in ('missing', None, 4, 8, 6.0, True, '6'):
            raw = chunk_document()
            profile = raw['scenario']['enemies'][0]['definition']['attack']['test_profile']
            if cap == 'missing':
                del profile['pool_cap']
            else:
                profile['pool_cap'] = cap
            with self.subTest(cap=cap), self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))
        for key, value in (('holds_shield', True), ('wields_weapon', False)):
            raw = chunk_document()
            raw['scenario']['enemies'][0][key] = value
            with self.subTest(key=key), self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_six_cannot_move_to_protection_or_other_canonical_attack(self):
        for index, role in ((0, 'protection'), (1, 'attack'), (1, 'protection')):
            raw = chunk_document()
            raw['scenario']['enemies'][index]['definition'][role]['test_profile']['pool_cap'] = 6
            with self.subTest(index=index, role=role), self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))
        for counts in ({'minotaur_greataxes':1}, {'bestigors':1}):
            source = book_pc_scenario(footpads=0, townsfolk=0, pc_count=1, **counts)
            raw = document()
            raw['scenario'] = scenario_document(source)
            parsed = wire.parse_pc_melee_simulation_request(json.dumps(raw))
            self.assertEqual(parsed.request.scenario.enemies[0].definition.attacks[0].test_profile.pool_cap, 8)

    def test_pegasus_without_grounded_source_or_with_fake_armament_is_rejected(self):
        for location, key, value in (('enemy', 'wields_weapon', True),
                ('enemy', 'holds_shield', True), ('attack', 'hands', '1h'),
                ('definition', 'id', 'pc-book-npc:pegasus'),
                ('definition', 'source_rule_id', 'BOOK-GM-GUIDE:1.1:p176:pegasus')):
            raw = chunk_document()
            enemy = raw['scenario']['enemies'][1]
            target = enemy if location == 'enemy' else enemy['definition']['attack'] if location == 'attack' else enemy['definition']
            target[key] = value
            with self.subTest(location=location, key=key), self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_actual_trials_summary_and_echo_preserve_caps_natural_facts_and_existing_metrics(self):
        raw = chunk_document()
        command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
        result = run_pc_melee_simulation(command.request)
        summary = summarize_pc_melee_simulation(result)
        self.assertEqual(len(result.records), 2)
        self.assertTrue(all(record.source_scenario == command.request.scenario for record in result.records))
        self.assertEqual(summary.total_action_count, sum(record.executed_actions for record in result.records))
        self.assertEqual(summary.total_npc_warped_form_count, 0)
        self.assertEqual(summary.total_npc_recover_action_count, 0)
        self.assertTrue(all(not hasattr(record, 'steps') for record in result.records))
        encoded = json.loads(wire.encode_pc_melee_simulation_result(command, summary))
        validate_pc_melee_simulation_document(encoded, 'result')
        self.assertEqual(encoded['request'], raw)

    def test_four_count_compositions_preserve_each_definition_and_subset_source_order(self):
        raw = chunk_document(balance=True)
        command = wire.parse_pc_melee_balance_request(json.dumps(raw))
        report = execute_pc_melee_balance(command)
        self.assertEqual((len(report.candidates), report.total_trials), (4, 4))
        encoded = json.loads(wire.encode_pc_melee_balance_result(command, report))
        validate_pc_melee_balance_document(encoded, 'result')
        self.assertEqual(encoded['request'], raw)
        definitions = {enemy['actor_id']:enemy['definition'] for enemy in raw['template']['enemies']}
        self.assertEqual({len(candidate.source_request.scenario.enemies) for candidate in report.candidates}, {1, 2, 3})
        for item, candidate in zip(encoded['candidates'], report.candidates, strict=True):
            source = candidate.source_request.scenario
            self.assertEqual(item['request']['scenario'], scenario_document(source))
            self.assertEqual(source.enemy_activation_order,
                tuple(actor for actor in raw['template']['enemy_activation_order'] if actor in source.enemy_activation_order))
            for enemy in item['request']['scenario']['enemies']:
                self.assertEqual(enemy['definition'], definitions[enemy['actor_id']])

    def test_equal_cached_cap_alias_is_readmitted_before_rng_and_runner(self):
        command = wire.parse_pc_melee_simulation_request(json.dumps(chunk_document()))
        forged = deepcopy(command.request)
        object.__setattr__(forged.scenario.enemy('ogre1').definition.attacks[0].test_profile, 'pool_cap', 6.0)
        self.assertEqual(forged, command.request)
        rng = Mock(side_effect=AssertionError('invalid source must not consume RNG'))
        runner = Mock(side_effect=AssertionError('invalid source must not enter runner'))
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario', runner):
            with self.assertRaises(TypeError):
                run_pc_melee_trial(forged, 0, rng_factory=rng)
        rng.assert_not_called()
        runner.assert_not_called()


if __name__ == '__main__':
    unittest.main()
