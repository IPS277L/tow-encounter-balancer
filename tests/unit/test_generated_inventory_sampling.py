"""Finite generated inventories retain their physical sources and union facts."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from random import Random
import unittest

from towr.application.dynamic_encounter import NpcSearchSpace
from towr.adapters._pc_melee_scenario_json import generated_components_document,parse_generated_components
from towr.adapters.character_files import parse_character_file
from towr.adapters.dynamic_encounter_json import DynamicEncounterInputError,parse_dynamic_encounter_request
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.adapters.pc_melee_json_errors import PcMeleeInputError
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.domain.armour_models import BodyArmour,ShieldKind
from towr.domain.generated_npc_models import GeneratedWeapon,GeneratedNpc
from towr.domain.ranged_weapon_profiles import RangedWeaponHands
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_inventory_models import WeaponItemLocation,WeaponGrip


def space(**changes):
    return NpcSearchSpace(**(dict(weapon_skill=(3,),strength=(3,),toughness=(3,),agility=(3,),
        melee=(4,),athletics=(4,),defence=(4,),brawn=(4,),weapon=(GeneratedWeapon.SWORD,),
        armour=(None,),shield=(None,),helmet=(None,),allowed_talents=(),
        ballistic_skill=(3,),shooting=(4,),initiative=(3,),dexterity=(4,),awareness=(4,))|changes))


class ChooseCandidate(Random):
    def __init__(self,predicate):
        super().__init__(0)
        self.predicate=predicate

    def choice(self,values):
        if values and type(values[0]) is GeneratedNpc:
            return next(value for value in values if self.predicate(value))
        return super().choice(values)


class GeneratedInventorySamplingTests(unittest.TestCase):
    def test_defaults_sample_each_count_with_stable_distinct_ids(self):
        allowed=space()
        members=[allowed.sample(Random(seed)) for seed in range(12)]
        self.assertEqual({len(member.weapons) for member in members},{1,2,3})
        for member in members:
            self.assertTrue(allowed.contains(member))
            self.assertEqual([item.id for item in member.weapons],
                ['item:'+str(index+1) for index in range(len(member.weapons))])
            self.assertIs(member.weapons[0].initial_location,WeaponItemLocation.HELD)

    def test_two_single_handed_items_use_two_hands_and_third_is_carried(self):
        member=space(weapon_count=(3,)).sample(Random(1))
        self.assertEqual([item.initial_grip for item in member.weapons],
            [WeaponGrip.LEFT,WeaponGrip.RIGHT,None])
        self.assertEqual([item.initial_location for item in member.weapons],
            [WeaponItemLocation.HELD,WeaponItemLocation.HELD,WeaponItemLocation.CARRIED])

    def test_shield_occupies_other_hand_and_two_handed_pool_member_can_be_carried(self):
        allowed=space(weapon=(GeneratedWeapon.SWORD,GeneratedWeapon.GREATSWORD),
            weapon_count=(2,),shield=(ShieldKind.SHIELD,))
        members=[allowed.sample(Random(seed)) for seed in range(8)]
        self.assertTrue(any(member.weapons[1].kind is WeaponKind.GREATSWORD for member in members))
        for member in members:
            self.assertIs(member.weapons[0].kind,WeaponKind.SWORD)
            self.assertIs(member.weapons[0].initial_grip,WeaponGrip.LEFT)
            self.assertIs(member.weapons[1].initial_location,WeaponItemLocation.CARRIED)
        with self.assertRaises(ValueError):
            space(weapon=(GeneratedWeapon.GREATSWORD,),shield=(ShieldKind.SHIELD,))

    def test_each_exacting_unit_gets_its_own_explicit_charge_and_union_preparation(self):
        allowed=space(weapon=(GeneratedWeapon.PISTOL,GeneratedWeapon.REPEATER_HANDBOW),
            weapon_count=(3,),initial_loaded=(False,True))
        members=[allowed.sample(Random(seed)) for seed in range(8)]
        self.assertTrue(any(len({item.initially_loaded for item in member.weapons})==2 for member in members))
        for member in members:
            self.assertTrue(all(type(item.initially_loaded) is bool for item in member.weapons))
            firearm=any(item.kind is WeaponKind.PISTOL for item in member.weapons)
            self.assertIs(member.ranged.has_blackpowder_lore,True if firearm else None)
            self.assertEqual((member.ranged.initiative,member.ranged.dexterity),(3,4))
            self.assertFalse(hasattr(member.ranged,'initially_loaded'))

    def test_free_bow_uses_awareness_without_exacting_dexterity_or_charge(self):
        member=space(weapon=(GeneratedWeapon.SHORTBOW,),weapon_count=(2,)).sample(Random(1))
        self.assertEqual((member.ranged.initiative,member.ranged.awareness),(3,4))
        self.assertIsNone(member.ranged.dexterity)
        self.assertTrue(all(item.initially_loaded is None for item in member.weapons))

    def test_mixed_melee_shooting_net_prepares_shared_bs_for_every_item(self):
        allowed=space(weapon=(GeneratedWeapon.SWORD,GeneratedWeapon.PISTOL,GeneratedWeapon.WEIGHTED_NET),
            weapon_count=(3,))
        member=next(allowed.sample(Random(seed)) for seed in range(60)
            if {item.kind for item in allowed.sample(Random(seed)).weapons}==
            {WeaponKind.SWORD,WeaponKind.PISTOL,WeaponKind.WEIGHTED_NET})
        self.assertEqual(member.throwing,4)
        self.assertEqual(member.ballistic_skill,member.ranged.ballistic_skill)
        self.assertTrue(allowed.contains(member))

    def test_chivalric_primary_can_keep_explicit_carried_firearm(self):
        allowed=space(weapon=(GeneratedWeapon.SWORD,GeneratedWeapon.PISTOL),weapon_count=(2,),
            armour=(BodyArmour.AGILULF,),agilulf_code_confirmed=True)
        member=next(allowed.sample(Random(seed)) for seed in range(10)
            if allowed.sample(Random(seed)).weapons[1].kind is WeaponKind.PISTOL)
        self.assertIs(member.weapon,GeneratedWeapon.SWORD)
        self.assertIs(member.weapons[1].initial_location,WeaponItemLocation.CARRIED)
        self.assertIsNotNone(member.ranged)

    def test_numeric_sampling_keeps_every_source_id_pose_and_charge(self):
        allowed=space(weapon=(GeneratedWeapon.PISTOL,GeneratedWeapon.WEIGHTED_NET),
            weapon_count=(3,),initial_loaded=(False,True),strength=(2,3,4),ballistic_skill=(2,3,4))
        before=allowed.sample(Random(3));original=deepcopy(before)
        result=allowed.resample_numeric((before,),Random(7),bias=1).composition[0]
        self.assertEqual(result.weapons,before.weapons)
        self.assertEqual(before,original)
        self.assertTrue(allowed.contains(result))
        if result.throwing is not None and result.ranged is not None:
            self.assertEqual(result.ballistic_skill,result.ranged.ballistic_skill)

    def test_mutation_add_remove_swap_and_charge_keep_surviving_ids(self):
        allowed=space(weapon=(GeneratedWeapon.SWORD,GeneratedWeapon.PISTOL),weapon_count=(1,2),initial_loaded=(True,False))
        original=space(weapon_count=(1,)).sample(Random(0))
        added=allowed.mutate(original,ChooseCandidate(lambda value:len(value.weapons)==2))
        self.assertEqual(added.weapons[0].id,original.weapons[0].id)
        self.assertEqual(len({item.id for item in added.weapons}),2)
        removed=allowed.mutate(added,ChooseCandidate(lambda value:len(value.weapons)==1))
        self.assertIn(removed.weapons[0].id,{item.id for item in added.weapons})
        pistol=allowed.mutate(original,ChooseCandidate(lambda value:value.weapons[0].kind is WeaponKind.PISTOL))
        self.assertEqual(pistol.weapons[0].id,original.weapons[0].id)
        discharged=allowed.mutate(pistol,ChooseCandidate(lambda value:value.weapons[0].initially_loaded is False))
        self.assertEqual(discharged.weapons[0].id,pistol.weapons[0].id)
        self.assertTrue(pistol.weapons[0].initially_loaded)

    def test_variable_grip_mutation_preserves_implement_and_charge(self):
        allowed=space(weapon=(GeneratedWeapon.FOOT_SPEAR,),weapon_count=(1,))
        member=allowed.sample(Random(1))
        other=allowed.mutate(member,ChooseCandidate(lambda value:value.weapons[0].initial_grip is not member.weapons[0].initial_grip))
        self.assertEqual(other.weapons[0].id,member.weapons[0].id)
        self.assertIn(other.weapon_grip,(RangedWeaponHands.ONE_HANDED,RangedWeaponHands.TWO_HANDED))

    def test_axes_and_out_of_space_physical_sources_are_rejected(self):
        for changes in ({'weapon_count':(True,)},{'weapon_count':(0,)},{'weapon_count':()},
                {'initial_loaded':(1,)},{'initial_loaded':()}):
            with self.subTest(changes=changes),self.assertRaises((TypeError,ValueError)):
                space(**changes)
        allowed=space(weapon=(GeneratedWeapon.PISTOL,),weapon_count=(1,))
        member=allowed.sample(Random(0))
        self.assertFalse(allowed.contains(replace(member,weapons=(replace(member.weapons[0],initially_loaded=False),))))

    def test_public_generated_character_shape_has_only_initial_item_fields(self):
        member=space(weapon=(GeneratedWeapon.PISTOL,),weapon_count=(2,),initial_loaded=(False,)).sample(Random(1))
        raw=generated_components_document(member)
        self.assertNotIn('weapon',raw);self.assertNotIn('weapon_grip',raw)
        for item in raw['weapons']:
            self.assertEqual(set(item),{'id','weapon','location','hand','initially_loaded'})
            self.assertIs(item['initially_loaded'],False)
        self.assertEqual(parse_generated_components(raw,path_prefix='/',error_type=DynamicEncounterInputError),member)
        self.assertEqual(parse_character_file(json.dumps(raw),'npc'),raw)
        malformed=deepcopy(raw);malformed['weapons'][0]['location']='dropped'
        with self.assertRaises(DynamicEncounterInputError):
            parse_character_file(json.dumps(malformed),'npc')
        malformed=deepcopy(raw);del malformed['weapons'][0]['initially_loaded']
        with self.assertRaises(DynamicEncounterInputError):
            parse_character_file(json.dumps(malformed),'npc')

    def test_finite_net_quantity_is_preserved_without_expanding_or_refilling_source(self):
        member=space(weapon=(GeneratedWeapon.WEIGHTED_NET,),weapon_count=(1,)).sample(Random(0))
        member=replace(member,weapons=(replace(member.weapons[0],quantity=3),))
        raw=generated_components_document(member)
        self.assertEqual(raw['weapons'][0]['quantity'],3)
        self.assertEqual(parse_generated_components(raw,path_prefix='/',error_type=DynamicEncounterInputError),member)
        self.assertEqual(parse_character_file(json.dumps(raw),'npc'),raw)
        for quantity in (0,True):
            malformed=deepcopy(raw);malformed['weapons'][0]['quantity']=quantity
            with self.assertRaises(DynamicEncounterInputError):
                parse_character_file(json.dumps(malformed),'npc')

    def test_native_json_carries_all_derived_profiles_including_carried_gun(self):
        request=parse_dynamic_encounter_request(Path('docs/examples/dynamic/inventory.request.json').read_text(encoding='utf8'))
        member=space(weapon=(GeneratedWeapon.SWORD,GeneratedWeapon.PISTOL),weapon_count=(2,),initial_loaded=(False,)).sample(Random(5))
        scenario=request.request.scenario((member,),'inventory-source-roundtrip')
        raw=dict(schema_version='1',kind='pc_melee_simulation',request_id=scenario.id,
            ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(scenario),simulation=dict(master_seed='42',trials=1),execution=dict(mode='sequential'))
        definition=raw['scenario']['enemies'][0]['definition']
        self.assertNotIn('attack',definition)
        self.assertEqual(len(definition['attacks']),len(scenario.enemies[0].definition.attacks))
        parsed=parse_pc_melee_simulation_request(json.dumps(raw))
        self.assertEqual(parsed.request.scenario,scenario)
        malformed=deepcopy(raw);malformed['scenario']['enemies'][0]['definition']['attacks'].pop()
        with self.assertRaises(PcMeleeInputError):
            parse_pc_melee_simulation_request(json.dumps(malformed))


if __name__=='__main__':
    unittest.main()
