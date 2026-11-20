"""Optional GM passage-blocking facts round-trip without running a search."""
from copy import deepcopy
import json
from random import Random
import unittest

from tests.integration.test_generated_talents_json import talent_request
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.dynamic_encounter_json import DynamicEncounterInputError, parse_dynamic_encounter_request
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.adapters.pc_melee_json_errors import PcMeleeInputError


def native_document(scenario):
    return dict(schema_version='1', kind='pc_melee_simulation', request_id='scene:blocking',
        ruleset='towr-pg1.4-gmg1.1', scenario=scenario_document(scenario),
        simulation=dict(master_seed='42', trials=1), execution=dict(mode='sequential'))


class EnemyZoneBlockingJsonTests(unittest.TestCase):
    def test_dynamic_scene_propagates_true_and_false_to_every_native_composition(self):
        for value in (False, True):
            raw = talent_request()
            raw['scene']['enemy_zone_blocking'] = value
            command = parse_dynamic_encounter_request(json.dumps(raw))
            with self.subTest(value=value):
                self.assertIs(command.request.battlefield.enemy_zone_blocking, value)
                self.assertEqual(json.loads(command.source_json), raw)
                npc = command.request.space.sample(Random(0))
                scenario = command.request.scenario((npc,), 'source:blocking')
                self.assertIs(scenario.battlefield.enemy_zone_blocking, value)
                native = native_document(scenario)
                self.assertIs(native['scenario']['battlefield']['enemy_zone_blocking'], value)
                self.assertEqual(parse_pc_melee_simulation_request(json.dumps(native)).request.scenario, scenario)

    def test_omitted_optional_field_is_false_and_pc_echo_matches_darkness_style(self):
        raw = talent_request()
        raw['scene'].pop('enemy_zone_blocking', None)
        command = parse_dynamic_encounter_request(json.dumps(raw))
        self.assertIs(command.request.battlefield.enemy_zone_blocking, False)
        self.assertNotIn('enemy_zone_blocking', json.loads(command.source_json)['scene'])
        scenario = command.request.scenario((command.request.space.sample(Random(0)),), 'source:default')
        native = native_document(scenario)
        self.assertIs(native['scenario']['battlefield']['enemy_zone_blocking'], False)
        self.assertIs(native['scenario']['battlefield']['darkness'], False)
        del native['scenario']['battlefield']['enemy_zone_blocking']
        parsed = parse_pc_melee_simulation_request(json.dumps(native))
        self.assertIs(parsed.request.scenario.battlefield.enemy_zone_blocking, False)
        self.assertEqual(parsed.request.scenario, scenario)

    def test_dynamic_and_native_sources_reject_truthy_values_and_null(self):
        raw = talent_request()
        command = parse_dynamic_encounter_request(json.dumps(raw))
        scenario = command.request.scenario((command.request.space.sample(Random(0)),), 'source:strict')
        for value in (1, 0, 'true', None, [], {}):
            dynamic = deepcopy(raw)
            dynamic['scene']['enemy_zone_blocking'] = value
            native = native_document(scenario)
            native['scenario']['battlefield']['enemy_zone_blocking'] = value
            with self.subTest(value=value):
                with self.assertRaises(DynamicEncounterInputError):
                    parse_dynamic_encounter_request(json.dumps(dynamic))
                with self.assertRaises(PcMeleeInputError):
                    parse_pc_melee_simulation_request(json.dumps(native))


if __name__ == '__main__':
    unittest.main()
