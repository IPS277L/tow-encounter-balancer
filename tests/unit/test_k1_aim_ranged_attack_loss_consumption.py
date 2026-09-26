from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_aim_consumption_resolution import request as non_attack_loss
from tests.unit.test_k1_aim_attack_consumption import request as applied_request
from tests.unit.test_k1_ranged_weapon_attack_preparation import preparation_request
from towr.domain.aim_consumption_models import (
    AIM_RANGED_ATTACK_LOSS_CONSUMPTION_RULE_ID,
    AimRangedAttackLossConsumptionRequest, AimConsumptionState,
)
from tests.unit.test_k1_aim_attack_loss_consumption import pending_inputs, request as ordinary_request
from tests.unit.test_k1_aim_charge_loss_consumption import request as charge_request
from tests.unit.test_k1_aim_long_charge_loss_consumption import request as long_request
from tests.unit.test_k1_aim_difficult_terrain_charge_loss_consumption import request as terrain_request
from towr.domain.ranged_weapon_attack_models import RangedWeaponAttackExecutionRequest
from towr.domain.reload_models import create_initial_ranged_weapon_reload_state
from towr.rules.ranged_weapon_attack_resolution import execute_ranged_weapon_attack
from towr.domain.aim_models import AimFollowUpOutcome
from towr.domain.aim_ranged_weapon_attack_models import AimRangedWeaponAttackExecutionRequest
from towr.domain.attack_models import AttackOutcome
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.test_models import Skill
from towr.rules import aim_consumption_resolution as consumption
from towr.rules.aim_resolution import execute_aim_action, resolve_aim_follow_up
from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack_with_aim_history


def inputs(*, hit=False, weapon_id=RangedWeaponId.CROSSBOW, **kwargs):
    follow_up, attack = pending_inputs(**kwargs)
    rng = SequenceRandom([1 if hit else 10, 10, 10, 7])
    renamed = kwargs.get("renamed")
    ranged = RangedWeaponAttackExecutionRequest(
        "ranged:new" if renamed else "ranged:loss", Skill.SHOOTING, attack,
        create_initial_ranged_weapon_reload_state("hero:weapon", weapon_id),
        ("reload:new" if renamed else "reload:next") if weapon_id is RangedWeaponId.CROSSBOW else None,
    )
    execution = execute_ranged_weapon_attack(ranged, rng)
    assert rng.randint(1, 10) == 7
    return follow_up, execution


def request(**kwargs):
    follow_up, execution = inputs(**kwargs)
    return AimRangedAttackLossConsumptionRequest(
        "consume:attack-loss", AimConsumptionState("hero", ("source:older",), ("follow:older", "follow:prior")),
        follow_up, execution,
    )


class K1AimRangedAttackLossConsumptionTests(unittest.TestCase):
    def test_hit_miss_and_zero_positive_aim_register_once_without_reexecution(self):
        for weapon_id in (RangedWeaponId.LONGBOW, RangedWeaponId.CROSSBOW):
            for values in ((1, 2, 10), (10, 10, 10)):
                for hit in (False, True):
                    with self.subTest(weapon=weapon_id, values=values, hit=hit):
                        source = request(values=values, hit=hit, weapon_id=weapon_id)
                        before = deepcopy(source)
                        with (
                            patch("towr.rules.attack_action_execution.execute_attack_action") as execute,
                            patch("towr.rules.attack_action_execution.resolve_kernel_attack") as kernel,
                            patch("towr.rules.aim_resolution.resolve_aim_follow_up") as follow_up,
                            patch("towr.rules.ranged_weapon_attack_resolution.execute_ranged_weapon_attack") as ranged,
                            patch("towr.rules.ranged_weapon_attack_resolution.execute_reloadable_ranged_attack") as reloadable,
                            patch("towr.rules.ranged_weapon_attack_resolution._spent_weapon_state") as spend,
                        ):
                            result = consumption.consume_ranged_attack_lost_aim(source)
                        execute.assert_not_called()
                        kernel.assert_not_called()
                        follow_up.assert_not_called()
                        ranged.assert_not_called()
                        reloadable.assert_not_called()
                        spend.assert_not_called()
                        self.assertIs(result.source_request, source)
                        self.assertIs(result.source_request.execution, source.execution)
                        weapon = result.source_request.execution.weapon_state
                        self.assertIs(weapon, source.execution.weapon_state)
                        self.assertIs(source.execution.previous_weapon_state, source.execution.source_request.weapon_state)
                        if weapon_id is RangedWeaponId.LONGBOW:
                            self.assertIs(weapon, source.execution.previous_weapon_state)
                        else:
                            self.assertFalse(weapon.loaded)
                            self.assertEqual(weapon.reload_cycle_id, "reload:next")
                            self.assertEqual(weapon.reload_cycle_ids, ("reload:next",))
                            self.assertEqual(source.execution.previous_weapon_state.reload_cycle_ids, ())
                        self.assertIs(result.previous_state, source.state)
                        self.assertEqual(result.state.consumed_aim_source_ids, ("source:older", "aim:execute"))
                        self.assertEqual(result.state.consumed_aim_follow_up_ids, ("follow:older", "follow:prior", "follow:lost-attack"))
                        self.assertEqual(source.execution.attack.resolution.attack.outcome, AttackOutcome.HIT if hit else AttackOutcome.MISS)
                        self.assertEqual(source.execution.attack.resolution.attack.attacker_test.trace.rolled_dice, 3)
                        self.assertEqual(source.execution.attack.resolution.attack.attacker_test.trace.regular_dice_delta, 0)
                        self.assertIs(source.follow_up.outcome, AimFollowUpOutcome.LOST)
                        self.assertIsNone(source.follow_up.modifier)
                        self.assertIn(AIM_RANGED_ATTACK_LOSS_CONSUMPTION_RULE_ID, result.applied_rule_ids)
                        self.assertTrue(set(source.follow_up.source_request.aim.applied_rule_ids) <= set(result.applied_rule_ids))
                        self.assertTrue(set(source.follow_up.applied_rule_ids) <= set(result.applied_rule_ids))
                        self.assertTrue(set(source.execution.applied_rule_ids) <= set(result.applied_rule_ids))
                        self.assertEqual(source, before)
                        with self.assertRaises(FrozenInstanceError):
                            result.state = source.state

    def test_source_replay_rejects_renamed_attack_follow_up_and_registration(self):
        source = request()
        done = consumption.consume_ranged_attack_lost_aim(source)
        for candidate in (source, request(renamed=True)):
            with self.subTest(id=candidate.follow_up.request_id), self.assertRaisesRegex(ValueError, "source was already consumed"):
                replace(candidate, id="consume:new", state=done.state)
        with self.assertRaisesRegex(ValueError, "follow-up was already consumed"):
            replace(source, state=replace(source.state, consumed_aim_follow_up_ids=(source.follow_up.request_id,)))

    def test_shared_history_blocks_replay_in_both_directions(self):
        source = request()
        consumers = (
            (consumption.consume_lost_aim, non_attack_loss()),
            (consumption.register_aim_ranged_attack, applied_request()),
            (consumption.consume_attack_lost_aim, ordinary_request()),
            (consumption.consume_charge_lost_aim, charge_request()),
            (consumption.consume_long_charge_lost_aim, long_request()),
            (consumption.consume_difficult_terrain_charge_lost_aim, terrain_request()),
        )
        done = consumption.consume_ranged_attack_lost_aim(source)
        for consume, prior in consumers:
            with self.subTest(consumer=consume.__name__):
                with self.assertRaisesRegex(ValueError, "source was already consumed"):
                    replace(source, state=consume(prior).state)
                with self.assertRaisesRegex(ValueError, "source was already consumed"):
                    replace(prior, state=done.state)

    def test_actor_target_kernel_attack_and_previous_state_binding(self):
        source = request()
        follow_source = source.follow_up.source_request
        attack = follow_source.attack
        for changed in (
            replace(attack, kernel_request=replace(attack.kernel_request, id="kernel:other")),
            replace(attack, kernel_request=replace(attack.kernel_request,
                attack=replace(attack.kernel_request.attack, id="attack:other"))),
            replace(attack, state=replace(attack.state, completed_turn_entity_ids=("ally",))),
        ):
            follow_up = resolve_aim_follow_up(replace(follow_source, attack=changed))
            with self.subTest(attack=changed), self.assertRaisesRegex(ValueError, "does not match"):
                replace(source, follow_up=follow_up)
        for changes in (
            {"state": replace(source.state, actor_id="other")},
            {"execution": inputs(renamed=True)[1]},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(source, **changes)

    def test_wrong_receipt_is_rejected_by_completed_attack_contract(self):
        source = request()
        receipt = source.execution.attack.slot.execution
        for changes in ({"id": "other"}, {"source_request_id": "other"}, {"actor_id": "other"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                changed = replace(source.execution.attack,
                                  slot=replace(source.execution.attack.slot, execution=replace(receipt, **changes)))
                replace(source, execution=replace(source.execution, attack=changed))

    def test_same_turn_or_later_first_slot_allowed_but_earlier_and_later_second_rejected(self):
        for later in (None, 2, 5):
            with self.subTest(round=later):
                consumption.consume_ranged_attack_lost_aim(request(later_round=later))
        with self.assertRaisesRegex(ValueError, "first slot"):
            request(later_round=2, later_second=True)
        source = request()
        pending = source.follow_up.source_request.aim.source_request
        future = execute_aim_action(replace(pending, round_state=replace(pending.round_state, round_number=2)), SequenceRandom([1, 2, 10]))
        with self.assertRaisesRegex(ValueError, "must follow Aim"):
            replace(source, follow_up=resolve_aim_follow_up(replace(source.follow_up.source_request, aim=future)))

    def test_applied_non_attack_and_noncombat_skill_are_outside_consumer(self):
        source = request()
        for target, skill in (
            ("enemy", Skill.SHOOTING), ("enemy", Skill.THROWING), ("enemy", Skill.AWARENESS),
            ("enemy", Skill.MELEE), ("enemy:other", Skill.THROWING),
        ):
            with self.subTest(target=target, skill=skill), self.assertRaisesRegex(ValueError, "requires LOST|requires Melee|requires Shooting"):
                request(target=target, skill=skill)
        with self.assertRaisesRegex(ValueError, "ordinary Attack"):
            replace(source, follow_up=non_attack_loss().follow_up)
        with self.assertRaisesRegex(ValueError, "bonus was not applied"):
            AimRangedWeaponAttackExecutionRequest("applied:only", source.follow_up, source.execution.source_request)

    def test_exact_attack_source_and_weapon_transition_cannot_be_substituted(self):
        source = request()
        attack = source.follow_up.source_request.attack
        changed = replace(attack, kernel_request=replace(attack.kernel_request,
            attack=replace(attack.kernel_request.attack, is_close_range=True)))
        follow_up = resolve_aim_follow_up(replace(source.follow_up.source_request, attack=changed))
        with self.assertRaisesRegex(ValueError, "source does not match"):
            replace(source, follow_up=follow_up)
        for changes in (
            {"weapon_state": source.execution.previous_weapon_state},
            {"previous_weapon_state": replace(source.execution.previous_weapon_state, weapon_instance_id="foreign")},
            {"source_request": replace(source.execution.source_request, id="foreign")},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(source.execution, **changes)

    def test_returned_history_rejects_next_preparation_with_new_ids(self):
        source = request()
        result = consumption.consume_ranged_attack_lost_aim(source)
        follow_up = source.follow_up.source_request
        next_attack = replace(follow_up.attack, id="attack:next", target_id=follow_up.aim.bonus.target_id,
            kernel_request=replace(follow_up.attack.kernel_request, target_id=follow_up.aim.bonus.target_id))
        candidate = replace(preparation_request(RangedWeaponId.LONGBOW,
            attack=next_attack, aim=follow_up.aim), id="prepare:new")
        with patch("towr.rules.ranged_weapon_attack_preparation.prepare_ranged_weapon_attack") as prepare:
            with self.assertRaisesRegex(ValueError, "source was already consumed"):
                prepare_ranged_weapon_attack_with_aim_history(result.state, candidate)
        prepare.assert_not_called()

    def test_types_rules_state_provenance_and_exact_trace(self):
        source = request()
        for changes in (
            {"id": ""}, {"rule_id": "foreign"}, {"state": None}, {"follow_up": None},
            {"execution": None}, {"execution": source.follow_up.attack},
            {"execution": source.execution.attack.slot.execution},
        ):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(source, **changes)
        with self.assertRaises(TypeError):
            consumption.consume_ranged_attack_lost_aim(None)
        result = consumption.consume_ranged_attack_lost_aim(source)
        for changes in (
            {"request_id": "other"}, {"rule_id": "other"}, {"source_request": None},
            {"source_request": replace(source, id="other")}, {"previous_state": result.state},
            {"state": source.state}, {"state": replace(result.state, actor_id="other")},
            {"state": replace(result.state, consumed_aim_follow_up_ids=tuple(reversed(result.state.consumed_aim_follow_up_ids)))},
            {"applied_rule_ids": ()}, {"applied_rule_ids": (*result.applied_rule_ids, "extra")},
        ):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(result, **changes)

    def test_result_failure_leaves_all_input_snapshots_unchanged(self):
        source = request()
        before = deepcopy(source)
        with patch.object(consumption, "AimRangedAttackLossConsumptionResult", side_effect=RuntimeError("result failed")):
            with self.assertRaisesRegex(RuntimeError, "result failed"):
                consumption.consume_ranged_attack_lost_aim(source)
        self.assertEqual(source, before)
