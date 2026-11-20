"""Canonical medical hand arrangements and actual physical item resources."""
from dataclasses import replace
from types import SimpleNamespace
import unittest

from tests.support.pc_shield_scenarios import make_pc_shield_scenario
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.unit.test_k1_combat_surgeon_treatment import untreated_state
from towr.domain.medical_preparation_models import MedicalPreparationFacts
from towr.domain.pc_melee_models import PcMeleePolicy,PcMeleeWeapon
from towr.domain.pc_melee_result_models import initial_pc_melee_state
from towr.domain.pc_medical_tactics import (
    MedicalActionChoice,MedicalActionKind,PcMedicalIntentProof,expected_medical_intent,
    committed_medical_intent,current_medical_choice,
)
from towr.domain.pc_medical_equipment_models import (
    expected_medical_preparation,project_medical_equipment,build_medical_tool_recover,
    complete_medical_tool_recover,project_medical_tool_recover,
)
from towr.domain.pc_medical_models import medical_hand_use
from towr.domain.armour_models import ArmourLoadout,ShieldKind
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.injury_models import (WoundRecord,WoundEntryId,WoundRestrictionEffect,WoundRestriction,
    WoundEffectDuration,WoundConditionEffect)
from towr.domain.condition_models import Condition
from towr.domain.pc_shield_models import PcShieldLocation
from towr.domain.tool_inventory_models import ToolItemSource,ToolKind
from towr.domain.weapon_inventory_models import WeaponItemLocation,WeaponGrip
from towr.domain.turn_models import (CombatTurnStartRequest,CombatActionSlotRequest,CombatActionDeclaration,
    CombatActionKind,ActionSlotGrant)
from towr.rules.turn_resolution import start_combat_turn,reserve_combat_action_slot


def source(*,shield=True,automatic=True):
    scene=make_pc_shield_scenario() if shield else make_pc_melee_scenario(weapon=PcMeleeWeapon.SWORD)
    member=scene.party[0]
    kit=ToolItemSource('kit',ToolKind.PHYSICKERS_KIT,1,WeaponItemLocation.CARRIED,None)
    pc=replace(member.pc,reason=3,recall=5,initiative=3,dexterity=5,
        medical=MedicalPreparationFacts(True,True,False),tools=(kit,))
    return replace(scene,party=(replace(member,pc=pc,policy=(PcMeleePolicy.AUTOMATIC_COMBAT
        if automatic else member.policy)),))


def prepared_state(*,shield=True,required=1,automatic=True):
    state=initial_pc_melee_state(source(shield=shield,automatic=automatic))
    state=replace(state,party=(replace(state.party[0],injury=untreated_state()),))
    clock=start_combat_turn(CombatTurnStartRequest('turn',state.round_state,'pc')).state
    state=replace(state,round_state=clock)
    choice=(expected_medical_intent(state).choice if required==1 and automatic else
        MedicalActionChoice(MedicalActionKind.SURGERY,'pc',1,2,True,0,
            state.party[0].tool_inventory.items[0].id))
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    intent=PcMedicalIntentProof('pc',pc_melee_action_id(state,'pc'),choice)
    return replace(state,history=(*state.history,intent))


def view(state,**updates):
    """Read-only preparation probe; not an invented admitted journal prefix."""
    class View:
        def __getattr__(self,name):return updates[name] if name in updates else getattr(state,name)
        def participant(self,actor):return next(member for member in self.party if member.actor_id==actor)
        def enemy(self,actor):return next(enemy for enemy in self.enemies if enemy.state.actor_id==actor)
    return View()


class MedicalEquipmentTests(unittest.TestCase):
    def test_one_hand_stows_weapon_preserving_shield_and_every_resource(self):
        state=prepared_state();before=state.party[0]
        proof=expected_medical_preparation(state)
        self.assertIsNotNone(proof)
        after=proof.equipment.state
        self.assertIs(after.shield.location,PcShieldLocation.HELD)
        self.assertIs(after.weapon_inventory.active.location,WeaponItemLocation.CARRIED)
        self.assertIsNone(after.weapon_inventory.active.grip)
        original=before.weapon_inventory.active
        self.assertEqual(after.weapon_inventory.active,replace(original,location=WeaponItemLocation.CARRIED,grip=None))
        updates=project_medical_equipment(state,proof)
        next_view=view(state,**updates)
        self.assertEqual(len(medical_hand_use(next_view,'pc').hands),1)
        self.assertEqual(current_medical_choice(next_view),committed_medical_intent(state).choice)
        self.assertEqual(proof.equipment.round_state,state.round_state)

    def test_two_hands_releases_real_shield_ground_and_stows_weapon(self):
        state=prepared_state(required=2)
        proof=expected_medical_preparation(state)
        after=proof.equipment.state
        self.assertIs(after.shield.location,PcShieldLocation.DROPPED)
        self.assertIsNotNone(after.shield.ground)
        self.assertEqual(after.shield.ground.zone_id,'arena')
        self.assertIsNone(after.weapon_inventory.shield_hand)
        updates=project_medical_equipment(state,proof)
        self.assertEqual(len(medical_hand_use(view(state,**updates),'pc',surgery=True).hands),2)

    def test_foreign_choice_and_second_same_action_preparation_rejected(self):
        state=prepared_state();proof=expected_medical_preparation(state)
        with self.assertRaises(ValueError):
            project_medical_equipment(state,replace(proof,choice=replace(proof.choice,target_id='foreign')))
        after=view(state,**project_medical_equipment(state,proof),history=(*state.history,proof))
        self.assertIsNone(expected_medical_preparation(after))
        with self.assertRaises(ValueError):project_medical_equipment(after,proof)

    def test_fixed_policy_does_not_acquire_automatic_medical_intent(self):
        state=initial_pc_melee_state(source(automatic=False))
        state=replace(state,party=(replace(state.party[0],injury=untreated_state()),),
            round_state=start_combat_turn(CombatTurnStartRequest('turn',state.round_state,'pc')).state)
        self.assertIsNone(expected_medical_intent(state))
        self.assertIsNone(current_medical_choice(state))

    def test_dropped_kit_has_paid_recover_and_cannot_be_remote_or_free(self):
        state=prepared_state(shield=False)
        member=state.party[0];kit=member.tool_inventory.items[0]
        dropped=replace(kit,location=WeaponItemLocation.DROPPED,dropped_zone_id='arena')
        before=view(state,party=(replace(member,tool_inventory=replace(member.tool_inventory,items=(dropped,))),),history=())
        intent=expected_medical_intent(before)
        self.assertTrue(intent.choice.pickup_tool)
        before=view(before,history=(intent,))
        self.assertIsNone(expected_medical_preparation(before))
        clock=reserve_combat_action_slot(CombatActionSlotRequest('reserve',before.round_state,'pc',
            CombatActionDeclaration(CombatActionKind.RECOVER),ActionSlotGrant.STANDARD)).state
        ready=view(before,round_state=clock)
        request=build_medical_tool_recover(ready)
        from towr.domain.pc_ally_recover_models import expected_pc_standard_recover
        result=expected_pc_standard_recover(request)
        proof=complete_medical_tool_recover(ready,result)
        updates=project_medical_tool_recover(ready,proof)
        held=updates['party'][0].tool_inventory.item(kit.id)
        self.assertIs(held.location,WeaponItemLocation.HELD)
        self.assertIsNotNone(updates['round_state'].active_turn.action_slots[0].execution)
        self.assertFalse(updates['party'][0].injury.wounds[0].treated)
        remote=replace(dropped,dropped_zone_id='elsewhere')
        remote_view=view(before,party=(replace(member,tool_inventory=replace(member.tool_inventory,items=(remote,))),))
        with self.assertRaises(ValueError):build_medical_tool_recover(view(remote_view,round_state=clock))

    def test_paid_kit_recover_prone_removal_keeps_actual_torn_leg_critical(self):
        state=prepared_state(shield=False);member=state.party[0];kit=member.tool_inventory.items[0]
        injury=replace(member.injury,wounds=(*member.injury.wounds,
            WoundRecord(3,WoundEntryId.TORN_LEG,13,(10,3),effect_resolved=True)),
            conditions=member.injury.conditions.with_condition(Condition.PRONE),
            active_wound_effects=(*member.injury.active_wound_effects,
                WoundConditionEffect(3,Condition.PRONE,WoundEffectDuration.UNTIL_REMOVED),
                WoundRestrictionEffect(3,WoundRestriction.REMOVING_PRONE_CAUSES_CRITICAL,WoundEffectDuration.UNTIL_HEALED)))
        dropped=replace(kit,location=WeaponItemLocation.DROPPED,dropped_zone_id='arena')
        before=view(state,party=(replace(member,injury=injury,
            tool_inventory=replace(member.tool_inventory,items=(dropped,))),),history=())
        intent=expected_medical_intent(before);before=view(before,history=(intent,))
        clock=reserve_combat_action_slot(CombatActionSlotRequest('reserve',before.round_state,'pc',
            CombatActionDeclaration(CombatActionKind.RECOVER),ActionSlotGrant.STANDARD)).state
        ready=view(before,round_state=clock)
        from towr.domain.pc_ally_recover_models import expected_pc_standard_recover
        proof=complete_medical_tool_recover(ready,expected_pc_standard_recover(build_medical_tool_recover(ready)))
        actual=project_medical_tool_recover(ready,proof)['party'][0].injury
        self.assertFalse(actual.conditions.has(Condition.PRONE))
        self.assertIn(WoundConditionEffect(3,Condition.CRITICALLY_INJURED,WoundEffectDuration.UNTIL_TREATED),
            actual.active_wound_effects)

    def test_generated_champion_shield_release_retains_true_hp_and_resilience_witness(self):
        base=make_pc_melee_scenario()
        npc=GeneratedNpc(3,3,3,3,5,4,initial_generated_weapons(GeneratedWeapon.SWORD),
            ArmourLoadout(shield=ShieldKind.SHIELD),defence=5,reason=3,recall=5,initiative=3,dexterity=5,
            medical=MedicalPreparationFacts(True,True,False),
            tools=(ToolItemSource('kit',ToolKind.PHYSICKERS_KIT,1,WeaponItemLocation.CARRIED,None),),
            injury_policy=TargetInjuryPolicy.CHAMPION,endurance=4)
        state=initial_pc_melee_state(replace(base,enemies=(npc.participant('minion1'),)))
        enemy=state.enemy('minion1')
        state=replace(state,enemies=(replace(enemy,state=replace(enemy.state,injury=untreated_state())),))
        clock=start_combat_turn(CombatTurnStartRequest('turn',
            replace(state.round_state,completed_turn_entity_ids=('pc',)),'minion1')).state
        state=replace(state,round_state=clock)
        from towr.domain.pc_melee_result_models import pc_melee_action_id
        choice=MedicalActionChoice(MedicalActionKind.SURGERY,'minion1',1,2,True,0,enemy.state.tool_inventory.items[0].id)
        state=replace(state,history=(PcMedicalIntentProof('minion1',pc_melee_action_id(state,'minion1'),choice),))
        proof=expected_medical_preparation(state)
        self.assertIsNotNone(proof.equipment.previous_npc_shield)
        self.assertFalse(proof.equipment.state.state.holds_shield)
        self.assertEqual(proof.equipment.state.state.current_resilience.total,
            enemy.state.current_resilience.total-1)
        self.assertEqual(proof.equipment.state.state.injury.wounds,untreated_state().wounds)
        updates=project_medical_equipment(state,proof)
        self.assertEqual(len(medical_hand_use(view(state,**updates),'minion1',surgery=True).hands),2)


if __name__=='__main__':unittest.main()
