"""Prepared retained-mount turns use the real Broken/terrain movement owners.

Source retention and next-round clock admission use existing typed receipts.
Subsequent injury/usage observations are prepared boundaries, not full battles.
The local Talent cap patch admits only these owner fixtures, not public input.
"""
from copy import copy, deepcopy
from dataclasses import replace
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch

from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit import test_pc_mount_retention as retention_fixtures
from towr.domain import talent_actor_models
from towr.domain.condition_models import Condition, ConditionApplicationRequest, EffectClassification
from towr.domain.movement_models import MovementSpeed
from towr.domain.pc_actor_models import pc_actor_injury, pc_actor_npc_update
from towr.domain.pc_battlefield_manoeuvre_models import pc_battlefield_actor_speed
from towr.domain.pc_broken_battlefield_models import (
    PcBrokenBlockedProof, PcBrokenBlockReason, PcBrokenMoveProof, PcBrokenRunProof,
    expected_pc_broken_battlefield_step, pc_broken_has_enemy_in_zone,
    pc_broken_run_selected, pc_broken_standard_recover_selected,
    pc_broken_turn_blocked, project_pc_broken_battlefield,
)
from towr.domain.pc_melee_result_models import PcMeleeState
from towr.domain.pc_mount_models import CombatMount
from towr.domain.pc_scene_feature_models import PcZoneFeatures
from towr.domain.pc_terrain_models import (
    PcTerrainTraversalProof, expected_pc_terrain_traversal, project_pc_terrain,
)
from towr.domain.talent_catalog import TalentId
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    ManoeuvreKind,
)
from towr.domain.undead_minion_models import UndeadMinionSource, undead_minion_effect_immunities
from towr.rules.condition_effect_resolution import resolve_condition_application
from towr.rules.difficult_terrain_resolution import resolve_difficult_terrain_traversal
from towr.rules.turn_resolution import reserve_combat_action_slot


class Preparation(SimpleNamespace):
    participant = PcMeleeState.participant
    enemy = PcMeleeState.enemy
    live_party = PcMeleeState.live_party
    live_enemies = PcMeleeState.live_enemies
    exited_npc_ids = PcMeleeState.exited_npc_ids


def as_preparation(state):
    return Preparation(**{name: getattr(state, name) for name in state.__dataclass_fields__})


def apply_prepared(state, updates, proof):
    after = copy(state)
    for name, value in updates.items():
        setattr(after, name, value)
    after.history = (*state.history, proof)
    return after


class CompanionBrokenMovementTests(TestCase):
    def setUp(self):
        for name in ('PC_EXECUTABLE_TALENTS', 'NPC_EXECUTABLE_TALENTS'):
            self.enterContext(patch.object(talent_actor_models, name,
                getattr(talent_actor_models, name) | {TalentId.BACK_IN_THE_SADDLE}))

    def prepared(self, *, npc=False, kind=CombatMount.HORSE, broken=True, terrain=False):
        fixture = retention_fixtures.MountRetentionTests()
        if terrain:
            base_prepared = fixture.prepared
            def scene_prepared(**kwargs):
                state = base_prepared(**kwargs)
                return replace(state, source=replace(state.source,
                    battlefield=replace(state.source.battlefield,
                        zone_features=(PcZoneFeatures(0, difficult_terrain=True),))))
            fixture.prepared = scene_prepared
        state, _ = fixture.retained(npc=npc, kind=kind)
        state = fixture.next_round_companion_turn(state, npc=npc)
        state = as_preparation(state)
        actor = 'minion1:mount' if npc else 'pc1:mount'
        if broken:
            body = pc_actor_injury(state, actor)
            updates = pc_actor_npc_update(state, actor,
                injury=replace(body, conditions=body.conditions.with_condition(Condition.BROKEN)))
            state.companions = updates['companions']
        return state, actor

    def test_healthy_companion_turn_has_no_broken_work_and_is_not_mistaken_for_pc(self):
        for npc in (False, True):
            state, actor = self.prepared(npc=npc, broken=False)
            with self.subTest(npc=npc):
                self.assertIsNone(expected_pc_broken_battlefield_step(state))
                self.assertFalse(pc_broken_turn_blocked(state))
                self.assertFalse(pc_broken_run_selected(state))
                self.assertFalse(pc_broken_standard_recover_selected(state))
                self.assertIs(pc_battlefield_actor_speed(state, actor), MovementSpeed.FAST)
                self.assertFalse(hasattr(pc_actor_injury(state, actor), 'fate'))

    def test_both_sides_really_leave_unsafe_zone_without_exit_or_condition_healing(self):
        for npc in (False, True):
            state, actor = self.prepared(npc=npc)
            before = deepcopy(state)
            proof = expected_pc_broken_battlefield_step(state)
            with self.subTest(npc=npc):
                self.assertIs(type(proof), PcBrokenMoveProof)
                self.assertIs(proof.request.speed, MovementSpeed.FAST)
                self.assertTrue(pc_broken_has_enemy_in_zone(state, actor))
                self.assertEqual(proof.actor_id, actor)
                self.assertEqual(proof.request.actor_id, actor)
                self.assertEqual(len(proof.request.traversed_zone_ids), 1)
                updates = project_pc_broken_battlefield(state, proof)
                self.assertEqual(tuple(updates), ('battlefield',))
                after = apply_prepared(state, updates, proof)
                self.assertFalse(pc_broken_has_enemy_in_zone(after, actor))
                self.assertTrue(pc_broken_standard_recover_selected(after))
                self.assertTrue(pc_actor_injury(after, actor).conditions.has(Condition.BROKEN))
                self.assertEqual(after.companions, state.companions)
                self.assertEqual(after.party, state.party)
                self.assertEqual(after.enemies, state.enemies)
                self.assertEqual(after.exited_npc_ids, ())
                self.assertEqual(after.round_state, state.round_state)
                self.assertIn(actor, after.battlefield.spatial.free_move_used_entity_ids)
                self.assertEqual(state, before)
                with self.assertRaises(ValueError):
                    project_pc_broken_battlefield(after, proof)

    def test_prone_defenceless_and_spent_free_move_burden_keep_real_blocked_turns(self):
        for condition, reason, used in ((Condition.PRONE, PcBrokenBlockReason.PRONE, False),
                (Condition.DEFENCELESS, PcBrokenBlockReason.DEFENCELESS, False),
                (Condition.BURDENED, PcBrokenBlockReason.BURDENED, True)):
            state, actor = self.prepared()
            body = pc_actor_injury(state, actor)
            state.companions = pc_actor_npc_update(state, actor,
                injury=replace(body, conditions=body.conditions.with_condition(condition)))['companions']
            if used:
                state.battlefield = replace(state.battlefield, spatial=replace(state.battlefield.spatial,
                    free_move_used_entity_ids=(actor,)))
            proof = expected_pc_broken_battlefield_step(state)
            with self.subTest(condition=condition):
                self.assertIs(type(proof), PcBrokenBlockedProof)
                self.assertIs(proof.reason, reason)
                self.assertEqual(project_pc_broken_battlefield(state, proof), {})
                after = apply_prepared(state, {}, proof)
                self.assertTrue(pc_broken_turn_blocked(after))
                self.assertFalse(pc_broken_standard_recover_selected(after))
                self.assertIsNone(expected_pc_broken_battlefield_step(after))
                self.assertFalse(after.round_state.active_turn.action_slots)

    def test_companion_run_spends_only_its_reserved_action_when_free_move_was_used(self):
        for npc in (False, True):
            state, actor = self.prepared(npc=npc)
            state.battlefield = replace(state.battlefield, spatial=replace(state.battlefield.spatial,
                free_move_used_entity_ids=(actor,)))
            with self.subTest(npc=npc):
                self.assertTrue(pc_broken_run_selected(state))
                self.assertIsNone(expected_pc_broken_battlefield_step(state))
                state.round_state = reserve_combat_action_slot(CombatActionSlotRequest('prepared:run',
                    state.round_state, actor, CombatActionDeclaration(CombatActionKind.MANOEUVRE,
                        manoeuvre=ManoeuvreKind.RUN), ActionSlotGrant.STANDARD)).state
                proof = expected_pc_broken_battlefield_step(state)
                self.assertIs(type(proof), PcBrokenRunProof)
                updates = project_pc_broken_battlefield(state, proof)
                self.assertEqual(set(updates), {'round_state', 'battlefield'})
                self.assertTrue(updates['round_state'].active_turn.action_slots[0].executed)
                self.assertEqual(len(updates['round_state'].active_turn.action_slots), 1)
                self.assertEqual(updates['round_state'].active_turn.actor_id, actor)
                self.assertIs(proof.request.speed, MovementSpeed.FAST)
                self.assertEqual(updates['battlefield'].spatial.free_move_used_entity_ids, (actor,))

    def test_companion_crossing_keeps_deferred_terrain_own_athletics_and_no_rider_staff_or_fate(self):
        for npc in (False, True):
            for success in (False, True):
                state, actor = self.prepared(npc=npc, terrain=True)
                movement = expected_pc_broken_battlefield_step(state)
                self.assertTrue(movement.request.crosses_difficult_terrain)
                self.assertTrue(movement.request.terrain_resolution_deferred)
                crossed = apply_prepared(state, project_pc_broken_battlefield(state, movement), movement)
                traversal = expected_pc_terrain_traversal(crossed)
                with self.subTest(npc=npc, success=success):
                    self.assertIsNotNone(traversal)
                    self.assertEqual(traversal.movement, movement)
                    self.assertEqual(traversal.traversal.completed_crossing, movement.state.spatial)
                    self.assertIsNone(traversal.staff_use)
                    self.assertEqual(traversal.athletics_test.profile.base_dice, 4)
                    self.assertEqual(traversal.athletics_test.profile.threshold, 4)
                    self.assertEqual(traversal.athletics_test.dice_modifiers, ())
                    rng = ScriptedD10(([1] if success else [10])*4)
                    result = resolve_difficult_terrain_traversal(traversal.traversal, rng)
                    rng.assert_exhausted()
                    proof = PcTerrainTraversalProof(traversal, result, None)
                    updates = project_pc_terrain(crossed, proof)
                    self.assertEqual(set(updates), {'companions', 'battlefield'})
                    after = apply_prepared(crossed, updates, proof)
                    own = pc_actor_injury(after, actor)
                    self.assertEqual(own.wounds, 0)
                    self.assertTrue(own.conditions.has(Condition.BROKEN))
                    self.assertEqual(own.conditions.has(Condition.PRONE), not success)
                    self.assertIn(actor, after.battlefield.spatial.difficult_terrain_tested_entity_ids)
                    self.assertEqual(after.party, state.party)
                    self.assertEqual(after.enemies, state.enemies)
                    self.assertEqual(after.round_state, state.round_state)
                    self.assertIsNone(expected_pc_terrain_traversal(after))
                    with self.assertRaises(ValueError):
                        project_pc_terrain(crossed, replace(proof, fate_decline=True))

    def test_actual_actor_source_enemy_set_safety_and_broken_marker_cannot_be_forged(self):
        state, actor = self.prepared()
        proof = expected_pc_broken_battlefield_step(state)
        for changes in (dict(actor_id='foreign'), dict(enemy_ids=()),
                dict(safe_zone_id=state.battlefield.spatial.placement_for(actor).zone_id)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                project_pc_broken_battlefield(state, replace(proof, **changes))
        with self.assertRaises(ValueError):
            pc_battlefield_actor_speed(state, 'foreign')
        state.mounts = tuple(replace(row, mount=CombatMount.DEMIGRYPH) if row.actor_id == 'pc1' else row
            for row in state.mounts)
        with self.assertRaises(ValueError):
            pc_battlefield_actor_speed(state, actor)

    def test_skeletal_psychological_immunity_prevents_broken_without_erasing_other_conditions(self):
        state, actor = self.prepared(kind=CombatMount.SKELETAL_STEED, broken=False)
        body = pc_actor_injury(state, actor)
        application = resolve_condition_application(ConditionApplicationRequest('actual:fear',
            body.conditions, Condition.BROKEN, 'actual:psychological-source', EffectClassification.PSYCHOLOGICAL,
            undead_minion_effect_immunities(UndeadMinionSource(actor), actor)))
        self.assertTrue(application.blocked)
        state.companions = pc_actor_npc_update(state, actor,
            injury=replace(body, conditions=application.state))['companions']
        self.assertFalse(pc_actor_injury(state, actor).conditions.has(Condition.BROKEN))
        self.assertIsNone(expected_pc_broken_battlefield_step(state))


if __name__ == '__main__':
    main()
