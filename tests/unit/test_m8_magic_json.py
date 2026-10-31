"""Pure ADR-0043 magic wire admission and aggregate projection."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from importlib.resources import files
import json
from pathlib import Path
import pickle
import random
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator, ValidationError

from tests.unit.test_m4_ranged_json import at, object_paths
from tests.unit.test_m8_miscast_continuation_policy import continuation_policy
from towr.adapters.magic_json_errors import MagicSimulationInputError
from towr.adapters.magic_json_schema import validate_magic_simulation_document as validate
from towr.adapters.magic_simulation_json import (
    parse_magic_simulation_request as parse, encode_magic_simulation_result as encode,
)
from towr.adapters.melee_json_errors import MeleeInputError
from towr.adapters.mixed_json_errors import MixedInputError
from towr.adapters.ranged_json_errors import RangedInputError, RangedInputErrorCode as Code
from towr.application.magic_simulation_models import MagicSimulationCommand
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions as Options
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.movement_models import MovementSpeed
from towr.domain.ranged_weapon_profiles import RangedWeaponHands
from towr.domain.test_models import Skill
from towr.simulation.npc_magic_models import NpcMagicOutcomeCounts
from towr.simulation.npc_magic_summary_models import NpcMagicSimulationSummary


EXAMPLES = Path(__file__).resolve().parents[2] / 'docs/examples/m8/json'


def document():
    return json.loads((EXAMPLES / 'magic-simulation-v1.request.json').read_text(encoding='utf-8'))


def summary(command):
    # Necessary native arithmetic only; no fabricated Monte Carlo distribution.
    return NpcMagicSimulationSummary(command.request,
        NpcMagicOutcomeCounts(0, 0, 0, command.request.trials), 0, command.request.trials, 0)


def balance_scenario_document():
    data = document()
    balance = json.loads((EXAMPLES / 'magic-balance-v1.request.json').read_text(encoding='utf-8'))
    data['scenario'] = balance['reserve']['scenario']
    data['simulation']['round_budget'] = balance['reserve']['round_budget']
    return data


class M8MagicJsonTests(unittest.TestCase):
    def test_v1_keeps_none_and_rejects_explicit_opt_in_without_projection(self):
        data = document()
        legacy = parse(json.dumps(data))
        self.assertIsNone(legacy.request.scenario.miscast_continuation)
        scenario = replace(legacy.request.scenario, miscast_continuation=continuation_policy())
        command = replace(legacy, request=replace(legacy.request, scenario=scenario))
        before = deepcopy(command)
        with (patch('towr.adapters.magic_simulation_json.parse_magic_simulation_request',
                    side_effect=AssertionError('must reject before round-trip')),
              self.assertRaisesRegex(ValueError, 'Miscast continuation.*losslessly')):
            encode(command, summary(command))
        self.assertEqual(command, before)
        for value in (None, {}, {'choice': 'decline_cast_before_miscast'}):
            with self.subTest(value=value):
                data['scenario']['miscast_continuation'] = value
                self.assert_invalid(data)

    def assert_invalid(self, data, code=Code.INVALID_INPUT):
        with self.assertRaises(MagicSimulationInputError) as caught:
            parse(json.dumps(data))
        error = caught.exception
        self.assertEqual(error.code, code)
        for family in (RangedInputError, MeleeInputError, MixedInputError):
            self.assertNotIsInstance(error, family)
        return error

    def assert_roundtrip(self, data):
        command = parse(json.dumps(data))
        before = deepcopy(command)
        encoded = encode(command, summary=summary(command))
        self.assertTrue(encoded.endswith('\n'))
        output = json.loads(encoded)
        validate(output, 'result')
        self.assertEqual(output['request'], data)
        self.assertEqual(parse(json.dumps(output['request'])), command)
        self.assertEqual(command, before)
        return command

    def test_packaged_schemas_and_contract_fixtures(self):
        for kind in ('request', 'result', 'error'):
            schema = json.loads(files('towr.adapters.schemas').joinpath(
                f'magic-simulation-{kind}-v1.schema.json').read_text(encoding='utf-8'))
            Draft202012Validator.check_schema(schema)
            self.assertEqual(schema['$id'], f'urn:towr:magic-simulation:{kind}:1')
            fixture = json.loads((EXAMPLES / f'magic-simulation-v1.{kind}.json').read_text(encoding='utf-8'))
            validate(fixture, kind)
        with self.assertRaises(ValueError):
            validate({}, 'balance')

    def test_every_input_object_rejects_missing_and_unknown_fields(self):
        source = document()
        for path in object_paths(source):
            for key in (None, *at(source, path)):
                with self.subTest(path=path, key=key):
                    data = deepcopy(source)
                    if key is None:
                        at(data, path)['extra_rule'] = True
                    else:
                        del at(data, path)[key]
                    self.assert_invalid(data)

    def test_every_result_and_error_object_is_closed_and_required(self):
        for kind in ('result', 'error'):
            original = json.loads((EXAMPLES / f'magic-simulation-v1.{kind}.json').read_text(encoding='utf-8'))
            for path in object_paths(original):
                for key in (None, *at(original, path)):
                    with self.subTest(kind=kind, path=path, key=key):
                        changed = deepcopy(original)
                        if key is None:
                            at(changed, path)['extra'] = True
                        else:
                            del at(changed, path)[key]
                        with self.assertRaises(ValidationError):
                            validate(changed, kind)
        error = json.loads((EXAMPLES / 'magic-simulation-v1.error.json').read_text(encoding='utf-8'))
        for path in ('/bad~2', '\n', '/bad~\n', 'no-slash'):
            with self.subTest(path=path), self.assertRaises(ValidationError):
                validate(dict(error, error=dict(error['error'], path=path)), 'error')

    def test_strict_lexical_reader_preserves_existing_boundary(self):
        cases = [(b'\xff', Code.INVALID_JSON), ('{', Code.INVALID_JSON),
                 ('{"a":1,"a":2}', Code.INVALID_JSON), ('{"a":{"b":1,"b":2}}', Code.INVALID_JSON),
                 ('{"a":NaN}', Code.INVALID_JSON), ('{"a":Infinity}', Code.INVALID_JSON),
                 ('{"a":-Infinity}', Code.INVALID_JSON), ('{"a":1.0}', Code.INVALID_INPUT),
                 ('{"a":1e0}', Code.INVALID_INPUT), ('{"a":1e999}', Code.INVALID_INPUT),
                 ('{} {}', Code.INVALID_JSON), ('\ufeff{}', Code.INVALID_JSON),
                 (json.dumps({'a': chr(0xD800)}), Code.INVALID_JSON),
                 (json.dumps({chr(0xD800): 'a'}), Code.INVALID_JSON)]
        for raw, code in cases:
            with self.subTest(raw=raw), self.assertRaises(MagicSimulationInputError) as caught:
                parse(raw)
            self.assertEqual(caught.exception.code, code)
        for value in ([], None, 1, 'object'):
            self.assert_invalid(value)
        for raw in (None, {}, bytearray(b'{}')):
            with self.assertRaises(TypeError):
                parse(raw)

    def test_version_ruleset_and_family_have_no_fallback(self):
        for field, value in (('schema_version', '3'), ('schema_version', 1),
                             ('kind', 'npc_ranged_simulation'), ('kind', 'npc_magic_balance'),
                             ('ruleset', 'other')):
            with self.subTest(field=field, value=value):
                data = dict(document(), **{field: value})
                error = self.assert_invalid(data, Code.UNSUPPORTED_VERSION if value == '3' else Code.INVALID_INPUT)
                self.assertEqual(error.request_id, data['request_id'])
                self.assertEqual(error.path, '/' + field)
        for value in ('', ' \t', 1, None):
            data = dict(document(), request_id=value)
            self.assertIsNone(self.assert_invalid(data).request_id)

    def test_fixture_initial_state_is_fresh_with_independent_identity(self):
        data = document()
        command = parse(json.dumps(data).encode('utf-8'))
        scenario, initial = command.request.scenario, command.request.scenario.initial
        self.assertEqual(command.request_id, data['request_id'])
        self.assertEqual(scenario.id, data['scenario']['scenario_id'])
        self.assertNotEqual(command.request_id, scenario.id)
        self.assertEqual(initial.champion_attack.daily_wounds.day_id, data['scenario']['wizard']['day_id'])
        self.assertEqual(initial.round_state.round_number, 1)
        self.assertIsNone(initial.round_state.active_turn)
        self.assertEqual(initial.consumed_execution_ids, ())
        for field in ('pending_miscast', 'pending_movement', 'pending_interruption', 'pending_minion_attack'):
            self.assertIsNone(getattr(initial, field))
        self.assertIsNone(initial.champion_attack.pending)
        self.assertIsNone(initial.minion_attack)
        self.assertEqual(initial.wizard.magic_state.casting_successes, 0)
        participants = initial.roster.participants
        self.assertIs(participants[1].definition, participants[2].definition)
        self.assertIsNot(participants[1].state, participants[2].state)
        self.assertTrue(all(not p.state.injury.wounds and not p.state.injury.conditions.conditions for p in participants))
        self.assertEqual(participants[1].definition.attacks[0].skill, Skill.SHOOTING)
        self.assertEqual(participants[1].definition.attacks[0].hands, RangedWeaponHands.TWO_HANDED)
        self.assertEqual(participants[0].definition.protection[0].skill, Skill.ATHLETICS)
        data['scenario']['actors'].clear()
        self.assertEqual(len(participants), 3)

    def test_uint64_seeds_and_large_exact_counters_roundtrip(self):
        for seed in ('0', str(2**64 - 1)):
            data = document()
            data['simulation'].update(master_seed=seed, trials=2**64 - 1, round_budget=2**53 + 1)
            command = self.assert_roundtrip(data)
            self.assertEqual(command.request.master_seed, int(seed))
            self.assertEqual(json.loads(encode(command, summary(command)))['summary']['trials'], 2**64 - 1)
        for value in (0, True, '01', '-1', '+1', ' 1', '1\n', '1.0', '1e0', '', str(2**64), '9' * 21):
            with self.subTest(value=value):
                data = document()
                data['simulation']['master_seed'] = value
                self.assertEqual(self.assert_invalid(data).path, '/simulation/master_seed')

    def test_integer_boolean_identifier_fields_never_coerce(self):
        cases = (
            (('simulation', 'trials'), (0, 2**64, True, '3', 3.0)),
            (('simulation', 'round_budget'), (0, False, '5')),
            (('scenario', 'definitions', 1, 'attacks', 0, 'dice'), (0, -1, True, '3')),
            (('scenario', 'definitions', 1, 'attacks', 0, 'threshold'), (0, 11)),
            (('scenario', 'definitions', 1, 'attacks', 0, 'damage'), (-1, True)),
            (('scenario', 'definitions', 0, 'resilience', 'toughness'), (-1, True)),
            (('scenario', 'definitions', 0, 'protection', 0, 'dice'), (0, True)),
            (('scenario', 'wizard', 'caster', 'wizard_level'), (0, 5, True, '2')),
            (('scenario', 'actor_policies', 1, 'willpower', 'threshold'), (0, 11, True)),
            (('request_id',), ('', ' \t', 17)),
            (('scenario', 'scenario_id'), ('', ' ', 17)),
            (('scenario', 'wizard', 'day_id'), ('', ' ', 17)),
        )
        for path, values in cases:
            for value in values:
                with self.subTest(path=path, value=value):
                    data = document()
                    at(data, path[:-1])[path[-1]] = value
                    self.assert_invalid(data)

    def test_process_options_preserve_historical_class_and_explicit_parameters(self):
        for workers in (1, 61):
            data = document()
            data['execution'] = {'mode': 'process', 'workers': workers, 'batch_size': 2**53 + 1}
            command = self.assert_roundtrip(data)
            self.assertIs(type(command.execution), Options)
            self.assertIs(command.execution.mode, Mode.PROCESS)
        for options in ({'mode': 'sequential', 'workers': 1}, {'mode': 'process'},
                        {'mode': 'process', 'workers': 62, 'batch_size': 1},
                        {'mode': 'process', 'workers': True, 'batch_size': 1},
                        {'mode': 'process', 'workers': 2, 'batch_size': 0}, {'mode': 'auto'}):
            self.assert_invalid(dict(document(), execution=options))

    def test_all_facts_canonical_spell_and_stagger_choice_are_explicit(self):
        for name in document()['scenario']['facts']:
            for value in ((True, 0, 'false') if name == 'requires_reload_action' else (False, 1, 'true')):
                with self.subTest(name=name, value=value):
                    data = document()
                    data['scenario']['facts'][name] = value
                    self.assert_invalid(data)
        for name, value in (('rule_id', 'other'), ('lore_id', 'other'), ('casting_value', 4),
                            ('target_kind', 'creature'), ('range', 'short'), ('duration', 'battle')):
            data = document()
            data['scenario']['spell'][name] = value
            self.assert_invalid(data)
        data = document()
        data['scenario']['repeated_stagger_choice'] = 'give_ground'
        self.assert_invalid(data)

    def test_command_is_typed_frozen_copies_order_and_pickles(self):
        command = parse(json.dumps(document()))
        for changes in ({'request': None}, {'execution': None}, {'request_id': ''}, {'request_id': 1},
                        {'definition_order': ()}, {'definition_order': ('unknown',)},
                        {'definition_order': (*command.definition_order, *command.definition_order)}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(command, **changes)
        for order in (None, set(command.definition_order), 'ab', iter(command.definition_order)):
            with self.assertRaises(TypeError):
                replace(command, definition_order=order)
        order = list(command.definition_order)
        copied = MagicSimulationCommand(command.request_id, command.request, command.execution, order)
        order.clear()
        self.assertEqual(copied, command)
        self.assertEqual(pickle.loads(pickle.dumps(command)), command)
        with self.assertRaises(FrozenInstanceError):
            command.definition_order = ()
        self.assertFalse(hasattr(command, '__dict__'))

    def test_wrong_family_is_rejected_by_command_and_encoder(self):
        from tests.unit.test_m7_mixed_json import document as mixed_document
        from towr.adapters.mixed_simulation_json import parse_mixed_simulation_request
        mixed = parse_mixed_simulation_request(json.dumps(mixed_document()))
        command = parse(json.dumps(document()))
        with self.assertRaises(TypeError):
            replace(command, request=mixed.request)
        with self.assertRaises(TypeError):
            encode(mixed, summary(command))
        with self.assertRaises(TypeError):
            encode(command, None)

    def test_all_independent_arrays_and_unicode_ids_roundtrip(self):
        data = document()
        data['request_id'] = ' внешний:🧙 '
        scenario = data['scenario']
        scenario['scenario_id'], scenario['wizard']['day_id'] = ' сцена:🎯 ', ' день:1 '
        scenario['definitions'].reverse()
        scenario['actors'].reverse()
        scenario['actor_policies'].reverse()
        scenario['activation_order'].reverse()
        scenario['placements'].reverse()
        scenario['objective_target_ids'].reverse()
        scenario['battlefield']['zone_ids'].reverse()
        scenario['battlefield']['connections'].reverse()
        for policy in scenario['actor_policies']:
            policy['target_actor_ids'].reverse()
            policy['defeat_decisions'].reverse()
            policy['zone_priorities'].reverse()
        for frame in scenario['scene_frames']:
            frame['key']['placements'].reverse()
            frame['key']['live_actor_ids'].reverse()
            frame['pair_ranges'].reverse()
            frame['give_ground_plans'].reverse()
            frame['broken_plans'].reverse()
            frame['attack_departures'].reverse()
            frame['zone_ranges'].reverse()
            for pair in frame['pair_ranges']:
                pair['first_actor_id'], pair['second_actor_id'] = pair['second_actor_id'], pair['first_actor_id']
                pair['first_range_approved_by_gm'], pair['second_range_approved_by_gm'] = (
                    pair['second_range_approved_by_gm'], pair['first_range_approved_by_gm'])
        scenario['scene_frames'].reverse()
        command = self.assert_roundtrip(data)
        self.assertEqual(command.definition_order, tuple(d['id'] for d in scenario['definitions']))
        self.assertNotEqual(tuple(p.state.actor_id for p in command.request.scenario.initial.roster.participants),
                            tuple(p.entity_id for p in command.request.scenario.initial.spatial_state.placements))

    def test_both_wizard_sides_and_perspectives_are_independent(self):
        for flip in (False, True):
            for perspective in ('players_and_allies', 'opposition'):
                with self.subTest(flip=flip, perspective=perspective):
                    data = document()
                    scenario = data['scenario']
                    if flip:
                        opposite = {'players_and_allies': 'opposition', 'opposition': 'players_and_allies'}
                        for actor in scenario['actors']:
                            actor['side'] = opposite[actor['side']]
                        for placement in scenario['placements']:
                            placement['side_id'] = opposite[placement['side_id']]
                        for frame in scenario['scene_frames']:
                            for placement in frame['key']['placements']:
                                placement['side_id'] = opposite[placement['side_id']]
                    scenario['perspective_side'] = perspective
                    scenario['objective_target_ids'] = [a['id'] for a in reversed(scenario['actors']) if a['side'] != perspective]
                    self.assert_roundtrip(data)

    def test_minion_profile_range_hands_numeric_and_defeat_enums_preserved(self):
        for disposition in NpcDefeatDisposition:
            data = document()
            for policy in data['scenario']['actor_policies']:
                for decision in policy['defeat_decisions']:
                    decision['disposition'] = disposition.value
            self.assert_roundtrip(data)
        for hands in RangedWeaponHands:
            data = document()
            definition = data['scenario']['definitions'][1]
            definition['source_rule_id'] = 'caller:numeric'
            definition['attacks'][0].update(hands=hands.value, damage=0, range_min='medium', range_max='medium')
            definition['resilience'].update(toughness=0, bonus=1)
            self.assert_roundtrip(data)
        for speed in MovementSpeed:
            data = document()
            for policy in data['scenario']['actor_policies']:
                policy['speed'] = speed.value
            self.assert_roundtrip(data)

    def test_profile_and_policy_mutations_do_not_infer_or_drop_fields(self):
        changes = [
            lambda s: s['definitions'][0].update(injury_policy='minion', wound_limit=1),
            lambda s: s['definitions'][0]['resilience'].update(bonus=1),
            lambda s: s['definitions'][1]['attacks'][0].update(skill='melee'),
            lambda s: s['definitions'][1]['attacks'][0].update(range_min='close'),
            lambda s: s['definitions'][1]['attacks'][0].update(range_min='long', range_max='short'),
            lambda s: s['definitions'][1]['protection'][0].update(skill='defence'),
            lambda s: s['wizard'].update(actor_id='unknown'),
            lambda s: s['wizard']['caster']['casting_profile'].update(dice=2),
            lambda s: s['actor_policies'][0].update(attack_id='shot'),
            lambda s: s['actor_policies'][0].update(casting_policy=None),
            lambda s: s['actor_policies'][1].update(casting_policy='cast_when_ready'),
            lambda s: s['actor_policies'][1]['target_actor_ids'].clear(),
            lambda s: s['actor_policies'][2]['defeat_decisions'].append({
                'attacker_id': 'enemy', 'target_id': 'wizard', 'disposition': 'killed', 'gm_approved': True}),
            lambda s: s['actor_policies'][1]['defeat_decisions'][0].update(gm_approved=False),
        ]
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                data = document()
                change(data['scenario'])
                self.assert_invalid(data)

    def test_references_partitions_placement_coverage_and_frame_keys_are_exact(self):
        changes = [
            lambda s: s['definitions'].append(deepcopy(s['definitions'][0])),
            lambda s: s['definitions'].append(dict(s['definitions'][0], id='unused')),
            lambda s: s['actors'][0].update(definition_id='absent'),
            lambda s: s['actors'][1].update(id='wizard'),
            lambda s: s['placements'].pop(),
            lambda s: s['placements'][0].update(side_id='players_and_allies'),
            lambda s: s['placements'][0].update(zone_id='unknown'),
            lambda s: s['activation_order'].pop(),
            lambda s: s['side_order'].reverse(),
            lambda s: s.update(objective_target_ids=['ally']),
            lambda s: s['scene_frames'].pop(0),
            lambda s: s['scene_frames'].append(deepcopy(s['scene_frames'][0])),
            lambda s: s['scene_frames'][0]['key']['live_actor_ids'].reverse(),
            lambda s: s['scene_frames'][0]['key']['placements'].reverse(),
            lambda s: s['scene_frames'][0]['pair_ranges'].pop(),
            lambda s: s['scene_frames'][0]['pair_ranges'].append(deepcopy(s['scene_frames'][0]['pair_ranges'][0])),
            lambda s: s['scene_frames'][0]['pair_ranges'][0].update(second_actor_id='ally'),
            lambda s: s['scene_frames'][0]['pair_ranges'][0].update(target_range='close'),
            lambda s: s['scene_frames'][0]['zone_ranges'].reverse(),
            lambda s: s['scene_frames'][0]['give_ground_plans'].clear(),
            lambda s: s['scene_frames'][0]['attack_departures'].append(deepcopy(s['scene_frames'][0]['attack_departures'][0])),
        ]
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                data = document()
                change(data['scenario'])
                error = self.assert_invalid(data)
                self.assertTrue(error.path.startswith('/scenario'))
                self.assertEqual(error.request_id, data['request_id'])

    def test_duplicate_definition_and_missing_actor_definition_have_specific_paths(self):
        data = document()
        data['scenario']['definitions'].append(deepcopy(data['scenario']['definitions'][0]))
        self.assertEqual(self.assert_invalid(data).path, '/scenario/definitions/2/id')
        data = document()
        data['scenario']['actors'][0]['definition_id'] = 'absent'
        self.assertEqual(self.assert_invalid(data).path, '/scenario/actors/0/definition_id')

    def test_future_frames_can_archive_wizard_or_all_actors_without_compaction(self):
        data = document()
        for live in (['enemy'], []):
            frame = deepcopy(data['scenario']['scene_frames'][0])
            frame['key']['live_actor_ids'] = live
            for field in ('pair_ranges', 'give_ground_plans', 'broken_plans', 'attack_departures'):
                frame[field] = []
            data['scenario']['scene_frames'].append(frame)
        command = self.assert_roundtrip(data)
        self.assertEqual(command.request.scenario.scene_frames[-1].key.live_actor_ids, ())
        self.assertEqual(len(command.request.scenario.scene_frames[-1].key.placements), 3)
        self.assertEqual(len(command.request.scenario.scene_frames[-1].zone_ranges), 3)

    def test_nullable_plans_and_ordinary_departures_remain_independent(self):
        data = document()
        plan = data['scenario']['scene_frames'][2]['give_ground_plans'][0]
        self.assertIsNone(plan['destination_zone_id'])
        plan['can_leave_zone'] = True
        data['scenario']['scene_frames'][0]['attack_departures'] = []
        self.assert_roundtrip(data)
        for field, value in (('route', {'path_entity_ids': [], 'crosses_obstacle': False, 'crosses_difficult_terrain': False}),
                             ('impossible_confirmed', False)):
            changed = deepcopy(data)
            changed['scenario']['scene_frames'][2]['give_ground_plans'][0][field] = value
            self.assert_invalid(changed)

    def test_broken_moving_routes_preserve_all_three_path_fields(self):
        data = balance_scenario_document()
        scenario = data['scenario']
        for placement in scenario['placements']:
            if placement['entity_id'] == 'ally':
                placement['zone_id'] = 'shelter'
        frame = scenario['scene_frames'][0]
        frame['key']['placements'] = deepcopy(scenario['placements'])
        for pair in frame['pair_ranges']:
            if 'ally' in (pair['first_actor_id'], pair['second_actor_id']):
                pair['target_range'] = 'medium'
        ground = next(plan for plan in frame['give_ground_plans'] if plan['actor_id'] == 'E1')
        ground['route']['path_entity_ids'] = ['E2', 'E3']
        route = {'path_entity_ids': ['E3', 'E2'], 'crosses_obstacle': False, 'crosses_difficult_terrain': False}
        frame['broken_plans'] = [{'actor_id': 'E1', 'kind': 'free_move_run', 'free_move_zone_ids': ['shelter'],
            'free_move_route': deepcopy(route), 'run_destination_zone_id': 'boundary', 'run_route': deepcopy(route),
            'fastest_route_confirmed': True}]
        self.assert_roundtrip(data)
        recovered = document()
        recovered['scenario']['scene_frames'] = [recovered['scenario']['scene_frames'][0]]
        recovered['scenario']['actor_policies'][2]['speed'] = 'slow'
        recovered['scenario']['scene_frames'][0]['broken_plans'] = [{'actor_id': 'enemy', 'kind': 'free_move_recover',
            'free_move_zone_ids': ['shelter'], 'free_move_route': dict(route, path_entity_ids=[]),
            'run_destination_zone_id': None, 'run_route': None, 'fastest_route_confirmed': True}]
        self.assert_roundtrip(recovered)
        for field in ('free_move_route', 'run_route'):
            changed = deepcopy(data)
            changed['scenario']['scene_frames'][0]['broken_plans'][0][field]['path_entity_ids'] = ['wizard']
            self.assert_invalid(changed)
        changed = deepcopy(data)
        changed['scenario']['scene_frames'][0]['broken_plans'][0]['free_move_route']['crosses_obstacle'] = True
        self.assert_invalid(changed)

    def test_directed_gm_range_approvals_and_orientation_are_lossless(self):
        data = document()
        scenario = data['scenario']
        scenario['definitions'][1]['attacks'][0]['range_max'] = 'short'
        for frame in scenario['scene_frames']:
            for pair in frame['pair_ranges']:
                beyond = pair['target_range'] in ('medium', 'long')
                pair['first_range_approved_by_gm'] = beyond and pair['first_actor_id'] != 'wizard'
                pair['second_range_approved_by_gm'] = beyond and pair['second_actor_id'] != 'wizard'
                pair['first_actor_id'], pair['second_actor_id'] = pair['second_actor_id'], pair['first_actor_id']
                pair['first_range_approved_by_gm'], pair['second_range_approved_by_gm'] = (
                    pair['second_range_approved_by_gm'], pair['first_range_approved_by_gm'])
        self.assert_roundtrip(data)
        changed = deepcopy(data)
        changed['scenario']['scene_frames'][0]['pair_ranges'][0]['first_range_approved_by_gm'] = True
        self.assert_invalid(changed)

    def test_future_close_and_extreme_ranges_are_explicit_not_inferred(self):
        data = document()
        scenario = data['scenario']
        # A future archive key differs from the initial key; same-Zone range
        # remains explicitly Close here, while the initial frame uses Short.
        close = scenario['scene_frames'][3]
        for pair in close['pair_ranges']:
            pair['target_range'] = 'close'
        scenario['battlefield']['zone_ids'].append('remote')
        scenario['battlefield']['connections'].append({
            'first_zone_id': 'boundary', 'second_zone_id': 'remote'})
        scenario['actor_policies'][0]['zone_priorities'].append('remote')
        for frame in scenario['scene_frames']:
            frame['zone_ranges'].append({'zone_id': 'remote', 'target_range': 'extreme'})
        extreme = deepcopy(scenario['scene_frames'][0])
        for placement in extreme['key']['placements']:
            if placement['entity_id'] == 'enemy':
                placement['zone_id'] = 'remote'
        for pair in extreme['pair_ranges']:
            pair['target_range'] = 'extreme'
        extreme['give_ground_plans'][0].update(destination_zone_id=None, route=None,
            can_leave_zone=True, impossible_confirmed=True)
        scenario['scene_frames'].append(extreme)
        command = self.assert_roundtrip(data)
        self.assertEqual(command.request.scenario.scene_frames[3].pair_ranges[0].target_range.value, 'close')
        self.assertTrue(all(p.target_range.value == 'extreme'
                            for p in command.request.scenario.scene_frames[-1].pair_ranges))
        # Neither same-Zone placement nor graph distance authorizes replacing
        # caller-supplied facts with a preferred wire range.
        changed = deepcopy(data)
        changed['scenario']['scene_frames'][-1]['pair_ranges'][0]['target_range'] = 'long'
        self.assert_invalid(changed)

    def test_native_summary_has_four_counts_and_three_totals_without_aliases(self):
        command = parse(json.dumps(document()))
        observed = NpcMagicSimulationSummary(command.request, NpcMagicOutcomeCounts(1, 1, 1, 1), 6, 7, 4)
        output = json.loads(encode(command, observed))
        self.assertEqual(output['summary'], {'trials': 4, 'outcome_counts': {
            'objective_achieved': 1, 'perspective_defeated': 1, 'round_limit_reached': 1, 'unsupported_path': 1},
            'total_action_count': 6, 'total_started_round_count': 7, 'total_completed_round_count': 4})
        self.assertEqual(set(output), {'schema_version', 'kind', 'request', 'seed_scheme', 'runtime', 'summary'})
        self.assertEqual(output['seed_scheme'], 'towr:npc-magic-trial:v1')
        self.assertEqual(output['runtime']['rng'], 'random.Random')

    def test_saved_result_projection_matches_contract_fixture(self):
        command = parse(json.dumps(document()))
        expected = json.loads((EXAMPLES / 'magic-simulation-v1.result.json').read_text(encoding='utf-8'))
        saved = expected['summary']
        observed = NpcMagicSimulationSummary(command.request, NpcMagicOutcomeCounts(**saved['outcome_counts']),
            saved['total_action_count'], saved['total_started_round_count'], saved['total_completed_round_count'])
        actual = json.loads(encode(command, observed))
        expected['runtime'] = actual['runtime']
        self.assertEqual(actual, expected)

    def test_summary_source_requires_full_request_not_just_scenario_id(self):
        command = parse(json.dumps(document()))
        observed = summary(command)
        variants = []
        for change in (
            lambda d: d['simulation'].update(master_seed='43'),
            lambda d: d['simulation'].update(trials=5),
            lambda d: d['simulation'].update(round_budget=5),
            lambda d: d['scenario']['wizard'].update(day_id='other-day'),
            lambda d: d['scenario']['wizard']['caster'].update(wizard_level=3),
            lambda d: d['scenario']['activation_order'].reverse(),
            lambda d: d['scenario']['scene_frames'].reverse(),
            lambda d: d['scenario']['scene_frames'][0]['attack_departures'][0].update(can_leave_zone=False),
            lambda d: d['scenario']['actor_policies'][1]['willpower'].update(dice=4),
        ):
            data = document()
            change(data)
            variants.append(parse(json.dumps(data)))
        for altered in variants:
            with self.subTest(source=altered), self.assertRaises(ValueError):
                encode(altered, observed)
        # External request identity is intentionally separate from domain source.
        renamed = replace(command, request_id='other external request')
        self.assertEqual(json.loads(encode(renamed, observed))['request']['request_id'], renamed.request_id)

    def test_encoder_refuses_typed_source_not_representable_in_utf8(self):
        command = parse(json.dumps(document()))
        # Domain IDs are nonblank Python strings; v1 also requires UTF-8.
        scenario = replace(command.request.scenario, id=chr(0xD800))
        changed = replace(command, request=replace(command.request, scenario=scenario))
        with self.assertRaises(ValueError):
            encode(changed, summary(changed))

    def test_parser_and_encoder_are_pure_without_rng_runner_or_pool(self):
        before = random.getstate()
        with patch('random.Random', side_effect=AssertionError('RNG created')), \
                patch('towr.simulation.npc_magic_simulation.run_npc_magic_simulation', side_effect=AssertionError('runner called')), \
                patch('towr.simulation.npc_magic_parallel.ProcessPoolExecutor', side_effect=AssertionError('pool created')):
            command = self.assert_roundtrip(document())
            invalid = document()
            invalid['scenario']['facts']['targets_aware'] = False
            self.assert_invalid(invalid)
            self.assertEqual(command.request.trials, 4)
        self.assertEqual(random.getstate(), before)
