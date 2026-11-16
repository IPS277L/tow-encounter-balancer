"""Current PC ranged facts, instance source and editable character files."""
from copy import deepcopy
import json
from pathlib import Path
from random import Random
import unittest
from unittest.mock import patch

from towr.adapters.character_files import parse_character_file
from towr.adapters.dynamic_encounter_json import (
    DynamicEncounterInputError,parse_dynamic_encounter_request,
    execute_dynamic_encounter,encode_dynamic_encounter_result,
)
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.adapters.pc_melee_json_errors import PcMeleeInputError


def request(weapon='repeater_pistol'):
    raw=json.loads(Path('docs/examples/dynamic/pc-ranged.request.json').read_text('utf-8'))
    raw['party'][0]['equipment']['weapons'][0]['weapon']=weapon
    if weapon=='repeater_handbow':
        raw['party'][0]['ranged'].update(has_blackpowder_lore=None,has_blackpowder_kit=None)
    return raw


def native(raw):
    command=parse_dynamic_encounter_request(json.dumps(raw))
    scenario=command.request.scenario((command.request.space.sample(Random(42)),),'pc-ranged:replay')
    return dict(schema_version='1',kind='pc_melee_simulation',request_id='pc-ranged',
        ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(scenario),
        simulation=dict(master_seed='42',trials=1),execution=dict(mode='sequential')),scenario


class DynamicPcRangedSourceTests(unittest.TestCase):
    def test_all_three_loadouts_retain_actual_stats_equipment_and_preparation(self):
        for weapon in ('pistol','repeater_pistol','repeater_handbow'):
            raw=request(weapon)
            with self.subTest(weapon=weapon):
                member=parse_dynamic_encounter_request(json.dumps(raw)).request.party[0]
                self.assertEqual(member.policy.value,'automatic_combat')
                self.assertEqual((member.pc.ranged.ballistic_skill,member.pc.ranged.shooting,
                    member.pc.ranged.initiative,member.pc.ranged.dexterity),(3,5,3,4))
                self.assertEqual([item.id for item in member.combat_equipment],['weapon:1','weapon:backup'])
                self.assertEqual([item.location.value for item in member.combat_equipment],['held','carried'])
                self.assertEqual(member.pc.ranged.has_blackpowder_lore,None if weapon=='repeater_handbow' else True)

    def test_character_drafts_preserve_missing_stats_and_unconfirmed_preparation(self):
        player=request()['party'][0]
        del player['characteristics']['ballistic_skill']
        player['ranged']['ammunition_supply_confirmed']=False
        self.assertEqual(parse_character_file(json.dumps(player),'player'),player)
        raw=request();raw['party'][0]=player
        with self.assertRaises(DynamicEncounterInputError):parse_dynamic_encounter_request(json.dumps(raw))

    def test_bad_source_facts_fail_before_any_simulation(self):
        alterations=[('ranged',None),('ranged',dict(initially_loaded=True)),
            ('ranged',dict(initially_loaded=False,ammunition_supply_confirmed=True,has_blackpowder_lore=True,has_blackpowder_kit=True)),
            ('ranged',dict(initially_loaded=True,ammunition_supply_confirmed=True,has_blackpowder_lore=False,has_blackpowder_kit=True))]
        for key,value in alterations:
            raw=request();raw['party'][0][key]=value
            with self.subTest(value=value),patch('towr.application.dynamic_encounter.Random.randint') as roll:
                with self.assertRaises(DynamicEncounterInputError):parse_dynamic_encounter_request(json.dumps(raw))
                roll.assert_not_called()
        for key in ('ballistic_skill','initiative'):
            raw=request();raw['party'][0]['characteristics'][key]=True
            with self.subTest(key=key),self.assertRaises(DynamicEncounterInputError):
                parse_dynamic_encounter_request(json.dumps(raw))

    def test_inactive_character_stats_remain_in_editable_source(self):
        raw=request();player=raw['party'][0]
        player['equipment']['weapons']=[dict(id='sword',weapon='sword',location='left_hand')]
        del player['ranged']
        command=parse_dynamic_encounter_request(json.dumps(raw))
        self.assertEqual(json.loads(command.source_json)['party'][0],player)
        self.assertEqual(parse_character_file(json.dumps(player),'player'),player)
        self.assertIsNone(command.request.party[0].pc.ranged)

    def test_native_roundtrip_has_full_item_identity_and_no_old_policy_aliases(self):
        document,scenario=native(request())
        self.assertEqual(parse_pc_melee_simulation_request(json.dumps(document)).request.scenario,scenario)
        source=document['scenario']['party'][0]
        self.assertEqual(source['combat_equipment'][0],dict(id='weapon:1',weapon='repeater_pistol',location='held',hand='left'))
        self.assertEqual(source['pc']['ranged']['repeater_bonus_policy'],'automatic')
        invalid=deepcopy(document);invalid['scenario']['party'][0]['policy']='automatic_melee'
        with self.assertRaises(PcMeleeInputError):parse_pc_melee_simulation_request(json.dumps(invalid))
        for mode in ('never','when_available'):
            invalid=deepcopy(document)
            invalid['scenario']['party'][0]['pc']['ranged']['repeater_bonus_policy']=mode
            with self.subTest(mode=mode),self.assertRaises(PcMeleeInputError):
                parse_pc_melee_simulation_request(json.dumps(invalid))
        for changes in (dict(combat_equipment=[]),dict(combat_equipment=[dict(source['combat_equipment'][0],id='weapon:backup'),source['combat_equipment'][1]])):
            invalid=deepcopy(document);invalid['scenario']['party'][0].update(changes)
            with self.subTest(changes=changes),self.assertRaises(PcMeleeInputError):
                parse_pc_melee_simulation_request(json.dumps(invalid))


class DynamicPcRangedExecutionTests(unittest.TestCase):
    def test_real_generator_echoes_full_player_source_and_separate_test_counts(self):
        raw=request()
        raw['npc_count']=dict(minimum=1,maximum=1)
        raw['search'].update(exploration_trials=1,finalist_trials=1,max_total_trials=2)
        raw['max_rounds']=3
        command=parse_dynamic_encounter_request(json.dumps(raw))
        result=execute_dynamic_encounter(command)
        report=json.loads(encode_dynamic_encounter_result(command,result))
        self.assertEqual(report['source_request'],raw)
        self.assertEqual(report['total_trials'],2)
        for candidate in report['explored']+report['validations']:
            self.assertEqual([row['actor_id'] for row in candidate['pc_ranged_counts']],['pc'])
            counts=candidate['pc_ranged_counts'][0]
            self.assertLessEqual(counts['bonus_shots'],counts['shots'])
            self.assertLessEqual(counts['bonus_help_tests'],counts['shooting_help_tests'])
            replay=parse_pc_melee_simulation_request(json.dumps(candidate['replay'])).request.scenario
            self.assertEqual(replay.party[0].combat_equipment,command.request.party[0].combat_equipment)
            self.assertEqual(replay.party[0].pc.ranged,command.request.party[0].pc.ranged)


class DynamicPcRangedProcessTests(unittest.TestCase):
    def test_player_inventory_ranged_help_and_reload_state_survive_real_process_trials(self):
        from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
        from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
        from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
        from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
        raw=request();raw['max_rounds']=3
        command=parse_dynamic_encounter_request(json.dumps(raw))
        scenario=command.request.scenario(tuple(command.request.space.sample(Random(seed))
            for seed in (1,2)),'pc-ranged:process')
        source=PcMeleeSimulationRequest(scenario,42,2)
        sequential=run_pc_melee_simulation(source)
        parallel=run_pc_melee_simulation_parallel(source,workers=2,batch_size=1)
        self.assertEqual(sequential,parallel)
        summary=summarize_pc_melee_simulation(parallel)
        self.assertEqual(summary,summarize_pc_melee_simulation(sequential))
        self.assertEqual([row.actor_id for row in summary.pc_ranged_counts],['pc'])
        self.assertEqual(summary.source_request.scenario.party[0].combat_equipment,
            command.request.party[0].combat_equipment)


if __name__=='__main__':
    unittest.main()
