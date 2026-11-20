"""Current dynamic generation JSON1, without a supplied enemy reserve."""
from dataclasses import asdict, dataclass, replace
from fractions import Fraction
from functools import lru_cache
from towr.adapters._oath_json import parse_oath_context, oath_context_document, parse_generated_oath_sources, generated_oath_sources_document
from importlib.resources import files
import json

from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from towr.adapters._json_common import build_value, parse_seed, read_request
from towr.adapters._pc_melee_scenario_json import (scenario_document,parse_airspace,generated_components_document,
    parse_medical_preparation,parse_surgery_risk,parse_generated_medical_sources,generated_medical_sources_document,parse_npc_allies)
from towr.adapters.ranged_json_errors import RangedInputError, RangedInputErrorCode as Code
from towr.application.dynamic_encounter import (
    DynamicEncounterRequest, DynamicEncounterResult, NpcSearchSpace,
    search_dynamic_encounter, validate_dynamic_encounter_result,
    DynamicEncounterCancelled, automatic_npc_search_space,
    assess_dynamic_targets,assess_dynamic_candidate,WIN_RATE_TOLERANCE,STARTED_ROUNDS_TOLERANCE,
)
from towr.application.encounter_character import EncounterCharacter
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions
from towr.application.encounter_inventory import (
    EncounterEquipment, WeaponItem, ArmourItem, ArmourItemKind, ItemLocation,
    ConsumableItem, ConsumableKind,
)
from towr.domain.generated_npc_models import GeneratedAbility, GeneratedWeapon
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import TalentOwnerFacts
from towr.domain.talent_actor_models import PC_EXECUTABLE_TALENTS
from towr.adapters._talent_json import parse_acquired_talents, parse_talent_owner_facts
from towr.adapters._tool_json import parse_tool_item_sources
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.pc_melee_models import (PcMeleeFacts,PcMeleeWeapon,PcRangedProfile,PC_THROWING_WEAPONS,
    PcRangedReloadHandPolicy,PcRepeaterBonusPolicy)
from towr.domain.pc_magic_source_models import PcWizardProfile, PcSpellId
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_single_combat_models import PcSingleCombatPair
from towr.adapters._pc_melee_scenario_json import parse_scene_features
from towr.adapters._pc_melee_scenario_json import parse_music_acoustics
from towr.domain.pc_mount_models import CombatMount, RiderKind
from towr.domain.armour_models import BodyArmour, HelmetKind, ShieldKind, armour_is_worn
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.ranged_weapon_profiles import RangedWeaponHands
from towr.domain.weapon_capability_models import weapon_ranged_requirements


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
    names = ['talent-common.schema.json','dynamic-encounter-common.schema.json', 'pc-melee-common.schema.json',
        'pc-melee-simulation-request-v1.schema.json'] + [
        f'dynamic-encounter-{k}-v1.schema.json' for k in ('request', 'result', 'error')]
    docs = {name: json.loads(files('towr.adapters.schemas').joinpath(name).read_text(encoding='utf-8')) for name in names}
    registry = Registry().with_resources((d['$id'], Resource.from_contents(d)) for d in docs.values())
    for document in docs.values():
        Draft202012Validator.check_schema(document)
    return Draft202012Validator(docs[f'dynamic-encounter-{kind}-v1.schema.json'], registry=registry)


def validate_dynamic_encounter_document(document, kind='request'):
    _validator(kind).validate(document)
    if kind == 'result':
        _validate_target_metadata(document)


def _validate_target_metadata(document):
    targets = document['source_request']['targets']
    try:
        win_target = float(Fraction(targets['win_rate']['numerator'],targets['win_rate']['denominator']))
        round_target = float(Fraction(targets['started_rounds']['numerator'],targets['started_rounds']['denominator']))
    except (ValueError,TypeError,OverflowError,ZeroDivisionError) as error:
        raise ValidationError('invalid target source') from error
    maximum = document['source_request']['max_rounds']
    if not 0 <= win_target <= 1 or not 1 <= round_target <= maximum:
        raise ValidationError('joint targets are outside the source encounter bounds')
    scores = []
    for stage in ('explored','validations'):
        for candidate in document[stage]:
            try:
                expected = assess_dynamic_targets(win_target,round_target,candidate['win_rate'],
                    candidate['mean_started_rounds'],candidate['outcomes']['unsupported_path'])
            except (ValueError,TypeError,OverflowError) as error:
                raise ValidationError('invalid joint target aggregate') from error
            if (candidate['win_rate'] != candidate['outcomes']['objective_achieved']/candidate['trials']
                    or sum(candidate['outcomes'].values()) != candidate['trials']
                    or candidate['mean_started_rounds'] > maximum):
                raise ValidationError('target assessment contradicts candidate accounting/budget')
            if candidate['target_assessment'] != asdict(expected):
                raise ValidationError('joint target metadata differs from the reported aggregate')
            if stage == 'validations':
                scores.append((expected.status == 'unsupported',expected.normalized_max_deviation,
                    expected.normalized_total_deviation))
    if scores != sorted(scores):
        raise ValidationError('validation joint target ranking is inconsistent')
    supported = [c for c in document['validations'] if c['target_assessment']['status'] != 'unsupported']
    if document['selected'] != [c['replay']['scenario']['id'] for c in supported]:
        raise ValidationError('selected candidates differ from supported validations')
    expected_match = any(c['target_assessment']['status'] == 'within_targets' for c in supported)
    if document['target_match_found'] != expected_match:
        raise ValidationError('target match flag differs from supported validation estimates')


@dataclass(frozen=True, slots=True)
class DynamicEncounterCommand:
    request_id: str
    request: DynamicEncounterRequest
    execution: SimulationExecutionOptions
    source_json: str


def _target(data, path, *, minimum=0, maximum=1):
    value = Fraction(data['numerator'], data['denominator'])
    if (value.numerator, value.denominator) != (data['numerator'], data['denominator']):
        raise DynamicEncounterInputError(Code.INVALID_INPUT, 'fraction must be reduced', path=path)
    if not minimum <= value <= maximum:
        raise DynamicEncounterInputError(Code.INVALID_INPUT, 'target is outside encounter bounds', path=path)
    return float(value)


def _party_talent_facts(raw, path):
    """Preserve additional initial characteristics, not temporary modifiers."""
    supplied = (None if raw.get('talent_facts') is None else parse_talent_owner_facts(
        raw['talent_facts'],path=path+'/talent_facts',error_type=DynamicEncounterInputError))
    extra = {name: raw['characteristics'][name] for name in
        ('ballistic_skill','initiative','reason','fellowship')
        if raw['characteristics'].get(name) is not None}
    if supplied is None and not extra:
        return None
    supplied = TalentOwnerFacts() if supplied is None else supplied
    for name,value in extra.items():
        previous = getattr(supplied,name)
        if previous is not None and previous != value:
            raise DynamicEncounterInputError(Code.INVALID_INPUT,
                'Talent facts disagree with the actual initial characteristic.',path=path+'/talent_facts/'+name)
    return build_value(DynamicEncounterInputError,path+'/talent_facts',replace,supplied,**extra)


def parse_dynamic_encounter_request(text: str | bytes) -> DynamicEncounterCommand:
    document = read_request(text, DynamicEncounterInputError, validate_dynamic_encounter_document)
    try:
        execution_data = document['execution']
        execution = build_value(DynamicEncounterInputError, '/execution', SimulationExecutionOptions,
            mode=SimulationExecutionMode(execution_data['mode']),
            workers=execution_data.get('workers'),
            batch_size=1 if execution_data['mode'] == 'process' else None)
        disposition = NpcDefeatDisposition(document['defeat_disposition'])
        party = []
        for index, raw in enumerate(document['party']):
            path = f'/party/{index}'
            gear = raw['equipment']
            tools = parse_tool_item_sources(gear.get('tools', []),
                path_prefix=path+'/equipment/tools', error_type=DynamicEncounterInputError)
            equipment = build_value(DynamicEncounterInputError, path + '/equipment', EncounterEquipment,
                armour_benefit_id=gear.get('armour_benefit_id'),
                weapons=tuple(build_value(DynamicEncounterInputError, f'{path}/equipment/weapons/{i}', WeaponItem,
                    id=w['id'], weapon=PcMeleeWeapon(w['weapon']), location=ItemLocation(w['location']),
                    initially_loaded=w.get('initially_loaded'),quantity=w.get('quantity',1),
                    initial_charges=w.get('initial_charges',0),gm_fit_confirmed=w.get('gm_fit_confirmed'))
                    for i, w in enumerate(gear['weapons'])),
                armour=tuple(build_value(DynamicEncounterInputError, f'{path}/equipment/armour/{i}', ArmourItem,
                    id=a['id'], kind=ArmourItemKind(a['kind']), location=ItemLocation(a['location']))
                    for i, a in enumerate(gear['armour'])))
            consumables = tuple(build_value(DynamicEncounterInputError, f'{path}/consumables/{i}', ConsumableItem,
                id=c['id'], kind=ConsumableKind(c['kind']), quantity=c['quantity'], characteristic=c['characteristic'])
                for i, c in enumerate(raw['consumables']))
            ids = [item.id for item in (*equipment.weapons, *equipment.armour, *consumables, *tools)]
            if len(set(ids)) != len(ids):
                raise DynamicEncounterInputError(Code.INVALID_INPUT, 'Inventory instance IDs must be unique.', path=path)
            if any(item.kind is ConsumableKind.ENHANCEMENT and item.characteristic not in
                    ('weapon_skill','strength','toughness','agility') for item in consumables):
                raise DynamicEncounterInputError(Code.INVALID_INPUT,
                    'Усиление (Enhancement Potion) пока поддерживает WS, Strength, Toughness и Agility.',
                    path=path + '/consumables')
            talents = parse_acquired_talents(raw['talents'],path=path+'/talents',error_type=DynamicEncounterInputError)
            talent_facts = _party_talent_facts(raw,path)
            unsupported = [entry.id.value for entry in talents if entry.id not in PC_EXECUTABLE_TALENTS]
            if unsupported:
                raise DynamicEncounterInputError(Code.INVALID_INPUT,
                    'Таланты пока не поддержаны симуляцией: ' + ', '.join(unsupported), path=path + '/talents')
            loadout = build_value(DynamicEncounterInputError, path + '/equipment', equipment.combat_loadout,
                raw['characteristics']['strength'],
                mount=None if raw.get('mount') is None else CombatMount(raw['mount']))
            wizard = None
            characteristics, skills = dict(raw['characteristics']), dict(raw['skills'])
            ranged=None
            requirements=weapon_ranged_requirements(tuple(item.weapon for item in loadout['combat_equipment']))
            throwing_inventory=any(item.weapon in PC_THROWING_WEAPONS for item in loadout['combat_equipment'])
            supplied_bs=characteristics.get('ballistic_skill')
            if requirements is not None:
                if 'ranged' not in raw:
                    raise DynamicEncounterInputError(Code.INVALID_INPUT,
                        'Для стрелкового оружия нужны факты подготовки (Ranged preparation).',path=path+'/ranged')
                prep=raw['ranged']
                required_stats={'ballistic_skill'} | ({'initiative'} if requirements.exacting else set())
                required_skills={'shooting'} | ({'dexterity'} if requirements.exacting else set())
                if requirements.requires_aim or 'awareness' in skills:
                    required_stats.add('initiative')
                    required_skills.add('awareness')
                if not required_stats<=characteristics.keys() or not required_skills<=skills.keys():
                    raise DynamicEncounterInputError(Code.INVALID_INPUT,
                        'Не заполнены характеристики/навыки стрельбы, зарядки или прицеливания (Shooting/Reload/Aim).',path=path)
                if not requirements.firearm and any(prep.get(key) is not None
                        for key in ('has_blackpowder_lore','has_blackpowder_kit')):
                    raise DynamicEncounterInputError(Code.INVALID_INPUT,
                        'Lore/Kit относятся к огнестрельному оружию (Firearms) в инвентаре.',path=path+'/ranged')
                ranged=build_value(DynamicEncounterInputError,path+'/ranged',PcRangedProfile,
                    ballistic_skill=characteristics.pop('ballistic_skill'),
                    shooting=skills.pop('shooting'),
                    **prep,reload_hand_policy=PcRangedReloadHandPolicy.TWO_AVAILABLE_HANDS if requirements.exacting else None,
                    repeater_bonus_policy=PcRepeaterBonusPolicy.AUTOMATIC if requirements.repeater else None)
            elif 'ranged' in raw:
                raise DynamicEncounterInputError(Code.INVALID_INPUT,
                    'Стрелковая подготовка требует оружия (Shooting Weapon) в инвентаре.',path=path+'/ranged')
            elif not throwing_inventory:
                # Inactive character facts remain in the editable source echo
                # and individual character file; this loadout cannot use them.
                characteristics.pop('ballistic_skill',None)
                skills.pop('shooting',None)
            if throwing_inventory:
                characteristics.pop('ballistic_skill',None)
                if requirements is None:
                    skills.pop('shooting',None)
            throwing=skills.pop('throwing',None)
            if 'magic' in raw:
                magic = raw['magic']
                wizard = build_value(DynamicEncounterInputError, path + '/magic', PcWizardProfile,
                    **dict(magic, willpower=skills.pop('willpower'),
                        lores=tuple(magic['lores']), memorised_spells=tuple(PcSpellId(value)
                            for value in magic['memorised_spells'])))
            character = build_value(DynamicEncounterInputError, f'/party/{index}', EncounterCharacter,
                throwing=throwing if throwing_inventory else None,
                ballistic_skill=supplied_bs if throwing_inventory else None,
                brawn=skills.pop('brawn',None),
                tools=tools,
                actor_id=raw['actor_id'], **characteristics, **skills,
                **loadout,
                talents=talents, fate=raw['resources']['fate'],
                talent_facts=talent_facts,
                oath_context=parse_oath_context(raw.get('oath_context'),path=path+'/oath_context',error_type=DynamicEncounterInputError),
                mount=None if raw.get('mount') is None else CombatMount(raw['mount']),
                rider_kind=None if raw.get('rider_kind') is None else RiderKind(raw['rider_kind']),
                agilulf_code_confirmed=raw.get('agilulf_code_confirmed'),
                ranged=ranged,
                medical=parse_medical_preparation(raw.get('medical'),path=path+'/medical',error_type=DynamicEncounterInputError),
                consumables=consumables, wizard=wizard,
                armour_worn=armour_is_worn(loadout['armour']))
            party.append(character.participant(document['request_id'] + ':session', disposition))
        battlefield=build_value(DynamicEncounterInputError,'/scene',PcBattlefieldSpec,
            RangedWeaponRange(document['scene']['range']),RangedWeaponRange(document['scene']['two_handed_max_range']),
            airspace=parse_airspace(document['scene'].get('airspace'),path='/scene/airspace',
                error_type=DynamicEncounterInputError),
            **parse_scene_features(document['scene'],path='/scene',error_type=DynamicEncounterInputError))
        npc_allies=parse_npc_allies(document.get('npc_allies',[]),path_prefix='/npc_allies',error_type=DynamicEncounterInputError)
        options = document.get('search_space')
        space = automatic_npc_search_space(tuple(party),npc_allies=npc_allies,battlefield=battlefield) if options is None else build_value(
            DynamicEncounterInputError, '/search_space', NpcSearchSpace,
            **{name: (tuple(GeneratedWeapon(v) for v in values) if name == 'weapon' else
                tuple(RangedWeaponHands(v) for v in values) if name == 'weapon_grip' else
                tuple(None if v is None else CombatMount(v) for v in values) if name == 'mount' else
                tuple(None if v is None else BodyArmour(v) for v in values) if name in ('armour','secondary_armour') else
                tuple(None if v is None else HelmetKind(v) for v in values) if name == 'helmet' else
                tuple(None if v is None else ShieldKind(v) for v in values) if name == 'shield' else
                tuple(RiderKind(v) for v in values) if name == 'rider_kind' else
                tuple(tuple(GeneratedAbility(a) for a in group) for group in values) if name == 'abilities' else
                tuple(TalentId(v) for v in values) if name == 'allowed_talents' else
                tuple(TargetInjuryPolicy(v) for v in values) if name == 'injury_policy' else
                parse_generated_oath_sources(values,path='/search_space/allowed_oath_sources',error_type=DynamicEncounterInputError) if name == 'allowed_oath_sources' else
                parse_generated_medical_sources(values,path='/search_space/allowed_medical_sources',error_type=DynamicEncounterInputError) if name == 'allowed_medical_sources' else
                values if name in ('agilulf_code_confirmed','ogre_fit_confirmed') else tuple(values))
                for name, values in options.items()})
        search = dict(document['search'])
        search['master_seed'] = parse_seed(search['master_seed'], DynamicEncounterInputError, '/search/master_seed')
        request = build_value(DynamicEncounterInputError, '/', DynamicEncounterRequest,
            party=tuple(party),npc_allies=npc_allies,
            player_side_activation_order=(None if document.get('player_side_activation_order') is None
                else tuple(document['player_side_activation_order'])), facts=PcMeleeFacts('arena', battlefield.initial_range is RangedWeaponRange.CLOSE, True, True, True,
                True, True, True, True, True, True,
                daylight_confirmed=True if any(member.wizard is not None for member in party) else None),
            day_id=document['request_id'] + ':day', space=space,battlefield=battlefield,
            surgery_risk=parse_surgery_risk(document['scene'].get('surgery_risk'),
                path='/scene/surgery_risk',error_type=DynamicEncounterInputError),
            music_acoustics=parse_music_acoustics(document['scene'].get('music_acoustics'),
                path='/scene/music_acoustics', error_type=DynamicEncounterInputError),
            single_combat_pairs=tuple(build_value(DynamicEncounterInputError,
                f'/scene/single_combat_pairs/{index}',PcSingleCombatPair,**pair)
                for index,pair in enumerate(document['scene'].get('single_combat_pairs',()))),
            minimum_npcs=document['npc_count']['minimum'], maximum_npcs=document['npc_count']['maximum'],
            target_win_rate=_target(document['targets']['win_rate'], '/targets/win_rate'),
            target_rounds=_target(document['targets']['started_rounds'], '/targets/started_rounds',
                minimum=1, maximum=document['max_rounds']),
            max_rounds=document['max_rounds'], defeat_disposition=disposition, **search)
        return DynamicEncounterCommand(document['request_id'], request, execution,
            json.dumps(document, ensure_ascii=False, allow_nan=False))
    except DynamicEncounterInputError as error:
        error.request_id = document['request_id']
        raise
    except (ValueError, TypeError, OverflowError) as error:
        raise DynamicEncounterInputError(Code.INVALID_INPUT, str(error), path='/', request_id=document['request_id']) from error


def execute_dynamic_encounter(command: DynamicEncounterCommand, *, cancel_requested=None, on_progress=None) -> DynamicEncounterResult:
    try:
        return search_dynamic_encounter(command.request, execution=command.execution,
            cancel_requested=cancel_requested, on_progress=on_progress)
    except DynamicEncounterCancelled:
        raise
    except Exception as error:
        raise DynamicEncounterExecutionError(command.request_id) from error


def candidate_document(request,candidate):
    source = candidate.summary.source_request
    document = dict(npcs=[generated_components_document(n) for n in candidate.composition],
        win_rate=candidate.win_rate, win_interval_95=candidate.win_interval_95,
        mean_started_rounds=candidate.mean_started_rounds, rounds_interval_95=candidate.rounds_interval_95,
        outcomes=asdict(candidate.summary.outcome_counts), trials=candidate.summary.trials,
        target_assessment=asdict(assess_dynamic_candidate(request,candidate)),
        replay=dict(schema_version='1', kind='pc_melee_simulation', request_id=source.scenario.id,
            ruleset='towr-pg1.4-gmg1.1', scenario=scenario_document(source.scenario),
            simulation=dict(master_seed=str(source.master_seed), trials=source.trials), execution=dict(mode='sequential')))
    if candidate.summary.npc_ally_counts is not None:
        document['npc_ally_counts']=[asdict(item) for item in candidate.summary.npc_ally_counts]
    if candidate.summary.potion_use_counts is not None:
        document['potion_use_counts'] = [asdict(item) for item in candidate.summary.potion_use_counts]
    if candidate.summary.npc_ranged_counts is not None:
        document['npc_ranged_counts'] = [asdict(item) for item in candidate.summary.npc_ranged_counts]
    if candidate.summary.pc_ranged_counts is not None:
        document['pc_ranged_counts'] = [asdict(item) for item in candidate.summary.pc_ranged_counts]
    if candidate.summary.rapid_reload_counts is not None:
        document['rapid_reload_counts'] = [asdict(item) for item in candidate.summary.rapid_reload_counts]
    if candidate.summary.immediate_attack_counts is not None:
        document['immediate_attack_counts'] = [asdict(item) for item in candidate.summary.immediate_attack_counts]
        document['total_immediate_attack_count'] = candidate.summary.total_immediate_attack_count
    if candidate.summary.companion_counts is not None:
        document['companion_counts'] = [asdict(item) for item in candidate.summary.companion_counts]
    if candidate.summary.music_counts is not None:
        document['music_counts'] = [asdict(item) for item in candidate.summary.music_counts]
    if candidate.summary.oath_counts is not None:
        document['oath_counts'] = [asdict(item) for item in candidate.summary.oath_counts]
    if candidate.summary.npc_aim_counts is not None:
        document['npc_aim_counts'] = [asdict(item) for item in candidate.summary.npc_aim_counts]
    if candidate.summary.magic_counts is not None:
        document['magic_counts'] = [asdict(item) for item in candidate.summary.magic_counts]
    return document


def encode_dynamic_encounter_result(command, result):
    if type(result) is not DynamicEncounterResult or result.source != command.request:
        raise ValueError('dynamic result belongs to another request')
    if type(command.execution) is not SimulationExecutionOptions:
        raise TypeError('dynamic execution options must be typed')
    replace(command.execution)
    admitted = parse_dynamic_encounter_request(command.source_json)
    if (admitted.request != command.request or admitted.request_id != command.request_id
            or admitted.execution != command.execution):
        raise ValueError('wire source differs from executable request')
    validate_dynamic_encounter_result(result)
    document = dict(schema_version='1', kind='dynamic_encounter_search_result', request_id=command.request_id,
        source_request=json.loads(command.source_json), resolved_search_space=dict(asdict(command.request.space),
            allowed_medical_sources=generated_medical_sources_document(command.request.space.allowed_medical_sources),
            allowed_oath_sources=generated_oath_sources_document(command.request.space.allowed_oath_sources)),
        target_criteria=dict(basis='point_estimates',win_rate_tolerance=WIN_RATE_TOLERANCE,
            started_rounds_tolerance=STARTED_ROUNDS_TOLERANCE),target_match_found=result.target_match_found,
        explored=[candidate_document(result.source,c) for c in result.explored],
        validations=[candidate_document(result.source,c) for c in result.validations],
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
