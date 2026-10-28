"""Magic balance wire -> existing generator/stages -> aggregate wire, no new service."""
from copy import deepcopy
import json
from multiprocessing import active_children
import random
import unittest

from tests.unit.test_m8_magic_balance_json import document
from towr.adapters.magic_balance_json import parse_magic_balance_request as parse, encode_magic_balance_result as encode
from towr.adapters.magic_json_schema import validate_magic_balance_document
from towr.application.magic_balance_models import MagicBalanceResult
from towr.application.magic_candidate_generation import generate_magic_candidates
from towr.application.magic_staged_evaluation_service import evaluate_magic_candidates_staged


class M8MagicBalanceJsonIntegrationTests(unittest.TestCase):
    def compare_backends(self, original):
        outputs = []
        before_rng, children = random.getstate(), {c.pid for c in active_children()}
        before_raw = deepcopy(original)
        for execution in ({'mode': 'sequential'}, {'mode': 'process', 'workers': 2, 'batch_size': 3}):
            data = dict(original, execution=execution)
            command = parse(json.dumps(data).encode('utf-8'))
            before = deepcopy(command)
            generated = generate_magic_candidates(command.generation_request)
            result = MagicBalanceResult(generated,
                evaluate_magic_candidates_staged(generated.evaluation_request, command.execution))
            encoded = json.loads(encode(command, result))
            validate_magic_balance_document(encoded, 'result')
            self.assertEqual(encoded['request'], data)
            self.assertEqual(parse(json.dumps(encoded['request'])), command)
            self.assertEqual(encoded['total_trials'], result.evaluation_result.total_trials)
            self.assertLessEqual(encoded['total_trials'], command.generation_request.planned_trials)
            self.assertEqual(command, before)
            for report, typed in zip(encoded['stage_reports'], result.evaluation_result.stage_reports, strict=True):
                self.assertEqual(len(report['candidates']), len(typed.candidates))
                for row, typed_row in zip(report['candidates'], typed.candidates, strict=True):
                    native = typed_row.assessment.summary
                    for field in ('total_action_count', 'total_started_round_count', 'total_completed_round_count'):
                        self.assertEqual(row['summary'][field], getattr(native, field))
                    self.assertEqual(sum(row['summary']['outcome_counts'].values()), native.trials)
            encoded['request'].pop('execution')
            outputs.append((result.evaluation_result, encoded))
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(original, before_raw)
        self.assertEqual(random.getstate(), before_rng)
        self.assertEqual({c.pid for c in active_children()}, children)

    def test_documented_reserve_roundtrips_through_real_sequential_and_spawn(self):
        self.compare_backends(document())

    def test_distinct_definition_and_independent_orders_roundtrip_through_both_backends(self):
        data = document(); scenario = data['reserve']['scenario']
        alternate = deepcopy(scenario['definitions'][1]); alternate['id'] = 'another:bow'
        alternate['attacks'][0]['damage'] = 4
        scenario['definitions'].insert(0, alternate)
        scenario['actors'][-1]['definition_id'] = alternate['id']
        scenario['activation_order'].reverse(); scenario['objective_target_ids'].reverse()
        scenario['placements'].reverse()
        for policy in scenario['actor_policies']:
            policy['target_actor_ids'].reverse(); policy['defeat_decisions'].reverse()
        for frame in scenario['scene_frames']:
            frame['key']['placements'].reverse(); frame['pair_ranges'].reverse()
            for pair in frame['pair_ranges']:
                pair['first_actor_id'], pair['second_actor_id'] = pair['second_actor_id'], pair['first_actor_id']
                pair['first_range_approved_by_gm'], pair['second_range_approved_by_gm'] = (
                    pair['second_range_approved_by_gm'], pair['first_range_approved_by_gm'])
        data['generation']['scene_frames'] = deepcopy(scenario['scene_frames'])
        data['generation']['groups'].reverse(); data['generation']['groups'][1]['actor_ids'].reverse()
        self.compare_backends(data)
