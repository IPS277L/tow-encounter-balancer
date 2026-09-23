from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from itertools import product
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_aim_resolution import active_round, aim_request, attack_execution_request, reserve_action
from tests.unit.test_k1_aim_consumption_resolution import request as non_attack_request
from tests.unit.test_k1_aim_attack_consumption import request as applied_request
from tests.unit.test_k1_aim_attack_loss_consumption import request as attack_loss_request
from tests.unit.test_k1_charge_action_execution import (
    charge_declaration, request as charge_request, reserve_action as reserve_charge, spatial_state,
)
from tests.unit.test_k1_ranged_weapon_attack_preparation import preparation_request
from towr.domain.aim_consumption_models import (
    AIM_CHARGE_LOSS_CONSUMPTION_RULE_ID, AimChargeLossConsumptionRequest, AimConsumptionState,
)
from towr.domain.aim_models import AimFollowUpOutcome, AimFollowUpRequest
from towr.domain.attack_models import AttackOutcome
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.test_models import Skill
from towr.domain.turn_models import ActionSlotGrant, CombatActionKind, CombatRoundState, CombatTurnStartRequest
from towr.rules import aim_consumption_resolution as consumption
from towr.rules.aim_resolution import execute_aim_action, resolve_aim_follow_up
from towr.rules.charge_action_execution import execute_charge_action
from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack_with_aim_history
from towr.rules.turn_resolution import start_combat_turn


def pending_inputs(*, values=(1, 2, 10), renamed=False, later_round=None, later_second=False,
            aim_target="enemy", skill=Skill.MELEE):
    aim = execute_aim_action(aim_request(reserve_action(active_round(), CombatActionKind.AIM),
                                       target_id=aim_target), SequenceRandom(values))
    turn, slot = aim.round_state, 2
    if later_round is not None:
        turn = start_combat_turn(CombatTurnStartRequest("turn:later", CombatRoundState(
            round_number=later_round, participants=turn.participants), "hero")).state
        slot = 1
        if later_second:
            turn = execute_aim_action(replace(aim_request(reserve_action(turn, CombatActionKind.AIM)),
                id="aim:intervening"), SequenceRandom([10] * 3)).round_state
            slot = 2
    turn = reserve_charge(turn, charge_declaration(),
                          grant=ActionSlotGrant.ABILITY if slot == 2 else ActionSlotGrant.STANDARD)
    pending = charge_request(round_state=turn, slot_index=slot, attack_skill=skill,
                             state=replace(spatial_state(), round_number=turn.round_number))
    if renamed:
        pending = replace(pending, id="charge:new", kernel_request=replace(pending.kernel_request, id="kernel:new"))
    follow = resolve_aim_follow_up(AimFollowUpRequest(
        "follow:new" if renamed else "follow:charge", aim, "hero", pending.id, charge_declaration(),
    ))
    return follow, pending


def request(*, hit=False, **kwargs):
    follow, pending = pending_inputs(**kwargs)
    rng = SequenceRandom([1 if hit else 10, *([10] if pending.attack_skill is Skill.MELEE else []), 7])
    execution = execute_charge_action(pending, rng)
    assert rng.randint(1, 10) == 7
    return AimChargeLossConsumptionRequest(
        "consume:charge", AimConsumptionState("hero", ("source:older",), ("follow:older", "follow:prior")),
        follow, execution,
    )


class K1AimChargeLossConsumptionTests(unittest.TestCase):
    def test_hit_miss_aim_zero_positive_and_same_different_targets_preserve_single_charge(self):
        for values, hit, target in product(((10, 10, 10), (1, 2, 10)), (False, True), ("enemy", "enemy:other")):
            with self.subTest(values=values, hit=hit, aim_target=target):
                source = request(values=values, hit=hit, aim_target=target)
                before = deepcopy(source)
                with (
                    patch("towr.rules.charge_action_execution.execute_charge_action") as execute,
                    patch("towr.rules.charge_action_execution.resolve_kernel_attack") as kernel,
                    patch("towr.rules.aim_resolution.resolve_aim_follow_up") as follow,
                ):
                    result = consumption.consume_charge_lost_aim(source)
                execute.assert_not_called()
                kernel.assert_not_called()
                follow.assert_not_called()
                self.assertIs(result.source_request.execution, source.execution)
                self.assertIs(result.previous_state, source.state)
                self.assertIs(source.follow_up.outcome, AimFollowUpOutcome.LOST)
                self.assertIsNone(source.follow_up.modifier)
                self.assertEqual(result.state.consumed_aim_source_ids, ("source:older", "aim:execute"))
                self.assertEqual(result.state.consumed_aim_follow_up_ids, ("follow:older", "follow:prior", "follow:charge"))
                execution = result.source_request.execution
                self.assertIs(execution.resolution.attack.outcome, AttackOutcome.HIT if hit else AttackOutcome.MISS)
                self.assertEqual(execution.resolution.attack.attacker_test.trace.rolled_dice, 2)
                self.assertEqual(execution.resolution.attack.attacker_test.trace.regular_dice_delta, 1)
                self.assertEqual(execution.melee_bonus.amount, 1)
                self.assertEqual(execution.previous_spatial_state.placement_for("hero").zone_id, "zone:a")
                self.assertEqual(execution.spatial_state.placement_for("hero").zone_id, "zone:b")
                self.assertEqual(execution.slot.execution.id, execution.request_id)
                expected = tuple(dict.fromkeys((AIM_CHARGE_LOSS_CONSUMPTION_RULE_ID,
                    *source.follow_up.source_request.aim.applied_rule_ids, *source.follow_up.applied_rule_ids,
                    *execution.applied_rule_ids)))
                self.assertEqual(result.applied_rule_ids, expected)
                self.assertEqual(source, before)
                with self.assertRaises(FrozenInstanceError):
                    result.state = source.state

    def test_source_and_follow_up_replay_with_new_charge_ids(self):
        source = request()
        history = consumption.consume_charge_lost_aim(source).state
        for candidate in (source, request(renamed=True)):
            with self.assertRaisesRegex(ValueError, "source was already consumed"):
                replace(candidate, id="consume:new", state=history)
        with self.assertRaisesRegex(ValueError, "follow-up was already consumed"):
            replace(source, state=replace(source.state, consumed_aim_follow_up_ids=(source.follow_up.request_id,)))

    def test_shared_history_with_non_attack_attack_lost_and_applied(self):
        source = request()
        histories = (
            consumption.consume_lost_aim(non_attack_request()).state,
            consumption.consume_attack_lost_aim(attack_loss_request()).state,
            consumption.register_aim_ranged_attack(applied_request()).state,
        )
        for history in histories:
            with self.assertRaisesRegex(ValueError, "source was already consumed"):
                replace(source, state=history)
        history = consumption.consume_charge_lost_aim(source).state
        for other in (non_attack_request(), attack_loss_request()):
            with self.assertRaisesRegex(ValueError, "source was already consumed"):
                replace(other, state=history)

    def test_actor_action_and_receipt_binding(self):
        source = request()
        for changes in (
            {"state": replace(source.state, actor_id="other")},
            {"execution": request(renamed=True).execution},
            {"follow_up": resolve_aim_follow_up(replace(source.follow_up.source_request, next_action_id="other"))},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(source, **changes)
        for changes in ({"actor_id": "other"}, {"round_number": 2}, {"executor_rule_id": "foreign"}):
            with self.subTest(receipt=changes), self.assertRaises(ValueError):
                execution = source.execution
                receipt = replace(execution.slot.execution, **changes)
                slot = replace(execution.slot, execution=receipt)
                turn = execution.round_state.active_turn
                changed = replace(execution, slot=slot, round_state=replace(execution.round_state,
                    active_turn=replace(turn, action_slots=(*turn.action_slots[:-1], slot))))
                replace(source, execution=changed)

    def test_same_turn_later_first_slot_and_invalid_chronology(self):
        for later in (None, 2, 5):
            consumption.consume_charge_lost_aim(request(later_round=later))
        with self.assertRaisesRegex(ValueError, "must follow Aim"):
            request(later_round=1)
        with self.assertRaisesRegex(ValueError, "first slot"):
            request(later_round=2, later_second=True)

    def test_unsupported_follow_ups_skills_and_old_consumers_remain_closed(self):
        source = request()
        for follow in (non_attack_request().follow_up, applied_request().execution.source_request.aim_follow_up,
                       attack_loss_request().follow_up):
            with self.assertRaisesRegex(ValueError, "requires LOST|Charge follow-up"):
                replace(source, follow_up=follow)
        with self.assertRaisesRegex(ValueError, "requires Melee"):
            request(skill=Skill.BRAWN)
        with self.assertRaisesRegex(ValueError, "non-attacking"):
            replace(non_attack_request(), follow_up=source.follow_up, action=source.execution.slot.execution)
        with self.assertRaises(TypeError):
            replace(attack_loss_request(), follow_up=source.follow_up, execution=source.execution)

    def test_returned_history_rejects_preparation_with_renamed_ids(self):
        source = request()
        result = consumption.consume_charge_lost_aim(source)
        candidate = replace(preparation_request(RangedWeaponId.LONGBOW,
            attack=replace(attack_execution_request(), id="attack:new"),
            aim=source.follow_up.source_request.aim), id="prepare:new")
        with patch("towr.rules.ranged_weapon_attack_preparation.prepare_ranged_weapon_attack") as prepare:
            with self.assertRaisesRegex(ValueError, "source was already consumed"):
                prepare_ranged_weapon_attack_with_aim_history(result.state, candidate)
        prepare.assert_not_called()

    def test_types_result_provenance_history_and_trace(self):
        source = request()
        for changes in ({"id": ""}, {"rule_id": "foreign"}, {"state": None}, {"follow_up": None},
                        {"execution": None}, {"execution": source.execution.slot.execution}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(source, **changes)
        with self.assertRaises(TypeError):
            consumption.consume_charge_lost_aim(None)
        result = consumption.consume_charge_lost_aim(source)
        for changes in ({"request_id": "other"}, {"rule_id": "other"}, {"source_request": None},
                        {"source_request": replace(source, id="other")}, {"previous_state": result.state},
                        {"state": source.state}, {"state": replace(result.state, actor_id="other")},
                        {"applied_rule_ids": ()}, {"applied_rule_ids": (*result.applied_rule_ids, "foreign")}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(result, **changes)

    def test_result_failure_leaves_input_snapshots_unchanged(self):
        source = request()
        before = deepcopy(source)
        with patch.object(consumption, "AimChargeLossConsumptionResult", side_effect=RuntimeError("failed")):
            with self.assertRaisesRegex(RuntimeError, "failed"):
                consumption.consume_charge_lost_aim(source)
        self.assertEqual(source, before)


if __name__ == "__main__":
    unittest.main()
