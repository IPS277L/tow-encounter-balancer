"""Actual K1 moves feed one mandatory terrain Test, without another action.

Prepared initial turn clocks isolate this owner. They are not complete battle
replays; movement source/results and Tests themselves are executed by K1.
"""
from dataclasses import replace
import json
from random import Random
import unittest

from tests.support.magic_weapon_fixtures import request
from tests.support.pc_melee_scripted import ScriptedD10
from towr.adapters.dynamic_encounter_json import parse_dynamic_encounter_request
from towr.domain.condition_models import Condition
from towr.domain.pc_battlefield_movement_models import expected_pc_battlefield_move
from towr.domain.pc_melee_result_models import initial_pc_melee_state,PcFateDecline
from towr.domain.pc_terrain_models import (
    PcTerrainTraversalProof,expected_pc_terrain_traversal,project_pc_terrain,
)
from towr.domain.test_models import Skill
from towr.domain.turn_models import (
    CombatTurnStartRequest,CombatActionSlotRequest,CombatActionDeclaration,
    CombatActionKind,ManoeuvreKind,ActionSlotGrant,
)
from towr.domain.weapon_effect_preparation import STAFF_TERRAIN_RULE_ID
from towr.rules.difficult_terrain_resolution import resolve_difficult_terrain_traversal
from towr.rules.turn_resolution import start_combat_turn,reserve_combat_action_slot


def moved(*,npc=False,staff=True,distance='long',fate=0):
    raw=request('staff' if staff else 'sword')
    raw['party'][0]['resources']['fate']=fate
    raw['scene'].update(range=distance,zone_features=[dict(index=1,difficult_terrain=True)])
    raw['npc_count']=dict(minimum=1,maximum=1)
    raw['search_space'].update(weapon=['staff' if staff else 'sword'],mount=[None],weapon_count=[1])
    command=parse_dynamic_encounter_request(json.dumps(raw))
    source=command.request.scenario((command.request.space.sample(Random(1)),),'terrain')
    current=initial_pc_melee_state(source)
    actor=source.enemy_activation_order[0] if npc else source.pc_activation_order[0]
    clock=current.round_state
    if npc:clock=replace(clock,completed_turn_entity_ids=source.pc_activation_order)
    start=start_combat_turn(CombatTurnStartRequest('terrain:start',clock,actor))
    current=replace(current,round_state=start.state)
    move=expected_pc_battlefield_move(current)
    if move is None:raise AssertionError('fixture needs the actual automatic incidental move')
    return replace(current,battlefield=move.state,history=(*current.history,move))


def completed(current,*,success):
    expected=expected_pc_terrain_traversal(current)
    if expected is None:raise AssertionError('fixture needs actual ground terrain')
    # A generous finite literal pool; only a prefix is needed for these Tests.
    rng=ScriptedD10(([1] if success else [10])*20)
    result=resolve_difficult_terrain_traversal(expected.traversal,rng)
    actor=expected.actor_id
    decline=(PcFateDecline(actor,expected.athletics_test.id,'test',current.source.participant(actor).fate_policy)
        if actor in current.source.pc_activation_order else None)
    return PcTerrainTraversalProof(expected,result,decline)


class PcTerrainTests(unittest.TestCase):
    def test_move_carefully_is_a_real_action_for_both_roles_with_no_terrain_test(self):
        from towr.domain.pc_battlefield_manoeuvre_models import (
            proposed_pc_battlefield_manoeuvre,build_pc_battlefield_careful,
            PcBattlefieldCarefulProof,battlefield_after_manoeuvre,project_pc_battlefield_manoeuvre,
        )
        from towr.rules.move_carefully_resolution import execute_move_carefully_action
        for npc in (False,True):
            with self.subTest(npc=npc):
                raw=request('sword');raw['party'][0]['resources']['fate']=0
                raw['party'][0]['characteristics']['agility']=1
                raw['party'][0]['skills']['athletics']=2
                raw['scene'].update(range='medium',zone_features=[dict(index=0,difficult_terrain=True),
                    dict(index=1,difficult_terrain=True)])
                raw['npc_count']=dict(minimum=1,maximum=1)
                raw['search_space'].update(weapon=['sword'],weapon_count=[1],agility=[1],athletics=[2],mount=[None])
                command=parse_dynamic_encounter_request(json.dumps(raw))
                source=command.request.scenario((command.request.space.sample(Random(1)),),'careful')
                current=initial_pc_melee_state(source)
                actor=source.enemy_activation_order[0] if npc else source.pc_activation_order[0]
                clock=current.round_state
                if npc:clock=replace(clock,completed_turn_entity_ids=source.pc_activation_order)
                clock=start_combat_turn(CombatTurnStartRequest('careful:start',clock,actor)).state
                current=replace(current,round_state=clock)
                proposal=proposed_pc_battlefield_manoeuvre(current)
                self.assertIs(proposal.kind,ManoeuvreKind.MOVE_CAREFULLY)
                self.assertIsNone(expected_pc_battlefield_move(current))
                clock=reserve_combat_action_slot(CombatActionSlotRequest('careful:slot',clock,actor,
                    CombatActionDeclaration(CombatActionKind.MANOEUVRE,manoeuvre=ManoeuvreKind.MOVE_CAREFULLY),
                    ActionSlotGrant.STANDARD)).state
                current=replace(current,round_state=clock)
                request_=build_pc_battlefield_careful(current,proposal.target_id)
                result=execute_move_carefully_action(request_)
                after=battlefield_after_manoeuvre(current,result,proposal.target_id)
                proof=PcBattlefieldCarefulProof(request_,result,current.battlefield,after,target_id=proposal.target_id)
                updates=project_pc_battlefield_manoeuvre(current,proof)
                current=replace(current,**updates,history=(*current.history,proof))
                self.assertEqual(len(current.round_state.active_turn.action_slots),1)
                self.assertTrue(current.round_state.active_turn.action_slots[0].executed)
                self.assertIn(actor,current.battlefield.spatial.free_move_used_entity_ids)
                self.assertNotIn(actor,current.battlefield.spatial.difficult_terrain_tested_entity_ids)
                self.assertIsNone(result.awareness_test_result)
                self.assertIsNone(expected_pc_terrain_traversal(current))

    def test_both_roles_resolve_once_after_actual_crossing_with_a_real_staff(self):
        for npc in (False,True):
            for success in (False,True):
                with self.subTest(npc=npc,success=success):
                    current=moved(npc=npc)
                    before=current.battlefield
                    proof=completed(current,success=success)
                    self.assertIs(proof.request.movement.movement_request.crosses_difficult_terrain,True)
                    self.assertIs(proof.request.movement.movement_request.terrain_resolution_deferred,True)
                    self.assertTrue(any(mod.rule_id==STAFF_TERRAIN_RULE_ID and mod.amount==1
                        for mod in proof.request.athletics_test.dice_modifiers))
                    updates=project_pc_terrain(current,proof)
                    after=replace(current,**updates,history=(*current.history,proof))
                    self.assertEqual(after.round_state,current.round_state)
                    self.assertEqual(after.battlefield.spatial.placements,before.spatial.placements)
                    self.assertEqual(after.battlefield.spatial.free_move_used_entity_ids,before.spatial.free_move_used_entity_ids)
                    self.assertIn(proof.request.actor_id,after.battlefield.spatial.difficult_terrain_tested_entity_ids)
                    injury=(after.enemy(proof.request.actor_id).state.injury if npc else after.participant(proof.request.actor_id).injury)
                    self.assertIs(injury.conditions.has(Condition.PRONE),not success)
                    self.assertIsNone(expected_pc_terrain_traversal(after))
                    with self.assertRaises(ValueError):project_pc_terrain(after,proof)

    def test_staff_modifier_has_no_invented_item_when_no_staff_is_held(self):
        proof=completed(moved(staff=False),success=True)
        self.assertFalse(any(mod.rule_id==STAFF_TERRAIN_RULE_ID for mod in proof.request.athletics_test.dice_modifiers))
        self.assertIsNone(proof.request.staff_use)

    def test_forged_route_movement_origin_clock_and_test_result_are_rejected(self):
        current=moved();proof=completed(current,success=True)
        for changed in (dict(movement_index=proof.request.movement_index+1),
                dict(crossed_zone_ids=('arena:zone:0',)),dict(staff_use=None)):
            forged=replace(proof,request=replace(proof.request,**changed))
            with self.subTest(changed=changed),self.assertRaises(ValueError):project_pc_terrain(current,forged)
        with self.assertRaises((ValueError,TypeError)):
            forged_result=replace(proof.result,athletics_test_result=replace(proof.result.athletics_test_result,
                trace=replace(proof.result.athletics_test_result.trace,request_id='other-test')))
            project_pc_terrain(current,replace(proof,result=forged_result))

    def test_completed_crossing_rejects_another_actors_position_before_rng(self):
        current=moved();request=expected_pc_terrain_traversal(current)
        bad=replace(request.traversal.completed_crossing,placements=tuple(
            replace(item,zone_id='arena:zone:-1') if item.entity_id!=request.actor_id else item
            for item in request.traversal.completed_crossing.placements))
        with self.assertRaises(ValueError):replace(request.traversal,completed_crossing=bad)

    def test_plain_clear_route_guard_is_not_bypassed_without_explicit_deferred_phase(self):
        from towr.rules.free_movement_resolution import resolve_free_movement
        current=moved();move=current.history[-1]
        with self.assertRaises(ValueError):resolve_free_movement(replace(move.movement_request,
            terrain_resolution_deferred=False))
        with self.assertRaises(ValueError):replace(move.movement_request,crosses_difficult_terrain=False)
        self.assertEqual(resolve_free_movement(move.movement_request),move.movement_result)

    def test_terrain_test_excludes_long_charge_and_optional_run_extension_this_turn(self):
        from towr.domain.pc_battlefield_manoeuvre_models import (
            proposed_pc_battlefield_manoeuvre,build_pc_battlefield_run,build_pc_battlefield_run_extension,
        )
        from towr.rules.run_action_execution import execute_run_action
        current=moved(distance='extreme');proof=completed(current,success=True)
        current=replace(current,**project_pc_terrain(current,proof),history=(*current.history,proof))
        proposal=proposed_pc_battlefield_manoeuvre(current)
        self.assertIs(proposal.kind,ManoeuvreKind.RUN)
        actor=proposal.actor_id
        clock=reserve_combat_action_slot(CombatActionSlotRequest('terrain:run',current.round_state,actor,
            CombatActionDeclaration(CombatActionKind.MANOEUVRE,manoeuvre=ManoeuvreKind.RUN),
            ActionSlotGrant.STANDARD)).state
        current=replace(current,round_state=clock)
        request=build_pc_battlefield_run(current,proposal.target_id)
        result=execute_run_action(request)
        self.assertIsNone(build_pc_battlefield_run_extension(current,result,proposal.target_id))

    def test_npc_cannot_invent_pc_fate_for_terrain(self):
        current=moved(npc=True);proof=completed(current,success=True)
        actor=proof.request.actor_id
        decline=PcFateDecline(actor,proof.request.athletics_test.id,'test',current.source.party[0].fate_policy)
        with self.assertRaises(ValueError):project_pc_terrain(current,replace(proof,fate_decline=decline))

    def test_pc_glorious_spends_actual_fate_once_without_rerunning_movement(self):
        from towr.engine.pc_melee_runner import _resolve_pc_test,_Decisions
        from towr.rules.difficult_terrain_resolution import _complete_difficult_terrain_after_test
        current=moved(fate=1)
        request_=expected_pc_terrain_traversal(current)
        # Ag3 plus the one actual held Staff: four initial failures, four rerolls.
        rng=ScriptedD10((10,10,10,10,1,1,1,1))
        test,decline,spend,effective=_resolve_pc_test(current,request_.actor_id,Skill.ATHLETICS,
            request_.athletics_test,rng,_Decisions())
        rng.assert_exhausted()
        self.assertIsNotNone(spend)
        self.assertIsNone(decline)
        result=_complete_difficult_terrain_after_test(replace(request_.traversal,athletics_test=effective),test)
        proof=PcTerrainTraversalProof(request_,result,decline,spend)
        updates=project_pc_terrain(current,proof)
        self.assertEqual(updates['party'][0].fate.remaining_spends,0)
        self.assertEqual(updates['party'][0].fate.spends[-1].id,spend.spend.id)
        self.assertEqual(updates['battlefield'].spatial.placements,current.battlefield.spatial.placements)
        self.assertNotIn('round_state',updates)
        with self.assertRaises((ValueError,TypeError)):project_pc_terrain(current,replace(proof,glorious=None))

    def test_drained_does_not_add_staff_dice_or_optional_hand_use(self):
        for npc in (False,True):
            with self.subTest(npc=npc):
                current=moved(npc=npc)
                actor=current.round_state.active_turn.actor_id
                if npc:
                    enemy=current.enemy(actor)
                    enemy=replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
                        conditions=enemy.state.injury.conditions.with_condition(Condition.DRAINED))))
                    current=replace(current,enemies=(enemy,))
                else:
                    member=current.participant(actor)
                    member=replace(member,injury=replace(member.injury,
                        conditions=member.injury.conditions.with_condition(Condition.DRAINED)))
                    current=replace(current,party=(member,))
                request_=expected_pc_terrain_traversal(current)
                self.assertIsNone(request_.staff_use)
                self.assertFalse(any(mod.amount>0 for mod in request_.athletics_test.dice_modifiers))

