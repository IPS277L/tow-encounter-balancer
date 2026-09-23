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
from towr.domain.aim_models import AIM_FOLLOW_UP_RULE_ID, AimFollowUpOutcome, AimFollowUpRequest
from towr.domain.aim_consumption_models import AimAttackConsumptionRequest, AimConsumptionState, AimLossConsumptionRequest
from towr.domain.aim_ranged_weapon_attack_models import AimRangedWeaponAttackExecutionRequest
from towr.domain.attack_models import AttackOutcome, ResilienceProfile
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.hidden_attack_models import HiddenAttackOpportunityLossReason
from towr.domain.hidden_continuation_models import (
    HiddenOpportunityContinuationOutcome, MoveQuietlyHiddenAttackContinuationRequest,
)
from towr.domain.hidden_give_ground_models import HiddenGiveGroundExecutionRequest
from towr.domain.hidden_lifecycle_models import HiddenLifecycleApplicationRequest, HiddenLifecycleState
from towr.domain.hiding_position_models import HidingPositionState, RegisteredHiddenAttackExecutionRequest
from towr.domain.move_quietly_models import MoveQuietlyHidingChoice, MoveQuietlyOutcome
from towr.domain.movement_models import FreeMovementRequest, MovementSpeed
from towr.domain.prepared_hidden_ranged_attack_models import PreparedHiddenRangedAttackExecutionRequest
from towr.domain.prepared_ranged_weapon_attack_models import PreparedRangedWeaponAttackExecutionRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.magic_models import WizardMagicState
from towr.domain.recover_models import (
    RecoverActionExecutionRequest, RecoverConditionRemovalChoice, RecoverMode, RecoverStandardChoice,
)
from towr.domain.reload_models import (
    ReloadActionExecutionRequest, create_initial_ranged_weapon_reload_state, reload_approach_id,
)
from towr.domain.resolution_models import GiveGroundRequest, GiveGroundResolutionRequest
from towr.domain.test_models import Skill, TestProfile, TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest, CombatRoundAdvanceRequest,
    CombatTurnEndRequest, CombatTurnStartRequest, ImproviseKind,
)
from towr.rules import hidden_lifecycle_resolution as lifecycle
from towr.rules.aim_resolution import execute_aim_action, resolve_aim_follow_up
from towr.rules.aim_consumption_resolution import consume_lost_aim, register_aim_ranged_attack
from towr.rules.free_movement_resolution import resolve_free_movement
from towr.rules.hiding_position_resolution import prepare_move_quietly_with_hiding_positions
from towr.rules.prepared_hidden_ranged_attack_resolution import execute_prepared_hidden_ranged_attack
from towr.rules.ranged_weapon_attack_preparation import (
    prepare_ranged_weapon_attack, prepare_ranged_weapon_attack_with_aim_history,
)
from towr.rules.recover_resolution import execute_recover_action
from towr.rules.reload_resolution import execute_reload_action
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
                    self.reach_first_shot(aim_success, hit)

    def reach_first_shot(self, aim_success, hit):
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
        applied = register_aim_ranged_attack(AimAttackConsumptionRequest(
            "register:first-aim", AimConsumptionState("hero", consumed_aim_follow_up_ids=shot.previous_consumed_aim_follow_up_ids),
            shot.prepared_attack.execution,
        ))
        self.assertIs(applied.source_request.execution.ranged_attack, shot.ranged_attack)
        self.assertEqual(applied.state.consumed_aim_source_ids, (aim.request_id,))
        self.assertEqual(applied.state.consumed_aim_follow_up_ids, shot.consumed_aim_follow_up_ids)
        with self.assertRaisesRegex(ValueError, "source was already consumed"):
            replace(applied.source_request, state=applied.state)
        return final, spatial, recovered.resolution.conditions, applied.state

    def test_reload_then_new_hiding_and_second_shot_preserve_history_and_consumption(self):
        for second_hit in (False, True):
            with self.subTest(second_hit=second_hit):
                self.complete_reload_cycle(second_hit)

    def test_failed_then_declined_hiding_after_reload_can_retry_without_consumption(self):
        for second_hit in (False, True):
            with self.subTest(second_hit=second_hit):
                self.complete_reload_cycle(second_hit, include_non_hidden_attempts=True)

    def complete_reload_cycle(self, second_hit: bool, *, include_non_hidden_attempts: bool = False):
        # Start with a miss so intervening idle Recover actions need no target Condition transition.
        first, spatial, conditions, aim_history = self.reach_first_shot(True, False)
        shot = first.completed.execution
        weapon = shot.ranged_attack.weapon_state
        round_state = shot.ranged_attack.attack.state
        before = deepcopy(first)

        reloaded, spatial, _, _ = self.reload_crossbow(weapon, round_state, spatial, conditions)
        weapon, round_state = reloaded.state, reloaded.round_state

        current_hidden = first.state
        if include_non_hidden_attempts:
            preserved = deepcopy((current_hidden, weapon, shot.consumed_aim_follow_up_ids))
            cases = (
                (MoveQuietlyHidingChoice.HIDE_IN_CURRENT_ZONE, (10, 10, 1), MoveQuietlyOutcome.FAILED),
                (MoveQuietlyHidingChoice.DECLINE, (1, 10, 10), MoveQuietlyOutcome.SUCCEEDED_WITHOUT_HIDING),
            )
            for index, (choice, values, expected) in enumerate(cases):
                round_state = next_hero_round(round_state, spatial)
                spatial = start_next_spatial_round(spatial)
                reserved = reserve_action(round_state, move_quietly_declaration())
                candidate = replace(quietly_request(
                    round_state=reserved, state=spatial, conditions=conditions,
                    include_movement=False, hiding_choice=choice, hiding_position_id="hiding:rock",
                ), id=f"quietly:non-hidden:{index}")
                candidate = prepare_move_quietly_with_hiding_positions(current_hidden.hiding_positions, candidate)
                source = deepcopy((current_hidden, candidate))
                rng = SequenceRandom([*values, 7])
                attempt = lifecycle.execute_hidden_lifecycle_move_quietly(current_hidden, candidate, rng)
                self.assertEqual(rng.randint(1, 10), 7)
                completed = attempt.completed
                self.assertIs(completed.outcome, expected)
                self.assertIs(completed.source_request, candidate)
                self.assertIs(completed.previous_round_state, reserved)
                self.assertIs(completed.spatial_state, spatial)
                self.assertIsNone(completed.free_movement_result)
                self.assertIsNone(completed.hidden_attack_opportunity)
                self.assertIsNone(attempt.state.opportunity)
                self.assertIs(attempt.state, current_hidden)
                self.assertTrue(completed.slot.executed)
                self.assertEqual(completed.slot.execution.id, candidate.id)
                self.assertEqual(len(completed.round_state.active_turn.action_slots), 1)
                self.assertNotIn("hero", completed.spatial_state.free_move_used_entity_ids)
                self.assertTrue(set(completed.applied_rule_ids) <= set(attempt.applied_rule_ids))
                self.assertEqual((current_hidden, candidate), source)
                self.assertEqual((attempt.state, weapon, shot.consumed_aim_follow_up_ids), preserved)
                self.assertTrue(weapon.loaded)
                replay_rng = Mock()
                with self.assertRaisesRegex(ValueError, "already been executed"):
                    lifecycle.execute_hidden_lifecycle_move_quietly(
                        attempt.state, replace(candidate, round_state=completed.round_state), replay_rng)
                self.assertEqual(replay_rng.mock_calls, [])
                current_hidden, round_state, spatial = attempt.state, completed.round_state, completed.spatial_state

        hidden = self.hide_again(current_hidden, round_state, spatial, conditions)
        self.finish_second_shot(first, hidden.state, reloaded, hidden.completed.round_state,
                                hidden.completed.spatial_state, second_hit)
        self.assertEqual(first, before)

    def test_reload_inside_hiding_preserves_opportunity_until_second_hit_or_miss(self):
        for second_hit in (False, True):
            with self.subTest(second_hit=second_hit):
                first, spatial, conditions, aim_history = self.reach_first_shot(True, False)
                shot = first.completed.execution
                weapon = shot.ranged_attack.weapon_state
                before = deepcopy((first, weapon))
                hidden = self.hide_again(first.state, shot.ranged_attack.attack.state, spatial, conditions)
                self.assertFalse(weapon.loaded)
                reloaded, spatial, continued, _ = self.reload_crossbow(
                    weapon, hidden.completed.round_state, hidden.completed.spatial_state, conditions,
                    hidden_state=hidden.state,
                )
                self.assertIs(continued, hidden.state)
                self.assertIs(continued.active_move_quietly, hidden.completed)
                self.finish_second_shot(first, continued, reloaded, reloaded.round_state, spatial, second_hit)
                self.assertEqual((first, weapon), before)

    def test_reveal_after_partial_reload_preserves_progress_then_allows_new_hiding(self):
        for second_hit in (False, True):
            with self.subTest(second_hit=second_hit):
                first, spatial, conditions, aim_history = self.reach_first_shot(True, False)
                shot = first.completed.execution
                weapon = shot.ranged_attack.weapon_state
                hidden = self.hide_again(first.state, shot.ranged_attack.attack.state, spatial, conditions)
                before = deepcopy((first, hidden, weapon))
                reloaded, spatial, lost, _ = self.reload_crossbow(
                    weapon, hidden.completed.round_state, hidden.completed.spatial_state, conditions,
                    hidden_state=hidden.state, reveal_after_partial=True,
                )
                self.assertIsNone(lost.opportunity)
                self.assertIs(lost.hiding_positions, first.state.hiding_positions)
                self.assertEqual(lost.consumed_opportunity_ids,
                                 (*first.state.consumed_opportunity_ids, hidden.state.opportunity.id))
                self.assertTrue(reloaded.state.loaded)
                self.assertEqual(reloaded.previous_state.exacting.accumulated_successes, 1)
                self.assertEqual(reloaded.state.exacting.accumulated_successes, 2)

                # A valid prepared shot from the old source must fail at the lifecycle boundary.
                preview_round = next_hero_round(reloaded.round_state, spatial)
                preview_spatial = start_next_spatial_round(spatial)
                preview_round = reserve_action(preview_round, CombatActionDeclaration(CombatActionKind.ATTACK))
                attack = replace(attack_execution_request(state=preview_round, target_id="guard"), id="attack:stale-source")
                preparation = prepare_ranged_weapon_attack(replace(preparation_request(
                    RangedWeaponId.CROSSBOW, attack=attack, next_cycle="hero:reload:2",
                ), weapon_state=reloaded.state))
                stale = hidden_request(
                    move_quietly=hidden.completed, attack=preparation.execution.attack,
                    spatial_state=preview_spatial, target_id="guard", hiding_position_id="hiding:rock",
                    consumed=hidden.state.consumed_opportunity_ids,
                )
                prepared = PreparedHiddenRangedAttackExecutionRequest(
                    "prepared:stale:hidden", stale, PreparedRangedWeaponAttackExecutionRequest(
                        "prepared:stale", preparation, consumed_aim_follow_up_ids=shot.consumed_aim_follow_up_ids),
                )
                registered = RegisteredHiddenAttackExecutionRequest("registered:stale", lost.hiding_positions, prepared)
                rng = Mock()
                with patch.object(lifecycle, "execute_registered_hidden_attack") as execute:
                    with self.assertRaisesRegex(ValueError, "no active"):
                        lifecycle.execute_hidden_lifecycle_attack(lost, registered, rng)
                execute.assert_not_called()
                self.assertEqual(rng.mock_calls, [])
                with self.assertRaisesRegex(ValueError, "already consumed"):
                    replace(stale, consumed_opportunity_ids=lost.consumed_opportunity_ids)

                fresh = self.hide_again(lost, reloaded.round_state, spatial, conditions,
                                        position_id="hiding:crates", request_id="quietly:fourth")
                self.assertEqual(fresh.state.consumed_opportunity_ids, lost.consumed_opportunity_ids)
                final = self.finish_second_shot(first, fresh.state, reloaded, fresh.completed.round_state,
                                               fresh.completed.spatial_state, second_hit)
                self.assertEqual(final.state.hiding_positions.used_hiding_position_ids,
                                 ("hiding:older", "hiding:tree", "hiding:crates"))
                self.assertEqual(final.state.consumed_opportunity_ids,
                                 (*lost.consumed_opportunity_ids, fresh.state.opportunity.id))
                self.assertEqual((first, hidden, weapon), before)

    def test_aim_is_lost_on_reload_while_hidden_opportunity_survives_until_attack(self):
        for aim_successes in (0, 2):
            for second_hit in (False, True):
                with self.subTest(aim_successes=aim_successes, second_hit=second_hit):
                    first, spatial, conditions, aim_history = self.reach_first_shot(True, False)
                    shot = first.completed.execution
                    hidden = self.hide_again(first.state, shot.ranged_attack.attack.state, spatial, conditions)
                    round_state = next_hero_round(hidden.completed.round_state, hidden.completed.spatial_state)
                    spatial = start_next_spatial_round(hidden.completed.spatial_state)
                    reserved = reserve_action(round_state, CombatActionDeclaration(CombatActionKind.AIM))
                    candidate = aim_request(reserved, target_id="guard")
                    candidate = replace(candidate, id="aim:before-reload",
                                        awareness_test=replace(candidate.awareness_test, id="aim:before-reload:test"))
                    aim = execute_aim_action(candidate, SequenceRandom([1 if aim_successes else 10] * 2 + [10]))
                    self.assertEqual(aim.bonus.bonus_dice, aim_successes)
                    continued = lifecycle.continue_hidden_lifecycle(hidden.state, MoveQuietlyHiddenAttackContinuationRequest(
                        "continue:aim-before-reload", hidden.completed, hidden.state.opportunity, aim.slot.execution,
                        spatial, "hiding:rock", False, hidden.state.consumed_opportunity_ids,
                    ))
                    self.assertIs(continued.state, hidden.state)
                    before = deepcopy((first, hidden, aim))
                    reloaded, spatial, state, reloads = self.reload_crossbow(
                        shot.ranged_attack.weapon_state, aim.round_state, spatial, conditions, hidden_state=continued.state,
                    )
                    first_reload = reloads[0]
                    receipt = first_reload.slot.execution
                    self.assertEqual(receipt.round_number, aim.round_state.round_number + 1)
                    self.assertEqual(receipt.slot_index, 1)
                    self.assertEqual(first_reload.exacting.contribution.successes, 0)
                    self.assertTrue(first_reload.slot.executed)
                    follow_up_request = AimFollowUpRequest(
                        "aim:lost-on-reload", aim, receipt.actor_id, receipt.id, receipt.declaration,
                    )
                    lost_aim = resolve_aim_follow_up(follow_up_request)
                    self.assertIs(lost_aim.outcome, AimFollowUpOutcome.LOST)
                    self.assertIsNone(lost_aim.modifier)
                    self.assertIsNone(lost_aim.attack)
                    self.assertIs(lost_aim.source_request.aim, aim)
                    self.assertEqual(lost_aim.source_request.next_action_id, first_reload.request_id)
                    self.assertEqual(lost_aim.source_request.declaration.improvise_approach_id,
                                     reload_approach_id(reloaded.state.weapon_instance_id))
                    self.assertIn(AIM_FOLLOW_UP_RULE_ID, lost_aim.applied_rule_ids)
                    self.assertIn(aim.rule_id, lost_aim.applied_rule_ids)
                    self.assertIs(state, hidden.state)
                    first_aim = shot.source_request.prepared_attack.preparation.aim_follow_up.source_request.aim
                    history = aim_history
                    consumed = consume_lost_aim(AimLossConsumptionRequest(
                        "consume:aim-on-reload", history, lost_aim, receipt,
                    ))
                    self.assertEqual(consumed.state.consumed_aim_source_ids, (first_aim.request_id, aim.request_id))
                    self.assertIs(consumed.source_request.action, first_reload.slot.execution)
                    with self.assertRaisesRegex(ValueError, "source was already consumed"):
                        replace(consumed.source_request, state=consumed.state)
                    final = self.finish_second_shot(first, state, reloaded, reloaded.round_state, spatial,
                                                   second_hit, lost_aim=lost_aim, aim_history=consumed.state)
                    self.assertEqual(final.completed.execution.consumed_aim_follow_up_ids,
                                     (*shot.consumed_aim_follow_up_ids, lost_aim.request_id))
                    self.assertEqual(final.state.consumed_opportunity_ids,
                                     (*hidden.state.consumed_opportunity_ids, hidden.state.opportunity.id))
                    self.assertEqual((first, hidden, aim), before)

    def reload_crossbow(self, weapon, round_state, spatial, conditions,
                        *, hidden_state: HiddenLifecycleState | None = None, reveal_after_partial: bool = False):
        reloads = []
        # One Dexterity Test per standard action: failure, partial progress, completion.
        for index, (values, successes) in enumerate((((10, 10), 0), ((1, 10), 1), ((1, 10), 2))):
            round_state = next_hero_round(round_state, spatial)
            spatial = start_next_spatial_round(spatial)
            # Rejected pure preparation does not spend an action or replace the accepted snapshot.
            preview_turn = reserve_action(round_state, CombatActionDeclaration(CombatActionKind.ATTACK))
            with self.assertRaisesRegex(ValueError, "loaded"):
                prepare_ranged_weapon_attack(replace(preparation_request(
                    RangedWeaponId.CROSSBOW, next_cycle="hero:reload:2",
                    attack=attack_execution_request(state=preview_turn, target_id="guard"),
                ), weapon_state=weapon))
            self.assertEqual(round_state.active_turn.action_slots, ())
            reserved = reserve_action(round_state, CombatActionDeclaration(
                CombatActionKind.IMPROVISE, improvise_kind=ImproviseKind.SKILL,
                improvise_approach_id=reload_approach_id(weapon.weapon_instance_id),
            ))
            request = ReloadActionExecutionRequest(
                f"hero:reload-action:{index}", reserved, "hero", conditions, 1, weapon,
                TestRequest(f"hero:dexterity:{index}", TestProfile(2, 5)),
            )
            rng = SequenceRandom([*values, 7])
            reloaded = execute_reload_action(request, rng)
            reloads.append(reloaded)
            self.assertEqual(rng.randint(1, 10), 7)
            self.assertIs(reloaded.previous_state, weapon)
            self.assertIs(reloaded.previous_round_state, reserved)
            self.assertEqual(reloaded.state.exacting.accumulated_successes, successes)
            self.assertEqual(len(reloaded.state.exacting.contributions), index + 1)
            self.assertEqual(reloaded.state.loaded, successes == 2)
            self.assertEqual(reloaded.state.reload_cycle_ids, ("hero:reload:1",))
            self.assertEqual(reloaded.state.weapon_instance_id, weapon.weapon_instance_id)
            self.assertTrue(reloaded.slot.executed)
            self.assertEqual(len(reloaded.round_state.active_turn.action_slots), 1)
            replay_rng = Mock()
            with self.assertRaisesRegex(ValueError, "slot has already been executed"):
                execute_reload_action(replace(request, round_state=reloaded.round_state), replay_rng)
            self.assertEqual(replay_rng.mock_calls, [])
            if hidden_state is not None and hidden_state.opportunity is not None:
                before_continuation = deepcopy((hidden_state, reloaded, spatial))
                source = hidden_state.active_move_quietly
                continuation_request = MoveQuietlyHiddenAttackContinuationRequest(
                    f"continue:reload:{index}", source, hidden_state.opportunity, reloaded.slot.execution,
                    spatial, "hiding:rock", reveal_after_partial and index == 1, hidden_state.consumed_opportunity_ids,
                )
                continued = lifecycle.continue_hidden_lifecycle(hidden_state, continuation_request)
                if continuation_request.position_revealed:
                    self.assertIs(continued.completed.outcome, HiddenOpportunityContinuationOutcome.LOST)
                    self.assertIs(continued.completed.loss_reason, HiddenAttackOpportunityLossReason.POSITION_REVEALED)
                    self.assertIsNone(continued.completed.remaining_opportunity)
                    self.assertIsNone(continued.state.opportunity)
                    self.assertIs(continued.state.hiding_positions, hidden_state.hiding_positions)
                    self.assertEqual(continued.state.consumed_opportunity_ids,
                                     (*hidden_state.consumed_opportunity_ids, hidden_state.opportunity.id))
                    self.assertFalse(reloaded.state.loaded)
                    self.assertEqual(reloaded.state.exacting.accumulated_successes, 1)
                    with self.assertRaisesRegex(ValueError, "no active"):
                        lifecycle.continue_hidden_lifecycle(continued.state, continuation_request)
                else:
                    self.assertIs(continued.state, hidden_state)
                    self.assertIs(continued.state.active_move_quietly, source)
                    self.assertIs(continued.completed.outcome, HiddenOpportunityContinuationOutcome.PRESERVED)
                    self.assertIsNone(continued.completed.loss_reason)
                    self.assertIs(continued.completed.remaining_opportunity, hidden_state.opportunity)
                self.assertIs(continued.completed.source_request.action, reloaded.slot.execution)
                self.assertIs(continued.completed.source_request.spatial_state, spatial)
                self.assertIn(reloaded.rule_id, continued.applied_rule_ids)
                self.assertEqual((hidden_state, reloaded, spatial), before_continuation)
                hidden_state = continued.state
            weapon, round_state = reloaded.state, reloaded.round_state

        return reloaded, spatial, hidden_state, tuple(reloads)

    def hide_again(self, current_hidden, round_state, spatial, conditions,
                   *, position_id: str = "hiding:rock", request_id: str = "quietly:third"):
        round_state = next_hero_round(round_state, spatial)
        spatial = start_next_spatial_round(spatial)
        reserved = reserve_action(round_state, move_quietly_declaration())
        candidate = replace(quietly_request(
            round_state=reserved, state=spatial, conditions=conditions,
            include_movement=False, hiding_choice=MoveQuietlyHidingChoice.HIDE_IN_CURRENT_ZONE,
            hiding_position_id="hiding:tree",
        ), id=request_id)
        with self.assertRaisesRegex(ValueError, "new hiding position"):
            prepare_move_quietly_with_hiding_positions(current_hidden.hiding_positions, candidate)
        candidate = prepare_move_quietly_with_hiding_positions(
            current_hidden.hiding_positions, replace(candidate, hiding_position_id=position_id))
        self.assertEqual(candidate.used_hiding_position_ids, ("hiding:older", "hiding:tree"))
        hidden = lifecycle.execute_hidden_lifecycle_move_quietly(
            current_hidden, candidate, SequenceRandom([1, 10, 10]))
        self.assertEqual(hidden.state.consumed_opportunity_ids, current_hidden.consumed_opportunity_ids)
        self.assertIs(hidden.state.hiding_positions, current_hidden.hiding_positions)

        return hidden

    def finish_second_shot(self, first, hidden, reloaded, round_state, spatial, second_hit: bool,
                           *, lost_aim=None, aim_history: AimConsumptionState | None = None):
        shot = first.completed.execution
        weapon = reloaded.state
        before = deepcopy(first)
        consumed_aim_ids = shot.consumed_aim_follow_up_ids
        if lost_aim is not None:
            self.assertIsNotNone(aim_history)
            self.assertIn(lost_aim.source_request.aim.request_id, aim_history.consumed_aim_source_ids)
            consumed_aim_ids = aim_history.consumed_aim_follow_up_ids
        round_state = next_hero_round(round_state, spatial)
        spatial = start_next_spatial_round(spatial)
        reserved = reserve_action(round_state, CombatActionDeclaration(CombatActionKind.ATTACK))
        attack = attack_execution_request(state=reserved, target_id="guard", attacker_profile=TestProfile(2, 5))
        kernel = attack.kernel_request
        target = shot.ranged_attack.attack.resolution.target_state
        attack = replace(attack, id="attack:second", kernel_request=replace(
            kernel, id="kernel:second", target_state=target, attack=replace(
                kernel.attack, id="attack-request:second",
                attacker_test=replace(kernel.attack.attacker_test, id="attack-test:second"),
                impact_spec=replace(kernel.attack.impact_spec, resilience=ResilienceProfile(20)),
            )))
        candidate = replace(preparation_request(
            RangedWeaponId.CROSSBOW, attack=attack, next_cycle="hero:reload:2",
        ), id="prepare:second", weapon_state=weapon)
        if aim_history is None:
            preparation = prepare_ranged_weapon_attack(candidate)
        else:
            before_history = deepcopy(aim_history)
            # Renaming preparation also renames its generated follow-up; source history must still block it.
            expired = replace(candidate, id="prepare:expired-aim:new-id", aim=lost_aim.source_request.aim)
            with patch("towr.rules.ranged_weapon_attack_preparation.prepare_ranged_weapon_attack") as prepare:
                with self.assertRaisesRegex(ValueError, "source was already consumed"):
                    prepare_ranged_weapon_attack_with_aim_history(aim_history, expired)
            prepare.assert_not_called()
            preparation = prepare_ranged_weapon_attack_with_aim_history(aim_history, candidate)
            self.assertEqual(aim_history, before_history)
        self.assertIs(preparation.source_request.weapon_state, reloaded.state)
        self.assertIs(preparation.execution.attack.kernel_request.target_state, target)
        self.assertIsNone(preparation.aim_follow_up)
        self.assertFalse(any(modifier.rule_id == AIM_FOLLOW_UP_RULE_ID
                             for modifier in preparation.execution.attack.kernel_request.attack.attacker_test.dice_modifiers))
        if lost_aim is not None:
            with self.assertRaisesRegex(ValueError, "Aim bonus was not applied"):
                AimRangedWeaponAttackExecutionRequest(
                    "aim:invalid-reuse", lost_aim, preparation.execution, consumed_aim_follow_up_ids=consumed_aim_ids)
        prepared = PreparedHiddenRangedAttackExecutionRequest(
            "prepared:hidden:second", hidden_request(
                move_quietly=hidden.active_move_quietly, attack=preparation.execution.attack,
                spatial_state=spatial, target_id="guard", hiding_position_id=hidden.opportunity.hiding_position_id,
                consumed=hidden.consumed_opportunity_ids,
            ), PreparedRangedWeaponAttackExecutionRequest(
                "prepared:second", preparation, consumed_aim_follow_up_ids=consumed_aim_ids),
        )
        registered = RegisteredHiddenAttackExecutionRequest("registered:second", hidden.hiding_positions, prepared)
        rng = SequenceRandom([1 if second_hit else 10, 10, 7])
        with patch("towr.rules.hiding_position_resolution.execute_prepared_hidden_ranged_attack",
                   wraps=execute_prepared_hidden_ranged_attack) as execute:
            final = lifecycle.execute_hidden_lifecycle_attack(hidden, registered, rng)
        execute.assert_called_once_with(prepared, rng, decisions=None)
        self.assertEqual(rng.randint(1, 10), 7)
        second_shot = final.completed.execution
        self.assertEqual(second_shot.ranged_attack.attack.resolution.attack.outcome,
                         AttackOutcome.HIT if second_hit else AttackOutcome.MISS)
        self.assertIsNone(second_shot.ranged_attack.attack.resolution.attack.defender_test)
        self.assertFalse(second_shot.ranged_attack.weapon_state.loaded)
        self.assertEqual(second_shot.ranged_attack.weapon_state.reload_cycle_ids,
                         ("hero:reload:1", "hero:reload:2"))
        self.assertEqual(second_shot.ranged_attack.weapon_state.exacting.accumulated_successes, 0)
        self.assertEqual(second_shot.ranged_attack.weapon_state.exacting.contributions, ())
        self.assertEqual(second_shot.consumed_aim_follow_up_ids, consumed_aim_ids)
        self.assertEqual(final.state.consumed_opportunity_ids,
                         (*hidden.consumed_opportunity_ids, hidden.opportunity.id))
        self.assertEqual(final.state.hiding_positions.used_hiding_position_ids,
                         (*hidden.hiding_positions.used_hiding_position_ids, hidden.opportunity.hiding_position_id))
        self.assertEqual(final.state.hiding_positions.consumed_attack_execution_ids,
                         (*first.state.hiding_positions.consumed_attack_execution_ids, attack.id))
        self.assertIsNone(final.state.opportunity)
        slots = second_shot.ranged_attack.attack.state.active_turn.action_slots
        self.assertEqual(len(slots), 1)
        self.assertTrue(slots[0].executed)
        self.assertEqual(slots[0].execution.id, attack.id)
        self.assertTrue(set(preparation.applied_rule_ids) <= set(final.applied_rule_ids))
        self.assertTrue(set(hidden.active_move_quietly.applied_rule_ids) <= set(final.applied_rule_ids))
        self.assertTrue(weapon.loaded)
        self.assertEqual(first, before)
        replay_rng = Mock()
        with self.assertRaisesRegex(ValueError, "no active"):
            lifecycle.execute_hidden_lifecycle_attack(final.state, registered, replay_rng)
        self.assertEqual(replay_rng.mock_calls, [])

        return final

    def test_failed_recover_keeps_broken_and_completed_slot_without_restoring_opportunity(self):
        first, lost, fled, recovered = self.reach_recovery((10, 10))
        self.assertFalse(recovered.resolution.removed)
        self.assertTrue(recovered.resolution.conditions.has(Condition.BROKEN))
        self.assertTrue(recovered.slot.executed)
        self.assertFalse(has_enemy_in_zone(fled.state))
        self.assertIsNone(lost.state.opportunity)
        self.assertEqual(lost.state.consumed_opportunity_ids, ("hidden:older", first.state.opportunity.id))
        self.assertEqual(lost.state.hiding_positions.used_hiding_position_ids, ("hiding:older",))
