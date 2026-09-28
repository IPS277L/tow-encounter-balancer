from contextlib import ExitStack
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
from importlib.resources import files
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator, ValidationError

from tests.unit.test_m4_ranged_json import at, object_paths
from towr.adapters.ranged_balance_json import parse_ranged_balance_request as parse, encode_ranged_balance_result as encode
from towr.adapters.ranged_balance_json_errors import RangedBalanceInputError
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code, RangedSimulationInputError
from towr.adapters.ranged_json_schema import validate_ranged_balance_document as validate
from towr.adapters.ranged_simulation_json import parse_ranged_simulation_request
from towr.application.ranged_balance_models import RangedBalanceResult
from towr.application.ranged_candidate_generation import generate_ranged_candidates
from towr.balance.ranged_assessment_models import RangedCandidateAssessment
from towr.balance.ranged_evaluation_models import (
    RangedBalanceEvaluationRequest, RangedBalanceEvaluationResult, RangedBalanceCandidateResult,
)
from towr.balance.ranged_staged_evaluation import ranged_continuation_candidate_ids
from towr.balance.ranged_staged_evaluation_models import RangedStagedEvaluationResult
from towr.simulation.npc_ranged_models import NpcRangedOutcomeCounts
from towr.simulation.npc_ranged_summary_models import NpcRangedSimulationSummary


EXAMPLES = Path(__file__).resolve().parents[2] / "docs/examples/m5/json"


def document():
    return json.loads((EXAMPLES / "balance-v1.request.json").read_text(encoding="utf-8"))


def make_result(command, counts=None):
    """Explicit aggregate fixtures, no Monte Carlo assumptions or execution."""
    generated = generate_ranged_candidates(command.generation_request)
    source = generated.evaluation_request
    candidates = source.candidates
    reports = []
    for index, stage in enumerate(source.stages):
        n = stage.trials_per_candidate
        request = RangedBalanceEvaluationRequest(candidates, source.master_seed, n,
            len(candidates) * n, source.window, stage.keep)
        rows = []
        for position, (candidate, simulation) in enumerate(zip(candidates, request.simulation_requests)):
            outcomes = counts(index, position, n) if counts else (n // 2, n - n // 2, 0, 0)
            summary = NpcRangedSimulationSummary(simulation, NpcRangedOutcomeCounts(*outcomes),
                n, n * simulation.scenario.initial.max_rounds)
            rows.append(RangedBalanceCandidateResult(candidate.candidate_id,
                RangedCandidateAssessment(simulation, summary, source.window)))
        report = RangedBalanceEvaluationResult(request, tuple(rows))
        reports.append(report)
        kept = ranged_continuation_candidate_ids(report)
        candidates = tuple(c for c in candidates if c.candidate_id in kept)
        if not candidates:
            break
    return RangedBalanceResult(generated, RangedStagedEvaluationResult(source, tuple(reports)))


class M5BalanceJsonTests(unittest.TestCase):
    def invalid(self, data, code=Code.INVALID_INPUT):
        with self.assertRaises(RangedBalanceInputError) as caught:
            parse(json.dumps(data))
        self.assertEqual(caught.exception.code, code)
        self.assertNotIsInstance(caught.exception, RangedSimulationInputError)
        return caught.exception

    def test_all_packaged_schemas_and_five_contract_examples(self):
        for kind in ("request", "result", "error"):
            schema = json.loads(files("towr.adapters.schemas").joinpath(
                f"ranged-balance-{kind}-v1.schema.json").read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
        for file in EXAMPLES.glob("*.json"):
            kind = "error" if "error" in file.name else "result" if "result" in file.name else "request"
            validate(json.loads(file.read_text(encoding="utf-8")), kind)
        with self.assertRaises(ValueError):
            validate({}, "unknown")

    def test_saved_aggregate_example_is_reproduced_by_encoder_from_typed_sources(self):
        expected = json.loads((EXAMPLES / 'balance-v1.result.json').read_text(encoding='utf-8'))
        command = parse(json.dumps(expected['request']))
        generated = generate_ranged_candidates(command.generation_request)
        source = generated.evaluation_request
        candidates = source.candidates
        reports = []
        for index, raw in enumerate(expected['stage_reports']):
            stage = source.stages[index]
            request = RangedBalanceEvaluationRequest(candidates, source.master_seed, stage.trials_per_candidate,
                len(candidates) * stage.trials_per_candidate, source.window, stage.keep)
            rows = []
            for item, simulation in zip(raw['candidates'], request.simulation_requests, strict=True):
                s = item['summary']
                summary = NpcRangedSimulationSummary(simulation, NpcRangedOutcomeCounts(**s['outcome_counts']),
                    s['total_attack_count'], s['total_visited_round_count'])
                rows.append(RangedBalanceCandidateResult(item['candidate_id'],
                    RangedCandidateAssessment(simulation, summary, source.window)))
            report = RangedBalanceEvaluationResult(request, tuple(rows))
            reports.append(report)
            kept = ranged_continuation_candidate_ids(report)
            candidates = tuple(c for c in candidates if c.candidate_id in kept)
        result = RangedBalanceResult(generated, RangedStagedEvaluationResult(source, tuple(reports)))
        actual = json.loads(encode(command, result))
        # Saved observations are explicit deterministic fixtures; no runner is invoked.
        expected['runtime'] = actual['runtime']
        self.assertEqual(actual, expected)

    def test_request_maps_to_frozen_source_with_separate_ids_and_facts(self):
        data = document()
        command = parse(json.dumps(data).encode("utf-8"))
        source = command.generation_request
        self.assertEqual(command.request_id, data["request_id"])
        self.assertEqual(source.template_scenario.initial.current.id, data["reserve"]["initial_request_id"])
        self.assertNotEqual(command.request_id, source.template_scenario.initial.current.id)
        self.assertEqual(source.candidate_count, 5)
        self.assertEqual(source.planned_trials, 136)
        self.assertEqual(source.window.target, Fraction(1, 2))
        self.assertEqual(source.facts, source.template_scenario.facts)
        self.assertIsNot(source.facts, source.template_scenario.facts)
        data["generation"]["groups"][0]["actor_ids"].clear()
        self.assertEqual(source.groups[0].actor_ids, ("A1", "A2"))
        with self.assertRaises(FrozenInstanceError):
            command.request_id = "other"

    def test_unknown_and_missing_fields_on_every_request_object(self):
        original = document()
        for path in object_paths(original):
            data = deepcopy(original)
            at(data, path)["unexpected"] = 1
            with self.subTest(path=path, variant="unknown"):
                self.invalid(data)
            for key in at(original, path):
                data = deepcopy(original)
                del at(data, path)[key]
                with self.subTest(path=path, key=key):
                    self.invalid(data)

    def test_strict_json_tokens_duplicates_unicode_and_nonobjects(self):
        raw = json.dumps(document())
        for text, code in (
            (b"\xff", Code.INVALID_JSON), ("{", Code.INVALID_JSON),
            ('{"a":NaN}', Code.INVALID_JSON), ('{"a":Infinity}', Code.INVALID_JSON),
            ('{"a":1e0}', Code.INVALID_INPUT), ('{"a":1.0}', Code.INVALID_INPUT),
            ('{"a":{"b":1,"b":2}}', Code.INVALID_JSON),
            (json.dumps({"a": chr(0xD800)}), Code.INVALID_JSON),
            (json.dumps({chr(0xD800): "a"}), Code.INVALID_JSON),
            (raw.replace('"denominator": 4', '"denominator": 4.0'), Code.INVALID_INPUT),
        ):
            with self.subTest(text=text), self.assertRaises(RangedBalanceInputError) as caught:
                parse(text)
            self.assertEqual(caught.exception.code, code)
        for data in ([], None, True, 1, "x"):
            self.invalid(data)
        with self.assertRaises(TypeError): parse({})
        data = document()
        data["request_id"] = "запрос/⚔"
        self.assertEqual(parse(json.dumps(data)).request_id, data["request_id"])

    def test_versions_kind_ruleset_and_request_context(self):
        data = document()
        data["schema_version"] = "2"
        error = self.invalid(data, Code.UNSUPPORTED_VERSION)
        self.assertEqual((error.path, error.request_id), ("/schema_version", data["request_id"]))
        for key, value in (("schema_version", 1), ("kind", "npc_ranged_simulation"),
                           ("ruleset", "other"), ("request_id", " ")):
            data = document(); data[key] = value
            error = self.invalid(data)
            self.assertEqual(error.request_id, None if key == "request_id" else data["request_id"])

    def test_decimal_seed_limits_and_exact_integer_controls(self):
        for value in ("0", str(2**64-1)):
            data = document(); data["evaluation"]["master_seed"] = value
            self.assertEqual(parse(json.dumps(data)).generation_request.master_seed, int(value))
        for value in (str(2**64), "01", "0x2a", "-1", "42\n", 42, True):
            data = document(); data["evaluation"]["master_seed"] = value
            self.invalid(data)
        for path, key in ((('generation',), 'max_candidates'), (('evaluation',), 'max_total_trials'),
                          (('evaluation', 'stages', 0), 'trials_per_candidate'),
                          (('evaluation', 'window', 'minimum'), 'numerator')):
            for value in (True, 1.0, "1", -1):
                data = document(); at(data, path)[key] = value
                with self.subTest(path=path, value=value): self.invalid(data)

    def test_fraction_normalization_and_invalid_windows(self):
        data = document()
        data["evaluation"]["window"]["minimum"] = {"numerator": 2, "denominator": 8}
        command = parse(json.dumps(data))
        encoded = json.loads(encode(command, make_result(command)))
        self.assertEqual(encoded["request"]["evaluation"]["window"]["minimum"], {"numerator": 1, "denominator": 4})
        self.assertEqual(parse(json.dumps(encoded["request"])), command)
        for value in ({"numerator": 1, "denominator": 0}, {"numerator": -1, "denominator": 2},
                      {"numerator": 3, "denominator": 2}, {"numerator": 2, "denominator": 3}, 0.25, "1/4"):
            data = document(); data["evaluation"]["window"]["minimum"] = value
            self.invalid(data)
        data = document()
        data["evaluation"]["window"] = {k: {"numerator": 0, "denominator": 7} for k in ('minimum','target','maximum')}
        self.assertEqual(parse(json.dumps(data)).generation_request.window.target, Fraction(0))

    def test_explicit_execution_options(self):
        data = document(); data["execution"] = {"mode": "process", "workers": 2, "batch_size": 4}
        command = parse(json.dumps(data))
        self.assertEqual(command.execution.workers, 2)
        for execution in ({"mode": "auto"}, {"mode": "sequential", "workers": 1},
                          {"mode": "process", "workers": 2}, {"mode": "process", "workers": 62, "batch_size": 1},
                          {"mode": "process", "workers": True, "batch_size": 1},
                          {"mode": "process", "workers": 2, "batch_size": 0}):
            data["execution"] = execution
            self.invalid(data)

    def test_family_facts_are_required_and_admitted_separately(self):
        data = document(); del data["generation"]["facts"]
        self.invalid(data)
        for field in ('targets_aware', 'stationary', 'clear_line_of_sight', 'no_additional_rules'):
            data = document(); data["generation"]["facts"][field] = False
            self.assertTrue(self.invalid(data).path.startswith('/generation/facts'))

    def test_groups_and_budget_fail_before_materialization_or_execution(self):
        mutations = (
            lambda d: d['generation']['groups'][0].update(maximum_count=3),
            lambda d: d['generation']['groups'][0].update(minimum_count=2, maximum_count=1),
            lambda d: d['generation']['groups'][0].update(actor_ids=['A1','P1']),
            lambda d: d['generation']['groups'][1].update(group_id='A'),
            lambda d: d['generation']['groups'][1].update(actor_ids=['A1']),
            lambda d: d['generation']['groups'].pop(),
            lambda d: d['generation'].update(max_candidates=4),
            lambda d: d['evaluation'].update(max_total_trials=135),
            lambda d: d['evaluation']['stages'][1].update(trials_per_candidate=8),
            lambda d: d['evaluation']['stages'][0].update(keep=0),
            lambda d: [g.update(minimum_count=0, maximum_count=0) for g in d['generation']['groups']],
        )
        with patch('towr.application.ranged_candidate_generation._project_candidate', side_effect=AssertionError('materialized')):
            for mutate in mutations:
                data = document(); mutate(data)
                self.invalid(data)
            data = document()
            scenario = data['reserve']['scenario']
            alternate = deepcopy(scenario['definitions'][0]); alternate['id'] = 'other'
            scenario['definitions'].append(alternate)
            scenario['actors'][2]['definition_id'] = 'other'
            self.invalid(data)  # Group A no longer has one exact definition.

    def test_reserve_errors_keep_balance_id_and_rebased_m4_pointer(self):
        data = document()
        data['reserve']['scenario']['actors'][0]['definition_id'] = 'unknown'
        error = self.invalid(data)
        self.assertEqual(error.request_id, data['request_id'])
        self.assertEqual(error.path, '/reserve/scenario/actors/0/definition_id')
        m4 = dict(schema_version='1', kind='npc_ranged_simulation', ruleset=data['ruleset'],
            request_id=data['reserve']['initial_request_id'], scenario=data['reserve']['scenario'],
            execution=data['execution'], simulation=dict(master_seed='42', trials=8, round_budget=3))
        with self.assertRaises(RangedSimulationInputError) as caught:
            parse_ranged_simulation_request(json.dumps(m4))
        self.assertEqual(caught.exception.path, '/scenario/actors/0/definition_id')
        self.assertEqual(str(caught.exception), str(error))
        self.assertEqual(caught.exception.request_id, m4['request_id'])

    def test_models_reject_untyped_foreign_sources_and_copy_orders(self):
        command = parse(json.dumps(document()))
        result = make_result(command)
        order = list(command.definition_order)
        copied = replace(command, definition_order=order); order.clear()
        self.assertEqual(copied, command)
        for changes in ({'request_id': ''}, {'generation_request': None}, {'execution': None},
                        {'definition_order': ()}, {'definition_order': command.definition_order * 2},
                        {'definition_order': ([],)}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(command, **changes)
        with self.assertRaises(FrozenInstanceError): result.evaluation_result = None
        for changes in ({'generation_result': None}, {'evaluation_result': None}):
            with self.assertRaises(TypeError): replace(result, **changes)
        foreign = make_result(replace(command, generation_request=replace(command.generation_request, master_seed=43)))
        with self.assertRaisesRegex(ValueError, 'exact generated'):
            replace(result, evaluation_result=foreign.evaluation_result)
        with self.assertRaisesRegex(ValueError, 'different generation'):
            encode(command, foreign)
        with self.assertRaises(TypeError): encode(command, None)
        with self.assertRaises(TypeError): encode(None, result)

    def test_encoder_rejects_unrepresentable_low_level_placement_order(self):
        command = parse(json.dumps(document()))
        scenario = command.generation_request.template_scenario
        spatial = scenario.initial.spatial_state
        scenario = replace(scenario, initial=replace(scenario.initial, spatial_state=replace(spatial, placements=spatial.placements[::-1])))
        command = replace(command, generation_request=replace(command.generation_request, template_scenario=scenario))
        with self.assertRaisesRegex(ValueError, 'losslessly'):
            encode(command, make_result(command))

    def test_complete_report_keeps_catalog_sources_exact_fractions_and_tie_order(self):
        command = parse(json.dumps(document())); before = deepcopy(command)
        result = make_result(command)
        text = encode(command, result); actual = json.loads(text)
        self.assertTrue(text.endswith('\n'))
        self.assertEqual(actual['request'], document())
        self.assertEqual(actual['candidate_count'], 5)
        self.assertEqual([c['counts'] for c in actual['candidates']], [[0,1],[1,0],[1,1],[2,0],[2,1]])
        self.assertEqual(actual['planned_trials'], 136)
        self.assertEqual(actual['total_trials'], 136)
        self.assertEqual(actual['selected_candidate_ids'], ['example:counts:0,1','example:counts:1,0'])
        self.assertEqual(actual['stage_reports'][1]['continuation_candidate_ids'], [])
        self.assertEqual(actual['stage_reports'][0]['candidates'][0]['rates']['objective_achieved'], {'numerator':1,'denominator':2})
        self.assertEqual(command, before)
        self.assertNotIn('seed_hex', text)
        self.assertNotIn('trial_index', text)
        self.assertNotIn('journal', text)

    def test_outside_window_continuation_is_not_local_selection(self):
        command = parse(json.dumps(document()))
        result = make_result(command, lambda index, pos, n: (n, 0, 0, 0) if index == 0 else (n//2,n//2,0,0))
        actual = json.loads(encode(command, result))
        first = actual['stage_reports'][0]
        self.assertEqual(first['selected_candidate_ids'], [])
        self.assertEqual(len(first['continuation_candidate_ids']), 3)
        self.assertEqual(len(actual['selected_candidate_ids']), 2)

    def test_all_four_outcomes_early_stop_and_final_unsupported(self):
        command = parse(json.dumps(document()))
        actual = json.loads(encode(command, make_result(command, lambda i,p,n: (2,2,3,n-7))))
        self.assertEqual(actual['status'], 'no_eligible_candidates')
        self.assertEqual(actual['total_trials'], 40)
        self.assertEqual(actual['planned_trials'], 136)
        self.assertEqual(actual['selected_candidate_ids'], [])
        row = actual['stage_reports'][0]['candidates'][0]
        self.assertEqual(row['rates']['round_limit'], {'numerator':3,'denominator':8})
        self.assertEqual(row['status'], 'unsupported_observations')
        self.assertIsNone(row['window_match'])
        result = make_result(command, lambda i,p,n: (0,0,0,n) if i else (n//2,n//2,0,0))
        actual = json.loads(encode(command, result))
        self.assertEqual(actual['status'], 'completed')
        self.assertEqual(actual['selected_candidate_ids'], [])
        self.assertEqual(actual['stage_reports'][-1]['continuation_candidate_ids'], [])

    def test_one_stage_has_no_continuation_even_with_eligible_candidates(self):
        data = document(); data['evaluation']['stages'] = [dict(trials_per_candidate=8, keep=10)]
        command = parse(json.dumps(data))
        actual = json.loads(encode(command, make_result(command)))
        self.assertEqual(actual['planned_trials'], 40)
        self.assertEqual(len(actual['selected_candidate_ids']), 5)
        self.assertEqual(actual['stage_reports'][0]['continuation_candidate_ids'], [])

    def test_source_chain_rejects_missing_reordered_and_foreign_reports(self):
        command = parse(json.dumps(document())); result = make_result(command)
        evaluation = result.evaluation_result
        for reports in ((), evaluation.stage_reports[:1], evaluation.stage_reports[::-1], evaluation.stage_reports * 2):
            with self.assertRaises(ValueError): replace(evaluation, stage_reports=reports)
        foreign = make_result(replace(command, generation_request=replace(command.generation_request, master_seed=43)))
        with self.assertRaises(ValueError):
            replace(evaluation, stage_reports=foreign.evaluation_result.stage_reports)

    def test_result_schema_rejects_unknown_missing_and_wrong_nullable_fields(self):
        command = parse(json.dumps(document())); original = json.loads(encode(command, make_result(command)))
        # Request nesting is exhaustively covered by the strict-input test above.
        for path in (p for p in object_paths(original) if not p or p[0] != 'request'):
            data = deepcopy(original); at(data, path)['extra'] = 1
            with self.subTest(path=path), self.assertRaises(ValidationError): validate(data, 'result')
            for key in at(original, path):
                data = deepcopy(original); del at(data, path)[key]
                with self.subTest(path=path, key=key), self.assertRaises(ValidationError): validate(data, 'result')
        data = deepcopy(original); data['stage_reports'][0]['candidates'][0]['window_match'] = None
        with self.assertRaises(ValidationError): validate(data, 'result')

    def test_error_schema_contexts_and_no_partial_reports(self):
        for file in EXAMPLES.glob('*-error.json'):
            original = json.loads(file.read_text(encoding='utf-8'))
            for path in object_paths(original):
                data = deepcopy(original); at(data, path)['partial'] = []
                with self.assertRaises(ValidationError): validate(data, 'error')
                for key in at(original, path):
                    data = deepcopy(original); del at(data, path)[key]
                    with self.assertRaises(ValidationError): validate(data, 'error')
            for key, value in (('path','/bad~2'),('stage_index',-1),('counts',[-1]),('code','io_failed')):
                data = deepcopy(original); data['error'][key] = value
                with self.assertRaises(ValidationError): validate(data, 'error')
        data = json.loads((EXAMPLES/'balance-v1.input-error.json').read_text(encoding='utf-8'))
        data['error']['candidate_id'] = 'candidate'
        with self.assertRaises(ValidationError): validate(data, 'error')

    def test_parse_encode_have_no_generation_rng_runner_or_pool_side_effects(self):
        data = document(); command = parse(json.dumps(data)); result = make_result(command)
        with ExitStack() as stack:
            for target in ('random.Random', 'concurrent.futures.ProcessPoolExecutor',
                           'towr.application.ranged_candidate_generation.generate_ranged_candidates',
                           'towr.application.ranged_candidate_generation._project_candidate',
                           'towr.application.ranged_staged_evaluation_service.evaluate_ranged_candidates_staged',
                           'towr.application.ranged_evaluation_service.run_npc_ranged_simulation',
                           'towr.application.ranged_evaluation_service.run_npc_ranged_simulation_parallel'):
                stack.enter_context(patch(target, side_effect=AssertionError(target)))
            self.assertEqual(parse(json.dumps(data)), command)
            self.assertEqual(json.loads(encode(command, result))['request'], data)
