"""Ordinary Throwing through real Tests, finite items, areas and native replay."""
from copy import deepcopy
from dataclasses import replace
import json
from random import Random
import unittest

from tests.integration.test_throwing_weapon_json import request,native_document,WEAPONS
from towr.adapters.dynamic_encounter_json import parse_dynamic_encounter_request
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedNpc
from towr.domain.pc_extinguish_models import PcExtinguishProof
from towr.domain.pc_melee_models import PcMeleePolicy
from towr.domain.pc_melee_result_models import PcAttackProof,initial_pc_melee_state,PcWoundCompletionProof
from towr.domain.pc_weapon_area_models import (
    PcWeaponHazardProof,PcWeaponHazardCompletionProof,PcWeaponAreaEndProof,
    PcWeaponAreaConditionProof,ABLAZE_HAZARD_RULE_ID,
)
from towr.domain.weapon_inventory_models import WeaponItemLocation
from towr.domain.weapon_impact_preparation import BLAST_IMPACT_RULE_ID
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step


class Threes:
    def randint(self,low,high):
        if (low,high)!=(1,10):raise AssertionError('unexpected die')
        return 3


class FirstAttackMisses(Threes):
    def __init__(self):self.remaining=7  # six BS dice and the one real Protection die
    def randint(self,low,high):
        value=super().randint(low,high)
        if self.remaining:
            self.remaining-=1
            return 10
        return value


def battle(kind,*,npc_throws=False,count=1,rounds=2,distance='medium',hit=True,players=1,
        pc_toughness=20,pc_athletics=2,npc_athletics=2):
    raw=request(kind)
    member=raw['party'][0]
    member['characteristics'].update(weapon_skill=1,ballistic_skill=6,
        toughness=pc_toughness,agility=3 if pc_athletics>2 else 1)
    member['skills'].update(melee=2,defence=2,throwing=6,
        endurance=2,athletics=pc_athletics)
    member['resources']['fate']=0
    member['skills'].pop('brawn',None)
    if npc_throws:
        member['equipment']['weapons']=[dict(id='sling',weapon='sling',location='left_hand')]
        member['characteristics']['ballistic_skill']=1
        member['skills']['shooting']=2
        member['ranged']=dict(ammunition_supply_confirmed=True,has_blackpowder_lore=None,has_blackpowder_kit=None)
    raw['party']=[member]
    for index in range(1,players):
        ally=deepcopy(member);ally['actor_id']='ally:'+str(index);raw['party'].append(ally)
    raw['npc_count']=dict(minimum=count,maximum=count)
    raw['max_rounds']=rounds
    raw['targets']['started_rounds']=dict(numerator=rounds,denominator=1)
    raw['scene']['range']=distance
    raw['search_space'].update(weapon=[kind if npc_throws else 'staff'],weapon_count=[1],
        weapon_skill=[1],melee=[2],strength=[3],toughness=[1],agility=[1],
        defence=[2],athletics=[npc_athletics],endurance=[2],brawn=[4],ballistic_skill=[6],throwing=[6],mount=[None])
    command=parse_dynamic_encounter_request(json.dumps(raw))
    sources=tuple(command.request.space.sample(Random(index+1)) for index in range(count))
    source=command.request.scenario(sources,'throwing-native:'+kind)
    if npc_throws:
        source=replace(source,enemies=tuple(replace(npc.participant(enemy.state.actor_id),
            definition=replace(npc.participant(enemy.state.actor_id).definition,id=enemy.definition.id),
            state=replace(npc.participant(enemy.state.actor_id).state,definition_id=enemy.definition.id))
            for enemy in source.enemies
            for npc in (replace(enemy.definition.generated_components,toughness=20),)))
    return source


class ThrowingWeaponExecutionTests(unittest.TestCase):
    def run_native(self,source,rng=None):
        restored=parse_pc_melee_simulation_request(json.dumps(native_document(source))).request.scenario
        self.assertEqual(restored,source)
        result=run_pc_melee_scenario(restored,rng or Threes())
        self.assertIsNone(result.unsupported)
        current=initial_pc_melee_state(source)
        for step in result.steps:
            current=apply_pc_melee_step(current,step)
        self.assertEqual(current,result.state)
        return result

    def test_each_ordinary_weapon_has_real_player_and_npc_attacks(self):
        for kind in WEAPONS:
            for npc_throws in (False,True):
                with self.subTest(kind=kind,npc_throws=npc_throws):
                    source=battle(kind,npc_throws=npc_throws,rounds=1)
                    result=self.run_native(source)
                    actor=(source.enemy_activation_order if npc_throws else source.pc_activation_order)[0]
                    attacks=[step for step in result.steps if type(step.proof) is PcAttackProof
                        and step.proof.request.actor_id==actor and step.proof.throwing_inventory is not None]
                    self.assertEqual(len(attacks),1)
                    proof=attacks[0].proof
                    self.assertEqual(proof.weapon_intent.attack_use.kind.value,kind)
                    self.assertEqual(proof.weapon_intent.attack_use.used_hands[0].value,'left')
                    receipt=proof.throwing_inventory
                    location=receipt.after_inventory.item(receipt.weapon_use.primary_item_id).location
                    self.assertIs(location,WeaponItemLocation.SPENT if kind in ('oil_flask','blasting_charge') else
                        WeaponItemLocation.HELD if kind=='throwing_knives' else WeaponItemLocation.DROPPED)

    def test_stationary_close_scene_does_not_invent_optimum_for_a_rock(self):
        from towr.domain.generated_npc_models import GENERATED_CLOSE_WEAPONS,GeneratedWeapon
        self.assertNotIn(GeneratedWeapon.ROCK,GENERATED_CLOSE_WEAPONS)
        source=battle('rock',rounds=1,distance='close')
        source=replace(source,battlefield=None,facts=replace(source.facts,all_opponents_close=True,can_leave_zone=False))
        result=self.run_native(source)
        actor=source.pc_activation_order[0]
        self.assertFalse(any(type(step.proof) is PcAttackProof and step.proof.request.actor_id==actor
            for step in result.steps))
        self.assertIs(result.state.participant(actor).weapon_inventory.active.location,WeaponItemLocation.HELD)

    def test_blast_hit_visits_every_npc_in_frozen_target_zone_once(self):
        source=battle('blasting_charge',count=3,rounds=1)
        result=self.run_native(source)
        hazards=[step.proof for step in result.steps if type(step.proof) is PcWeaponHazardProof]
        self.assertEqual(tuple(proof.request.actor_id for proof in hazards),source.enemy_activation_order)
        self.assertTrue(all(proof.request.exposure.rule_id==BLAST_IMPACT_RULE_ID for proof in hazards))
        self.assertTrue(all(proof.result.shortfall==3 for proof in hazards))
        self.assertTrue(all(enemy.state.injury.defeated for enemy in result.state.enemies))
        self.assertEqual(sum(type(step.proof) is PcWeaponAreaEndProof for step in result.steps),1)

    def test_blast_miss_exposes_attacker_and_ally_instead_of_target_zone(self):
        source=battle('blasting_charge',count=2,rounds=1,hit=False,players=2,pc_toughness=1)
        result=self.run_native(source,FirstAttackMisses())
        first=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id==source.pc_activation_order[0])
        self.assertFalse(first.weapon_area.hit)
        self.assertEqual(first.weapon_area.target_ids,source.pc_activation_order)
        hazards=[step.proof for step in result.steps if type(step.proof) is PcWeaponHazardProof
            and step.proof.request.event_id==first.request.id]
        self.assertEqual(tuple(proof.request.actor_id for proof in hazards),source.pc_activation_order)
        self.assertTrue(all(proof.result.shortfall==3 for proof in hazards))
        completions=[step.proof for step in result.steps if type(step.proof) is PcWeaponHazardCompletionProof]
        self.assertGreaterEqual(len(completions),2)
        wave_end=next(step for step in result.steps if type(step.proof) is PcWeaponAreaEndProof
            and step.proof.action_id==first.request.id)
        self.assertTrue(all(not enemy.state.injury.wounds for enemy in wave_end.state.enemies))

    def test_spent_volatile_npc_without_brawn_uses_real_recover_without_refill(self):
        from towr.domain.pc_battlefield_movement_models import PcBattlefieldRecoverProof
        for kind in ('oil_flask','blasting_charge'):
            with self.subTest(kind=kind):
                source=battle(kind,npc_throws=True,rounds=3)
                enemy=source.enemies[0]
                npc=replace(enemy.definition.generated_components,brawn=None)
                changed=npc.participant(enemy.state.actor_id)
                source=replace(source,party=tuple(replace(member,pc=replace(member.pc,endurance=6)) for member in source.party),
                    enemies=(replace(changed,definition=replace(changed.definition,id=enemy.definition.id),
                        state=replace(changed.state,definition_id=enemy.definition.id)),))
                result=self.run_native(source)
                actor=source.enemy_activation_order[0]
                shots=[step.proof for step in result.steps if type(step.proof) is PcAttackProof
                    and step.proof.request.actor_id==actor]
                self.assertEqual(len(shots),1)
                waits=[step.proof for step in result.steps if type(step.proof) is PcBattlefieldRecoverProof
                    and step.proof.request.actor_id==actor]
                self.assertEqual(len(waits),2)
                self.assertTrue(all(item.location is WeaponItemLocation.SPENT
                    for item in result.state.enemy(actor).state.weapon_inventory.items))

    def test_oil_nearby_and_real_failed_extinguish_precede_end_phase_fire(self):
        source=battle('oil_flask',count=3,rounds=1)
        result=self.run_native(source)
        applications=[step.proof for step in result.steps if type(step.proof) is PcWeaponAreaConditionProof]
        self.assertEqual(tuple(proof.actor_id for proof in applications),source.enemy_activation_order[1:])
        fire=[(i,step) for i,step in enumerate(result.steps) if type(step.proof) is PcWeaponHazardProof
            and step.proof.request.exposure.rule_id==ABLAZE_HAZARD_RULE_ID]
        self.assertEqual(tuple(step.proof.request.actor_id for _,step in fire),source.enemy_activation_order)
        for index,step in fire:
            actor=step.proof.request.actor_id
            preceding=[item.proof for item in result.steps[:index] if type(item.proof) is PcExtinguishProof
                and item.proof.request.actor_id==actor]
            self.assertEqual(len(preceding),1)
            self.assertFalse(preceding[0].result.resolution.removed)
            self.assertEqual(step.proof.result.shortfall,2)
        from unittest.mock import patch
        from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
        from towr.simulation.pc_melee_simulation import run_pc_melee_trial
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',return_value=result):
            record=run_pc_melee_trial(PcMeleeSimulationRequest(source,42,1),0)
        self.assertEqual(record.executed_actions,4)
        self.assertEqual(tuple(row.count for row in record.npc_recover_action_counts),(1,1,1))

    def test_players_extinguish_actual_oil_without_standard_recover_or_fire_test(self):
        source=battle('oil_flask',npc_throws=True,rounds=2,players=2,pc_toughness=1,pc_athletics=6,npc_athletics=6)
        result=self.run_native(source)
        proofs=[step.proof for step in result.steps if type(step.proof) is PcExtinguishProof]
        self.assertEqual(tuple(proof.request.actor_id for proof in proofs),source.pc_activation_order)
        self.assertTrue(all(proof.result.resolution.removed for proof in proofs))
        self.assertFalse(any(type(step.proof) is PcWeaponHazardProof and
            step.proof.request.actor_id in source.pc_activation_order for step in result.steps))
        self.assertTrue(all(not member.injury.conditions.has(Condition.ABLAZE) for member in result.state.party))

    def test_throw_receipts_and_area_snapshots_reject_source_and_victim_changes(self):
        source=battle('oil_flask',count=2,rounds=1)
        result=self.run_native(source)
        step=next(step for step in result.steps if type(step.proof) is PcAttackProof)
        for proof in (replace(step.proof,throwing_inventory=None),replace(step.proof,weapon_area=None),
                replace(step.proof,weapon_area=replace(step.proof.weapon_area,target_ids=()))):
            with self.subTest(proof=proof),self.assertRaises((ValueError,TypeError)):
                apply_pc_melee_step(step.source,replace(step,proof=proof))
