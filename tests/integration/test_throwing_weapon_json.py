"""Full ordinary Throwing source/transport, without executing combat or RNG in codecs."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from random import Random
import unittest

from towr.adapters._pc_melee_scenario_json import generated_components_document,scenario_document
from towr.adapters.character_files import parse_character_file
from towr.adapters.dynamic_encounter_json import DynamicEncounterInputError,parse_dynamic_encounter_request
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.adapters.pc_melee_json_errors import PcMeleeInputError
from towr.domain.test_models import Skill
from towr.domain.pc_weapon_inventory import initial_pc_weapon_inventory


WEAPONS=('rock','throwing_spear','throwing_axe','throwing_knives','oil_flask','blasting_charge')


def request(kind='throwing_spear'):
    raw=json.loads(Path('docs/examples/dynamic/brawn.request.json').read_text(encoding='utf-8'))
    raw['party'][0]['characteristics']['ballistic_skill']=3
    raw['party'][0]['skills']['throwing']=5
    raw['party'][0]['equipment']={'weapons':[dict(id='thrown',weapon=kind,location='left_hand')],'armour':[]}
    raw['search_space'].update(weapon_count=[1],weapon=[kind],throwing=[4],ballistic_skill=[3],
        endurance=[4],abilities=[[]],brawn=[4])
    raw['scene']['range']='short'
    return raw


def native_document(scenario):
    return dict(schema_version='1',kind='pc_melee_simulation',request_id='throwing:source',
        ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(scenario),
        simulation=dict(master_seed='42',trials=1),execution=dict(mode='sequential'))


class ThrowingWeaponJsonTests(unittest.TestCase):
    def test_all_six_sources_roundtrip_players_generated_npcs_and_character_files(self):
        for kind in WEAPONS:
            with self.subTest(kind=kind):
                raw=request(kind)
                before=deepcopy(raw)
                command=parse_dynamic_encounter_request(json.dumps(raw))
                npc=command.request.space.sample(Random(2))
                self.assertEqual(npc.throwing,4)
                self.assertEqual(npc.endurance,4)
                source=generated_components_document(npc)
                self.assertEqual(parse_character_file(json.dumps(source),'npc'),source)
                self.assertEqual(parse_character_file(json.dumps(raw['party'][0]),'player'),raw['party'][0])
                scenario=command.request.scenario((npc,),'throwing-source')
                native=native_document(scenario)
                restored=parse_pc_melee_simulation_request(json.dumps(native)).request.scenario
                self.assertEqual(restored,scenario)
                self.assertEqual(scenario_document(restored),native['scenario'])
                profile=next(attack for attack in restored.enemies[0].definition.attacks if attack.skill is Skill.THROWING)
                self.assertEqual(profile.test_profile.dice,3)
                self.assertEqual(profile.test_profile.threshold,4)
                self.assertEqual(raw,before)

    def test_finite_quantity_is_preserved_in_full_pc_and_generated_item_sources(self):
        for kind in ('rock','throwing_spear','throwing_axe','oil_flask','blasting_charge'):
            with self.subTest(kind=kind):
                raw=request(kind)
                raw['party'][0]['equipment']['weapons'][0]['quantity']=3
                command=parse_dynamic_encounter_request(json.dumps(raw))
                member=command.request.party[0]
                self.assertEqual(member.combat_equipment[0].quantity,3)
                units=initial_pc_weapon_inventory(member).items
                self.assertEqual(len(units),3)
                self.assertEqual(len({unit.id for unit in units}),3)
                self.assertTrue(all(unit.source_item_id=='thrown' for unit in units))
                npc=command.request.space.sample(Random(2))
                npc=replace(npc,weapons=(replace(npc.weapons[0],quantity=3),))
                source=generated_components_document(npc)
                self.assertEqual(source['weapons'][0]['quantity'],3)
                self.assertEqual(parse_character_file(json.dumps(source),'npc'),source)
                scenario=command.request.scenario((npc,),'finite-stock')
                native=native_document(scenario)
                restored=parse_pc_melee_simulation_request(json.dumps(native)).request.scenario
                self.assertEqual(restored.party[0].combat_equipment[0].quantity,3)
                self.assertEqual(restored.enemies[0].definition.generated_components.weapons[0].quantity,3)

    def test_stock_requires_positive_exact_counts_and_cannot_reload_throwables(self):
        for quantity in (True,0,-1,1.5):
            raw=request('oil_flask')
            raw['party'][0]['equipment']['weapons'][0]['quantity']=quantity
            with self.subTest(quantity=quantity),self.assertRaises(DynamicEncounterInputError):
                parse_dynamic_encounter_request(json.dumps(raw))
        raw=request('throwing_spear')
        raw['party'][0]['equipment']['weapons'][0]['initially_loaded']=True
        with self.assertRaises(DynamicEncounterInputError):
            parse_dynamic_encounter_request(json.dumps(raw))

    def test_actual_bs_and_throwing_are_required_even_for_a_carried_throwable(self):
        for field,group in (('ballistic_skill','characteristics'),('throwing','skills')):
            raw=request()
            raw['party'][0]['equipment']['weapons'][0]['location']='carried'
            del raw['party'][0][group][field]
            with self.subTest(field=field),self.assertRaises(DynamicEncounterInputError):
                parse_dynamic_encounter_request(json.dumps(raw))

    def test_condition_hazard_and_damage_profiles_are_explicit_and_cannot_be_forged(self):
        for kind,impact in (('rock','condition'),('oil_flask','condition'),('blasting_charge','hazard'),('throwing_axe','damage')):
            with self.subTest(kind=kind):
                command=parse_dynamic_encounter_request(json.dumps(request(kind)))
                npc=command.request.space.sample(Random(2))
                native=native_document(command.request.scenario((npc,),'exact-impact'))
                attack=next(attack for attack in native['scenario']['enemies'][0]['definition']['attacks']
                    if attack.get('skill')=='throwing')
                if impact=='damage':
                    self.assertEqual(attack['damage']['base'],4)
                    self.assertNotIn('impact',attack)
                    attack['damage']['base']+=1
                else:
                    self.assertNotIn('damage',attack)
                    self.assertEqual(attack['impact']['kind'],impact)
                    if impact=='hazard':
                        self.assertEqual(attack['impact']['rating'],3)
                        self.assertEqual(attack['impact']['avoidance_skill'],'endurance')
                        attack['impact']['rating']=2
                    else:attack['impact']['rule_id']='forged:impact'
                with self.assertRaises(PcMeleeInputError):
                    parse_pc_melee_simulation_request(json.dumps(native))

    def test_mixed_shooting_throwing_sampler_and_numeric_mutation_keep_shared_bs(self):
        raw=request()
        raw['search_space'].update(weapon=['throwing_axe','pistol'],weapon_count=[3],
            ballistic_skill=[2,3],throwing=[3,4],strength=[3,4])
        command=parse_dynamic_encounter_request(json.dumps(raw))
        space=command.request.space
        npc=next(member for member in (space.sample(Random(seed)) for seed in range(20))
            if member.ranged is not None and member.throwing is not None)
        for member in (npc,space.mutate(npc,Random(3)),space.resample_numeric((npc,),Random(4)).composition[0]):
            self.assertTrue(space.contains(member))
            if member.ranged is not None and member.throwing is not None:
                self.assertEqual(member.ballistic_skill,member.ranged.ballistic_skill)
        numeric=space.resample_numeric((npc,),Random(5)).composition[0]
        self.assertEqual(numeric.weapons,npc.weapons)


class ThrowingWeaponProcessTests(unittest.TestCase):
    def test_finite_stock_and_hazard_profiles_have_equal_sequential_process_results(self):
        from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
        from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
        from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
        from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation
        raw=request('oil_flask')
        raw['max_rounds']=1
        raw['targets']['started_rounds']['numerator']=1
        raw['party'][0]['equipment']['weapons'][0]['quantity']=2
        raw['search_space']['weapon']=['blasting_charge']
        command=parse_dynamic_encounter_request(json.dumps(raw))
        npc=command.request.space.sample(Random(1))
        source=PcMeleeSimulationRequest(command.request.scenario((npc,),'throwing-process'),42,2)
        sequential=run_pc_melee_simulation(source)
        parallel=run_pc_melee_simulation_parallel(source,workers=2,batch_size=1)
        self.assertEqual(sequential,parallel)
        self.assertEqual(summarize_pc_melee_simulation(sequential),summarize_pc_melee_simulation(parallel))
        self.assertEqual(len(initial_pc_weapon_inventory(source.scenario.party[0]).items),2)
        self.assertTrue(any(attack.hazard_impact is not None for attack in source.scenario.enemies[0].definition.attacks))

