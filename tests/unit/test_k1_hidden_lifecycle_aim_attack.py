from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_registered_hidden_aim_attack import request as joint_request
from towr.domain.attack_models import AttackOutcome
from towr.domain.hidden_lifecycle_aim_models import HiddenLifecycleAimAttackExecutionRequest
from towr.domain.hidden_lifecycle_models import HiddenLifecycleApplicationRequest, HiddenLifecycleState
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.rules import hidden_lifecycle_aim_resolution as resolution
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.move_quietly_resolution import execute_move_quietly_action


def request(**kwargs):
    joint = joint_request(**kwargs)
    hidden = replace(joint.attack.hidden_request, consumed_opportunity_ids=("hidden:older", "hidden:prior"))
    joint = replace(joint, attack=replace(joint.attack,
        attack=replace(joint.attack.attack, hidden_attack=hidden)))
    state = HiddenLifecycleState(joint.attack.state, hidden.move_quietly, hidden.consumed_opportunity_ids)
    return HiddenLifecycleAimAttackExecutionRequest("lifecycle:aim", state, joint)


class K1HiddenLifecycleAimAttackTests(unittest.TestCase):
    def test_one_joint_executor_kernel_receipt_and_lifecycle_transition_for_all_outcomes(self):
        for weapon in (RangedWeaponId.LONGBOW, RangedWeaponId.CROSSBOW):
            for values in ((1, 2, 10), (10, 10, 10)):
                for hit in (False, True):
                    with self.subTest(weapon=weapon, values=values, hit=hit):
                        source = request(weapon=weapon, values=values)
                        before = deepcopy(source)
                        dice = 2 + sum(value <= 5 for value in values)
                        rng = SequenceRandom([1 if hit else 10, *([10] * (dice - 1)), 7])
                        decisions = Mock()
                        with (
                            patch.object(resolution, "execute_registered_hidden_aim_attack", wraps=resolution.execute_registered_hidden_aim_attack) as execute,
                            patch.object(resolution, "apply_hidden_lifecycle_result", wraps=resolution.apply_hidden_lifecycle_result) as apply,
                            patch("towr.rules.attack_action_execution.resolve_kernel_attack", wraps=resolve_kernel_attack) as kernel,
                        ):
                            result = resolution.execute_hidden_lifecycle_aim_attack(source, rng, decisions=decisions)
                        execute.assert_called_once_with(source.attack, rng, decisions=decisions)
                        apply.assert_called_once_with(result.lifecycle.source_request)
                        kernel.assert_called_once()
                        self.assertIs(result.lifecycle.completed, result.attack.hidden_attack)
                        self.assertIs(result.execution, result.attack.execution)
                        self.assertIs(result.state, result.lifecycle.state)
                        self.assertIs(result.aim_state, result.attack.aim_state)
                        self.assertIs(result.lifecycle.previous_state, source.state)
                        self.assertIsNone(result.state.active_move_quietly)
                        self.assertIs(result.state.hiding_positions, result.attack.hiding_position_state)
                        self.assertEqual(result.state.consumed_opportunity_ids,
                                         (*source.state.consumed_opportunity_ids, source.state.opportunity.id))
                        self.assertEqual(result.aim_state.consumed_aim_source_ids, ("source:older", "aim:execute"))
                        self.assertEqual(result.aim_state.consumed_aim_follow_up_ids, result.execution.consumed_aim_follow_up_ids)
                        self.assertEqual(result.state.hiding_positions.used_hiding_position_ids, ("hiding:older", "hiding:wall"))
                        shot = result.execution.ranged_attack
                        self.assertEqual(shot.attack.resolution.attack.outcome, AttackOutcome.HIT if hit else AttackOutcome.MISS)
                        self.assertEqual(shot.attack.resolution.attack.attacker_test.trace.rolled_dice, dice)
                        old_slots = source.attack.attack.hidden_request.attack.state.active_turn.action_slots
                        new_slots = shot.attack.state.active_turn.action_slots
                        self.assertEqual(new_slots[:-1], old_slots[:-1])
                        self.assertEqual(sum(s.executed for s in new_slots), sum(s.executed for s in old_slots) + 1)
                        self.assertTrue(set(result.attack.applied_rule_ids) <= set(result.applied_rule_ids))
                        self.assertTrue(set(result.lifecycle.applied_rule_ids) <= set(result.applied_rule_ids))
                        if weapon is RangedWeaponId.CROSSBOW:
                            self.assertFalse(shot.weapon_state.loaded)
                            self.assertEqual(shot.weapon_state.reload_cycle_id, "weapon:crossbow:hero:1:reload:1")
                        else:
                            self.assertIs(shot.weapon_state, source.attack.attack.attack.prepared_attack.preparation.execution.weapon_state)
                        self.assertEqual(rng.randint(1, 10), 7)
                        self.assertEqual(source, before)

    def test_inactive_different_source_chain_order_and_history_fail_before_rng(self):
        source = request()
        alternate_source = execute_move_quietly_action(
            source.state.active_move_quietly.source_request, SequenceRandom([1, 1, 10]))
        self.assertEqual(alternate_source.request_id, source.state.active_move_quietly.request_id)
        self.assertNotEqual(alternate_source, source.state.active_move_quietly)
        for state in (
            replace(source.state, active_move_quietly=None),
            replace(source.state, active_move_quietly=alternate_source),
            replace(source.state, consumed_opportunity_ids=()),
            replace(source.state, consumed_opportunity_ids=tuple(reversed(source.state.consumed_opportunity_ids))),
            replace(source.state, hiding_positions=replace(source.state.hiding_positions, consumed_attack_execution_ids=("different",))),
        ):
            rng, decisions = Mock(), Mock()
            with self.subTest(state=state), patch.object(resolution, "execute_registered_hidden_aim_attack") as execute:
                with self.assertRaises(ValueError):
                    resolution.execute_hidden_lifecycle_aim_attack(replace(source, state=state), rng, decisions=decisions)
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])
            self.assertEqual(decisions.mock_calls, [])

    def test_completed_lifecycle_and_aim_each_block_replay_even_with_new_ids(self):
        source = request()
        result = resolution.execute_hidden_lifecycle_aim_attack(source, SequenceRandom([10] * 4))
        for renamed in (False, True):
            candidate = request(renamed=renamed)
            for history in ("lifecycle", "aim"):
                rng = Mock()
                with self.subTest(renamed=renamed, history=history), patch.object(resolution, "execute_registered_hidden_aim_attack") as execute:
                    with self.assertRaises(ValueError):
                        if history == "lifecycle":
                            candidate = replace(candidate, id="new:wrapper", state=result.state)
                        else:
                            candidate = replace(candidate, attack=replace(candidate.attack, aim_state=result.aim_state))
                        resolution.execute_hidden_lifecycle_aim_attack(candidate, rng)
                execute.assert_not_called()
                self.assertEqual(rng.mock_calls, [])

    def test_runtime_preflight_rechecks_lifecycle_and_joint_history_before_executor(self):
        source = request()
        for guard in ("_validate_lifecycle_attack", "_validate_registered_hidden_aim_preflight"):
            rng = Mock()
            with (
                self.subTest(guard=guard),
                patch(f"towr.domain.hidden_lifecycle_aim_models.{guard}", side_effect=ValueError("preflight failed")) as check,
                patch.object(resolution, "execute_registered_hidden_aim_attack") as execute,
            ):
                with self.assertRaisesRegex(ValueError, "preflight failed"):
                    resolution.execute_hidden_lifecycle_aim_attack(source, rng)
            check.assert_called_once()
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])

    def test_rng_failure_skips_lifecycle_and_preserves_inputs(self):
        source = request()
        before = deepcopy(source)
        rng = Mock()
        rng.randint.side_effect = [1, RuntimeError("RNG failed")]
        with patch.object(resolution, "apply_hidden_lifecycle_result") as apply:
            with self.assertRaisesRegex(RuntimeError, "RNG failed"):
                resolution.execute_hidden_lifecycle_aim_attack(source, rng)
        apply.assert_not_called()
        self.assertEqual(rng.randint.call_count, 2)
        self.assertEqual(source, before)

    def test_lifecycle_or_final_result_failure_preserves_inputs_without_undoing_rng(self):
        for stage in ("apply_hidden_lifecycle_result", "HiddenLifecycleAimAttackExecutionResult"):
            source = request()
            before = deepcopy(source)
            rng = SequenceRandom([10] * 4 + [7])
            with (
                self.subTest(stage=stage),
                patch.object(resolution, stage, side_effect=RuntimeError("stage failed")),
                patch.object(resolution, "execute_registered_hidden_aim_attack", wraps=resolution.execute_registered_hidden_aim_attack) as execute,
            ):
                with self.assertRaisesRegex(RuntimeError, "stage failed"):
                    resolution.execute_hidden_lifecycle_aim_attack(source, rng)
            execute.assert_called_once()
            self.assertEqual(rng.randint(1, 10), 7)
            self.assertEqual(source, before)

    def test_request_types_rule_and_immutability(self):
        source = request()
        for changes in ({"id": ""}, {"rule_id": "foreign"}, {"state": None}, {"attack": None}, {"attack": source.attack.attack}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(source, **changes)
        with self.assertRaises(FrozenInstanceError):
            source.state = None
        with self.assertRaises(TypeError):
            resolution.execute_hidden_lifecycle_aim_attack(None, Mock())

    def test_result_binds_exact_source_lifecycle_attack_history_and_trace(self):
        source = request()
        result = resolution.execute_hidden_lifecycle_aim_attack(source, SequenceRandom([10] * 4))
        other = resolution.execute_hidden_lifecycle_aim_attack(request(renamed=True), SequenceRandom([10] * 4))
        renamed_application = resolution.apply_hidden_lifecycle_result(replace(result.lifecycle.source_request, id="other"))
        for changes in (
            {"request_id": "other"}, {"rule_id": "other"}, {"source_request": None},
            {"attack": None}, {"lifecycle": None}, {"attack": other.attack},
            {"lifecycle": other.lifecycle}, {"lifecycle": renamed_application},
            {"source_request": replace(source, id="other")},
            {"applied_rule_ids": ()}, {"applied_rule_ids": (*result.applied_rule_ids, "extra")},
        ):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(result, **changes)
        with self.assertRaises(FrozenInstanceError):
            result.lifecycle = other.lifecycle

    def test_completed_registration_cannot_be_applied_twice_or_reactivate_source(self):
        source = request()
        result = resolution.execute_hidden_lifecycle_aim_attack(source, SequenceRandom([10] * 4))
        for completed in (result.attack.hidden_attack, source.state.active_move_quietly):
            with self.subTest(type=type(completed)), self.assertRaises(ValueError):
                HiddenLifecycleApplicationRequest("replay", result.state, completed)
