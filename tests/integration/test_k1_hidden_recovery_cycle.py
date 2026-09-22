from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_aim_resolution import aim_request, attack_execution_request
from tests.unit.test_k1_hidden_attack_resolution import execution_request as hidden_request
from tests.unit.test_k1_move_quietly_resolution import (
    move_quietly_declaration, request as quietly_request, reserve_action,
)
from tests.unit.test_k1_ranged_weapon_attack_preparation import preparation_request
from tests.unit.test_k1_recover_resolution import recover_request, self_target
from towr.domain.attack_models import AttackOutcome, ResilienceProfile
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.hidden_continuation_models import MoveQuietlyHiddenAttackContinuationRequest
from towr.domain.hidden_give_ground_models import HiddenGiveGroundExecutionRequest
from towr.domain.hidden_lifecycle_models import HiddenLifecycleApplicationRequest, HiddenLifecycleState
from towr.domain.hiding_position_models import HidingPositionState, RegisteredHiddenAttackExecutionRequest
from towr.domain.move_quietly_models import MoveQuietlyHidingChoice
from towr.domain.movement_models import FreeMovementRequest, MovementSpeed
from towr.domain.prepared_hidden_ranged_attack_models import PreparedHiddenRangedAttackExecutionRequest
from towr.domain.prepared_ranged_weapon_attack_models import PreparedRangedWeaponAttackExecutionRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.magic_models import WizardMagicState
from towr.domain.recover_models import (
    RecoverActionExecutionRequest, RecoverConditionRemovalChoice, RecoverMode, RecoverStandardChoice,
)
from towr.domain.reload_models import create_initial_ranged_weapon_reload_state
from towr.domain.resolution_models import GiveGroundRequest, GiveGroundResolutionRequest
from towr.domain.test_models import Skill, TestProfile, TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest, CombatRoundAdvanceRequest,
    CombatTurnEndRequest, CombatTurnStartRequest,
)
from towr.rules import hidden_lifecycle_resolution as lifecycle
from towr.rules.aim_resolution import execute_aim_action
from towr.rules.free_movement_resolution import resolve_free_movement
from towr.rules.hiding_position_resolution import prepare_move_quietly_with_hiding_positions
from towr.rules.prepared_hidden_ranged_attack_resolution import execute_prepared_hidden_ranged_attack
from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack
from towr.rules.recover_resolution import execute_recover_action
from towr.rules.spatial_resolution import start_next_spatial_round
from towr.rules.turn_resolution import (
    advance_combat_round, end_combat_turn, reserve_combat_action_slot, start_combat_turn,
)


def finish_turn(state, spatial):
    actor = state.active_turn.actor_id
    if not state.active_turn.action_slots:
        # Other actors spend their required standard action on Recover without selected effects.
        state = reserve_combat_action_slot(CombatActionSlotRequest(
            f"slot:{state.round_number}:{actor}", state, actor, CombatActionDeclaration(CombatActionKind.RECOVER),
            ActionSlotGrant.STANDARD,
        )).state
        state = execute_recover_action(RecoverActionExecutionRequest(
            f"recover:{state.round_number}:{actor}", state, actor, ConditionState(),
            has_enemy_in_zone(spatial, actor), 1, RecoverMode.STANDARD,
            RecoverStandardChoice(WizardMagicState()),
        ), SequenceRandom([])).round_state
    return end_combat_turn(CombatTurnEndRequest(
        f"end:{state.round_number}:{actor}", state, actor,
    )).state


def next_hero_round(state, spatial):
    """Complete turns through the public scheduler without changing spatial state."""
    if state.active_turn is not None:
        state = finish_turn(state, spatial)
    for participant in state.participants:
        if participant.entity_id not in state.completed_turn_entity_ids:
            state = start_combat_turn(CombatTurnStartRequest(
                f"start:{state.round_number}:{participant.entity_id}", state, participant.entity_id,
            )).state
            state = finish_turn(state, spatial)
    state = advance_combat_round(CombatRoundAdvanceRequest(
        f"advance:{state.round_number}", state, state.participants,
    )).state
    return start_combat_turn(CombatTurnStartRequest(f"hero:{state.round_number}", state, "hero")).state


def has_enemy_in_zone(spatial, actor="hero"):
    owner = spatial.placement_for(actor)
    return any(item.side_id != owner.side_id for item in spatial.placements_in(owner.zone_id))


class K1HiddenRecoveryCycleTests(unittest.TestCase):
    def reach_recovery(self, recover_values=(1, 10)):
        initial = HiddenLifecycleState(
            HidingPositionState("hero", ("hiding:older",), ("attack:older",)),
            consumed_opportunity_ids=("hidden:older",),
        )
        request = prepare_move_quietly_with_hiding_positions(initial.hiding_positions, quietly_request())
        first = lifecycle.execute_hidden_lifecycle_move_quietly(initial, request, SequenceRandom([1, 10, 10]))
        quietly = first.completed
        turn = end_combat_turn(CombatTurnEndRequest("hero:end:1", quietly.round_state, "hero")).state
        turn = start_combat_turn(CombatTurnStartRequest("scout:start:1", turn, "scout")).state
        scout = resolve_free_movement(FreeMovementRequest(
            "scout:free:1", turn, quietly.spatial_state, "scout", MovementSpeed.NORMAL,
            ConditionState(), ("zone:a",),
        ))
        ground_request = HiddenGiveGroundExecutionRequest(
            "hero:ground:1", quietly,
            GiveGroundResolutionRequest(
                GiveGroundRequest("external:scout-reaction:1"), scout.state, "hero", "zone:c",
                request.actor_conditions, away_from_entity_id="scout",
            ), first.state.consumed_opportunity_ids, intervening_movements=(scout,),
        )
        lost = lifecycle.execute_hidden_lifecycle_give_ground(first.state, ground_request)
        movement = lost.completed.source_request.movement
        self.assertTrue(movement.conditions.has(Condition.BROKEN))
        self.assertIsNone(lost.state.opportunity)
        self.assertIs(lost.state.hiding_positions, initial.hiding_positions)
        self.assertEqual(lost.state.consumed_opportunity_ids, ("hidden:older", first.state.opportunity.id))
        self.assertIs(lost.completed.source_request.intervening_movements[0], scout)
        self.assertTrue(set(scout.applied_rule_ids) <= set(lost.applied_rule_ids))
        with self.assertRaisesRegex(ValueError, "no active"):
            lifecycle.execute_hidden_lifecycle_give_ground(lost.state, ground_request)

        round_state = next_hero_round(scout.round_state, movement.state)
        spatial = start_next_spatial_round(movement.state)
        choice = RecoverConditionRemovalChoice(
            self_target(movement.conditions), Condition.BROKEN,
            TestRequest("hero:courage:2", TestProfile(2, 5)), Skill.WILLPOWER, True,
        )
        # Recover in the enemy Zone must fail before RNG; do not remove Broken by hand.
        reserved = reserve_action(round_state, CombatActionDeclaration(CombatActionKind.RECOVER))
        rng = Mock()
        with self.assertRaises(ValueError):
            execute_recover_action(recover_request(
                reserved, actor_conditions=movement.conditions, mode=RecoverMode.REMOVE_CONDITION,
                choice=choice, actor_has_enemy_in_zone=has_enemy_in_zone(spatial),
            ), rng)
        self.assertEqual(rng.mock_calls, [])
        fled = resolve_free_movement(FreeMovementRequest(
            "hero:flee:2", reserved, spatial, "hero", MovementSpeed.NORMAL,
            movement.conditions, ("zone:b",),
        ))
        self.assertFalse(has_enemy_in_zone(fled.state))
        self.assertTrue(movement.conditions.has(Condition.BROKEN))
        recovered = execute_recover_action(recover_request(
            fled.round_state, actor_conditions=movement.conditions, mode=RecoverMode.REMOVE_CONDITION,
            choice=choice, actor_has_enemy_in_zone=has_enemy_in_zone(fled.state),
        ), SequenceRandom(recover_values))
        self.assertTrue(recovered.slot.executed)
        self.assertEqual(recovered.resolution.conditions.has(Condition.BROKEN), recover_values[0] > 5)
        return first, lost, fled, recovered

    def test_recovery_new_hiding_aim_and_crossbow_hit_or_miss_share_continuous_snapshots(self):
        for aim_success in (False, True):
            for hit in (False, True):
                with self.subTest(aim_success=aim_success, hit=hit):
                    first, lost, fled, recovered = self.reach_recovery()
                    weapon = create_initial_ranged_weapon_reload_state("hero:crossbow", RangedWeaponId.CROSSBOW)
                    round_state = next_hero_round(recovered.round_state, fled.state)
                    spatial = start_next_spatial_round(fled.state)
                    round_state = reserve_action(round_state, move_quietly_declaration())
                    candidate = replace(quietly_request(
                        round_state=round_state, state=spatial, conditions=recovered.resolution.conditions,
                        include_movement=False, hiding_choice=MoveQuietlyHidingChoice.HIDE_IN_CURRENT_ZONE,
                        hiding_position_id="hiding:tree",
                    ), id="quietly:second")
                    candidate = prepare_move_quietly_with_hiding_positions(lost.state.hiding_positions, candidate)
                    second = lifecycle.execute_hidden_lifecycle_move_quietly(
                        lost.state, candidate, SequenceRandom([1, 10, 10]))
                    self.assertIs(second.completed.previous_spatial_state, spatial)
                    self.assertEqual(candidate.used_hiding_position_ids, ("hiding:older",))
                    self.assertFalse(candidate.actor_conditions.has(Condition.BROKEN))
                    self.assertIs(candidate.actor_conditions, recovered.resolution.conditions)

                    round_state = next_hero_round(second.completed.round_state, second.completed.spatial_state)
                    spatial = start_next_spatial_round(second.completed.spatial_state)
                    aimed_turn = reserve_action(round_state, CombatActionDeclaration(CombatActionKind.AIM))
                    aim = execute_aim_action(aim_request(aimed_turn, target_id="guard"),
                                            SequenceRandom([1 if aim_success else 10, 10, 10]))
                    continued = lifecycle.continue_hidden_lifecycle(second.state, MoveQuietlyHiddenAttackContinuationRequest(
                        "continue:aim", second.completed, second.state.opportunity, aim.slot.execution,
                        spatial, "hiding:tree", False, second.state.consumed_opportunity_ids,
                    ))
                    self.assertIs(continued.state, second.state)

                    # The next owner action is the shot in round 5, with no invented extra action grant.
                    round_state = next_hero_round(aim.round_state, spatial)
                    spatial = start_next_spatial_round(spatial)
                    attack_turn = reserve_action(round_state, CombatActionDeclaration(CombatActionKind.ATTACK))
                    attack = attack_execution_request(state=attack_turn, target_id="guard", attacker_profile=TestProfile(2, 5))
                    # A resilient target keeps this integration scenario independent of Wounds Table RNG.
                    kernel = attack.kernel_request
                    attack = replace(attack, kernel_request=replace(kernel, attack=replace(kernel.attack,
                        impact_spec=replace(kernel.attack.impact_spec, resilience=ResilienceProfile(20)))))
                    preparation = prepare_ranged_weapon_attack(replace(preparation_request(
                        RangedWeaponId.CROSSBOW, attack=attack, aim=aim, next_cycle="hero:reload:1",
                    ), weapon_state=weapon))
                    hidden = hidden_request(
                        move_quietly=second.completed, attack=preparation.execution.attack, spatial_state=spatial,
                        target_id="guard", hiding_position_id="hiding:tree",
                        consumed=continued.state.consumed_opportunity_ids,
                    )
                    prepared = PreparedHiddenRangedAttackExecutionRequest(
                        "prepared:hidden:5", hidden, PreparedRangedWeaponAttackExecutionRequest(
                            "prepared:5", preparation, consumed_aim_follow_up_ids=("aim:older",)),
                    )
                    registered = RegisteredHiddenAttackExecutionRequest("registered:5", continued.state.hiding_positions, prepared)
                    before = deepcopy((continued.state, registered, weapon, recovered))
                    values = [1 if hit else 10, 10] + ([10] if aim_success else [])
                    rng = SequenceRandom([*values, 7])
                    with patch("towr.rules.hiding_position_resolution.execute_prepared_hidden_ranged_attack",
                               wraps=execute_prepared_hidden_ranged_attack) as execute:
                        final = lifecycle.execute_hidden_lifecycle_attack(continued.state, registered, rng)
                    execute.assert_called_once_with(prepared, rng, decisions=None)
                    self.assertEqual(rng.randint(1, 10), 7)
                    shot = final.completed.execution
                    self.assertEqual(shot.ranged_attack.attack.resolution.attack.outcome,
                                     AttackOutcome.HIT if hit else AttackOutcome.MISS)
                    self.assertIsNone(shot.ranged_attack.attack.resolution.attack.defender_test)
                    self.assertFalse(shot.ranged_attack.weapon_state.loaded)
                    self.assertEqual(shot.ranged_attack.weapon_state.reload_cycle_id, "hero:reload:1")
                    self.assertTrue(weapon.loaded)
                    self.assertEqual(shot.consumed_aim_follow_up_ids,
                                     ("aim:older", preparation.aim_follow_up.request_id))
                    self.assertEqual(final.state.consumed_opportunity_ids,
                                     ("hidden:older", first.state.opportunity.id, second.state.opportunity.id))
                    self.assertEqual(final.state.hiding_positions.used_hiding_position_ids,
                                     ("hiding:older", "hiding:tree"))
                    self.assertEqual(final.state.hiding_positions.consumed_attack_execution_ids,
                                     ("attack:older", attack.id))
                    self.assertIsNone(final.state.opportunity)
                    self.assertTrue(set(preparation.applied_rule_ids) <= set(final.applied_rule_ids))
                    self.assertTrue(set(second.completed.applied_rule_ids) <= set(final.applied_rule_ids))
                    slots = shot.ranged_attack.attack.state.active_turn.action_slots
                    self.assertEqual(len(slots), 1)
                    self.assertTrue(slots[0].executed)
                    self.assertEqual((continued.state, registered, weapon, recovered), before)
                    with self.assertRaisesRegex(ValueError, "no active"):
                        lifecycle.execute_hidden_lifecycle_attack(final.state, registered, Mock())
                    with self.assertRaisesRegex(ValueError, "already consumed"):
                        HiddenLifecycleApplicationRequest("reactivate:second", final.state, second.completed)

    def test_failed_recover_keeps_broken_and_completed_slot_without_restoring_opportunity(self):
        first, lost, fled, recovered = self.reach_recovery((10, 10))
        self.assertFalse(recovered.resolution.removed)
        self.assertTrue(recovered.resolution.conditions.has(Condition.BROKEN))
        self.assertTrue(recovered.slot.executed)
        self.assertFalse(has_enemy_in_zone(fled.state))
        self.assertIsNone(lost.state.opportunity)
        self.assertEqual(lost.state.consumed_opportunity_ids, ("hidden:older", first.state.opportunity.id))
        self.assertEqual(lost.state.hiding_positions.used_hiding_position_ids, ("hiding:older",))
