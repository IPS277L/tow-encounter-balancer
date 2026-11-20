"""Whole-inventory Shooting source admission; no Monte Carlo or combat runs."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.character_files import parse_character_file
from towr.adapters.dynamic_encounter_json import DynamicEncounterInputError,parse_dynamic_encounter_request
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.adapters.pc_melee_json_errors import PcMeleeInputError
from towr.domain.pc_battlefield_models import PcBattlefieldSpec
from towr.domain.pc_combat_equipment_models import PcWeaponItem,PcItemLocation
from towr.domain.pc_melee_models import (
    PcMeleePolicy,PcMeleeWeapon as W,PcWeaponHand as H,PcRangedProfile,
    PcRangedReloadHandPolicy,PcRepeaterBonusPolicy,
)
from towr.domain.pc_weapon_inventory import initial_pc_weapon_inventory
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.test_models import Skill


def profile(*,repeater=False):
    return PcRangedProfile(3, 5,  has_blackpowder_lore=True, has_blackpowder_kit=True, ammunition_supply_confirmed=True, reload_hand_policy=PcRangedReloadHandPolicy.TWO_AVAILABLE_HANDS, repeater_bonus_policy=PcRepeaterBonusPolicy.AUTOMATIC if repeater else None)


def native_document(*,extra=(),facts=None,primary=W.SWORD,policy=PcMeleePolicy.AUTOMATIC_COMBAT,
        include_pistol=True,initiative=3,awareness=None,dexterity=4):
    source=make_pc_melee_scenario(max_rounds=1)
    items=(PcWeaponItem('primary',primary,PcItemLocation.HELD,H.LEFT,
        initially_loaded=True if primary is W.PISTOL else None),
        *((PcWeaponItem('pistol',W.PISTOL,PcItemLocation.CARRIED,None,initially_loaded=False),)
            if include_pistol else ()),*extra)
    member=source.party[0]
    member=replace(member,pc=replace(member.pc,weapon=primary,strength=5,ranged=profile() if facts is None else facts,initiative=initiative,awareness=awareness,dexterity=dexterity),
        policy=policy,combat_equipment=items)
    enemy=source.enemies[0]
    enemy=replace(enemy,definition=replace(enemy.definition,
        protection=(replace(enemy.definition.protection[0],skill=Skill.ATHLETICS),)))
    battlefield=(PcBattlefieldSpec(RangedWeaponRange.CLOSE,RangedWeaponRange.LONG)
        if policy is PcMeleePolicy.AUTOMATIC_COMBAT else None)
    source=replace(source,party=(member,),enemies=(enemy,),battlefield=battlefield,
        facts=replace(source.facts,can_leave_zone=battlefield is not None))
    return dict(schema_version='1',kind='pc_melee_simulation',request_id='inventory-source',
        ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(source),
        simulation=dict(master_seed='42',trials=1),execution=dict(mode='sequential'))


def dynamic_document():
    raw=json.loads(Path('docs/examples/dynamic/search.request.json').read_text('utf-8'))
    player=raw['party'][0]
    player['characteristics'].update(ballistic_skill=3,initiative=3,strength=5)
    player['skills'].update(shooting=5,dexterity=4)
    player['equipment']['weapons']=[
        dict(id='primary',weapon='sword',location='left_hand'),
        dict(id='pistol',weapon='pistol',location='carried',initially_loaded=False)]
    player['equipment']['armour']=[]
    player['ranged']=dict(ammunition_supply_confirmed=True,has_blackpowder_lore=True,has_blackpowder_kit=True)
    return raw


class InventorySourceAdapterTests(unittest.TestCase):
    def test_current_schemas_are_valid_draft_2020_12(self):
        for name in ('pc-melee-common','dynamic-encounter-common'):
            Draft202012Validator.check_schema(json.loads(Path(
                'src/towr/adapters/schemas/'+name+'.schema.json').read_text('utf-8')))

    def test_melee_primary_and_carried_empty_pistol_roundtrip_without_actor_charge(self):
        raw=native_document()
        command=parse_pc_melee_simulation_request(json.dumps(raw))
        member=command.request.scenario.party[0]
        self.assertIs(member.pc.weapon,W.SWORD)
        self.assertEqual(member.pc.ranged.ballistic_skill,3)
        self.assertNotIn('initially_loaded',raw['scenario']['party'][0]['pc']['ranged'])
        self.assertEqual(scenario_document(command.request.scenario),raw['scenario'])
        inventory=initial_pc_weapon_inventory(member)
        self.assertIsNone(inventory.items[0].reload)
        self.assertFalse(inventory.items[1].reload.loaded)
        self.assertIs(inventory.items[1].source.initially_loaded,False)

    def test_union_of_bow_firearm_and_repeater_facts_is_independent_of_primary(self):
        extra=(PcWeaponItem('bow',W.SHORTBOW,PcItemLocation.CARRIED,None),
            PcWeaponItem('handbow',W.REPEATER_HANDBOW,PcItemLocation.CARRIED,None,initially_loaded=True))
        raw=native_document(extra=extra,facts=profile(repeater=True))
        parsed=parse_pc_melee_simulation_request(json.dumps(raw)).request.scenario
        member=parsed.party[0]
        self.assertEqual(len(member.combat_equipment),4)
        self.assertIs(member.pc.ranged.repeater_bonus_policy,PcRepeaterBonusPolicy.AUTOMATIC)
        self.assertIs(member.pc.ranged.has_blackpowder_lore,True)
        inventory=initial_pc_weapon_inventory(member)
        self.assertEqual([None if item.reload is None else item.reload.loaded for item in inventory.items],
            [None,False,None,True])
        self.assertEqual(scenario_document(parsed),raw['scenario'])

    def test_manual_shooting_also_requires_all_explicit_item_sources(self):
        raw=native_document(primary=W.PISTOL,policy=PcMeleePolicy.ATTACK_OR_RECOVER_SELF)
        self.assertIs(parse_pc_melee_simulation_request(json.dumps(raw)).request.scenario.party[0].policy,
            PcMeleePolicy.ATTACK_OR_RECOVER_SELF)
        del raw['scenario']['party'][0]['combat_equipment']
        with self.assertRaises(PcMeleeInputError):
            parse_pc_melee_simulation_request(json.dumps(raw))

    def test_carried_hochland_requires_awareness_and_complete_union(self):
        extra=(PcWeaponItem('hochland',W.HOCHLAND_LONG_RIFLE,PcItemLocation.CARRIED,None,initially_loaded=False),)
        raw=native_document(extra=extra,facts=profile(),awareness=4)
        parsed=parse_pc_melee_simulation_request(json.dumps(raw)).request.scenario
        self.assertEqual(parsed.party[0].pc.awareness,4)
        del raw['scenario']['party'][0]['pc']['awareness']
        with self.assertRaises(PcMeleeInputError):
            parse_pc_melee_simulation_request(json.dumps(raw))

    def test_free_bow_inventory_needs_no_reload_or_firearm_facts_but_allows_aim(self):
        for aim in (False,True):
            with self.subTest(aim=aim):
                facts=PcRangedProfile(3, 5, ammunition_supply_confirmed=True)
                raw=native_document(include_pistol=False,facts=facts,initiative=3 if aim else None,awareness=4 if aim else None,dexterity=None,
                    extra=(PcWeaponItem('bow',W.SHORTBOW,PcItemLocation.CARRIED,None),))
                parsed=parse_pc_melee_simulation_request(json.dumps(raw)).request.scenario
                self.assertEqual(parsed.party[0].pc.ranged,facts)
                wire=raw['scenario']['party'][0]['pc']['ranged']
                self.assertFalse(set(wire)&{'dexterity','reload_hand_policy','has_blackpowder_lore',
                    'has_blackpowder_kit','repeater_bonus_policy','initially_loaded'})
                if not aim:
                    self.assertEqual(set(wire),{'ballistic_skill','shooting','ammunition_supply_confirmed'})
                invalid=deepcopy(raw)
                invalid['scenario']['party'][0]['pc'].update(initiative=3,dexterity=4)
                prepared=parse_pc_melee_simulation_request(json.dumps(invalid)).request.scenario
                self.assertEqual(prepared.party[0].pc.dexterity,4)

    def test_dynamic_melee_primary_keeps_carried_charge_and_actor_preparation(self):
        raw=dynamic_document()
        command=parse_dynamic_encounter_request(json.dumps(raw))
        self.assertEqual(json.loads(command.source_json),raw)
        member=command.request.party[0]
        self.assertIs(member.pc.weapon,W.SWORD)
        self.assertEqual(member.pc.dexterity,4)
        self.assertFalse(initial_pc_weapon_inventory(member).items[1].reload.loaded)
        player=raw['party'][0]
        self.assertEqual(parse_character_file(json.dumps(player),'player'),player)

    def test_dynamic_free_bow_and_optional_aim_do_not_activate_exacting(self):
        raw=dynamic_document();player=raw['party'][0]
        player['equipment']['weapons'][1]=dict(id='bow',weapon='shortbow',location='carried')
        player['ranged'].update(has_blackpowder_lore=None,has_blackpowder_kit=None)
        member=parse_dynamic_encounter_request(json.dumps(raw)).request.party[0]
        self.assertEqual(member.pc.initiative,3)
        self.assertEqual(member.pc.dexterity,4)
        self.assertIsNone(member.pc.ranged.reload_hand_policy)
        player['skills']['awareness']=4
        member=parse_dynamic_encounter_request(json.dumps(raw)).request.party[0]
        self.assertEqual((member.pc.initiative,member.pc.awareness),(3,4))
        self.assertEqual(member.pc.dexterity,4)

    def test_dynamic_net_and_shooting_share_ballistic_skill_without_consuming_it(self):
        raw=dynamic_document();player=raw['party'][0]
        player['equipment']['weapons'].append(dict(id='net',weapon='weighted_net',location='carried'))
        player['skills']['throwing']=5
        member=parse_dynamic_encounter_request(json.dumps(raw)).request.party[0]
        self.assertEqual((member.pc.ballistic_skill,member.pc.ranged.ballistic_skill),(3,3))
        self.assertEqual(member.pc.throwing,5)
        self.assertEqual(tuple(item.weapon for item in member.combat_equipment),(W.SWORD,W.PISTOL,W.WEIGHTED_NET))

    def test_actor_loaded_and_missing_or_invalid_item_charge_have_no_fallback(self):
        with patch('towr.rules.test_resolution.roll_test_initial') as roll,patch(
                'towr.adapters.dynamic_encounter_json.search_dynamic_encounter') as search:
            for value in (None,1,'false'):
                native=native_document()
                native['scenario']['party'][0]['combat_equipment'][1]['initially_loaded']=value
                dynamic=dynamic_document()
                dynamic['party'][0]['equipment']['weapons'][1]['initially_loaded']=value
                with self.subTest(value=value):
                    with self.assertRaises(PcMeleeInputError):parse_pc_melee_simulation_request(json.dumps(native))
                    with self.assertRaises(DynamicEncounterInputError):parse_dynamic_encounter_request(json.dumps(dynamic))
            native=native_document();del native['scenario']['party'][0]['combat_equipment'][1]['initially_loaded']
            with self.assertRaises(PcMeleeInputError):parse_pc_melee_simulation_request(json.dumps(native))
            dynamic=dynamic_document();del dynamic['party'][0]['equipment']['weapons'][1]['initially_loaded']
            with self.assertRaises(DynamicEncounterInputError):parse_dynamic_encounter_request(json.dumps(dynamic))
            native=native_document();native['scenario']['party'][0]['pc']['ranged']['initially_loaded']=True
            with self.assertRaises(PcMeleeInputError):parse_pc_melee_simulation_request(json.dumps(native))
            dynamic=dynamic_document();dynamic['party'][0]['ranged']['initially_loaded']=True
            with self.assertRaises(DynamicEncounterInputError):parse_dynamic_encounter_request(json.dumps(dynamic))
            for location in ('dropped','deployed','spent'):
                native=native_document()
                native['scenario']['party'][0]['combat_equipment'][1]['location']=location
                dynamic=dynamic_document()
                dynamic['party'][0]['equipment']['weapons'][1]['location']=location
                with self.subTest(location=location):
                    with self.assertRaises(PcMeleeInputError):parse_pc_melee_simulation_request(json.dumps(native))
                    with self.assertRaises(DynamicEncounterInputError):parse_dynamic_encounter_request(json.dumps(dynamic))
            roll.assert_not_called();search.assert_not_called()


if __name__=='__main__':unittest.main()
