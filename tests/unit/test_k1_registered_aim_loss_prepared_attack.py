from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_aim_prepared_attack_loss_consumption import pending_prepared, request as completed_request
from tests.unit.test_k1_aim_ranged_attack_loss_consumption import request as ranged_request
from tests.unit.test_k1_aim_attack_consumption import request as applied_request
from tests.unit.test_k1_aim_consumption_resolution import request as non_attack_request
from tests.unit.test_k1_ranged_weapon_attack_preparation import preparation_request
from towr.domain.aim_consumption_models import (
    AimConsumptionState, RegisteredAimLossPreparedAttackExecutionRequest,
)
from towr.domain.attack_models import AttackOutcome
from towr.domain.ranged_weapon_attack_preparation_models import OUTSIDE_OPTIMUM_RANGE_RULE_ID
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.test_models import Skill
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind
from towr.rules import aim_consumption_resolution as consumption
from towr.rules.aim_resolution import execute_aim_action, resolve_aim_follow_up
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.ranged_weapon_attack_preparation import (
    prepare_ranged_weapon_attack, prepare_ranged_weapon_attack_with_aim_history,
)


def request(**kwargs):
    follow, prepared = pending_prepared(**kwargs)
    return RegisteredAimLossPreparedAttackExecutionRequest(
        "registered:prepared-loss", AimConsumptionState("hero", ("source:older",), prepared.consumed_aim_follow_up_ids),
        follow, prepared)


class K1RegisteredAimLossPreparedAttackTests(unittest.TestCase):
    def test_free_crossbow_hit_miss_aim_and_turn_execute_register_once(self):
        for weapon, values, hit, later in product(
            (RangedWeaponId.LONGBOW, RangedWeaponId.CROSSBOW),
            ((1, 2, 10), (10, 10, 10)), (False, True), (None, 2),
        ):
            with self.subTest(weapon=weapon, values=values, hit=hit, later=later):
                source = request(weapon=weapon, values=values, later_round=later)
                before = deepcopy(source)
                rng, decisions = SequenceRandom([1 if hit else 10, 10, 10, 7]), Mock()
                with (
                    patch.object(consumption, "execute_prepared_ranged_weapon_attack", wraps=consumption.execute_prepared_ranged_weapon_attack) as execute,
                    patch.object(consumption, "consume_prepared_attack_lost_aim", wraps=consumption.consume_prepared_attack_lost_aim) as register,
                    patch("towr.rules.attack_action_execution.resolve_kernel_attack", wraps=resolve_kernel_attack) as kernel,
                    patch("towr.rules.ranged_weapon_attack_preparation.prepare_ranged_weapon_attack") as prepare,
                ):
                    result = consumption.execute_registered_aim_loss_prepared_attack(source, rng, decisions=decisions)
                execute.assert_called_once_with(source.prepared_attack, rng, decisions=decisions)
                register.assert_called_once_with(result.registration.source_request)
                kernel.assert_called_once()
                prepare.assert_not_called()
                self.assertIs(result.execution, result.registration.source_request.execution)
                self.assertIs(result.execution.source_request, source.prepared_attack)
                self.assertIs(result.state, result.registration.state)
                self.assertIs(result.registration.previous_state, source.state)
                self.assertEqual(result.state.consumed_aim_source_ids, ("source:older", "aim:execute"))
                self.assertEqual(result.state.consumed_aim_follow_up_ids,
                    (*source.state.consumed_aim_follow_up_ids, source.follow_up.request_id))
                self.assertEqual(result.execution.consumed_aim_follow_up_ids, source.state.consumed_aim_follow_up_ids)
                ranged = result.execution.ranged_attack
                attack = ranged.attack
                self.assertIs(attack.resolution.attack.outcome, AttackOutcome.HIT if hit else AttackOutcome.MISS)
                self.assertEqual(attack.resolution.attack.attacker_test.trace.rolled_dice, 3)
                self.assertEqual(attack.resolution.attack.attacker_test.trace.regular_dice_delta, 0)
                self.assertEqual(attack.slot.execution.id, source.follow_up.attack.id)
                old_slots = source.follow_up.attack.state.active_turn.action_slots
                new_slots = attack.state.active_turn.action_slots
                self.assertEqual(new_slots[:-1], old_slots[:-1])
                self.assertEqual(sum(s.executed for s in new_slots), sum(s.executed for s in old_slots) + 1)
                if weapon is RangedWeaponId.LONGBOW:
                    self.assertIs(ranged.weapon_state, ranged.previous_weapon_state)
                else:
                    self.assertFalse(ranged.weapon_state.loaded)
                    self.assertEqual(ranged.weapon_state.reload_cycle_ids, ("reload:loss",))
                self.assertEqual(result.applied_rule_ids, tuple(dict.fromkeys((
                    source.rule_id, *result.registration.applied_rule_ids))))
                self.assertTrue(set(source.prepared_attack.preparation.applied_rule_ids) <= set(result.applied_rule_ids))
                self.assertEqual(rng.randint(1, 10), 7)
                self.assertEqual(source, before)
                with self.assertRaises(FrozenInstanceError):
                    result.state = source.state

    def test_profile_modifier_survives_once(self):
        source = request(weapon=RangedWeaponId.LONGBOW, outside=True)
        rng = SequenceRandom([10, 10, 7])
        result = consumption.execute_registered_aim_loss_prepared_attack(source, rng)
        trace = result.execution.ranged_attack.attack.resolution.attack.attacker_test.trace
        self.assertEqual(trace.rolled_dice, 2)
        self.assertEqual(trace.regular_dice_delta, -1)
        self.assertIn(OUTSIDE_OPTIMUM_RANGE_RULE_ID, result.applied_rule_ids)
        self.assertEqual(rng.randint(1, 10), 7)

    def test_shared_history_and_renamed_replay_rejected_before_rng(self):
        source = request()
        result = consumption.execute_registered_aim_loss_prepared_attack(source, SequenceRandom([10] * 3))
        histories = (
            result.state,
            consumption.consume_prepared_attack_lost_aim(completed_request()).state,
            consumption.consume_ranged_attack_lost_aim(ranged_request()).state,
            consumption.consume_lost_aim(non_attack_request()).state,
            consumption.register_aim_ranged_attack(applied_request()).state,
        )
        for candidate, history in product((source, request(renamed=True)), histories):
            rng, decisions = Mock(), Mock()
            with self.subTest(history=history), patch.object(consumption, "execute_prepared_ranged_weapon_attack") as execute:
                with self.assertRaisesRegex(ValueError, "source was already consumed"):
                    consumption.execute_registered_aim_loss_prepared_attack(
                        replace(candidate, id="wrapper:renamed", state=history), rng, decisions=decisions)
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])
            self.assertEqual(decisions.mock_calls, [])

    def test_ordered_prepared_history_guard_before_rng(self):
        source = request()
        for history in ((), ("foreign",), tuple(reversed(source.state.consumed_aim_follow_up_ids))):
            rng = Mock()
            with self.subTest(history=history), patch.object(consumption, "execute_prepared_ranged_weapon_attack") as execute:
                with self.assertRaisesRegex(ValueError, "stale follow-up history"):
                    consumption.execute_registered_aim_loss_prepared_attack(replace(
                        source, prepared_attack=replace(source.prepared_attack, consumed_aim_follow_up_ids=history)), rng)
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])

    def test_actor_exact_final_attack_and_slot_binding_before_rng(self):
        source = request()
        attack = source.follow_up.attack
        raw = source.prepared_attack.preparation.source_request.attack
        changed = replace(attack, kernel_request=replace(attack.kernel_request, id="other"))
        turn = raw.state.active_turn
        slot = replace(turn.action_slots[-1], declaration=CombatActionDeclaration(CombatActionKind.RECOVER))
        wrong_slot = replace(raw, state=replace(raw.state,
            active_turn=replace(turn, action_slots=(*turn.action_slots[:-1], slot))))
        preparation = prepare_ranged_weapon_attack(replace(source.prepared_attack.preparation.source_request, attack=wrong_slot))
        cases = [
            {"state": replace(source.state, actor_id="other")},
            {"state": replace(source.state, consumed_aim_follow_up_ids=(source.follow_up.request_id,))},
            {"prepared_attack": replace(source.prepared_attack, preparation=preparation),
             "follow_up": resolve_aim_follow_up(replace(source.follow_up.source_request, attack=preparation.execution.attack))},
        ]
        for candidate in (raw, changed):
            cases.append({"follow_up": resolve_aim_follow_up(replace(source.follow_up.source_request, attack=candidate))})
        for changes in cases:
            rng = Mock()
            with self.subTest(changes=changes), patch.object(consumption, "execute_prepared_ranged_weapon_attack") as execute:
                with self.assertRaises(ValueError):
                    consumption.execute_registered_aim_loss_prepared_attack(replace(source, **changes), rng)
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])

    def test_chronology_and_applied_branch_remain_closed_before_rng(self):
        source = request()
        pending = source.follow_up.source_request.aim.source_request
        future = execute_aim_action(replace(pending, round_state=replace(pending.round_state, round_number=2)), SequenceRandom([1, 2, 10]))
        cases = [
            (resolve_aim_follow_up(replace(source.follow_up.source_request, aim=future)), source.prepared_attack),
            (non_attack_request().follow_up, source.prepared_attack),
            pending_prepared(later_round=2, later_second=True),
            pending_prepared(target="enemy"),
            pending_prepared(target="enemy", prepared_aim=True),
            pending_prepared(skill=Skill.THROWING),
        ]
        for follow, prepared in cases:
            rng = Mock()
            with self.subTest(follow=follow), patch.object(consumption, "execute_prepared_ranged_weapon_attack") as execute:
                with self.assertRaises(ValueError):
                    consumption.execute_registered_aim_loss_prepared_attack(
                        replace(source, follow_up=follow, prepared_attack=prepared), rng)
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])

    def test_runtime_rechecks_preflight_before_executor(self):
        source, rng = request(), Mock()
        with (
            patch.object(consumption, "_validate_prepared_attack_loss_preflight", side_effect=ValueError("preflight failed")) as check,
            patch.object(consumption, "execute_prepared_ranged_weapon_attack") as execute,
        ):
            with self.assertRaisesRegex(ValueError, "preflight failed"):
                consumption.execute_registered_aim_loss_prepared_attack(source, rng)
        check.assert_called_once_with(source.state, source.follow_up, source.prepared_attack)
        execute.assert_not_called()
        self.assertEqual(rng.mock_calls, [])

    def test_rng_and_registration_failures_preserve_snapshots_without_rng_rollback(self):
        source, rng = request(), Mock()
        before = deepcopy(source)
        rng.randint.side_effect = [1, RuntimeError("RNG failed")]
        with patch.object(consumption, "consume_prepared_attack_lost_aim") as register:
            with self.assertRaisesRegex(RuntimeError, "RNG failed"):
                consumption.execute_registered_aim_loss_prepared_attack(source, rng)
        register.assert_not_called()
        self.assertEqual(rng.randint.call_count, 2)
        self.assertEqual(source, before)
        for stage in ("consume_prepared_attack_lost_aim", "RegisteredAimLossPreparedAttackExecutionResult"):
            rng = SequenceRandom([10, 10, 10, 7])
            with self.subTest(stage=stage), patch.object(consumption, stage, side_effect=RuntimeError("stage failed")):
                with self.assertRaisesRegex(RuntimeError, "stage failed"):
                    consumption.execute_registered_aim_loss_prepared_attack(source, rng)
            self.assertEqual(rng.randint(1, 10), 7)
            self.assertEqual(source, before)

    def test_result_cannot_rebind_preparation_weapon_cycle_or_trace(self):
        source = request()
        result = consumption.execute_registered_aim_loss_prepared_attack(source, SequenceRandom([10] * 3))
        other = consumption.execute_registered_aim_loss_prepared_attack(request(renamed=True), SequenceRandom([10] * 3))
        prepared = source.prepared_attack
        raw = prepared.preparation.source_request
        altered_sources = [
            replace(source, prepared_attack=replace(prepared, id="prepared:other")),
            replace(source, id="other"),
            replace(source, state=replace(source.state, consumed_aim_source_ids=("other",))),
        ]
        for change in (
            {"id": "prepare:other"}, {"next_reload_cycle_id": "cycle:other"},
            {"weapon_state": replace(raw.weapon_state, weapon_instance_id="other")},
            {"attacker_strength": raw.attacker_strength + 1},
        ):
            new_preparation = prepare_ranged_weapon_attack(replace(raw, **change))
            altered_sources.append(replace(source, prepared_attack=replace(prepared, preparation=new_preparation)))
        for changes in (
            {"request_id": "other"}, {"rule_id": "other"}, {"source_request": None},
            {"registration": None}, {"registration": other.registration},
            {"applied_rule_ids": ()}, {"applied_rule_ids": (*result.applied_rule_ids, "extra")},
            *({"source_request": candidate} for candidate in altered_sources),
        ):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(result, **changes)

    def test_types_and_next_preparation_with_returned_history(self):
        source = request()
        for changes in ({"id": ""}, {"rule_id": "other"}, {"state": None}, {"follow_up": None}, {"prepared_attack": None}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(source, **changes)
        with self.assertRaises(TypeError):
            consumption.execute_registered_aim_loss_prepared_attack(None, Mock())
        result = consumption.execute_registered_aim_loss_prepared_attack(source, SequenceRandom([10] * 3))
        aim = source.follow_up.source_request.aim
        raw = source.prepared_attack.preparation.source_request.attack
        next_attack = replace(raw, id="attack:next", target_id=aim.bonus.target_id,
            kernel_request=replace(raw.kernel_request, target_id=aim.bonus.target_id))
        candidate = replace(preparation_request(RangedWeaponId.LONGBOW, attack=next_attack, aim=aim), id="prepare:next")
        with self.assertRaisesRegex(ValueError, "source was already consumed"):
            prepare_ranged_weapon_attack_with_aim_history(result.state, candidate)
