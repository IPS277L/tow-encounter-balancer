import json
from pathlib import Path
import unittest

from towr.adapters.character_files import parse_character_file
from towr.adapters.dynamic_encounter_json import DynamicEncounterInputError


class CharacterFileTests(unittest.TestCase):
    def player(self):
        return json.loads(Path('docs/examples/dynamic/search.request.json').read_text('utf-8'))['party'][0]

    def npc(self):
        return dict(weapon_skill=3, strength=4, toughness=3, agility=2, melee=4,
            athletics=3, defence=5, shield=True, weapon='dagger', light_armour=True, abilities=['drained_on_hit'],talents=[],
            weapon_grip=None,mount=None,throwing=None,brawn=None,ballistic_skill=None)

    def test_player_roundtrip_preserves_inventory_and_unimplemented_draft(self):
        player = self.player()
        player['equipment']['weapons'].append(dict(id='spare', weapon='glaive', location='carried'))
        player['equipment']['armour'].append(dict(id='heavy', kind='heavy_armour', location='carried'))
        player['consumables'] = [dict(id='potion', kind='enhancement_potion', quantity=3,
            characteristic='ballistic_skill')]
        player['talents'] = ['lucky', 'Future talent']
        self.assertEqual(parse_character_file('\ufeff' + json.dumps(player), 'player'), player)
        self.assertEqual(parse_character_file(b'\xef\xbb\xbf' + json.dumps(player).encode(), 'player'), player)

    def test_npc_roundtrip_is_a_profile_without_report_or_derived_state(self):
        npc = self.npc()
        self.assertEqual(parse_character_file(json.dumps(npc), 'npc'), npc)
        for field in ('damage', 'resilience', 'win_rate', 'trials', 'schema_version'):
            with self.subTest(field=field), self.assertRaises(DynamicEncounterInputError):
                parse_character_file(json.dumps({**npc, field: 1}), 'npc')

    def test_all_six_weapons_and_independent_shield_survive_character_files(self):
        for weapon in ('staff','dagger','axe','sword','warhammer','morning_star'):
            for shield in (False,True):
                npc = dict(self.npc(),weapon=weapon,shield=shield,defence=6,light_armour=False)
                with self.subTest(weapon=weapon,shield=shield):
                    self.assertEqual(parse_character_file(json.dumps(npc),'npc'),npc)
        for changes in (dict(defence=True),dict(defence=1),dict(shield=1)):
            with self.subTest(changes=changes),self.assertRaises(DynamicEncounterInputError):
                parse_character_file(json.dumps(dict(self.npc(),**changes)),'npc')

    def test_wrong_family_and_invalid_source_values_are_rejected(self):
        cases = [('player', self.npc()), ('npc', self.player()), ('player', []),
            ('npc', {**self.npc(), 'melee': True}), ('npc', {**self.npc(), 'athletics': 7}),
            ('npc', {**self.npc(), 'strength': 0}), ('npc', {**self.npc(), 'abilities': ['unknown']}),
            ('npc', {**self.npc(), 'weapon': 'great_sword'})]
        for kind, document in cases:
            with self.subTest(kind=kind, document=document), self.assertRaises(DynamicEncounterInputError):
                parse_character_file(json.dumps(document), kind)

    def test_strict_json_rejects_duplicate_keys_float_tokens_and_nonfinite(self):
        raw = json.dumps(self.npc())
        for bad in ('{', raw.replace('"strength": 4', '"strength": 4, "strength": 5'),
                raw.replace('"strength": 4', '"strength": 4.0'),
                raw.replace('"strength": 4', '"strength": NaN')):
            with self.subTest(raw=bad), self.assertRaises(DynamicEncounterInputError):
                parse_character_file(bad, 'npc')
        with self.assertRaises(ValueError):
            parse_character_file(raw, 'unknown')

    def test_duplicate_item_ids_and_talent_names_are_rejected(self):
        player = self.player()
        player['consumables'] = [dict(id=player['equipment']['weapons'][0]['id'],
            kind='healing_potion', quantity=1, characteristic=None)]
        with self.assertRaises(DynamicEncounterInputError):
            parse_character_file(json.dumps(player), 'player')
        player['consumables'] = []
        player['talents'] = ['Lucky', 'lucky']
        with self.assertRaises(DynamicEncounterInputError):
            parse_character_file(json.dumps(player), 'player')
