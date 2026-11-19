"""Current Magic Weapon/Ogre item contracts, without Monte Carlo execution."""
from copy import deepcopy
import json
from pathlib import Path
from random import Random
import unittest

from towr.adapters._pc_melee_scenario_json import generated_components_document, scenario_document
from towr.adapters.character_files import parse_character_file
from towr.adapters.dynamic_encounter_json import DynamicEncounterInputError,parse_dynamic_encounter_request
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.adapters.pc_melee_json_errors import PcMeleeInputError
from towr.domain.pc_weapon_inventory import initial_pc_weapon_inventory


from tests.support.magic_weapon_fixtures import MAGIC,TWO_HANDED,request,native


class MagicWeaponProcessTests(unittest.TestCase):
    def test_actual_duellist_action_counters_and_scene_sources_have_process_parity(self):
        from tests.support.magic_weapon_battles import magic_battle
        from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
        from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
        from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
        from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
        source=magic_battle('duellist_blades',npc_magic=True,pc_weapon='duellist_blades')
        simulation=PcMeleeSimulationRequest(source,42,2)
        sequential=run_pc_melee_simulation(simulation)
        parallel=run_pc_melee_simulation_parallel(simulation,workers=2,batch_size=1)
        self.assertEqual(sequential,parallel)
        self.assertEqual(summarize_pc_melee_simulation(sequential),summarize_pc_melee_simulation(parallel))
        self.assertIsNotNone(sequential.records[0].pc_extra_attack_counts)


class MagicWeaponJsonTests(unittest.TestCase):
    def test_automatic_npc_pool_keeps_magic_and_ogre_opt_in(self):
        raw=request()
        raw.pop('search_space')
        command=parse_dynamic_encounter_request(json.dumps(raw))
        self.assertEqual(len(command.request.space.weapon),39)
        self.assertFalse(set(kind.value for kind in command.request.space.weapon)&set((*MAGIC,'ogre_pistol')))

    def test_one_handed_magic_and_ogre_allow_actual_shield_without_losing_item_facts(self):
        for kind in ('morning_star_of_fracasse','scarab_knife','trickster_blade','sword_of_justice','ogre_pistol'):
            with self.subTest(kind=kind):
                raw=request(kind)
                raw['party'][0]['equipment']['armour']=[dict(id='shield',kind='shield',location='right_hand')]
                command=parse_dynamic_encounter_request(json.dumps(raw))
                source=command.request.space.sample(Random(2))
                scenario=command.request.scenario((source,),'magic-shield')
                restored=parse_pc_melee_simulation_request(json.dumps(native(scenario))).request.scenario
                self.assertEqual(restored,scenario)
                self.assertIsNotNone(restored.party[0].shield)

    def test_all_ten_item_sources_native_roundtrip_and_granular_files(self):
        for kind in (*MAGIC,'ogre_pistol'):
            with self.subTest(kind=kind):
                raw=request(kind)
                command=parse_dynamic_encounter_request(json.dumps(raw))
                source=command.request.space.sample(Random(1))
                scenario=command.request.scenario((source,),'magic-source')
                document=native(scenario)
                restored=parse_pc_melee_simulation_request(json.dumps(document)).request.scenario
                self.assertEqual(restored,scenario)
                self.assertEqual(parse_character_file(json.dumps(raw['party'][0]),'player'),raw['party'][0])
                npc_document=generated_components_document(source)
                self.assertEqual(parse_character_file(json.dumps(npc_document),'npc'),npc_document)
                self.assertEqual(len(initial_pc_weapon_inventory(scenario.party[0]).items),1)
                if kind=='scarab_knife':
                    self.assertEqual(initial_pc_weapon_inventory(scenario.party[0]).active.charges,4)
                    self.assertEqual(source.weapons[0].initial_charges,2)
                if kind=='ogre_pistol':
                    self.assertIs(initial_pc_weapon_inventory(scenario.party[0]).active.source.gm_fit_confirmed,True)

    def test_ogre_pool_and_each_item_require_exact_explicit_fit(self):
        for location in ('party','search_space'):
            for value in (None,False,1,'true'):
                raw=request('ogre_pistol')
                target=raw['search_space'] if location=='search_space' else raw['party'][0]['equipment']['weapons'][0]
                target['ogre_fit_confirmed' if location=='search_space' else 'gm_fit_confirmed']=value
                with self.subTest(location=location,value=value),self.assertRaises(DynamicEncounterInputError):
                    parse_dynamic_encounter_request(json.dumps(raw))

    def test_charges_are_strict_item_specific_and_do_not_disappear_in_source_echo(self):
        for value in (True,-1,1.5):
            raw=request()
            raw['party'][0]['equipment']['weapons'][0]['initial_charges']=value
            with self.subTest(value=value),self.assertRaises(DynamicEncounterInputError):
                parse_dynamic_encounter_request(json.dumps(raw))
        raw=request('trickster_blade')
        raw['party'][0]['equipment']['weapons'][0]['initial_charges']=3
        with self.assertRaises(DynamicEncounterInputError):parse_dynamic_encounter_request(json.dumps(raw))
        raw=request()
        command=parse_dynamic_encounter_request(json.dumps(raw))
        self.assertEqual(json.loads(command.source_json),raw)

    def test_forged_printed_magic_or_ogre_attack_is_rejected(self):
        for kind in ('scarab_knife','dragon_bow','ogre_pistol'):
            with self.subTest(kind=kind):
                command=parse_dynamic_encounter_request(json.dumps(request(kind)))
                source=command.request.space.sample(Random(1))
                document=native(command.request.scenario((source,),'actual-magic'))
                document['scenario']['enemies'][0]['definition']['attacks'][0]['damage']['base']+=1
                with self.assertRaises(PcMeleeInputError):parse_pc_melee_simulation_request(json.dumps(document))

