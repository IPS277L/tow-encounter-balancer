"""Prepared own-body end phases with real Recover and Hazard receipts."""
from copy import copy
from dataclasses import fields, replace
from unittest import TestCase, main

from tests.support.pc_companion_attack_views import CompanionAttackView, prepared_companion_attack
from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_pc_mount_companion_owner import source
from towr.domain.condition_models import Condition
from towr.domain.magic_models import WizardMagicState
from towr.domain.pc_actor_models import pc_actor_injury, pc_actor_npc_update
from towr.domain.pc_ally_recover_models import expected_pc_standard_recover
from towr.domain.pc_battlefield_movement_models import PcBattlefieldRecoverProof
from towr.domain.pc_companion_turn_models import expected_companion_wait
from towr.domain.pc_melee_result_models import PcRecoverProof, initial_pc_melee_state, pc_melee_action_id, pc_melee_round_participants
from towr.domain.pc_mount_models import CombatMount, expected_pc_dismount, mount_resilience_bonus, updated_pc_mounts
from towr.domain.pc_weapon_area_models import (
    PcWeaponHazardProof, expected_ablaze_hazard, project_weapon_area_step, weapon_hazard_resolution_request,
)
from towr.domain.recover_models import RecoverActionExecutionRequest, RecoverMode, RecoverStandardChoice
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundState, CombatTurnStartRequest,
)
from towr.rules.hazard_resolution import resolve_hazard
from towr.rules.test_resolution import resolve_test
from towr.rules.turn_resolution import reserve_combat_action_slot, start_combat_turn


def burning(view, actor):
    injury=pc_actor_injury(view,actor)
    after=replace(injury,conditions=injury.conditions.with_condition(Condition.ABLAZE))
    for key,value in pc_actor_npc_update(view,actor,injury=after).items(): setattr(view,key,value)


def mounted_end_phase(*,npc=False,kind=CombatMount.DEMIGRYPH,round_number=1):
    initial=initial_pc_melee_state(source(kind))
    view=CompanionAttackView(**{field.name:getattr(initial,field.name) for field in fields(initial)})
    actor=(view.source.enemy_activation_order if npc else view.source.pc_activation_order)[0]
    clock=replace(view.round_state,round_number=round_number,
        completed_turn_entity_ids=view.source.pc_activation_order if npc else ())
    identifier=pc_melee_action_id(view,actor)
    clock=start_combat_turn(CombatTurnStartRequest(identifier+':start',clock,actor)).state
    clock=reserve_combat_action_slot(CombatActionSlotRequest(identifier+':reserve',clock,actor,
        CombatActionDeclaration(CombatActionKind.RECOVER),ActionSlotGrant.STANDARD)).state
    injury=pc_actor_injury(view,actor)
    request=RecoverActionExecutionRequest(identifier+':recover',clock,actor,injury.conditions,True,1,
        RecoverMode.STANDARD,RecoverStandardChoice(WizardMagicState()))
    result=expected_pc_standard_recover(request)
    view.round_state=result.round_state
    proof=(PcBattlefieldRecoverProof(request,result,injury,injury) if npc else PcRecoverProof(result))
    view.history=(*view.history,proof)
    burning(view,actor+':mount')
    return view,actor,actor+':mount'


def settle(view, values):
    request=expected_ablaze_hazard(view)
    rng=ScriptedD10(values)
    test=resolve_test(request.avoidance_test,rng)
    result=resolve_hazard(weapon_hazard_resolution_request(request,test),rng)
    rng.assert_exhausted()
    proof=PcWeaponHazardProof(request,test,result)
    updates=project_weapon_area_step(view,proof)
    after=copy(view)
    for key,value in updates.items(): setattr(after,key,value)
    after.history=(*view.history,proof)
    return after,proof


class CompanionPeriodicTests(TestCase):
    def test_mounted_body_uses_its_own_hp_test_and_actual_rider_clock_on_both_sides(self):
        for npc in (False,True):
            with self.subTest(npc=npc):
                view,rider,body=mounted_end_phase(npc=npc)
                request=expected_ablaze_hazard(view)
                self.assertEqual(request.actor_id,body)
                self.assertEqual(request.periodic_clock,view.round_state)
                self.assertEqual(request.periodic_clock.active_turn.actor_id,rider)
                self.assertEqual(request.avoidance_test.profile.base_dice,4)
                after,proof=settle(view,[1,10,10,10])
                self.assertEqual(pc_actor_injury(after,body).wounds,1)
                self.assertTrue(pc_actor_injury(after,body).conditions.has(Condition.DRAINED))
                self.assertEqual(after.party,view.party)
                self.assertEqual(after.enemies,view.enemies)
                self.assertEqual(after.round_state,view.round_state)
                self.assertIsNone(proof.fate_decline)
                self.assertIsNone(proof.glorious)
                self.assertIsNone(expected_ablaze_hazard(after))
                with self.assertRaises(ValueError): project_weapon_area_step(after,proof)
                wrong_clock=mounted_end_phase(npc=npc,round_number=2)[0].round_state
                forged=replace(proof,request=replace(request,periodic_clock=wrong_clock))
                with self.assertRaises(ValueError): project_weapon_area_step(view,forged)

    def test_waiting_detached_body_cannot_skip_fire_or_gain_a_second_tick_after_remount(self):
        view,_,body=prepared_companion_attack(kind=CombatMount.DEMIGRYPH)
        view.round_state=CombatRoundState(2,pc_melee_round_participants(view),
            completed_turn_entity_ids=view.source.pc_activation_order)
        view.round_state=start_combat_turn(CombatTurnStartRequest('companion:start',view.round_state,body)).state
        burning(view,body)
        self.assertIsNotNone(expected_companion_wait(view))
        after,proof=settle(view,[1]*4)
        self.assertEqual(proof.request.periodic_clock.active_turn.actor_id,body)
        self.assertIsNone(expected_ablaze_hazard(after))
        remounted,rider,_=mounted_end_phase(kind=CombatMount.DEMIGRYPH,round_number=2)
        remounted.history=(*remounted.history,proof)
        self.assertIsNone(expected_ablaze_hazard(remounted))

    def test_body_defeat_removes_mount_bonuses_with_its_own_dismount_witness(self):
        view,rider,body=mounted_end_phase(kind=CombatMount.HORSE)
        after,_=settle(view,[10]*3)
        self.assertTrue(pc_actor_injury(after,body).defeated)
        self.assertEqual(pc_actor_injury(after,rider),pc_actor_injury(view,rider))
        proof=expected_pc_dismount(after)
        self.assertEqual(proof.actor_id,rider)
        self.assertEqual(proof.mount_injury,pc_actor_injury(after,body))
        self.assertEqual(proof.source_injury,pc_actor_injury(after,rider))
        self.assertFalse(proof.source_injury.conditions.has(Condition.PRONE))
        self.assertEqual(mount_resilience_bonus(after,rider),0)
        self.assertFalse(next(row for row in updated_pc_mounts(after,proof) if row.actor_id==rider).mounted)
        with self.assertRaises(ValueError): updated_pc_mounts(after,replace(proof,mount_injury=None))


if __name__=='__main__': main()
