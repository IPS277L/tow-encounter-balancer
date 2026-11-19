"""Prepared Broken turns use real movement/Run without exit or false recovery.

Prepared injury/clock boundaries isolate PG122. Whole battle replay coverage
belongs to the native Give Ground/Fearsome integration path.
"""
from dataclasses import replace
import json
from random import Random
import unittest

from tests.support.magic_weapon_fixtures import request
from towr.adapters.dynamic_encounter_json import parse_dynamic_encounter_request
from towr.domain.condition_models import Condition
from towr.domain.pc_battlefield_models import with_actor_placement
from towr.domain.pc_broken_battlefield_models import (
    PcBrokenMoveProof,PcBrokenRunProof,PcBrokenBlockedProof,PcBrokenBlockReason,
    expected_pc_broken_battlefield_step,project_pc_broken_battlefield,
    pc_broken_has_enemy_in_zone,pc_broken_standard_recover_selected,
    pc_broken_run_selected,pc_broken_turn_blocked,
)
from towr.domain.pc_melee_result_models import initial_pc_melee_state
from towr.domain.spatial_models import SpatialEntityPlacement
from towr.domain.turn_models import (
    CombatTurnStartRequest,CombatActionSlotRequest,CombatActionDeclaration,
    CombatActionKind,ManoeuvreKind,ActionSlotGrant,
)
from towr.rules.turn_resolution import start_combat_turn,reserve_combat_action_slot


def prepared(*,npc=False,prone=False,distance='short',terrain=False,mount=None):
    raw=request('sword');raw['npc_count']=dict(minimum=1,maximum=1)
    raw['scene']['range']=distance
    raw['party'][0]['resources']['fate']=0
    if terrain:raw['scene']['zone_features']=[dict(index=0,difficult_terrain=True)]
    if mount is not None:raw['party'][0]['mount']=mount
    raw['search_space'].update(weapon=['sword'],weapon_count=[1],mount=[None])
    command=parse_dynamic_encounter_request(json.dumps(raw))
    source=command.request.scenario((command.request.space.sample(Random(2)),),'broken')
    current=initial_pc_melee_state(source)
    actor=source.enemy_activation_order[0] if npc else source.pc_activation_order[0]
    clock=current.round_state
    if npc:clock=replace(clock,completed_turn_entity_ids=source.pc_activation_order)
    clock=start_combat_turn(CombatTurnStartRequest('broken:start',clock,actor)).state
    if npc:
        enemy=current.enemy(actor);conditions=enemy.state.injury.conditions.with_condition(Condition.BROKEN)
        if prone:conditions=conditions.with_condition(Condition.PRONE)
        enemy=replace(enemy,state=replace(enemy.state,injury=replace(enemy.state.injury,conditions=conditions)))
        current=replace(current,enemies=(enemy,),round_state=clock)
    else:
        member=current.participant(actor);conditions=member.injury.conditions.with_condition(Condition.BROKEN)
        if prone:conditions=conditions.with_condition(Condition.PRONE)
        member=replace(member,injury=replace(member.injury,conditions=conditions))
        current=replace(current,party=(member,),round_state=clock)
    return current,actor


class QueryContext:
    """A pure query over prepared typed positions, not a native history."""
    def __init__(self,base,**changes):self.base=base;self.__dict__.update(changes)
    def __getattr__(self,key):return getattr(self.base,key)


class PcBrokenBattlefieldTests(unittest.TestCase):
    def test_both_roles_move_to_real_safety_and_keep_broken_and_all_resources(self):
        for npc in (False,True):
            with self.subTest(npc=npc):
                current,actor=prepared(npc=npc)
                self.assertTrue(pc_broken_has_enemy_in_zone(current,actor))
                proof=expected_pc_broken_battlefield_step(current)
                self.assertIs(type(proof),PcBrokenMoveProof)
                updates=project_pc_broken_battlefield(current,proof)
                after=replace(current,**updates,history=(*current.history,proof))
                self.assertFalse(pc_broken_has_enemy_in_zone(after,actor))
                self.assertEqual(after.round_state,current.round_state)
                self.assertEqual(after.exited_npc_ids,())
                self.assertEqual(after.party,current.party)
                self.assertEqual(after.enemies,current.enemies)
                self.assertTrue(pc_broken_standard_recover_selected(after))
                self.assertIsNone(expected_pc_broken_battlefield_step(after))
                self.assertIn(actor,after.battlefield.spatial.free_move_used_entity_ids)
                with self.assertRaises(ValueError):project_pc_broken_battlefield(after,proof)

    def test_unsafe_prone_is_a_confirmed_blocked_turn_without_fake_action(self):
        current,actor=prepared(prone=True)
        proof=expected_pc_broken_battlefield_step(current)
        self.assertIs(type(proof),PcBrokenBlockedProof)
        self.assertIs(proof.reason,PcBrokenBlockReason.PRONE)
        self.assertEqual(project_pc_broken_battlefield(current,proof),{})
        after=replace(current,history=(*current.history,proof))
        self.assertTrue(pc_broken_turn_blocked(after))
        self.assertFalse(pc_broken_standard_recover_selected(after))
        self.assertEqual(after.round_state.active_turn.action_slots,())
        self.assertEqual(after.battlefield,current.battlefield)
        self.assertIsNone(expected_pc_broken_battlefield_step(after))
        with self.assertRaises(ValueError):project_pc_broken_battlefield(after,proof)

    def test_object_markers_are_not_enemies_in_a_genuinely_safe_zone(self):
        current,actor=prepared(distance='medium')
        spatial=current.battlefield.spatial
        marker=SpatialEntityPlacement('dropped:shield','objects',spatial.placement_for(actor).zone_id)
        spatial=replace(spatial,placements=(*spatial.placements,marker))
        query=QueryContext(current,battlefield=replace(current.battlefield,spatial=spatial))
        self.assertFalse(pc_broken_has_enemy_in_zone(query,actor))
        self.assertTrue(pc_broken_standard_recover_selected(query))
        self.assertIsNone(expected_pc_broken_battlefield_step(query))

    def test_actual_run_spends_one_reserved_action_when_free_move_is_already_used(self):
        current,actor=prepared()
        # Prepared physical usage: no remaining free movement, still unsafe.
        spatial=replace(current.battlefield.spatial,free_move_used_entity_ids=(actor,))
        query=QueryContext(current,battlefield=replace(current.battlefield,spatial=spatial))
        self.assertTrue(pc_broken_run_selected(query))
        self.assertIsNone(expected_pc_broken_battlefield_step(query))
        clock=reserve_combat_action_slot(CombatActionSlotRequest('broken:run',query.round_state,actor,
            CombatActionDeclaration(CombatActionKind.MANOEUVRE,manoeuvre=ManoeuvreKind.RUN),
            ActionSlotGrant.STANDARD)).state
        query=QueryContext(current,battlefield=query.battlefield,round_state=clock)
        proof=expected_pc_broken_battlefield_step(query)
        self.assertIs(type(proof),PcBrokenRunProof)
        updates=project_pc_broken_battlefield(query,proof)
        self.assertTrue(updates['round_state'].active_turn.action_slots[-1].executed)
        self.assertEqual(updates['battlefield'].spatial.free_move_used_entity_ids,(actor,))
        self.assertEqual(updates['battlefield'].spatial.placement_for(actor).zone_id,proof.safe_zone_id)

    def test_forged_actor_clock_enemy_set_safety_and_result_are_rejected(self):
        current,actor=prepared();proof=expected_pc_broken_battlefield_step(current)
        for changes in (dict(actor_id='missing'),dict(enemy_ids=('dropped:shield',)),
                dict(safe_zone_id=current.battlefield.spatial.placement_for(actor).zone_id)):
            with self.subTest(changes=changes),self.assertRaises((ValueError,TypeError)):
                project_pc_broken_battlefield(current,replace(proof,**changes))
        current,actor=prepared(prone=True);blocked=expected_pc_broken_battlefield_step(current)
        with self.assertRaises(ValueError):project_pc_broken_battlefield(current,
            replace(blocked,reason=PcBrokenBlockReason.NO_LEGAL_ROUTE))

    def test_broken_crossing_retains_real_terrain_and_actual_fast_mount(self):
        from towr.domain.movement_models import MovementSpeed
        from towr.domain.pc_terrain_models import expected_pc_terrain_traversal
        current,actor=prepared(terrain=True,mount='horse')
        proof=expected_pc_broken_battlefield_step(current)
        self.assertIs(proof.request.speed,MovementSpeed.FAST)
        self.assertIs(proof.request.crosses_difficult_terrain,True)
        self.assertIs(proof.request.terrain_resolution_deferred,True)
        after=replace(current,**project_pc_broken_battlefield(current,proof),history=(*current.history,proof))
        terrain=expected_pc_terrain_traversal(after)
        self.assertIsNotNone(terrain)
        self.assertEqual(terrain.movement,proof)
        self.assertEqual(terrain.traversal.completed_crossing,proof.state.spatial)
        self.assertTrue(after.participant(actor).injury.conditions.has(Condition.BROKEN))

