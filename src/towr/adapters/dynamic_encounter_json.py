"""Current dynamic generation JSON1, without a supplied enemy reserve."""
from dataclasses import asdict, dataclass
from fractions import Fraction
from functools import lru_cache
from importlib.resources import files
import json

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from towr.adapters._json_common import build_value, parse_seed, read_request
from towr.adapters._pc_melee_scenario_json import _parse_participant, parse_facts, scenario_document
from towr.adapters.ranged_json_errors import RangedInputError, RangedInputErrorCode as Code
from towr.application.dynamic_encounter import (
    DynamicEncounterRequest, DynamicEncounterResult, NpcSearchSpace,
    search_dynamic_encounter, validate_dynamic_encounter_result,
)
from towr.domain.generated_npc_models import GeneratedAbility, GeneratedWeapon
from towr.domain.minion_defeat_models import NpcDefeatDisposition


class DynamicEncounterInputError(RangedInputError):
    pass


class DynamicEncounterExecutionError(RuntimeError):
    def __init__(self, request_id):
        super().__init__('dynamic encounter search failed')
        self.request_id = request_id


@lru_cache(maxsize=3)
def _validator(kind):
    if kind not in ('request', 'result', 'error'):
        raise ValueError('unknown dynamic schema kind')
    names = ['dynamic-encounter-common.schema.json', 'pc-melee-common.schema.json',
        'pc-melee-simulation-request-v1.schema.json'] + [
        f'dynamic-encounter-{k}-v1.schema.json' for k in ('request', 'result', 'error')]
    docs = {name: json.loads(files('towr.adapters.schemas').joinpath(name).read_text(encoding='utf-8')) for name in names}
    registry = Registry().with_resources((d['$id'], Resource.from_contents(d)) for d in docs.values())
    for document in docs.values():
        Draft202012Validator.check_schema(document)
    return Draft202012Validator(docs[f'dynamic-encounter-{kind}-v1.schema.json'], registry=registry)


def validate_dynamic_encounter_document(document, kind='request'):
    _validator(kind).validate(document)


@dataclass(frozen=True, slots=True)
class DynamicEncounterCommand:
    request_id: str
    request: DynamicEncounterRequest
    source_json: str


def _target(data, path, *, minimum=0, maximum=1):
    value = Fraction(data['numerator'], data['denominator'])
    if (value.numerator, value.denominator) != (data['numerator'], data['denominator']):
        raise DynamicEncounterInputError(Code.INVALID_INPUT, 'fraction must be reduced', path=path)
    if not minimum <= value <= maximum:
        raise DynamicEncounterInputError(Code.INVALID_INPUT, 'target is outside encounter bounds', path=path)
    return float(value)


def parse_dynamic_encounter_request(text: str | bytes) -> DynamicEncounterCommand:
    document = read_request(text, DynamicEncounterInputError, validate_dynamic_encounter_document)
    try:
        disposition = NpcDefeatDisposition(document['defeat_disposition'])
        party = []
        # PcMeleeParticipant describes concrete targets; the new wire party does
        # not. Bridge to the first generated slot, then scenario() binds all slots.
        for index, raw in enumerate(document['party']):
            concrete = dict(raw, target_priority=['generated-npc:1'], defeat_decisions=[dict(
                attacker_id=raw['actor_id'], target_id='generated-npc:1', disposition=disposition.value, gm_approved=True)])
            party.append(_parse_participant(concrete, path_prefix=f'/party/{index}', error_type=DynamicEncounterInputError))
        options = document['search_space']
        space = build_value(DynamicEncounterInputError, '/search_space', NpcSearchSpace,
            **{name: (tuple(GeneratedWeapon(v) for v in values) if name == 'weapon' else
                tuple(tuple(GeneratedAbility(a) for a in group) for group in values) if name == 'abilities' else tuple(values))
                for name, values in options.items()})
        search = dict(document['search'])
        search['master_seed'] = parse_seed(search['master_seed'], DynamicEncounterInputError, '/search/master_seed')
        request = build_value(DynamicEncounterInputError, '/', DynamicEncounterRequest,
            party=tuple(party), facts=parse_facts(document['facts']), day_id=document['day_id'], space=space,
            minimum_npcs=document['npc_count']['minimum'], maximum_npcs=document['npc_count']['maximum'],
            target_win_rate=_target(document['targets']['win_rate'], '/targets/win_rate'),
            target_rounds=_target(document['targets']['started_rounds'], '/targets/started_rounds',
                minimum=1, maximum=document['max_rounds']),
            max_rounds=document['max_rounds'], defeat_disposition=disposition, **search)
        return DynamicEncounterCommand(document['request_id'], request, json.dumps(document, ensure_ascii=False, allow_nan=False))
    except DynamicEncounterInputError as error:
        error.request_id = document['request_id']
        raise
    except (ValueError, TypeError, OverflowError) as error:
        raise DynamicEncounterInputError(Code.INVALID_INPUT, str(error), path='/', request_id=document['request_id']) from error


def execute_dynamic_encounter(command: DynamicEncounterCommand) -> DynamicEncounterResult:
    try:
        return search_dynamic_encounter(command.request)
    except Exception as error:
        raise DynamicEncounterExecutionError(command.request_id) from error


def candidate_document(candidate):
    source = candidate.summary.source_request
    return dict(npcs=[asdict(n) for n in candidate.composition],
        win_rate=candidate.win_rate, win_interval_95=candidate.win_interval_95,
        mean_started_rounds=candidate.mean_started_rounds, rounds_interval_95=candidate.rounds_interval_95,
        outcomes=asdict(candidate.summary.outcome_counts), trials=candidate.summary.trials,
        replay=dict(schema_version='1', kind='pc_melee_simulation', request_id=source.scenario.id,
            ruleset='towr-pg1.4-gmg1.1', scenario=scenario_document(source.scenario),
            simulation=dict(master_seed=str(source.master_seed), trials=source.trials), execution=dict(mode='sequential')))


def encode_dynamic_encounter_result(command, result):
    if type(result) is not DynamicEncounterResult or result.source != command.request:
        raise ValueError('dynamic result belongs to another request')
    admitted = parse_dynamic_encounter_request(command.source_json)
    if admitted.request != command.request or admitted.request_id != command.request_id:
        raise ValueError('wire source differs from executable request')
    validate_dynamic_encounter_result(result)
    document = dict(schema_version='1', kind='dynamic_encounter_search_result', request_id=command.request_id,
        source_request=json.loads(command.source_json), explored=[candidate_document(c) for c in result.explored],
        validations=[candidate_document(c) for c in result.validations],
        selected=[c.summary.source_request.scenario.id for c in result.finalists], total_trials=result.total_trials,
        proposal_attempts=result.proposal_attempts, proposal_limit_reached=result.proposal_limit_reached)
    # JSON schema types are lists, never native tuples (intervals/abilities).
    document = json.loads(json.dumps(document, allow_nan=False))
    validate_dynamic_encounter_document(document, 'result')
    return json.dumps(document, ensure_ascii=False, allow_nan=False, indent=2) + '\n'


def encode_dynamic_encounter_error(error):
    code = error.code.value if isinstance(error, DynamicEncounterInputError) else 'execution_failed'
    document = dict(schema_version='1', kind='dynamic_encounter_search_error',
        request_id=error.request_id, error=dict(code=code, path=getattr(error, 'path', None), message=str(error)))
    validate_dynamic_encounter_document(document, 'error')
    return json.dumps(document, ensure_ascii=False, allow_nan=False) + '\n'
