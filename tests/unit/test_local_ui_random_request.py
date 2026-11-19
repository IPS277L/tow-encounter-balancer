"""Random UI drafts are valid facts, independent of combat/search RNG."""
from copy import deepcopy
import json
from pathlib import Path
from random import Random
import unittest

from towr.adapters._local_ui_random_request import random_ui_request
from towr.adapters.dynamic_encounter_json import parse_dynamic_encounter_request
from towr.domain.weapon_catalog import WEAPON_PROFILES, WeaponKind


class SelectWeapon(Random):
    def __init__(self, profile):
        super().__init__(42)
        self.profile = profile

    def choice(self, values):
        if values and hasattr(values[0], 'kind'):
            return self.profile
        return super().choice(values)


class LocalUiRandomRequestTests(unittest.TestCase):
    def setUp(self):
        self.template = json.loads(Path('docs/examples/dynamic/ui.request.json').read_text('utf-8'))

    def test_all_ordinary_weapon_modes_have_valid_hands_preparation_and_native_parties(self):
        profiles = [p for p in WEAPON_PROFILES if not p.magical and p.kind is not WeaponKind.OGRE_PISTOL]
        self.assertEqual(len(profiles), 40)
        for profile in profiles:
            with self.subTest(weapon=profile.kind.value):
                draft = random_ui_request(self.template, SelectWeapon(profile))
                command = parse_dynamic_encounter_request(json.dumps(draft))
                self.assertEqual(len(command.request.party), len(draft['party']))
                for member in draft['party']:
                    if profile.physical:
                        self.assertEqual(member['equipment']['weapons'][0]['weapon'], profile.kind.value)
                    else:
                        self.assertEqual(member['equipment']['weapons'], [])

    def test_explicit_rng_varies_the_editable_inputs_without_changing_search_seed_or_source(self):
        template = deepcopy(self.template)
        template['scene'].update(single_combat_pairs=[dict(actor_id='old',target_id='removed')],
            visibility=[dict(observer_id='old',target_id='removed',visible=False)])
        original = deepcopy(template)
        drafts = [random_ui_request(template, Random(seed)) for seed in range(24)]
        self.assertEqual(template, original)
        self.assertEqual(drafts[0], random_ui_request(template, Random(0)))
        self.assertGreater(len({len(d['party']) for d in drafts}), 1)
        self.assertGreater(len({json.dumps(d['targets']) for d in drafts}), 1)
        self.assertGreater(len({json.dumps(d['npc_count']) for d in drafts}), 1)
        for draft in drafts:
            self.assertEqual(draft['search'], template['search'])
            self.assertEqual(draft['execution'], template['execution'])
            self.assertEqual(draft['defeat_disposition'], template['defeat_disposition'])
            self.assertIsNone(draft['search_space'])
            self.assertNotIn('visibility', draft['scene'])
            self.assertNotIn('single_combat_pairs', draft['scene'])
            self.assertEqual(len(set(m['actor_id'] for m in draft['party'])), len(draft['party']))
            self.assertGreater(draft['max_rounds'], draft['targets']['started_rounds']['numerator'])
        drafts[0]['search']['master_seed'] = '100'
        self.assertEqual(template['search'], original['search'])

