"""Individual character files reuse the current dynamic JSON source fragments."""
from functools import lru_cache

from towr.adapters._json_common import read_request
from towr.adapters.dynamic_encounter_json import DynamicEncounterInputError, _validator,pc_combat_talent_facts
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.adapters._pc_melee_scenario_json import parse_generated_components


@lru_cache(maxsize=2)
def _character_validator(kind):
    fragment = {'player': 'party_member', 'npc': 'candidate/properties/npcs/items'}
    if kind not in fragment:
        raise ValueError('unknown character kind')
    return _validator('request').evolve(schema={
        '$ref': 'urn:towr:dynamic-encounter:common:1#/$defs/' + fragment[kind]})


def parse_character_file(text: str | bytes, kind: str) -> dict:
    """Validate a draft, without compiling a loadout or starting a simulation."""
    validator = _character_validator(kind)
    if isinstance(text, bytes):
        text = text.removeprefix(b'\xef\xbb\xbf')
    elif isinstance(text, str):
        text = text.removeprefix('\ufeff')
    document = read_request(text, DynamicEncounterInputError,
        lambda value, _kind: validator.validate(value))
    if kind == 'player':
        equipment = document['equipment']
        ids = [item['id'] for item in (*equipment['weapons'], *equipment['armour'],
            *document['consumables'])]
        if len(ids) != len(set(ids)):
            raise DynamicEncounterInputError(Code.INVALID_INPUT,
                'IDs предметов персонажа должны быть уникальны.', path='/equipment')
        talents = [value.casefold() for value in document['talents']]
        if len(talents) != len(set(talents)):
            raise DynamicEncounterInputError(Code.INVALID_INPUT,
                'Таланты не должны повторяться.', path='/talents')
        pc_combat_talent_facts(document)
    else:
        try:
            parse_generated_components(document, path_prefix='/', error_type=DynamicEncounterInputError)
        except DynamicEncounterInputError:
            raise
        except (ValueError, TypeError) as error:
            raise DynamicEncounterInputError(Code.INVALID_INPUT, str(error), path='/') from error
    return document
