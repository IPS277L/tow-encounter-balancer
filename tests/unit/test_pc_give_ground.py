"""Prepared phase queries with real completed K1 Give Ground sources.

Prepared injuries isolate movement permissions. These boundaries are not
claimed as full replay histories; native integration belongs to the PC runner.
"""
from copy import copy,deepcopy
from dataclasses import replace
import unittest

from tests.support.magic_weapon_battles import magic_battle,Threes
from towr.domain.attack_models import ConditionAfterGiveGroundSpec
from towr.domain.condition_models import Condition,StaggerChoice,StaggerRequest
from towr.domain.injury_models import (
    CharacterInjuryState,WoundRecord,WoundEntryId,WoundRestriction,WoundRestrictionEffect,WoundEffectDuration,
)
from towr.domain.pc_give_ground_models import (
    PcGiveGroundProof,PcAfterGiveGroundProof,pc_give_ground_context,pc_attack_decisions,
    expected_pc_give_ground,project_pc_give_ground,pc_give_ground_pending_actor,
)
from towr.domain.pc_melee_models import PcMeleePolicy
from towr.domain.pc_melee_result_models import PcAttackProof,initial_pc_melee_state,build_pc_melee_attack
from towr.domain.pc_mount_models import DEMIGRYPH_FEARSOME_RULE_ID,CombatMount,RiderKind
from towr.domain.pc_battlefield_models import PcAirspaceSpec
from towr.domain.pc_scene_feature_models import PcZoneFeatures
from towr.domain.pc_weapon_intent_models import build_pc_attack_weapon_intent
from towr.domain.resolution_models import GiveGroundRequest,ConditionAfterGiveGroundRequest
from towr.domain.turn_models import (
    ActionSlotGrant,CombatActionDeclaration,CombatActionKind,CombatActionSlotRequest,CombatTurnStartRequest,
)
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.protection_preparation import prepare_protection
from towr.rules.test_resolution import RerollAllFailures
from towr.rules.turn_resolution import start_combat_turn,reserve_combat_action_slot
from towr.rules.spatial_resolution import resolve_give_ground
from towr.domain.spatial_models import SpatialEntityPlacement
from tests.unit.test_k1_spatial_resolution import state as k1_state,request as k1_request


class SufferWound(RerollAllFailures):
    def choose_repeated_stagger(self,*,request,allowed_choices):
        return StaggerChoice.SUFFER_WOUND


def injury_view(state,actor,injury):
    """Prepared typed body observation, without inventing an earlier Attack."""
    view=copy(state)
    if actor in state.source.pc_activation_order:
        object.__setattr__(view,'party',tuple(replace(row,injury=injury)
            if row.actor_id==actor else row for row in state.party))
    else:
        object.__setattr__(view,'enemies',tuple(replace(row,state=replace(row.state,injury=injury))
            if row.state.actor_id==actor else row for row in state.enemies))
    return view


def phase(*,npc_moves=True,after_effect=False):
    source=magic_battle('staff',pc_ws=6 if npc_moves else 1,npc_ws=1 if npc_moves else 6)
    state=initial_pc_melee_state(source)
    actor,target=('pc',source.enemy_activation_order[0]) if npc_moves else (source.enemy_activation_order[0],'pc')
    body=state.enemy(target).state.injury if npc_moves else state.participant(target).injury
    state=injury_view(state,target,replace(body,conditions=body.conditions.with_condition(Condition.STAGGERED)))
    clock=state.round_state
    if not npc_moves:clock=replace(clock,completed_turn_entity_ids=source.pc_activation_order)
    clock=start_combat_turn(CombatTurnStartRequest('phase:start',clock,actor)).state
    clock=reserve_combat_action_slot(CombatActionSlotRequest('phase:slot',clock,actor,
        CombatActionDeclaration(CombatActionKind.ATTACK),ActionSlotGrant.STANDARD)).state
    object.__setattr__(state,'round_state',clock)
    intent=build_pc_attack_weapon_intent(state)
    request,protection=build_pc_melee_attack(state,weapon_intent=intent)
    if after_effect:
        # A real K1 Fearsome effect tests its ordered continuation owner. The
        # prepared phase does not assert a canonical complete Demigryph scene.
        attack=replace(request.kernel_request.attack,secondary_effects=(
            ConditionAfterGiveGroundSpec(Condition.BROKEN,DEMIGRYPH_FEARSOME_RULE_ID),))
        request=replace(request,kernel_request=replace(request.kernel_request,attack=attack))
    actual=execute_attack_action(request,Threes(),decisions=pc_attack_decisions(state,request,SufferWound()))
    proof=PcAttackProof(request,prepare_protection(protection),actual,None,weapon_intent=intent)
    following=injury_view(state,target,actual.resolution.target_state)
    object.__setattr__(following,'round_state',actual.state)
    object.__setattr__(following,'history',(proof,))
    object.__setattr__(following,'pending',actual.resolution.follow_ups)
    object.__setattr__(following,'pending_actor_id',target)
    return following


def project_prepared(state,proof):
    updates=project_pc_give_ground(state,proof)
    following=copy(state)
    for name,value in updates.items():object.__setattr__(following,name,value)
    object.__setattr__(following,'history',(*state.history,proof))
    return following


class PcGiveGroundTests(unittest.TestCase):
    def test_actual_open_route_is_adjacent_away_and_stationary_does_not_invent_one(self):
        source=magic_battle('staff')
        state=initial_pc_melee_state(source)
        actor='pc';attacker=source.enemy_activation_order[0]
        context=pc_give_ground_context(state,actor,attacker)
        self.assertTrue(context.can_leave)
        self.assertTrue(state.battlefield.spatial.graph.are_adjacent(
            state.battlefield.spatial.placement_for(actor).zone_id,context.destination_zone_id))
        source=replace(source,battlefield=None,
            facts=replace(source.facts,all_opponents_close=True,can_leave_zone=False))
        self.assertFalse(pc_give_ground_context(initial_pc_melee_state(source),actor,attacker).can_leave)

    def test_prone_and_defenceless_do_not_receive_a_movement_route(self):
        source=magic_battle('staff')
        state=initial_pc_melee_state(source)
        for condition in (Condition.PRONE,Condition.DEFENCELESS):
            body=replace(state.participant('pc').injury,
                conditions=state.participant('pc').injury.conditions.with_condition(condition))
            view=injury_view(state,'pc',body)
            with self.subTest(condition=condition):
                self.assertFalse(pc_give_ground_context(view,'pc',source.enemy_activation_order[0]).can_leave)

    def test_pg119_terrain_at_departure_or_all_destinations_blocks_the_route(self):
        source=magic_battle('staff')
        for indices in ((0,),(-1,1)):
            specified=replace(source,battlefield=replace(source.battlefield,zone_features=tuple(
                PcZoneFeatures(index,difficult_terrain=True) for index in indices)))
            state=initial_pc_melee_state(specified)
            with self.subTest(indices=indices):
                self.assertFalse(pc_give_ground_context(state,'pc',source.enemy_activation_order[0]).can_leave)

    def test_personal_leg_spasm_terrain_survives_after_prone_was_removed(self):
        source=magic_battle('staff')
        state=initial_pc_melee_state(source)
        body=CharacterInjuryState((WoundRecord(1,WoundEntryId.LEG_SPASM,9,(9,),effect_resolved=True),),
            active_wound_effects=(WoundRestrictionEffect(1,WoundRestriction.MOVEMENT_IS_DIFFICULT_TERRAIN,
                WoundEffectDuration.UNTIL_TREATED),))
        view=injury_view(state,'pc',body)
        self.assertFalse(pc_give_ground_context(view,'pc',source.enemy_activation_order[0]).can_leave)

    def test_pegasus_name_alone_does_not_allow_takeoff_beside_a_close_enemy(self):
        source=magic_battle('staff')
        source=replace(source,party=(replace(source.party[0],mount=CombatMount.PEGASUS,rider_kind=RiderKind.HUMAN),),
            facts=replace(source.facts,unmounted=False),
            battlefield=replace(source.battlefield,airspace=PcAirspaceSpec(),zone_features=(
                PcZoneFeatures(0,difficult_terrain=True),)))
        state=initial_pc_melee_state(source)
        self.assertFalse(pc_give_ground_context(state,'pc',source.enemy_activation_order[0]).can_leave)

    def test_both_roles_project_real_give_ground_without_action_or_free_move_cost(self):
        for npc_moves in (False,True):
            state=phase(npc_moves=npc_moves)
            expected=expected_pc_give_ground(state)
            self.assertIs(type(expected),PcGiveGroundProof)
            self.assertEqual(pc_give_ground_pending_actor(state),expected.actor_id)
            before=state.battlefield.spatial
            after=project_prepared(state,expected)
            self.assertEqual(after.round_state,state.round_state)
            self.assertEqual(after.battlefield.spatial.free_move_used_entity_ids,before.free_move_used_entity_ids)
            self.assertEqual(after.battlefield.spatial.gave_ground_entity_ids,(expected.actor_id,))
            self.assertFalse(any(expected.actor_id in pair for pair in after.battlefield.close_pairs))
            self.assertEqual(after.participant('pc').weapon_inventory,state.participant('pc').weapon_inventory)
            self.assertFalse(after.pending)
            self.assertIsNone(after.pending_actor_id)
            with self.subTest(npc_moves=npc_moves),self.assertRaises(ValueError):
                project_pc_give_ground(after,expected)

    def test_once_per_round_bank_prevents_another_reactive_move(self):
        state=phase(npc_moves=True)
        proof=expected_pc_give_ground(state)
        after=project_prepared(state,proof)
        context=pc_give_ground_context(after,proof.actor_id,proof.attack.request.actor_id)
        self.assertTrue(context.given_this_round)
        self.assertFalse(context.can_leave)

    def test_fearsome_broken_is_a_separate_follow_up_after_actual_movement(self):
        state=phase(npc_moves=False,after_effect=True)
        proof=expected_pc_give_ground(state)
        self.assertIs(type(state.pending[0]),GiveGroundRequest)
        self.assertIs(type(state.pending[1]),ConditionAfterGiveGroundRequest)
        after=project_prepared(state,proof)
        self.assertFalse(after.participant('pc').injury.conditions.has(Condition.BROKEN))
        following=expected_pc_give_ground(after)
        self.assertIs(type(following),PcAfterGiveGroundProof)
        self.assertEqual(pc_give_ground_pending_actor(after),'pc')
        finished=project_prepared(after,following)
        self.assertTrue(finished.participant('pc').injury.conditions.has(Condition.BROKEN))
        self.assertEqual(finished.round_state,state.round_state)
        self.assertFalse(finished.pending)

    def test_a_missing_attack_or_changed_source_cannot_authorize_movement(self):
        state=phase(npc_moves=True)
        missing=copy(state);object.__setattr__(missing,'history',())
        with self.assertRaises(ValueError):expected_pc_give_ground(missing)
        changed=copy(state);object.__setattr__(changed,'pending',(GiveGroundRequest('foreign'),))
        with self.assertRaises(ValueError):pc_give_ground_pending_actor(changed)
        proof=expected_pc_give_ground(state)
        with self.assertRaises(ValueError):
            project_pc_give_ground(state,replace(proof,attack_index=99))

    def test_automatic_reaction_prefers_legal_retreat_then_prone_while_manual_keeps_its_choice(self):
        state=phase(npc_moves=False)
        attack=state.history[0].request
        decision=pc_attack_decisions(state,attack,SufferWound())
        repeated=StaggerRequest(attack.kernel_request.id+':stagger',state.participant('pc').injury.conditions,
            True,False)
        choices=(StaggerChoice.GIVE_GROUND,StaggerChoice.FALL_PRONE,StaggerChoice.SUFFER_WOUND)
        self.assertIs(decision.choose_repeated_stagger(request=repeated,allowed_choices=choices),StaggerChoice.GIVE_GROUND)
        self.assertIs(decision.choose_repeated_stagger(request=repeated,allowed_choices=choices[1:]),StaggerChoice.FALL_PRONE)
        self.assertIs(decision.choose_repeated_stagger(request=replace(repeated,id='other-source'),
            allowed_choices=choices),StaggerChoice.SUFFER_WOUND)
        source=replace(state.source,party=(replace(state.source.party[0],policy=PcMeleePolicy.ATTACK_OR_RECOVER_SELF),),
            battlefield=None,facts=replace(state.source.facts,all_opponents_close=True,can_leave_zone=False))
        manual=initial_pc_melee_state(source)
        self.assertIs(pc_attack_decisions(manual,attack,SufferWound()).choose_repeated_stagger(
            request=repeated,allowed_choices=choices),StaggerChoice.SUFFER_WOUND)
        self.assertEqual(decision.choose_glorious_rerolls(request=None,initial_values=(1,10),eligible_indices=(1,)),(1,))

    def test_equal_cached_bool_aliases_are_rejected(self):
        state=phase(npc_moves=True)
        proof=deepcopy(expected_pc_give_ground(state))
        object.__setattr__(proof.result,'entered_enemy_zone',0)
        self.assertEqual(proof,expected_pc_give_ground(state))
        with self.assertRaises(TypeError):project_pc_give_ground(state,proof)

    def test_an_empty_enemy_list_cannot_bypass_the_battle_owners_complete_source(self):
        state=phase(npc_moves=True)
        proof=expected_pc_give_ground(state)
        request=replace(proof.request,enemy_entity_ids=())
        forged=replace(proof,request=request,result=resolve_give_ground(request))
        with self.assertRaises(ValueError):project_pc_give_ground(state,forged)


class GiveGroundEnemySourceTests(unittest.TestCase):
    def test_a_dropped_item_is_not_an_enemy_and_remains_in_the_actual_spatial_state(self):
        spatial=k1_state(SpatialEntityPlacement('mover','heroes','zone:a'),
            SpatialEntityPlacement('attacker','enemies','zone:a'),
            SpatialEntityPlacement('dropped-sword','objects','zone:b'))
        request=replace(k1_request(spatial),enemy_entity_ids=('attacker',))
        result=resolve_give_ground(request)
        self.assertFalse(result.entered_enemy_zone)
        self.assertFalse(result.conditions.has(Condition.BROKEN))
        self.assertEqual(result.state.placement_for('dropped-sword'),spatial.placement_for('dropped-sword'))
        self.assertEqual(result.source_request.enemy_entity_ids,('attacker',))

    def test_a_real_enemy_in_the_destination_still_causes_broken(self):
        spatial=k1_state(SpatialEntityPlacement('mover','heroes','zone:a'),
            SpatialEntityPlacement('attacker','enemies','zone:a'),
            SpatialEntityPlacement('other','enemies','zone:b'),
            SpatialEntityPlacement('dropped-shield','objects','zone:b'))
        result=resolve_give_ground(replace(k1_request(spatial),enemy_entity_ids=('attacker','other')))
        self.assertTrue(result.entered_enemy_zone)
        self.assertTrue(result.conditions.has(Condition.BROKEN))

    def test_enemy_facts_require_exact_unique_existing_opposition_ids(self):
        request=k1_request(k1_state())
        for ids in (['attacker'],('attacker','attacker'),('unknown',),('mover',),(False,)):
            with self.subTest(ids=ids),self.assertRaises((TypeError,ValueError,KeyError)):
                replace(request,enemy_entity_ids=ids)


if __name__=='__main__':
    unittest.main()
