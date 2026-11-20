"""Departure source/geometry/clock boundaries, without native encounter runs.

Retention receipts are real. Later rider injuries/clocks are explicitly prepared
views with real K1 death receipts; these are not whole native battle journals.
"""
from copy import copy, deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.talent_sources import free_talent
from tests.unit.test_pc_mount_companion_owner import source as mount_source
from towr.domain import talent_actor_models
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.condition_models import Condition
from towr.domain.critical_injury_models import CriticalInjuryTestRequest
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.pc_actor_models import pc_active_actor_ids, pc_actor_side
from towr.domain.pc_companion_departure_models import (
    PcCompanionDepartureProof, expected_companion_departure, project_companion_departure,
)
from towr.domain.pc_companion_usage_models import capture_companion_usage
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcCriticalProof, PcFateDecline, PcIncapacitatedTurnEndProof,
    PcMeleeState, PcMeleeStep, PcProfileWoundProof, _pc_test, initial_pc_melee_state, prepare_pc_weapon_kernel,
)
from towr.domain.pc_mount_models import expected_pc_dismount
from towr.domain.pc_mount_retention_models import expected_pc_mount_retention
from towr.domain.pc_npc_exit_models import PcNpcExitProof
from towr.domain.pc_weapon_area_models import (
    ABLAZE_HAZARD_RULE_ID, PcWeaponHazardProof, _hazard_request, weapon_hazard_resolution_request,
)
from towr.domain.pc_weapon_intent_models import build_pc_explicit_attack_weapon_intent
from towr.domain.movement_models import FreeMovementRequest, MovementSpeed
from towr.domain.talent_catalog import TalentId
from towr.domain.test_models import Skill, _expected_initial_roll_parameters
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundState, CombatSide, CombatTurnEndResult, CombatTurnParticipant, CombatTurnStartRequest,
)
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.critical_injury_resolution import resolve_critical_injury_test
from towr.rules.free_movement_resolution import resolve_free_movement
from towr.rules.hazard_resolution import resolve_hazard
from towr.rules.test_resolution import resolve_test
from towr.rules.turn_resolution import reserve_combat_action_slot, start_combat_turn


class Preparation(SimpleNamespace):
    participant = PcMeleeState.participant
    enemy = PcMeleeState.enemy


def clock(state, actor, *, action=None):
    side = pc_actor_side(state,actor)
    opposite = CombatSide.OPPOSITION if side is CombatSide.PLAYERS_AND_ALLIES else CombatSide.PLAYERS_AND_ALLIES
    ids = (actor,*(candidate for candidate in pc_active_actor_ids(state) if candidate != actor))
    result = CombatRoundState(2,tuple(CombatTurnParticipant(value,pc_actor_side(state,value)) for value in ids),
        side_order=(side,opposite))
    result = start_combat_turn(CombatTurnStartRequest('prepared:start:'+actor,result,actor)).state
    if action is not None:
        result = reserve_combat_action_slot(CombatActionSlotRequest('prepared:reserve:'+actor,result,actor,
            CombatActionDeclaration(action),ActionSlotGrant.STANDARD)).state
    state.round_state = result
    state.battlefield = replace(state.battlefield,spatial=replace(state.battlefield.spatial,round_number=2))


def view(*, npc=False, mounted=False, disposition=NpcDefeatDisposition.KILLED):
    source = mount_source()
    talent = free_talent(TalentId.BACK_IN_THE_SADDLE)
    components = replace(source.enemies[0].definition.generated_components,endurance=3,
        talents=(talent,) if npc else ())
    source = replace(source,max_rounds=3,enemies=(components.participant('minion1'),),
        party=(replace(source.party[0],talents=() if npc else (talent,),
            defeat_decisions=tuple(replace(decision,disposition=disposition)
                for decision in source.party[0].defeat_decisions)),))
    actual = initial_pc_melee_state(source)
    if not mounted:
        if npc:
            enemy = actual.enemies[0]
            actual = replace(actual,enemies=(replace(enemy,state=replace(enemy.state,
                injury=replace(enemy.state.injury,conditions=enemy.state.injury.conditions.with_condition(Condition.PRONE)))),))
        else:
            member = actual.party[0]
            actual = replace(actual,party=(replace(member,injury=replace(member.injury,
                conditions=member.injury.conditions.with_condition(Condition.PRONE))),))
        actual = PcMeleeStep(actual,expected_pc_dismount(actual)).state
        actual = PcMeleeStep(actual,expected_pc_mount_retention(actual)).state
    state = Preparation(**{name:getattr(actual,name) for name in actual.__dataclass_fields__})
    state.exited_npc_ids = actual.exited_npc_ids
    return state


def pc_critical_death(state):
    actor = state.source.pc_activation_order[0]
    member = state.participant(actor)
    injured = replace(member.injury,conditions=member.injury.conditions
        .with_condition(Condition.CRITICALLY_INJURED).with_condition(Condition.DEFENCELESS))
    state.party = tuple(replace(row,injury=injured) if row.actor_id == actor else row for row in state.party)
    clock(state,actor)
    test_request = _pc_test(state,actor,'prepared:critical:endurance',Skill.ENDURANCE)
    rng = ScriptedD10([10]*_expected_initial_roll_parameters(test_request)[5])
    test = resolve_test(test_request,rng)
    rng.assert_exhausted()
    result = resolve_critical_injury_test(CriticalInjuryTestRequest('prepared:critical',actor,injured,test_request.id),test)
    critical = PcCriticalProof(test_request,result,PcFateDecline(actor,test_request.id,'test',
        state.source.participant(actor).fate_policy))
    previous = state.round_state
    following = replace(previous,active_turn=None,completed_turn_entity_ids=(actor,))
    receipt = CombatTurnEndResult('prepared:end',following,previous.active_turn,following.next_side,
        following.round_complete,('RULE-COMBAT-001:rounds-sides-turns','RULE-HEALTH-008:defenceless-turn'))
    proof = PcIncapacitatedTurnEndProof(receipt,critical)
    state.party = tuple(replace(row,injury=result.state) if row.actor_id == actor else row for row in state.party)
    state.round_state = following
    state.history = (*state.history,proof)
    return proof


def npc_attack_defeat(state, *, disposition=NpcDefeatDisposition.KILLED):
    actor,target = state.source.pc_activation_order[0],state.source.enemy_activation_order[0]
    clock(state,actor,action=CombatActionKind.ATTACK)
    action_id = 'prepared:physical-kill'
    intent = build_pc_explicit_attack_weapon_intent(state,actor,target,action_id)
    kernel,protection = prepare_pc_weapon_kernel(state,intent,action_id)
    request = AttackActionExecutionRequest(action_id,state.round_state,actor,target,1,kernel)
    attack_dice = _expected_initial_roll_parameters(kernel.attack.attacker_test)[5]
    defender = kernel.attack.defender_test
    defence_dice = 0 if defender is None else _expected_initial_roll_parameters(defender)[5]
    rng = ScriptedD10([1]*attack_dice+[10]*defence_dice)
    result = execute_attack_action(request,rng)
    rng.assert_exhausted()
    attack = PcAttackProof(request,protection,result,None,weapon_intent=intent)
    source_decision = state.source.participant(actor).defeat_decision(target)
    decision = replace(source_decision,disposition=disposition)
    acknowledgement = PcProfileWoundProof(result.resolution.profile_wound.state_change,decision)
    state.enemies = tuple(replace(row,state=replace(row.state,injury=result.resolution.target_state))
        if row.state.actor_id == target else row for row in state.enemies)
    state.history = (*state.history,attack,acknowledgement)
    state.round_state = result.state
    return acknowledgement


class CompanionDepartureTests(unittest.TestCase):
    def setUp(self):
        # Explicit local admission for retained-body source fixtures. Public
        # Back in the Saddle admission is owned by the whole feature checkpoint.
        for name in ('PC_EXECUTABLE_TALENTS','NPC_EXECUTABLE_TALENTS'):
            self.enterContext(patch.object(talent_actor_models,name,
                getattr(talent_actor_models,name)|{TalentId.BACK_IN_THE_SADDLE}))

    def test_confirmed_pc_death_preserves_body_hp_conditions_and_cleans_only_its_presence(self):
        state = view()
        death = pc_critical_death(state)
        actor = 'pc1:mount'
        state.battlefield = replace(state.battlefield,spatial=replace(state.battlefield.spatial,
            gave_ground_entity_ids=(actor,'minion1'),free_move_used_entity_ids=('minion1',actor),
            difficult_terrain_tested_entity_ids=(actor,)))
        body = state.companions[0]
        own_injury = replace(body.snapshot.state.injury,
            conditions=body.snapshot.state.injury.conditions.with_condition(Condition.ABLAZE))
        body = replace(body,snapshot=replace(body.snapshot,state=replace(body.snapshot.state,injury=own_injury)),
            stored_spatial_usage=capture_companion_usage(state.battlefield,actor))
        state.companions = (body,*state.companions[1:])
        proof = expected_companion_departure(state)
        self.assertIs(proof.source_proof,death)
        self.assertEqual(proof.source_history_index,len(state.history)-1)
        self.assertEqual(proof.source_id,death.result.request_id)
        updates = project_companion_departure(state,proof)
        self.assertEqual(set(updates),{'companions','mounts','battlefield','round_state'})
        self.assertIs(updates['companions'][0].snapshot,body.snapshot)
        self.assertIsNone(updates['companions'][0].retained_since_round)
        self.assertIsNone(updates['companions'][0].stored_spatial_usage)
        self.assertEqual(updates['companions'][1:],state.companions[1:])
        self.assertEqual(updates['battlefield'].spatial.free_move_used_entity_ids,('minion1',))
        self.assertEqual(updates['battlefield'].spatial.gave_ground_entity_ids,('minion1',))
        self.assertEqual(updates['battlefield'].spatial.difficult_terrain_tested_entity_ids,())
        self.assertFalse(any(actor in pair for pair in updates['battlefield'].close_pairs))
        self.assertEqual(tuple(row for row in state.battlefield.spatial.placements if row.entity_id != actor),
            updates['battlefield'].spatial.placements)
        self.assertEqual(updates['round_state'].participants,state.round_state.participants)
        self.assertEqual(updates['round_state'].completed_turn_entity_ids,state.round_state.completed_turn_entity_ids)
        self.assertEqual(updates['round_state'].excluded_turn_entity_ids,(actor,))

    def test_acknowledged_npc_kill_excludes_only_its_unused_body_turn_and_preserves_foreign_active_turn(self):
        state = view(npc=True)
        acknowledgement = npc_attack_defeat(state)
        proof = expected_companion_departure(state)
        self.assertIs(proof.source_proof,acknowledgement)
        updates = project_companion_departure(state,proof)
        self.assertEqual(proof.rider_id,'minion1')
        self.assertEqual(proof.actor_id,'minion1:mount')
        self.assertIs(updates['round_state'].active_turn,state.round_state.active_turn)
        self.assertEqual(updates['round_state'].excluded_turn_entity_ids,('minion1:mount',))
        completed = copy(state)
        completed.round_state = replace(state.round_state,completed_turn_entity_ids=('minion1:mount',))
        proof = expected_companion_departure(completed)
        self.assertIs(proof.round_state,completed.round_state)

    def test_knockout_defenceless_raw_death_pending_work_or_missing_talent_does_not_depart(self):
        state = view(npc=True,disposition=NpcDefeatDisposition.KNOCKED_OUT)
        npc_attack_defeat(state,disposition=NpcDefeatDisposition.KNOCKED_OUT)
        self.assertIsNone(expected_companion_departure(state))
        for conditions_only in (True,False):
            state = view()
            member = state.party[0]
            injury = (replace(member.injury,conditions=member.injury.conditions.with_condition(Condition.DEFENCELESS))
                if conditions_only else replace(member.injury,dead=True))
            state.party = (replace(member,injury=injury),)
            self.assertIsNone(expected_companion_departure(state))
        state = view()
        pc_critical_death(state)
        for field,value in (('pending',(object(),)),('pending_wound',object()),('magic_pending',object())):
            blocked = copy(state)
            setattr(blocked,field,value)
            self.assertIsNone(expected_companion_departure(blocked))
        missing = copy(state)
        missing.source = replace(state.source,party=(replace(state.source.party[0],talents=()),))
        self.assertIsNone(expected_companion_departure(missing))

    def test_mounted_departure_clears_only_actual_mount_without_inventing_prone_fall_or_body_damage(self):
        for npc in (False,True):
            state = view(npc=npc,mounted=True)
            if npc:
                npc_attack_defeat(state)
            else:
                pc_critical_death(state)
            proof = expected_companion_departure(state)
            with self.subTest(npc=npc):
                self.assertTrue(proof.previous_mount.mounted)
                self.assertFalse(proof.mount.mounted)
                self.assertEqual(proof.previous,proof.state)
                self.assertIsNone(proof.previous.retained_since_round)
                self.assertIs(proof.battlefield,state.battlefield)
                self.assertIs(proof.round_state,state.round_state)
                updates = project_companion_departure(state,proof)
                self.assertEqual(tuple(row for row in updates['mounts'] if row.actor_id != proof.rider_id),
                    tuple(row for row in state.mounts if row.actor_id != proof.rider_id))
                self.assertIs(updates['companions'][0 if not npc else 1].snapshot,proof.previous.snapshot)
                if npc:
                    previous = state.enemy(proof.rider_id).state
                    following = next(row.state for row in updates['enemies'] if row.state.actor_id == proof.rider_id)
                    self.assertEqual(following.injury,previous.injury)
                    self.assertEqual(following.current_resilience.total,previous.current_resilience.total-1)
                else:
                    self.assertNotIn('party',updates)
                after = copy(state)
                for field,value in updates.items():
                    setattr(after,field,value)
                after.history = (*state.history,proof)
                self.assertIsNone(expected_companion_departure(after))

    def test_actual_npc_hazard_killed_receipt_has_no_implicit_knockout_to_death_conversion(self):
        state = view(npc=True)
        actor = 'minion1'
        enemy = state.enemy(actor)
        state.enemies = (replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
            conditions=enemy.state.injury.conditions.with_condition(Condition.ABLAZE)))),)
        request = _hazard_request(state,actor,'prepared:actual-ablaze',2,ABLAZE_HAZARD_RULE_ID)
        rng = ScriptedD10([10]*_expected_initial_roll_parameters(request.avoidance_test)[5])
        test = resolve_test(request.avoidance_test,rng)
        result = resolve_hazard(weapon_hazard_resolution_request(request,test),rng)
        rng.assert_exhausted()
        proof = PcWeaponHazardProof(request,test,result,None,None,NpcDefeatDisposition.KILLED)
        state.enemies = (replace(state.enemies[0],state=replace(state.enemies[0].state,injury=result.state)),)
        state.history = (*state.history,proof)
        departure = expected_companion_departure(state)
        self.assertIs(departure.source_proof,proof)
        self.assertEqual(departure.source_id,request.id+':defeat')
        for disposition in (None,NpcDefeatDisposition.KNOCKED_OUT):
            without = copy(state)
            without.history = (*state.history[:-1],replace(proof,npc_disposition=disposition))
            self.assertIsNone(expected_companion_departure(without))

    def test_confirmed_exit_uses_exact_movement_receipt_and_preserves_living_rider_and_body(self):
        state = view(npc=True)
        actor = 'minion1'
        enemy = state.enemy(actor)
        state.enemies = (replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,
            conditions=enemy.state.injury.conditions.without_condition(Condition.PRONE)
                .with_condition(Condition.BROKEN)))),)
        clock(state,actor)
        origin = state.battlefield.spatial.placement_for(actor).zone_id
        destination = state.battlefield.spatial.graph.adjacent_zone_ids(origin)[0]
        request = FreeMovementRequest('prepared:confirmed-exit',state.round_state,state.battlefield.spatial,
            actor,MovementSpeed.NORMAL,state.enemy(actor).state.injury.conditions,(destination,))
        proof = PcNpcExitProof(request,resolve_free_movement(request))
        state.history = (*state.history,proof)
        # This is the exit consumer's existing confirmed-ID view. It does not
        # claim that the native exit producer supports arbitrary generated NPCs.
        self.assertIsNone(expected_companion_departure(state))
        state.exited_npc_ids = (actor,)
        departure = expected_companion_departure(state)
        self.assertIs(departure.source_proof,proof)
        self.assertEqual(departure.source_id,request.id)
        self.assertFalse(state.enemy(actor).state.injury.defeated)
        self.assertEqual(departure.previous.snapshot,departure.state.snapshot)

    def test_bound_history_geometry_clock_and_cached_types_cannot_be_changed_or_replayed(self):
        state = view()
        pc_critical_death(state)
        proof = expected_companion_departure(state)
        for field,value in (('history_index',True),('source_history_index',True),('source_proof',object()),
                ('state',proof.previous),('battlefield',proof.previous_battlefield),('round_state',proof.source_round)):
            with self.subTest(field=field),self.assertRaises((TypeError,ValueError)):
                replace(proof,**{field:value})
        for field,value in (('source_id','foreign'),('source_history_index',0)):
            with self.subTest(field=field),self.assertRaises(ValueError):
                project_companion_departure(state,replace(proof,**{field:value}))
        erased = copy(state)
        erased.history = state.history[:-1]
        with self.assertRaises(ValueError):
            project_companion_departure(erased,proof)
        updates = project_companion_departure(state,proof)
        following = copy(state)
        for field,value in updates.items():
            setattr(following,field,value)
        following.history = (*state.history,proof)
        self.assertIsNone(expected_companion_departure(following))
        with self.assertRaises(ValueError):
            project_companion_departure(following,proof)
        malformed = deepcopy(proof)
        object.__setattr__(malformed.previous.snapshot.state.injury,'defeated',1)
        with self.assertRaises((TypeError,ValueError)):
            project_companion_departure(state,malformed)


if __name__=='__main__':
    unittest.main()
