"""Closed current wire objects for common Talent acquisition facts.

Codecs preserve ownership facts only. Actor admission and active Talent
effects belong to their domain owners; no defaults grant runtime abilities.
"""
from dataclasses import replace

from towr.adapters._json_common import build_value
from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.domain.talent_catalog import (
    FamiliarEffect, TalentEquipmentRequirement, TalentId, TalentOrigin,
    TalentSelection, TalentStatusTier, talent_definition,
)
from towr.domain.talent_models import (
    AcquiredTalent, BloodlineChoice, DeityChoice, DeityId, FamiliarEffectChoice,
    HatredGroupChoice, MagicLoreChoice, OathChoice, TalentAcquisition,
    TalentAcquisitionPhase, TalentFunding, TalentLoreFact, TalentOwnerFacts,
)


_CHARACTERISTICS = ('weapon_skill', 'ballistic_skill', 'strength', 'toughness',
    'initiative', 'agility', 'reason', 'fellowship')
_CHOICES = {
    TalentSelection.DEITY: ('deity', DeityChoice, DeityId),
    TalentSelection.FAMILIAR_EFFECT: ('effect', FamiliarEffectChoice, FamiliarEffect),
    TalentSelection.HATED_GROUP: ('group_id', HatredGroupChoice, None),
    TalentSelection.OATH: ('oath_id', OathChoice, None),
    TalentSelection.SECRET_BLOODLINE: ('bloodline_id', BloodlineChoice, None),
    TalentSelection.MAGIC_LORE: ('lore_id', MagicLoreChoice, None),
}


def _child(path, key):
    return path + '/' + str(key).replace('~', '~0').replace('/', '~1')


def _invalid(error_type, path, message):
    raise error_type(Code.INVALID_INPUT, message, path=path)


def _object(raw, *, allowed, required=(), path, error_type):
    if type(raw) is not dict:
        _invalid(error_type, path, 'expected a Talent source object')
    for key in raw:
        if type(key) is not str:
            _invalid(error_type, path, 'Talent source keys require exact strings')
        if key not in allowed:
            _invalid(error_type, _child(path, key), 'unknown Talent source field')
    for key in required:
        if key not in raw:
            _invalid(error_type, _child(path, key), 'missing required Talent source field')
    return raw


def _array(raw, *, path, error_type):
    if type(raw) is not list:
        _invalid(error_type, path, 'expected an array of Talent source facts')
    return raw


def _enum(raw, kind, *, path, error_type):
    if type(raw) is not str:
        _invalid(error_type, path, 'expected an exact Talent source identifier')
    return build_value(error_type, path, kind, raw)


def _identifier(raw, *, path, error_type):
    if type(raw) is not str or not raw.strip():
        _invalid(error_type, path, 'expected a nonempty exact Talent source identifier')
    return raw


def _bool(raw, *, path, error_type):
    if type(raw) is not bool:
        _invalid(error_type, path, 'expected an exact boolean Talent source fact')
    return raw


def _choice(raw, talent, *, path, error_type):
    if raw is None:
        return None
    selection = talent_definition(talent).selection
    if selection not in _CHOICES:
        _invalid(error_type, path, 'this Talent acquisition has no choice payload')
    key, constructor, enum = _CHOICES[selection]
    _object(raw, allowed=(key,), required=(key,), path=path, error_type=error_type)
    value_path = _child(path, key)
    value = (_enum(raw[key], enum, path=value_path, error_type=error_type)
        if enum is not None else _identifier(raw[key], path=value_path, error_type=error_type))
    return build_value(error_type, path, constructor, value)


def parse_acquired_talents(raw, *, path, error_type) -> tuple[AcquiredTalent, ...]:
    result = []
    seen = set()
    for index, item in enumerate(_array(raw, path=path, error_type=error_type)):
        item_path = _child(path, index)
        _object(item, allowed=('id', 'acquisitions'), required=('id', 'acquisitions'),
            path=item_path, error_type=error_type)
        talent = _enum(item['id'], TalentId, path=_child(item_path, 'id'), error_type=error_type)
        if talent in seen:
            _invalid(error_type, _child(item_path, 'id'), 'duplicate acquired Talent identity')
        seen.add(talent)
        acquisition_path = _child(item_path, 'acquisitions')
        acquisitions = []
        for number, value in enumerate(_array(item['acquisitions'],
                path=acquisition_path, error_type=error_type)):
            source_path = _child(acquisition_path, number)
            _object(value, allowed=('phase', 'funding', 'choice', 'devotion_confirmed'),
                required=('phase', 'funding'), path=source_path, error_type=error_type)
            phase = _enum(value['phase'], TalentAcquisitionPhase,
                path=_child(source_path, 'phase'), error_type=error_type)
            funding = _enum(value['funding'], TalentFunding,
                path=_child(source_path, 'funding'), error_type=error_type)
            choice = _choice(value.get('choice'), talent,
                path=_child(source_path, 'choice'), error_type=error_type)
            devotion = value.get('devotion_confirmed')
            if devotion is not None:
                devotion = _bool(devotion, path=_child(source_path, 'devotion_confirmed'), error_type=error_type)
            acquisitions.append(build_value(error_type, source_path, TalentAcquisition,
                phase, funding, choice, devotion))
        result.append(build_value(error_type, item_path, AcquiredTalent, talent, tuple(acquisitions)))
    return tuple(result)


def acquired_talents_document(talents) -> list[dict]:
    if type(talents) is not tuple or any(type(value) is not AcquiredTalent for value in talents):
        raise TypeError('Talent serialization requires an exact tuple of acquired Talents')
    for value in talents:
        replace(value)
    if len({value.id for value in talents}) != len(talents):
        raise ValueError('Talent serialization cannot duplicate an acquired identity')
    result = []
    for value in talents:
        acquisitions = []
        for acquisition in value.acquisitions:
            choice = acquisition.choice
            payload = None
            if choice is not None:
                key, constructor, enum = _CHOICES[talent_definition(value.id).selection]
                # AcquiredTalent already verifies its exact contextual choice type.
                selected = getattr(choice, key)
                payload = {key: selected.value if enum is not None else selected}
            acquisitions.append(dict(phase=acquisition.phase.value, funding=acquisition.funding.value,
                choice=payload, devotion_confirmed=acquisition.devotion_confirmed))
        result.append(dict(id=value.id.value, acquisitions=acquisitions))
    return result


def parse_talent_owner_facts(raw, *, path, error_type) -> TalentOwnerFacts:
    _object(raw, allowed=(*_CHARACTERISTICS, 'origin', 'lores', 'status', 'equipment',
        'grail_quest_completed', 'can_cast_spells'), path=path, error_type=error_type)
    values = {}
    for name in _CHARACTERISTICS:
        value = raw.get(name)
        if value is not None and (type(value) is not int or value < 1):
            _invalid(error_type, _child(path, name), 'Characteristic requires a positive exact integer or null')
        values[name] = value
    for name, kind in (('origin', TalentOrigin), ('status', TalentStatusTier)):
        value = raw.get(name)
        values[name] = None if value is None else _enum(value, kind,
            path=_child(path, name), error_type=error_type)
    lore_path = _child(path, 'lores')
    lores = []
    seen_lores = set()
    for index, value in enumerate(_array(raw.get('lores', []), path=lore_path, error_type=error_type)):
        item_path = _child(lore_path, index)
        _object(value, allowed=('id', 'magic'), required=('id',), path=item_path, error_type=error_type)
        id = _identifier(value['id'], path=_child(item_path, 'id'), error_type=error_type)
        if id in seen_lores:
            _invalid(error_type, _child(item_path, 'id'), 'duplicate or conflicting Talent Lore identity')
        seen_lores.add(id)
        magic = _bool(value.get('magic', False), path=_child(item_path, 'magic'), error_type=error_type)
        lores.append(build_value(error_type, item_path, TalentLoreFact, id, magic))
    values['lores'] = tuple(lores)
    equipment_path = _child(path, 'equipment')
    equipment = []
    for index, value in enumerate(_array(raw.get('equipment', []), path=equipment_path, error_type=error_type)):
        item_path = _child(equipment_path, index)
        item = _enum(value, TalentEquipmentRequirement, path=item_path, error_type=error_type)
        if item in equipment:
            _invalid(error_type, item_path, 'duplicate Talent prerequisite equipment')
        equipment.append(item)
    values['equipment'] = tuple(equipment)
    for name in ('grail_quest_completed', 'can_cast_spells'):
        values[name] = _bool(raw.get(name, False), path=_child(path, name), error_type=error_type)
    return build_value(error_type, path, TalentOwnerFacts, **values)


def talent_owner_facts_document(facts) -> dict:
    if type(facts) is not TalentOwnerFacts:
        raise TypeError('Talent owner serialization requires its exact typed facts')
    replace(facts)
    return {**{name: getattr(facts, name) for name in _CHARACTERISTICS},
        'origin': facts.origin.value if facts.origin is not None else None,
        'lores': [dict(id=value.id, magic=value.magic) for value in facts.lores],
        'status': facts.status.value if facts.status is not None else None,
        'equipment': [value.value for value in facts.equipment],
        'grail_quest_completed': facts.grail_quest_completed,
        'can_cast_spells': facts.can_cast_spells}
