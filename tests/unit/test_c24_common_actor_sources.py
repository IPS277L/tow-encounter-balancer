"""Current C24 sources keep actual common ratings outside special loadouts."""
from dataclasses import replace
import json
from pathlib import Path
from random import Random
from unittest import TestCase

from towr.adapters.dynamic_encounter_json import (
    DynamicEncounterInputError,parse_dynamic_encounter_request,
)
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.adapters.pc_melee_json_errors import PcMeleeSimulationInputError
from towr.adapters._pc_melee_scenario_json import scenario_document,generated_components_document,parse_generated_components
from towr.application.dynamic_encounter import NpcSearchSpace
from towr.domain.generated_npc_models import GeneratedWeapon
from towr.domain.injury_models import CharacterInjuryState
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.medical_preparation_models import MedicalPreparationFacts
from towr.application.generated_medical_sources import GeneratedMedicalSource
from towr.domain.tool_inventory_models import ToolItemSource,ToolKind
from towr.domain.weapon_inventory_models import WeaponItemLocation,WeaponGrip


def document(name='cleaving-blow'):
    return json.loads(Path('docs/examples/dynamic',name+'.request.json').read_text(encoding='utf-8'))


def space(**changes):
    return NpcSearchSpace(weapon=(GeneratedWeapon.STAFF,),weapon_count=(1,),allowed_talents=(),
        shield=(None,),mount=(None,),barding=(False,),**changes)


class C24CommonActorSourcesTests(TestCase):
    def test_physical_pc_keeps_reason_recall_and_dexterity_without_magic_or_shooting(self):
        raw=document()
        raw['party'][0]['characteristics'].update(reason=4,initiative=3)
        raw['party'][0]['skills'].update(recall=5,dexterity=4)
        member=parse_dynamic_encounter_request(json.dumps(raw)).request.party[0]
        self.assertIsNone(member.pc.ranged)
        self.assertIsNone(member.wizard)
        self.assertEqual((member.pc.reason,member.pc.recall,member.pc.dexterity),(4,5,4))
        self.assertEqual((member.pc.recall_profile.characteristic,member.pc.recall_profile.skill),(4,5))
        self.assertEqual((member.pc.dexterity_profile.characteristic,member.pc.dexterity_profile.skill),(3,4))

    def test_recall_and_dexterity_require_their_real_common_characteristic(self):
        for skill,stat in (('recall','reason'),('dexterity','initiative')):
            with self.subTest(skill=skill):
                raw=document();raw['party'][0]['skills'][skill]=4
                raw['party'][0]['characteristics'].pop(stat,None)
                with self.assertRaises(DynamicEncounterInputError): parse_dynamic_encounter_request(json.dumps(raw))

    def test_wizard_reason_is_the_shared_characteristic_and_no_longer_a_wizard_field(self):
        raw=document('elemental-mage')
        member=parse_dynamic_encounter_request(json.dumps(raw)).request.party[0]
        self.assertEqual(member.pc.reason,raw['party'][0]['characteristics']['reason'])
        self.assertFalse(hasattr(member.wizard,'reason'))
        self.assertEqual(member.willpower_profile.characteristic,member.pc.reason)
        raw['party'][0]['magic']['reason']=4
        with self.assertRaises(DynamicEncounterInputError): parse_dynamic_encounter_request(json.dumps(raw))

    def test_native_ranged_roundtrip_has_owner_dexterity_and_rejects_old_nested_field(self):
        raw=json.loads(Path('docs/examples/m54/pc-melee-simulation.request.json').read_text(encoding='utf-8'))
        command=parse_pc_melee_simulation_request(json.dumps(raw))
        actor=command.request.scenario.party[0]
        encoded=scenario_document(command.request.scenario)
        self.assertEqual(encoded['party'][0]['pc']['dexterity'],actor.pc.dexterity)
        self.assertNotIn('dexterity',encoded['party'][0]['pc']['ranged'])
        raw['scenario']=encoded
        self.assertEqual(parse_pc_melee_simulation_request(json.dumps(raw)).request.scenario,command.request.scenario)
        raw['scenario']['party'][0]['pc']['ranged']['dexterity']=actor.pc.dexterity
        with self.assertRaises(PcMeleeSimulationInputError): parse_pc_melee_simulation_request(json.dumps(raw))

    def test_generated_pistol_uses_common_dexterity_through_all_numeric_proposals(self):
        current=space()
        current=replace(current,weapon=(GeneratedWeapon.PISTOL,))
        npc=current.sample(Random(1))
        self.assertIsNotNone(npc.dexterity)
        self.assertFalse(hasattr(npc.ranged,'dexterity'))
        self.assertTrue(current.contains(current.mutate(npc,Random(2))))
        sampled=current.resample_numeric((npc,),Random(3)).composition[0]
        self.assertTrue(current.contains(sampled))
        raw=generated_components_document(npc)
        self.assertEqual(raw['dexterity'],npc.dexterity)
        self.assertNotIn('dexterity',raw['ranged'])
        self.assertEqual(parse_generated_components(raw,path_prefix='/npc',error_type=PcMeleeSimulationInputError),npc)

    def test_champion_generation_is_opt_in_and_keeps_true_injury_role_without_fate(self):
        current=space(injury_policy=(TargetInjuryPolicy.CHAMPION,))
        npc=current.sample(Random(3))
        self.assertIs(npc.injury_policy,TargetInjuryPolicy.CHAMPION)
        self.assertIsNotNone(npc.endurance)
        snapshot=npc.participant('champion')
        self.assertIs(type(snapshot.state.injury),CharacterInjuryState)
        self.assertIsNone(snapshot.definition.wound_limit)
        self.assertFalse(hasattr(snapshot.state,'fate'))
        self.assertTrue(current.contains(current.mutate(npc,Random(4))))
        self.assertTrue(current.contains(current.resample_numeric((npc,),Random(5)).composition[0]))
        self.assertFalse(space().contains(npc))
        raw=generated_components_document(npc)
        self.assertEqual(raw['injury_policy'],'champion')
        self.assertEqual(parse_generated_components(raw,path_prefix='/npc',error_type=PcMeleeSimulationInputError),npc)

    def test_explicit_role_search_and_native_champion_source_roundtrip(self):
        raw=document();raw['search_space']['injury_policy']=['champion']
        command=parse_dynamic_encounter_request(json.dumps(raw))
        self.assertEqual(command.request.space.injury_policy,(TargetInjuryPolicy.CHAMPION,))
        npc=command.request.space.sample(Random(1))
        source=command.request.scenario((npc,),'c24:champion-source')
        native=json.loads(Path('docs/examples/m54/pc-melee-simulation.request.json').read_text(encoding='utf-8'))
        native['scenario']=scenario_document(source)
        restored=parse_pc_melee_simulation_request(json.dumps(native)).request.scenario
        self.assertEqual(restored,source)
        self.assertIs(type(restored.enemies[0].state.injury),CharacterInjuryState)

    def test_default_minion_role_does_not_add_a_random_draw(self):
        class Recorded(Random):
            def __init__(self,seed): super().__init__(seed);self.draws=[]
            def choice(self,values): self.draws.append(tuple(values));return super().choice(values)
        rng=Recorded(7);npc=space().sample(rng)
        self.assertIs(npc.injury_policy,TargetInjuryPolicy.MINION)
        self.assertNotIn((TargetInjuryPolicy.MINION,),rng.draws)
        with self.assertRaises((TypeError,ValueError)):
            space(injury_policy=('champion',))

    def test_explicit_medical_preparation_and_risk_roundtrip_without_a_talent_gift(self):
        raw=document()
        raw['party'][0]['characteristics'].update(reason=4,initiative=3)
        raw['party'][0]['skills'].update(recall=5,dexterity=4)
        raw['party'][0]['medical']={'anatomy_lore':True,'treatment_supplies':True,'surgery_supplies':True,
            'recovery_supports':['severed_arm'],'self_treatment_modifier':-1,'makeshift_modifier':None}
        raw['party'][0]['equipment']['tools']=[{'id':'kit','kind':'physickers_kit','hands_required':1,'location':'carried'}]
        raw['scene']['surgery_risk']={'id':'gm:case','no_complication':5,'permanent_disfigurement':1,'death':0,
            'disfigurement_description':'GM-defined scar'}
        command=parse_dynamic_encounter_request(json.dumps(raw))
        member=command.request.party[0]
        self.assertTrue(member.pc.medical.anatomy_lore)
        self.assertEqual(member.pc.tools[0].kind,ToolKind.PHYSICKERS_KIT)
        self.assertEqual(command.request.surgery_risk.total,6)
        npc=command.request.space.sample(Random(1))
        source=command.request.scenario((npc,),'c24:medical-source')
        native=json.loads(Path('docs/examples/m54/pc-melee-simulation.request.json').read_text(encoding='utf-8'))
        native['scenario']=scenario_document(source)
        restored=parse_pc_melee_simulation_request(json.dumps(native)).request.scenario
        self.assertEqual(restored,source)
        self.assertEqual(restored.surgery_risk,command.request.surgery_risk)
        self.assertFalse(any(t.id.value=='combat_surgeon' for t in member.talents))

    def test_declared_medical_actions_require_actual_ratings_without_talent_fact_substitution(self):
        raw=document()
        raw['party'][0]['medical']={'anatomy_lore':False,'treatment_supplies':True,'surgery_supplies':False}
        with self.assertRaises(DynamicEncounterInputError): parse_dynamic_encounter_request(json.dumps(raw))
        raw['party'][0]['characteristics']['reason']=3
        raw['party'][0]['skills']['recall']=5
        self.assertEqual(parse_dynamic_encounter_request(json.dumps(raw)).request.party[0].pc.recall,5)
        raw['party'][0]['medical'].update(anatomy_lore=True,surgery_supplies=True)
        with self.assertRaises(DynamicEncounterInputError): parse_dynamic_encounter_request(json.dumps(raw))
        raw['party'][0]['characteristics']['initiative']=3
        raw['party'][0]['skills']['dexterity']=5
        self.assertEqual(parse_dynamic_encounter_request(json.dumps(raw)).request.party[0].pc.dexterity,5)
        plain=space().sample(Random(0))
        with self.assertRaises(ValueError):
            replace(plain,medical=MedicalPreparationFacts(False,True,False),reason=None,recall=None)
        with self.assertRaises(ValueError):
            replace(plain,medical=MedicalPreparationFacts(True,False,True),initiative=None,dexterity=None)

    def test_surgery_risk_needs_explicit_legal_weights_and_disfigurement_description(self):
        base={'id':'gm:risk','no_complication':1,'permanent_disfigurement':0,'death':0}
        for changes in ({'no_complication':0},{'death':True},{'death':-1},{'permanent_disfigurement':1},
                {'owner':'actor'},{'disfigurement_description':'unused'}):
            with self.subTest(changes=changes):
                raw=document();raw['scene']['surgery_risk']={**base,**changes}
                with self.assertRaises(DynamicEncounterInputError): parse_dynamic_encounter_request(json.dumps(raw))
        self.assertIsNone(parse_dynamic_encounter_request(json.dumps(document())).request.surgery_risk)

    def test_medical_bundles_are_explicit_and_survive_proposals_without_granting_a_talent(self):
        medical=MedicalPreparationFacts(True,True,True)
        bundle=GeneratedMedicalSource(medical,(ToolItemSource('kit',ToolKind.PHYSICKERS_KIT,1,
            WeaponItemLocation.CARRIED,None),))
        current=space(allowed_medical_sources=(bundle,))
        members=[current.sample(Random(i)) for i in range(6)]
        self.assertTrue(any(n.medical is None for n in members))
        npc=next(n for n in members if n.medical is not None)
        self.assertEqual(npc.medical,medical)
        self.assertEqual(npc.tools,bundle.tools)
        self.assertFalse(npc.talents)
        self.assertTrue(all(getattr(npc,k) is not None for k in ('initiative','reason','recall','dexterity')))
        for seed in range(12): self.assertTrue(current.contains(current.mutate(npc,Random(seed))))
        self.assertTrue(current.contains(current.resample_numeric((npc,),Random(8)).composition[0]))
        self.assertFalse(current.contains(replace(npc,medical=replace(medical,treatment_supplies=False))))

    def test_initially_held_medical_tools_keep_their_hands_and_weapons_stay_physical(self):
        bundle=GeneratedMedicalSource(MedicalPreparationFacts(True,True,True),(
            ToolItemSource('item:1',ToolKind.PHYSICKERS_KIT,2,WeaponItemLocation.HELD,WeaponGrip.BOTH),))
        current=space(allowed_medical_sources=(bundle,))
        npc=next(n for n in (current.sample(Random(i)) for i in range(6)) if n.medical is not None)
        self.assertEqual(npc.tools,bundle.tools)
        self.assertTrue(npc.weapons)
        self.assertTrue(all(item.initial_location is WeaponItemLocation.CARRIED for item in npc.weapons))
        self.assertNotIn('item:1',{item.id for item in npc.weapons})
        self.assertTrue(current.contains(npc))

    def test_current_json_medical_source_keeps_physical_tool_shape_in_resolved_space(self):
        from towr.adapters._pc_melee_scenario_json import generated_medical_sources_document
        raw=document()
        raw['search_space']['allowed_medical_sources']=[{'medical':{'anatomy_lore':True,
            'treatment_supplies':True,'surgery_supplies':True},'tools':[{'id':'kit','kind':'physickers_kit',
            'hands_required':1,'location':'carried'}]}]
        command=parse_dynamic_encounter_request(json.dumps(raw))
        sources=command.request.space.allowed_medical_sources
        encoded=generated_medical_sources_document(sources)
        self.assertEqual(encoded[0]['tools'][0]['location'],'carried')
        self.assertNotIn('initial_location',encoded[0]['tools'][0])
        raw['search_space']['allowed_medical_sources']=encoded
        self.assertEqual(parse_dynamic_encounter_request(json.dumps(raw)).request.space.allowed_medical_sources,sources)
