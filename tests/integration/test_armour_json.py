"""Current armour source admission, character files and native replay roundtrip."""
from tests.support.generated_weapon_sources import initial_generated_weapons
from copy import deepcopy
from dataclasses import asdict
import json
from importlib import import_module
from pathlib import Path
import unittest

from towr.adapters.character_files import parse_character_file
from towr.adapters.dynamic_encounter_json import (
    DynamicEncounterInputError, parse_dynamic_encounter_request, validate_dynamic_encounter_document,
)
from towr.adapters._pc_melee_scenario_json import scenario_document,generated_components_document
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.adapters.pc_melee_json_errors import PcMeleeInputError
from towr.domain.armour_models import ArmourLoadout, BodyArmour, HelmetKind, ShieldKind
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon


def armour_document(body=(), benefit=None, *, helmet=None, shield=None, barding=False):
    return dict(body=list(body), benefit=benefit, helmet=helmet, shield=shield, barding=barding)


def request_document():
    return dict(schema_version='1', kind='dynamic_encounter_search', request_id='armour:wire',
        ruleset='towr-pg1.4-gmg1.1', party=[dict(actor_id='pc',
            characteristics=dict(weapon_skill=3, strength=3, toughness=3, agility=3),
            skills=dict(melee=5, defence=5, athletics=4, endurance=4),
            equipment=dict(weapons=[dict(id='weapon:1', weapon='sword', location='left_hand')], armour=[]),
            talents=[], resources=dict(fate=2), consumables=[])],
        search_space=dict(weapon_skill=[3], strength=[3], toughness=[3], agility=[3], melee=[4],
            defence=[4], athletics=[4], weapon=['sword'], armour=[None, 'heavy_armour'],
            shield=[None], abilities=[[]], allowed_talents=[], ballistic_skill=[3],
            initiative=[3], shooting=[4], dexterity=[4]),
        npc_count=dict(minimum=1, maximum=1),
        targets=dict(win_rate=dict(numerator=1, denominator=2), started_rounds=dict(numerator=2, denominator=1)),
        search=dict(master_seed='42', max_candidates=1, exploration_trials=1, finalist_trials=1,
            top_k=1, max_total_trials=2), max_rounds=3, defeat_disposition='killed',
        execution=dict(mode='sequential'), scene=dict(range='close', two_handed_max_range='long',
            ambush='none', terrain='open', session_start='fresh'))


def npc_document(armour, **kwargs):
    source = GeneratedNpc(3, 4, 3, 2, 4, 3, initial_generated_weapons(GeneratedWeapon.SWORD), armour, defence=5, **kwargs)
    return json.loads(json.dumps(generated_components_document(source)))


def native_armour_document(armour, strength):
    document=request_document()
    document['search_space'].update(weapon_count=[1],strength=[strength],
        armour=[None if armour.benefit is None else armour.benefit.value],
        secondary_armour=[next((body.value for body in armour.body if body is not armour.benefit),None)])
    command=parse_dynamic_encounter_request(json.dumps(document))
    npc=GeneratedNpc(3,strength,3,3,4,4,initial_generated_weapons(GeneratedWeapon.SWORD),armour,defence=4)
    source=command.request.scenario((npc,),'armour:initial-condition')
    replay=dict(schema_version='1',kind='pc_melee_simulation',request_id='armour:initial-condition',
        ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(source),
        simulation=dict(master_seed='42',trials=1),execution=dict(mode='sequential'))
    return replay,source


class ArmourJsonTests(unittest.TestCase):
    def test_native_roundtrip_derives_only_the_actual_initial_armour_burden(self):
        cases=((ArmourLoadout(),2,False),
            (ArmourLoadout((BodyArmour.HEAVY,),BodyArmour.HEAVY),2,True),
            (ArmourLoadout((BodyArmour.HEAVY,),BodyArmour.HEAVY),3,False),
            (ArmourLoadout((BodyArmour.FULL_PLATE,),BodyArmour.FULL_PLATE),3,True),
            (ArmourLoadout((BodyArmour.FULL_PLATE,),BodyArmour.FULL_PLATE),4,False),
            (ArmourLoadout((BodyArmour.ITHILMAR,BodyArmour.HEAVY),BodyArmour.ITHILMAR),2,True))
        for armour,strength,burdened in cases:
            with self.subTest(armour=armour,strength=strength):
                document,source=native_armour_document(armour,strength)
                parsed=parse_pc_melee_simulation_request(json.dumps(document)).request.scenario
                self.assertEqual(parsed,source)
                expected=frozenset((Condition.BURDENED,)) if burdened else frozenset()
                self.assertEqual(parsed.enemies[0].state.injury.conditions.conditions,expected)

    def test_native_armour_roundtrip_rejects_forged_derived_or_initial_state_facts(self):
        document,_=native_armour_document(
            ArmourLoadout((BodyArmour.FULL_PLATE,),BodyArmour.FULL_PLATE),3)
        invalid=deepcopy(document)
        invalid['scenario']['enemies'][0]['definition']['resilience']['bonus']-=1
        with self.assertRaises(PcMeleeInputError):
            parse_pc_melee_simulation_request(json.dumps(invalid))
        invalid=deepcopy(document)
        invalid['scenario']['enemies'][0]['initial_conditions']=[]
        with self.assertRaises(PcMeleeInputError):
            parse_pc_melee_simulation_request(json.dumps(invalid))

    def test_airspace_is_an_explicit_optional_scene_fact(self):
        document=request_document()
        self.assertIsNone(parse_dynamic_encounter_request(json.dumps(document)).request.battlefield.airspace)
        document['scene']['airspace']=dict(open_sky_confirmed=True,fall_hazard_rating=3)
        command=parse_dynamic_encounter_request(json.dumps(document))
        self.assertEqual(command.request.battlefield.airspace.fall_hazard_rating,3)
        self.assertEqual(json.loads(command.source_json)['scene']['airspace'],document['scene']['airspace'])
        document['scene']['airspace']=None
        self.assertIsNone(parse_dynamic_encounter_request(json.dumps(document)).request.battlefield.airspace)

    def test_airspace_native_roundtrip_preserves_rating_and_sky_confirmation(self):
        document=request_document()
        document['scene']['airspace']=dict(open_sky_confirmed=True,fall_hazard_rating=2)
        command=parse_dynamic_encounter_request(json.dumps(document))
        source=command.request.scenario((GeneratedNpc(3,3,3,3,4,4,
            initial_generated_weapons(GeneratedWeapon.SWORD),ArmourLoadout(),defence=4),),'sky:replay')
        replay=dict(schema_version='1',kind='pc_melee_simulation',request_id='sky:replay',
            ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(source),
            simulation=dict(master_seed='42',trials=1),execution=dict(mode='sequential'))
        actual=parse_pc_melee_simulation_request(json.dumps(replay))
        self.assertEqual(actual.request.scenario.battlefield,source.battlefield)

    def test_airspace_rejects_invented_or_incomplete_gm_facts(self):
        for airspace in ({'open_sky_confirmed':False,'fall_hazard_rating':2},
                {'open_sky_confirmed':True,'fall_hazard_rating':True},
                {'open_sky_confirmed':True,'fall_hazard_rating':0},
                {'open_sky_confirmed':True},
                {'open_sky_confirmed':True,'fall_hazard_rating':2,'free_flight':True}):
            document=request_document();document['scene']['airspace']=airspace
            with self.subTest(airspace=airspace),self.assertRaises(DynamicEncounterInputError):
                parse_dynamic_encounter_request(json.dumps(document))

    def test_agilulf_code_confirmation_cannot_authorise_surrender(self):
        document=request_document()
        document['search_space']['armour']=['armour_of_agilulf']
        document['search_space']['agilulf_code_confirmed']=True
        document['defeat_disposition']='disarmed_and_surrendered'
        with self.assertRaises(DynamicEncounterInputError):
            parse_dynamic_encounter_request(json.dumps(document))
        for disposition in ('killed','knocked_out'):
            document['defeat_disposition']=disposition
            with self.subTest(disposition=disposition):
                self.assertIsNotNone(parse_dynamic_encounter_request(json.dumps(document)).request)

    def test_layered_player_inventory_compiles_and_native_replay_preserves_sources(self):
        document = request_document()
        gear = document['party'][0]['equipment']
        gear['armour'] = [dict(id='mail', kind='heavy_armour', location='worn'),
            dict(id='mantle', kind='mantle_of_ithilmar', location='worn'),
            dict(id='helm', kind='helm_of_the_hunt', location='worn')]
        gear['armour_benefit_id'] = 'mantle'
        command = parse_dynamic_encounter_request(json.dumps(document))
        member = command.request.party[0]
        self.assertEqual(member.armour.body, (BodyArmour.HEAVY, BodyArmour.ITHILMAR))
        self.assertIs(member.armour.benefit, BodyArmour.ITHILMAR)
        self.assertIs(member.armour.helmet, HelmetKind.HUNT)
        self.assertEqual(member.pc.armour_bonus, 4)
        self.assertTrue(member.armour_worn)
        self.assertEqual(json.loads(command.source_json)['party'][0]['equipment'], gear)
        source = command.request.scenario((GeneratedNpc(3, 3, 3, 3, 4, 4,
            initial_generated_weapons(GeneratedWeapon.SWORD), ArmourLoadout(), defence=4),), 'armour:replay')
        replay = dict(schema_version='1', kind='pc_melee_simulation', request_id='armour:replay',
            ruleset='towr-pg1.4-gmg1.1', scenario=scenario_document(source),
            simulation=dict(master_seed='42', trials=1), execution=dict(mode='sequential'))
        reparsed = parse_pc_melee_simulation_request(json.dumps(replay))
        self.assertEqual(reparsed.request.scenario, source)

    def test_player_files_keep_all_armour_rows_and_benefit_instance_id(self):
        player = request_document()['party'][0]
        player['equipment']['armour'] = [dict(id='plate', kind='full_plate_armour', location='worn'),
            dict(id='magic', kind='armour_of_meteoric_iron', location='worn'),
            dict(id='roots', kind='briarroot_shield', location='carried'),
            dict(id='barding', kind='barding', location='carried')]
        player['equipment']['armour_benefit_id'] = 'magic'
        self.assertEqual(parse_character_file(json.dumps(player), 'player'), player)

    def test_each_body_armour_and_both_shields_survive_individual_npc_files(self):
        for body in BodyArmour:
            for shield in (None, *ShieldKind):
                with self.subTest(body=body, shield=shield):
                    source = ArmourLoadout((body,), body, HelmetKind.HUNT, shield)
                    npc = npc_document(source, agilulf_code_confirmed=True if body is BodyArmour.AGILULF else None)
                    self.assertEqual(parse_character_file(json.dumps(npc), 'npc'), npc)

    def test_old_flat_equipment_keys_and_partial_loadouts_are_rejected(self):
        npc = npc_document(ArmourLoadout())
        for change in (dict(light_armour=True), dict(shield=False),
                dict(armour={}), dict(armour={**npc['armour'], 'extra': 1}),
                dict(armour={**npc['armour'], 'benefit': 'heavy_armour'})):
            with self.subTest(change=change), self.assertRaises(DynamicEncounterInputError):
                parse_character_file(json.dumps(dict(npc, **change)), 'npc')

    def test_inactive_agilulf_still_requires_code_confirmation(self):
        npc = npc_document(ArmourLoadout((BodyArmour.LIGHT, BodyArmour.AGILULF), BodyArmour.LIGHT),
            agilulf_code_confirmed=True)
        self.assertEqual(parse_character_file(json.dumps(npc), 'npc'), npc)
        for confirmation in (None, False, 1):
            invalid = dict(npc, agilulf_code_confirmed=confirmation)
            with self.subTest(confirmation=confirmation), self.assertRaises(DynamicEncounterInputError):
                parse_character_file(json.dumps(invalid), 'npc')

    def test_barding_requires_actual_mount_and_rider_benefits_keep_species_limits(self):
        npc = npc_document(ArmourLoadout())
        npc['armour']['barding'] = True
        with self.assertRaises(DynamicEncounterInputError):
            parse_character_file(json.dumps(npc), 'npc')
        npc['mount'] = 'pegasus'
        npc['rider_kind'] = 'elf'
        self.assertEqual(parse_character_file(json.dumps(npc), 'npc'), npc)
        npc['mount'] = 'demigryph'
        with self.assertRaises(DynamicEncounterInputError):
            parse_character_file(json.dumps(npc), 'npc')
        npc['rider_kind'] = 'human'
        self.assertEqual(parse_character_file(json.dumps(npc), 'npc'), npc)

    def test_search_space_uses_item_kinds_and_rejects_old_boolean_armour(self):
        document = request_document()
        document['search_space'].update(secondary_armour=[None], helmet=[None, 'helmet'],
            shield=[None, 'briarroot_shield'], barding=[False, True], mount=[None, 'elven_steed'],
            rider_kind=['human', 'elf', 'other'], agilulf_code_confirmed=None)
        command = parse_dynamic_encounter_request(json.dumps(document))
        self.assertIn(BodyArmour.HEAVY, command.request.space.armour)
        self.assertEqual(command.request.space.shield, (None, ShieldKind.BRIARROOT))
        invalid = deepcopy(document)
        invalid['search_space']['light_armour'] = [False, True]
        with self.assertRaises(DynamicEncounterInputError):
            parse_dynamic_encounter_request(json.dumps(invalid))
        validate_dynamic_encounter_document(document)

    def test_generic_resilience_ward_survives_all_current_numeric_source_families(self):
        cases = (
            ('ranged', 'docs/examples/m4/ranged-v1.request.json'),
            ('melee', 'docs/examples/m6/json/melee-simulation-v1.request.json'),
            ('mixed', 'docs/examples/m7/json/mixed-simulation-v1.request.json'),
            ('magic', 'docs/examples/m8/json/magic-simulation-v6.request.json'),
        )
        for family, path in cases:
            with self.subTest(family=family):
                module = import_module('towr.adapters.'+family+'_simulation_json')
                parse = getattr(module, 'parse_'+family+'_simulation_request')
                document = json.loads(Path(path).read_text(encoding='utf8'))
                document['scenario']['definitions'][0]['resilience']['mundane_armour_ward'] = True
                command = parse(json.dumps(document))
                encoded = module._request_document(command)
                self.assertIs(encoded['scenario']['definitions'][0]['resilience']['mundane_armour_ward'], True)
                self.assertEqual(parse(json.dumps(encoded)), command)


if __name__ == '__main__':
    unittest.main()
