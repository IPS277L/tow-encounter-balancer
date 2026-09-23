from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_aim_attack_loss_consumption import pending_inputs
from tests.unit.test_k1_aim_consumption_resolution import request as non_attack_loss
from tests.unit.test_k1_aim_attack_consumption import request as applied_request
from tests.unit.test_k1_ranged_weapon_attack_preparation import preparation_request
from towr.domain.aim_consumption_models import AimConsumptionState, RegisteredAimLossAttackExecutionRequest
from towr.domain.attack_models import AttackOutcome
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.test_models import Skill
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind
from towr.rules import aim_consumption_resolution as consumption
from towr.rules.aim_resolution import execute_aim_action, resolve_aim_follow_up
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack_with_aim_history


def request(**kwargs):
    follow_up, attack = pending_inputs(**kwargs)
    return RegisteredAimLossAttackExecutionRequest(
        "registered:aim-loss", AimConsumptionState("hero", ("source:older",), ("follow:older", "follow:prior")),
        follow_up, attack,
    )


class K1RegisteredAimLossAttackTests(unittest.TestCase):
    def test_hit_miss_aim_zero_positive_and_later_turn_execute_and_register_once(self):
        for values in ((1, 2, 10), (10, 10, 10)):
            for hit in (False, True):
                for later in (None, 2):
                    with self.subTest(values=values, hit=hit, round=later):
                        source = request(values=values, later_round=later)
                        before = deepcopy(source)
                        rng, decisions = SequenceRandom([1 if hit else 10, 10, 10, 7]), Mock()
                        with (
                            patch.object(consumption, "execute_attack_action", wraps=consumption.execute_attack_action) as execute,
                            patch.object(consumption, "consume_attack_lost_aim", wraps=consumption.consume_attack_lost_aim) as register,
                            patch("towr.rules.attack_action_execution.resolve_kernel_attack", wraps=resolve_kernel_attack) as kernel,
                        ):
                            result = consumption.execute_registered_aim_loss_attack(source, rng, decisions=decisions)
                        execute.assert_called_once_with(source.attack, rng, decisions=decisions)
                        kernel.assert_called_once()
                        register.assert_called_once_with(result.registration.source_request)
                        self.assertIs(result.execution, result.registration.source_request.execution)
                        self.assertIs(result.state, result.registration.state)
                        self.assertIs(result.registration.previous_state, source.state)
                        self.assertIs(result.registration.source_request.follow_up, source.follow_up)
                        self.assertEqual(result.state.consumed_aim_source_ids, ("source:older", "aim:execute"))
                        self.assertEqual(result.state.consumed_aim_follow_up_ids,
                                         ("follow:older", "follow:prior", source.follow_up.request_id))
                        self.assertEqual(result.execution.resolution.attack.outcome, AttackOutcome.HIT if hit else AttackOutcome.MISS)
                        self.assertEqual(result.execution.resolution.attack.attacker_test.trace.rolled_dice, 3)
                        self.assertEqual(result.execution.resolution.attack.attacker_test.trace.regular_dice_delta, 0)
                        old_slots = source.attack.state.active_turn.action_slots
                        new_slots = result.execution.state.active_turn.action_slots
                        self.assertEqual(new_slots[:-1], old_slots[:-1])
                        self.assertEqual(sum(s.executed for s in new_slots), sum(s.executed for s in old_slots) + 1)
                        self.assertEqual(result.execution.slot.execution.id, source.attack.id)
                        self.assertTrue(set(result.registration.applied_rule_ids) <= set(result.applied_rule_ids))
                        self.assertEqual(rng.randint(1, 10), 7)
                        self.assertEqual(source, before)

    def test_replay_and_consumed_non_attack_or_applied_source_rejected_before_rng(self):
        source = request()
        result = consumption.execute_registered_aim_loss_attack(source, SequenceRandom([10] * 3))
        histories = (
            result.state,
            consumption.consume_lost_aim(non_attack_loss()).state,
            consumption.register_aim_ranged_attack(applied_request()).state,
        )
        for candidate in (source, request(renamed=True)):
            for history in histories:
                rng, decisions = Mock(), Mock()
                with self.subTest(id=candidate.attack.id, history=history), patch.object(consumption, "execute_attack_action") as execute:
                    with self.assertRaisesRegex(ValueError, "source was already consumed"):
                        consumption.execute_registered_aim_loss_attack(
                            replace(candidate, id="wrapper:new", state=history), rng, decisions=decisions)
                execute.assert_not_called()
                self.assertEqual(rng.mock_calls, [])
                self.assertEqual(decisions.mock_calls, [])

    def test_actor_follow_up_and_exact_attack_binding_before_executor(self):
        source = request()
        different_target = replace(source.attack, target_id="enemy",
            kernel_request=replace(source.attack.kernel_request, target_id="enemy"))
        for changes in (
            {"state": replace(source.state, actor_id="other")},
            {"state": replace(source.state, consumed_aim_follow_up_ids=(source.follow_up.request_id,))},
            {"attack": replace(source.attack, id="attack:foreign")},
            {"attack": different_target},
            {"attack": replace(source.attack, kernel_request=replace(source.attack.kernel_request, id="kernel:foreign"))},
        ):
            rng = Mock()
            with self.subTest(changes=changes), patch.object(consumption, "execute_attack_action") as execute:
                with self.assertRaises(ValueError):
                    consumption.execute_registered_aim_loss_attack(replace(source, **changes), rng)
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])

    def test_chronology_slot_declaration_and_unsupported_follow_up_before_rng(self):
        source = request()
        pending = source.follow_up.source_request.aim.source_request
        future = execute_aim_action(replace(pending, round_state=replace(pending.round_state, round_number=2)), SequenceRandom([1, 2, 10]))
        earlier = resolve_aim_follow_up(replace(source.follow_up.source_request, aim=future))
        turn = source.attack.state.active_turn
        wrong_slot = replace(turn.action_slots[-1], declaration=CombatActionDeclaration(CombatActionKind.RECOVER))
        wrong_attack = replace(source.attack, state=replace(source.attack.state,
            active_turn=replace(turn, action_slots=(*turn.action_slots[:-1], wrong_slot))))
        wrong_follow = resolve_aim_follow_up(replace(source.follow_up.source_request, attack=wrong_attack))
        cases = (
            (earlier, source.attack), (wrong_follow, wrong_attack),
            pending_inputs(later_round=2, later_second=True),
            pending_inputs(target="enemy"), pending_inputs(target="enemy", skill=Skill.THROWING),
            pending_inputs(target="enemy", skill=Skill.AWARENESS),
            (non_attack_loss().follow_up, source.attack),
        )
        for follow_up, attack in cases:
            rng = Mock()
            with self.subTest(follow_up=follow_up), patch.object(consumption, "execute_attack_action") as execute:
                with self.assertRaises(ValueError):
                    consumption.execute_registered_aim_loss_attack(replace(source, follow_up=follow_up, attack=attack), rng)
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])

    def test_runtime_rechecks_shared_preflight_before_rng(self):
        source, rng = request(), Mock()
        with (
            patch.object(consumption, "_validate_attack_loss_preflight", side_effect=ValueError("preflight failed")) as check,
            patch.object(consumption, "execute_attack_action") as execute,
        ):
            with self.assertRaisesRegex(ValueError, "preflight failed"):
                consumption.execute_registered_aim_loss_attack(source, rng)
        check.assert_called_once_with(source.state, source.follow_up, source.attack)
        execute.assert_not_called()
        self.assertEqual(rng.mock_calls, [])

    def test_rng_failure_preserves_inputs_and_does_not_register(self):
        source = request()
        before = deepcopy(source)
        rng = Mock()
        rng.randint.side_effect = [1, RuntimeError("RNG failed")]
        with patch.object(consumption, "consume_attack_lost_aim") as register:
            with self.assertRaisesRegex(RuntimeError, "RNG failed"):
                consumption.execute_registered_aim_loss_attack(source, rng)
        register.assert_not_called()
        self.assertEqual(rng.randint.call_count, 2)
        self.assertEqual(source, before)

    def test_registration_or_result_failure_does_not_mutate_inputs_or_undo_rng(self):
        for stage in ("consume_attack_lost_aim", "RegisteredAimLossAttackExecutionResult"):
            source, rng = request(), SequenceRandom([10, 10, 10, 7])
            before = deepcopy(source)
            with self.subTest(stage=stage), patch.object(consumption, stage, side_effect=RuntimeError("stage failed")):
                with self.assertRaisesRegex(RuntimeError, "stage failed"):
                    consumption.execute_registered_aim_loss_attack(source, rng)
            self.assertEqual(rng.randint(1, 10), 7)
            self.assertEqual(source, before)

    def test_result_registration_source_history_and_trace_cannot_be_rebound(self):
        source = request()
        result = consumption.execute_registered_aim_loss_attack(source, SequenceRandom([10] * 3))
        other = consumption.execute_registered_aim_loss_attack(request(renamed=True), SequenceRandom([10] * 3))
        for changes in (
            {"request_id": "other"}, {"rule_id": "other"}, {"source_request": None},
            {"registration": None}, {"registration": other.registration},
            {"source_request": replace(source, id="other")},
            {"source_request": replace(source, state=replace(source.state, consumed_aim_source_ids=("different",)))},
            {"applied_rule_ids": ()}, {"applied_rule_ids": (*result.applied_rule_ids, "extra")},
        ):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(result, **changes)

    def test_types_and_next_preparation_with_returned_history(self):
        source = request()
        for changes in ({"id": ""}, {"rule_id": "foreign"}, {"state": None}, {"follow_up": None}, {"attack": None}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(source, **changes)
        with self.assertRaises(TypeError):
            consumption.execute_registered_aim_loss_attack(None, Mock())
        result = consumption.execute_registered_aim_loss_attack(source, SequenceRandom([10] * 3))
        aim = source.follow_up.source_request.aim
        next_attack = replace(source.attack, id="attack:next", target_id=aim.bonus.target_id,
            kernel_request=replace(source.attack.kernel_request, target_id=aim.bonus.target_id))
        candidate = replace(preparation_request(RangedWeaponId.LONGBOW, attack=next_attack, aim=aim), id="prepare:new")
        with self.assertRaisesRegex(ValueError, "source was already consumed"):
            prepare_ranged_weapon_attack_with_aim_history(result.state, candidate)
