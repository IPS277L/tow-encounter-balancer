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
from towr.adapters.mixed_balance_json import parse_mixed_balance_request as parse, encode_mixed_balance_result as encode
from towr.adapters.mixed_json_errors import MixedBalanceInputError
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code, RangedInputError
from towr.adapters.mixed_json_errors import MixedSimulationInputError
from towr.adapters.mixed_json_schema import validate_mixed_balance_document as validate
from towr.adapters.mixed_simulation_json import parse_mixed_simulation_request
from towr.application.mixed_balance_models import MixedBalanceResult
from towr.application.mixed_candidate_generation import generate_mixed_candidates
from towr.balance.mixed_assessment_models import MixedCandidateAssessment
from towr.balance.mixed_evaluation_models import (
    MixedBalanceEvaluationRequest, MixedBalanceEvaluationResult, MixedBalanceCandidateResult,
)
from towr.balance.mixed_staged_evaluation import mixed_continuation_candidate_ids
from towr.balance.mixed_staged_evaluation_models import MixedStagedEvaluationResult
from towr.simulation.npc_mixed_models import NpcMixedOutcomeCounts
from towr.simulation.npc_mixed_summary_models import NpcMixedSimulationSummary


EXAMPLES = Path(__file__).resolve().parents[2] / "docs/examples/m7/json"


def document():
    return json.loads((EXAMPLES / "mixed-balance-v1.request.json").read_text(encoding="utf-8"))


def make_result(command, counts=None):
    """Explicit aggregate fixtures, no Monte Carlo assumptions or execution."""
    generated = generate_mixed_candidates(command.generation_request)
    source = generated.evaluation_request
    candidates = source.candidates
    reports = []
    for index, stage in enumerate(source.stages):
        n = stage.trials_per_candidate
        request = MixedBalanceEvaluationRequest(candidates, source.master_seed, n,
            len(candidates) * n, source.window, stage.keep)
        rows = []
        for position, (candidate, simulation) in enumerate(zip(candidates, request.simulation_requests)):
            outcomes = counts(index, position, n) if counts else (n // 2, n - n // 2, 0, 0)
            summary = NpcMixedSimulationSummary(simulation, NpcMixedOutcomeCounts(*outcomes),
                n, n * simulation.scenario.initial.max_rounds)
            rows.append(MixedBalanceCandidateResult(candidate.candidate_id,
                MixedCandidateAssessment(simulation, summary, source.window)))
        report = MixedBalanceEvaluationResult(request, tuple(rows))
        reports.append(report)
        kept = mixed_continuation_candidate_ids(report)
        candidates = tuple(c for c in candidates if c.candidate_id in kept)
        if not candidates:
            break
    return MixedBalanceResult(generated, MixedStagedEvaluationResult(source, tuple(reports)))


class M7MixedBalanceJsonTests(unittest.TestCase):
    def invalid(self, data, code=Code.INVALID_INPUT):
        with self.assertRaises(MixedBalanceInputError) as caught:
            parse(json.dumps(data))
        self.assertEqual(caught.exception.code, code)
        self.assertNotIsInstance(caught.exception, MixedSimulationInputError)
        self.assertNotIsInstance(caught.exception, RangedInputError)
        return caught.exception

    def test_all_packaged_schemas_and_contract_examples(self):
        for kind in ("request", "result", "error"):
            schema = json.loads(files("towr.adapters.schemas").joinpath(
                f"mixed-balance-{kind}-v1.schema.json").read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
        for file in EXAMPLES.glob("mixed-balance-*.json"):
            kind = "error" if "error" in file.name else "result" if "result" in file.name else "request"
            validate(json.loads(file.read_text(encoding="utf-8")), kind)
        with self.assertRaises(ValueError):
            validate({}, "unknown")

    def test_saved_aggregate_example_is_reproduced_by_encoder_from_typed_sources(self):
        expected = json.loads((EXAMPLES / 'mixed-balance-v1.result.json').read_text(encoding='utf-8'))
        command = parse(json.dumps(expected['request']))
        generated = generate_mixed_candidates(command.generation_request)
        source = generated.evaluation_request
        candidates = source.candidates
        reports = []
        for index, raw in enumerate(expected['stage_reports']):
            stage = source.stages[index]
            request = MixedBalanceEvaluationRequest(candidates, source.master_seed, stage.trials_per_candidate,
                len(candidates) * stage.trials_per_candidate, source.window, stage.keep)
            rows = []
            for item, simulation in zip(raw['candidates'], request.simulation_requests, strict=True):
                s = item['summary']
                summary = NpcMixedSimulationSummary(simulation, NpcMixedOutcomeCounts(**s['outcome_counts']),
                    s['total_attack_count'], s['total_visited_round_count'])
                rows.append(MixedBalanceCandidateResult(item['candidate_id'],
                    MixedCandidateAssessment(simulation, summary, source.window)))
            report = MixedBalanceEvaluationResult(request, tuple(rows))
            reports.append(report)
            kept = mixed_continuation_candidate_ids(report)
            candidates = tuple(c for c in candidates if c.candidate_id in kept)
        result = MixedBalanceResult(generated, MixedStagedEvaluationResult(source, tuple(reports)))
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
        self.assertEqual(source.candidate_count, 4)
        self.assertEqual(source.planned_trials, 16)
        self.assertEqual(source.window.target, Fraction(1, 2))
        self.assertEqual(source.facts, source.template_scenario.facts)
        self.assertIsNot(source.facts, source.template_scenario.facts)
        data["generation"]["groups"][0]["actor_ids"].clear()
        self.assertEqual(source.groups[0].actor_ids, ("E2", "E1"))
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
            with self.subTest(text=text), self.assertRaises(MixedBalanceInputError) as caught:
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
        for key, value in (("schema_version", 1), ("kind", "npc_mixed_simulation"),
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
            lambda d: d['generation']['groups'][0].update(actor_ids=['E2','P1']),
            lambda d: d['generation']['groups'][1].update(group_id='A'),
            lambda d: d['generation']['groups'][1].update(actor_ids=['E2']),
            lambda d: d['generation']['groups'].pop(),
            lambda d: d['generation'].update(max_candidates=3),
            lambda d: d['evaluation'].update(max_total_trials=15),
            lambda d: d['evaluation']['stages'][1].update(trials_per_candidate=2),
            lambda d: d['evaluation']['stages'][0].update(keep=0),
            lambda d: [g.update(minimum_count=0, maximum_count=0) for g in d['generation']['groups']],
        )
        with patch('towr.application.mixed_candidate_generation._project_candidate', side_effect=AssertionError('materialized')):
            for mutate in mutations:
                data = document(); mutate(data)
                self.invalid(data)
            data = document()
            scenario = data['reserve']['scenario']
            alternate = deepcopy(scenario['definitions'][1]); alternate['id'] = 'other'
            scenario['definitions'].append(alternate)
            scenario['actors'][3]['definition_id'] = 'other'
            self.invalid(data)  # Group A no longer has one exact definition.

    def test_reserve_errors_keep_balance_id_and_rebased_simulation_pointer(self):
        data = document()
        data['reserve']['scenario']['actors'][0]['definition_id'] = 'unknown'
        error = self.invalid(data)
        self.assertEqual(error.request_id, data['request_id'])
        self.assertEqual(error.path, '/reserve/scenario/actors/0/definition_id')
        simulation_document = dict(schema_version='1', kind='npc_mixed_simulation', ruleset=data['ruleset'],
            request_id=data['reserve']['initial_request_id'], scenario=data['reserve']['scenario'],
            execution=data['execution'], simulation=dict(master_seed='42', trials=8, round_budget=3))
        with self.assertRaises(MixedSimulationInputError) as caught:
            parse_mixed_simulation_request(json.dumps(simulation_document))
        self.assertEqual(caught.exception.path, '/scenario/actors/0/definition_id')
        self.assertEqual(str(caught.exception), str(error))
        self.assertEqual(caught.exception.request_id, simulation_document['request_id'])

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
        self.assertEqual(actual['candidate_count'], 4)
        self.assertEqual([c['counts'] for c in actual['candidates']], [[1,0],[1,1],[2,0],[2,1]])
        self.assertEqual(actual['planned_trials'], 16)
        self.assertEqual(actual['total_trials'], 16)
        self.assertEqual(actual['selected_candidate_ids'], ['mixed:counts:1,0'])
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
        self.assertEqual(len(first['continuation_candidate_ids']), 2)
        self.assertEqual(len(actual['selected_candidate_ids']), 1)

    def test_all_four_outcomes_early_stop_and_final_unsupported(self):
        data = document()
        data['evaluation']['stages'] = [dict(trials_per_candidate=8, keep=3), dict(trials_per_candidate=32, keep=2)]
        data['evaluation']['max_total_trials'] = 128
        command = parse(json.dumps(data))
        actual = json.loads(encode(command, make_result(command, lambda i,p,n: (2,2,3,n-7))))
        self.assertEqual(actual['status'], 'no_eligible_candidates')
        self.assertEqual(actual['total_trials'], 32)
        self.assertEqual(actual['planned_trials'], 128)
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
        data['evaluation']['max_total_trials'] = 32
        command = parse(json.dumps(data))
        actual = json.loads(encode(command, make_result(command)))
        self.assertEqual(actual['planned_trials'], 32)
        self.assertEqual(len(actual['selected_candidate_ids']), 4)
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
        for code in ('invalid_json', 'unsupported_version', 'invalid_input', 'generation_failed', 'execution_failed'):
            original = {'schema_version': '1', 'kind': 'mixed_balance_error', 'request_id': 'outer',
                'error': {'code': code, 'path': None, 'message': 'failed', 'candidate_id': None,
                          'counts': None, 'stage_index': None}}
            if code == 'generation_failed':
                original['error'].update(candidate_id='candidate', counts=[0,1])
            if code == 'execution_failed':
                original['error'].update(candidate_id='candidate', stage_index=1)
            validate(original, 'error')
            for path in object_paths(original):
                data = deepcopy(original); at(data, path)['partial'] = []
                with self.assertRaises(ValidationError): validate(data, 'error')
                for key in at(original, path):
                    data = deepcopy(original); del at(data, path)[key]
                    with self.assertRaises(ValidationError): validate(data, 'error')
            for key, value in (('path','/bad~2'),('path','\n'),('stage_index',-1),('counts',[-1]),('code','io_failed')):
                data = deepcopy(original); data['error'][key] = value
                with self.assertRaises(ValidationError): validate(data, 'error')
            if code.startswith('invalid') or code == 'unsupported_version':
                for key,value in (('candidate_id','candidate'),('stage_index',0),('counts',[1])):
                    data = deepcopy(original); data['error'][key] = value
                    with self.assertRaises(ValidationError): validate(data, 'error')

    def test_parse_encode_have_no_generation_rng_runner_or_pool_side_effects(self):
        data = document(); command = parse(json.dumps(data)); result = make_result(command)
        with ExitStack() as stack:
            for target in ('random.Random', 'concurrent.futures.ProcessPoolExecutor',
                           'towr.adapters.mixed_simulation_json.parse_mixed_simulation_request',
                           'towr.adapters.ranged_balance_json.parse_ranged_balance_request',
                           'towr.application.mixed_candidate_generation.generate_mixed_candidates',
                           'towr.application.mixed_candidate_generation._project_candidate',
                           'towr.application.mixed_staged_evaluation_service.evaluate_mixed_candidates_staged',
                           'towr.application.mixed_evaluation_service.run_npc_mixed_simulation',
                           'towr.application.mixed_evaluation_service.run_npc_mixed_simulation_parallel'):
                stack.enter_context(patch(target, side_effect=AssertionError(target)))
            self.assertEqual(parse(json.dumps(data)), command)
            self.assertEqual(json.loads(encode(command, result))['request'], data)

    def test_actor_escape_is_explicit_and_preserved_in_every_projection(self):
        data = document()
        command = parse(json.dumps(data))
        result = make_result(command)
        for candidate in result.generation_result.evaluation_request.candidates:
            self.assertTrue(candidate.scenario.policy_for('P2').can_leave_zone)
            self.assertFalse(candidate.scenario.policy_for('P1').can_leave_zone)
        self.assertEqual(json.loads(encode(command, result))['request'], data)
        for root in (('generation',), ('reserve', 'scenario')):
            data = document(); at(data, root)['facts']['can_leave_zone'] = False
            self.invalid(data)

    def test_mixed_facts_ordinary_side_order_and_gm_flags_are_not_inferred(self):
        for root in (('generation',), ('reserve', 'scenario')):
            for field in ('ammunition_sufficient', 'all_zone_combatants_included',
                          'unmounted_combatants_only', 'no_higher_ground', 'no_other_test_modifiers'):
                data = document()
                at(data, root)['facts'][field] = False
                error = self.invalid(data)
                self.assertEqual(error.path, '/' + '/'.join(root) + '/facts/' + field)
        for mutate in (
            lambda d: d['generation']['facts'].update(zone_id='exit'),
            lambda d: d['reserve']['scenario']['side_order'].reverse(),
            lambda d: d['reserve']['scenario']['actor_policies'][0]['targets'][0].update(gm_approved=False),
            lambda d: d['reserve']['scenario']['actor_policies'][0].update(outnumbering_bonus_approved=0),
        ):
            data = document(); mutate(data)
            self.assertEqual(self.invalid(data).request_id, data['request_id'])

    def test_explicit_false_gm_flag_hands_and_protection_survive_projection(self):
        from towr.domain.test_models import Skill
        from towr.domain.ranged_weapon_profiles import RangedWeaponHands
        data = document()
        definition = data['reserve']['scenario']['definitions'][1]
        definition['source_rule_id'] = 'caller:supplied-numeric-profile'
        definition['attack']['hands'] = '2h'
        definition['protection']['skill'] = 'athletics'
        command = parse(json.dumps(data))
        result = make_result(command)
        for candidate in result.generation_result.evaluation_request.candidates:
            self.assertFalse(candidate.scenario.policy_for('P2').outnumbering_bonus_approved)
            for participant in candidate.scenario.initial.current.state.roster.participants:
                self.assertIs(participant.definition.attacks[0].hands, RangedWeaponHands.TWO_HANDED)
                self.assertIs(participant.definition.protection[0].skill, Skill.ATHLETICS)
        self.assertEqual(json.loads(encode(command, result))['request'], data)

    def test_shared_class_identity_and_ranged_type_rejection(self):
        from towr.application.ranged_simulation_models import SimulationExecutionOptions
        from towr.balance.ranged_assessment_models import ObjectiveRateWindow
        from tests.unit.test_m5_ranged_balance_json import document as ranged_document, make_result as ranged_result
        from towr.adapters.ranged_balance_json import parse_ranged_balance_request
        command = parse(json.dumps(document()))
        result = make_result(command)
        ranged = parse_ranged_balance_request(json.dumps(ranged_document()))
        other = ranged_result(ranged)
        self.assertIs(type(command.execution), SimulationExecutionOptions)
        self.assertIs(type(command.generation_request.window), ObjectiveRateWindow)
        self.assertFalse(hasattr(command, '__dict__'))
        self.assertFalse(hasattr(result, '__dict__'))
        with self.assertRaises(TypeError): replace(command, generation_request=ranged.generation_request)
        for changes in ({'generation_result': other.generation_result}, {'evaluation_result': other.evaluation_result}):
            with self.assertRaises(TypeError): replace(result, **changes)
        with self.assertRaises(TypeError): encode(ranged, result)
        with self.assertRaises(TypeError): encode(command, other)
        self.invalid(ranged_document())

    def test_large_stage_counts_and_budgets_keep_exact_integer_precision(self):
        data = document()
        n = 2**64 - 1
        data['evaluation']['stages'] = [dict(trials_per_candidate=n, keep=5)]
        data['evaluation']['max_total_trials'] = 4*n
        with patch('towr.application.mixed_candidate_generation._project_candidate', side_effect=AssertionError('materialized')):
            command = parse(json.dumps(data))
        result = make_result(command)
        encoded = json.loads(encode(command, result))
        self.assertEqual(encoded['planned_trials'], 4*n)
        self.assertEqual(encoded['total_trials'], 4*n)
        self.assertEqual(encoded['stage_reports'][0]['candidates'][0]['summary']['trials'], n)
        self.assertEqual(encoded['request'], data)
        for value in (0, 2**64, True):
            data['evaluation']['stages'][0]['trials_per_candidate'] = value
            self.invalid(data)

    def test_source_guards_include_facts_policy_and_window_not_only_ids(self):
        command = parse(json.dumps(document()))
        source = command.generation_request
        scenario = source.template_scenario
        policies = tuple(replace(p, outnumbering_bonus_approved=True) if p.actor_id == 'P2' else p
                         for p in scenario.actor_policies)
        for changed in (
            replace(source, template_scenario=replace(scenario, actor_policies=tuple(
                replace(p, can_leave_zone=False) if p.actor_id == 'P2' else p for p in scenario.actor_policies))),
            replace(source, template_scenario=replace(scenario, actor_policies=policies)),
            replace(source, window=replace(source.window, target=Fraction(1, 3))),
        ):
            with self.subTest(source=changed):
                foreign = make_result(replace(command, generation_request=changed))
                with self.assertRaisesRegex(ValueError, 'different generation'):
                    encode(command, foreign)
                with self.assertRaisesRegex(ValueError, 'exact generated'):
                    replace(make_result(command), evaluation_result=foreign.evaluation_result)

    def test_external_id_and_candidate_prefix_are_labels_not_parsed_counts(self):
        data = document()
        data['generation']['candidate_id_prefix'] = 'name:counts:999,3/⚔'
        command = parse(json.dumps(data))
        result = make_result(command)
        renamed = replace(command, request_id='outer:renamed')
        actual = json.loads(encode(renamed, result))
        self.assertEqual(actual['request']['request_id'], 'outer:renamed')
        self.assertEqual(actual['request']['reserve']['initial_request_id'], data['reserve']['initial_request_id'])
        self.assertEqual([c['counts'] for c in actual['candidates']], [[1,0],[1,1],[2,0],[2,1]])
        self.assertTrue(all(c['candidate_id'].startswith(data['generation']['candidate_id_prefix']) for c in actual['candidates']))

    def test_low_level_combat_order_cannot_be_silently_normalized(self):
        command = parse(json.dumps(document()))
        scenario = command.generation_request.template_scenario
        current = scenario.initial.current
        reordered = replace(current.round_state, participants=current.round_state.participants[::-1])
        changed = replace(scenario, initial=replace(scenario.initial, current=replace(current, round_state=reordered)))
        command = replace(command, generation_request=replace(command.generation_request, template_scenario=changed))
        with self.assertRaisesRegex(ValueError, 'losslessly'):
            encode(command, make_result(command))

    def test_partial_candidate_rows_and_foreign_catalog_are_rejected(self):
        command = parse(json.dumps(document()))
        result = make_result(command)
        report = result.evaluation_result.stage_reports[0]
        with self.assertRaises(ValueError): replace(report, candidates=report.candidates[:-1])
        generated = result.generation_result
        source = generated.evaluation_request
        # A valid staged source with a smaller catalog still cannot be the generation result.
        foreign = replace(source, candidates=source.candidates[:-1])
        with self.assertRaises(ValueError): replace(generated, evaluation_request=foreign)

    def test_final_eligible_outside_window_is_complete_with_empty_selection(self):
        command = parse(json.dumps(document()))
        result = make_result(command, lambda i,p,n: (n,0,0,0))
        actual = json.loads(encode(command, result))
        self.assertEqual(actual['status'], 'completed')
        self.assertEqual(actual['selected_candidate_ids'], [])
        self.assertEqual(actual['total_trials'], actual['planned_trials'])
        self.assertEqual(actual['stage_reports'][-1]['continuation_candidate_ids'], [])
        self.assertTrue(all(row['status'] == 'eligible' and row['window_match'] is False
                            for row in actual['stage_reports'][-1]['candidates']))

    def test_family_pairs_are_separate_exact_ordered_assertions(self):
        data = document()
        command = parse(json.dumps(data))
        source = command.generation_request
        self.assertEqual(source.pair_ranges, source.template_scenario.pair_ranges)
        self.assertIsNot(source.pair_ranges, source.template_scenario.pair_ranges)
        self.assertIsNot(source.pair_ranges[0], source.template_scenario.pair_ranges[0])
        for variant in ('missing', 'duplicate', 'reordered', 'reversed', 'distance', 'foreign'):
            data = document()
            pairs = data['generation']['pair_ranges']
            if variant == 'missing': pairs.pop()
            elif variant == 'duplicate': pairs.append(deepcopy(pairs[0]))
            elif variant == 'reordered': pairs.reverse()
            elif variant == 'reversed':
                p = pairs[0]
                p['first_actor_id'], p['second_actor_id'] = p['second_actor_id'], p['first_actor_id']
            elif variant == 'distance': pairs[0]['target_range'] = 'close'
            else: pairs[0]['first_actor_id'] = 'unknown'
            with self.subTest(variant=variant):
                error = self.invalid(data)
                self.assertEqual(error.path, '/generation/pair_ranges')
                self.assertEqual(error.request_id, data['request_id'])
        data = document()
        data['generation']['pair_ranges'][0]['first_actor_id'] = data['generation']['pair_ranges'][0]['second_actor_id']
        self.assertEqual(self.invalid(data).path, '/generation/pair_ranges/0')

    def test_arithmetic_admission_does_not_silently_drop_invalid_subsets(self):
        from towr.application.mixed_candidate_generation_errors import MixedCandidateGenerationError
        data = document()
        data['generation']['groups'][0]['minimum_count'] = 0
        data['generation']['max_candidates'] = 5
        data['evaluation']['max_total_trials'] = 18
        with patch('towr.application.mixed_candidate_generation._count_vectors', side_effect=AssertionError('enumerated')), \
                patch('towr.application.mixed_candidate_generation._project_candidate', side_effect=AssertionError('materialized')):
            command = parse(json.dumps(data))
        self.assertEqual(command.generation_request.candidate_count, 5)
        self.assertEqual(command.generation_request.planned_trials, 18)
        with self.assertRaises(MixedCandidateGenerationError) as caught:
            generate_mixed_candidates(command.generation_request)
        self.assertEqual(caught.exception.counts, (0, 1))
        self.assertIsInstance(caught.exception.__cause__, ValueError)

    def test_exact_source_chain_includes_order_and_orientation_of_pairs(self):
        command = parse(json.dumps(document()))
        source = command.generation_request
        original = make_result(command)
        p = source.pair_ranges[0]
        for pairs in (source.pair_ranges[::-1],
                      (replace(p, first_actor_id=p.second_actor_id, second_actor_id=p.first_actor_id), *source.pair_ranges[1:])):
            scenario = replace(source.template_scenario, pair_ranges=pairs)
            changed = replace(source, template_scenario=scenario, pair_ranges=pairs)
            foreign_command = replace(command, generation_request=changed)
            foreign = make_result(foreign_command)
            with self.assertRaisesRegex(ValueError, 'different generation'):
                encode(command, foreign)
            with self.assertRaisesRegex(ValueError, 'exact generated'):
                replace(original, evaluation_result=foreign.evaluation_result)
            wire = json.loads(encode(foreign_command, foreign))
            self.assertEqual(wire['request']['generation']['pair_ranges'], wire['request']['reserve']['scenario']['pair_ranges'])
            self.assertEqual(parse(json.dumps(wire['request'])), foreign_command)

    def test_melee_family_and_unordered_definition_sequence_are_rejected(self):
        from tests.unit.test_m6_melee_balance_json import document as melee_document, make_result as melee_result
        from towr.adapters.melee_balance_json import parse_melee_balance_request
        from towr.adapters.melee_json_errors import MeleeInputError
        command = parse(json.dumps(document()))
        other = parse_melee_balance_request(json.dumps(melee_document()))
        other_result = melee_result(other)
        result = make_result(command)
        for order in ('ab', set(command.definition_order), iter(command.definition_order), None):
            with self.assertRaises(TypeError): replace(command, definition_order=order)
        with self.assertRaises(TypeError): replace(command, generation_request=other.generation_request)
        with self.assertRaises(TypeError): replace(result, generation_result=other_result.generation_result)
        with self.assertRaises(TypeError): replace(result, evaluation_result=other_result.evaluation_result)
        with self.assertRaises(TypeError): encode(other, result)
        self.assertNotIsInstance(self.invalid(melee_document()), MeleeInputError)
