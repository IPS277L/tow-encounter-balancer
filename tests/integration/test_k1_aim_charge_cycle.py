from copy import deepcopy
from dataclasses import replace
from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.integration.test_k1_aim_target_switch import aimed_shot, next_hero_round, pending_attack
from tests.unit.test_k1_aim_resolution import active_round, aim_request, reserve_action
from tests.unit.test_k1_charge_action_execution import (
    charge_declaration, graph, request as charge_request, reserve_action as reserve_charge,
)
from tests.unit.test_k1_ranged_weapon_attack_preparation import preparation_request
from towr.domain.aim_consumption_models import (
    AimConsumptionState, RegisteredAimLossChargeExecutionRequest, RegisteredAimRangedAttackExecutionRequest,
)
from towr.domain.aim_models import AimFollowUpOutcome, AimFollowUpRequest
from towr.domain.attack_models import AttackOutcome, ResilienceProfile
from towr.domain.condition_models import Condition, ConditionApplicationRequest, ConditionState
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.reload_models import create_initial_ranged_weapon_reload_state
from towr.domain.resolution_models import AttackerStaggerRequest
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement
from towr.domain.test_models import TestProfile, TestRequest
from towr.domain.turn_models import CombatActionKind
from towr.rules import aim_consumption_resolution as consumption
from towr.rules.aim_resolution import execute_aim_action, resolve_aim_follow_up
from towr.rules.condition_effect_resolution import resolve_condition_application
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack_with_aim_history
from towr.rules.spatial_resolution import start_next_spatial_round


class K1AimChargeCycleTests(unittest.TestCase):
    def test_aim_charge_lost_recover_fresh_aim_and_shot_carry_states_across_rounds(self):
        for first_bonus, fresh_bonus, charge_hit, shot_hit in product((0, 2), (0, 2), (False, True), (False, True)):
            with self.subTest(first=first_bonus, fresh=fresh_bonus, charge_hit=charge_hit, shot_hit=shot_hit):
                spatial = SpatialBattleState(graph=graph(), placements=(
                    SpatialEntityPlacement("hero", "heroes", "zone:a"),
                    SpatialEntityPlacement("ally", "heroes", "zone:b"),
                    SpatialEntityPlacement("enemy", "enemies", "zone:b"),
                    SpatialEntityPlacement("enemy:other", "enemies", "zone:c"),
                ))
                initial_spatial = deepcopy(spatial)
                history = AimConsumptionState("hero")
                first = execute_aim_action(aim_request(reserve_action(active_round(), CombatActionKind.AIM)),
                    SequenceRandom([1] * first_bonus + [10] * (3 - first_bonus)))
                turn, _, _, _ = next_hero_round(first.round_state, spatial=spatial)
                spatial = start_next_spatial_round(spatial)
                self.assertEqual(turn.round_number, spatial.round_number)
                charge = charge_request(round_state=reserve_charge(turn, charge_declaration()), state=spatial)
                charge = replace(charge, kernel_request=replace(charge.kernel_request, attack=replace(
                    charge.kernel_request.attack, defender_test=TestRequest("defence:charge", TestProfile(1, 5)),
                    impact_spec=replace(charge.kernel_request.attack.impact_spec, resilience=ResilienceProfile(toughness=20)),
                )))
                lost = resolve_aim_follow_up(AimFollowUpRequest(
                    "follow:charge", first, "hero", charge.id, charge_declaration(),
                ))
                source = RegisteredAimLossChargeExecutionRequest("registered:charge", history, lost, charge)
                source_before = deepcopy(source)
                kernel = Mock(wraps=resolve_kernel_attack)
                with (
                    patch("towr.rules.charge_action_execution.resolve_kernel_attack", kernel),
                    patch("towr.rules.attack_action_execution.resolve_kernel_attack", kernel),
                ):
                    rng = SequenceRandom([1 if charge_hit else 10, 10, 10, 7])
                    charged = consumption.execute_registered_aim_loss_charge(source, rng)
                    self.assertEqual(rng.randint(1, 10), 7)
                    kernel.assert_called_once()
                    self.assertIs(charged.registration.previous_state, history)
                    history, spatial = charged.state, charged.execution.spatial_state
                    self.assertEqual(spatial.placement_for("hero").zone_id, "zone:b")
                    self.assertEqual(spatial.placement_for("ally").zone_id, "zone:b")
                    self.assertEqual(spatial.placements[1:], source.charge.spatial_state.placements[1:])
                    self.assertIs(lost.outcome, AimFollowUpOutcome.LOST)
                    target = charged.execution.resolution.target_state
                    hero_conditions = ConditionState()
                    if not charge_hit:
                        follow, = charged.execution.resolution.follow_ups
                        self.assertEqual(follow, AttackerStaggerRequest(charge.kernel_request.attack.id))
                        hero_conditions = resolve_condition_application(ConditionApplicationRequest(
                            f"{follow.attack_id}:stagger", hero_conditions, Condition.STAGGERED, follow.rule_id,
                        )).state
                    turn, target_conditions, hero_conditions, recoveries = next_hero_round(
                        charged.execution.round_state, target.conditions, target_id="enemy",
                        hero_conditions=hero_conditions, spatial=spatial,
                    )
                    target_recovery = next(r for r in recoveries if r.source_request.actor_id == "enemy")
                    self.assertIs(target_recovery.source_request.actor_conditions, target.conditions)
                    changes = tuple(c for r in recoveries for c in r.resolution.condition_changes)
                    self.assertEqual(tuple(c.entity_id for c in changes), ("enemy",) if charge_hit else ("hero",))
                    self.assertEqual(changes[0].removed_conditions, (Condition.STAGGERED,))
                    self.assertTrue(changes[0].previous_conditions.has(Condition.STAGGERED))
                    self.assertEqual(hero_conditions, ConditionState())
                    target = replace(target, conditions=target_conditions)
                    spatial = start_next_spatial_round(spatial)
                    self.assertEqual(turn.round_number, spatial.round_number)
                    fresh_request = aim_request(reserve_action(turn, CombatActionKind.AIM))
                    fresh = execute_aim_action(replace(fresh_request, id="aim:fresh",
                        awareness_test=replace(fresh_request.awareness_test, id="awareness:fresh")),
                        SequenceRandom([1] * fresh_bonus + [10] * (3 - fresh_bonus)))
                    turn, unchanged_target, hero_conditions, idle_recoveries = next_hero_round(
                        fresh.round_state, target.conditions, target_id="enemy", hero_conditions=hero_conditions, spatial=spatial,
                    )
                    self.assertIs(unchanged_target, target.conditions)
                    self.assertTrue(all(not r.resolution.condition_changes for r in idle_recoveries))
                    spatial = start_next_spatial_round(spatial)
                    self.assertEqual(turn.round_number, spatial.round_number)
                    self.assertEqual(spatial.placements, charged.execution.spatial_state.placements)
                    attack = pending_attack(turn, "enemy", "attack:fresh")
                    # Charge established Close Range; no actor moved afterwards.
                    attack = replace(attack, kernel_request=replace(attack.kernel_request, target_state=target,
                        attack=replace(attack.kernel_request.attack, is_close_range=charged.execution.target_in_close_range,
                            attacker_is_staggered=hero_conditions.has(Condition.STAGGERED),
                            defender_test=TestRequest("defence:fresh", TestProfile(1, 5)))))
                    self.assertIs(attack.kernel_request.target_state, target)
                    weapon = create_initial_ranged_weapon_reload_state("hero:bow", RangedWeaponId.LONGBOW)
                    stale = aimed_shot(first, attack, history, weapon, "shot:renamed")
                    rejected_rng = Mock()
                    with patch.object(consumption, "execute_aim_ranged_weapon_attack") as execute:
                        with self.assertRaisesRegex(ValueError, "source was already consumed"):
                            consumption.execute_registered_aim_ranged_attack(
                                RegisteredAimRangedAttackExecutionRequest("registered:renamed", history, stale), rejected_rng,
                            )
                    execute.assert_not_called()
                    self.assertEqual(rejected_rng.mock_calls, [])
                    with patch("towr.rules.ranged_weapon_attack_preparation.prepare_ranged_weapon_attack") as prepare:
                        with self.assertRaisesRegex(ValueError, "source was already consumed"):
                            prepare_ranged_weapon_attack_with_aim_history(history, replace(
                                preparation_request(RangedWeaponId.LONGBOW, attack=attack, aim=first), id="prepare:renamed"))
                    prepare.assert_not_called()
                    with patch.object(consumption, "execute_charge_action") as execute:
                        with self.assertRaisesRegex(ValueError, "source was already consumed"):
                            renamed_charge = replace(charge, id="charge:renamed")
                            renamed_follow = resolve_aim_follow_up(replace(lost.source_request,
                                id="follow:renamed", next_action_id=renamed_charge.id))
                            consumption.execute_registered_aim_loss_charge(RegisteredAimLossChargeExecutionRequest(
                                "registered:replay", history, renamed_follow, renamed_charge), rejected_rng)
                    execute.assert_not_called()
                    self.assertEqual(rejected_rng.mock_calls, [])
                    kernel.assert_called_once()
                    shot = aimed_shot(fresh, attack, history, weapon, "shot:fresh")
                    rng = SequenceRandom([1 if shot_hit else 10, *([10] * (3 + fresh_bonus)), 7])
                    applied = consumption.execute_registered_aim_ranged_attack(
                        RegisteredAimRangedAttackExecutionRequest("registered:fresh", history, shot), rng)
                    self.assertEqual(rng.randint(1, 10), 7)
                    self.assertEqual(kernel.call_count, 2)
                final = applied.execution.ranged_attack.attack
                self.assertIs(applied.registration.previous_state, charged.state)
                self.assertEqual(applied.state.consumed_aim_source_ids, (first.request_id, fresh.request_id))
                self.assertEqual(applied.state.consumed_aim_follow_up_ids, (lost.request_id, shot.aim_follow_up.request_id))
                self.assertEqual(applied.execution.consumed_aim_follow_up_ids, applied.state.consumed_aim_follow_up_ids)
                self.assertEqual((first.round_state.round_number, charged.execution.round_state.round_number,
                                  fresh.round_state.round_number, final.state.round_number), (1, 2, 3, 4))
                for execution, state, hit, dice, bonus in (
                    (charged.execution, charged.execution.round_state, charge_hit, 2, 1),
                    (final, final.state, shot_hit, 3 + fresh_bonus, fresh_bonus),
                ):
                    self.assertIs(execution.resolution.attack.outcome, AttackOutcome.HIT if hit else AttackOutcome.MISS)
                    self.assertEqual(execution.resolution.attack.attacker_test.trace.rolled_dice, dice)
                    self.assertEqual(execution.resolution.attack.attacker_test.trace.regular_dice_delta, bonus)
                    self.assertEqual(len(state.active_turn.action_slots), 1)
                    self.assertTrue(execution.slot.executed)
                    self.assertEqual(execution.slot.execution.id, execution.request_id)
                self.assertEqual(final.resolution.target_state.conditions.has(Condition.STAGGERED), shot_hit)
                self.assertEqual(final.resolution.follow_ups, () if shot_hit else (AttackerStaggerRequest(attack.kernel_request.attack.id),))
                self.assertEqual(source, source_before)
                self.assertEqual(source.charge.spatial_state.placements, initial_spatial.placements)
                self.assertEqual(history.consumed_aim_source_ids, (first.request_id,))
                self.assertIs(applied.execution.ranged_attack.weapon_state, weapon)
                self.assertTrue(set(charged.registration.applied_rule_ids) <= set(charged.applied_rule_ids))
                self.assertTrue(set(applied.registration.applied_rule_ids) <= set(applied.applied_rule_ids))


if __name__ == "__main__":
    unittest.main()
