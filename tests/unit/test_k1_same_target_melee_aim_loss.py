from copy import deepcopy
from dataclasses import replace
from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_aim_attack_loss_consumption import request as completed_request
from tests.unit.test_k1_registered_aim_loss_attack import request as registered_request
from tests.unit.test_k1_ranged_weapon_attack_preparation import preparation_request
from towr.domain.aim_models import AimFollowUpOutcome
from towr.domain.attack_models import AttackOutcome
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.test_models import Skill
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind
from towr.rules import aim_consumption_resolution as consumption
from towr.rules.aim_resolution import resolve_aim_follow_up
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack_with_aim_history


def melee_request(**kwargs):
    return registered_request(target="enemy", skill=Skill.MELEE, **kwargs)


class K1SameTargetMeleeAimLossTests(unittest.TestCase):
    def test_completed_hit_miss_zero_positive_aim_consumes_once_without_execution(self):
        for values, hit in product(((10, 10, 10), (1, 2, 10)), (False, True)):
            with self.subTest(values=values, hit=hit):
                source = completed_request(target="enemy", skill=Skill.MELEE, values=values, hit=hit)
                before = deepcopy(source)
                with (
                    patch.object(consumption, "execute_attack_action") as execute,
                    patch("towr.rules.attack_action_execution.resolve_kernel_attack") as kernel,
                ):
                    result = consumption.consume_attack_lost_aim(source)
                execute.assert_not_called()
                kernel.assert_not_called()
                self.assertIs(result.source_request.execution, source.execution)
                self.assertIs(result.previous_state, source.state)
                self.assertIs(source.follow_up.outcome, AimFollowUpOutcome.LOST)
                self.assertIsNone(source.follow_up.modifier)
                self.assertEqual(source.execution.target_id, source.follow_up.source_request.aim.bonus.target_id)
                self.assertEqual(source.execution.resolution.attack.attacker_test.trace.regular_dice_delta, 0)
                self.assertIs(source.execution.resolution.attack.outcome, AttackOutcome.HIT if hit else AttackOutcome.MISS)
                self.assertEqual(result.state.consumed_aim_source_ids, ("source:older", "aim:execute"))
                self.assertEqual(result.state.consumed_aim_follow_up_ids, ("follow:older", "follow:prior", "follow:lost-attack"))
                self.assertTrue(set(source.execution.applied_rule_ids) <= set(result.applied_rule_ids))
                self.assertEqual(source, before)
                for candidate in (source, completed_request(target="enemy", skill=Skill.MELEE, renamed=True)):
                    with self.assertRaisesRegex(ValueError, "source was already consumed"):
                        consumption.consume_attack_lost_aim(replace(candidate, id="consume:new", state=result.state))

    def test_atomic_same_turn_and_later_turn_have_one_kernel_receipt_and_registration(self):
        for values, hit, later in product(((10, 10, 10), (1, 2, 10)), (False, True), (None, 2)):
            with self.subTest(values=values, hit=hit, later=later):
                source = melee_request(values=values, later_round=later)
                before = deepcopy(source)
                rng = SequenceRandom([1 if hit else 10, 10, 10, 7])
                with (
                    patch.object(consumption, "execute_attack_action", wraps=consumption.execute_attack_action) as execute,
                    patch.object(consumption, "consume_attack_lost_aim", wraps=consumption.consume_attack_lost_aim) as register,
                    patch("towr.rules.attack_action_execution.resolve_kernel_attack", wraps=resolve_kernel_attack) as kernel,
                ):
                    result = consumption.execute_registered_aim_loss_attack(source, rng)
                execute.assert_called_once_with(source.attack, rng, decisions=None)
                kernel.assert_called_once()
                register.assert_called_once_with(result.registration.source_request)
                self.assertIs(result.execution, result.registration.source_request.execution)
                self.assertIs(result.registration.previous_state, source.state)
                self.assertEqual(result.state.consumed_aim_source_ids, ("source:older", "aim:execute"))
                self.assertEqual(result.state.consumed_aim_follow_up_ids, ("follow:older", "follow:prior", "follow:lost-attack"))
                self.assertEqual(result.execution.resolution.attack.attacker_test.trace.rolled_dice, 3)
                self.assertEqual(result.execution.resolution.attack.attacker_test.trace.regular_dice_delta, 0)
                self.assertIs(result.execution.resolution.attack.outcome, AttackOutcome.HIT if hit else AttackOutcome.MISS)
                self.assertEqual(result.execution.state.active_turn.action_slots[:-1], source.attack.state.active_turn.action_slots[:-1])
                self.assertTrue(result.execution.slot.executed)
                self.assertEqual(result.execution.slot.execution.id, source.attack.id)
                self.assertTrue(set(result.registration.applied_rule_ids) <= set(result.applied_rule_ids))
                self.assertEqual(rng.randint(1, 10), 7)
                self.assertEqual(source, before)

    def test_renamed_replay_is_blocked_across_same_and_different_target_paths_before_rng(self):
        for first in (melee_request(), registered_request()):
            history = consumption.execute_registered_aim_loss_attack(first, SequenceRandom([10] * 3)).state
            for candidate in (melee_request(), melee_request(renamed=True), registered_request(renamed=True)):
                rng, decisions = Mock(), Mock()
                with self.subTest(first=first.attack.target_id, next=candidate.attack.target_id), patch.object(consumption, "execute_attack_action") as execute:
                    with self.assertRaisesRegex(ValueError, "source was already consumed"):
                        consumption.execute_registered_aim_loss_attack(
                            replace(candidate, id="registered:new", state=history), rng, decisions=decisions,
                        )
                execute.assert_not_called()
                self.assertEqual(rng.mock_calls, [])
                self.assertEqual(decisions.mock_calls, [])

    def test_exact_attack_actor_history_slot_and_chronology_guards_still_apply(self):
        source = melee_request()
        for changes in (
            {"state": replace(source.state, actor_id="other")},
            {"state": replace(source.state, consumed_aim_follow_up_ids=(source.follow_up.request_id,))},
            {"attack": replace(source.attack, id="other")},
            {"attack": replace(source.attack, kernel_request=replace(source.attack.kernel_request, id="other"))},
        ):
            rng = Mock()
            with self.subTest(changes=changes), patch.object(consumption, "execute_attack_action") as execute:
                with self.assertRaises(ValueError):
                    consumption.execute_registered_aim_loss_attack(replace(source, **changes), rng)
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])
        with self.assertRaisesRegex(ValueError, "first slot"):
            melee_request(later_round=2, later_second=True)
        with self.assertRaisesRegex(ValueError, "must follow Aim"):
            melee_request(later_round=1)
        turn = source.attack.state.active_turn
        attack = replace(source.attack, state=replace(source.attack.state, active_turn=replace(
            turn, action_slots=(*turn.action_slots[:-1], replace(
                turn.action_slots[-1], declaration=CombatActionDeclaration(CombatActionKind.RECOVER),
            )),
        )))
        follow = resolve_aim_follow_up(replace(source.follow_up.source_request, attack=attack))
        with self.assertRaisesRegex(ValueError, "slot does not match"):
            replace(source, attack=attack, follow_up=follow)

    def test_completed_receipt_and_kernel_cannot_be_rebound(self):
        source = completed_request(target="enemy", skill=Skill.MELEE)
        for execution in (
            completed_request(target="enemy", skill=Skill.MELEE, renamed=True).execution,
            completed_request().execution,
        ):
            with self.subTest(execution=execution), self.assertRaisesRegex(ValueError, "does not match"):
                replace(source, execution=execution)
        with self.assertRaises(ValueError):
            replace(source, execution=replace(source.execution, slot=replace(source.execution.slot,
                execution=replace(source.execution.slot.execution, id="receipt:other"))))

    def test_returned_history_blocks_ranged_preparation_for_the_original_target(self):
        source = melee_request()
        result = consumption.execute_registered_aim_loss_attack(source, SequenceRandom([10] * 3))
        candidate = replace(preparation_request(
            RangedWeaponId.LONGBOW, aim=source.follow_up.source_request.aim,
            attack=replace(source.attack, id="attack:ranged:new"),
        ), id="prepare:new")
        with patch("towr.rules.ranged_weapon_attack_preparation.prepare_ranged_weapon_attack") as prepare:
            with self.assertRaisesRegex(ValueError, "source was already consumed"):
                prepare_ranged_weapon_attack_with_aim_history(result.state, candidate)
        prepare.assert_not_called()


if __name__ == "__main__":
    unittest.main()
