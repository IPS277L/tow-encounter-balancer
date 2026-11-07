"""Conditional two-profile source, actual Trample costs and current PC JSON1."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import Mock, patch

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_m9_pc_melee_json import document
from tests.unit.test_m51_great_stag_execution import scene, PC_MISS, ANTLERS, TRAMPLE_MISS
from towr.adapters import pc_melee_json as wire
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json_errors import PcMeleeBalanceInputError, PcMeleeSimulationInputError
from towr.adapters.pc_melee_json_schema import (
    validate_pc_melee_balance_document, validate_pc_melee_simulation_document,
)
from towr.application.pc_melee_service import execute_pc_melee_balance
from towr.domain.test_models import Skill
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation, run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def stag_document(*, balance=False):
    source = book_pc_scenario(great_stags=2 if balance else 1, bears=1,
        footpads=0, townsfolk=0, max_rounds=2)
    source = replace(source, npc_extra_attack_actor_ids=source.enemy_activation_order)
    raw = document(balance=balance)
    raw['template' if balance else 'scenario'] = scenario_document(source)
    if balance:
        raw['generation'] = {'groups':[
            dict(group_id='stags', actor_ids=['great_stag1', 'great_stag2'], minimum_count=1, maximum_count=2),
            dict(group_id='bears', actor_ids=['bear1'], minimum_count=0, maximum_count=1)],
            'facts':deepcopy(raw['template']['facts']), 'max_candidates':4}
        raw['evaluation'].update(master_seed='42', trials_per_candidate=1, max_total_trials=4, top_k=2)
    else:
        raw['simulation'].update(master_seed='42', trials=2)
    return raw


class PcGreatStagJsonTests(unittest.TestCase):
    def test_both_families_roundtrip_full_two_profiles_and_existing_policy(self):
        for balance in (False, True):
            raw = stag_document(balance=balance)
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            command = parse(json.dumps(raw))
            source = command.request.template if balance else command.request.scenario
            self.assertEqual(scenario_document(source), raw[key])
            self.assertEqual(set(raw[key]), set(document(balance=balance)[key]))
            self.assertEqual(raw['schema_version'], '1')
            profiles = source.enemy('great_stag1').definition.attacks
            self.assertEqual(tuple(p.skill for p in profiles), (Skill.MELEE, Skill.BRAWN))
            self.assertEqual(tuple(p.test_profile.base_dice for p in profiles), (4, 5))
            self.assertEqual(tuple(p.test_profile.maximum_dice for p in profiles), (8, 10))
            trample = raw[key]['enemies'][0]['definition']['trample_attack']
            self.assertEqual((trample['id'], trample['skill'], trample['damage']['base']), ('trample', 'brawn', 5))
            self.assertIsNone(trample['test_profile']['pool_cap'])
            self.assertNotIn('trample_attack', raw[key]['enemies'][-1]['definition'])

    def test_required_conditional_secondary_cannot_be_missing_malformed_or_defaulted(self):
        for balance in (False, True):
            key = 'template' if balance else 'scenario'
            parse = wire.parse_pc_melee_balance_request if balance else wire.parse_pc_melee_simulation_request
            error = PcMeleeBalanceInputError if balance else PcMeleeSimulationInputError
            raw = stag_document(balance=balance)
            del raw[key]['enemies'][0]['definition']['trample_attack']
            with self.assertRaises(error):
                parse(json.dumps(raw))
            for field, value in (('skill', 'melee'), ('skill', 'shooting'), ('id', 'mighty_antlers'),
                    ('hands', '1h'), ('range_max', 'short'), ('unexpected', True),
                    ('source_rule_id', 'authored:trample')):
                raw = stag_document(balance=balance)
                raw[key]['enemies'][0]['definition']['trample_attack'][field] = value
                with self.subTest(balance=balance, field=field, value=value), self.assertRaises(error):
                    parse(json.dumps(raw))
            original = stag_document(balance=balance)[key]['enemies'][0]['definition']['trample_attack']
            for field in original:
                raw = stag_document(balance=balance)
                del raw[key]['enemies'][0]['definition']['trample_attack'][field]
                with self.subTest(balance=balance, missing=field), self.assertRaises(error):
                    parse(json.dumps(raw))

    def test_caps_numbers_and_flags_cannot_change_the_canonical_trample(self):
        for role, field, value in (('test_profile', 'pool_cap', 8), ('test_profile', 'pool_cap', 10),
                ('test_profile', 'dice', 4), ('test_profile', 'dice', 5.0),
                ('test_profile', 'threshold', 4), ('damage', 'base', 6),
                ('damage', 'success_multiplier', True)):
            raw = stag_document()
            raw['scenario']['enemies'][0]['definition']['trample_attack'][role][field] = value
            with self.subTest(role=role, field=field, value=value), self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))
        for field, value in (('holds_shield', True), ('wields_weapon', True)):
            raw = stag_document()
            raw['scenario']['enemies'][0][field] = value
            with self.subTest(field=field), self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_secondary_field_is_forbidden_for_bear_and_authored_source(self):
        trample = stag_document()['scenario']['enemies'][0]['definition']['trample_attack']
        for raw, index in ((document(), 0), (stag_document(), -1)):
            raw['scenario']['enemies'][index]['definition']['trample_attack'] = deepcopy(trample)
            with self.assertRaises(PcMeleeSimulationInputError):
                wire.parse_pc_melee_simulation_request(json.dumps(raw))
        raw = stag_document()
        raw['scenario']['enemies'][0]['definition']['id'] = 'authored:stag'
        with self.assertRaises(PcMeleeSimulationInputError):
            wire.parse_pc_melee_simulation_request(json.dumps(raw))

    def test_literal_trample_is_counted_as_one_real_extra_action_in_compact_records(self):
        raw = document()
        raw['scenario'] = scenario_document(scene())
        raw['simulation'].update(trials=2)
        command = wire.parse_pc_melee_simulation_request(json.dumps(raw))
        rolls = []
        def dice(_seed):
            rng = ScriptedD10(PC_MISS+ANTLERS+[9]+TRAMPLE_MISS)
            rolls.append(rng)
            return rng
        result = run_pc_melee_simulation(command.request, rng_factory=dice)
        for rng in rolls:
            rng.assert_exhausted()
        summary = summarize_pc_melee_simulation(result)
        self.assertEqual((summary.total_action_count, summary.npc_extra_attack_trial_count,
            summary.total_npc_extra_attack_count), (6, 2, 2))
        self.assertEqual(tuple((row.actor_id, row.count) for row in summary.npc_extra_attack_counts),
            (('great_stag1', 2),))
        self.assertTrue(all(record.executed_actions==3 for record in result.records))
        self.assertTrue(all(not hasattr(record, 'steps') for record in result.records))
        encoded = json.loads(wire.encode_pc_melee_simulation_result(command, summary))
        validate_pc_melee_simulation_document(encoded, 'result')
        self.assertEqual(encoded['request'], raw)
        self.assertNotIn('trample_counts', encoded['summary'])

    def test_four_count_compositions_preserve_both_profiles_and_filter_actor_list(self):
        raw = stag_document(balance=True)
        command = wire.parse_pc_melee_balance_request(json.dumps(raw))
        report = execute_pc_melee_balance(command)
        self.assertEqual((len(report.candidates), report.total_trials), (4, 4))
        encoded = json.loads(wire.encode_pc_melee_balance_result(command, report))
        validate_pc_melee_balance_document(encoded, 'result')
        self.assertEqual(encoded['request'], raw)
        originals = {enemy['actor_id']:enemy['definition'] for enemy in raw['template']['enemies']}
        for row, candidate in zip(encoded['candidates'], report.candidates, strict=True):
            source = candidate.source_request.scenario
            self.assertEqual(row['request']['scenario'], scenario_document(source))
            self.assertEqual(source.npc_extra_attack_actor_ids, source.enemy_activation_order)
            for enemy in row['request']['scenario']['enemies']:
                self.assertEqual(enemy['definition'], originals[enemy['actor_id']])

    def test_equal_cached_secondary_alias_is_readmitted_before_rng_and_runner(self):
        command = wire.parse_pc_melee_simulation_request(json.dumps(stag_document()))
        request = deepcopy(command.request)
        object.__setattr__(request.scenario.enemy('great_stag1').definition.attacks[1].test_profile, 'dice', 5.0)
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
