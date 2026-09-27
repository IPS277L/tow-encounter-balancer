from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_aim_attack_loss_consumption import pending_inputs, request as ordinary_loss
from tests.unit.test_k1_aim_ranged_attack_loss_consumption import request as ranged_loss
from tests.unit.test_k1_aim_consumption_resolution import request as non_attack_loss
from tests.unit.test_k1_aim_attack_consumption import request as applied_request
from tests.unit.test_k1_ranged_weapon_attack_preparation import preparation_request
from towr.domain.aim_consumption_models import (
    AimConsumptionState, RegisteredAimLossRangedAttackExecutionRequest,
)
from towr.domain.attack_models import AttackOutcome
from towr.domain.ranged_weapon_attack_models import RangedWeaponAttackExecutionRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponId, ranged_weapon_reload_profile
from towr.domain.reload_models import create_initial_ranged_weapon_reload_state
from towr.domain.test_models import Skill
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind
from towr.rules import aim_consumption_resolution as consumption
from towr.rules.aim_resolution import execute_aim_action, resolve_aim_follow_up
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack_with_aim_history


def request(*, weapon=RangedWeaponId.CROSSBOW, optional=False, **kwargs):
    follow_up, attack = pending_inputs(**kwargs)
    if optional:
        test = attack.kernel_request.attack.attacker_test
        test = replace(test, dice_modifiers=(*test.dice_modifiers,
            ranged_weapon_reload_profile(weapon).optional_bonus_modifier()))
        attack = replace(attack, kernel_request=replace(attack.kernel_request,
            attack=replace(attack.kernel_request.attack, attacker_test=test)))
        follow_up = resolve_aim_follow_up(replace(follow_up.source_request, attack=attack))
    suffix = "new" if kwargs.get("renamed") else "loss"
    ranged = RangedWeaponAttackExecutionRequest(
        f"ranged:{suffix}", Skill.SHOOTING, attack,
        create_initial_ranged_weapon_reload_state("hero:weapon", weapon),
        f"reload:{suffix}" if weapon is RangedWeaponId.CROSSBOW or optional else None,
        uses_optional_reload_bonus=optional,
    )
    return RegisteredAimLossRangedAttackExecutionRequest(
        "registered:loss", AimConsumptionState("hero", ("source:older",), ("follow:older",)),
        follow_up, ranged,
    )


class K1RegisteredAimLossRangedAttackTests(unittest.TestCase):
    def test_free_and_crossbow_hit_miss_aim_and_turn_execute_once(self):
        for weapon, values, hit, later in product(
            (RangedWeaponId.LONGBOW, RangedWeaponId.CROSSBOW),
            ((1, 2, 10), (10, 10, 10)), (False, True), (None, 2),
        ):
            with self.subTest(weapon=weapon, values=values, hit=hit, later=later):
                source = request(weapon=weapon, values=values, later_round=later)
                before = deepcopy(source)
                rng, decisions = SequenceRandom([1 if hit else 10, 10, 10, 7]), Mock()
                with (
                    patch.object(consumption, "execute_ranged_weapon_attack", wraps=consumption.execute_ranged_weapon_attack) as execute,
                    patch.object(consumption, "consume_ranged_attack_lost_aim", wraps=consumption.consume_ranged_attack_lost_aim) as register,
                    patch("towr.rules.attack_action_execution.resolve_kernel_attack", wraps=resolve_kernel_attack) as kernel,
                ):
                    result = consumption.execute_registered_aim_loss_ranged_attack(source, rng, decisions=decisions)
                execute.assert_called_once_with(source.ranged_attack, rng, decisions=decisions)
                register.assert_called_once_with(result.registration.source_request)
                kernel.assert_called_once()
                self.assertIs(result.execution, result.registration.source_request.execution)
                self.assertIs(result.execution.source_request, source.ranged_attack)
                self.assertIs(result.state, result.registration.state)
                self.assertIs(result.registration.previous_state, source.state)
                self.assertEqual(result.state.consumed_aim_source_ids, ("source:older", "aim:execute"))
                self.assertEqual(result.state.consumed_aim_follow_up_ids, ("follow:older", source.follow_up.request_id))
                attack = result.execution.attack
                self.assertEqual(attack.resolution.attack.outcome, AttackOutcome.HIT if hit else AttackOutcome.MISS)
                self.assertEqual(attack.resolution.attack.attacker_test.trace.rolled_dice, 3)
                self.assertEqual(attack.resolution.attack.attacker_test.trace.regular_dice_delta, 0)
                old_slots = source.ranged_attack.attack.state.active_turn.action_slots
                new_slots = attack.state.active_turn.action_slots
                self.assertEqual(new_slots[:-1], old_slots[:-1])
                self.assertEqual(sum(s.executed for s in new_slots), sum(s.executed for s in old_slots) + 1)
                self.assertEqual(attack.slot.execution.id, source.ranged_attack.attack.id)
                if weapon is RangedWeaponId.LONGBOW:
                    self.assertIs(result.execution.weapon_state, source.ranged_attack.weapon_state)
                else:
                    self.assertFalse(result.execution.weapon_state.loaded)
                    self.assertEqual(result.execution.weapon_state.reload_cycle_ids, ("reload:loss",))
                self.assertEqual(result.applied_rule_ids, tuple(dict.fromkeys((
                    source.rule_id, *result.registration.applied_rule_ids))))
                self.assertEqual(rng.randint(1, 10), 7)
                self.assertEqual(source, before)
                with self.assertRaises(FrozenInstanceError):
                    result.state = source.state

    def test_optional_repeater_bonus_retains_its_profile_and_reload_trigger(self):
        for optional in (False, True):
            with self.subTest(optional=optional):
                source = request(weapon=RangedWeaponId.REPEATER_CROSSBOW, optional=optional)
                rng = SequenceRandom([10] * (3 + int(optional)) + [7])
                result = consumption.execute_registered_aim_loss_ranged_attack(source, rng)
                self.assertEqual(result.execution.attack.resolution.attack.attacker_test.trace.regular_dice_delta, int(optional))
                self.assertEqual(result.execution.weapon_state.loaded, not optional)
                self.assertEqual(result.execution.weapon_state.reload_cycle_ids, ("reload:loss",) if optional else ())
                self.assertEqual(rng.randint(1, 10), 7)

    def test_shared_history_and_renamed_replay_fail_before_rng(self):
        source = request()
        result = consumption.execute_registered_aim_loss_ranged_attack(source, SequenceRandom([10] * 3))
        histories = (
            result.state,
            consumption.consume_lost_aim(non_attack_loss()).state,
            consumption.register_aim_ranged_attack(applied_request()).state,
            consumption.consume_attack_lost_aim(ordinary_loss()).state,
            consumption.consume_ranged_attack_lost_aim(ranged_loss()).state,
        )
        for candidate, history in product((source, request(renamed=True)), histories):
            rng, decisions = Mock(), Mock()
            with self.subTest(history=history), patch.object(consumption, "execute_ranged_weapon_attack") as execute:
                with self.assertRaisesRegex(ValueError, "source was already consumed"):
                    consumption.execute_registered_aim_loss_ranged_attack(
                        replace(candidate, id="wrapper:new", state=history), rng, decisions=decisions)
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])
            self.assertEqual(decisions.mock_calls, [])

    def test_actor_follow_up_exact_attack_and_slot_binding_before_rng(self):
        source = request()
        attack = source.ranged_attack.attack
        changed_profile = replace(attack, kernel_request=replace(attack.kernel_request,
            attack=replace(attack.kernel_request.attack, is_close_range=True)))
        turn = attack.state.active_turn
        slot = replace(turn.action_slots[-1], declaration=CombatActionDeclaration(CombatActionKind.RECOVER))
        wrong_slot = replace(attack, state=replace(attack.state,
            active_turn=replace(turn, action_slots=(*turn.action_slots[:-1], slot))))
        cases = [
            {"state": replace(source.state, actor_id="other")},
            {"state": replace(source.state, consumed_aim_follow_up_ids=(source.follow_up.request_id,))},
            {"follow_up": resolve_aim_follow_up(replace(source.follow_up.source_request, attack=wrong_slot)),
             "ranged_attack": replace(source.ranged_attack, attack=wrong_slot)},
        ]
        for changed in (replace(attack, id="other"), changed_profile,
                        replace(attack, kernel_request=replace(attack.kernel_request, id="other"))):
            cases.append({"ranged_attack": replace(source.ranged_attack, attack=changed)})
        for changes in cases:
            rng = Mock()
            with self.subTest(changes=changes), patch.object(consumption, "execute_ranged_weapon_attack") as execute:
                with self.assertRaises(ValueError):
                    consumption.execute_registered_aim_loss_ranged_attack(replace(source, **changes), rng)
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])

    def test_chronology_and_unsupported_follow_up_before_rng(self):
        source = request()
        pending = source.follow_up.source_request.aim.source_request
        future = execute_aim_action(replace(pending, round_state=replace(pending.round_state, round_number=2)),
                                   SequenceRandom([1, 2, 10]))
        earlier = resolve_aim_follow_up(replace(source.follow_up.source_request, aim=future))
        cases = (
            (earlier, source.ranged_attack.attack),
            (non_attack_loss().follow_up, source.ranged_attack.attack),
            pending_inputs(later_round=2, later_second=True),
            pending_inputs(target="enemy"),
            pending_inputs(target="enemy", skill=Skill.MELEE),
            pending_inputs(skill=Skill.THROWING),
        )
        for follow_up, attack in cases:
            rng = Mock()
            with self.subTest(follow_up=follow_up), patch.object(consumption, "execute_ranged_weapon_attack") as execute:
                with self.assertRaises(ValueError):
                    consumption.execute_registered_aim_loss_ranged_attack(replace(
                        source, follow_up=follow_up, ranged_attack=replace(source.ranged_attack, attack=attack)), rng)
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])

    def test_runtime_rechecks_shared_preflight_before_executor(self):
        source, rng = request(), Mock()
        with (
            patch.object(consumption, "_validate_ranged_attack_loss_preflight", side_effect=ValueError("preflight failed")) as check,
            patch.object(consumption, "execute_ranged_weapon_attack") as execute,
        ):
            with self.assertRaisesRegex(ValueError, "preflight failed"):
                consumption.execute_registered_aim_loss_ranged_attack(source, rng)
        check.assert_called_once_with(source.state, source.follow_up, source.ranged_attack)
        execute.assert_not_called()
        self.assertEqual(rng.mock_calls, [])

    def test_rng_failure_does_not_register_or_mutate_inputs(self):
        source, rng = request(), Mock()
        before = deepcopy(source)
        rng.randint.side_effect = [1, RuntimeError("RNG failed")]
        with patch.object(consumption, "consume_ranged_attack_lost_aim") as register:
            with self.assertRaisesRegex(RuntimeError, "RNG failed"):
                consumption.execute_registered_aim_loss_ranged_attack(source, rng)
        register.assert_not_called()
        self.assertEqual(rng.randint.call_count, 2)
        self.assertEqual(source, before)

    def test_registration_and_result_failure_preserve_inputs_without_rng_rollback(self):
        for stage in ("consume_ranged_attack_lost_aim", "RegisteredAimLossRangedAttackExecutionResult"):
            source, rng = request(), SequenceRandom([10, 10, 10, 7])
            before = deepcopy(source)
            with self.subTest(stage=stage), patch.object(consumption, stage, side_effect=RuntimeError("stage failed")):
                with self.assertRaisesRegex(RuntimeError, "stage failed"):
                    consumption.execute_registered_aim_loss_ranged_attack(source, rng)
            self.assertEqual(rng.randint(1, 10), 7)
            self.assertEqual(source, before)

    def test_result_cannot_rebind_source_weapon_cycle_history_or_trace(self):
        source = request()
        result = consumption.execute_registered_aim_loss_ranged_attack(source, SequenceRandom([10] * 3))
        other = consumption.execute_registered_aim_loss_ranged_attack(request(renamed=True), SequenceRandom([10] * 3))
        changes = [
            {"request_id": "other"}, {"rule_id": "other"}, {"source_request": None}, {"registration": None},
            {"registration": other.registration}, {"source_request": replace(source, id="other")},
            {"source_request": replace(source, state=replace(source.state, consumed_aim_source_ids=("different",)))},
            {"applied_rule_ids": ()}, {"applied_rule_ids": (*result.applied_rule_ids, "extra")},
        ]
        for ranged in (
            replace(source.ranged_attack, id="ranged:foreign"),
            replace(source.ranged_attack, next_reload_cycle_id="reload:foreign"),
            replace(source.ranged_attack, weapon_state=replace(source.ranged_attack.weapon_state, weapon_instance_id="other")),
        ):
            changes.append({"source_request": replace(source, ranged_attack=ranged)})
        for change in changes:
            with self.subTest(change=change), self.assertRaises((TypeError, ValueError)):
                replace(result, **change)

    def test_types_and_next_preparation_with_returned_history(self):
        source = request()
        for changes in ({"id": ""}, {"rule_id": "foreign"}, {"state": None}, {"follow_up": None}, {"ranged_attack": None}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(source, **changes)
        with self.assertRaises(TypeError):
            consumption.execute_registered_aim_loss_ranged_attack(None, Mock())
        result = consumption.execute_registered_aim_loss_ranged_attack(source, SequenceRandom([10] * 3))
        aim = source.follow_up.source_request.aim
        attack = source.ranged_attack.attack
        next_attack = replace(attack, id="attack:next", target_id=aim.bonus.target_id,
            kernel_request=replace(attack.kernel_request, target_id=aim.bonus.target_id))
        candidate = replace(preparation_request(RangedWeaponId.LONGBOW, attack=next_attack, aim=aim), id="prepare:new")
        with self.assertRaisesRegex(ValueError, "source was already consumed"):
            prepare_ranged_weapon_attack_with_aim_history(result.state, candidate)
