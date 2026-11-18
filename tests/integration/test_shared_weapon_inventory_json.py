"""Current JSON admits finite items and preserves each item's initial charge.

Actor shooting preparation applies to the complete inventory; every Exacting
item declares its own initial charge without a separate actor charge state.
No combat or Monte Carlo trial is needed for source/readmission checks.
"""
from copy import deepcopy
import json
from pathlib import Path
from random import Random
import unittest
from unittest.mock import patch

from tests.integration.test_shared_pc_inventory import two_sword_source
from tests.integration.test_shared_pc_ranged_inventory import scene as pistol_source
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.character_files import parse_character_file
from towr.adapters.dynamic_encounter_json import DynamicEncounterInputError,parse_dynamic_encounter_request
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.adapters.pc_melee_json_errors import PcMeleeInputError
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_melee_result_models import initial_pc_melee_state
from towr.domain.weapon_inventory_models import WeaponGrip,WeaponItemLocation,weapon_reload_cycle_id


def simulation_document(source):
    return dict(schema_version='1',kind='pc_melee_simulation',request_id='shared-inventory',
        ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(source),
        simulation=dict(master_seed='42',trials=1),execution=dict(mode='sequential'))


def dynamic_document():
    raw=json.loads(Path('docs/examples/dynamic/ranged.request.json').read_text('utf-8'))
    ranged_player=json.loads(Path('docs/examples/dynamic/pc-ranged.request.json').read_text('utf-8'))['party'][0]
    player=raw['party'][0]
    player['characteristics'].update(ballistic_skill=3,initiative=3,strength=4)
    player['skills'].update(shooting=5,dexterity=4)
    player['ranged']=deepcopy(ranged_player['ranged'])
    player['equipment']['weapons']=[
        dict(id='left',weapon='pistol',location='left_hand',initially_loaded=True),
        dict(id='right',weapon='pistol',location='right_hand',initially_loaded=False),
        dict(id='spare',weapon='sword',location='carried')]
    return raw


class SharedWeaponInventoryJsonTests(unittest.TestCase):
    def test_pc_roundtrip_preserves_more_than_two_items_and_both_held_swords(self):
        source=two_sword_source(carried=(PcMeleeWeapon.STAFF,PcMeleeWeapon.DAGGER),strength=4)
        document=simulation_document(source)
        parsed=parse_pc_melee_simulation_request(json.dumps(document)).request.scenario
        self.assertEqual(parsed,source)
        self.assertEqual(scenario_document(parsed),document['scenario'])
        inventory=initial_pc_melee_state(parsed).participant('pc1').weapon_inventory
        self.assertEqual(len(inventory.items),4)
        self.assertEqual(tuple(item.source_item_id for item in inventory.items),
            ('left','right','carried:0','carried:1'))
        self.assertEqual(tuple(item.grip for item in inventory.items[:2]),(WeaponGrip.LEFT,WeaponGrip.RIGHT))
        self.assertTrue(all(item.location is WeaponItemLocation.CARRIED for item in inventory.items[2:]))

    def test_pc_roundtrip_keeps_different_charge_flags_for_same_kind_units(self):
        for flags in ((True,False),(False,True)):
            with self.subTest(flags=flags):
                source=pistol_source(rounds=1,loaded=flags)
                document=simulation_document(source)
                self.assertEqual(tuple(item['initially_loaded'] for item in
                    document['scenario']['party'][0]['combat_equipment']),flags)
                parsed=parse_pc_melee_simulation_request(json.dumps(document)).request.scenario
                self.assertEqual(parsed,source)
                inventory=initial_pc_melee_state(parsed).participant('pc1').weapon_inventory
                self.assertEqual(tuple(item.reload.loaded for item in inventory.items),flags)
                self.assertNotEqual(inventory.items[0].id,inventory.items[1].id)
                for item,loaded in zip(inventory.items,flags):
                    self.assertIs(item.source.initially_loaded,loaded)
                    self.assertEqual(item.reload.weapon_instance_id,item.id)
                    self.assertEqual(item.reload.reload_cycle_ids,
                        () if loaded else (weapon_reload_cycle_id(item.id,1),))

    def test_dynamic_echo_and_native_compilation_retain_every_item_flag(self):
        raw=dynamic_document()
        command=parse_dynamic_encounter_request(json.dumps(raw))
        self.assertEqual(json.loads(command.source_json),raw)
        equipment=command.request.party[0].combat_equipment
        self.assertEqual(tuple(item.id for item in equipment),('left','right','spare'))
        self.assertEqual(tuple(item.initially_loaded for item in equipment),(True,False,None))
        npc=command.request.space.sample(Random(42))
        source=command.request.scenario((npc,),'shared-inventory:compiled')
        inventory=initial_pc_melee_state(source).participant('pc').weapon_inventory
        self.assertEqual(tuple(item.source_item_id for item in inventory.items),('left','right','spare'))
        self.assertEqual(tuple(item.reload.loaded for item in inventory.items[:2]),(True,False))
        self.assertIsNone(inventory.items[2].reload)
        native=simulation_document(source)
        self.assertEqual(parse_pc_melee_simulation_request(json.dumps(native)).request.scenario,source)

    def test_character_file_save_load_preserves_per_item_flags_without_compiling(self):
        player=dynamic_document()['party'][0]
        serialized=json.dumps(player,ensure_ascii=False,indent=2)
        self.assertEqual(parse_character_file(serialized,'player'),player)
        self.assertEqual(parse_character_file(serialized.encode('utf-8'),'player'),player)

    def test_pc_rejects_non_boolean_and_non_exacting_charge_before_calculation(self):
        base=simulation_document(pistol_source(rounds=1))
        for value in (1,'true',[],{}):
            invalid=deepcopy(base)
            invalid['scenario']['party'][0]['combat_equipment'][1]['initially_loaded']=value
            with self.subTest(value=value),self.assertRaises(PcMeleeInputError):
                parse_pc_melee_simulation_request(json.dumps(invalid))
        invalid=simulation_document(two_sword_source())
        invalid['scenario']['party'][0]['combat_equipment'][0]['initially_loaded']=True
        with self.assertRaises(PcMeleeInputError):
            parse_pc_melee_simulation_request(json.dumps(invalid))

    def test_dynamic_invalid_item_flags_fail_before_any_roll_or_search(self):
        with patch('towr.rules.test_resolution.roll_test_initial') as roll,patch(
                'towr.adapters.dynamic_encounter_json.search_dynamic_encounter') as search:
            for index,value in ((0,1),(1,'false'),(2,True),(2,False)):
                invalid=dynamic_document()
                invalid['party'][0]['equipment']['weapons'][index]['initially_loaded']=value
                with self.subTest(index=index,value=value),self.assertRaises(DynamicEncounterInputError):
                    parse_dynamic_encounter_request(json.dumps(invalid))
            invalid=dynamic_document()
            del invalid['party'][0]['equipment']['weapons'][1]['initially_loaded']
            with self.assertRaises(DynamicEncounterInputError):
                parse_dynamic_encounter_request(json.dumps(invalid))
            roll.assert_not_called()
            search.assert_not_called()


if __name__=='__main__':unittest.main()
