from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_aim_resolution import (
    attack_execution_request,
    completed_aim,
    reserve_action,
)
from tests.unit.test_k1_ranged_weapon_attack_preparation import preparation_request
from towr.domain.aim_ranged_weapon_attack_models import AimRangedWeaponAttackExecutionResult
from towr.domain.prepared_ranged_weapon_attack_models import (
    PREPARED_RANGED_ATTACK_EXECUTION_RULE_ID,
    PreparedRangedWeaponAttackExecutionRequest,
)
from towr.domain.ranged_weapon_profiles import (
    RangedWeaponId,
    RangedWeaponRange,
    ranged_weapon_reload_profile,
)
from towr.domain.turn_models import ActionSlotGrant, CombatActionKind
from towr.rules.aim_ranged_weapon_attack_resolution import execute_aim_ranged_weapon_attack
from towr.rules.prepared_ranged_weapon_attack_resolution import execute_prepared_ranged_weapon_attack
from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack
from towr.rules.ranged_weapon_attack_resolution import execute_ranged_weapon_attack


MODULE = "towr.rules.prepared_ranged_weapon_attack_resolution"


def prepared_request(
    weapon_id=RangedWeaponId.LONGBOW,
    *,
    aim_values=None,
    consumed=("aim:older",),
    **kwargs,
):
    if aim_values is not None:
        aim = completed_aim(values=aim_values)
        state = reserve_action(
            aim.round_state, CombatActionKind.ATTACK, grant=ActionSlotGrant.ABILITY
        )
        modifiers = ()
        if kwargs.get("uses_repeater_bonus", False):
            modifiers = (ranged_weapon_reload_profile(weapon_id).optional_bonus_modifier(),)
        kwargs.update(
            aim=aim,
            attack=attack_execution_request(
                state=state, slot_index=2, existing_modifiers=modifiers
            ),
        )
    preparation = prepare_ranged_weapon_attack(preparation_request(weapon_id, **kwargs))
    return PreparedRangedWeaponAttackExecutionRequest(
        id="execute:prepared", preparation=preparation,
        consumed_aim_follow_up_ids=consumed,
    )


class K1PreparedRangedWeaponAttackResolutionTests(unittest.TestCase):
    def assert_one_attack(self, request, result):
        before = request.preparation.execution.attack.state.active_turn
        after = result.ranged_attack.attack.state.active_turn
        self.assertEqual(len(before.action_slots), len(after.action_slots))
        self.assertEqual(
            sum(slot.executed for slot in after.action_slots),
            sum(slot.executed for slot in before.action_slots) + 1,
        )
        self.assertTrue(result.ranged_attack.attack.slot.executed)
        self.assertEqual(result.ranged_attack.source_request, request.preparation.execution)
        self.assertEqual(
            result.applied_rule_ids,
            tuple(dict.fromkeys((request.rule_id, *request.preparation.applied_rule_ids,
                                 *result.execution.applied_rule_ids))),
        )

    def test_direct_free_shot_routes_once_and_preserves_preparation_and_chain(self):
        request = prepared_request()
        rng = SequenceRandom([1, 10, 10, 7])
        decisions = Mock()
        with (
            patch(f"{MODULE}.execute_ranged_weapon_attack", wraps=execute_ranged_weapon_attack) as direct,
            patch(f"{MODULE}.execute_aim_ranged_weapon_attack") as aimed,
        ):
            result = execute_prepared_ranged_weapon_attack(request, rng, decisions=decisions)
        direct.assert_called_once_with(request.preparation.execution, rng, decisions=decisions)
        aimed.assert_not_called()
        self.assertIs(result.source_request, request)
        self.assertIs(result.execution, result.ranged_attack)
        self.assertIs(result.ranged_attack.weapon_state, request.preparation.source_request.weapon_state)
        self.assertEqual(result.consumed_aim_follow_up_ids, request.consumed_aim_follow_up_ids)
        self.assertEqual(rng.randint(1, 10), 7)
        self.assert_one_attack(request, result)

    def test_direct_reloadable_hit_and_miss_both_open_one_cycle(self):
        for values in ((1, 10, 10, 1), (10, 10, 10)):
            with self.subTest(values=values):
                request = prepared_request(
                    RangedWeaponId.CROSSBOW, target_range=RangedWeaponRange.LONG,
                    next_cycle="weapon:crossbow:hero:1:reload:1",
                )
                # Crossbow's armoured-target bonus turns the hit into a Wound.
                rng = SequenceRandom((*values, 7))
                result = execute_prepared_ranged_weapon_attack(request, rng)
                self.assertEqual(rng.randint(1, 10), 7)
                self.assertFalse(result.ranged_attack.weapon_state.loaded)
                self.assertEqual(result.ranged_attack.weapon_state.reload_cycle_id,
                                 "weapon:crossbow:hero:1:reload:1")
                self.assertTrue(request.preparation.execution.weapon_state.loaded)
                self.assert_one_attack(request, result)

    def test_aim_routes_once_without_reapplying_bonus(self):
        request = prepared_request(aim_values=(1, 10, 10))
        rng = SequenceRandom([10, 10, 10, 10, 7])
        decisions = Mock()
        with (
            patch(f"{MODULE}.execute_ranged_weapon_attack") as direct,
            patch(f"{MODULE}.execute_aim_ranged_weapon_attack", wraps=execute_aim_ranged_weapon_attack) as aimed,
        ):
            result = execute_prepared_ranged_weapon_attack(request, rng, decisions=decisions)
        direct.assert_not_called()
        aimed.assert_called_once()
        self.assertIs(aimed.call_args.args[1], rng)
        self.assertIs(aimed.call_args.kwargs["decisions"], decisions)
        self.assertIsInstance(result.execution, AimRangedWeaponAttackExecutionResult)
        self.assertEqual(result.consumed_aim_follow_up_ids,
                         ("aim:older", request.preparation.aim_follow_up.request_id))
        trace = result.ranged_attack.attack.resolution.attack.attacker_test.trace
        self.assertEqual(trace.regular_dice_delta, 1)
        self.assertEqual(trace.rolled_dice, 4)
        self.assertEqual(rng.randint(1, 10), 7)
        self.assert_one_attack(request, result)

    def test_zero_success_aim_is_consumed(self):
        request = prepared_request(aim_values=(10, 10, 10))
        result = execute_prepared_ranged_weapon_attack(request, SequenceRandom([10] * 3))
        self.assertIsNone(request.preparation.aim_follow_up.modifier)
        self.assertEqual(result.consumed_aim_follow_up_ids,
                         (*request.consumed_aim_follow_up_ids, request.preparation.aim_follow_up.request_id))
        self.assertEqual(result.ranged_attack.attack.resolution.attack.attacker_test.trace.rolled_dice, 3)
        self.assert_one_attack(request, result)

    def test_aim_and_repeater_preserve_profile_bonus_and_reload_choice(self):
        for use_bonus in (False, True):
            with self.subTest(use_bonus=use_bonus):
                request = prepared_request(
                    RangedWeaponId.REPEATER_PISTOL, aim_values=(1, 10, 10), lore=True,
                    target_range=RangedWeaponRange.SHORT,
                    uses_repeater_bonus=use_bonus,
                    next_cycle="weapon:repeater_pistol:hero:1:reload:1" if use_bonus else None,
                )
                # Base 3 + Aim 1 (+ Repeater 2), with the common cap at twice base.
                dice_count = 6 if use_bonus else 4
                rng = SequenceRandom([10] * dice_count + [7])
                result = execute_prepared_ranged_weapon_attack(request, rng)
                trace = result.ranged_attack.attack.resolution.attack.attacker_test.trace
                self.assertEqual(trace.regular_dice_delta, 3 if use_bonus else 1)
                self.assertEqual(trace.rolled_dice, dice_count)
                self.assertEqual(rng.randint(1, 10), 7)
                self.assertEqual(result.ranged_attack.weapon_state.loaded, not use_bonus)
                self.assert_one_attack(request, result)

    def test_long_rifle_keeps_extreme_range_and_wounds_preparation_trace(self):
        request = prepared_request(
            RangedWeaponId.HOCHLAND_LONG_RIFLE, aim_values=(1, 10, 10), lore=True,
            target_range=RangedWeaponRange.EXTREME, range_approved=True,
            next_cycle="weapon:hochland_long_rifle:hero:1:reload:1",
        )
        result = execute_prepared_ranged_weapon_attack(request, SequenceRandom([10] * 4))
        self.assertTrue(set(request.preparation.applied_rule_ids) <= set(result.applied_rule_ids))
        self.assertFalse(result.ranged_attack.weapon_state.loaded)
        self.assert_one_attack(request, result)

    def test_replay_is_rejected_before_rng(self):
        request = prepared_request(aim_values=(1, 10, 10))
        result = execute_prepared_ranged_weapon_attack(request, SequenceRandom([10] * 4))
        rng = Mock()
        with self.assertRaisesRegex(ValueError, "already consumed"):
            execute_prepared_ranged_weapon_attack(
                replace(request, consumed_aim_follow_up_ids=result.consumed_aim_follow_up_ids), rng
            )
        rng.randint.assert_not_called()

    def test_execution_failure_keeps_input_chain_weapon_and_slot_unchanged(self):
        for aim_values in (None, (1, 10, 10)):
            with self.subTest(aim_values=aim_values):
                request = prepared_request(
                    RangedWeaponId.CROSSBOW, aim_values=aim_values,
                    target_range=RangedWeaponRange.LONG,
                    next_cycle="weapon:crossbow:hero:1:reload:1",
                )
                with self.assertRaises(RuntimeError):
                    execute_prepared_ranged_weapon_attack(request, SequenceRandom([]))
                self.assertEqual(request.consumed_aim_follow_up_ids, ("aim:older",))
                self.assertTrue(request.preparation.execution.weapon_state.loaded)
                self.assertFalse(request.preparation.execution.attack.state.active_turn.action_slots[-1].executed)
                result = execute_prepared_ranged_weapon_attack(request, SequenceRandom([10] * 4))
                self.assert_one_attack(request, result)

    def test_request_rejects_invalid_ids_source_and_chain(self):
        request = prepared_request()
        for fields in (
            {"id": " "}, {"id": request.preparation.request_id},
            {"id": request.preparation.execution.id},
            {"id": request.preparation.execution.attack.id},
            {"rule_id": "other"}, {"preparation": request.preparation.source_request},
            {"consumed_aim_follow_up_ids": ("same", "same")},
            {"consumed_aim_follow_up_ids": ("",)},
            {"consumed_aim_follow_up_ids": "not-a-tuple"},
        ):
            with self.subTest(fields=fields), self.assertRaises((ValueError, TypeError)):
                replace(request, **fields)

    def test_result_rejects_foreign_execution_branch_chain_and_trace(self):
        direct = execute_prepared_ranged_weapon_attack(prepared_request(), SequenceRandom([10] * 3))
        aimed = execute_prepared_ranged_weapon_attack(
            prepared_request(aim_values=(1, 10, 10)), SequenceRandom([10] * 4)
        )
        foreign = execute_prepared_ranged_weapon_attack(
            prepared_request(RangedWeaponId.WARBOW), SequenceRandom([10] * 3)
        )
        for result, fields in (
            (direct, {"execution": foreign.execution}),
            (direct, {"execution": aimed.execution}),
            (aimed, {"execution": aimed.ranged_attack}),
            (direct, {"request_id": "stale"}),
            (direct, {"rule_id": "foreign"}),
            (direct, {"previous_consumed_aim_follow_up_ids": ()}),
            (direct, {"consumed_aim_follow_up_ids": ("aim:older", "extra")}),
            (aimed, {"consumed_aim_follow_up_ids": ("aim:older",)}),
            (direct, {"applied_rule_ids": (PREPARED_RANGED_ATTACK_EXECUTION_RULE_ID,)}),
            (aimed, {"applied_rule_ids": (*aimed.applied_rule_ids, "invented")}),
            (aimed, {"execution": replace(aimed.execution, request_id="foreign",
                                        source_request=replace(aimed.execution.source_request, id="foreign"))}),
        ):
            with self.subTest(fields=fields), self.assertRaises((ValueError, TypeError)):
                replace(result, **fields)


if __name__ == "__main__":
    unittest.main()
