"""Current public Net facts round-trip without a Damage or fictional stock."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
from random import Random
import unittest

from towr.adapters.character_files import parse_character_file
from towr.adapters.dynamic_encounter_json import parse_dynamic_encounter_request, DynamicEncounterInputError
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.adapters.pc_melee_json_errors import PcMeleeInputError
from towr.domain.generated_npc_models import GeneratedWeapon
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.test_models import Skill
from towr.domain.pc_melee_result_models import initial_pc_melee_state
from towr.engine.pc_melee_runner import apply_pc_melee_step
from towr.domain.pc_weapon_inventory import pc_weapon_inventory_view
from towr.domain.pc_ranged_advice import pc_attack_value


def document():
    raw=json.loads(Path('docs/examples/dynamic/weighted-net.request.json').read_text('utf-8'))
    raw['search_space'].update(weapon=['weighted_net'],ballistic_skill=[2],strength=[4],throwing=[5])
    return raw


def native_document(scenario):
    return dict(schema_version='1',kind='pc_melee_simulation',request_id='net:roundtrip',
        ruleset='towr-pg1.4-gmg1.1',scenario=scenario_document(scenario),
        simulation=dict(master_seed='42',trials=1),execution=dict(mode='sequential'))


class DynamicWeightedNetTests(unittest.TestCase):
    def test_net_facts_both_sides_roundtrip_current_native_source(self):
        raw=document(); before=deepcopy(raw)
        command=parse_dynamic_encounter_request(json.dumps(raw))
        npc=command.request.space.sample(Random(7))
        self.assertIs(npc.weapon,GeneratedWeapon.WEIGHTED_NET)
        self.assertIsNone(npc.ranged)
        scenario=command.request.scenario((npc,),'net:source')
        pc=scenario.party[0].pc
        self.assertIs(pc.weapon,PcMeleeWeapon.WEIGHTED_NET)
        self.assertEqual(pc.throwing_profile.characteristic,3)
        self.assertEqual(pc.throwing_profile.skill,5)
        attack=scenario.enemies[0].definition.attacks[0]
        self.assertIs(attack.skill,Skill.THROWING)
        self.assertIsNone(attack.damage)
        self.assertEqual(attack.test_profile.dice,2)
        self.assertIsNone(attack.test_profile.pool_cap)  # Default cap = twice the explicit BS.
        self.assertEqual(attack.range_max.value,'medium')
        encoded=native_document(scenario)
        self.assertEqual(parse_pc_melee_simulation_request(json.dumps(encoded)).request.scenario,scenario)
        self.assertEqual(raw,before)

    def test_player_and_generated_npc_character_files_preserve_net_facts(self):
        raw=document()
        self.assertEqual(parse_character_file(json.dumps(raw['party'][0]),'player'),raw['party'][0])
        npc=parse_dynamic_encounter_request(json.dumps(raw)).request.space.sample(Random(1))
        encoded=json.loads(json.dumps(asdict(npc)))
        self.assertEqual(parse_character_file(json.dumps(encoded),'npc'),encoded)

    def test_missing_throwing_bs_incompatible_shield_or_damage_ability_rejected(self):
        for change in ('throwing','ballistic_skill','shield','ability'):
            raw=document()
            if change=='throwing': del raw['party'][0]['skills']['throwing']
            elif change=='ballistic_skill': del raw['party'][0]['characteristics']['ballistic_skill']
            elif change=='shield': raw['search_space']['shield']=[True]
            else: raw['search_space']['abilities']=[['drained_on_hit']]
            with self.subTest(change=change),self.assertRaises(DynamicEncounterInputError):
                parse_dynamic_encounter_request(json.dumps(raw))

    def test_forged_generated_attack_profile_cannot_override_physical_source(self):
        request=parse_dynamic_encounter_request(json.dumps(document())).request
        scenario=request.scenario((request.space.sample(Random(0)),),'net:forgery')
        raw=native_document(scenario)
        attack=raw['scenario']['enemies'][0]['definition']['attack']
        attack['test_profile']['pool_cap']=99
        with self.assertRaises(PcMeleeInputError):
            parse_pc_melee_simulation_request(json.dumps(raw))

    def test_backup_advice_preserves_the_real_net_bank_and_is_not_an_executable_state(self):
        request=parse_dynamic_encounter_request(json.dumps(document())).request
        scenario=request.scenario((request.space.sample(Random(0)),),'net:advice')
        state=initial_pc_melee_state(scenario)
        original=replace(state)
        view=pc_weapon_inventory_view(state,scenario.party[0].actor_id,'backup:1')
        self.assertIsNotNone(view)
        self.assertEqual(view.participant(scenario.party[0].actor_id).weapon_inventory.active_item_id,'backup:1')
        self.assertIs(view.weighted_nets,state.weighted_nets)
        self.assertIs(view.history,state.history)
        pc_attack_value(view,scenario.party[0].actor_id)
        self.assertEqual(state,original)
        with self.assertRaises(TypeError):
            apply_pc_melee_step(view,None)

    def test_spent_net_does_not_prevent_drawing_and_approaching_with_real_backup(self):
        from towr.engine.pc_melee_runner import run_pc_melee_scenario
        from towr.domain.pc_weapon_inventory import PcWeaponSwapProof
        from towr.domain.pc_melee_result_models import PcAttackProof
        raw=document();raw['party']=raw['party'][:1]
        command=parse_dynamic_encounter_request(json.dumps(raw))
        scenario=command.request.scenario((command.request.space.sample(Random(0)),),'net:backup-approach')
        class Ones:
            def randint(self,low,high):
                if (low,high)!=(1,10):raise AssertionError('only d10 are expected')
                return 1
        result=run_pc_melee_scenario(scenario,Ones())
        self.assertIsNone(result.unsupported)
        swaps=[step.proof for step in result.steps if type(step.proof) is PcWeaponSwapProof]
        self.assertEqual([proof.state.active_item_id for proof in swaps],['backup:1'])
        attacks=[step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id==scenario.party[0].actor_id]
        from towr.domain.attack_models import DamageImpactSpec
        self.assertTrue(any(type(proof.request.kernel_request.attack.impact_spec) is DamageImpactSpec
            and proof.weighted_net_landing is None for proof in attacks))
        self.assertEqual(replace(result),result)


class WeightedNetProcessParityTests(unittest.TestCase):
    def test_physical_net_source_and_trials_are_identical_in_real_workers(self):
        from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
        from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
        from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
        request=parse_dynamic_encounter_request(json.dumps(document())).request
        source=PcMeleeSimulationRequest(request.scenario((request.space.sample(Random(7)),),'net:workers'),42,2)
        sequential=run_pc_melee_simulation(source)
        parallel=run_pc_melee_simulation_parallel(source,workers=2,batch_size=1)
        self.assertEqual(parallel,sequential)
        self.assertEqual(parallel.source_request.scenario,source.scenario)
