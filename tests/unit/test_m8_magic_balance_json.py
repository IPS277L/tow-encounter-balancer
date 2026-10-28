"""Pure magic balance wire admission and source-bound aggregate projection."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
from importlib.resources import files
import json
from pathlib import Path
import pickle
import random
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator, ValidationError

from tests.unit.test_m4_ranged_json import at, object_paths
from towr.adapters.magic_balance_json import parse_magic_balance_request as parse, encode_magic_balance_result as encode
from towr.adapters.magic_json_errors import MagicBalanceInputError, MagicSimulationInputError
from towr.adapters.magic_json_schema import validate_magic_balance_document as validate
from towr.adapters.ranged_json_errors import RangedInputError, RangedInputErrorCode as Code
from towr.application.magic_balance_models import MagicBalanceCommand, MagicBalanceResult
from towr.application.magic_candidate_generation import generate_magic_candidates
from towr.application.magic_candidate_generation_errors import MagicCandidateGenerationError
from towr.balance.magic_assessment_models import MagicCandidateAssessment
from towr.balance.magic_evaluation_models import (
    MagicBalanceEvaluationRequest, MagicBalanceEvaluationResult, MagicBalanceCandidateResult,
)
from towr.balance.magic_staged_evaluation import magic_continuation_candidate_ids
from towr.balance.magic_staged_evaluation_models import MagicStagedEvaluationResult
from towr.simulation.npc_magic_models import NpcMagicOutcomeCounts
from towr.simulation.npc_magic_summary_models import NpcMagicSimulationSummary


EXAMPLES = Path(__file__).resolve().parents[2] / 'docs/examples/m8/json'


def document():
    return json.loads((EXAMPLES / 'magic-balance-v1.request.json').read_text(encoding='utf-8'))


def make_result(command, counts=None):
    """Construct explicit native aggregates; no battle/RNG or distribution oracle."""
    generated = generate_magic_candidates(command.generation_request)
    source, reports = generated.evaluation_request, []
    candidates = source.candidates
    for index, stage in enumerate(source.stages):
        n = stage.trials_per_candidate
        request = MagicBalanceEvaluationRequest(candidates, source.master_seed, n,
            len(candidates) * n, source.window, stage.keep)
        rows = []
        for position, (candidate, simulation) in enumerate(zip(candidates, request.simulation_requests)):
            outcomes = counts(index, position, n) if counts else (n // 2, n - n // 2, 0, 0)
            terminal, limited = outcomes[0] + outcomes[1], outcomes[2]
            completed = limited * simulation.scenario.max_rounds
            summary = NpcMagicSimulationSummary(simulation, NpcMagicOutcomeCounts(*outcomes),
                terminal + completed, completed + n - limited, completed)
            rows.append(MagicBalanceCandidateResult(candidate.candidate_id,
                MagicCandidateAssessment(simulation, summary, source.window)))
        report = MagicBalanceEvaluationResult(request, tuple(rows))
        reports.append(report)
        kept = magic_continuation_candidate_ids(report)
        candidates = tuple(c for c in candidates if c.candidate_id in kept)
        if not candidates:
            break
    return MagicBalanceResult(generated, MagicStagedEvaluationResult(source, tuple(reports)))


def generation_failure_document():
    """Valid full reserve whose first projected subset invalidates Broken routing."""
    data = document()
    frame = deepcopy(data['reserve']['scenario']['scene_frames'][0])
    for placement in frame['key']['placements']:
        if placement['entity_id'] in ('E2', 'E3'):
            placement['zone_id'] = 'boundary'
    for pair in frame['pair_ranges']:
        pair['target_range'] = 'short' if pair['second_actor_id'] == 'E1' else 'long'
    for plan in frame['give_ground_plans']:
        if plan['actor_id'] in ('E2', 'E3'):
            plan.update(can_leave_zone=False, destination_zone_id=None, route=None, impossible_confirmed=True)
    frame['broken_plans'] = [{'actor_id': 'ally', 'kind': 'free_move_recover', 'free_move_zone_ids': ['shelter'],
        'free_move_route': {'path_entity_ids': [], 'crosses_obstacle': False, 'crosses_difficult_terrain': False},
        'run_destination_zone_id': None, 'run_route': None, 'fastest_route_confirmed': True}]
    data['reserve']['scenario']['scene_frames'].append(frame)
    data['generation']['scene_frames'] = deepcopy(data['reserve']['scenario']['scene_frames'])
    return data


class M8MagicBalanceJsonTests(unittest.TestCase):
    def invalid(self, data, code=Code.INVALID_INPUT):
        with self.assertRaises(MagicBalanceInputError) as caught:
            parse(json.dumps(data))
        self.assertEqual(caught.exception.code, code)
        self.assertNotIsInstance(caught.exception, MagicSimulationInputError)
        self.assertNotIsInstance(caught.exception, RangedInputError)
        return caught.exception

    def assert_roundtrip(self, data):
        command = parse(json.dumps(data))
        before = deepcopy(command)
        output = json.loads(encode(command, make_result(command)))
        validate(output, 'result')
        self.assertEqual(output['request'], data)
        self.assertEqual(parse(json.dumps(output['request'])), command)
        self.assertEqual(command, before)
        return command, output

    def test_packaged_schemas_and_three_contract_fixtures(self):
        for kind in ('request', 'result', 'error'):
            schema = json.loads(files('towr.adapters.schemas').joinpath(
                f'magic-balance-{kind}-v1.schema.json').read_text(encoding='utf-8'))
            Draft202012Validator.check_schema(schema)
            self.assertEqual(schema['$id'], f'urn:towr:magic-balance:{kind}:1')
            validate(json.loads((EXAMPLES / f'magic-balance-v1.{kind}.json').read_text(encoding='utf-8')), kind)
        with self.assertRaises(ValueError):
            validate({}, 'unknown')

    def test_request_objects_require_all_fields_and_reject_unknown_fields(self):
        original = document()
        for path in object_paths(original):
            for key in (None, *at(original, path)):
                with self.subTest(path=path, key=key):
                    data = deepcopy(original)
                    if key is None:
                        at(data, path)['unexpected'] = True
                    else:
                        del at(data, path)[key]
                    self.invalid(data)

    def test_strict_lexical_reader_and_wrong_root_types(self):
        for raw, code in ((b'\xff', Code.INVALID_JSON), ('{', Code.INVALID_JSON),
                ('{"x":1,"x":2}', Code.INVALID_JSON), ('{"x":{"a":1,"a":2}}', Code.INVALID_JSON),
                ('{"x":NaN}', Code.INVALID_JSON), ('{"x":Infinity}', Code.INVALID_JSON),
                ('{"x":1.0}', Code.INVALID_INPUT), ('{"x":1e0}', Code.INVALID_INPUT),
                ('\ufeff{}', Code.INVALID_JSON), (json.dumps({'x': chr(0xD800)}), Code.INVALID_JSON)):
            with self.subTest(raw=raw), self.assertRaises(MagicBalanceInputError) as caught:
                parse(raw)
            self.assertEqual(caught.exception.code, code)
        for data in ([], None, True, 1, 'x'):
            self.invalid(data)
        for raw in ({}, None, bytearray(b'{}')):
            with self.assertRaises(TypeError):
                parse(raw)

    def test_versions_kind_ruleset_and_external_request_context(self):
        for field, value in (('schema_version', '2'), ('schema_version', 1),
                ('kind', 'npc_magic_simulation'), ('kind', 'npc_mixed_balance'), ('ruleset', 'other')):
            data = dict(document(), **{field: value})
            error = self.invalid(data, Code.UNSUPPORTED_VERSION if value == '2' else Code.INVALID_INPUT)
            self.assertEqual(error.path, '/' + field)
            self.assertEqual(error.request_id, data['request_id'])
        for value in ('', ' \t', None, 1):
            self.assertIsNone(self.invalid(dict(document(), request_id=value)).request_id)

    def test_request_uses_separate_ids_facts_and_full_frames(self):
        data = document()
        command = parse(json.dumps(data).encode('utf-8'))
        source = command.generation_request
        self.assertEqual(command.request_id, data['request_id'])
        self.assertEqual(source.template_scenario.id, data['reserve']['scenario']['scenario_id'])
        self.assertNotEqual(command.request_id, source.template_scenario.id)
        self.assertEqual(source.template_scenario.initial.champion_attack.daily_wounds.day_id,
                         data['reserve']['scenario']['wizard']['day_id'])
        self.assertEqual(source.facts, source.template_scenario.facts)
        self.assertIsNot(source.facts, source.template_scenario.facts)
        self.assertEqual(source.scene_frames, source.template_scenario.scene_frames)
        self.assertIsNot(source.scene_frames, source.template_scenario.scene_frames)
        self.assertEqual((source.candidate_count, source.planned_trials), (4, 16))
        data['generation']['groups'][0]['actor_ids'].clear()
        self.assertEqual(source.groups[0].actor_ids, ('E2', 'E1'))

    def test_seed_integer_and_large_budget_boundaries(self):
        for value in ('0', str(2**64 - 1)):
            data = document(); data['evaluation']['master_seed'] = value
            self.assertEqual(parse(json.dumps(data)).generation_request.master_seed, int(value))
        for value in (str(2**64), '01', '-1', '+1', '42\n', 42, True, '9' * 21):
            data = document(); data['evaluation']['master_seed'] = value
            self.assertEqual(self.invalid(data).path, '/evaluation/master_seed')
        for path in (('generation', 'max_candidates'), ('evaluation', 'max_total_trials'),
                ('evaluation', 'stages', 0, 'trials_per_candidate'), ('evaluation', 'stages', 0, 'keep'),
                ('evaluation', 'window', 'minimum', 'numerator')):
            for value in (True, '3', -1):
                data = document(); at(data, path[:-1])[path[-1]] = value
                self.invalid(data)
        data = document()
        data['evaluation']['stages'] = [{'trials_per_candidate': 2**64 - 1, 'keep': 2**53 + 1}]
        data['evaluation']['max_total_trials'] = 4 * (2**64 - 1)
        data['generation']['max_candidates'] = 2**53 + 1
        command = parse(json.dumps(data))
        output = json.loads(encode(command, make_result(command)))
        self.assertEqual(output['planned_trials'], 4 * (2**64 - 1))
        self.assertEqual(output['request'], data)

    def test_fraction_input_is_normalized_without_float_rates(self):
        data = document()
        data['evaluation']['window']['minimum'] = {'numerator': 2, 'denominator': 8}
        command = parse(json.dumps(data))
        output = json.loads(encode(command, make_result(command)))
        self.assertEqual(command.generation_request.window.minimum, Fraction(1, 4))
        self.assertEqual(output['request']['evaluation']['window']['minimum'], {'numerator': 1, 'denominator': 4})
        self.assertEqual(parse(json.dumps(output['request'])), command)
        for value in ({'numerator': 1, 'denominator': 0}, {'numerator': -1, 'denominator': 2},
                {'numerator': 3, 'denominator': 2}, {'numerator': 2, 'denominator': 3}, '1/4', 0.25):
            changed = deepcopy(data); changed['evaluation']['window']['minimum'] = value
            self.invalid(changed)

    def test_execution_options_reuse_historical_classes_and_remain_explicit(self):
        from towr.application.ranged_simulation_models import SimulationExecutionOptions, SimulationExecutionMode
        data = dict(document(), execution={'mode': 'process', 'workers': 61, 'batch_size': 2**53 + 1})
        command, _ = self.assert_roundtrip(data)
        self.assertIs(type(command.execution), SimulationExecutionOptions)
        self.assertIs(command.execution.mode, SimulationExecutionMode.PROCESS)
        for options in ({'mode': 'auto'}, {'mode': 'sequential', 'workers': 1}, {'mode': 'process'},
                {'mode': 'process', 'workers': True, 'batch_size': 1},
                {'mode': 'process', 'workers': 62, 'batch_size': 1},
                {'mode': 'process', 'workers': 2, 'batch_size': 0}):
            self.invalid(dict(document(), execution=options))

    def test_family_facts_and_scene_frames_are_explicit_not_defaults(self):
        for name in document()['generation']['facts']:
            data = document(); data['generation']['facts'][name] = name == 'requires_reload_action'
            self.assertTrue(self.invalid(data).path.startswith('/generation/facts'))
        for change in (
                lambda f: f[0]['pair_ranges'].reverse(),
                lambda f: f[0]['pair_ranges'][0].update(first_range_approved_by_gm=True),
                lambda f: f[0]['key']['placements'].reverse(),
                lambda f: f[0]['attack_departures'][0].update(can_leave_zone=False),
                lambda f: f[0]['give_ground_plans'][0]['route']['path_entity_ids'].append('E2'),
                lambda f: f.clear()):
            data = document(); change(data['generation']['scene_frames'])
            self.assertTrue(self.invalid(data).path.startswith('/generation/scene_frames'))

    def test_group_partition_definition_and_full_budget_fail_before_projection(self):
        changes = (
            lambda d: d['generation']['groups'][0].update(actor_ids=['E2', 'wizard']),
            lambda d: d['generation']['groups'][0].update(actor_ids=['E2', 'ally']),
            lambda d: d['generation']['groups'][1].update(actor_ids=['E2']),
            lambda d: d['generation']['groups'][1].update(group_id='A'),
            lambda d: d['generation']['groups'].pop(),
            lambda d: d['generation']['groups'][0].update(minimum_count=2, maximum_count=1),
            lambda d: d['generation']['groups'][0].update(maximum_count=3),
            lambda d: d['generation'].update(max_candidates=3),
            lambda d: d['evaluation'].update(max_total_trials=15),
            lambda d: d['evaluation']['stages'][1].update(trials_per_candidate=2),
            lambda d: d['evaluation']['stages'][0].update(keep=0),
            lambda d: [g.update(minimum_count=0, maximum_count=0) for g in d['generation']['groups']],
        )
        with patch('towr.application.magic_candidate_generation._project_candidate', side_effect=AssertionError('materialized')):
            for index, change in enumerate(changes):
                with self.subTest(change=index):
                    data = document(); change(data); self.invalid(data)
            data = document()
            definition = deepcopy(data['reserve']['scenario']['definitions'][1]); definition['id'] = 'another'
            data['reserve']['scenario']['definitions'].append(definition)
            data['reserve']['scenario']['actors'][3]['definition_id'] = 'another'
            self.invalid(data)

    def test_all_zero_vector_exclusion_is_arithmetic_before_construction(self):
        data = document(); data['generation']['groups'][0]['minimum_count'] = 0
        data['generation']['max_candidates'] = 5
        data['evaluation']['max_total_trials'] = 18
        command = parse(json.dumps(data))
        self.assertEqual((command.generation_request.candidate_count, command.generation_request.planned_trials), (5, 18))
        output = json.loads(encode(command, make_result(command)))
        self.assertEqual([c['counts'] for c in output['candidates']], [[0, 1], [1, 0], [1, 1], [2, 0], [2, 1]])

    def test_reserve_error_has_balance_family_external_id_and_rebased_pointer(self):
        data = document(); data['reserve']['scenario']['actors'][0]['definition_id'] = 'unknown'
        error = self.invalid(data)
        self.assertEqual(error.path, '/reserve/scenario/actors/0/definition_id')
        self.assertEqual(error.request_id, data['request_id'])
        self.assertNotIsInstance(error, MagicSimulationInputError)

    def test_both_perspectives_and_wizard_sides_keep_wizard_outside_groups(self):
        for flip in (False, True):
            for perspective in ('players_and_allies', 'opposition'):
                data = document(); scene = data['reserve']['scenario']
                if flip:
                    opposite = {'players_and_allies': 'opposition', 'opposition': 'players_and_allies'}
                    for actor in scene['actors']: actor['side'] = opposite[actor['side']]
                    for placement in scene['placements']: placement['side_id'] = opposite[placement['side_id']]
                    for frame in scene['scene_frames']:
                        for placement in frame['key']['placements']: placement['side_id'] = opposite[placement['side_id']]
                scene['perspective_side'] = perspective
                scene['objective_target_ids'] = [a['id'] for a in scene['actors'] if a['side'] != perspective]
                reserve = [a['id'] for a in scene['actors'] if a['side'] != perspective and a['id'] != 'wizard']
                if reserve == ['ally']:
                    data['generation']['groups'] = [{'group_id': 'allies', 'actor_ids': reserve,
                        'minimum_count': 0, 'maximum_count': 1}]
                data['generation']['scene_frames'] = deepcopy(scene['scene_frames'])
                with self.subTest(flip=flip, perspective=perspective):
                    command, output = self.assert_roundtrip(data)
                    self.assertNotIn('wizard', [a for g in command.generation_request.groups for a in g.actor_ids])
                    self.assertTrue(all(c.scenario.initial.wizard.actor_id == 'wizard'
                        for c in make_result(command).generation_result.evaluation_request.candidates))
                    self.assertEqual(output['request'], data)

    def test_independent_orders_archives_and_nullable_routes_roundtrip(self):
        data = document(); scene = data['reserve']['scenario']
        data['request_id'], scene['scenario_id'], scene['wizard']['day_id'] = ' внешний:🧙 ', ' сцена:1 ', ' день:1 '
        scene['definitions'].reverse(); scene['actors'].reverse(); scene['actor_policies'].reverse()
        scene['activation_order'].reverse(); scene['objective_target_ids'].reverse()
        scene['battlefield']['zone_ids'].reverse(); scene['battlefield']['connections'].reverse()
        for policy in scene['actor_policies']:
            policy['target_actor_ids'].reverse(); policy['defeat_decisions'].reverse(); policy['zone_priorities'].reverse()
        for frame in scene['scene_frames']:
            frame['key']['live_actor_ids'].reverse()
            frame['pair_ranges'].reverse(); frame['give_ground_plans'].reverse(); frame['attack_departures'].reverse()
            frame['zone_ranges'].reverse()
            for pair in frame['pair_ranges']:
                pair['first_actor_id'], pair['second_actor_id'] = pair['second_actor_id'], pair['first_actor_id']
                pair['first_range_approved_by_gm'], pair['second_range_approved_by_gm'] = (
                    pair['second_range_approved_by_gm'], pair['first_range_approved_by_gm'])
        archive = deepcopy(scene['scene_frames'][0]); archive['key']['live_actor_ids'] = []
        for key in ('pair_ranges', 'give_ground_plans', 'broken_plans', 'attack_departures'): archive[key] = []
        scene['scene_frames'].append(archive)
        data['generation']['scene_frames'] = deepcopy(scene['scene_frames'])
        data['generation']['groups'].reverse()
        data['generation']['groups'][1]['actor_ids'].reverse()
        command, output = self.assert_roundtrip(data)
        self.assertNotEqual(tuple(p.state.actor_id for p in command.generation_request.template_scenario.initial.roster.participants),
            tuple(p.entity_id for p in command.generation_request.template_scenario.initial.spatial_state.placements))
        self.assertEqual(output['request'], data)

    def test_full_source_preflight_does_not_claim_every_subset_is_admissible(self):
        data = generation_failure_document()
        with patch('towr.application.magic_candidate_generation._project_candidate', side_effect=AssertionError('projected')):
            command = parse(json.dumps(data))
        self.assertEqual((command.generation_request.candidate_count, command.generation_request.planned_trials), (4, 16))
        with self.assertRaises(MagicCandidateGenerationError) as caught:
            generate_magic_candidates(command.generation_request)
        self.assertEqual(caught.exception.counts, (1, 0))
        self.assertIsNotNone(caught.exception.__cause__)

    def test_models_are_typed_frozen_copy_order_and_pickle(self):
        command = parse(json.dumps(document())); result = make_result(command)
        order = list(command.definition_order)
        copied = replace(command, definition_order=order); order.clear()
        self.assertEqual(copied, command)
        self.assertEqual(pickle.loads(pickle.dumps(command)), command)
        self.assertEqual(pickle.loads(pickle.dumps(result)), result)
        for changes in ({'request_id': ''}, {'request_id': 1}, {'generation_request': None}, {'execution': None},
                {'definition_order': ()}, {'definition_order': command.definition_order * 2}, {'definition_order': ([],)}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(command, **changes)
        for value in ('abc', set(command.definition_order), iter(command.definition_order)):
            with self.assertRaises(TypeError): replace(command, definition_order=value)
        with self.assertRaises(FrozenInstanceError): result.evaluation_result = None
        self.assertFalse(hasattr(command, '__dict__'))
        for changes in ({'generation_result': None}, {'evaluation_result': None}):
            with self.assertRaises(TypeError): replace(result, **changes)
        for pair in ((None, result), (command, None), (command, result.generation_result)):
            with self.assertRaises(TypeError): encode(*pair)

    def test_result_binds_exact_generation_and_staged_source_chain(self):
        command = parse(json.dumps(document())); result = make_result(command)
        for change in (
                lambda d: d['evaluation'].update(master_seed='43'),
                lambda d: d['reserve']['scenario']['wizard'].update(day_id='other-day'),
                lambda d: d['reserve']['scenario']['wizard']['caster'].update(wizard_level=3),
                lambda d: d['reserve']['scenario']['actor_policies'][1]['willpower'].update(dice=4),
                lambda d: d['reserve']['scenario']['activation_order'].reverse(),
                lambda d: (d['reserve']['scenario']['scene_frames'][0]['attack_departures'][0].update(can_leave_zone=False),
                    d['generation'].update(scene_frames=deepcopy(d['reserve']['scenario']['scene_frames']))),
                lambda d: d['generation'].update(candidate_id_prefix='other')):
            data = document(); change(data)
            other = parse(json.dumps(data)); foreign = make_result(other)
            with self.subTest(change=change), self.assertRaises(ValueError): encode(command, foreign)
            with self.assertRaises(ValueError): replace(result, evaluation_result=foreign.evaluation_result)
        evaluation = result.evaluation_result
        for reports in ((), evaluation.stage_reports[:1], evaluation.stage_reports[::-1], evaluation.stage_reports * 2):
            with self.assertRaises(ValueError): replace(evaluation, stage_reports=reports)
        renamed = replace(command, request_id='other external ID')
        self.assertEqual(json.loads(encode(renamed, result))['request']['request_id'], renamed.request_id)

    def test_encoder_refuses_typed_source_not_representable_in_utf8(self):
        command = parse(json.dumps(document()))
        scene = replace(command.generation_request.template_scenario, id=chr(0xD800))
        source = replace(command.generation_request, template_scenario=scene)
        changed = replace(command, generation_request=source)
        with self.assertRaises(ValueError): encode(changed, make_result(changed))

    def test_complete_report_preserves_catalog_full_native_summary_and_fraction_rates(self):
        command = parse(json.dumps(document())); output = json.loads(encode(command, make_result(command)))
        self.assertEqual(output['request'], document())
        self.assertEqual((output['candidate_count'], output['planned_trials'], output['total_trials']), (4, 16, 16))
        self.assertEqual([c['counts'] for c in output['candidates']], [[1, 0], [1, 1], [2, 0], [2, 1]])
        first = output['stage_reports'][0]['candidates'][0]
        self.assertEqual(set(first['summary']), {'trials', 'outcome_counts', 'total_action_count',
            'total_started_round_count', 'total_completed_round_count'})
        self.assertEqual(set(first['rates']), {'objective_achieved', 'perspective_defeated', 'round_limit_reached', 'unsupported_path'})
        self.assertEqual(first['rates']['objective_achieved'], {'numerator': 1, 'denominator': 2})
        self.assertEqual(output['stage_reports'][-1]['continuation_candidate_ids'], [])
        self.assertEqual(output['selected_candidate_ids'], [output['candidates'][0]['candidate_id']])
        text = encode(command, make_result(command))
        for forbidden in ('"trial_index"', '"journal"', '"mean_action_count"', '"side_defeated"', '"round_limit"'):
            self.assertNotIn(forbidden, text)

    def test_catalog_comes_from_ordered_vectors_with_arbitrary_prefix(self):
        data = document(); data['generation']['candidate_id_prefix'] = 'counts:999,999/🧙'
        command, output = self.assert_roundtrip(data)
        self.assertEqual([c['counts'] for c in output['candidates']], [[1, 0], [1, 1], [2, 0], [2, 1]])
        self.assertTrue(all(c['candidate_id'].startswith(data['generation']['candidate_id_prefix']) for c in output['candidates']))
        self.assertEqual(len(make_result(command).generation_result.evaluation_request.candidates), 4)

    def test_outside_window_continues_without_local_selection(self):
        command = parse(json.dumps(document()))
        result = make_result(command, lambda i, p, n: (n, 0, 0, 0) if i == 0 else (n // 2, n - n // 2, 0, 0))
        output = json.loads(encode(command, result))
        self.assertEqual(output['stage_reports'][0]['selected_candidate_ids'], [])
        self.assertEqual(len(output['stage_reports'][0]['continuation_candidate_ids']), 2)
        self.assertEqual(len(output['selected_candidate_ids']), 1)

    def test_early_all_unsupported_and_final_all_unsupported_have_distinct_statuses(self):
        command = parse(json.dumps(document()))
        early = json.loads(encode(command, make_result(command, lambda i, p, n: (0, 0, 0, n))))
        self.assertEqual((early['status'], early['total_trials'], early['planned_trials']), ('no_eligible_candidates', 8, 16))
        self.assertEqual(early['selected_candidate_ids'], [])
        row = early['stage_reports'][0]['candidates'][0]
        self.assertIsNone(row['window_match']); self.assertEqual(row['status'], 'unsupported_observations')
        final = json.loads(encode(command, make_result(command,
            lambda i, p, n: (0, 0, 0, n) if i else (n // 2, n - n // 2, 0, 0))))
        self.assertEqual(final['status'], 'completed')
        self.assertEqual(final['selected_candidate_ids'], [])
        self.assertEqual(final['stage_reports'][-1]['continuation_candidate_ids'], [])

    def test_all_four_native_rates_use_full_n_including_unsupported(self):
        data = document(); data['evaluation']['stages'] = [{'trials_per_candidate': 8, 'keep': 2}]
        data['evaluation']['max_total_trials'] = 32
        command = parse(json.dumps(data))
        output = json.loads(encode(command, make_result(command, lambda i, p, n: (2, 2, 3, 1))))
        row = output['stage_reports'][0]['candidates'][0]
        self.assertEqual(row['rates']['round_limit_reached'], {'numerator': 3, 'denominator': 8})
        self.assertEqual(row['rates']['unsupported_path'], {'numerator': 1, 'denominator': 8})
        self.assertEqual(row['summary']['trials'], 8)
        self.assertEqual(output['status'], 'completed')
        self.assertEqual(output['stage_reports'][0]['continuation_candidate_ids'], [])

    def test_saved_result_projects_exact_native_aggregates_without_sampling(self):
        expected = json.loads((EXAMPLES / 'magic-balance-v1.result.json').read_text(encoding='utf-8'))
        command = parse(json.dumps(expected['request'])); generated = generate_magic_candidates(command.generation_request)
        source, candidates, reports = generated.evaluation_request, generated.evaluation_request.candidates, []
        for index, raw in enumerate(expected['stage_reports']):
            stage = source.stages[index]
            request = MagicBalanceEvaluationRequest(candidates, source.master_seed, stage.trials_per_candidate,
                len(candidates) * stage.trials_per_candidate, source.window, stage.keep)
            rows = []
            for item, simulation in zip(raw['candidates'], request.simulation_requests, strict=True):
                s = item['summary']
                summary = NpcMagicSimulationSummary(simulation, NpcMagicOutcomeCounts(**s['outcome_counts']),
                    s['total_action_count'], s['total_started_round_count'], s['total_completed_round_count'])
                rows.append(MagicBalanceCandidateResult(item['candidate_id'], MagicCandidateAssessment(simulation, summary, source.window)))
            report = MagicBalanceEvaluationResult(request, tuple(rows)); reports.append(report)
            kept = magic_continuation_candidate_ids(report)
            candidates = tuple(c for c in candidates if c.candidate_id in kept)
        result = MagicBalanceResult(generated, MagicStagedEvaluationResult(source, tuple(reports)))
        actual = json.loads(encode(command, result)); expected['runtime'] = actual['runtime']
        self.assertEqual(actual, expected)

    def test_result_schema_closes_every_object_and_checks_nullable_assessment_fields(self):
        command = parse(json.dumps(document())); original = json.loads(encode(command, make_result(command)))
        for path in (p for p in object_paths(original) if not p or p[0] != 'request'):
            for key in (None, *at(original, path)):
                data = deepcopy(original)
                if key is None: at(data, path)['extra'] = True
                else: del at(data, path)[key]
                with self.subTest(path=path, key=key), self.assertRaises(ValidationError): validate(data, 'result')
        data = deepcopy(original); data['stage_reports'][0]['candidates'][0]['window_match'] = None
        with self.assertRaises(ValidationError): validate(data, 'result')

    def test_error_schema_contexts_are_phase_specific_without_partial_reports(self):
        for code in ('invalid_json', 'unsupported_version', 'invalid_input', 'generation_failed', 'evaluation_failed'):
            original = {'schema_version': '1', 'kind': 'magic_balance_error', 'request_id': 'external',
                'error': {'code': code, 'path': None, 'message': 'failed', 'candidate_id': None, 'counts': None, 'stage_index': None}}
            if code == 'generation_failed': original['error'].update(path='/generation', candidate_id='candidate', counts=[1, 0])
            if code == 'evaluation_failed': original['error'].update(path='/evaluation', candidate_id='candidate', stage_index=1)
            validate(original, 'error')
            for path in object_paths(original):
                for key in (None, *at(original, path)):
                    data = deepcopy(original)
                    if key is None: at(data, path)['partial'] = []
                    else: del at(data, path)[key]
                    with self.assertRaises(ValidationError): validate(data, 'error')
            for field, value in (('path', '/bad~2'), ('stage_index', -1), ('counts', [-1]), ('code', 'execution_failed')):
                data = deepcopy(original); data['error'][field] = value
                with self.assertRaises(ValidationError): validate(data, 'error')
            if code in ('invalid_json', 'unsupported_version', 'invalid_input'):
                for field, value in (('candidate_id', 'c'), ('counts', [1]), ('stage_index', 0)):
                    data = deepcopy(original); data['error'][field] = value
                    with self.assertRaises(ValidationError): validate(data, 'error')

    def test_parse_encode_do_not_execute_generation_rng_runner_or_pool(self):
        data = document(); command = parse(json.dumps(data)); result = make_result(command)
        before = random.getstate()
        with ExitStack() as stack:
            for target in ('random.Random', 'concurrent.futures.ProcessPoolExecutor',
                    'towr.application.magic_candidate_generation.generate_magic_candidates',
                    'towr.application.magic_staged_evaluation_service.evaluate_magic_candidates_staged',
                    'towr.application.magic_evaluation_service.run_npc_magic_simulation',
                    'towr.application.magic_evaluation_service.run_npc_magic_simulation_parallel',
                    'towr.adapters.magic_simulation_json.parse_magic_simulation_request'):
                stack.enter_context(patch(target, side_effect=AssertionError(target)))
            self.assertEqual(parse(json.dumps(data)), command)
            self.assertEqual(json.loads(encode(command, result))['request'], data)
        self.assertEqual(random.getstate(), before)
