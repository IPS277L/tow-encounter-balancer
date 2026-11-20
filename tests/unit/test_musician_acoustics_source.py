"""GM acoustic facts retain None/false and resolve stable scene Zone keys."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from random import Random
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.adapters._local_ui_random_request import random_ui_request
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.dynamic_encounter_json import DynamicEncounterInputError, parse_dynamic_encounter_request
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.adapters.pc_melee_json_errors import PcMeleeSimulationInputError
from towr.domain.battlefield_music_models import BattlefieldMusicAcoustics


def dynamic_document():
    return json.loads(Path('docs/examples/dynamic/search.request.json').read_text(encoding='utf-8'))


def native_document(source):
    return dict(schema_version='1', kind='pc_melee_simulation', request_id='acoustics:wire',
        ruleset='towr-pg1.4-gmg1.1', scenario=scenario_document(source),
        simulation=dict(master_seed='42', trials=1), execution=dict(mode='sequential'))


class MusicianAcousticsSourceTests(unittest.TestCase):
    def test_dynamic_current_source_preserves_unknown_false_and_confirmed_facts(self):
        for value in (None, dict(audible_confirmed=False, blocked_zone_pairs=[]),
                dict(audible_confirmed=True, blocked_zone_pairs=[['zone:0', 'zone:1']])):
            raw = dynamic_document()
            raw['scene']['music_acoustics'] = value
            before = deepcopy(raw)
            command = parse_dynamic_encounter_request(json.dumps(raw))
            with self.subTest(value=value):
                actual = command.request.music_acoustics
                expected = (None if value is None else BattlefieldMusicAcoustics(value['audible_confirmed'],
                    tuple(tuple(pair) for pair in value['blocked_zone_pairs'])))
                self.assertEqual(actual, expected)
                self.assertEqual(json.loads(command.source_json), before)
                npc = command.request.space.sample(Random(0))
                source = command.request.scenario((npc,), 'acoustics:source')
                self.assertIs(source.music_acoustics, actual)
                restored = parse_pc_melee_simulation_request(json.dumps(native_document(source))).request.scenario
                self.assertEqual(restored, source)
                self.assertEqual(raw, before)

    def test_absent_facts_remain_unknown_and_stationary_scene_rejects_barriers(self):
        self.assertIsNone(parse_dynamic_encounter_request(json.dumps(dynamic_document())).request.music_acoustics)
        stationary = make_pc_melee_scenario()
        self.assertIsNone(stationary.music_acoustics)
        for audible in (False, True):
            source = replace(stationary, music_acoustics=BattlefieldMusicAcoustics(audible))
            self.assertEqual(parse_pc_melee_simulation_request(json.dumps(native_document(source))).request.scenario,
                source)
        with self.assertRaisesRegex(ValueError, 'actual distinct battlefield Zones'):
            replace(stationary, music_acoustics=BattlefieldMusicAcoustics(True, (('zone:0', 'zone:1'),)))

    def test_relative_pairs_bind_existing_ground_and_air_zones(self):
        raw = dynamic_document()
        raw['scene']['music_acoustics'] = dict(audible_confirmed=True,
            blocked_zone_pairs=[['zone:-3', 'zone:0']])
        command = parse_dynamic_encounter_request(json.dumps(raw))
        self.assertFalse(command.request.music_acoustics.can_hear('zone:0', 'zone:-3'))
        self.assertTrue(command.request.music_acoustics.can_hear('zone:0', 'zone:1'))
        for pair in (['zone:0', 'zone:100'], ['zone:0', 'air:0']):
            raw['scene']['music_acoustics']['blocked_zone_pairs'] = [pair]
            with self.subTest(pair=pair), self.assertRaises(DynamicEncounterInputError):
                parse_dynamic_encounter_request(json.dumps(raw))
        raw['scene']['airspace'] = dict(open_sky_confirmed=True, fall_hazard_rating=2)
        command = parse_dynamic_encounter_request(json.dumps(raw))
        self.assertEqual(command.request.music_acoustics.blocked_zone_pairs, (('zone:0', 'air:0'),))

    def test_public_acoustics_rejects_coercions_duplicates_missing_and_foreign_keys(self):
        for value in (True, {}, dict(audible_confirmed=1, blocked_zone_pairs=[]),
                dict(audible_confirmed=True), dict(audible_confirmed=True, blocked_zone_pairs=True),
                dict(audible_confirmed=True, blocked_zone_pairs=[['zone:0', 'zone:0']]),
                dict(audible_confirmed=True, blocked_zone_pairs=[['zone:0', 'zone:1'], ['zone:1', 'zone:0']]),
                dict(audible_confirmed=True, blocked_zone_pairs=[['arena:zone:0', 'zone:1']]),
                dict(audible_confirmed=True, blocked_zone_pairs=[['zone:00', 'zone:1']]),
                dict(audible_confirmed=True, blocked_zone_pairs=[['zone:-0', 'zone:1']]),
                dict(audible_confirmed=True, blocked_zone_pairs=[], medium_confirmed=True)):
            raw = dynamic_document()
            raw['scene']['music_acoustics'] = value
            with self.subTest(value=value), self.assertRaises(DynamicEncounterInputError):
                parse_dynamic_encounter_request(json.dumps(raw))
        source = make_pc_melee_scenario()
        raw = native_document(source)
        raw['scenario']['music_acoustics'] = dict(audible_confirmed=1, blocked_zone_pairs=[])
        with self.assertRaises(PcMeleeSimulationInputError):
            parse_pc_melee_simulation_request(json.dumps(raw))

    def test_cached_source_requires_exact_acoustics_and_revalidates_nested_bool(self):
        source = make_pc_melee_scenario()
        with self.assertRaises(TypeError):
            replace(source, music_acoustics=True)
        corrupt = BattlefieldMusicAcoustics(True)
        object.__setattr__(corrupt, 'audible_confirmed', 1)
        with self.assertRaises(TypeError):
            replace(source, music_acoustics=corrupt)
        command = parse_dynamic_encounter_request(json.dumps(dynamic_document()))
        with self.assertRaises(TypeError):
            replace(command.request, music_acoustics=True)

    def test_random_ui_drafts_preserve_acoustic_policy_without_granting_music(self):
        for value in (None, dict(audible_confirmed=False, blocked_zone_pairs=[]),
                dict(audible_confirmed=True, blocked_zone_pairs=[['zone:0', 'zone:1']])):
            raw = dynamic_document()
            raw['scene']['music_acoustics'] = value
            before = deepcopy(raw)
            draft = random_ui_request(raw, Random(0))
            with self.subTest(value=value):
                self.assertEqual(draft['scene']['music_acoustics'], value)
                self.assertTrue(all(not member['equipment'].get('tools') for member in draft['party']))
                self.assertTrue(all(not any(talent['id'] == 'battlefield_musician'
                    for talent in member['talents']) for member in draft['party']))
                self.assertEqual(raw, before)
        raw = dynamic_document()
        self.assertNotIn('music_acoustics', random_ui_request(raw, Random(0))['scene'])


if __name__ == '__main__':
    unittest.main()
