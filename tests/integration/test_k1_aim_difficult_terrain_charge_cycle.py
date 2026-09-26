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
    AimConsumptionState, RegisteredAimLossDifficultTerrainChargeExecutionRequest, RegisteredAimRangedAttackExecutionRequest,
)
from towr.domain.aim_models import AimFollowUpOutcome, AimFollowUpRequest
from towr.domain.attack_models import AttackOutcome, ResilienceProfile
from towr.domain.condition_models import Condition, ConditionApplicationRequest, ConditionState
from tests.unit.test_k1_difficult_terrain_charge_action_execution import terrain_request
from tests.unit.test_k1_difficult_terrain_movement_integration import free_movement_request
from towr.domain.movement_models import DifficultTerrainFreeMovementRequest
from towr.rules.difficult_terrain_resolution import resolve_difficult_terrain_traversal
from towr.rules.free_movement_resolution import resolve_difficult_terrain_free_movement
from towr.rules.test_resolution import resolve_test
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.reload_models import create_initial_ranged_weapon_reload_state
from towr.domain.resolution_models import AttackerStaggerRequest
from towr.domain.spatial_models import SpatialBattleState, SpatialEntityPlacement, ZoneConnection
from towr.domain.test_models import TestProfile, TestRequest
from towr.domain.turn_models import CombatActionKind
from towr.rules import aim_consumption_resolution as consumption
from towr.rules.aim_resolution import execute_aim_action, resolve_aim_follow_up
from towr.rules.condition_effect_resolution import resolve_condition_application
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack_with_aim_history
from towr.rules.spatial_resolution import start_next_spatial_round


class K1AimDifficultTerrainChargeCycleTests(unittest.TestCase):
    def test_first_crossing_charge_recover_and_fresh_aim(self):
        self.check_cycle(repeated=False)

    def test_second_crossing_after_free_move_charge_recover_and_fresh_aim(self):
        self.check_cycle(repeated=True)

    def check_cycle(self, *, repeated):
        for first_bonus, fresh_bonus, charge_hit, shot_hit, terrain_roll in product(
            (0, 2), (0, 2), (False, True), (False, True), (1, 10),
        ):
            with self.subTest(first=first_bonus, fresh=fresh_bonus, charge_hit=charge_hit, shot_hit=shot_hit, terrain_roll=terrain_roll):
                zones = graph()
                zones = replace(zones, zone_ids=(*zones.zone_ids, "zone:approach"),
                                connections=(*zones.connections, ZoneConnection("zone:approach", "zone:a")))
                spatial = SpatialBattleState(graph=zones, placements=(
                    SpatialEntityPlacement("hero", "heroes", "zone:approach" if repeated else "zone:a"),
                    SpatialEntityPlacement("ally", "heroes", "zone:b"),
                    SpatialEntityPlacement("enemy", "enemies", "zone:b"),
                    SpatialEntityPlacement("enemy:other", "enemies", "zone:b"),
                ))
                initial_spatial = deepcopy(spatial)
                initial_state = spatial
                history = AimConsumptionState("hero")
                first = execute_aim_action(aim_request(reserve_action(active_round(), CombatActionKind.AIM)),
                    SequenceRandom([1] * first_bonus + [10] * (3 - first_bonus)))
                turn, _, _, _ = next_hero_round(first.round_state, spatial=spatial)
                spatial = start_next_spatial_round(spatial)
                self.assertEqual(turn.round_number, spatial.round_number)
                if repeated:
                    approach = replace(terrain_request(turn, spatial), id="terrain:approach",
                                       destination_zone_id="zone:a",
                                       athletics_test=TestRequest("athletics:approach", TestProfile(1, 5)))
                    approach_rng = SequenceRandom([1, 7])
                    crossed = resolve_difficult_terrain_traversal(approach, approach_rng)
                    self.assertEqual(approach_rng.randint(1, 10), 7)
                    free_move = replace(free_movement_request(turn, spatial), id="free:approach",
                                        traversed_zone_ids=("zone:a",))
                    moved = resolve_difficult_terrain_free_movement(DifficultTerrainFreeMovementRequest(
                        "consume:approach", free_move, crossed, crossed.state,
                    ))
                    spatial = moved.state
                    self.assertEqual(moved.conditions, ConditionState())
                    self.assertEqual(spatial.free_move_used_entity_ids, ("hero",))
                    self.assertEqual(spatial.difficult_terrain_tested_entity_ids, ("hero",))
                charge = replace(charge_request(round_state=reserve_charge(turn, charge_declaration()), state=spatial),
                                 crosses_difficult_terrain=True)
                charge = replace(charge, kernel_request=replace(charge.kernel_request, attack=replace(
                    charge.kernel_request.attack, defender_test=TestRequest("defence:charge", TestProfile(1, 5)),
                    impact_spec=replace(charge.kernel_request.attack.impact_spec, resilience=ResilienceProfile(toughness=20)),
                )))
                lost = resolve_aim_follow_up(AimFollowUpRequest(
                    "follow:charge", first, "hero", "execute:terrain-charge", charge_declaration(),
                ))
                source = RegisteredAimLossDifficultTerrainChargeExecutionRequest(
                    "registered:charge", history, lost, "execute:terrain-charge", charge,
                    terrain_request(charge.round_state, spatial),
                )
                source_before = deepcopy(source)
                kernel = Mock(wraps=resolve_kernel_attack)
                with (
                    patch("towr.rules.charge_action_execution.resolve_kernel_attack", kernel),
                    patch("towr.rules.attack_action_execution.resolve_kernel_attack", kernel),
                    patch.object(consumption, "resolve_difficult_terrain_traversal",
                                 wraps=consumption.resolve_difficult_terrain_traversal) as traverse,
                    patch("towr.rules.difficult_terrain_resolution.resolve_test", wraps=resolve_test) as athletics,
                    patch("towr.rules.difficult_terrain_resolution.resolve_condition_application",
                          wraps=resolve_condition_application) as prone,
                ):
                    rng = SequenceRandom([terrain_roll, 1 if charge_hit else 10, 10, 10, 7])
                    charged = consumption.execute_registered_aim_loss_difficult_terrain_charge(source, rng)
                    self.assertEqual(rng.randint(1, 10), 7)
                    kernel.assert_called_once()
                    traverse.assert_called_once_with(source.terrain, rng, decisions=None)
                    athletics.assert_called_once_with(source.terrain.athletics_test, rng, decisions=None)
                    self.assertEqual(prone.call_count, int(terrain_roll == 10))
                    self.assertIs(charged.registration.previous_state, history)
                    history, spatial = charged.state, charged.execution.spatial_state
                    self.assertEqual(spatial.placement_for("hero").zone_id, "zone:b")
                    self.assertEqual(spatial.placement_for("ally").zone_id, "zone:b")
                    self.assertEqual(spatial.placements[1:], source.charge.spatial_state.placements[1:])
                    self.assertIs(lost.outcome, AimFollowUpOutcome.LOST)
                    target = charged.execution.resolution.target_state
                    hero_conditions = charged.execution.conditions
                    self.assertEqual(hero_conditions.has(Condition.PRONE), terrain_roll == 10)
                    self.assertIs(hero_conditions, charged.execution.terrain_traversal.conditions)
                    self.assertEqual(spatial.difficult_terrain_tested_entity_ids, ("hero",))
                    self.assertEqual(spatial.free_move_used_entity_ids, ("hero",) if repeated else ())
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
                    expected_changes = {}
                    if not charge_hit or terrain_roll == 10:
                        expected_changes["hero"] = (
                            *((Condition.STAGGERED,) if not charge_hit else ()),
                            *((Condition.PRONE,) if terrain_roll == 10 else ()),
                        )
                    if charge_hit:
                        expected_changes["enemy"] = (Condition.STAGGERED,)
                    self.assertEqual({c.entity_id: c.removed_conditions for c in changes}, expected_changes)
                    for change in changes:
                        self.assertTrue(all(change.previous_conditions.has(c) for c in change.removed_conditions))
                    self.assertEqual(spatial.difficult_terrain_tested_entity_ids, ("hero",))
                    self.assertEqual(hero_conditions, ConditionState())
                    target = replace(target, conditions=target_conditions)
                    spatial = start_next_spatial_round(spatial)
                    self.assertEqual(spatial.difficult_terrain_tested_entity_ids, ())
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
                    self.assertEqual(spatial.difficult_terrain_tested_entity_ids, ())
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
                    with (
                        patch.object(consumption, "resolve_difficult_terrain_traversal") as replay_traversal,
                        patch.object(consumption, "execute_difficult_terrain_charge_action") as execute,
                    ):
                        with self.assertRaisesRegex(ValueError, "source was already consumed"):
                            renamed_charge = replace(charge, id="charge:renamed",
                                kernel_request=replace(charge.kernel_request, id="kernel:renamed"))
                            renamed_terrain = replace(source.terrain, id="terrain:renamed",
                                athletics_test=replace(source.terrain.athletics_test, id="athletics:renamed"))
                            renamed_follow = resolve_aim_follow_up(replace(lost.source_request,
                                id="follow:renamed", next_action_id="composite:renamed"))
                            consumption.execute_registered_aim_loss_difficult_terrain_charge(
                                RegisteredAimLossDifficultTerrainChargeExecutionRequest(
                                    "registered:replay", history, renamed_follow, "composite:renamed",
                                    renamed_charge, renamed_terrain), rejected_rng)
                    replay_traversal.assert_not_called()
                    execute.assert_not_called()
                    self.assertEqual(rejected_rng.mock_calls, [])
                    kernel.assert_called_once()
                    shot = aimed_shot(fresh, attack, history, weapon, "shot:fresh")
                    rng = SequenceRandom([1 if shot_hit else 10, *([10] * (3 + fresh_bonus)), 7])
                    applied = consumption.execute_registered_aim_ranged_attack(
                        RegisteredAimRangedAttackExecutionRequest("registered:fresh", history, shot), rng)
                    self.assertEqual(rng.randint(1, 10), 7)
                    self.assertEqual(kernel.call_count, 2)
                    traverse.assert_called_once()
                    athletics.assert_called_once()
                    self.assertEqual(prone.call_count, int(terrain_roll == 10))
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
                self.assertEqual(initial_state, initial_spatial)
                self.assertEqual(history.consumed_aim_source_ids, (first.request_id,))
                self.assertIs(applied.execution.ranged_attack.weapon_state, weapon)
                self.assertTrue(set(charged.registration.applied_rule_ids) <= set(charged.applied_rule_ids))
                self.assertTrue(set(applied.registration.applied_rule_ids) <= set(applied.applied_rule_ids))


if __name__ == "__main__":
    unittest.main()
