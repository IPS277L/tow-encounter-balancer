from copy import deepcopy
from dataclasses import replace
from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.integration.test_k1_aim_target_switch import follow_up, next_hero_round, pending_attack
from tests.unit.test_k1_aim_resolution import active_round, aim_request, reserve_action
from tests.unit.test_k1_ranged_weapon_attack_preparation import preparation_request
from towr.domain.aim_consumption_models import (
    AimConsumptionState, RegisteredAimLossRangedAttackExecutionRequest,
    RegisteredAimRangedAttackExecutionRequest, RegisteredAimLossPreparedAttackExecutionRequest,
    RegisteredPreparedAimRangedAttackExecutionRequest,
)
from towr.domain.aim_models import AimFollowUpOutcome
from towr.domain.aim_ranged_weapon_attack_models import AimRangedWeaponAttackExecutionRequest
from towr.domain.attack_models import AttackOutcome
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.prepared_ranged_weapon_attack_models import PreparedRangedWeaponAttackExecutionRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.reload_models import (
    ReloadActionExecutionRequest, create_initial_ranged_weapon_reload_state, reload_approach_id,
)
from towr.domain.test_models import TestProfile, TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind,
    CombatActionSlotRequest, ImproviseKind,
)
from towr.rules import aim_consumption_resolution as consumption
from towr.rules.aim_resolution import execute_aim_action
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.ranged_weapon_attack_preparation import (
    prepare_ranged_weapon_attack, prepare_ranged_weapon_attack_with_aim_history,
)
from towr.rules.reload_resolution import execute_reload_action
from towr.rules.turn_resolution import reserve_combat_action_slot


def opposed_attack(turn, target, identifier):
    attack = pending_attack(turn, target, identifier)
    return replace(attack, kernel_request=replace(attack.kernel_request,
        attack=replace(attack.kernel_request.attack,
            defender_test=TestRequest(f"{identifier}:defence", TestProfile(1, 5)))))


def prepared_request(weapon, attack, aim, identifier, cycle):
    return replace(preparation_request(weapon.weapon_id, attack=attack, aim=aim,
        next_cycle=cycle if weapon.weapon_id is RangedWeaponId.CROSSBOW else None),
        id=identifier, weapon_state=weapon)


def applied_shot(prepared, history, identifier):
    return AimRangedWeaponAttackExecutionRequest(
        identifier, prepared.aim_follow_up, prepared.execution, history.consumed_aim_follow_up_ids,
    )


def registered_loss_request(preparation, history, follow, identifier, *, prepared_mode):
    if prepared_mode:
        return RegisteredAimLossPreparedAttackExecutionRequest(identifier, history, follow,
            PreparedRangedWeaponAttackExecutionRequest(f"{identifier}:prepared", preparation,
                history.consumed_aim_follow_up_ids))
    return RegisteredAimLossRangedAttackExecutionRequest(identifier, history, follow, preparation.execution)


def registered_applied_request(preparation, history, identifier, *, prepared_mode):
    if prepared_mode:
        return RegisteredPreparedAimRangedAttackExecutionRequest(identifier, history,
            PreparedRangedWeaponAttackExecutionRequest(f"{identifier}:prepared", preparation,
                history.consumed_aim_follow_up_ids))
    return RegisteredAimRangedAttackExecutionRequest(identifier, history,
        applied_shot(preparation, history, f"{identifier}:aim"))


class K1AimRangedAttackCycleTests(unittest.TestCase):
    def test_longbow_lost_then_fresh_aim_applied(self):
        self.check_cycle(RangedWeaponId.LONGBOW)

    def test_crossbow_lost_reload_then_fresh_aim_applied(self):
        self.check_cycle(RangedWeaponId.CROSSBOW)

    def test_prepared_longbow_lost_then_fresh_aim_applied(self):
        self.check_cycle(RangedWeaponId.LONGBOW, prepared_mode=True)

    def test_prepared_crossbow_lost_reload_then_fresh_aim_applied(self):
        self.check_cycle(RangedWeaponId.CROSSBOW, prepared_mode=True)

    def check_cycle(self, weapon_id, *, prepared_mode=False):
        execute_loss = consumption.execute_registered_aim_loss_prepared_attack if prepared_mode else consumption.execute_registered_aim_loss_ranged_attack
        execute_applied = consumption.execute_registered_prepared_aim_ranged_attack if prepared_mode else consumption.execute_registered_aim_ranged_attack
        loss_consumer = "consume_prepared_attack_lost_aim" if prepared_mode else "consume_ranged_attack_lost_aim"
        loss_executor = "execute_prepared_ranged_weapon_attack" if prepared_mode else "execute_ranged_weapon_attack"
        applied_executor = "execute_prepared_ranged_weapon_attack" if prepared_mode else "execute_aim_ranged_weapon_attack"
        for first_bonus, fresh_bonus, first_hit, second_hit in product((0, 2), (0, 2), (False, True), (False, True)):
            with self.subTest(prepared=prepared_mode, weapon=weapon_id, first_bonus=first_bonus, fresh_bonus=fresh_bonus,
                              first_hit=first_hit, second_hit=second_hit):
                history = AimConsumptionState("hero")
                weapon = create_initial_ranged_weapon_reload_state("hero:weapon", weapon_id)
                initial = deepcopy((history, weapon))
                first = execute_aim_action(aim_request(reserve_action(active_round(), CombatActionKind.AIM)),
                    SequenceRandom([1] * first_bonus + [10] * (3 - first_bonus)))
                first_before = deepcopy(first)
                turn, _, hero_conditions, _ = next_hero_round(first.round_state)
                attack_b = opposed_attack(turn, "enemy:other", "attack:B")
                prepared_b = prepare_ranged_weapon_attack_with_aim_history(history,
                    prepared_request(weapon, attack_b, None, "prepare:B", "reload:1"))
                lost_follow = follow_up(first, prepared_b.execution.attack, "follow:lost")
                self.assertIs(lost_follow.outcome, AimFollowUpOutcome.LOST)
                self.assertIsNone(lost_follow.modifier)
                source = registered_loss_request(prepared_b, history, lost_follow, "registered:B", prepared_mode=prepared_mode)
                source_before = deepcopy(source)
                with (
                    patch("towr.rules.attack_action_execution.resolve_kernel_attack", wraps=resolve_kernel_attack) as kernel,
                    patch.object(consumption, loss_consumer, wraps=getattr(consumption, loss_consumer)) as register_lost,
                    patch.object(consumption, "register_aim_ranged_attack", wraps=consumption.register_aim_ranged_attack) as register_applied,
                    patch.object(consumption, "execute_prepared_ranged_weapon_attack", wraps=consumption.execute_prepared_ranged_weapon_attack) as execute_prepared,
                ):
                    rng_b = SequenceRandom([1 if first_hit else 10, 10, 10, 1, 7])
                    lost = execute_loss(source, rng_b)
                    first_ranged = lost.execution.ranged_attack if prepared_mode else lost.execution
                    self.assertEqual(rng_b.randint(1, 10), 7)
                    kernel.assert_called_once()
                    register_lost.assert_called_once_with(lost.registration.source_request)
                    self.assertIs(lost.registration.previous_state, history)
                    history, weapon = lost.state, first_ranged.weapon_state
                    lost_before = deepcopy(lost)
                    target_b = first_ranged.attack.resolution.target_state
                    turn, conditions_b, hero_conditions, recoveries = next_hero_round(
                        first_ranged.attack.state, target_b.conditions, hero_conditions=hero_conditions)
                    target_recovery = next(r for r in recoveries if r.source_request.actor_id == "enemy:other")
                    self.assertIs(target_recovery.source_request.actor_conditions, target_b.conditions)
                    self.assertEqual(len(target_recovery.resolution.condition_changes), int(first_hit))
                    self.assertEqual(conditions_b, ConditionState())
                    target_b = replace(target_b, conditions=conditions_b)
                    reloads = []
                    if weapon_id is RangedWeaponId.CROSSBOW:
                        self.assertFalse(weapon.loaded)
                        self.assertEqual(weapon.reload_cycle_ids, ("reload:1",))
                        for index, (values, successes) in enumerate((((10, 10), 0), ((1, 10), 1), ((1, 10), 2))):
                            preview = opposed_attack(turn, "enemy", f"attack:unloaded:{index}")
                            with self.assertRaisesRegex(ValueError, "loaded"):
                                prepare_ranged_weapon_attack_with_aim_history(history,
                                    prepared_request(weapon, preview, None, f"prepare:unloaded:{index}", "reload:2"))
                            self.assertEqual(turn.active_turn.action_slots, ())
                            reserved = reserve_combat_action_slot(CombatActionSlotRequest(
                                f"slot:reload:{index}", turn, "hero", CombatActionDeclaration(
                                    CombatActionKind.IMPROVISE, improvise_kind=ImproviseKind.SKILL,
                                    improvise_approach_id=reload_approach_id(weapon.weapon_instance_id)),
                                ActionSlotGrant.STANDARD)).state
                            reload_request = ReloadActionExecutionRequest(
                                f"reload:action:{index}", reserved, "hero", hero_conditions, 1, weapon,
                                TestRequest(f"reload:dexterity:{index}", TestProfile(2, 5)))
                            rng = SequenceRandom([*values, 7])
                            reloaded = execute_reload_action(reload_request, rng)
                            reloads.append(reloaded)
                            self.assertEqual(rng.randint(1, 10), 7)
                            self.assertIs(reloaded.previous_state, weapon)
                            self.assertEqual(reloaded.state.exacting.accumulated_successes, successes)
                            self.assertEqual(len(reloaded.state.exacting.contributions), index + 1)
                            self.assertEqual(reloaded.state.loaded, successes == 2)
                            self.assertEqual(reloaded.state.reload_cycle_ids, ("reload:1",))
                            self.assertEqual(reloaded.slot.execution.id, reload_request.id)
                            replay_rng = Mock()
                            with self.assertRaisesRegex(ValueError, "slot has already been executed"):
                                execute_reload_action(replace(reload_request, round_state=reloaded.round_state), replay_rng)
                            self.assertEqual(replay_rng.mock_calls, [])
                            weapon = reloaded.state
                            turn, conditions_b, hero_conditions, idle = next_hero_round(
                                reloaded.round_state, target_b.conditions, hero_conditions=hero_conditions)
                            self.assertIs(conditions_b, target_b.conditions)
                            self.assertTrue(all(not r.resolution.condition_changes for r in idle))
                            self.assertIs(history, lost.state)
                    else:
                        self.assertIs(weapon, prepared_b.execution.weapon_state)

                    fresh_request = aim_request(reserve_action(turn, CombatActionKind.AIM))
                    fresh = execute_aim_action(replace(fresh_request, id="aim:fresh",
                        awareness_test=replace(fresh_request.awareness_test, id="awareness:fresh")),
                        SequenceRandom([1] * fresh_bonus + [10] * (3 - fresh_bonus)))
                    turn, conditions_b, hero_conditions, _ = next_hero_round(
                        fresh.round_state, target_b.conditions, hero_conditions=hero_conditions)
                    self.assertIs(conditions_b, target_b.conditions)
                    attack_a = opposed_attack(turn, "enemy", "attack:A")
                    preparation_a = prepared_request(weapon, attack_a, fresh, "prepare:A", "reload:2")

                    # New IDs cannot revive the consumed source, even when bypassing history-aware preparation.
                    stale_preparation = replace(preparation_a, id="prepare:renamed", aim=first)
                    with patch("towr.rules.ranged_weapon_attack_preparation.prepare_ranged_weapon_attack") as prepare:
                        with self.assertRaisesRegex(ValueError, "source was already consumed"):
                            prepare_ranged_weapon_attack_with_aim_history(history, stale_preparation)
                    prepare.assert_not_called()
                    stale_applied = prepare_ranged_weapon_attack(stale_preparation)
                    rejected_rng, decisions = Mock(), Mock()
                    with patch.object(consumption, applied_executor) as execute:
                        with self.assertRaisesRegex(ValueError, "source was already consumed"):
                            execute_applied(registered_applied_request(stale_applied, history,
                                "registered:renamed", prepared_mode=prepared_mode), rejected_rng, decisions=decisions)
                    execute.assert_not_called()
                    stale_attack = opposed_attack(turn, "enemy:other", "attack:renamed:B")
                    stale_attack = replace(stale_attack, kernel_request=replace(stale_attack.kernel_request, target_state=target_b))
                    stale_lost = prepare_ranged_weapon_attack(prepared_request(
                        weapon, stale_attack, None, "prepare:renamed:B", "reload:renamed"))
                    stale_follow = follow_up(first, stale_lost.execution.attack, "follow:renamed:lost")
                    with patch.object(consumption, loss_executor) as execute:
                        with self.assertRaisesRegex(ValueError, "source was already consumed"):
                            execute_loss(registered_loss_request(stale_lost, history, stale_follow,
                                "registered:renamed:B", prepared_mode=prepared_mode), rejected_rng, decisions=decisions)
                    execute.assert_not_called()
                    self.assertEqual(rejected_rng.mock_calls, [])
                    self.assertEqual(decisions.mock_calls, [])
                    kernel.assert_called_once()

                    prepared_a = prepare_ranged_weapon_attack_with_aim_history(history, preparation_a)
                    self.assertIs(prepared_a.aim_follow_up.outcome, AimFollowUpOutcome.APPLIED_TO_RANGED_ATTACK)
                    rng_a = SequenceRandom([1 if second_hit else 10, *([10] * (2 + fresh_bonus)), 1, 7])
                    applied_source = registered_applied_request(prepared_a, history, "registered:A", prepared_mode=prepared_mode)
                    if prepared_mode:
                        self.assertEqual(applied_source.attack.consumed_aim_follow_up_ids, lost.state.consumed_aim_follow_up_ids)
                        with patch.object(consumption, applied_executor) as execute:
                            with self.assertRaisesRegex(ValueError, "stale consumed follow-up prefix"):
                                execute_applied(replace(applied_source,
                                    attack=replace(applied_source.attack, consumed_aim_follow_up_ids=())), rejected_rng)
                        execute.assert_not_called()
                        self.assertEqual(rejected_rng.mock_calls, [])
                    applied = execute_applied(applied_source, rng_a)
                    self.assertEqual(rng_a.randint(1, 10), 7)
                    self.assertEqual(kernel.call_count, 2)
                    self.assertEqual(kernel.call_args_list[0].args[0], prepared_b.execution.attack.kernel_request)
                    self.assertEqual(kernel.call_args_list[1].args[0], prepared_a.execution.attack.kernel_request)
                    register_applied.assert_called_once_with(applied.registration.source_request)
                    self.assertEqual(register_lost.call_count, 1)
                    self.assertEqual(execute_prepared.call_count, 2 if prepared_mode else 0)
                    if prepared_mode:
                        self.assertIs(execute_prepared.call_args_list[0].args[0], source.prepared_attack)
                        self.assertIs(execute_prepared.call_args_list[1].args[0], applied_source.attack)

                second = applied.execution.ranged_attack
                if prepared_mode:
                    self.assertIs(lost.execution.source_request, source.prepared_attack)
                    self.assertIs(lost.execution.source_request.preparation, prepared_b)
                    self.assertIs(applied.execution.source_request, applied_source.attack)
                    self.assertIs(applied.execution.source_request.preparation, prepared_a)
                    self.assertIs(applied.registration.source_request.execution, applied.execution.execution)
                    self.assertEqual(lost.execution.consumed_aim_follow_up_ids, source.state.consumed_aim_follow_up_ids)
                    self.assertNotEqual(lost.execution.consumed_aim_follow_up_ids, lost.state.consumed_aim_follow_up_ids)
                    for result, preparation in ((lost, prepared_b), (applied, prepared_a)):
                        self.assertTrue(set(preparation.applied_rule_ids) <= set(result.execution.applied_rule_ids))
                        self.assertTrue(set(result.execution.applied_rule_ids) <= set(result.applied_rule_ids))
                        self.assertEqual(len(result.applied_rule_ids), len(set(result.applied_rule_ids)))
                self.assertIs(second.previous_weapon_state, weapon)
                self.assertIs(applied.registration.previous_state, lost.state)
                self.assertEqual(applied.state.consumed_aim_source_ids, (first.request_id, fresh.request_id))
                self.assertEqual(applied.state.consumed_aim_follow_up_ids,
                    (lost_follow.request_id, prepared_a.aim_follow_up.request_id))
                self.assertEqual(applied.state.consumed_aim_follow_up_ids, applied.execution.consumed_aim_follow_up_ids)
                if weapon_id is RangedWeaponId.CROSSBOW:
                    self.assertEqual(second.weapon_state.reload_cycle_ids, ("reload:1", "reload:2"))
                    self.assertFalse(second.weapon_state.loaded)
                    self.assertEqual(second.weapon_state.exacting.accumulated_successes, 0)
                    self.assertEqual(len(second.weapon_state.exacting.contributions), 0)
                    self.assertEqual(tuple(r.round_state.round_number for r in reloads), (3, 4, 5))
                else:
                    self.assertIs(second.weapon_state, weapon)
                self.assertEqual((first.round_state.round_number, first_ranged.attack.state.round_number,
                    fresh.round_state.round_number, second.attack.state.round_number),
                    (1, 2, 6, 7) if reloads else (1, 2, 3, 4))
                for result, prepared, hit, bonus in (
                    (first_ranged, prepared_b, first_hit, 0), (second, prepared_a, second_hit, fresh_bonus),
                ):
                    attack = result.attack
                    self.assertIs(result.source_request, prepared.execution)
                    trace = attack.resolution.attack.attacker_test.trace
                    self.assertEqual(trace.rolled_dice, 3 + bonus)
                    self.assertEqual(trace.regular_dice_delta, bonus)
                    self.assertIs(attack.resolution.attack.outcome, AttackOutcome.HIT if hit else AttackOutcome.MISS)
                    self.assertEqual(attack.resolution.target_state.conditions.has(Condition.STAGGERED), hit)
                    self.assertEqual(attack.resolution.follow_ups, ())
                    self.assertEqual(len(attack.state.active_turn.action_slots), 1)
                    self.assertEqual(attack.slot.execution.id, prepared.execution.attack.id)
                    self.assertTrue(attack.slot.executed)
                    self.assertTrue(set(attack.applied_rule_ids) <= set(result.applied_rule_ids))
                _, recovered_a, _, recoveries = next_hero_round(second.attack.state,
                    second.attack.resolution.target_state.conditions, target_id="enemy", hero_conditions=hero_conditions)
                self.assertEqual(recovered_a, ConditionState())
                target_recovery = next(r for r in recoveries if r.source_request.actor_id == "enemy")
                self.assertIs(target_recovery.source_request.actor_conditions, second.attack.resolution.target_state.conditions)
                self.assertEqual(len(target_recovery.resolution.condition_changes), int(second_hit))
                self.assertEqual(first, first_before)
                self.assertEqual(source, source_before)
                self.assertEqual(lost, lost_before)
                self.assertEqual((source.state, prepared_b.execution.weapon_state), initial)
                self.assertTrue(set(lost.registration.applied_rule_ids) <= set(lost.applied_rule_ids))
                self.assertTrue(set(applied.registration.applied_rule_ids) <= set(applied.applied_rule_ids))
