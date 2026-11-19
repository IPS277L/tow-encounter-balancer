"""Current source contracts for ordinary Brawn/mounted weapons, without MC."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from random import Random
import unittest

from jsonschema import Draft202012Validator
from towr.adapters._pc_melee_scenario_json import generated_components_document, scenario_document
from towr.adapters.character_files import parse_character_file
from towr.adapters.dynamic_encounter_json import DynamicEncounterInputError, parse_dynamic_encounter_request
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.adapters.pc_melee_json_errors import PcMeleeInputError
from towr.application.dynamic_encounter import NpcSearchSpace
from towr.domain.armour_models import ArmourLoadout
from towr.domain.generated_npc_models import GeneratedNpc, GeneratedWeapon
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.test_models import Skill
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_inventory_models import WeaponGrip, WeaponItemLocation, WeaponItemSource


def request():
    raw=json.loads(Path('docs/examples/dynamic/search.request.json').read_text(encoding='utf-8'))
    raw['party']=raw['party'][:1]
    raw['party'][0]['skills']['brawn']=4
    raw['npc_count']={'minimum':1,'maximum':1}
    raw['max_rounds']=1
    raw['targets']['started_rounds']={'numerator':1,'denominator':1}
    raw['search'].update(max_candidates=1,exploration_trials=1,finalist_trials=1,top_k=1,max_total_trials=2)
    raw['search_space'].update(weapon_count=[0,1],weapon=['knuckledusters','cavalry_spear','lance'],
        brawn=[3,4],endurance=[4,5],mount=[None],barding=[False],allowed_talents=[])
    return raw


def native_document(command, npc):
    scenario=command.request.scenario((npc,),'brawn-source')
    return dict(schema_version='1',kind='pc_melee_simulation',request_id='brawn-source',
        ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(scenario),
        simulation=dict(master_seed='42',trials=1),execution=dict(mode='sequential'))


class BrawnWeaponJsonTests(unittest.TestCase):
    def test_current_schema_fragments_are_valid(self):
        for name in ('pc-melee-common','dynamic-encounter-common'):
            schema=json.loads(Path(f'src/towr/adapters/schemas/{name}.schema.json').read_text(encoding='utf-8'))
            Draft202012Validator.check_schema(schema)

    def test_unarmed_player_has_no_physical_item_and_preserves_actual_shield_hand(self):
        for hand in ('left_hand','right_hand'):
            with self.subTest(hand=hand):
                raw=request()
                player=raw['party'][0]
                player['equipment']={'weapons':[],'armour':[dict(id='shield',kind='shield',location=hand)]}
                parsed=parse_dynamic_encounter_request(json.dumps(raw))
                member=parsed.request.party[0]
                self.assertIs(member.pc.weapon,PcMeleeWeapon.UNARMED)
                self.assertIsNone(member.initial_weapon_hand)
                self.assertEqual(member.combat_equipment,())
                self.assertEqual(member.shield.initial_hand.value,hand.removesuffix('_hand'))
                self.assertEqual(parse_character_file(json.dumps(player),'player'),player)
                npc=parsed.request.space.sample(Random(1))
                native=native_document(parsed,npc)
                restored=parse_pc_melee_simulation_request(json.dumps(native)).request.scenario
                self.assertEqual(scenario_document(restored),native['scenario'])

    def test_all_carried_inventory_starts_unarmed_without_losing_its_items(self):
        raw=request()
        raw['party'][0]['equipment']['weapons']=[dict(id='sword',weapon='sword',location='carried')]
        parsed=parse_dynamic_encounter_request(json.dumps(raw))
        member=parsed.request.party[0]
        self.assertIs(member.pc.weapon,PcMeleeWeapon.UNARMED)
        self.assertEqual(len(member.combat_equipment),1)
        self.assertIs(member.combat_equipment[0].location,WeaponItemLocation.CARRIED)
        self.assertIsNone(member.combat_equipment[0].hand)

    def test_knuckledusters_and_unarmed_require_actual_brawn_before_execution(self):
        for weapons in ([],[dict(id='fist',weapon='knuckledusters',location='left_hand')]):
            raw=request()
            raw['party'][0]['equipment']['weapons']=weapons
            del raw['party'][0]['skills']['brawn']
            with self.subTest(weapons=weapons), self.assertRaises(DynamicEncounterInputError):
                parse_dynamic_encounter_request(json.dumps(raw))
        raw=request()
        raw['party'][0]['equipment']['weapons']=[dict(id='fake',weapon='unarmed',location='left_hand')]
        with self.assertRaises(DynamicEncounterInputError):
            parse_dynamic_encounter_request(json.dumps(raw))

    def test_all_new_physical_weapons_roundtrip_for_players_and_generated_npcs(self):
        for kind in ('knuckledusters','cavalry_spear','lance'):
            with self.subTest(kind=kind):
                raw=request()
                raw['party'][0]['equipment']['weapons']=[dict(id='primary',weapon=kind,location='left_hand')]
                command=parse_dynamic_encounter_request(json.dumps(raw))
                source=GeneratedNpc(3,4,3,3,4,4,(WeaponItemSource('item',WeaponKind(kind),
                    WeaponItemLocation.HELD,WeaponGrip.LEFT),),ArmourLoadout(),defence=4,brawn=4,endurance=5)
                document=generated_components_document(source)
                self.assertEqual(parse_character_file(json.dumps(document),'npc'),document)
                native=native_document(command,source)
                restored=parse_pc_melee_simulation_request(json.dumps(native)).request.scenario
                self.assertEqual(scenario_document(restored),native['scenario'])
                self.assertEqual(tuple(profile.skill for profile in restored.enemies[0].definition.protection),
                    (Skill.DEFENCE,Skill.ATHLETICS,Skill.ENDURANCE))
                brawn=[attack for attack in restored.enemies[0].definition.attacks if attack.skill is Skill.BRAWN]
                self.assertEqual(len(brawn),3 if kind=='knuckledusters' else 1)

    def test_empty_generated_inventory_and_exact_brawn_profile_survive_native_codec(self):
        command=parse_dynamic_encounter_request(json.dumps(request()))
        npc=GeneratedNpc(3,4,3,3,4,4,(),ArmourLoadout(),defence=4,brawn=5,endurance=3)
        source=generated_components_document(npc)
        self.assertEqual(parse_character_file(json.dumps(source),'npc'),source)
        native=native_document(command,npc)
        definition=native['scenario']['enemies'][0]['definition']
        self.assertEqual(definition['attacks'][0]['hands'],None)
        self.assertEqual(definition['attacks'][0]['impact']['condition'],'staggered')
        restored=parse_pc_melee_simulation_request(json.dumps(native)).request.scenario
        self.assertEqual(scenario_document(restored),native['scenario'])
        forged=deepcopy(native)
        forged['scenario']['enemies'][0]['definition']['attacks'][0]['test_profile']['dice']=3
        with self.assertRaises(PcMeleeInputError):
            parse_pc_melee_simulation_request(json.dumps(forged))
        forged=deepcopy(native)
        del forged['scenario']['enemies'][0]['definition']['endurance_protection']
        with self.assertRaises(PcMeleeInputError):
            parse_pc_melee_simulation_request(json.dumps(forged))

    def test_zero_item_sampling_mutation_and_numeric_sampling_preserve_source(self):
        space=NpcSearchSpace(weapon_skill=(3,),strength=(3,),toughness=(3,),agility=(3,),
            melee=(3,),defence=(3,),athletics=(3,),endurance=(4,),brawn=(4,),
            weapon=(GeneratedWeapon.KNUCKLEDUSTERS,),weapon_count=(0,1),
            armour=(None,),shield=(None,),allowed_talents=())
        bare=GeneratedNpc(3,3,3,3,3,3,(),ArmourLoadout(),defence=3,brawn=4,endurance=4)
        self.assertTrue(space.contains(bare))
        equipped=space.mutate(bare,Random(0))
        self.assertEqual(len(equipped.weapons),1)
        self.assertIs(equipped.weapon,GeneratedWeapon.KNUCKLEDUSTERS)
        self.assertEqual(space.mutate(equipped,Random(0)),bare)
        self.assertEqual(space.resample_numeric((bare,),Random(0)).composition,(bare,))
        empty_space=replace(space,weapon_count=(0,))
        for seed in range(8):
            sampled=empty_space.sample(Random(seed))
            self.assertEqual(sampled.weapons,())
            self.assertIs(sampled.weapon,GeneratedWeapon.UNARMED)
            self.assertEqual((sampled.brawn,sampled.endurance),(4,4))
            self.assertTrue(empty_space.contains(sampled))

    def test_nonphysical_unarmed_cannot_enter_item_pool_or_character_source(self):
        with self.assertRaises(ValueError):
            NpcSearchSpace(weapon=(GeneratedWeapon.UNARMED,))
        from towr.domain.generated_npc_models import GeneratedAbility
        with self.assertRaises(ValueError):
            NpcSearchSpace(weapon_count=(0,),abilities=((GeneratedAbility.DRAINED_ON_HIT,),))
        source=generated_components_document(GeneratedNpc(3,3,3,3,3,3,(),ArmourLoadout(),
            defence=3,brawn=4))
        source['weapons']=[dict(id='fake',weapon='unarmed',location='held',hand='left')]
        with self.assertRaises(DynamicEncounterInputError):
            parse_character_file(json.dumps(source),'npc')


class BrawnWeaponProcessParityTests(unittest.TestCase):
    def test_unarmed_inventory_and_endurance_profile_survive_process_transport(self):
        from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
        from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
        from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
        from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
        raw=request()
        raw['party'][0]['equipment']={'weapons':[],
            'armour':[dict(id='shield',kind='shield',location='left_hand')]}
        raw['search_space']['weapon_count']=[0]
        command=parse_dynamic_encounter_request(json.dumps(raw))
        npc=command.request.space.sample(Random(0))
        scenario=command.request.scenario((npc,),'brawn-process')
        source=PcMeleeSimulationRequest(scenario,42,2)
        sequential=run_pc_melee_simulation(source)
        parallel=run_pc_melee_simulation_parallel(source,workers=2,batch_size=1)
        self.assertEqual(sequential,parallel)
        self.assertEqual(summarize_pc_melee_simulation(sequential),summarize_pc_melee_simulation(parallel))
        self.assertEqual(parallel.source_request.scenario.enemies[0].definition.generated_components,npc)
        self.assertEqual(npc.weapons,())
        self.assertIn(Skill.ENDURANCE,tuple(profile.skill for profile in scenario.enemies[0].definition.protection))


if __name__=='__main__':
    unittest.main()
