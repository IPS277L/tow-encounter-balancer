"""Actual generated items, selections and Reload histories through native replay."""
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from towr.domain.armour_models import ArmourLoadout,ShieldKind
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedRangedFacts
from towr.domain.pc_melee_result_models import PcAttackProof,initial_pc_melee_state
from towr.domain.pc_npc_ranged_models import PcNpcRangedReloadProof
from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
from towr.domain.pc_npc_weapon_inventory import PcNpcWeaponEquipProof
from towr.domain.weapon_catalog import WeaponKind as W
from towr.domain.weapon_inventory_models import WeaponGrip as G,WeaponItemLocation as L,WeaponItemSource,weapon_unit_id
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step


class Tens:
    def randint(self,low,high):
        if (low,high)!=(1,10):raise AssertionError('unexpected dice')
        return 10


class FirstHitThenTens(Tens):
    def __init__(self):self.first=True
    def randint(self,low,high):
        if self.first:
            self.first=False
            return 1
        return super().randint(low,high)


def item(id,kind,grip=None,*,loaded=None):
    return WeaponItemSource(id,kind,L.CARRIED if grip is None else L.HELD,grip,initially_loaded=loaded)


def scene(items,*,ranged=None,throwing=None,rounds=3):
    source=make_pc_melee_scenario(max_rounds=rounds)
    npc=GeneratedNpc(1,4,20,1,2,2,items,ArmourLoadout(),defence=2,ranged=ranged,
        throwing=throwing,ballistic_skill=6 if throwing is not None and ranged is None else None)
    actor=source.enemy_activation_order[0]
    pc=source.party[0]
    pc=replace(pc,pc=replace(pc.pc,weapon_skill=1,melee=2,toughness=20))
    return replace(source,party=(pc,),enemies=(npc.participant(actor),),
        npc_ranged_policies=(pc_npc_ranged_policy_for_generated(npc,actor),) if ranged is not None else ())


class GeneratedInventoryExecutionTests(unittest.TestCase):
    def test_generated_sling_respects_close_and_long_bounds_and_its_physical_source(self):
        import json
        from random import Random
        from tests.integration.test_dynamic_two_handed_ranged import dynamic_document
        from towr.adapters.dynamic_encounter_json import parse_dynamic_encounter_request
        from towr.domain.pc_battlefield_movement_models import pc_battlefield_attack_available
        from towr.domain.generated_npc_models import GeneratedWeapon,GENERATED_CLOSE_WEAPONS
        self.assertNotIn(GeneratedWeapon.SLING,GENERATED_CLOSE_WEAPONS)
        for distance,allowed in (('close',False),('short',True),('medium',True),('long',True),('extreme',False)):
            with self.subTest(distance=distance):
                raw=dynamic_document('sling')
                raw['party'][0]['equipment']['weapons'][0].update(weapon='sword',location='left_hand')
                del raw['party'][0]['equipment']['weapons'][0]['initially_loaded']
                del raw['party'][0]['ranged']
                raw['scene']['range']=distance
                command=parse_dynamic_encounter_request(json.dumps(raw))
                npc=replace(command.request.space.sample(Random(1)),brawn=None)
                self.assertTrue(command.request.space.contains(npc))
                source=command.request.scenario((npc,),'sling-bounds')
                state=initial_pc_melee_state(source)
                self.assertIsNone(state.enemies[0].state.weapon_inventory.active.reload)
                self.assertEqual(pc_battlefield_attack_available(state,
                    source.enemy_activation_order[0],source.pc_activation_order[0]),allowed)

    def test_sling_has_real_strength_damage_free_reload_and_native_transport(self):
        import json
        from random import Random
        from tests.integration.test_dynamic_two_handed_ranged import dynamic_document,native_document,AllThrees
        from towr.adapters.dynamic_encounter_json import parse_dynamic_encounter_request
        from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
        from towr.domain.pc_ranged_models import PcRangedReloadProof
        from towr.domain.reload_models import FreeReloadWeaponState
        from towr.domain.ranged_weapon_profiles import RangedWeaponId,RangedWeaponRange
        from towr.domain.test_models import Skill
        raw=dynamic_document('sling')
        raw['party'][0]['equipment']['weapons'][0]['location']='left_hand'
        del raw['party'][0]['equipment']['weapons'][0]['initially_loaded']
        raw['party'][0]['equipment']['armour']=[dict(id='shield',kind='shield',location='right_hand')]
        raw['search_space']['shield']=['shield']
        raw['max_rounds']=3
        raw['targets']['started_rounds']['numerator']=3
        # A one-handed Sling uses its printed Long maximum, independently of
        # the explicitly narrower scene limit for two-handed Shooting.
        raw['scene']['two_handed_max_range']='short'
        command=parse_dynamic_encounter_request(json.dumps(raw))
        npc=replace(command.request.space.sample(Random(1)),brawn=None)
        self.assertIsNone(npc.ranged.initiative)
        self.assertIsNone(npc.ranged.dexterity)
        self.assertIsNone(npc.ranged.awareness)
        source=command.request.scenario((npc,),'sling')
        restored=parse_pc_melee_simulation_request(json.dumps(native_document(source))).request.scenario
        self.assertEqual(source,restored)
        result=run_pc_melee_scenario(restored,AllThrees())
        self.assertIsNone(result.unsupported)
        for pc_side,actual_actor in ((True,source.pc_activation_order[0]),(False,source.enemy_activation_order[0])):
            shots=[step.proof for step in result.steps if type(step.proof) is PcAttackProof
                and step.proof.request.actor_id==actual_actor]
            self.assertGreaterEqual(len(shots),2)
            for proof in shots:
                self.assertIs(proof.weapon_intent.attack_skill,Skill.SHOOTING)
                self.assertEqual(proof.request.kernel_request.attack.impact_spec.damage.base,3)
                shot=proof.ranged_shot if pc_side else proof.npc_ranged_shot
                self.assertIsInstance(shot.execution.weapon_state,FreeReloadWeaponState)
                self.assertIs(shot.execution.weapon_state.weapon_id,RangedWeaponId.SLING)
                self.assertIs(shot.preparation.source_request.target_range,RangedWeaponRange.MEDIUM)
        self.assertFalse(any(type(step.proof) in (PcRangedReloadProof,PcNpcRangedReloadProof)
            for step in result.steps))
        self.assertTrue(result.state.enemy(source.enemy_activation_order[0]).state.holds_shield)
        self.assert_replay(result)

    def test_initially_empty_shielded_pistol_keeps_its_initial_reload_cycle(self):
        from towr.domain.pc_npc_shield_models import NpcShieldLocation
        source=scene((item('empty-gun',W.PISTOL,G.LEFT,loaded=False),),
            ranged=GeneratedRangedFacts(6,6,3,6,True,True,True),rounds=1)
        npc=source.enemies[0].definition.generated_components
        npc=replace(npc,armour=ArmourLoadout(shield=ShieldKind.SHIELD))
        source=replace(source,enemies=(npc.participant('minion1'),))
        initial=initial_pc_melee_state(source).enemy('minion1').state.weapon_inventory.active.reload
        result=run_pc_melee_scenario(source,Tens())
        self.assertIsNone(result.unsupported)
        reload,=tuple(step.proof for step in result.steps if type(step.proof) is PcNpcRangedReloadProof)
        self.assertEqual(reload.request.weapon_state,initial)
        final=result.state.enemy('minion1').state.weapon_inventory.active.reload
        self.assertFalse(final.loaded)
        self.assertEqual(final.reload_cycle_ids,initial.reload_cycle_ids)
        self.assertEqual(len(final.exacting.contributions),1)
        self.assertEqual(final.exacting.accumulated_successes,0)
        self.assertEqual(result.state.npc_shields[0].location,NpcShieldLocation.DROPPED)
        self.assert_replay(result)

    def test_shield_allows_defence_against_shooting_without_erasing_held_sword_trait(self):
        from towr.domain.pc_generated_equipment import npc_protection_test
        from towr.domain.pc_npc_weapon_inventory import npc_protection_weapon_use
        from towr.domain.test_models import Skill
        source=scene((item('sword',W.SWORD,G.LEFT),),rounds=1)
        npc=source.enemies[0].definition.generated_components
        npc=replace(npc,armour=ArmourLoadout(shield=ShieldKind.SHIELD))
        source=replace(source,enemies=(npc.participant('minion1'),))
        state=initial_pc_melee_state(source)
        for attack_skill in (Skill.SHOOTING,Skill.THROWING):
            with self.subTest(attack_skill=attack_skill):
                use=npc_protection_weapon_use(state,'minion1',Skill.DEFENCE,attack_skill)
                self.assertTrue(use.shield_used)
                self.assertEqual(tuple(unit.source_item_id for unit in use.implements),('sword',))
                profile,request=npc_protection_test(state,'minion1','pc','protection',attack_skill=attack_skill)
                self.assertEqual(profile.skill,Skill.DEFENCE)
                self.assertEqual(sum(mod.amount for mod in request.dice_modifiers if mod.amount>0),1)

    def assert_replay(self,result):
        current=initial_pc_melee_state(result.source)
        for step in result.steps:
            self.assertEqual(step.source,current)
            current=apply_pc_melee_step(current,step)
            self.assertEqual(step.state,current)
        self.assertEqual(current,result.state)

    def test_two_loaded_pistols_shoot_before_reloading_one_actual_instance(self):
        source=scene((item('left',W.PISTOL,G.LEFT,loaded=True),item('right',W.PISTOL,G.RIGHT,loaded=True)),
            ranged=GeneratedRangedFacts(6,6,3,6,True,True,True))
        result=run_pc_melee_scenario(source,Tens())
        self.assertIsNone(result.unsupported)
        shots=tuple(step for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.npc_ranged_shot is not None)
        self.assertEqual(len(shots),2)
        ids=tuple(step.proof.npc_ranged_shot.execution.weapon_state.weapon_instance_id for step in shots)
        self.assertEqual(ids,tuple(weapon_unit_id('minion1',id,0) for id in ('left','right')))
        reloads=tuple(step for step in result.steps if type(step.proof) is PcNpcRangedReloadProof)
        self.assertEqual(len(reloads),1)
        self.assertEqual(reloads[0].proof.request.weapon_state.weapon_instance_id,ids[1])
        inventory=result.state.enemy('minion1').state.weapon_inventory
        self.assertTrue(all(not unit.reload.loaded for unit in inventory.items))
        self.assertEqual(sum(unit.location is L.HELD for unit in inventory.items),1)
        self.assert_replay(result)

    def test_melee_primary_draws_a_ready_carried_gun_and_preserves_source(self):
        source=scene((item('sword',W.SWORD,G.LEFT),item('gun',W.PISTOL,loaded=True)),
            ranged=GeneratedRangedFacts(6,6,3,6,True,True,True),rounds=1)
        result=run_pc_melee_scenario(source,Tens())
        self.assertIsNone(result.unsupported)
        swaps=tuple(step.proof for step in result.steps if type(step.proof) is PcNpcWeaponEquipProof)
        self.assertEqual(len(swaps),1)
        self.assertEqual(swaps[0].transition.after.active.source_item_id,'gun')
        shot=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.npc_ranged_shot is not None)
        self.assertEqual(shot.npc_ranged_shot.execution.weapon_state.weapon_instance_id,weapon_unit_id('minion1','gun',0))
        self.assertEqual(result.source.enemies,source.enemies)
        self.assert_replay(result)

    def test_spent_net_can_switch_to_carried_melee_without_fabricating_a_new_net(self):
        source=scene((item('net',W.WEIGHTED_NET,G.BOTH),item('sword',W.SWORD)),throwing=6,rounds=2)
        member=source.party[0]
        source=replace(source,party=(replace(member,pc=replace(member.pc,weapon_skill=3)),))
        result=run_pc_melee_scenario(source,Tens())
        self.assertIsNone(result.unsupported)
        inventory=result.state.enemy('minion1').state.weapon_inventory
        self.assertEqual(inventory.active.source_item_id,'sword')
        self.assertEqual(inventory.item(weapon_unit_id('minion1','net',0)).location,L.DEPLOYED)
        self.assertEqual(len(result.state.weighted_nets),1)
        self.assert_replay(result)

    def test_two_held_swords_supply_both_actual_defence_bonuses(self):
        source=scene((item('left',W.SWORD,G.LEFT),item('right',W.SWORD,G.RIGHT)),rounds=1)
        result=run_pc_melee_scenario(source,Tens())
        incoming=next(step.proof for step in result.steps if type(step.proof) is PcAttackProof
            and step.proof.request.actor_id=='pc')
        mods=incoming.request.kernel_request.attack.defender_test.dice_modifiers
        self.assertEqual(sum(mod.amount for mod in mods if mod.amount>0),2)
        self.assert_replay(result)

    def test_carried_bow_cannot_create_a_close_shot_without_a_battlefield(self):
        source=scene((item('sword',W.SWORD,G.LEFT),item('bow',W.SHORTBOW)),
            ranged=GeneratedRangedFacts(6,6,3,None,True,None,None,awareness=4),rounds=1)
        result=run_pc_melee_scenario(source,Tens())
        self.assertIsNone(result.unsupported)
        self.assertEqual(result.state.enemy('minion1').state.weapon_inventory.active.source_item_id,'sword')
        self.assertFalse(any(type(step.proof) is PcAttackProof and step.proof.npc_ranged_shot is not None
            for step in result.steps))
        self.assert_replay(result)

    def test_finite_carried_net_stock_throws_distinct_units_and_reconciles_carrying(self):
        source=scene((item('first',W.WEIGHTED_NET,G.BOTH),
            WeaponItemSource('stock',W.WEIGHTED_NET,L.CARRIED,None,quantity=2)),throwing=6)
        self.assertTrue(initial_pc_melee_state(source).enemy('minion1').state.injury.conditions.has(Condition.BURDENED))
        result=run_pc_melee_scenario(source,Tens())
        throws=tuple(step.proof.weighted_net_landing.item_id for step in result.steps
            if type(step.proof) is PcAttackProof and step.proof.request.actor_id=='minion1')
        self.assertEqual(len(throws),3)
        self.assertEqual(len(set(throws)),3)
        inventory=result.state.enemy('minion1').state.weapon_inventory
        self.assertTrue(all(unit.location is L.DEPLOYED for unit in inventory.items))
        self.assertFalse(result.state.enemy('minion1').state.injury.conditions.has(Condition.BURDENED))
        self.assertEqual(len(result.state.weighted_nets),3)
        self.assert_replay(result)

    def test_weapon_first_release_drops_the_same_shield_before_drawing_two_handed_weapon(self):
        from towr.domain.pc_npc_shield_models import PcNpcShieldDropProof,NpcShieldLocation
        source=scene((item('sword',W.SWORD,G.LEFT),item('hammer',W.GREATHAMMER)),rounds=1)
        npc=source.enemies[0].definition.generated_components
        npc=replace(npc,weapon_skill=3,melee=6,armour=ArmourLoadout(shield=ShieldKind.SHIELD))
        member=source.party[0]
        source=replace(source,enemies=(npc.participant('minion1'),),
            party=(replace(member,pc=replace(member.pc,toughness=5)),))
        result=run_pc_melee_scenario(source,FirstHitThenTens())
        self.assertIsNone(result.unsupported)
        drops=tuple(step for step in result.steps if type(step.proof) is PcNpcShieldDropProof)
        self.assertEqual(len(drops),1)
        self.assertEqual(drops[0].proof.weapon.source_item_id,'hammer')
        self.assertEqual(result.state.npc_shields[0].location,NpcShieldLocation.DROPPED)
        self.assertEqual(result.state.enemy('minion1').state.weapon_inventory.active.source_item_id,'hammer')
        self.assert_replay(result)


if __name__=='__main__':unittest.main()
