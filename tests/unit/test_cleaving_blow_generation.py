"""Cleaving Blow acquisition and dynamic source boundaries, PG74/C22."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from random import Random
import unittest

from tests.support.talent_sources import free_talent, paid_talent, paid_talent_document
from tests.unit.test_allies_in_arms_generation import FirstChoices, document, space
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.dynamic_encounter_json import DynamicEncounterInputError, parse_dynamic_encounter_request
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.domain.generated_npc_models import GeneratedWeapon, generated_talent_requirements_met
from towr.domain.talent_actor_models import (
    GENERATED_TALENT_POOL, NPC_EXECUTABLE_TALENTS, PC_EXECUTABLE_TALENTS,
)
from towr.domain.talent_catalog import TalentId


class CleavingBlowGenerationTests(unittest.TestCase):
    def test_both_actor_sources_and_default_generation_expose_the_same_talent(self):
        for admitted in (PC_EXECUTABLE_TALENTS, NPC_EXECUTABLE_TALENTS, GENERATED_TALENT_POOL):
            self.assertIn(TalentId.CLEAVING_BLOW, admitted)

    def test_paid_purchase_requires_actual_initial_strength_five(self):
        for value, expected in ((4, False), (5, True), (6, True), (True, False), (0, False), ('5', False)):
            with self.subTest(strength=value):
                self.assertIs(generated_talent_requirements_met(TalentId.CLEAVING_BLOW,
                    weapon_skill=3, strength=value), expected)

    def test_sample_selects_only_a_lawful_paid_acquisition_without_extra_source_facts(self):
        for strength in (4, 5):
            search = space(strength=(strength,), weapon=(GeneratedWeapon.GREATAXE,),
                allowed_talents=(TalentId.CLEAVING_BLOW,))
            npc = search.sample(FirstChoices())
            self.assertEqual(npc.talents,
                (paid_talent(TalentId.CLEAVING_BLOW),) if strength >= 5 else ())
            self.assertIsNone(npc.talent_facts)
            self.assertTrue(search.contains(npc))
            self.assertEqual(npc.participant('npc').definition.talents, npc.talents)

    def test_mutation_and_numeric_sampling_preserve_paid_requirements_and_physical_source(self):
        original = space(strength=(5,), weapon=(GeneratedWeapon.GREATAXE,),
            allowed_talents=(TalentId.CLEAVING_BLOW,)).sample(FirstChoices())
        search = space(strength=(4, 5, 6), weapon=(GeneratedWeapon.GREATAXE, GeneratedWeapon.SWORD),
            allowed_talents=(TalentId.CLEAVING_BLOW,))
        with self.assertRaises(ValueError):
            replace(original, strength=4)
        for seed in range(4):
            mutated = search.mutate(original, Random(seed))
            self.assertTrue(search.contains(mutated))
            if mutated.talents:
                self.assertGreaterEqual(mutated.strength, 5)
            numeric = search.resample_numeric((original,), Random(seed)).composition[0]
            self.assertTrue(search.contains(numeric))
            self.assertEqual(numeric.talents, original.talents)
            self.assertEqual(numeric.weapons, original.weapons)
            self.assertGreaterEqual(numeric.strength, 5)

    def test_free_creation_waiver_survives_numeric_resampling_below_five(self):
        search = space(strength=(3, 4, 5), allowed_talents=(TalentId.CLEAVING_BLOW,))
        original = replace(space().sample(FirstChoices()),
            talents=(free_talent(TalentId.CLEAVING_BLOW),))
        self.assertTrue(search.contains(original))
        for seed in range(4):
            numeric = search.resample_numeric((original,), Random(seed)).composition[0]
            self.assertEqual(numeric.talents, original.talents)
            self.assertTrue(search.contains(numeric))
        # A held two-handed weapon is a runtime trigger, not a purchase Requirement.
        self.assertEqual(original.weapons[0].kind.value, GeneratedWeapon.SWORD.value)

    def test_contains_rejects_an_unallowed_talent_outside_strength_or_forged_cached_source(self):
        search = space(strength=(5,), allowed_talents=(TalentId.CLEAVING_BLOW,))
        npc = search.sample(FirstChoices())
        self.assertFalse(replace(search, allowed_talents=()).contains(npc))
        self.assertFalse(search.contains(replace(npc, strength=6)))
        corrupted = deepcopy(npc)
        object.__setattr__(corrupted, 'strength', 4)
        self.assertFalse(search.contains(corrupted))

    def test_dynamic_pc_admission_checks_the_same_paid_requirement_and_preserves_source(self):
        raw = document()
        raw['party'][0]['characteristics']['strength'] = 5
        raw['party'][0]['talents'] = [paid_talent_document(TalentId.CLEAVING_BLOW)]
        parsed = parse_dynamic_encounter_request(json.dumps(raw))
        self.assertEqual(parsed.request.party[0].talents, (paid_talent(TalentId.CLEAVING_BLOW),))
        raw['party'][0]['characteristics']['strength'] = 4
        with self.assertRaises(DynamicEncounterInputError):
            parse_dynamic_encounter_request(json.dumps(raw))
        raw['party'][0]['talents'][0]['acquisitions'][0].update(phase='creation', funding='free')
        self.assertEqual(parse_dynamic_encounter_request(json.dumps(raw)).request.party[0].talents,
            (free_talent(TalentId.CLEAVING_BLOW),))

    def test_generated_acquisition_survives_current_native_json_without_new_wire_fields(self):
        raw = document()
        raw['search_space'].update(strength=[5], allowed_talents=['cleaving_blow'],
            weapon=['greataxe'], shield=[None])
        parsed = parse_dynamic_encounter_request(json.dumps(raw))
        npc = parsed.request.space.sample(FirstChoices())
        self.assertEqual(npc.talents, (paid_talent(TalentId.CLEAVING_BLOW),))
        source = parsed.request.scenario((npc,), 'cleaving:source')
        request = dict(schema_version='1', kind='pc_melee_simulation', request_id='cleaving:wire',
            ruleset='towr-pg1.4-gmg1.1', scenario=scenario_document(source),
            simulation=dict(master_seed='42', trials=1), execution=dict(mode='sequential'))
        restored = parse_pc_melee_simulation_request(json.dumps(request)).request.scenario
        self.assertEqual(restored, source)
        self.assertEqual(restored.enemies[0].definition.talents, npc.talents)

    def test_public_example_is_a_small_current_source_with_both_sides_eligible(self):
        raw = Path('docs/examples/dynamic/cleaving-blow.request.json').read_text(encoding='utf-8')
        parsed = parse_dynamic_encounter_request(raw)
        self.assertEqual(parsed.request.party[0].talents, (paid_talent(TalentId.CLEAVING_BLOW),))
        self.assertEqual(parsed.request.space.allowed_talents, (TalentId.CLEAVING_BLOW,))
        generated = parsed.request.space.sample(FirstChoices())
        self.assertTrue(parsed.request.space.contains(generated))
        self.assertEqual(generated.talents, (paid_talent(TalentId.CLEAVING_BLOW),))


if __name__ == '__main__':
    unittest.main()
