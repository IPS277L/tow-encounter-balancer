"""Current dynamic generation JSON1, without a supplied enemy reserve."""
from dataclasses import asdict, dataclass
from fractions import Fraction
from functools import lru_cache
from importlib.resources import files
import json

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from towr.adapters._json_common import build_value, parse_seed, read_request
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.ranged_json_errors import RangedInputError, RangedInputErrorCode as Code
from towr.application.dynamic_encounter import (
    DynamicEncounterRequest, DynamicEncounterResult, NpcSearchSpace,
    search_dynamic_encounter, validate_dynamic_encounter_result,
    DynamicEncounterCancelled, automatic_npc_search_space,
)
from towr.application.encounter_character import EncounterCharacter, EncounterTalent
from towr.application.encounter_inventory import (
    EncounterEquipment, WeaponItem, ArmourItem, ArmourItemKind, ItemLocation,
    ConsumableItem, ConsumableKind,
)
from towr.domain.generated_npc_models import GeneratedAbility, GeneratedWeapon, GeneratedTalent
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.pc_melee_models import (PcMeleeFacts,PcMeleeWeapon,PcRangedProfile,
    PcRangedReloadHandPolicy,PcRepeaterBonusPolicy)
from towr.domain.pc_magic_source_models import PcWizardProfile, PcSpellId
from towr.domain.pc_combat_talent_models import PcCombatTalent,TalentAcquisition


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


def pc_combat_talent_facts(raw, *, path_prefix='', error_type=DynamicEncounterInputError):
    """Validate acquisition facts even for an inventory draft; compile checks stats."""
    supported={'defensive_stance','wild_attack'}
    acquisition=raw.get('talent_acquisition',{})
    if (type(acquisition) is not dict or any(key not in supported or key not in raw['talents']
            or type(value) is not str or value not in ('earned','creation_free')
            for key,value in acquisition.items())):
        raise error_type(Code.INVALID_INPUT,'Talent acquisition must name a selected supported combat Talent.',
            path=path_prefix+'/talent_acquisition')
    return tuple(build_value(error_type,path_prefix+'/talent_acquisition/'+talent,PcCombatTalent,
        GeneratedTalent(talent),TalentAcquisition(acquisition.get(talent,'earned')))
        for talent in raw['talents'] if talent in supported)


def parse_dynamic_encounter_request(text: str | bytes) -> DynamicEncounterCommand:
    document = read_request(text, DynamicEncounterInputError, validate_dynamic_encounter_document)
    try:
        disposition = NpcDefeatDisposition(document['defeat_disposition'])
        party = []
        for index, raw in enumerate(document['party']):
            path = f'/party/{index}'
            gear = raw['equipment']
            equipment = build_value(DynamicEncounterInputError, path + '/equipment', EncounterEquipment,
                weapons=tuple(build_value(DynamicEncounterInputError, f'{path}/equipment/weapons/{i}', WeaponItem,
                    id=w['id'], weapon=PcMeleeWeapon(w['weapon']), location=ItemLocation(w['location']))
                    for i, w in enumerate(gear['weapons'])),
                armour=tuple(build_value(DynamicEncounterInputError, f'{path}/equipment/armour/{i}', ArmourItem,
                    id=a['id'], kind=ArmourItemKind(a['kind']), location=ItemLocation(a['location']))
                    for i, a in enumerate(gear['armour'])))
            consumables = tuple(build_value(DynamicEncounterInputError, f'{path}/consumables/{i}', ConsumableItem,
                id=c['id'], kind=ConsumableKind(c['kind']), quantity=c['quantity'], characteristic=c['characteristic'])
                for i, c in enumerate(raw['consumables']))
            ids = [item.id for item in (*equipment.weapons, *equipment.armour, *consumables)]
            if len(set(ids)) != len(ids):
                raise DynamicEncounterInputError(Code.INVALID_INPUT, 'Inventory instance IDs must be unique.', path=path)
            if any(item.kind is ConsumableKind.ENHANCEMENT and item.characteristic not in
                    ('weapon_skill','strength','toughness','agility') for item in consumables):
                raise DynamicEncounterInputError(Code.INVALID_INPUT,
                    'Усиление (Enhancement Potion) пока поддерживает WS, Strength, Toughness и Agility.',
                    path=path + '/consumables')
            unsupported = [talent for talent in raw['talents'] if talent not in {t.value for t in EncounterTalent}]
            if unsupported:
                raise DynamicEncounterInputError(Code.INVALID_INPUT,
                    'Таланты пока не поддержаны симуляцией: ' + ', '.join(unsupported), path=path + '/talents')
            loadout = build_value(DynamicEncounterInputError, path + '/equipment', equipment.combat_loadout,
                raw['characteristics']['strength'])
            wizard = None
            characteristics, skills = dict(raw['characteristics']), dict(raw['skills'])
            ranged=None
            if loadout['weapon'] in (PcMeleeWeapon.PISTOL,PcMeleeWeapon.REPEATER_PISTOL,
                    PcMeleeWeapon.REPEATER_HANDBOW):
                if 'ranged' not in raw:
                    raise DynamicEncounterInputError(Code.INVALID_INPUT,
                        'Для стрелкового оружия нужны факты подготовки (Ranged preparation).',path=path+'/ranged')
                prep=raw['ranged']
                required_stats={'ballistic_skill','initiative'}
                required_skills={'shooting','dexterity'}
                if not required_stats<=characteristics.keys() or not required_skills<=skills.keys():
                    raise DynamicEncounterInputError(Code.INVALID_INPUT,
                        'Для стрелка нужны BS/I/Shooting/Dexterity.',path=path)
                ranged=build_value(DynamicEncounterInputError,path+'/ranged',PcRangedProfile,
                    ballistic_skill=characteristics.pop('ballistic_skill'),initiative=characteristics.pop('initiative'),
                    shooting=skills.pop('shooting'),dexterity=skills.pop('dexterity'),
                    **prep,reload_hand_policy=PcRangedReloadHandPolicy.TWO_AVAILABLE_HANDS,
                    repeater_bonus_policy=(PcRepeaterBonusPolicy.AUTOMATIC
                        if loadout['weapon'] is not PcMeleeWeapon.PISTOL else None))
            elif 'ranged' in raw:
                raise DynamicEncounterInputError(Code.INVALID_INPUT,
                    'Стрелковая подготовка относится к начальному стрелковому оружию.',path=path+'/ranged')
            else:
                # Inactive character facts remain in the editable source echo
                # and individual character file; this loadout cannot use them.
                for name in ('ballistic_skill','initiative'):characteristics.pop(name,None)
                for name in ('shooting','dexterity'):skills.pop(name,None)
            if 'magic' in raw:
                magic = raw['magic']
                wizard = build_value(DynamicEncounterInputError, path + '/magic', PcWizardProfile,
                    **dict(magic, reason=characteristics.pop('reason'), willpower=skills.pop('willpower'),
                        lores=tuple(magic['lores']), memorised_spells=tuple(PcSpellId(value)
                            for value in magic['memorised_spells'])))
            character = build_value(DynamicEncounterInputError, f'/party/{index}', EncounterCharacter,
                actor_id=raw['actor_id'], **characteristics, **skills,
                **loadout,
                talents=tuple(EncounterTalent(t) for t in raw['talents']), fate=raw['resources']['fate'],
                combat_talents=pc_combat_talent_facts(raw,path_prefix=path),
                ranged=ranged,
                consumables=consumables, wizard=wizard,
                armour_worn=any(item.location is ItemLocation.WORN
                    and item.kind in (ArmourItemKind.LIGHT, ArmourItemKind.HEAVY, ArmourItemKind.HELMET)
                    for item in equipment.armour))
            party.append(character.participant(document['request_id'] + ':session', disposition))
        options = document.get('search_space')
        space = automatic_npc_search_space(tuple(party)) if options is None else build_value(
            DynamicEncounterInputError, '/search_space', NpcSearchSpace,
            **{name: (tuple(GeneratedWeapon(v) for v in values) if name == 'weapon' else
                tuple(tuple(GeneratedAbility(a) for a in group) for group in values) if name == 'abilities' else
                tuple(GeneratedTalent(v) for v in values) if name == 'allowed_talents' else tuple(values))
                for name, values in options.items()})
        search = dict(document['search'])
        search['master_seed'] = parse_seed(search['master_seed'], DynamicEncounterInputError, '/search/master_seed')
        request = build_value(DynamicEncounterInputError, '/', DynamicEncounterRequest,
            party=tuple(party), facts=PcMeleeFacts('arena', True, True, True, True,
                True, True, True, True, True, False,
                daylight_confirmed=True if any(member.wizard is not None for member in party) else None),
            day_id=document['request_id'] + ':day', space=space,
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


def execute_dynamic_encounter(command: DynamicEncounterCommand, *, cancel_requested=None, on_progress=None) -> DynamicEncounterResult:
    try:
        return search_dynamic_encounter(command.request, cancel_requested=cancel_requested, on_progress=on_progress)
    except DynamicEncounterCancelled:
        raise
    except Exception as error:
        raise DynamicEncounterExecutionError(command.request_id) from error


def candidate_document(candidate):
    source = candidate.summary.source_request
    document = dict(npcs=[asdict(n) for n in candidate.composition],
        win_rate=candidate.win_rate, win_interval_95=candidate.win_interval_95,
        mean_started_rounds=candidate.mean_started_rounds, rounds_interval_95=candidate.rounds_interval_95,
        outcomes=asdict(candidate.summary.outcome_counts), trials=candidate.summary.trials,
        replay=dict(schema_version='1', kind='pc_melee_simulation', request_id=source.scenario.id,
            ruleset='towr-pg1.4-gmg1.1', scenario=scenario_document(source.scenario),
            simulation=dict(master_seed=str(source.master_seed), trials=source.trials), execution=dict(mode='sequential')))
    if candidate.summary.potion_use_counts is not None:
        document['potion_use_counts'] = [asdict(item) for item in candidate.summary.potion_use_counts]
    if candidate.summary.npc_ranged_counts is not None:
        document['npc_ranged_counts'] = [asdict(item) for item in candidate.summary.npc_ranged_counts]
    if candidate.summary.pc_ranged_counts is not None:
        document['pc_ranged_counts'] = [asdict(item) for item in candidate.summary.pc_ranged_counts]
    if candidate.summary.magic_counts is not None:
        document['magic_counts'] = [asdict(item) for item in candidate.summary.magic_counts]
    return document


def encode_dynamic_encounter_result(command, result):
    if type(result) is not DynamicEncounterResult or result.source != command.request:
        raise ValueError('dynamic result belongs to another request')
    admitted = parse_dynamic_encounter_request(command.source_json)
    if admitted.request != command.request or admitted.request_id != command.request_id:
        raise ValueError('wire source differs from executable request')
    validate_dynamic_encounter_result(result)
    document = dict(schema_version='1', kind='dynamic_encounter_search_result', request_id=command.request_id,
        source_request=json.loads(command.source_json), resolved_search_space=asdict(command.request.space),
        explored=[candidate_document(c) for c in result.explored],
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
