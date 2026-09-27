from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from itertools import product
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_aim_attack_loss_consumption import pending_inputs, request as ordinary_request
from tests.unit.test_k1_aim_ranged_attack_loss_consumption import request as ranged_request
from tests.unit.test_k1_aim_consumption_resolution import request as non_attack_request
from tests.unit.test_k1_aim_attack_consumption import request as applied_request
from tests.unit.test_k1_ranged_weapon_attack_preparation import preparation_request
from towr.domain.aim_consumption_models import (
    AIM_PREPARED_ATTACK_LOSS_CONSUMPTION_RULE_ID, AimConsumptionState,
    AimPreparedAttackLossConsumptionRequest,
)
from towr.domain.attack_models import AttackOutcome, ResilienceProfile
from towr.domain.prepared_ranged_weapon_attack_models import PreparedRangedWeaponAttackExecutionRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponId, RangedWeaponRange
from towr.domain.ranged_weapon_attack_preparation_models import OUTSIDE_OPTIMUM_RANGE_RULE_ID
from towr.domain.test_models import Skill
from towr.rules import aim_consumption_resolution as consumption
from towr.rules.aim_resolution import execute_aim_action, resolve_aim_follow_up
from towr.rules.prepared_ranged_weapon_attack_resolution import execute_prepared_ranged_weapon_attack
from towr.rules.ranged_weapon_attack_preparation import (
    prepare_ranged_weapon_attack, prepare_ranged_weapon_attack_with_aim_history,
)


def pending_prepared(*, weapon=RangedWeaponId.CROSSBOW, outside=False, prepared_aim=False,
           history=("follow:older", "follow:prior"), **kwargs):
    follow, attack = pending_inputs(**kwargs)
    attack = replace(attack, kernel_request=replace(attack.kernel_request,
        attack=replace(attack.kernel_request.attack, impact_spec=replace(
            attack.kernel_request.attack.impact_spec, resilience=ResilienceProfile(toughness=20, bonus=1)))))
    suffix = "new" if kwargs.get("renamed") else "loss"
    preparation = prepare_ranged_weapon_attack(replace(preparation_request(
        weapon, attack=attack, aim=follow.source_request.aim if prepared_aim else None,
        target_range=RangedWeaponRange.SHORT if outside else RangedWeaponRange.MEDIUM,
        next_cycle=f"reload:{suffix}" if weapon is RangedWeaponId.CROSSBOW else None),
        id=f"prepare:{suffix}"))
    follow = preparation.aim_follow_up if prepared_aim else resolve_aim_follow_up(
        replace(follow.source_request, attack=preparation.execution.attack))
    source = PreparedRangedWeaponAttackExecutionRequest(f"prepared:{suffix}", preparation, history)
    return follow, source


def inputs(*, hit=False, **kwargs):
    follow, source = pending_prepared(**kwargs)
    bonus = follow.modifier.amount if kwargs.get("prepared_aim") and follow.modifier else 0
    dice = 3 - int(kwargs.get("outside", False)) + bonus
    rng = SequenceRandom([1 if hit else 10, *([10] * (dice - 1)), 7])
    execution = execute_prepared_ranged_weapon_attack(source, rng)
    assert rng.randint(1, 10) == 7
    return follow, execution


def request(**kwargs):
    follow, execution = inputs(**kwargs)
    return AimPreparedAttackLossConsumptionRequest("consume:prepared-loss",
        AimConsumptionState("hero", ("source:older",), execution.previous_consumed_aim_follow_up_ids),
        follow, execution)


class K1AimPreparedAttackLossConsumptionTests(unittest.TestCase):
    def test_free_crossbow_hit_miss_and_aim_zero_positive_preserve_entire_execution(self):
        for weapon, values, hit in product((RangedWeaponId.LONGBOW, RangedWeaponId.CROSSBOW),
                                          ((1, 2, 10), (10, 10, 10)), (False, True)):
            with self.subTest(weapon=weapon, values=values, hit=hit):
                source = request(weapon=weapon, values=values, hit=hit)
                before = deepcopy(source)
                with (
                    patch.object(consumption, "execute_prepared_ranged_weapon_attack") as prepared,
                    patch.object(consumption, "execute_ranged_weapon_attack") as ranged,
                    patch("towr.rules.prepared_ranged_weapon_attack_resolution.execute_ranged_weapon_attack") as nested,
                    patch("towr.rules.attack_action_execution.resolve_kernel_attack") as kernel,
                    patch("towr.rules.ranged_weapon_attack_resolution._spent_weapon_state") as spend,
                    patch("towr.rules.ranged_weapon_attack_preparation.prepare_ranged_weapon_attack") as prepare,
                ):
                    result = consumption.consume_prepared_attack_lost_aim(source)
                for call in (prepared, ranged, nested, kernel, spend, prepare):
                    call.assert_not_called()
                self.assertIs(result.source_request, source)
                self.assertIs(result.source_request.execution, source.execution)
                self.assertIs(result.previous_state, source.state)
                self.assertEqual(result.state.consumed_aim_source_ids, ("source:older", "aim:execute"))
                self.assertEqual(result.state.consumed_aim_follow_up_ids,
                    ("follow:older", "follow:prior", source.follow_up.request_id))
                self.assertEqual(source.execution.consumed_aim_follow_up_ids, source.state.consumed_aim_follow_up_ids)
                ranged = source.execution.ranged_attack
                attack = ranged.attack
                self.assertIs(attack.resolution.attack.outcome, AttackOutcome.HIT if hit else AttackOutcome.MISS)
                self.assertEqual(attack.resolution.attack.attacker_test.trace.rolled_dice, 3)
                self.assertEqual(attack.resolution.attack.attacker_test.trace.regular_dice_delta, 0)
                self.assertEqual(attack.slot.execution.id, source.follow_up.source_request.next_action_id)
                self.assertIs(ranged.source_request, source.execution.source_request.preparation.execution)
                if weapon is RangedWeaponId.LONGBOW:
                    self.assertIs(ranged.weapon_state, ranged.previous_weapon_state)
                else:
                    self.assertFalse(ranged.weapon_state.loaded)
                    self.assertEqual(ranged.weapon_state.reload_cycle_ids, ("reload:loss",))
                self.assertEqual(result.applied_rule_ids, tuple(dict.fromkeys((
                    AIM_PREPARED_ATTACK_LOSS_CONSUMPTION_RULE_ID,
                    *source.follow_up.source_request.aim.applied_rule_ids,
                    *source.follow_up.applied_rule_ids, *source.execution.applied_rule_ids))))
                self.assertTrue(set(source.execution.source_request.preparation.applied_rule_ids) <= set(result.applied_rule_ids))
                self.assertEqual(source, before)
                with self.assertRaises(FrozenInstanceError):
                    result.state = source.state

    def test_profile_penalty_and_final_attack_binding_survive_registration(self):
        source = request(weapon=RangedWeaponId.LONGBOW, outside=True)
        result = consumption.consume_prepared_attack_lost_aim(source)
        preparation = source.execution.source_request.preparation
        self.assertIn(OUTSIDE_OPTIMUM_RANGE_RULE_ID, result.applied_rule_ids)
        self.assertEqual(source.execution.ranged_attack.attack.resolution.attack.attacker_test.trace.regular_dice_delta, -1)
        self.assertEqual(source.execution.ranged_attack.attack.resolution.attack.attacker_test.trace.rolled_dice, 2)
        raw = preparation.source_request.attack
        # Same IDs, but the unprepared Attack lacks profile damage/range effects.
        self.assertNotEqual(raw, preparation.execution.attack)
        with self.assertRaisesRegex(ValueError, "source does not match"):
            replace(source, follow_up=resolve_aim_follow_up(replace(source.follow_up.source_request, attack=raw)))

    def test_shared_history_blocks_renamed_replay_in_both_directions(self):
        source = request()
        result = consumption.consume_prepared_attack_lost_aim(source)
        for candidate in (source, request(renamed=True)):
            with self.assertRaisesRegex(ValueError, "source was already consumed"):
                replace(candidate, id="consume:new", state=result.state)
        consumers = (
            (consumption.consume_attack_lost_aim, ordinary_request()),
            (consumption.consume_ranged_attack_lost_aim, ranged_request()),
            (consumption.consume_lost_aim, non_attack_request()),
            (consumption.register_aim_ranged_attack, applied_request()),
        )
        for consume, prior in consumers:
            with self.subTest(consumer=consume.__name__):
                with self.assertRaisesRegex(ValueError, "source was already consumed"):
                    replace(source, state=consume(prior).state)
                with self.assertRaisesRegex(ValueError, "source was already consumed"):
                    replace(prior, state=result.state)

    def test_ordered_input_history_must_match_prepared_execution(self):
        source = request()
        for history in ((), ("foreign",), ("follow:prior", "follow:older")):
            with self.subTest(history=history), self.assertRaisesRegex(ValueError, "stale follow-up history"):
                replace(source, state=replace(source.state, consumed_aim_follow_up_ids=history))
        with self.assertRaisesRegex(ValueError, "follow-up was already consumed"):
            replace(source, state=replace(source.state, consumed_aim_follow_up_ids=(source.follow_up.request_id,)))

    def test_actor_kernel_previous_state_and_receipt_binding(self):
        source = request()
        with self.assertRaisesRegex(ValueError, "another actor"):
            replace(source, state=replace(source.state, actor_id="other"))
        attack = source.follow_up.attack
        for changed in (
            replace(attack, kernel_request=replace(attack.kernel_request, id="other")),
            replace(attack, state=replace(attack.state, completed_turn_entity_ids=("ally",))),
        ):
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, "does not match"):
                replace(source, follow_up=resolve_aim_follow_up(replace(source.follow_up.source_request, attack=changed)))
        nested = source.execution.ranged_attack.attack
        with self.assertRaises(ValueError):
            replace(nested, slot=replace(nested.slot, execution=replace(nested.slot.execution, actor_id="other")))

    def test_chronology_same_or_later_first_slot_only(self):
        for later in (None, 2, 5):
            consumption.consume_prepared_attack_lost_aim(request(later_round=later))
        with self.assertRaisesRegex(ValueError, "first slot"):
            request(later_round=2, later_second=True)
        source = request()
        pending = source.follow_up.source_request.aim.source_request
        future = execute_aim_action(replace(pending, round_state=replace(pending.round_state, round_number=2)),
                                    SequenceRandom([1, 2, 10]))
        with self.assertRaisesRegex(ValueError, "must follow Aim"):
            replace(source, follow_up=resolve_aim_follow_up(replace(source.follow_up.source_request, aim=future)))

    def test_only_direct_no_aim_shooting_lost_is_accepted(self):
        source = request()
        for kwargs in ({"target": "enemy"}, {"skill": Skill.THROWING}):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ValueError, "requires LOST|requires Shooting"):
                request(**kwargs)
        with self.assertRaisesRegex(ValueError, "ordinary Attack"):
            replace(source, follow_up=non_attack_request().follow_up)
        # A valid APPLIED prepared result cannot be repurposed as a LOST registration.
        for values in ((10, 10, 10), (1, 2, 10)):
            follow, aimed = inputs(target="enemy", prepared_aim=True, values=values)
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, "direct no-Aim branch"):
                replace(source, follow_up=follow, execution=aimed)
        with self.assertRaisesRegex(ValueError, "another actor or target"):
            preparation_request(RangedWeaponId.LONGBOW, attack=source.follow_up.attack,
                                aim=source.follow_up.source_request.aim)

    def test_nested_source_weapon_and_trace_provenance_are_retained(self):
        source = request()
        execution = source.execution
        for changes in (
            {"request_id": "other"}, {"source_request": replace(execution.source_request, id="other")},
            {"applied_rule_ids": ()}, {"consumed_aim_follow_up_ids": ()},
            {"execution": inputs(renamed=True)[1].execution},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(execution, **changes)
        with self.assertRaises(ValueError):
            replace(execution.ranged_attack, weapon_state=execution.ranged_attack.previous_weapon_state)

    def test_returned_history_prevents_old_source_in_next_preparation(self):
        source = request()
        result = consumption.consume_prepared_attack_lost_aim(source)
        aim = source.follow_up.source_request.aim
        attack = source.execution.source_request.preparation.source_request.attack
        next_attack = replace(attack, id="attack:next", target_id=aim.bonus.target_id,
            kernel_request=replace(attack.kernel_request, target_id=aim.bonus.target_id))
        candidate = replace(preparation_request(RangedWeaponId.LONGBOW, attack=next_attack, aim=aim), id="prepare:next")
        with patch("towr.rules.ranged_weapon_attack_preparation.prepare_ranged_weapon_attack") as prepare:
            with self.assertRaisesRegex(ValueError, "source was already consumed"):
                prepare_ranged_weapon_attack_with_aim_history(result.state, candidate)
        prepare.assert_not_called()

    def test_types_result_state_trace_and_failures(self):
        source = request()
        for changes in ({"id": ""}, {"rule_id": "other"}, {"state": None}, {"follow_up": None},
                        {"execution": None}, {"execution": source.execution.ranged_attack}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(source, **changes)
        with self.assertRaises(TypeError):
            consumption.consume_prepared_attack_lost_aim(None)
        result = consumption.consume_prepared_attack_lost_aim(source)
        for changes in (
            {"request_id": "other"}, {"rule_id": "other"}, {"source_request": None},
            {"source_request": replace(source, id="other")}, {"previous_state": result.state}, {"state": source.state},
            {"state": replace(result.state, actor_id="other")},
            {"state": replace(result.state, consumed_aim_follow_up_ids=tuple(reversed(result.state.consumed_aim_follow_up_ids)))},
            {"applied_rule_ids": ()}, {"applied_rule_ids": (*result.applied_rule_ids, "extra")},
        ):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(result, **changes)
        before = deepcopy(source)
        with patch.object(consumption, "AimPreparedAttackLossConsumptionResult", side_effect=RuntimeError("result failed")):
            with self.assertRaisesRegex(RuntimeError, "result failed"):
                consumption.consume_prepared_attack_lost_aim(source)
        self.assertEqual(source, before)
