"""Full generated Shooting sources through current JSON and character files."""
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.armour_fixtures import light_loadout
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
from random import Random
import unittest
from unittest.mock import patch

from towr.adapters.character_files import parse_character_file
from towr.adapters.dynamic_encounter_json import (
    validate_dynamic_encounter_document,
    DynamicEncounterInputError, parse_dynamic_encounter_request,
    execute_dynamic_encounter, encode_dynamic_encounter_result,
)
from towr.adapters._pc_melee_scenario_json import scenario_document,generated_components_document
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.adapters.pc_melee_json_errors import PcMeleeInputError
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon, GeneratedRangedFacts


WEAPONS=('pistol','repeater_pistol','repeater_handbow')


def ranged_request(weapon='pistol'):
    raw=json.loads(Path('docs/examples/dynamic/ranged.request.json').read_text('utf-8'))
    raw['party']=raw['party'][:1]
    raw['max_rounds']=2
    raw['targets']['started_rounds']=dict(numerator=1,denominator=1)
    raw['npc_count']=dict(minimum=1,maximum=1)
    raw['search'].update(exploration_trials=1,finalist_trials=1,max_total_trials=2)
    raw['search_space'].update(weapon_count=[1],weapon=[weapon],shield=[None],allowed_talents=[],
        ballistic_skill=[2],shooting=[3],initiative=[4],dexterity=[5])
    return raw


def character(weapon):
    firearm=weapon!='repeater_handbow'
    return GeneratedNpc(3,4,5,2,3,4,initial_generated_weapons(GeneratedWeapon(weapon)),light_loadout(light=False, shield=False),defence=5,
        ranged=GeneratedRangedFacts(2,3,True,True if firearm else None,True if firearm else None), initiative=4, dexterity=5)


def native_document(raw):
    command=parse_dynamic_encounter_request(json.dumps(raw))
    npc=command.request.space.sample(Random(42))
    scenario=command.request.scenario((npc,),'ranged:replay')
    return dict(schema_version='1',kind='pc_melee_simulation',request_id='ranged:test',
        ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(scenario),
        simulation=dict(master_seed='42',trials=1),execution=dict(mode='sequential')),scenario


class GeneratedRangedJsonTests(unittest.TestCase):
    def test_character_files_keep_exact_conditional_component_and_arbitrary_stats(self):
        for weapon in WEAPONS:
            raw=generated_components_document(character(weapon))
            raw=json.loads(json.dumps(raw))
            with self.subTest(weapon=weapon):
                self.assertEqual(parse_character_file(json.dumps(raw),'npc'),raw)
                self.assertEqual(raw['ranged']['ballistic_skill'],2)
                self.assertEqual(raw['initiative'],4)
                self.assertEqual(raw['dexterity'],5)

    def test_character_files_reject_missing_false_and_foreign_ranged_facts(self):
        changes=[lambda n:n.pop('ranged'),lambda n:n.update(ranged=None),
            lambda n:n['armour'].update(shield=1),lambda n:n['ranged'].update(shooting=True),
            lambda n:n['weapons'][0].update(initially_loaded=1),
            lambda n:n['ranged'].update(ammunition_supply_confirmed=False),
            lambda n:n['ranged'].update(has_blackpowder_kit=False),
            lambda n:n['ranged'].update(has_blackpowder_lore=None),
            lambda n:n['ranged'].update(untracked_bonus=2),
            lambda n:n['weapons'][0].update(weapon='staff')]
        for change in changes:
            raw=json.loads(json.dumps(generated_components_document(character('pistol'))))
            change(raw)
            with self.subTest(raw=raw),self.assertRaises(DynamicEncounterInputError):
                parse_character_file(json.dumps(raw),'npc')
        raw=json.loads(json.dumps(generated_components_document(character('repeater_handbow'))))
        raw['ranged']['has_blackpowder_lore']=True
        with self.assertRaises(DynamicEncounterInputError):
            parse_character_file(json.dumps(raw),'npc')

    def test_all_native_profiles_roundtrip_full_source_and_closed_ranged_descriptor(self):
        for weapon in WEAPONS:
            raw,scenario=native_document(ranged_request(weapon))
            with self.subTest(weapon=weapon):
                enemy=raw['scenario']['enemies'][0]
                self.assertIn('ranged',enemy)
                self.assertNotIn('pistol',enemy)
                self.assertEqual(enemy['definition']['attacks'][0]['skill'],'shooting')
                self.assertEqual(enemy['definition']['attacks'][0]['ignores_armour'],weapon!='repeater_handbow')
                self.assertEqual(parse_pc_melee_simulation_request(json.dumps(raw)).request.scenario,scenario)
                self.assertEqual(enemy['definition']['generated_components']['dexterity'],5)

    def test_native_rejects_component_derived_forgeries_old_key_and_disagreeing_facts(self):
        changes=[lambda e:e.update(pistol=e.pop('ranged')),
            lambda e:e['definition']['attacks'][0]['test_profile'].update(dice=9),
            lambda e:e['definition']['attacks'][0].update(ignores_armour=False),
            lambda e:e['definition']['generated_components'].update(ranged=None),
            lambda e:e['ranged'].update(has_blackpowder_kit=None),
            lambda e:e.update(holds_shield=True)]
        for change in changes:
            raw,_=native_document(ranged_request())
            change(raw['scenario']['enemies'][0])
            with self.subTest(change=change),self.assertRaises(PcMeleeInputError):
                parse_pc_melee_simulation_request(json.dumps(raw))

    def test_manual_ranges_are_current_closed_inputs_and_fail_before_trials(self):
        for field,value in [('ballistic_skill',[True]),('initiative',[]),('shooting',[7]),
                ('dexterity',[2,2]),('weapon',['unknown'])]:
            raw=ranged_request()
            raw['search_space'][field]=value
            with self.subTest(field=field),patch('towr.application.dynamic_encounter.search_dynamic_encounter') as run:
                with self.assertRaises(DynamicEncounterInputError):
                    parse_dynamic_encounter_request(json.dumps(raw))
                run.assert_not_called()
        raw=ranged_request()
        del raw['search_space']['dexterity']
        with self.assertRaises(DynamicEncounterInputError):
            parse_dynamic_encounter_request(json.dumps(raw))

    def test_real_dynamic_result_keeps_components_character_and_executable_replay(self):
        raw=ranged_request('repeater_handbow')
        command=parse_dynamic_encounter_request(json.dumps(raw))
        result=execute_dynamic_encounter(command)
        report=json.loads(encode_dynamic_encounter_result(command,result))
        self.assertEqual(report['source_request'],raw)
        self.assertEqual(report['total_trials'],2)
        for candidate in report['explored']+report['validations']:
            npc=candidate['npcs'][0]
            self.assertEqual(npc['weapons'][0]['weapon'],'repeater_handbow')
            self.assertEqual([row['actor_id'] for row in candidate['npc_ranged_counts']],
                ['generated-npc:1'])
            self.assertTrue(all(row['bonus_shots']<=row['shots'] for row in candidate['npc_ranged_counts']))
            missing=deepcopy(report)
            del missing['explored'][0]['npc_ranged_counts']
            from jsonschema.exceptions import ValidationError
            with self.assertRaises(ValidationError):
                validate_dynamic_encounter_document(missing,'result')
            self.assertEqual(candidate['replay']['scenario']['enemies'][0]['definition']['generated_components'],npc)
            self.assertEqual(parse_character_file(json.dumps(npc),'npc'),npc)
            replay=parse_pc_melee_simulation_request(json.dumps(candidate['replay'])).request.scenario
            self.assertEqual(replay.enemies[0].definition.generated_components.dexterity,5)


class GeneratedRangedProcessTests(unittest.TestCase):
    def test_mixed_component_source_counts_and_real_reload_survive_process_transport(self):
        from dataclasses import replace
        from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
        from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
        from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
        from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation

        raw=ranged_request()
        raw['party'][0]['characteristics'].update(strength=1,toughness=20)
        raw['max_rounds']=4
        command=parse_dynamic_encounter_request(json.dumps(raw))
        melee=GeneratedNpc(2,1,8,2,3,3,initial_generated_weapons(GeneratedWeapon.STAFF),light_loadout(light=False, shield=False),defence=3)
        from towr.domain.weapon_inventory_models import WeaponItemSource,WeaponItemLocation
        from towr.domain.weapon_catalog import WeaponKind
        shooters=tuple(character(w) for w in WEAPONS)
        first_shooter=replace(shooters[0],weapons=(*shooters[0].weapons,
            WeaponItemSource('carried-empty-pistol',WeaponKind.PISTOL,WeaponItemLocation.CARRIED,None,
                initially_loaded=False)))
        scenario=command.request.scenario((first_shooter,*shooters[1:],melee),'mixed:ranged:process')
        request=PcMeleeSimulationRequest(scenario,42,2)
        sequential=run_pc_melee_simulation(request)
        parallel=run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(sequential,parallel)
        first=summarize_pc_melee_simulation(sequential)
        second=summarize_pc_melee_simulation(parallel)
        self.assertEqual(first,second)
        self.assertEqual([row.actor_id for row in second.npc_ranged_counts],
            ['generated-npc:1','generated-npc:2','generated-npc:3'])
        self.assertGreater(sum(row.reload_actions for row in second.npc_ranged_counts),0)
        self.assertTrue(all(row.shots>0 for row in second.npc_ranged_counts))
        self.assertEqual(second.source_request.scenario.enemies[3].definition.generated_components,melee)
        self.assertEqual(second.source_request.scenario.enemies[0].definition.generated_components.weapons,first_shooter.weapons)
        self.assertFalse(second.source_request.scenario.enemies[0].definition.generated_components.weapons[1].initially_loaded)


if __name__=='__main__':
    unittest.main()
