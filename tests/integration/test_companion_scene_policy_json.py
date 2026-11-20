"""Explicit dismounted-mount scene facts, without admission or combat claims."""
from copy import deepcopy
import json
from random import Random
import unittest

from tests.integration.test_enemy_zone_blocking_json import native_document
from tests.integration.test_generated_talents_json import talent_request
from towr.adapters.dynamic_encounter_json import DynamicEncounterInputError, parse_dynamic_encounter_request
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.adapters.pc_melee_json_errors import PcMeleeInputError
from towr.domain.pc_companion_policy_models import DismountedMountPolicy


class CompanionScenePolicyJsonTests(unittest.TestCase):
    def test_explicit_gm_facts_survive_dynamic_generation_and_native_source_roundtrip(self):
        for combatants in (False, True):
            raw = talent_request()
            raw['scene'].update(dismounted_mount_policy='wait_and_recover',
                dismounted_mounts_are_combatants=combatants)
            before = deepcopy(raw)
            with self.subTest(combatants=combatants):
                command = parse_dynamic_encounter_request(json.dumps(raw))
                self.assertIs(command.request.battlefield.dismounted_mount_policy,
                    DismountedMountPolicy.WAIT_AND_RECOVER)
                self.assertIs(command.request.battlefield.dismounted_mounts_are_combatants, combatants)
                scenario = command.request.scenario((command.request.space.sample(Random(0)),), 'companions:source')
                self.assertEqual(scenario.battlefield, command.request.battlefield)
                native = native_document(scenario)
                self.assertEqual(native['scenario']['battlefield']['dismounted_mount_policy'], 'wait_and_recover')
                self.assertIs(native['scenario']['battlefield']['dismounted_mounts_are_combatants'], combatants)
                self.assertEqual(parse_pc_melee_simulation_request(json.dumps(native)).request.scenario, scenario)
                self.assertEqual(json.loads(command.source_json), before)
                self.assertEqual(raw, before)

    def test_omitted_facts_default_to_wait_and_noncombatants_without_source_migration(self):
        raw = talent_request()
        raw['scene'].pop('dismounted_mount_policy', None)
        raw['scene'].pop('dismounted_mounts_are_combatants', None)
        command = parse_dynamic_encounter_request(json.dumps(raw))
        self.assertIs(command.request.battlefield.dismounted_mount_policy, DismountedMountPolicy.WAIT_AND_RECOVER)
        self.assertIs(command.request.battlefield.dismounted_mounts_are_combatants, False)
        self.assertEqual(json.loads(command.source_json), raw)
        scenario = command.request.scenario((command.request.space.sample(Random(0)),), 'companions:default')
        native = native_document(scenario)
        self.assertEqual(native['scenario']['battlefield']['dismounted_mount_policy'], 'wait_and_recover')
        self.assertIs(native['scenario']['battlefield']['dismounted_mounts_are_combatants'], False)
        del native['scenario']['battlefield']['dismounted_mount_policy']
        del native['scenario']['battlefield']['dismounted_mounts_are_combatants']
        self.assertEqual(parse_pc_melee_simulation_request(json.dumps(native)).request.scenario, scenario)

    def test_policy_is_closed_and_combatant_status_never_coerces_truthy_input(self):
        raw = talent_request()
        command = parse_dynamic_encounter_request(json.dumps(raw))
        scenario = command.request.scenario((command.request.space.sample(Random(0)),), 'companions:strict')
        invalid = dict(dismounted_mount_policy=('attack', 'wait', '', None, True, 1, [], {}),
            dismounted_mounts_are_combatants=(None, 0, 1, 'true', 'false', [], {}))
        for key, values in invalid.items():
            for value in values:
                dynamic = deepcopy(raw)
                dynamic['scene'][key] = value
                native = native_document(scenario)
                native['scenario']['battlefield'][key] = value
                with self.subTest(key=key, value=value):
                    with self.assertRaises(DynamicEncounterInputError):
                        parse_dynamic_encounter_request(json.dumps(dynamic))
                    with self.assertRaises(PcMeleeInputError):
                        parse_pc_melee_simulation_request(json.dumps(native))


if __name__ == '__main__':
    unittest.main()
