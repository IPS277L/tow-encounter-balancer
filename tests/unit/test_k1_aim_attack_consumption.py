from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_aim_consumption_resolution import request as loss_request
from tests.unit.test_k1_aim_ranged_weapon_attack_resolution import aimed_ranged_request
from tests.unit.test_k1_ranged_weapon_attack_preparation import preparation_request
from towr.domain.aim_consumption_models import (
    AIM_ATTACK_CONSUMPTION_RULE_ID, AimAttackConsumptionRequest, AimConsumptionState,
)
from towr.domain.attack_models import AttackOutcome
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.reload_models import create_initial_ranged_weapon_reload_state
from towr.rules.aim_consumption_resolution import consume_lost_aim, register_aim_ranged_attack
from towr.rules.aim_ranged_weapon_attack_resolution import execute_aim_ranged_weapon_attack
from towr.rules.aim_resolution import execute_aim_action, resolve_aim_follow_up
from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack_with_aim_history


def request(*, weapon_id=RangedWeaponId.CROSSBOW, aim_values=(1, 2, 10), hit=True, renamed=False):
    history = AimConsumptionState("hero", ("aim:older",), ("follow:older", "follow:prior"))
    source = aimed_ranged_request(
        create_initial_ranged_weapon_reload_state("hero:weapon", weapon_id), aim_values=aim_values,
        next_cycle_id="reload:1" if weapon_id is RangedWeaponId.CROSSBOW else None,
        consumed=history.consumed_aim_follow_up_ids,
    )
    if renamed:
        original = source.aim_follow_up.source_request
        attack = replace(original.attack, id="attack:new")
        follow_up = resolve_aim_follow_up(replace(original, id="follow:new", attack=attack, next_action_id=attack.id))
        source = replace(source, id="execute:new", aim_follow_up=follow_up,
                         ranged_attack=replace(source.ranged_attack, id="ranged:new", attack=follow_up.attack))
    dice = 2 + sum(value <= 5 for value in aim_values)
    rng = SequenceRandom([1 if hit else 10, *([10] * (dice - 1)), 7])
    execution = execute_aim_ranged_weapon_attack(source, rng)
    assert rng.randint(1, 10) == 7
    return AimAttackConsumptionRequest("register:aim-attack", history, execution)


class K1AimAttackConsumptionTests(unittest.TestCase):
    def test_free_and_crossbow_hit_miss_zero_positive_aim_register_without_reexecution(self):
        for weapon_id in (RangedWeaponId.LONGBOW, RangedWeaponId.CROSSBOW):
            for aim_values in ((1, 2, 10), (10, 10, 10)):
                for hit in (False, True):
                    with self.subTest(weapon=weapon_id, aim=aim_values, hit=hit):
                        source = request(weapon_id=weapon_id, aim_values=aim_values, hit=hit)
                        before = deepcopy(source)
                        with patch("towr.rules.aim_ranged_weapon_attack_resolution.execute_aim_ranged_weapon_attack") as execute:
                            result = register_aim_ranged_attack(source)
                        execute.assert_not_called()
                        self.assertIs(result.source_request.execution, source.execution)
                        self.assertIs(result.previous_state, source.state)
                        self.assertEqual(result.state.consumed_aim_source_ids, ("aim:older", "aim:execute"))
                        self.assertEqual(result.state.consumed_aim_follow_up_ids,
                                         (*source.state.consumed_aim_follow_up_ids, source.execution.source_request.aim_follow_up.request_id))
                        self.assertEqual(result.state.consumed_aim_follow_up_ids, source.execution.consumed_aim_follow_up_ids)
                        self.assertEqual(source.execution.ranged_attack.attack.resolution.attack.outcome,
                                         AttackOutcome.HIT if hit else AttackOutcome.MISS)
                        self.assertIn(AIM_ATTACK_CONSUMPTION_RULE_ID, result.applied_rule_ids)
                        self.assertTrue(set(source.execution.applied_rule_ids) <= set(result.applied_rule_ids))
                        if weapon_id is RangedWeaponId.CROSSBOW:
                            self.assertFalse(result.source_request.execution.ranged_attack.weapon_state.loaded)
                        self.assertEqual(source, before)

    def test_source_replay_rejects_renamed_attack_follow_up_and_registration(self):
        source = request()
        result = register_aim_ranged_attack(source)
        for execution in (source.execution, request(renamed=True).execution):
            with self.subTest(id=execution.request_id), self.assertRaisesRegex(ValueError, "source was already consumed"):
                replace(source, id="registration:new", state=result.state, execution=execution)

    def test_lost_source_cannot_be_registered_as_applied(self):
        lost = consume_lost_aim(loss_request()).state
        with self.assertRaisesRegex(ValueError, "source was already consumed"):
            replace(request(), state=lost)

    def test_exact_follow_up_prefix_and_actor_are_required(self):
        source = request()
        for history in (
            replace(source.state, actor_id="other"),
            replace(source.state, consumed_aim_follow_up_ids=()),
            replace(source.state, consumed_aim_follow_up_ids=tuple(reversed(source.state.consumed_aim_follow_up_ids))),
            replace(source.state, consumed_aim_follow_up_ids=(*source.state.consumed_aim_follow_up_ids, "extra")),
            replace(source.state, consumed_aim_follow_up_ids=source.execution.consumed_aim_follow_up_ids),
        ):
            with self.subTest(history=history), self.assertRaises(ValueError):
                replace(source, state=history)

    def test_registered_source_is_rejected_by_next_preparation_with_new_ids(self):
        source = request()
        result = register_aim_ranged_attack(source)
        follow_up = source.execution.source_request.aim_follow_up.source_request
        candidate = replace(preparation_request(
            RangedWeaponId.CROSSBOW, aim=follow_up.aim,
            attack=replace(follow_up.attack, id="attack:next"), next_cycle="reload:next",
        ), id="preparation:next")
        with patch("towr.rules.ranged_weapon_attack_preparation.prepare_ranged_weapon_attack") as prepare:
            with self.assertRaisesRegex(ValueError, "source was already consumed"):
                prepare_ranged_weapon_attack_with_aim_history(result.state, candidate)
        prepare.assert_not_called()

    def test_nested_result_validation_rejects_another_attack_or_receipt(self):
        source = request()
        with self.assertRaisesRegex(ValueError, "another Attack"):
            replace(source.execution, ranged_attack=request(renamed=True).execution.ranged_attack)
        attack = source.execution.ranged_attack.attack
        with self.assertRaises(ValueError):
            replace(attack, slot=replace(attack.slot, execution=replace(attack.slot.execution, id="receipt:foreign")))

    def test_completed_attack_before_its_aim_is_rejected(self):
        source = request()
        follow_up = source.execution.source_request.aim_follow_up
        pending = follow_up.source_request.aim.source_request
        future_aim = execute_aim_action(replace(pending, round_state=replace(pending.round_state, round_number=2)),
                                        SequenceRandom([1, 2, 10]))
        changed_follow_up = resolve_aim_follow_up(replace(follow_up.source_request, aim=future_aim))
        changed_execution = replace(source.execution, source_request=replace(
            source.execution.source_request, aim_follow_up=changed_follow_up))
        with self.assertRaisesRegex(ValueError, "Attack must follow Aim"):
            replace(source, execution=changed_execution)

    def test_result_rejects_stale_history_provenance_and_trace(self):
        source = request()
        result = register_aim_ranged_attack(source)
        for changes in (
            {"request_id": "other"}, {"rule_id": "other"}, {"source_request": None},
            {"previous_state": AimConsumptionState("hero")}, {"state": source.state},
            {"state": replace(result.state, consumed_aim_source_ids=())},
            {"applied_rule_ids": ()}, {"applied_rule_ids": (*result.applied_rule_ids, "extra")},
        ):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(result, **changes)

    def test_request_rejects_pending_non_aim_results_and_unknown_rule(self):
        source = request()
        for execution in (None, source.execution.source_request, source.execution.ranged_attack, loss_request().follow_up):
            with self.subTest(execution=type(execution)), self.assertRaises(TypeError):
                replace(source, execution=execution)
        for changes in ({"state": None}, {"id": ""}, {"rule_id": "foreign"}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(source, **changes)
        with self.assertRaises(TypeError):
            register_aim_ranged_attack(None)
