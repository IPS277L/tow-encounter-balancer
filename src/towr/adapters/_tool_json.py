"""One current physical ToolItemSource shape shared by all source codecs."""
from dataclasses import replace

from towr.adapters._json_common import build_value
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.domain.tool_inventory_models import ToolItemSource, ToolKind, initial_tool_inventory
from towr.domain.weapon_inventory_models import WeaponGrip, WeaponItemLocation


_HELD_GRIPS = {
    'left_hand': WeaponGrip.LEFT,
    'right_hand': WeaponGrip.RIGHT,
    'both_hands': WeaponGrip.BOTH,
}


def parse_tool_item_source(raw, *, path_prefix, error_type) -> ToolItemSource:
    required = {'id', 'kind', 'hands_required', 'location'}
    if type(raw) is not dict or not required <= raw.keys() or raw.keys() - required - {'instrument_name'}:
        raise error_type(Code.INVALID_INPUT, 'tool requires its complete closed physical source', path=path_prefix)
    if (type(raw['kind']) is not str or type(raw['location']) is not str
            or raw['location'] not in (*_HELD_GRIPS, 'carried')
            or 'instrument_name' in raw and type(raw['instrument_name']) is not str):
        raise error_type(Code.INVALID_INPUT, 'tool requires its exact kind, location and optional name', path=path_prefix)
    try:
        return build_value(error_type, path_prefix, ToolItemSource,
            raw['id'], ToolKind(raw['kind']), raw['hands_required'],
            WeaponItemLocation.CARRIED if raw['location'] == 'carried' else WeaponItemLocation.HELD,
            _HELD_GRIPS.get(raw['location']), raw.get('instrument_name'))
    except error_type:
        raise
    except (TypeError, ValueError) as error:
        raise error_type(Code.INVALID_INPUT, str(error), path=path_prefix) from error


def parse_tool_item_sources(raw, *, path_prefix, error_type) -> tuple[ToolItemSource, ...]:
    if type(raw) is not list:
        raise error_type(Code.INVALID_INPUT, 'tools require their exact source array', path=path_prefix)
    sources = tuple(parse_tool_item_source(item, path_prefix=f'{path_prefix}/{index}', error_type=error_type)
        for index, item in enumerate(raw))
    build_value(error_type, path_prefix, initial_tool_inventory, 'tools:source-admission', sources)
    return sources


def tool_item_source_document(source: ToolItemSource) -> dict:
    if type(source) is not ToolItemSource:
        raise TypeError('tool document requires its exact immutable source')
    replace(source)
    location = ('carried' if source.initial_location is WeaponItemLocation.CARRIED
        else next(name for name, grip in _HELD_GRIPS.items() if grip is source.initial_grip))
    document = dict(id=source.id, kind=source.kind.value,
        hands_required=source.hands_required, location=location)
    if source.instrument_name is not None:
        document['instrument_name'] = source.instrument_name
    return document


def tool_item_sources_document(sources: tuple[ToolItemSource, ...]) -> list[dict]:
    initial_tool_inventory('tools:source-admission', sources)
    return [tool_item_source_document(source) for source in sources]
