"""Pure magic balance v1–v5 admission/encoding, without simulation."""
from dataclasses import asdict, replace
from fractions import Fraction
from functools import partial
import json
import platform

from towr import __version__
from towr.adapters._json_common import build_value, parse_seed, read_request
from towr.adapters._magic_scenario_json import (
    facts_document, parse_facts, parse_scenario, parse_scene_frames, scenario_document, scene_frames_document,
    miscast_continuation_document, parse_miscast_continuation, parse_stationary_wound_continuation,
    parse_repeated_leg_spasm_continuation,
    parse_crushed_rib_continuation,
    validate_scenario_wire_permissions,
)
from towr.adapters.magic_json_errors import MagicBalanceInputError
from towr.adapters.magic_json_schema import validate_magic_balance_document
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.application.magic_balance_models import MagicBalanceCommand, MagicBalanceResult
from towr.application.magic_balance_errors import MagicBalanceGenerationError, MagicBalanceExecutionError
from towr.application.magic_candidate_generation import _count_vectors
from towr.application.magic_candidate_generation_models import (
    MagicCandidateGenerationRequest, MagicCompositionGroup, _validate_generation_source,
)
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.balance.magic_staged_evaluation import magic_continuation_candidate_ids
from towr.balance.magic_staged_evaluation_models import MagicBalanceStage
from towr.balance.ranged_assessment_models import ObjectiveRateWindow


def encode_magic_balance_error(
    error: MagicBalanceInputError | MagicBalanceGenerationError | MagicBalanceExecutionError,
) -> str:
    """Encode this family's failures without causes, notes or partial reports."""
    path = candidate_id = counts = stage_index = None
    if isinstance(error, MagicBalanceInputError):
        code, path, message = error.code.value, error.path, str(error)
    elif isinstance(error, MagicBalanceGenerationError):
        code, path, candidate_id = 'generation_failed', '/generation', error.candidate_id
        counts = list(error.counts) if error.counts is not None else None
        message = 'Magic balance candidate generation failed'
    elif isinstance(error, MagicBalanceExecutionError):
        code, path = 'evaluation_failed', '/evaluation'
        candidate_id, stage_index = error.candidate_id, error.stage_index
        message = 'Magic balance evaluation failed'
    else:
        raise TypeError('balance error encoding requires a magic balance input, generation or execution error')
    document = {'schema_version': error.schema_version, 'kind': 'magic_balance_error', 'request_id': error.request_id,
        'error': {'code': code, 'path': path, 'message': message, 'candidate_id': candidate_id,
            'counts': counts, 'stage_index': stage_index}}
    validate_magic_balance_document(document, 'error', schema_version=error.schema_version)
    # Malformed-input diagnostics can contain escaped lone Unicode surrogates.
    return json.dumps(document, ensure_ascii=True, indent=2, allow_nan=False) + '\n'


def parse_magic_balance_request(text: str | bytes) -> MagicBalanceCommand:
    """Read strict JSON, admit the full reserve, and preflight C/staged budget."""
    document = read_request(text, MagicBalanceInputError, validate_magic_balance_document,
                            magic_versions=('1', '2', '3', '4', '5'))
    try:
        return _parse_document(document)
    except MagicBalanceInputError as error:
        error.request_id = document['request_id']
        error.schema_version = document['schema_version']
        raise


def _parse_document(document: dict) -> MagicBalanceCommand:
    build = partial(build_value, MagicBalanceInputError)
    reserve, generation, evaluation = document['reserve'], document['generation'], document['evaluation']
    version = document['schema_version']
    scenario, definition_order = parse_scenario(reserve['scenario'], reserve['round_budget'],
        path_prefix='/reserve/scenario', error_type=MagicBalanceInputError, schema_version=version)
    continuation = None
    if version in ('2', '3', '4', '5'):
        continuation = parse_miscast_continuation(generation['miscast_continuation'],
            path_prefix='/generation/miscast_continuation', error_type=MagicBalanceInputError)
        if continuation != scenario.miscast_continuation:
            raise MagicBalanceInputError(Code.INVALID_INPUT,
                'family Miscast continuation must equal the full reserve policy',
                path='/generation/miscast_continuation')
    stationary = None
    if version in ('3', '4', '5'):
        stationary = parse_stationary_wound_continuation(generation['stationary_wound_continuation'],
            path_prefix='/generation/stationary_wound_continuation', error_type=MagicBalanceInputError)
        if stationary != scenario.stationary_wound_continuation:
            raise MagicBalanceInputError(Code.INVALID_INPUT,
                'family stationary Wound continuation must equal the full reserve policy',
                path='/generation/stationary_wound_continuation')
    repeated = None
    if version in ('4', '5'):
        repeated = parse_repeated_leg_spasm_continuation(generation['repeated_leg_spasm_continuation'],
            stationary=stationary, path_prefix='/generation/repeated_leg_spasm_continuation',
            error_type=MagicBalanceInputError)
        if repeated != scenario.repeated_leg_spasm_continuation:
            raise MagicBalanceInputError(Code.INVALID_INPUT,
                'family repeated Leg Spasm policy must match the template policy',
                path='/generation/repeated_leg_spasm_continuation')
    crushed_rib = None
    if version == '5':
        crushed_rib = parse_crushed_rib_continuation(generation['crushed_rib_continuation'],
            path_prefix='/generation/crushed_rib_continuation', error_type=MagicBalanceInputError)
        if crushed_rib != scenario.crushed_rib_continuation:
            raise MagicBalanceInputError(Code.INVALID_INPUT,
                'family Crushed Rib policy must match the template policy',
                path='/generation/crushed_rib_continuation')
    groups = tuple(build(f'/generation/groups/{i}', MagicCompositionGroup, **group)
                   for i, group in enumerate(generation['groups']))
    facts = build('/generation/facts', parse_facts, generation['facts'])
    frames = parse_scene_frames(generation['scene_frames'], path_prefix='/generation/scene_frames',
                                error_type=MagicBalanceInputError)
    if frames != scenario.scene_frames:
        raise MagicBalanceInputError(Code.INVALID_INPUT,
            'family scene frames must retain the exact ordered template frames', path='/generation/scene_frames')
    stages = tuple(build(f'/evaluation/stages/{i}', MagicBalanceStage, **stage)
                   for i, stage in enumerate(evaluation['stages']))
    seed = parse_seed(evaluation['master_seed'], MagicBalanceInputError, '/evaluation/master_seed')
    window = build('/evaluation/window', ObjectiveRateWindow, **{
        name: Fraction(value['numerator'], value['denominator']) for name, value in evaluation['window'].items()})
    request = build('', MagicCandidateGenerationRequest, scenario, groups, facts, frames,
        generation['candidate_id_prefix'], generation['max_candidates'], seed, stages,
        evaluation['max_total_trials'], window, miscast_continuation=continuation,
        stationary_wound_continuation=stationary, repeated_leg_spasm_continuation=repeated,
        crushed_rib_continuation=crushed_rib)
    execution = document['execution']
    options = build('/execution', SimulationExecutionOptions, SimulationExecutionMode(execution['mode']),
                    execution.get('workers'), execution.get('batch_size'))
    return build('', MagicBalanceCommand, document['request_id'], request, options, definition_order, version)


def _fraction_document(value: Fraction) -> dict:
    return {'numerator': value.numerator, 'denominator': value.denominator}


def _request_document(command: MagicBalanceCommand) -> dict:
    source = command.generation_request
    scenario = source.template_scenario
    execution = {'mode': command.execution.mode.value}
    if command.execution.mode is SimulationExecutionMode.PROCESS:
        execution.update(workers=command.execution.workers, batch_size=command.execution.batch_size)
    document = {'schema_version': command.schema_version, 'kind': 'npc_magic_balance', 'request_id': command.request_id,
        'ruleset': 'towr-pg1.4-gmg1.1',
        'reserve': {'round_budget': scenario.max_rounds, 'scenario': scenario_document(scenario,
            command.definition_order, schema_version=command.schema_version)},
        'generation': {'groups': [{'group_id': g.group_id, 'actor_ids': list(g.actor_ids),
            'minimum_count': g.minimum_count, 'maximum_count': g.maximum_count} for g in source.groups],
            'facts': facts_document(source.facts), 'scene_frames': scene_frames_document(source.scene_frames),
            'candidate_id_prefix': source.candidate_id_prefix, 'max_candidates': source.max_candidates},
        'evaluation': {'master_seed': str(source.master_seed), 'stages': [asdict(stage) for stage in source.stages],
            'max_total_trials': source.max_total_trials,
            'window': {name: _fraction_document(getattr(source.window, name)) for name in ('minimum', 'target', 'maximum')}},
        'execution': execution}
    if command.schema_version in ('2', '3', '4', '5'):
        document['generation']['miscast_continuation'] = miscast_continuation_document(source.miscast_continuation)
    if command.schema_version in ('3', '4', '5'):
        policy = source.stationary_wound_continuation
        document['generation']['stationary_wound_continuation'] = None if policy is None else policy.value
    if command.schema_version in ('4', '5'):
        policy = source.repeated_leg_spasm_continuation
        document['generation']['repeated_leg_spasm_continuation'] = None if policy is None else policy.value
    if command.schema_version == '5':
        policy = source.crushed_rib_continuation
        document['generation']['crushed_rib_continuation'] = None if policy is None else policy.value
    return document


def encode_magic_balance_result(command: MagicBalanceCommand, result: MagicBalanceResult) -> str:
    """Encode the exact completed source chain, retaining aggregate reports only."""
    if not isinstance(command, MagicBalanceCommand) or not isinstance(result, MagicBalanceResult):
        raise TypeError('balance encoding requires a typed magic command and result')
    source = command.generation_request
    _validate_generation_source(source)
    validate_scenario_wire_permissions(source.template_scenario, command.schema_version)
    replace(result)
    if result.generation_result.source_request != source:
        raise ValueError('balance result belongs to a different generation request')
    request_document = _request_document(command)
    if parse_magic_balance_request(json.dumps(request_document)) != command:
        raise ValueError('balance command cannot be represented losslessly by magic JSON')
    evaluation = result.evaluation_result
    catalog = [{'candidate_id': candidate.candidate_id, 'counts': list(counts)}
               for candidate, counts in zip(result.generation_result.evaluation_request.candidates,
                                            _count_vectors(source), strict=True)]
    reports = []
    for index, report in enumerate(evaluation.stage_reports):
        candidates = []
        for candidate in report.candidates:
            assessment, summary = candidate.assessment, candidate.assessment.summary
            candidates.append({'candidate_id': candidate.candidate_id,
                'summary': {'trials': summary.trials, 'outcome_counts': asdict(summary.outcome_counts),
                    'total_action_count': summary.total_action_count,
                    'total_started_round_count': summary.total_started_round_count,
                    'total_completed_round_count': summary.total_completed_round_count},
                'rates': {name: _fraction_document(getattr(assessment, attribute)) for name, attribute in (
                    ('objective_achieved', 'objective_achieved_rate'), ('perspective_defeated', 'perspective_defeated_rate'),
                    ('round_limit_reached', 'round_limit_rate'), ('unsupported_path', 'unsupported_path_rate'))},
                'status': assessment.status.value, 'window_match': assessment.window_match})
        reports.append({'stage_index': index, 'trials_per_candidate': report.source_request.trials_per_candidate,
            'keep': report.source_request.top_k, 'total_trials': report.total_trials, 'candidates': candidates,
            'selected_candidate_ids': list(report.selected_candidate_ids),
            'continuation_candidate_ids': list(magic_continuation_candidate_ids(report))
                if index + 1 < len(source.stages) else []})
    document = {'schema_version': command.schema_version, 'kind': 'npc_magic_balance_result', 'request': request_document,
        'seed_scheme': evaluation.seed_scheme,
        'runtime': {'package_version': __version__, 'python_implementation': platform.python_implementation(),
            'python_version': platform.python_version(), 'rng': 'random.Random'},
        'candidate_count': source.candidate_count, 'planned_trials': evaluation.planned_trials,
        'total_trials': evaluation.total_trials, 'candidates': catalog, 'stage_reports': reports,
        'status': evaluation.status.value, 'selected_candidate_ids': list(evaluation.selected_candidate_ids)}
    validate_magic_balance_document(document, 'result', schema_version=command.schema_version)
    return json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
