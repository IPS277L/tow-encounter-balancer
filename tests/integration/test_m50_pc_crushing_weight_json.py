"""Closed early-Prone descriptor, current metrics and subset search for both Bears."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import Mock, patch

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError, PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document, validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_service import execute_pc_melee_balance
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation, run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


RULE = 'RULE-PROFILE-CREATURE-010:crushing-weight-prone'
EFFECT = {'kind':'prone_before_give_ground', 'rule_id':RULE, 'affects_monstrosities':True}


def crushing_document(*, balance=False):
    source = book_pc_scenario(crushing_bears=2 if balance else 1, bears=1,
        footpads=0, townsfolk=0, max_rounds=2)
    source = replace(source, npc_extra_attack_actor_ids=source.enemy_activation_order)
    raw = document(balance=balance)
    raw['template' if balance else 'scenario'] = scenario_document(source)
    if balance:
        raw['generation'] = {'groups':[
            dict(group_id='crushing', actor_ids=['crushing_bear1', 'crushing_bear2'], minimum_count=1, maximum_count=2),
            dict(group_id='sweeping', actor_ids=['bear1'], minimum_count=0, maximum_count=1)],
            'facts':deepcopy(raw['template']['facts']), 'max_candidates':4}
        raw['evaluation'].update(master_seed='42', trials_per_candidate=1, max_total_trials=4, top_k=2)
    else:
        raw['simulation'].update(master_seed='42', trials=2)
    return raw


class PcCrushingWeightJsonTests(unittest.TestCase):
    def test_both_families_roundtrip_closed_descriptor_caps_and_existing_policy(self):
        for balance in (False, True):
            raw = crushing_document(balance=balance)
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command = parse(json.dumps(raw))
            source = command.request.template if balance else command.request.scenario
            key = 'template' if balance else 'scenario'
            self.assertEqual(scenario_document(source), raw[key])
            self.assertEqual(raw[key]['enemies'][0]['definition']['attack']['secondary_effects'], [EFFECT])
            self.assertEqual(raw[key]['enemies'][0]['definition']['attack']['test_profile']['pool_cap'], 8)
            self.assertEqual(set(raw[key]), set(document(balance=balance)[key]))
            self.assertEqual(raw['schema_version'], '1')

    def test_missing_unknown_false_and_equal_type_alias_descriptor_fields_are_rejected(self):
        for balance in (False, True):
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            error = PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            key = 'template' if balance else 'scenario'
            malformed = [dict(EFFECT, affects_monstrosities=value) for value in (False, 1, 'true')]
            malformed += [dict(EFFECT, unexpected=True), dict(EFFECT, rule_id='authored:prone'),
                dict(EFFECT, kind='condition_on_hit')]
            for missing in EFFECT:
                row = dict(EFFECT)
                del row[missing]
                malformed.append(row)
            for row in malformed:
                raw = crushing_document(balance=balance)
                raw[key]['enemies'][0]['definition']['attack']['secondary_effects'] = [row]
                with self.subTest(balance=balance, row=row), self.assertRaises(error):
                    parse(json.dumps(raw))

    def test_other_bear_or_authored_npc_cannot_borrow_the_pre_stagger_descriptor(self):
        for raw in (document(), crushing_document()):
            index = 0 if raw['scenario']['enemies'][0]['actor_id'].startswith('minion') else -1
            raw['scenario']['enemies'][index]['definition']['attack']['secondary_effects'] = [EFFECT]
            with self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_canonical_effect_and_cap_are_both_required_and_cannot_move_to_protection(self):
        for effects in ([], [dict(EFFECT), dict(EFFECT)]):
            raw = crushing_document()
            raw['scenario']['enemies'][0]['definition']['attack']['secondary_effects'] = effects
            with self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))
        for role, cap in (('attack', None), ('attack', 6), ('attack', 8.0), ('protection', 8)):
            raw = crushing_document()
            raw['scenario']['enemies'][0]['definition'][role]['test_profile']['pool_cap'] = cap
            with self.subTest(role=role, cap=cap), self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_actual_trials_and_summary_keep_existing_extra_attack_counters_and_no_prone_bank(self):
        raw = crushing_document()
        command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
        result = run_pc_melee_simulation(command.request)
        summary = summarize_pc_melee_simulation(result)
        self.assertTrue(all(record.source_scenario == command.request.scenario for record in result.records))
        self.assertGreater(summary.total_npc_extra_attack_count, 0)
        self.assertEqual(summary.total_action_count, sum(record.executed_actions for record in result.records))
        self.assertEqual(tuple(row.actor_id for row in summary.npc_extra_attack_counts),
            command.request.scenario.enemy_activation_order)
        encoded = json.loads(wire.encode_pc_melee_simulation_result(command, summary))
        validate_pc_melee_simulation_document(encoded, 'result')
        self.assertEqual(encoded['request'], raw)
        self.assertFalse(any(hasattr(record, 'steps') for record in result.records))
        self.assertNotIn('prone_counts', encoded['summary'])

    def test_count_search_filters_both_bear_policies_without_reassigning_or_changing_sources(self):
        raw = crushing_document(balance=True)
        command = wire.parse_pc_melee_balance_request(json.dumps(raw))
        report = execute_pc_melee_balance(command)
        self.assertEqual((len(report.candidates), report.total_trials), (4, 4))
        encoded = json.loads(wire.encode_pc_melee_balance_result(command, report))
        validate_pc_melee_balance_document(encoded, 'result')
        self.assertEqual(encoded['request'], raw)
        original = {row['actor_id']:row['definition'] for row in raw['template']['enemies']}
        for row, candidate in zip(encoded['candidates'], report.candidates, strict=True):
            source = candidate.source_request.scenario
            self.assertEqual(source.npc_extra_attack_actor_ids, source.enemy_activation_order)
            self.assertEqual(row['request']['scenario'], scenario_document(source))
            for enemy in row['request']['scenario']['enemies']:
                self.assertEqual(enemy['definition'], original[enemy['actor_id']])

    def test_cached_equal_bool_flag_cannot_reach_rng_or_runner(self):
        command = wire.parse_pc_melee_simulation_request(json.dumps(crushing_document()))
        request = deepcopy(command.request)
        object.__setattr__(request.scenario.enemies[0].definition.attacks[0].secondary_effects[0],
            'affects_monstrosities', 1)
        self.assertEqual(request, command.request)
        rng = Mock(side_effect=AssertionError('malformed source must not consume RNG'))
        runner = Mock(side_effect=AssertionError('malformed source must not enter runner'))
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario', runner):
            with self.assertRaises(TypeError):
                run_pc_melee_trial(request, 0, rng_factory=rng)
        rng.assert_not_called()
        runner.assert_not_called()


if __name__ == '__main__':
    unittest.main()
