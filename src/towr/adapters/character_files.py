"""Individual character files reuse the current dynamic JSON source fragments."""
from functools import lru_cache
from towr.adapters._oath_json import parse_oath_context
from towr.domain.oath_context_models import validate_oath_context

from towr.adapters._json_common import read_request, build_value
from towr.adapters.dynamic_encounter_json import DynamicEncounterInputError, _party_talent_facts, _validator
from towr.adapters._talent_json import parse_acquired_talents
from towr.adapters._tool_json import parse_tool_item_sources
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.adapters._pc_melee_scenario_json import parse_generated_components
from towr.domain.tool_inventory_models import initial_tool_inventory
from towr.domain.weapon_inventory_models import WeaponGrip


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
        tools = parse_tool_item_sources(equipment.get('tools', []),
            path_prefix='/equipment/tools', error_type=DynamicEncounterInputError)
        ids = [item['id'] for item in (*equipment['weapons'], *equipment['armour'],
            *document['consumables'], *equipment.get('tools', []))]
        if len(ids) != len(set(ids)):
            raise DynamicEncounterInputError(Code.INVALID_INPUT,
                'IDs предметов персонажа должны быть уникальны.', path='/equipment')
        tool_hands = initial_tool_inventory(document['actor_id'], tools).occupied_hands
        hands = {'left_hand': (WeaponGrip.LEFT,), 'right_hand': (WeaponGrip.RIGHT,),
            'both_hands': (WeaponGrip.LEFT, WeaponGrip.RIGHT)}
        occupied = {hand for item in (*equipment['weapons'], *equipment['armour'])
            for hand in hands.get(item['location'], ())}
        if any(hand in occupied for hand in tool_hands):
            raise DynamicEncounterInputError(Code.INVALID_INPUT,
                'Tools, weapons and Shield cannot share an occupied hand.', path='/equipment/tools')
        talents=parse_acquired_talents(document['talents'],path='/talents',error_type=DynamicEncounterInputError)
        context=parse_oath_context(document.get('oath_context'),path='/oath_context',error_type=DynamicEncounterInputError)
        build_value(DynamicEncounterInputError,'/oath_context',validate_oath_context,talents,context)
        _party_talent_facts(document, '')
    else:
        try:
            parse_generated_components(document, path_prefix='/', error_type=DynamicEncounterInputError)
        except DynamicEncounterInputError:
            raise
        except (ValueError, TypeError) as error:
            raise DynamicEncounterInputError(Code.INVALID_INPUT, str(error), path='/') from error
    return document
