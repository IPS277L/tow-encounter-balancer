from copy import deepcopy
from dataclasses import replace
from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_aim_resolution import (
    active_round, aim_request, attack_execution_request, follow_up_request, reserve_action,
)
from tests.unit.test_k1_ranged_weapon_attack_preparation import preparation_request
from towr.domain.aim_consumption_models import (
    AimConsumptionState, RegisteredAimLossAttackExecutionRequest, RegisteredAimRangedAttackExecutionRequest,
)
from towr.domain.aim_models import AimFollowUpOutcome
from towr.domain.aim_ranged_weapon_attack_models import AimRangedWeaponAttackExecutionRequest
from towr.domain.attack_models import AttackOutcome, ResilienceProfile
from towr.domain.condition_models import Condition, ConditionApplicationRequest, ConditionState
from towr.domain.magic_models import WizardMagicState
from towr.domain.ranged_weapon_attack_models import RangedWeaponAttackExecutionRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.recover_models import RecoverActionExecutionRequest, RecoverConditionTarget, RecoverMode, RecoverStandardChoice
from towr.domain.resolution_models import AttackerStaggerRequest
from towr.domain.reload_models import create_initial_ranged_weapon_reload_state
from towr.domain.test_models import Skill
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundAdvanceRequest, CombatTurnEndRequest, CombatTurnStartRequest,
)
from towr.rules import aim_consumption_resolution as consumption
from towr.rules.aim_resolution import execute_aim_action, resolve_aim_follow_up
from towr.rules.condition_effect_resolution import resolve_condition_application
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack_with_aim_history
from towr.rules.recover_resolution import execute_recover_action
from towr.rules.turn_resolution import (
    advance_combat_round, end_combat_turn, reserve_combat_action_slot, start_combat_turn,
)


def next_hero_round(state, target_conditions=ConditionState(), *, target_id="enemy:other",
                    hero_conditions=ConditionState(), close_combat=False, spatial=None):
    """Recover the target and, with an explicitly Close ally, the hero between real turns."""
    if spatial is not None:
        assert spatial.round_number == state.round_number
    recoveries = []
    state = end_combat_turn(CombatTurnEndRequest(
        f"end:{state.round_number}:hero", state, "hero",
    )).state
    for participant in state.participants:
        actor = participant.entity_id
        if actor in state.completed_turn_entity_ids:
            continue
        action_id = f"recover:{state.round_number}:{actor}"
        state = start_combat_turn(CombatTurnStartRequest(f"start:{action_id}", state, actor)).state
        state = reserve_combat_action_slot(CombatActionSlotRequest(
            f"slot:{action_id}", state, actor, CombatActionDeclaration(CombatActionKind.RECOVER),
            ActionSlotGrant.STANDARD,
        )).state
        removal = None
        if actor == target_id and target_conditions.has(Condition.STAGGERED):
            removal = RecoverConditionTarget(actor, target_conditions, None)
        elif actor == "ally" and hero_conditions.has(Condition.STAGGERED):
            if spatial is not None:
                assert spatial.placement_for(actor).zone_id == spatial.placement_for("hero").zone_id
            removal = RecoverConditionTarget("hero", hero_conditions, True)
        has_enemy_in_zone = close_combat
        if spatial is not None:
            placement = spatial.placement_for(actor)
            has_enemy_in_zone = any(p.side_id != placement.side_id for p in spatial.placements_in(placement.zone_id))
        recovery = execute_recover_action(RecoverActionExecutionRequest(
            action_id, state, actor, target_conditions if actor == target_id else ConditionState(),
            has_enemy_in_zone, 1, RecoverMode.STANDARD,
            RecoverStandardChoice(WizardMagicState(), staggered_target=removal),
        ), SequenceRandom([]))
        recoveries.append(recovery)
        for change in recovery.resolution.condition_changes:
            if change.entity_id == target_id:
                target_conditions = change.conditions
            elif change.entity_id == "hero":
                hero_conditions = change.conditions
        state = recovery.round_state
        state = end_combat_turn(CombatTurnEndRequest(f"end:{action_id}", state, actor)).state
    state = advance_combat_round(CombatRoundAdvanceRequest(
        f"advance:{state.round_number}", state, state.participants,
    )).state
    state = start_combat_turn(CombatTurnStartRequest(f"hero:{state.round_number}", state, "hero")).state
    return state, target_conditions, hero_conditions, tuple(recoveries)


def pending_attack(state, target, identifier):
    attack = attack_execution_request(
        state=reserve_action(state, CombatActionKind.ATTACK), target_id=target,
    )
    kernel = attack.kernel_request
    # Avoid Wounds; a hit still applies Staggered, carried to the target's later turns.
    return replace(attack, id=identifier, kernel_request=replace(
        kernel, id=f"{identifier}:kernel", attack=replace(
            kernel.attack, id=f"{identifier}:test", impact_spec=replace(
                kernel.attack.impact_spec, resilience=ResilienceProfile(toughness=20),
            ),
        ),
    ))


def follow_up(aim, attack, identifier, *, skill=Skill.SHOOTING):
    return resolve_aim_follow_up(replace(
        follow_up_request(aim, attack=attack, skill=skill), id=identifier,
    ))


def aimed_shot(aim, attack, history, weapon, identifier):
    follow = follow_up(aim, attack, f"{identifier}:follow")
    return AimRangedWeaponAttackExecutionRequest(
        identifier, follow, RangedWeaponAttackExecutionRequest(
            f"{identifier}:ranged", Skill.SHOOTING, follow.attack, weapon,
        ), history.consumed_aim_follow_up_ids,
    )


class K1AimTargetSwitchTests(unittest.TestCase):
    def test_lost_on_other_target_then_fresh_aim_applied_across_real_turns(self):
        self.check_loss_then_fresh_aim(Skill.SHOOTING, "enemy:other")

    def test_same_target_melee_loss_recover_and_fresh_aim_across_real_turns(self):
        self.check_loss_then_fresh_aim(Skill.MELEE, "enemy")

    def test_same_target_brawn_loss_recover_and_fresh_aim_across_real_turns(self):
        self.check_loss_then_fresh_aim(Skill.BRAWN, "enemy")

    def check_loss_then_fresh_aim(self, skill, first_target):
        close_combat = skill in (Skill.MELEE, Skill.BRAWN)
        for first_bonus, fresh_bonus, first_hit, second_hit in product((0, 2), (0, 2), (False, True), (False, True)):
            with self.subTest(first=first_bonus, fresh=fresh_bonus, first_hit=first_hit, second_hit=second_hit):
                history = AimConsumptionState("hero")
                initial_history = deepcopy(history)
                first = execute_aim_action(
                    aim_request(reserve_action(active_round(), CombatActionKind.AIM)),
                    SequenceRandom([1] * first_bonus + [10] * (3 - first_bonus)),
                )
                first_before = deepcopy(first)
                turn, _, _, _ = next_hero_round(first.round_state)
                attack_b = pending_attack(turn, first_target, "attack:first")
                if close_combat:
                    attack_b = replace(attack_b, kernel_request=replace(attack_b.kernel_request,
                        attack=replace(attack_b.kernel_request.attack, is_close_range=True)))
                lost = follow_up(first, attack_b, "follow:lost", skill=skill)
                self.assertIs(lost.outcome, AimFollowUpOutcome.LOST)
                self.assertIs(lost.attack, attack_b)
                rng_b = SequenceRandom([1 if first_hit else 10, 10, 10, 7])
                with patch("towr.rules.attack_action_execution.resolve_kernel_attack", wraps=resolve_kernel_attack) as kernel:
                    result_b = consumption.execute_registered_aim_loss_attack(
                        RegisteredAimLossAttackExecutionRequest("registered:B", history, lost, attack_b), rng_b,
                    )
                    kernel.assert_called_once()
                    self.assertEqual(kernel.call_args.args[0], attack_b.kernel_request)
                    self.assertIs(result_b.registration.previous_state, history)
                    history = result_b.state
                    lost_history_before = deepcopy(history)
                    self.assertEqual(history.consumed_aim_source_ids, (first.request_id,))
                    self.assertEqual(history.consumed_aim_follow_up_ids, (lost.request_id,))
                    self.assertEqual(rng_b.randint(1, 10), 7)

                    target_after_attack = result_b.execution.resolution.target_state
                    hero_conditions = ConditionState()
                    follow_ups = result_b.execution.resolution.follow_ups
                    if close_combat and not first_hit:
                        self.assertEqual(follow_ups, (AttackerStaggerRequest(attack_id=attack_b.kernel_request.attack.id),))
                        hero_conditions = resolve_condition_application(ConditionApplicationRequest(
                            f"{follow_ups[0].attack_id}:stagger-attacker", hero_conditions, Condition.STAGGERED,
                            follow_ups[0].rule_id,
                        )).state
                    else:
                        self.assertEqual(follow_ups, ())
                    turn, target_conditions, recovered_hero, recoveries = next_hero_round(
                        result_b.execution.state, target_after_attack.conditions, target_id=first_target,
                        hero_conditions=hero_conditions, close_combat=close_combat,
                    )
                    target_recovery = next(r for r in recoveries if r.source_request.actor_id == first_target)
                    self.assertIs(target_recovery.source_request.actor_conditions, target_after_attack.conditions)
                    changes = tuple(c for r in recoveries for c in r.resolution.condition_changes)
                    self.assertEqual(tuple(c.entity_id for c in changes),
                                     (first_target,) if first_hit else (("hero",) if close_combat else ()))
                    for change in changes:
                        self.assertEqual(change.removed_conditions, (Condition.STAGGERED,))
                        self.assertTrue(change.previous_conditions.has(Condition.STAGGERED))
                    self.assertEqual(target_conditions, ConditionState())
                    self.assertEqual(recovered_hero, ConditionState())
                    recovered_target = replace(target_after_attack, conditions=target_conditions)
                    fresh_request = aim_request(reserve_action(
                        turn, CombatActionKind.AIM,
                    ))
                    fresh = execute_aim_action(replace(
                        fresh_request, id="aim:fresh", awareness_test=replace(fresh_request.awareness_test, id="awareness:fresh"),
                    ), SequenceRandom([1] * fresh_bonus + [10] * (3 - fresh_bonus)))
                    turn, next_conditions, next_hero_conditions, idle_recoveries = next_hero_round(
                        fresh.round_state, recovered_target.conditions, target_id=first_target,
                        hero_conditions=recovered_hero, close_combat=close_combat,
                    )
                    self.assertIs(next_conditions, recovered_target.conditions)
                    self.assertIs(next_hero_conditions, recovered_hero)
                    self.assertTrue(all(not r.resolution.condition_changes for r in idle_recoveries))
                    attack_a = pending_attack(turn, "enemy", "attack:A")
                    if first_target == "enemy":
                        attack_a = replace(attack_a, kernel_request=replace(attack_a.kernel_request,
                            target_state=recovered_target))
                        self.assertIs(attack_a.kernel_request.target_state, recovered_target)
                    weapon = create_initial_ranged_weapon_reload_state("hero:bow", RangedWeaponId.LONGBOW)

                    # A renamed preparation cannot restore the old Aim source.
                    stale_preparation = replace(preparation_request(
                        RangedWeaponId.LONGBOW, attack=attack_a, aim=first,
                    ), id="prepare:renamed")
                    with patch("towr.rules.ranged_weapon_attack_preparation.prepare_ranged_weapon_attack") as prepare:
                        with self.assertRaisesRegex(ValueError, "source was already consumed"):
                            prepare_ranged_weapon_attack_with_aim_history(history, stale_preparation)
                    prepare.assert_not_called()
                    # Bypassing preparation with new Attack/follow-up IDs is also rejected before RNG.
                    stale = aimed_shot(first, attack_a, history, weapon, "shot:renamed")
                    rejected_rng, decisions = Mock(), Mock()
                    with patch.object(consumption, "execute_aim_ranged_weapon_attack") as execute:
                        with self.assertRaisesRegex(ValueError, "source was already consumed"):
                            consumption.execute_registered_aim_ranged_attack(
                                RegisteredAimRangedAttackExecutionRequest("registered:renamed", history, stale),
                                rejected_rng, decisions=decisions,
                            )
                    execute.assert_not_called()
                    self.assertEqual(rejected_rng.mock_calls, [])
                    self.assertEqual(decisions.mock_calls, [])
                    kernel.assert_called_once()

                    shot = aimed_shot(fresh, attack_a, history, weapon, "shot:fresh")
                    self.assertIs(shot.aim_follow_up.outcome, AimFollowUpOutcome.APPLIED_TO_RANGED_ATTACK)
                    rng_a = SequenceRandom([1 if second_hit else 10, *([10] * (2 + fresh_bonus)), 7])
                    result_a = consumption.execute_registered_aim_ranged_attack(
                        RegisteredAimRangedAttackExecutionRequest("registered:A", history, shot), rng_a,
                    )
                    self.assertEqual(kernel.call_count, 2)
                    self.assertEqual(kernel.call_args.args[0], shot.ranged_attack.attack.kernel_request)
                    self.assertEqual(rng_a.randint(1, 10), 7)
                execution_a = result_a.execution.ranged_attack.attack
                self.assertIs(result_a.registration.previous_state, result_b.state)
                self.assertEqual(result_a.state.consumed_aim_source_ids, (first.request_id, fresh.request_id))
                self.assertEqual(result_a.state.consumed_aim_follow_up_ids, (lost.request_id, shot.aim_follow_up.request_id))
                self.assertEqual(result_a.state.consumed_aim_follow_up_ids, result_a.execution.consumed_aim_follow_up_ids)
                self.assertIs(result_a.execution.ranged_attack.weapon_state, weapon)
                self.assertEqual((first.round_state.round_number, result_b.execution.state.round_number,
                                  fresh.round_state.round_number, execution_a.state.round_number), (1, 2, 3, 4))
                for execution, request, hit, bonus in (
                    (result_b.execution, attack_b, first_hit, 0),
                    (execution_a, shot.ranged_attack.attack, second_hit, fresh_bonus),
                ):
                    trace = execution.resolution.attack.attacker_test.trace
                    self.assertEqual(trace.rolled_dice, 3 + bonus)
                    self.assertEqual(trace.regular_dice_delta, bonus)
                    self.assertIs(execution.resolution.attack.outcome, AttackOutcome.HIT if hit else AttackOutcome.MISS)
                    expected_conditions = ConditionState(frozenset({Condition.STAGGERED})) if hit else ConditionState()
                    self.assertEqual(execution.resolution.target_state, replace(
                        request.kernel_request.target_state, conditions=expected_conditions,
                    ))
                    slots = execution.state.active_turn.action_slots
                    self.assertEqual(len(slots), 1)
                    self.assertTrue(slots[0].executed)
                    self.assertEqual(slots[0].execution.id, request.id)
                    self.assertFalse(request.state.active_turn.action_slots[0].executed)
                self.assertEqual(first, first_before)
                self.assertEqual(result_b.state, lost_history_before)
                self.assertEqual(result_b.source_request.state, initial_history)
                self.assertTrue(set(result_b.registration.applied_rule_ids) <= set(result_b.applied_rule_ids))
                self.assertTrue(set(result_a.registration.applied_rule_ids) <= set(result_a.applied_rule_ids))


if __name__ == "__main__":
    unittest.main()
