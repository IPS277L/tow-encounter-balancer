"""Random editable UI examples, not character creation or encounter search."""
from copy import deepcopy
import json
from math import gcd

from towr.adapters.dynamic_encounter_json import parse_dynamic_encounter_request
from towr.domain.ranged_weapon_profiles import RangedWeaponHands
from towr.domain.weapon_capability_models import weapon_ranged_requirements
from towr.domain.weapon_catalog import WEAPON_PROFILES, WeaponGroup, WeaponKind
from towr.domain.weapon_inventory_models import weapon_reload_target


# Magic items and GM-specific equipment must be granted explicitly by the user.
_WEAPONS = tuple(profile for profile in WEAPON_PROFILES
    if not profile.magical and profile.kind is not WeaponKind.OGRE_PISTOL)
_BACKUP = ('dagger', 'staff', 'axe', 'sword', 'warhammer', 'morning_star')


def _player(index, rng):
    profile = rng.choice(_WEAPONS)
    both = profile.hands is RangedWeaponHands.TWO_HANDED or (
        profile.variable_grip and rng.choice((False, True)))
    characteristics = dict(weapon_skill=rng.randint(2, 5), strength=rng.randint(2, 5),
        toughness=rng.randint(2, 5), agility=rng.randint(3, 5))
    skills = {key: rng.randint(3, 6)
        for key in ('melee', 'defence', 'athletics', 'endurance', 'brawn')}
    weapons = []
    if profile.physical:
        item = dict(id='weapon:1', weapon=profile.kind.value,
            location='both_hands' if both else 'left_hand')
        if weapon_reload_target(profile.kind) is not None:
            item['initially_loaded'] = True
        weapons.append(item)
    if profile.group is not WeaponGroup.MELEE or both and rng.choice((False, True)):
        weapons.append(dict(id='weapon:2', weapon=rng.choice(_BACKUP), location='carried'))
    armour = []
    body = rng.choice((None, 'light_armour', 'heavy_armour', 'full_plate_armour'))
    if body:
        armour.append(dict(id='body', kind=body, location='worn'))
    if rng.choice((False, True)):
        armour.append(dict(id='helmet', kind='helmet', location='worn'))
    if not both and rng.choice((False, True)):
        armour.append(dict(id='shield', kind='shield', location='right_hand'))
    talents = []
    for talent, eligible in (('lucky', True),
            ('defensive_stance', characteristics['weapon_skill'] >= 3),
            ('wild_attack', characteristics['strength'] >= 4)):
        if eligible and rng.randrange(4) == 0:
            talents.append(dict(id=talent,acquisitions=[dict(phase='advancement',funding='xp',
                choice=None,devotion_confirmed=None)]))
    consumables = []
    if rng.randrange(3) == 0:
        consumables.append(dict(id='healing', kind='healing_potion', quantity=rng.randint(1, 2),
            characteristic=None))
    if rng.randrange(3) == 0:
        consumables.append(dict(id='enhancement', kind='enhancement_potion', quantity=rng.randint(1, 2),
            characteristic=rng.choice(('weapon_skill', 'strength', 'toughness', 'agility'))))
    player = dict(actor_id=f'pc:{index}', characteristics=characteristics, skills=skills,
        equipment=dict(weapons=weapons, armour=armour), talents=talents,
        resources=dict(fate=rng.randint(0, 3)), consumables=consumables)
    requirements = weapon_ranged_requirements((profile.kind,))
    if requirements:
        characteristics['ballistic_skill'] = rng.randint(2, 5)
        skills['shooting'] = rng.randint(3, 6)
        if requirements.exacting or requirements.requires_aim:
            characteristics['initiative'] = rng.randint(2, 5)
        if requirements.exacting:
            skills['dexterity'] = rng.randint(3, 6)
        if requirements.requires_aim:
            skills['awareness'] = rng.randint(3, 6)
        player['ranged'] = dict(ammunition_supply_confirmed=True,
            has_blackpowder_lore=True if requirements.firearm else None,
            has_blackpowder_kit=True if requirements.firearm else None)
    elif profile.group is WeaponGroup.THROWING:
        characteristics['ballistic_skill'] = rng.randint(2, 5)
        skills['throwing'] = rng.randint(3, 6)
    return player


def random_ui_request(template, rng):
    """Keep seed/precision/execution and explicit GM scene policy facts.

    Ratings, ordinary equipment, preparation, talents and supplies here are
    example facts, not a book Character Creation procedure or XP allocation.
    The existing parser admits the complete request before it reaches the UI.
    """
    if type(template) is not dict:
        raise ValueError('Запрос должен быть JSON-объектом.')
    previous_scene = template.get('scene', {})
    if type(previous_scene) is not dict:
        raise ValueError('Условия сцены должны быть JSON-объектом.')
    party = [_player(index + 1, rng) for index in range(rng.randint(1, 5))]
    rounds = rng.randint(3, 8)
    percent = rng.choice((30, 40, 50, 60, 70))
    common = gcd(percent, 100)
    minimum = rng.randint(1, len(party))
    maximum = rng.randint(max(minimum, len(party)), min(10, len(party) * 2 + 2))
    document = dict(schema_version='1', kind='dynamic_encounter_search',
        request_id='dynamic:ui-random', ruleset='towr-pg1.4-gmg1.1', party=party,
        search_space=None, npc_count=dict(minimum=minimum, maximum=maximum),
        targets=dict(win_rate=dict(numerator=percent // common, denominator=100 // common),
            started_rounds=dict(numerator=rounds, denominator=1)),
        search=deepcopy(template.get('search')), max_rounds=rng.randint(rounds + 4, 20),
        defeat_disposition=template.get('defeat_disposition', 'killed'),
        execution=deepcopy(template.get('execution', dict(mode='sequential'))),
        scene=dict(range=rng.choice(('close', 'short', 'medium', 'long')),
            ambush='none', terrain='open', session_start='fresh', two_handed_max_range='long',
            enemy_zone_blocking=previous_scene.get('enemy_zone_blocking', False),
            dismounted_mount_policy=previous_scene.get('dismounted_mount_policy', 'wait_and_recover'),
            dismounted_mounts_are_combatants=previous_scene.get('dismounted_mounts_are_combatants', False)))
    if 'music_acoustics' in previous_scene:
        document['scene']['music_acoustics'] = deepcopy(previous_scene['music_acoustics'])
    parse_dynamic_encounter_request(json.dumps(document, ensure_ascii=False, allow_nan=False))
    return document
