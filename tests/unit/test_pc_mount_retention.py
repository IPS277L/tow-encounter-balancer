"""Prepared injury prefixes test retention, not full native Talent admission.

The Talent execution cap stays closed until the complete companion consumer
is connected. The local admission patch admits this fixture only.
"""
from dataclasses import replace
from unittest import TestCase, main
from unittest.mock import patch

from tests.support.talent_sources import free_talent
from tests.unit.test_pc_mount_companion_owner import source
from towr.domain.condition_models import Condition
from towr.domain.pc_actor_models import pc_active_actor_ids, pc_companion_turn_eligible
from towr.domain.pc_battlefield_models import PcAirspaceSpec, battlefield_is_midair, battlefield_range
from towr.domain.pc_battlefield_movement_models import pc_battlefield_allows_outnumbering
from towr.domain.pc_melee_result_models import initial_pc_melee_state, PcMeleeStep
from towr.domain.pc_mount_models import CombatMount, expected_pc_dismount
from towr.domain.pc_mount_retention_models import expected_pc_mount_retention
from towr.domain.ranged_weapon_profiles import RangedWeaponRange as R
from towr.domain.talent_catalog import TalentId
from towr.domain import talent_actor_models


class MountRetentionTests(TestCase):
    def setUp(self):
        # Explicit prepared owner foundation, not public/native feature admission.
        for name in ('PC_EXECUTABLE_TALENTS', 'NPC_EXECUTABLE_TALENTS'):
            self.enterContext(patch.object(talent_actor_models, name,
                getattr(talent_actor_models, name) | {TalentId.BACK_IN_THE_SADDLE}))

    def prepared(self, kind=CombatMount.HORSE, *, npc=False, combatant=False, distance=R.CLOSE):
        battle = replace(source(kind), max_rounds=3)
        talent = free_talent(TalentId.BACK_IN_THE_SADDLE)
        if npc:
            original = battle.enemies[0].definition.generated_components
            enemy = replace(original, talents=(talent,)).participant('minion1')
            battle = replace(battle, enemies=(enemy,))
        else:
            battle = replace(battle, party=(replace(battle.party[0], talents=(talent,)),))
        battle = replace(battle, facts=replace(battle.facts, all_opponents_close=distance is R.CLOSE),
            battlefield=replace(battle.battlefield,
            dismounted_mounts_are_combatants=combatant, initial_range=distance))
        state = initial_pc_melee_state(battle)
        if npc:
            enemy = state.enemies[0]
            enemy = replace(enemy, state=replace(enemy.state, injury=replace(enemy.state.injury,
                conditions=enemy.state.injury.conditions.with_condition(Condition.PRONE))))
            return replace(state, enemies=(enemy,))
        member = state.party[0]
        return replace(state, party=(replace(member, injury=replace(member.injury,
            conditions=member.injury.conditions.with_condition(Condition.PRONE))),))

    def retained(self, **kwargs):
        state = self.prepared(**kwargs)
        state = PcMeleeStep(state, expected_pc_dismount(state)).state
        proof = expected_pc_mount_retention(state)
        return PcMeleeStep(state, proof).state, proof

    def test_pc_retention_is_real_target_but_has_no_same_round_turn_or_fate(self):
        state, proof = self.retained()
        self.assertEqual(pc_active_actor_ids(state), ('pc1', 'pc1:mount', 'minion1'))
        self.assertIs(battlefield_range(state.battlefield, 'pc1', 'pc1:mount'), R.CLOSE)
        self.assertFalse(pc_companion_turn_eligible(state, 'pc1:mount'))
        self.assertNotIn('pc1:mount', tuple(p.entity_id for p in state.round_state.participants))
        self.assertEqual(proof.previous.snapshot, proof.state.snapshot)
        self.assertEqual(state.party[0].fate, initial_pc_melee_state(state.source).party[0].fate)
        self.assertIsNone(expected_pc_mount_retention(state))
        with self.assertRaises(ValueError): PcMeleeStep(state, proof)

    def test_opposition_retains_own_profile_and_side_without_entering_pc_roster(self):
        state, proof = self.retained(npc=True)
        self.assertEqual(pc_active_actor_ids(state), ('pc1', 'minion1', 'minion1:mount'))
        self.assertEqual(tuple(member.actor_id for member in state.party), ('pc1',))
        self.assertEqual(tuple(member.state.actor_id for member in state.enemies), ('minion1',))
        self.assertEqual(proof.state.snapshot.state.side, state.enemies[0].state.side)

    def test_noncombatant_is_target_but_outnumbering_requires_explicit_gm_fact(self):
        state, _ = self.retained()
        self.assertFalse(pc_battlefield_allows_outnumbering(state, 'pc1'))
        state, _ = self.retained(combatant=True)
        self.assertTrue(pc_battlefield_allows_outnumbering(state, 'pc1'))

    def test_an_actor_without_the_talent_cannot_retain_a_departed_mount(self):
        state = initial_pc_melee_state(source())
        member = state.party[0]
        state = replace(state, party=(replace(member, injury=replace(member.injury,
            conditions=member.injury.conditions.with_condition(Condition.PRONE))),))
        state = PcMeleeStep(state, expected_pc_dismount(state)).state
        self.assertIsNone(expected_pc_mount_retention(state))
        self.assertEqual(pc_active_actor_ids(state), ('pc1', 'minion1'))
        with self.assertRaises(ValueError):
            replace(state, companions=(replace(state.companions[0], retained_since_round=1),
                state.companions[1]))

    def test_retention_cannot_forge_new_hp_or_another_physical_location(self):
        _, proof = self.retained()
        injured = replace(proof.state.snapshot, state=replace(proof.state.snapshot.state,
            injury=replace(proof.state.snapshot.state.injury,
                conditions=proof.state.snapshot.state.injury.conditions.with_condition(Condition.STAGGERED))))
        with self.assertRaises(ValueError):
            replace(proof, state=replace(proof.state, snapshot=injured))
        with self.assertRaises(ValueError): replace(proof, history_index=proof.history_index + 1)
        with self.assertRaises(ValueError): replace(proof, battlefield=proof.previous_battlefield)

    def next_round_companion_turn(self, state, *, npc=False):
        from towr.domain.pc_melee_result_models import pc_melee_round_participants, pc_melee_next_actor, pc_melee_action_id
        from towr.domain.turn_models import CombatRoundAdvanceRequest, CombatTurnStartRequest
        from towr.rules.turn_resolution import advance_combat_round, start_combat_turn
        # A prepared clock boundary, followed by real round/turn admission receipts.
        state = replace(state, round_state=replace(state.round_state,
            completed_turn_entity_ids=('pc1', 'minion1')))
        request = CombatRoundAdvanceRequest(state.source.id+':r1:advance', state.round_state,
            pc_melee_round_participants(state))
        state = PcMeleeStep(state, advance_combat_round(request)).state
        expected = ('pc1', 'minion1', 'minion1:mount') if npc else ('pc1', 'pc1:mount', 'minion1')
        self.assertEqual(tuple(p.entity_id for p in state.round_state.participants), expected)
        completed = ('pc1', 'minion1') if npc else ('pc1',)
        state = replace(state, round_state=replace(state.round_state, completed_turn_entity_ids=completed))
        actor = pc_melee_next_actor(state)
        self.assertEqual(actor, 'minion1:mount' if npc else 'pc1:mount')
        return PcMeleeStep(state, start_combat_turn(CombatTurnStartRequest(
            pc_melee_action_id(state, actor)+':start', state.round_state, actor))).state

    def test_waiting_companion_gets_next_round_slot_after_rider_and_no_action(self):
        from towr.domain.pc_companion_turn_models import expected_companion_wait
        for npc in (False, True):
            with self.subTest(npc=npc):
                state, _ = self.retained(npc=npc)
                state = self.next_round_companion_turn(state, npc=npc)
                before = state.companions
                proof = expected_companion_wait(state)
                self.assertFalse(proof.result.completed_turn.action_slots)
                after = PcMeleeStep(state, proof).state
                self.assertIsNone(after.round_state.active_turn)
                self.assertEqual(after.companions, before)
                with self.assertRaises(ValueError): PcMeleeStep(after, proof)

    def test_companion_uses_one_real_recover_on_own_conditions_without_healing_or_fate(self):
        from towr.domain.pc_actor_models import pc_actor_injury, pc_actor_npc_update
        from towr.domain.pc_companion_turn_models import build_companion_recover, expected_companion_wait
        from towr.domain.pc_melee_result_models import pc_melee_action_id, pc_melee_action_declaration, PcTurnEndProof
        from towr.domain.pc_battlefield_movement_models import PcBattlefieldRecoverProof, battlefield_recovered_injury
        from towr.domain.pc_ally_recover_models import expected_pc_standard_recover
        from towr.domain.turn_models import CombatActionSlotRequest, ActionSlotGrant, CombatTurnEndRequest
        from towr.rules.turn_resolution import reserve_combat_action_slot, end_combat_turn
        state, _ = self.retained(kind=CombatMount.DEMIGRYPH)
        injury = pc_actor_injury(state, 'pc1:mount')
        injury = replace(injury, wounds=1, conditions=injury.conditions.with_condition(
            Condition.STAGGERED).with_condition(Condition.PRONE).with_condition(Condition.DRAINED))
        state = replace(state, **pc_actor_npc_update(state, 'pc1:mount', injury=injury))
        state = self.next_round_companion_turn(state)
        self.assertIsNone(expected_companion_wait(state))
        actor, fate = 'pc1:mount', state.party[0].fate
        action_id = pc_melee_action_id(state, actor)
        slot = reserve_combat_action_slot(CombatActionSlotRequest(action_id+':reserve',
            state.round_state, actor, pc_melee_action_declaration(state), ActionSlotGrant.STANDARD))
        state = PcMeleeStep(state, slot).state
        request = build_companion_recover(state)
        result = expected_pc_standard_recover(request)
        state = PcMeleeStep(state, PcBattlefieldRecoverProof(request, result, injury,
            battlefield_recovered_injury(injury, result))).state
        own = pc_actor_injury(state, actor)
        self.assertEqual(own.wounds, 1)
        self.assertTrue(own.conditions.has(Condition.DRAINED))
        self.assertFalse(own.conditions.has(Condition.STAGGERED))
        self.assertFalse(own.conditions.has(Condition.PRONE))
        self.assertTrue(state.round_state.active_turn.action_slots[0].executed)
        self.assertEqual(state.party[0].fate, fate)
        end = end_combat_turn(CombatTurnEndRequest(action_id+':end', state.round_state, actor))
        self.assertIsNone(PcMeleeStep(state, PcTurnEndProof(end, None, None)).state.round_state.active_turn)

    def test_free_stand_and_remount_in_place_spends_one_move_preserves_body_and_no_action(self):
        from towr.domain.pc_back_in_saddle_models import expected_back_in_saddle_move
        from towr.domain.pc_actor_models import pc_actor_injury, pc_actor_npc_update
        from towr.domain.pc_mount_models import pc_is_mounted
        from towr.domain.pc_melee_result_models import pc_melee_action_id
        from towr.domain.turn_models import CombatTurnStartRequest
        from towr.rules.turn_resolution import start_combat_turn
        for npc in (False, True):
            with self.subTest(npc=npc):
                state, _ = self.retained(kind=CombatMount.DEMIGRYPH, npc=npc, distance=R.SHORT)
                actor = 'minion1' if npc else 'pc1'
                mount_id = actor+':mount'
                before = pc_actor_injury(state, mount_id)
                before = replace(before, wounds=1, conditions=before.conditions.with_condition(Condition.DRAINED))
                state = replace(state, **pc_actor_npc_update(state, mount_id, injury=before))
                if npc:
                    state = replace(state, round_state=replace(state.round_state, completed_turn_entity_ids=('pc1',)))
                state = PcMeleeStep(state, start_combat_turn(CombatTurnStartRequest(
                    pc_melee_action_id(state, actor)+':start', state.round_state, actor))).state
                proof = expected_back_in_saddle_move(state)
                self.assertIsNotNone(proof)
                after = PcMeleeStep(state, proof).state
                self.assertTrue(pc_is_mounted(after, actor))
                self.assertFalse(pc_actor_injury(after, actor).conditions.has(Condition.PRONE))
                self.assertEqual(pc_actor_injury(after, mount_id), before)
                self.assertFalse(after.round_state.active_turn.action_slots)
                self.assertIn(actor, after.battlefield.spatial.free_move_used_entity_ids)
                self.assertEqual(after.battlefield.spatial.placement_for(actor).zone_id,
                    state.battlefield.spatial.placement_for(actor).zone_id)
                self.assertNotIn(mount_id, pc_active_actor_ids(after))
                self.assertNotIn(mount_id, tuple(p.entity_id for p in after.battlefield.spatial.placements))
                self.assertIsNone(expected_back_in_saddle_move(after))
                with self.assertRaises(ValueError): PcMeleeStep(after, proof)

    def test_close_enemy_requires_paid_recover_and_remount_does_not_spend_free_movement(self):
        from towr.domain.pc_back_in_saddle_models import expected_back_in_saddle_move, expected_back_in_saddle_recover
        from towr.domain.pc_melee_result_models import pc_melee_action_id, pc_melee_action_declaration, build_pc_melee_recover, PcRecoverProof
        from towr.domain.pc_battlefield_movement_models import build_pc_battlefield_npc_recover, PcBattlefieldRecoverProof, battlefield_recovered_injury
        from towr.domain.pc_ally_recover_models import expected_pc_standard_recover
        from towr.domain.pc_mount_models import pc_is_mounted
        from towr.domain.pc_actor_models import pc_actor_injury
        from towr.domain.turn_models import CombatTurnStartRequest, CombatActionSlotRequest, ActionSlotGrant
        from towr.rules.turn_resolution import start_combat_turn, reserve_combat_action_slot
        for npc in (False, True):
            with self.subTest(npc=npc):
                state, _ = self.retained(npc=npc)
                actor = 'minion1' if npc else 'pc1'
                if npc:
                    state = replace(state, round_state=replace(state.round_state, completed_turn_entity_ids=('pc1',)))
                action_id = pc_melee_action_id(state, actor)
                state = PcMeleeStep(state, start_combat_turn(CombatTurnStartRequest(
                    action_id+':start', state.round_state, actor))).state
                self.assertIsNone(expected_back_in_saddle_move(state))
                state = PcMeleeStep(state, reserve_combat_action_slot(CombatActionSlotRequest(
                    action_id+':reserve', state.round_state, actor,
                    pc_melee_action_declaration(state), ActionSlotGrant.STANDARD))).state
                request = build_pc_battlefield_npc_recover(state) if npc else build_pc_melee_recover(state)
                self.assertEqual(request.choice.mount.mount_id, actor+':mount')
                self.assertIsNotNone(request.choice.back_in_saddle_source)
                result = expected_pc_standard_recover(request)
                before = pc_actor_injury(state, actor)
                recovery = (PcBattlefieldRecoverProof(request,result,before,battlefield_recovered_injury(before,result))
                    if npc else PcRecoverProof(result))
                state = PcMeleeStep(state, recovery).state
                proof = expected_back_in_saddle_recover(state)
                self.assertIsNotNone(proof)
                after = PcMeleeStep(state, proof).state
                self.assertTrue(pc_is_mounted(after, actor))
                self.assertNotIn(actor, after.battlefield.spatial.free_move_used_entity_ids)
                self.assertEqual(len(after.round_state.active_turn.action_slots), 1)
                self.assertTrue(after.round_state.active_turn.action_slots[0].executed)
                self.assertEqual(pc_actor_injury(after, actor+':mount'), pc_actor_injury(state, actor+':mount'))
                with self.assertRaises(ValueError): PcMeleeStep(after, proof)

    def test_physical_kernel_targets_real_npc_bodies_on_either_side_without_pc_wound_or_fate(self):
        from towr.domain.pc_melee_result_models import prepare_pc_weapon_kernel, pc_melee_action_id
        from towr.domain.pc_weapon_intent_models import build_pc_explicit_attack_weapon_intent
        from towr.domain.turn_models import CombatTurnState, CombatSide
        from towr.domain.resolution_models import TargetInjuryPolicy
        from towr.rules.kernel import resolve_kernel_attack

        class HitThenFailedProtection:
            def __init__(self): self.rolls = 0
            def randint(self, low, high):
                self.rolls += 1
                return 1 if self.rolls <= 3 else 10

        for npc_attacks in (False, True):
            with self.subTest(npc_attacks=npc_attacks):
                state, _ = self.retained(npc=not npc_attacks)
                actor, target = ('minion1', 'pc1:mount') if npc_attacks else ('pc1', 'minion1:mount')
                side = CombatSide.OPPOSITION if npc_attacks else CombatSide.PLAYERS_AND_ALLIES
                state = replace(state, round_state=replace(state.round_state,
                    active_turn=CombatTurnState(actor, side),
                    completed_turn_entity_ids=('pc1',) if npc_attacks else ()))
                identifier = pc_melee_action_id(state, actor)
                intent = build_pc_explicit_attack_weapon_intent(state, actor, target, identifier)
                kernel, protection = prepare_pc_weapon_kernel(state, intent, identifier)
                self.assertIs(kernel.target_policy, TargetInjuryPolicy.MINION)
                self.assertEqual(kernel.target_id, target)
                self.assertEqual(protection.defender_id, target)
                result = resolve_kernel_attack(kernel, HitThenFailedProtection())
                self.assertIsNotNone(result.profile_wound)
                self.assertIsNone(result.character_wound)
                self.assertIsNone(result.pending_character_wound)
                self.assertTrue(result.target_state.defeated)

    def test_prepared_spatial_budget_observations_survive_remount_and_same_round_detach(self):
        from types import SimpleNamespace
        from dataclasses import fields
        from towr.domain.pc_back_in_saddle_models import expected_back_in_saddle_move
        from towr.domain.pc_mount_models import PcDismountProof, _source_id
        from towr.domain.turn_models import CombatTurnState, CombatSide
        state, _ = self.retained(distance=R.SHORT)
        # Observed creature usage is a prepared spatial prefix. This is a
        # receipt-factory check, not a claimed native Give Ground/Run journal.
        values = {field.name: getattr(state, field.name) for field in fields(state)}
        values['round_state'] = replace(state.round_state,
            active_turn=CombatTurnState('pc1', CombatSide.PLAYERS_AND_ALLIES))
        spatial = replace(state.battlefield.spatial, gave_ground_entity_ids=('pc1:mount',),
            free_move_used_entity_ids=('pc1:mount',), difficult_terrain_tested_entity_ids=('pc1:mount',))
        values['battlefield'] = replace(state.battlefield, spatial=spatial)
        view = SimpleNamespace(**values, participant=state.participant, enemy=state.enemy,
            exited_npc_ids=state.exited_npc_ids)
        move = expected_back_in_saddle_move(view)
        usage = move.body.stored_spatial_usage
        self.assertEqual((usage.gave_ground, usage.free_move_used, usage.difficult_terrain_tested),
            (True, True, True))
        self.assertEqual(move.battlefield.spatial.free_move_used_entity_ids, ('pc1',))
        index = len(state.history) + 1
        dismount = PcDismountProof('pc1', _source_id(state.source, 'pc1', index), index,
            move.mount, replace(move.mount, mounted=False), state.party[0].injury)
        view.history = (*state.history, move, dismount)
        view.mounts = tuple(dismount.state if row.actor_id == 'pc1' else row for row in state.mounts)
        view.companions = (move.body, state.companions[1])
        view.battlefield = move.battlefield
        retained = expected_pc_mount_retention(view)
        spatial = retained.battlefield.spatial
        for ids in (spatial.gave_ground_entity_ids, spatial.free_move_used_entity_ids,
                spatial.difficult_terrain_tested_entity_ids):
            self.assertEqual(ids.count('pc1:mount'), 1)
        self.assertIn('pc1', spatial.free_move_used_entity_ids)


if __name__ == '__main__': main()
