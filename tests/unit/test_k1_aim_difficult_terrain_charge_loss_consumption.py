from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from itertools import product
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_aim_resolution import attack_execution_request
from tests.unit.test_k1_aim_consumption_resolution import request as non_attack_request
from tests.unit.test_k1_aim_attack_consumption import request as applied_request
from tests.unit.test_k1_aim_attack_loss_consumption import request as attack_loss_request
from tests.unit.test_k1_aim_charge_loss_consumption import pending_inputs as ordinary_pending_inputs, request as ordinary_request
from tests.unit.test_k1_aim_long_charge_loss_consumption import request as long_request
from tests.unit.test_k1_difficult_terrain_charge_action_execution import terrain_request
from towr.domain.charge_models import DifficultTerrainChargeActionExecutionRequest
from towr.domain.condition_models import Condition
from towr.rules.difficult_terrain_resolution import resolve_difficult_terrain_traversal
from tests.unit.test_k1_ranged_weapon_attack_preparation import preparation_request
from towr.domain.aim_consumption_models import (
    AIM_DIFFICULT_TERRAIN_CHARGE_LOSS_CONSUMPTION_RULE_ID, AimDifficultTerrainChargeLossConsumptionRequest, AimConsumptionState,
)
from towr.domain.aim_models import AimFollowUpOutcome
from towr.domain.attack_models import AttackOutcome
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.resolution_models import AttackerStaggerRequest
from towr.domain.test_models import Skill
from towr.rules import aim_consumption_resolution as consumption
from towr.rules.aim_resolution import resolve_aim_follow_up
from towr.rules.charge_action_execution import execute_difficult_terrain_charge_action
from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack_with_aim_history


def pending_inputs(*, terrain_roll=1, already_tested=False, **kwargs):
    follow, charge = ordinary_pending_inputs(**kwargs)
    state = charge.spatial_state
    if already_tested:
        state = replace(state, difficult_terrain_tested_entity_ids=("hero",))
    charge = replace(charge, spatial_state=state, crosses_difficult_terrain=True)
    terrain = terrain_request(charge.round_state, state, charge.actor_conditions)
    if kwargs.get("renamed"):
        terrain = replace(terrain, id="terrain:new", athletics_test=replace(terrain.athletics_test, id="athletics:new"))
    rng = SequenceRandom([terrain_roll, 7])
    traversal = resolve_difficult_terrain_traversal(terrain, rng)
    assert rng.randint(1, 10) == 7  # A previous crossing does not skip the next terrain Test.
    pending = DifficultTerrainChargeActionExecutionRequest(
        "terrain-charge:new" if kwargs.get("renamed") else "execute:terrain-charge",
        charge, traversal, charge.round_state, traversal.state,
    )
    follow = resolve_aim_follow_up(replace(follow.source_request, next_action_id=pending.id))
    return follow, pending


def request(*, hit=False, **kwargs):
    follow, pending = pending_inputs(**kwargs)
    rng = SequenceRandom([1 if hit else 10, *([10] if pending.charge_action.attack_skill is Skill.MELEE else []), 7])
    execution = execute_difficult_terrain_charge_action(pending, rng)
    assert rng.randint(1, 10) == 7
    return AimDifficultTerrainChargeLossConsumptionRequest(
        "consume:charge", AimConsumptionState("hero", ("source:older",), ("follow:older", "follow:prior")),
        follow, execution,
    )


class K1AimDifficultTerrainChargeLossConsumptionTests(unittest.TestCase):
    skill = Skill.MELEE

    @property
    def charge_dice(self):
        return 2 if self.skill is Skill.MELEE else 1

    def make_request(self, **kwargs):
        kwargs.setdefault("skill", self.skill)
        return request(**kwargs)

    def test_terrain_outcomes_hit_miss_and_aim_preserve_completed_charge(self):
        for values, hit, target, terrain_roll, tested in product(
            ((10, 10, 10), (1, 2, 10)), (False, True), ("enemy", "enemy:other"), (1, 10), (False, True),
        ):
            with self.subTest(values=values, hit=hit, aim_target=target, terrain_roll=terrain_roll, tested=tested):
                source = self.make_request(values=values, hit=hit, aim_target=target, terrain_roll=terrain_roll, already_tested=tested)
                before = deepcopy(source)
                with (
                    patch("towr.rules.charge_action_execution.execute_difficult_terrain_charge_action") as execute,
                    patch("towr.rules.charge_action_execution.resolve_kernel_attack") as kernel,
                    patch("towr.rules.difficult_terrain_resolution.resolve_difficult_terrain_traversal") as traverse,
                    patch("towr.rules.difficult_terrain_resolution.resolve_test") as athletics,
                    patch("towr.rules.difficult_terrain_resolution.resolve_condition_application") as condition,
                    patch("towr.rules.aim_resolution.resolve_aim_follow_up") as follow,
                ):
                    result = consumption.consume_difficult_terrain_charge_lost_aim(source)
                execute.assert_not_called()
                kernel.assert_not_called()
                traverse.assert_not_called()
                athletics.assert_not_called()
                condition.assert_not_called()
                follow.assert_not_called()
                self.assertIs(result.source_request.execution, source.execution)
                self.assertIs(result.previous_state, source.state)
                self.assertIs(source.follow_up.outcome, AimFollowUpOutcome.LOST)
                self.assertIsNone(source.follow_up.modifier)
                self.assertEqual(result.state.consumed_aim_source_ids, ("source:older", "aim:execute"))
                self.assertEqual(result.state.consumed_aim_follow_up_ids, ("follow:older", "follow:prior", "follow:charge"))
                execution = result.source_request.execution
                self.assertIs(execution.resolution.attack.outcome, AttackOutcome.HIT if hit else AttackOutcome.MISS)
                self.assertEqual(execution.resolution.target_state.conditions.has(Condition.STAGGERED), hit)
                self.assertEqual(execution.resolution.follow_ups, () if hit else (
                    AttackerStaggerRequest(execution.source_kernel_request.attack.id),))
                self.assertEqual(execution.resolution.attack.attacker_test.trace.rolled_dice, self.charge_dice)
                self.assertEqual(execution.resolution.attack.attacker_test.trace.regular_dice_delta, self.charge_dice - 1)
                if self.skill is Skill.MELEE:
                    self.assertEqual(execution.melee_bonus.amount, 1)
                else:
                    self.assertIsNone(execution.melee_bonus)
                    self.assertIs(execution.kernel_request, execution.source_kernel_request)
                traversal = execution.terrain_traversal
                self.assertEqual(traversal.previous_state.placement_for("hero").zone_id, "zone:a")
                self.assertIs(execution.previous_spatial_state, traversal.state)
                self.assertIs(execution.spatial_state, traversal.state)
                self.assertIs(execution.conditions, traversal.conditions)
                self.assertEqual(execution.conditions.has(Condition.PRONE), terrain_roll == 10)
                self.assertEqual(traversal.athletics_test_result.succeeded, terrain_roll == 1)
                self.assertEqual(traversal.athletics_test_result.trace.rolled_dice, 1)
                self.assertEqual(traversal.previous_state.difficult_terrain_tested_entity_ids, ("hero",) if tested else ())
                self.assertEqual(traversal.state.difficult_terrain_tested_entity_ids, ("hero",))
                if terrain_roll == 1:
                    self.assertIsNone(traversal.prone_application)
                else:
                    self.assertIs(traversal.prone_application.state, execution.conditions)
                self.assertEqual(execution.spatial_state.placement_for("hero").zone_id, "zone:b")
                self.assertEqual(execution.slot.execution.id, execution.request_id)
                self.assertNotEqual(execution.slot.execution.id, execution.charge_action_request.id)
                expected = tuple(dict.fromkeys((AIM_DIFFICULT_TERRAIN_CHARGE_LOSS_CONSUMPTION_RULE_ID,
                    *source.follow_up.source_request.aim.applied_rule_ids, *source.follow_up.applied_rule_ids,
                    *execution.applied_rule_ids)))
                self.assertEqual(result.applied_rule_ids, expected)
                self.assertEqual(source, before)
                with self.assertRaises(FrozenInstanceError):
                    result.state = source.state

    def test_source_and_follow_up_replay_with_new_charge_ids(self):
        source = self.make_request()
        history = consumption.consume_difficult_terrain_charge_lost_aim(source).state
        other_skill = Skill.BRAWN if self.skill is Skill.MELEE else Skill.MELEE
        for candidate in (source, self.make_request(renamed=True),
                          self.make_request(renamed=True, terrain_roll=10, already_tested=True),
                          self.make_request(renamed=True, skill=other_skill)):
            with self.assertRaisesRegex(ValueError, "source was already consumed"):
                replace(candidate, id="consume:new", state=history)
        with self.assertRaisesRegex(ValueError, "follow-up was already consumed"):
            replace(source, state=replace(source.state, consumed_aim_follow_up_ids=(source.follow_up.request_id,)))

    def test_shared_history_with_non_attack_attack_lost_and_applied(self):
        source = self.make_request()
        histories = (
            consumption.consume_lost_aim(non_attack_request()).state,
            consumption.consume_attack_lost_aim(attack_loss_request()).state,
            consumption.consume_charge_lost_aim(ordinary_request()).state,
            consumption.consume_long_charge_lost_aim(long_request(reached=False)).state,
            consumption.register_aim_ranged_attack(applied_request()).state,
        )
        for history in histories:
            with self.assertRaisesRegex(ValueError, "source was already consumed"):
                replace(source, state=history)
        history = consumption.consume_difficult_terrain_charge_lost_aim(source).state
        for other in (non_attack_request(), attack_loss_request(), ordinary_request(), long_request(), applied_request()):
            with self.assertRaisesRegex(ValueError, "source was already consumed"):
                replace(other, state=history)

    def test_actor_action_and_receipt_binding(self):
        source = self.make_request()
        for changes in (
            {"state": replace(source.state, actor_id="other")},
            {"execution": self.make_request(renamed=True).execution},
            {"follow_up": resolve_aim_follow_up(replace(source.follow_up.source_request, next_action_id="other"))},
            {"follow_up": resolve_aim_follow_up(replace(source.follow_up.source_request,
                next_action_id=source.execution.charge_action_request.id))},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(source, **changes)
        for changes in ({"actor_id": "other"}, {"round_number": 2}, {"executor_rule_id": "foreign"},
                        {"slot_index": 1}, {"id": "other"}):
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
            consumption.consume_difficult_terrain_charge_lost_aim(self.make_request(later_round=later))
        with self.assertRaisesRegex(ValueError, "must follow Aim"):
            self.make_request(later_round=1)
        with self.assertRaisesRegex(ValueError, "first slot"):
            self.make_request(later_round=2, later_second=True)

    def test_unsupported_follow_ups_skills_and_old_consumers_remain_closed(self):
        source = self.make_request()
        for follow in (non_attack_request().follow_up, applied_request().execution.source_request.aim_follow_up,
                       attack_loss_request().follow_up):
            with self.assertRaisesRegex(ValueError, "requires LOST|Charge follow-up"):
                replace(source, follow_up=follow)
        with self.assertRaisesRegex(ValueError, "requires Melee"):
            self.make_request(skill=Skill.SHOOTING)
        with self.assertRaisesRegex(ValueError, "non-attacking"):
            replace(non_attack_request(), follow_up=source.follow_up, action=source.execution.slot.execution)
        with self.assertRaises(TypeError):
            replace(attack_loss_request(), follow_up=source.follow_up, execution=source.execution)
        for other in (ordinary_request(), long_request()):
            with self.assertRaises(TypeError):
                replace(other, follow_up=source.follow_up, execution=source.execution)
            with self.assertRaises(TypeError):
                replace(source, execution=other.execution)

    def test_nested_traversal_conditions_kernel_and_source_binding(self):
        source = self.make_request(terrain_roll=10)
        execution = source.execution
        for changes in (
            {"conditions": execution.previous_conditions},
            {"terrain_traversal": self.make_request().execution.terrain_traversal},
            {"previous_spatial_state": execution.terrain_traversal.previous_state},
            {"charge_action_request": replace(execution.charge_action_request,
                kernel_request=replace(execution.source_kernel_request, id="other"))},
            {"charge_action_request": replace(execution.charge_action_request,
                attack_skill=Skill.BRAWN if self.skill is Skill.MELEE else Skill.MELEE)},
            {"resolution": None},
        ):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(source, execution=replace(execution, **changes))

    def test_returned_history_rejects_preparation_with_renamed_ids(self):
        for terrain_roll, tested in product((1, 10), (False, True)):
            source = self.make_request(terrain_roll=terrain_roll, already_tested=tested)
            result = consumption.consume_difficult_terrain_charge_lost_aim(source)
            candidate = replace(preparation_request(RangedWeaponId.LONGBOW,
                attack=replace(attack_execution_request(), id="attack:new"),
                aim=source.follow_up.source_request.aim), id="prepare:new")
            with patch("towr.rules.ranged_weapon_attack_preparation.prepare_ranged_weapon_attack") as prepare:
                with self.assertRaisesRegex(ValueError, "source was already consumed"):
                    prepare_ranged_weapon_attack_with_aim_history(result.state, candidate)
            prepare.assert_not_called()

    def test_types_result_provenance_history_and_trace(self):
        source = self.make_request()
        for changes in ({"id": ""}, {"rule_id": "foreign"}, {"state": None}, {"follow_up": None},
                        {"execution": None}, {"execution": source.execution.slot.execution}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(source, **changes)
        with self.assertRaises(TypeError):
            consumption.consume_difficult_terrain_charge_lost_aim(None)
        result = consumption.consume_difficult_terrain_charge_lost_aim(source)
        for changes in ({"request_id": "other"}, {"rule_id": "other"}, {"source_request": None},
                        {"source_request": replace(source, id="other")}, {"previous_state": result.state},
                        {"state": source.state}, {"state": replace(result.state, actor_id="other")},
                        {"applied_rule_ids": ()}, {"applied_rule_ids": (*result.applied_rule_ids, "foreign")}):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(result, **changes)

    def test_result_failure_leaves_input_snapshots_unchanged(self):
        source = self.make_request()
        before = deepcopy(source)
        with patch.object(consumption, "AimDifficultTerrainChargeLossConsumptionResult", side_effect=RuntimeError("failed")):
            with self.assertRaisesRegex(RuntimeError, "failed"):
                consumption.consume_difficult_terrain_charge_lost_aim(source)
        self.assertEqual(source, before)


class K1AimDifficultTerrainBrawnChargeLossConsumptionTests(K1AimDifficultTerrainChargeLossConsumptionTests):
    skill = Skill.BRAWN


if __name__ == "__main__":
    unittest.main()
