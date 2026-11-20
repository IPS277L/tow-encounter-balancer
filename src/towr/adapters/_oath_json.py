"""The one closed current JSON shape for actual GM oath scene facts."""
from dataclasses import asdict, replace

from towr.adapters._json_common import build_value
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.domain.oath_context_models import OathBattleContext
from towr.domain.test_models import Skill
from towr.application.generated_oath_sources import GeneratedOathSource
from towr.adapters._talent_json import (
    parse_acquired_talents, acquired_talents_document, parse_talent_owner_facts, talent_owner_facts_document,
)


_REQUIRED = {'gm_confirmation_id', 'in_good_standing_confirmed'}
_OPTIONAL = {'oath_id', 'combat_tests_fulfil_oath_confirmed', 'forbidden_attack_skills',
    'fleeing_breaks_oath', 'lady_prayer_before_battle_confirmed', 'honour_bound_used_this_session',
    'unmitigated_success_scope_confirmed'}


def parse_oath_context(raw, *, path, error_type):
    if raw is None:
        return None
    if type(raw) is not dict or not _REQUIRED <= raw.keys() or raw.keys() - _REQUIRED - _OPTIONAL:
        raise error_type(Code.INVALID_INPUT, 'Oath context requires its closed GM scene source.', path=path)
    skills = raw.get('forbidden_attack_skills', [])
    if type(skills) is not list or any(type(value) is not str for value in skills):
        raise error_type(Code.INVALID_INPUT, 'Oath restrictions require an array of Attack Skills.',
            path=path+'/forbidden_attack_skills')
    try:
        converted = tuple(Skill(value) for value in skills)
    except ValueError as error:
        raise error_type(Code.INVALID_INPUT, str(error), path=path+'/forbidden_attack_skills') from error
    return build_value(error_type, path, OathBattleContext,
        **dict(raw, forbidden_attack_skills=converted))


def oath_context_document(context):
    if type(context) is not OathBattleContext:
        raise TypeError('Oath context export requires its exact typed source')
    replace(context)
    return dict(asdict(context), forbidden_attack_skills=[skill.value for skill in context.forbidden_attack_skills])


def parse_generated_oath_sources(raw, *, path, error_type):
    if type(raw) is not list:
        raise error_type(Code.INVALID_INPUT, 'Allowed Oath sources require an array.', path=path)
    result=[]
    for index,item in enumerate(raw):
        entry=path+'/'+str(index)
        if type(item) is not dict or set(item) != {'talents','context','talent_facts'}:
            raise error_type(Code.INVALID_INPUT, 'An Oath source requires its full acquisition/context/facts bundle.',path=entry)
        result.append(build_value(error_type,entry,GeneratedOathSource,
            parse_acquired_talents(item['talents'],path=entry+'/talents',error_type=error_type),
            parse_oath_context(item['context'],path=entry+'/context',error_type=error_type),
            parse_talent_owner_facts(item['talent_facts'],path=entry+'/talent_facts',error_type=error_type)))
    return tuple(result)


def generated_oath_sources_document(sources):
    if type(sources) is not tuple:
        raise TypeError('Allowed Oath sources retain their exact immutable bundles')
    result=[]
    for source in sources:
        if type(source) is not GeneratedOathSource:
            raise TypeError('Allowed Oath sources require the actual complete typed source')
        replace(source)
        result.append(dict(talents=acquired_talents_document(source.talents),
            context=oath_context_document(source.context),
            talent_facts=talent_owner_facts_document(source.talent_facts)))
    return result
