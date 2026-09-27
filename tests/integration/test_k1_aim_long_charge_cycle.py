from copy import deepcopy
from dataclasses import replace
from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.integration.test_k1_aim_target_switch import next_hero_round, pending_attack
from tests.unit.test_k1_aim_resolution import active_round, aim_request, reserve_action
from tests.unit.test_k1_charge_action_execution import (
    charge_declaration, reserve_action as reserve_charge,
)
from tests.unit.test_k1_long_charge_action_execution import graph, request as charge_request
from tests.unit.test_k1_ranged_weapon_attack_preparation import preparation_request
from towr.domain.aim_consumption_models import (
    AimConsumptionState, RegisteredAimLossLongChargeExecutionRequest, RegisteredAimRangedAttackExecutionRequest,
)
from towr.domain.aim_models import AimFollowUpOutcome, AimFollowUpRequest
from towr.domain.aim_ranged_weapon_attack_models import AimRangedWeaponAttackExecutionRequest
from towr.domain.attack_models import AttackOutcome, ResilienceProfile
from towr.domain.charge_models import LongChargeOutcome
from towr.domain.condition_models import Condition, ConditionApplicationRequest, ConditionState
from towr.domain.ranged_weapon_profiles import RangedWeaponId, RangedWeaponRange
from towr.domain.reload_models import create_initial_ranged_weapon_reload_state
from towr.domain.resolution_models import AttackerStaggerRequest
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement
from towr.domain.test_models import Skill, TestProfile, TestRequest
from towr.domain.turn_models import CombatActionKind
from towr.rules import aim_consumption_resolution as consumption
from towr.rules.aim_resolution import execute_aim_action, resolve_aim_follow_up
from towr.rules.condition_effect_resolution import resolve_condition_application
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.ranged_weapon_attack_preparation import (
    prepare_ranged_weapon_attack, prepare_ranged_weapon_attack_with_aim_history,
)
from towr.rules.spatial_resolution import start_next_spatial_round
from towr.rules.test_resolution import resolve_test


class K1AimLongChargeCycleTests(unittest.TestCase):
    skill = Skill.MELEE

    def test_reached_target_then_recover_fresh_aim_and_shot(self):
        self.check_cycle(LongChargeOutcome.REACHED_TARGET_AND_ATTACKED)

    def test_stopped_short_then_recover_fresh_aim_and_shot(self):
        self.check_cycle(LongChargeOutcome.STOPPED_SHORT_STAGGERED)

    def test_already_staggered_stopped_short_then_recover_fresh_aim_and_shot(self):
        self.check_cycle(LongChargeOutcome.STOPPED_SHORT_ALREADY_STAGGERED)

    def check_cycle(self, outcome):
        charge_bonus = int(self.skill is Skill.MELEE)
        reached = outcome is LongChargeOutcome.REACHED_TARGET_AND_ATTACKED
        already_staggered = outcome is LongChargeOutcome.STOPPED_SHORT_ALREADY_STAGGERED
        final_zone = "zone:c" if reached else "zone:b"
        for first_bonus, fresh_bonus, charge_hit, shot_hit in product(
            (0, 2), (0, 2), (False, True) if reached else (False,), (False, True),
        ):
            with self.subTest(first=first_bonus, fresh=fresh_bonus, charge_hit=charge_hit, shot_hit=shot_hit):
                spatial = SpatialBattleState(graph=graph(), placements=(
                    SpatialEntityPlacement("hero", "heroes", "zone:a"),
                    SpatialEntityPlacement("ally", "heroes", final_zone),
                    SpatialEntityPlacement("enemy", "enemies", "zone:c"),
                    SpatialEntityPlacement("enemy:other", "enemies", "zone:c"),
                ))
                initial_spatial = deepcopy(spatial)
                history = AimConsumptionState("hero")
                initial_history = history
                first = execute_aim_action(aim_request(reserve_action(active_round(), CombatActionKind.AIM)),
                    SequenceRandom([1] * first_bonus + [10] * (3 - first_bonus)))
                initial_conditions = ConditionState(frozenset({Condition.STAGGERED})) if already_staggered else ConditionState()
                turn, _, hero_conditions, before_charge_recoveries = next_hero_round(
                    first.round_state, spatial=spatial, hero_conditions=initial_conditions, recover_hero=False,
                )
                self.assertIs(hero_conditions, initial_conditions)
                self.assertTrue(all(not r.resolution.condition_changes for r in before_charge_recoveries))
                spatial = start_next_spatial_round(spatial)
                self.assertEqual(turn.round_number, spatial.round_number)
                charge = charge_request(round_state=reserve_charge(turn, charge_declaration()),
                    state=spatial, conditions=hero_conditions, attack_skill=self.skill)
                charge = replace(charge, kernel_request=replace(charge.kernel_request, attack=replace(
                    charge.kernel_request.attack, defender_test=TestRequest("defence:charge", TestProfile(1, 5)),
                    impact_spec=replace(charge.kernel_request.attack.impact_spec, resilience=ResilienceProfile(toughness=20)),
                )))
                lost = resolve_aim_follow_up(AimFollowUpRequest(
                    "follow:charge", first, "hero", charge.id, charge_declaration(),
                ))
                source = RegisteredAimLossLongChargeExecutionRequest("registered:charge", history, lost, charge)
                source_before = deepcopy(source)
                kernel = Mock(wraps=resolve_kernel_attack)
                with (
                    patch("towr.rules.charge_action_execution.resolve_kernel_attack", kernel),
                    patch("towr.rules.attack_action_execution.resolve_kernel_attack", kernel),
                    patch.object(consumption, "register_aim_ranged_attack",
                                 wraps=consumption.register_aim_ranged_attack) as register_applied,
                    patch("towr.rules.charge_action_execution.resolve_test", wraps=resolve_test) as athletics,
                    patch("towr.rules.charge_action_execution.resolve_condition_application",
                          wraps=resolve_condition_application) as stagger,
                    patch.object(consumption, "consume_long_charge_lost_aim",
                                 wraps=consumption.consume_long_charge_lost_aim) as register,
                ):
                    rng = SequenceRandom([1, 1 if charge_hit else 10, *([10] * (1 + charge_bonus)), 7] if reached else [10, 7])
                    charged = consumption.execute_registered_aim_loss_long_charge(source, rng)
                    self.assertEqual(rng.randint(1, 10), 7)
                    self.assertEqual(kernel.call_count, int(reached))
                    self.assertIs(charged.registration.previous_state, history)
                    history, spatial = charged.state, charged.execution.spatial_state
                    self.assertEqual(spatial.placement_for("hero").zone_id, final_zone)
                    self.assertEqual(spatial.placement_for("ally").zone_id, final_zone)
                    self.assertEqual(spatial.placements[1:], source.charge.spatial_state.placements[1:])
                    self.assertIs(lost.outcome, AimFollowUpOutcome.LOST)
                    self.assertIs(charged.execution.outcome, outcome)
                    athletics.assert_called_once_with(charge.athletics_test, rng, decisions=None)
                    register.assert_called_once_with(charged.registration.source_request)
                    self.assertEqual(stagger.call_count, int(not reached))
                    self.assertEqual(charged.execution.athletics_test_result.succeeded, reached)
                    self.assertEqual(len(charged.execution.round_state.active_turn.action_slots), 1)
                    self.assertTrue(charged.execution.slot.executed)
                    self.assertEqual(charged.execution.slot.execution.id, charge.id)
                    self.assertEqual(charged.execution.slot.execution.result_request_id,
                                     charged.execution.resolution.request_id if reached else charge.id)
                    self.assertIs(charged.execution.previous_conditions, hero_conditions)
                    hero_conditions = charged.execution.conditions
                    if reached:
                        target = charged.execution.resolution.target_state
                        self.assertIsNone(charged.execution.stagger_application)
                        if self.skill is Skill.BRAWN:
                            self.assertIsNone(charged.execution.melee_bonus)
                            self.assertIs(charged.execution.kernel_request, charge.kernel_request)
                    else:
                        target = charged.execution.source_kernel_request.target_state
                        self.assertIsNone(charged.execution.resolution)
                        self.assertIsNone(charged.execution.melee_bonus)
                        self.assertEqual(charged.execution.stagger_application.was_already_present, already_staggered)
                        self.assertTrue(hero_conditions.has(Condition.STAGGERED))
                        self.assertEqual(charged.execution.kernel_request, charge.kernel_request)
                    if reached and not charge_hit:
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
                    # Keep the actual final range: Close on success, one Zone away after stopping short.
                    attack = replace(attack, kernel_request=replace(attack.kernel_request, target_state=target,
                        attack=replace(attack.kernel_request.attack, is_close_range=charged.execution.target_in_close_range,
                            attacker_is_staggered=hero_conditions.has(Condition.STAGGERED),
                            defender_test=TestRequest("defence:fresh", TestProfile(1, 5)))))
                    self.assertIs(attack.kernel_request.target_state, target)
                    close = charged.execution.target_in_close_range
                    self.assertEqual(close, reached)
                    actor_zone = spatial.placement_for("hero").zone_id
                    target_zone = spatial.placement_for("enemy").zone_id
                    if close:
                        self.assertEqual(actor_zone, target_zone)
                    else:
                        self.assertTrue(spatial.graph.are_adjacent(actor_zone, target_zone))
                    weapon_id = RangedWeaponId.PISTOL if close else RangedWeaponId.LONGBOW
                    weapon = create_initial_ranged_weapon_reload_state("hero:weapon", weapon_id)
                    candidate = replace(preparation_request(weapon_id, attack=attack, aim=fresh,
                        target_range=RangedWeaponRange.CLOSE if close else RangedWeaponRange.MEDIUM,
                        lore=close, has_close_enemy=close,
                        next_cycle="pistol:reload:1" if close else None), weapon_state=weapon)
                    if close:
                        with self.assertRaises(ValueError):
                            prepare_ranged_weapon_attack_with_aim_history(history, replace(candidate,
                                weapon_state=create_initial_ranged_weapon_reload_state("hero:bow", RangedWeaponId.LONGBOW),
                                next_reload_cycle_id=None))
                        with self.assertRaises(ValueError):
                            prepare_ranged_weapon_attack_with_aim_history(history, replace(candidate, has_blackpowder_lore=False))
                    stale_preparation = prepare_ranged_weapon_attack(replace(candidate, id="prepare:renamed", aim=first))
                    stale = AimRangedWeaponAttackExecutionRequest("shot:renamed", stale_preparation.aim_follow_up,
                        stale_preparation.execution, history.consumed_aim_follow_up_ids)
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
                                candidate, aim=first, id="prepare:renamed"))
                    prepare.assert_not_called()
                    with patch.object(consumption, "execute_long_charge_action") as execute:
                        with self.assertRaisesRegex(ValueError, "source was already consumed"):
                            renamed_charge = replace(charge, id="charge:renamed",
                                athletics_test=replace(charge.athletics_test, id="athletics:renamed"),
                                kernel_request=replace(charge.kernel_request, id="kernel:renamed"))
                            renamed_follow = resolve_aim_follow_up(replace(lost.source_request,
                                id="follow:renamed", next_action_id=renamed_charge.id))
                            consumption.execute_registered_aim_loss_long_charge(RegisteredAimLossLongChargeExecutionRequest(
                                "registered:replay", history, renamed_follow, renamed_charge), rejected_rng)
                    execute.assert_not_called()
                    self.assertEqual(rejected_rng.mock_calls, [])
                    self.assertEqual(kernel.call_count, int(reached))
                    preparation = prepare_ranged_weapon_attack_with_aim_history(history, candidate)
                    self.assertIs(preparation.execution.attack.kernel_request.target_state, target)
                    shot = AimRangedWeaponAttackExecutionRequest("shot:fresh", preparation.aim_follow_up,
                        preparation.execution, history.consumed_aim_follow_up_ids)
                    rng = SequenceRandom([1 if shot_hit else 10, *([10] * (3 + fresh_bonus)), 7])
                    applied = consumption.execute_registered_aim_ranged_attack(
                        RegisteredAimRangedAttackExecutionRequest("registered:fresh", history, shot), rng)
                    self.assertEqual(rng.randint(1, 10), 7)
                    self.assertEqual(kernel.call_count, int(reached) + 1)
                    athletics.assert_called_once()
                    register.assert_called_once()
                    self.assertEqual(stagger.call_count, int(not reached))
                    register_applied.assert_called_once_with(applied.registration.source_request)
                final = applied.execution.ranged_attack.attack
                self.assertIs(applied.registration.previous_state, charged.state)
                self.assertEqual(applied.state.consumed_aim_source_ids, (first.request_id, fresh.request_id))
                self.assertEqual(applied.state.consumed_aim_follow_up_ids, (lost.request_id, shot.aim_follow_up.request_id))
                self.assertEqual(applied.execution.consumed_aim_follow_up_ids, applied.state.consumed_aim_follow_up_ids)
                self.assertEqual((first.round_state.round_number, charged.execution.round_state.round_number,
                                  fresh.round_state.round_number, final.state.round_number), (1, 2, 3, 4))
                executions = [(final, final.state, shot_hit, 3 + fresh_bonus, fresh_bonus)]
                if reached:
                    executions.append((charged.execution, charged.execution.round_state, charge_hit,
                                       1 + charge_bonus, charge_bonus))
                for execution, state, hit, dice, bonus in executions:
                    self.assertIs(execution.resolution.attack.outcome, AttackOutcome.HIT if hit else AttackOutcome.MISS)
                    self.assertEqual(execution.resolution.attack.attacker_test.trace.rolled_dice, dice)
                    self.assertEqual(execution.resolution.attack.attacker_test.trace.regular_dice_delta, bonus)
                    self.assertEqual(len(state.active_turn.action_slots), 1)
                    self.assertTrue(execution.slot.executed)
                    self.assertEqual(execution.slot.execution.id, execution.request_id)
                self.assertEqual(final.resolution.target_state.conditions.has(Condition.STAGGERED), shot_hit)
                self.assertEqual(final.resolution.follow_ups, () if shot_hit or not reached else (AttackerStaggerRequest(attack.kernel_request.attack.id),))
                self.assertEqual(source, source_before)
                self.assertEqual(initial_history, AimConsumptionState("hero"))
                self.assertEqual(source.charge.spatial_state.placements, initial_spatial.placements)
                self.assertEqual(history.consumed_aim_source_ids, (first.request_id,))
                self.assertIs(applied.execution.ranged_attack.source_request, preparation.execution)
                if reached:
                    self.assertTrue(weapon.loaded)
                    self.assertFalse(applied.execution.ranged_attack.weapon_state.loaded)
                    self.assertEqual(applied.execution.ranged_attack.weapon_state.reload_cycle_ids, ("pistol:reload:1",))
                    self.assertEqual(applied.execution.ranged_attack.weapon_state.exacting.accumulated_successes, 0)
                else:
                    self.assertIs(applied.execution.ranged_attack.weapon_state, weapon)
                    self.assertIs(preparation.source_request.target_range, RangedWeaponRange.MEDIUM)
                    self.assertFalse(preparation.source_request.has_enemy_in_close_range)
                self.assertTrue(set(charged.registration.applied_rule_ids) <= set(charged.applied_rule_ids))
                self.assertTrue(set(applied.registration.applied_rule_ids) <= set(applied.applied_rule_ids))


class K1AimLongBrawnChargeCycleTests(K1AimLongChargeCycleTests):
    skill = Skill.BRAWN


if __name__ == "__main__":
    unittest.main()
