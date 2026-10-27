"""Pure magic simulation v1 parser/summary encoder (ADR-0043, first slice)."""
from dataclasses import asdict
import json
import platform

from towr import __version__
from towr.adapters._json_common import build_value, parse_seed, read_request
from towr.adapters._magic_scenario_json import parse_scenario, scenario_document
from towr.adapters.magic_json_errors import MagicSimulationInputError
from towr.adapters.magic_json_schema import validate_magic_simulation_document
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.application.magic_simulation_models import MagicSimulationCommand
from towr.application.magic_simulation_errors import MagicSimulationExecutionError
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest, SEED_SCHEME
from towr.simulation.npc_magic_summary_models import NpcMagicSimulationSummary


def encode_magic_simulation_error(
    error: MagicSimulationInputError | MagicSimulationExecutionError,
) -> str:
    """Encode this boundary's failures without causes, notes or partial results."""
    if isinstance(error, MagicSimulationInputError):
        code, path, message = error.code.value, error.path, str(error)
    elif isinstance(error, MagicSimulationExecutionError):
        code, path, message = 'simulation_failed', None, 'Magic simulation execution failed'
    else:
        raise TypeError('error encoding requires a magic simulation input or execution error')
    document = {'schema_version': '1', 'kind': 'magic_simulation_error', 'request_id': error.request_id,
        'error': {'code': code, 'path': path, 'message': message}}
    validate_magic_simulation_document(document, 'error')
    # Invalid input diagnostics can contain escaped lone Unicode surrogates.
    return json.dumps(document, ensure_ascii=True, indent=2, allow_nan=False) + '\n'


def parse_magic_simulation_request(text: str | bytes) -> MagicSimulationCommand:
    """Read strict UTF-8 JSON and admit the full fresh authored scenario."""
    document = read_request(text, MagicSimulationInputError, validate_magic_simulation_document)
    try:
        options = document['simulation']
        scenario, definitions = parse_scenario(document['scenario'], options['round_budget'],
            path_prefix='/scenario', error_type=MagicSimulationInputError)
        seed = parse_seed(options['master_seed'], MagicSimulationInputError, '/simulation/master_seed')
        request = build_value(MagicSimulationInputError, '/simulation', NpcMagicSimulationRequest,
                              scenario, seed, options['trials'])
        execution = document['execution']
        return MagicSimulationCommand(document['request_id'], request,
            SimulationExecutionOptions(SimulationExecutionMode(execution['mode']),
                execution.get('workers'), execution.get('batch_size')), definitions)
    except MagicSimulationInputError as error:
        error.request_id = document['request_id']
        raise
    except (TypeError, ValueError) as error:
        raise MagicSimulationInputError(Code.INVALID_INPUT, str(error),
            path='/scenario', request_id=document['request_id']) from error


def _request_document(command: MagicSimulationCommand) -> dict:
    scenario = command.request.scenario
    execution = {'mode': command.execution.mode.value}
    if command.execution.mode is SimulationExecutionMode.PROCESS:
        execution.update(workers=command.execution.workers, batch_size=command.execution.batch_size)
    return {'schema_version': '1', 'kind': 'npc_magic_simulation', 'request_id': command.request_id,
        'ruleset': 'towr-pg1.4-gmg1.1',
        'simulation': {'master_seed': str(command.request.master_seed), 'trials': command.request.trials,
            'round_budget': scenario.max_rounds}, 'execution': execution,
        'scenario': scenario_document(scenario, command.definition_order)}


def encode_magic_simulation_result(command: MagicSimulationCommand, summary: NpcMagicSimulationSummary) -> str:
    """Encode an aggregate with exact full source, without RNG/runner/pool calls."""
    if not isinstance(command, MagicSimulationCommand) or not isinstance(summary, NpcMagicSimulationSummary):
        raise TypeError('encoder requires a magic command and magic simulation summary')
    if summary.source_request != command.request:
        raise ValueError('summary belongs to a different full simulation request')
    request_document = _request_document(command)
    if parse_magic_simulation_request(json.dumps(request_document)) != command:
        raise ValueError('command cannot be represented losslessly by magic JSON v1')
    document = {'schema_version': '1', 'kind': 'npc_magic_simulation_result', 'request': request_document,
        'seed_scheme': SEED_SCHEME,
        'runtime': {'package_version': __version__, 'python_implementation': platform.python_implementation(),
            'python_version': platform.python_version(), 'rng': 'random.Random'},
        'summary': {'trials': summary.trials, 'outcome_counts': asdict(summary.outcome_counts),
            'total_action_count': summary.total_action_count,
            'total_started_round_count': summary.total_started_round_count,
            'total_completed_round_count': summary.total_completed_round_count}}
    validate_magic_simulation_document(document, 'result')
    return json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
