from copy import deepcopy
from dataclasses import replace
from itertools import product
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_aim_charge_loss_consumption import pending_inputs, request as ordinary_request
from tests.unit.test_k1_aim_difficult_terrain_charge_loss_consumption import request as completed_request
from tests.unit.test_k1_aim_long_charge_loss_consumption import request as long_request
from tests.unit.test_k1_difficult_terrain_charge_action_execution import terrain_request
from towr.domain.condition_models import Condition, ConditionState
from towr.rules.test_resolution import resolve_test
from towr.rules.condition_effect_resolution import resolve_condition_application
from towr.rules.aim_resolution import resolve_aim_follow_up
from tests.unit.test_k1_aim_consumption_resolution import request as non_attack_request
from tests.unit.test_k1_aim_attack_consumption import request as applied_request
from tests.unit.test_k1_aim_attack_loss_consumption import request as attack_loss_request
from tests.unit.test_k1_aim_resolution import attack_execution_request
from tests.unit.test_k1_ranged_weapon_attack_preparation import preparation_request
from towr.domain.aim_consumption_models import AimConsumptionState, RegisteredAimLossDifficultTerrainChargeExecutionRequest
from towr.domain.attack_models import AttackOutcome
from towr.domain.movement_models import MovementSpeed
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.resolution_models import AttackerStaggerRequest
from towr.domain.test_models import Skill
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind
from towr.rules import aim_consumption_resolution as consumption
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack_with_aim_history


def request(*, already_tested=False, **kwargs):
    follow, charge = pending_inputs(**kwargs)
    state = charge.spatial_state
    if already_tested:
        state = replace(state, difficult_terrain_tested_entity_ids=("hero",))
    charge = replace(charge, spatial_state=state, crosses_difficult_terrain=True)
    terrain = terrain_request(charge.round_state, state, charge.actor_conditions)
    if kwargs.get("renamed"):
        terrain = replace(terrain, id="terrain:new", athletics_test=replace(terrain.athletics_test, id="athletics:new"))
    action_id = "composite:new" if kwargs.get("renamed") else "execute:terrain-charge"
    follow = resolve_aim_follow_up(replace(follow.source_request, next_action_id=action_id))
    return RegisteredAimLossDifficultTerrainChargeExecutionRequest(
        "registered:charge", AimConsumptionState("hero", ("source:older",), ("follow:older", "follow:prior")),
        follow, action_id, charge, terrain,
    )


class K1RegisteredAimLossDifficultTerrainChargeTests(unittest.TestCase):
    skill = Skill.MELEE

    @property
    def charge_dice(self):
        return 2 if self.skill is Skill.MELEE else 1

    def make_request(self, **kwargs):
        kwargs.setdefault("skill", self.skill)
        return request(**kwargs)

    def test_one_charge_kernel_receipt_registration_for_hit_miss_aim_zero_positive_and_later_turn(self):
        for values, hit, later, target, terrain_roll, tested in product(
            ((10, 10, 10), (1, 2, 10)), (False, True), (None, 2), ("enemy", "enemy:other"), (1, 10), (False, True),
        ):
            with self.subTest(values=values, hit=hit, later=later, target=target, terrain_roll=terrain_roll, tested=tested):
                source = self.make_request(values=values, later_round=later, aim_target=target, already_tested=tested)
                before = deepcopy(source)
                rng, decisions = SequenceRandom([terrain_roll, 1 if hit else 10, *([10] * (self.charge_dice - 1)), 7]), Mock()
                with (
                    patch.object(consumption, "resolve_difficult_terrain_traversal",
                                 wraps=consumption.resolve_difficult_terrain_traversal) as traverse,
                    patch.object(consumption, "execute_difficult_terrain_charge_action", wraps=consumption.execute_difficult_terrain_charge_action) as execute,
                    patch.object(consumption, "consume_difficult_terrain_charge_lost_aim", wraps=consumption.consume_difficult_terrain_charge_lost_aim) as register,
                    patch("towr.rules.charge_action_execution.resolve_kernel_attack", wraps=resolve_kernel_attack) as kernel,
                    patch("towr.rules.difficult_terrain_resolution.resolve_test", wraps=resolve_test) as athletics,
                    patch("towr.rules.difficult_terrain_resolution.resolve_condition_application",
                          wraps=resolve_condition_application) as prone,
                ):
                    result = consumption.execute_registered_aim_loss_difficult_terrain_charge(source, rng, decisions=decisions)
                traverse.assert_called_once_with(source.terrain, rng, decisions=decisions)
                athletics.assert_called_once_with(source.terrain.athletics_test, rng, decisions=decisions)
                self.assertEqual(prone.call_count, int(terrain_roll == 10))
                execute.assert_called_once()
                composite = execute.call_args.args[0]
                self.assertEqual(execute.call_args.args[1:], (rng,))
                self.assertEqual(execute.call_args.kwargs, {"decisions": decisions})
                self.assertIs(composite.charge_action, source.charge)
                self.assertIs(composite.terrain_traversal, result.execution.terrain_traversal)
                kernel.assert_called_once()
                self.assertEqual(kernel.call_args.kwargs, {"decisions": decisions})
                register.assert_called_once_with(result.registration.source_request)
                self.assertIs(result.execution, result.registration.source_request.execution)
                self.assertIs(result.state, result.registration.state)
                self.assertIs(result.registration.previous_state, source.state)
                self.assertIs(result.registration.source_request.follow_up, source.follow_up)
                self.assertEqual(result.state.consumed_aim_source_ids, ("source:older", "aim:execute"))
                self.assertEqual(result.state.consumed_aim_follow_up_ids, ("follow:older", "follow:prior", "follow:charge"))
                execution = result.execution
                self.assertEqual(execution.resolution.attack.attacker_test.trace.rolled_dice, self.charge_dice)
                self.assertEqual(execution.resolution.attack.attacker_test.trace.regular_dice_delta, self.charge_dice - 1)
                self.assertIs(execution.resolution.attack.outcome, AttackOutcome.HIT if hit else AttackOutcome.MISS)
                self.assertEqual(execution.resolution.target_state.conditions.has(Condition.STAGGERED), hit)
                self.assertEqual(execution.resolution.follow_ups, () if hit else (
                    AttackerStaggerRequest(source.charge.kernel_request.attack.id),))
                if self.skill is Skill.BRAWN:
                    self.assertIsNone(execution.melee_bonus)
                    self.assertIs(execution.kernel_request, source.charge.kernel_request)
                self.assertEqual(execution.terrain_traversal.previous_state, source.terrain.state)
                self.assertIs(execution.previous_spatial_state, execution.terrain_traversal.state)
                self.assertIs(execution.conditions, execution.terrain_traversal.conditions)
                self.assertEqual(execution.conditions.has(Condition.PRONE), terrain_roll == 10)
                self.assertEqual(execution.spatial_state.placement_for("hero").zone_id, "zone:b")
                self.assertEqual(execution.round_state.active_turn.action_slots[:-1], source.charge.round_state.active_turn.action_slots[:-1])
                self.assertEqual(execution.slot.execution.id, source.action_id)
                self.assertTrue(execution.slot.executed)
                self.assertEqual(rng.randint(1, 10), 7)
                self.assertEqual(result.applied_rule_ids, tuple(dict.fromkeys((source.rule_id, *result.registration.applied_rule_ids))))
                self.assertEqual(source, before)

    def test_renamed_replay_and_shared_histories_fail_before_charge_rng_or_decisions(self):
        source = self.make_request()
        histories = (
            consumption.execute_registered_aim_loss_difficult_terrain_charge(source, SequenceRandom([1, *([10] * self.charge_dice)])).state,
            consumption.execute_registered_aim_loss_difficult_terrain_charge(source, SequenceRandom([10, *([10] * self.charge_dice)])).state,
            consumption.consume_difficult_terrain_charge_lost_aim(completed_request()).state,
            consumption.consume_charge_lost_aim(ordinary_request()).state,
            consumption.consume_long_charge_lost_aim(long_request(reached=False)).state,
            consumption.consume_lost_aim(non_attack_request()).state,
            consumption.consume_attack_lost_aim(attack_loss_request()).state,
            consumption.register_aim_ranged_attack(applied_request()).state,
        )
        other_skill = Skill.BRAWN if self.skill is Skill.MELEE else Skill.MELEE
        for history, candidate in product(histories, (source, self.make_request(renamed=True),
                self.make_request(renamed=True, skill=other_skill, already_tested=True))):
            rng, decisions = Mock(), Mock()
            with (
                self.subTest(id=candidate.charge.id, history=history),
                patch.object(consumption, "execute_difficult_terrain_charge_action") as execute,
                patch.object(consumption, "resolve_difficult_terrain_traversal") as traverse,
            ):
                with self.assertRaisesRegex(ValueError, "source was already consumed"):
                    consumption.execute_registered_aim_loss_difficult_terrain_charge(
                        replace(candidate, id="wrapper:new", state=history), rng, decisions=decisions,
                    )
            execute.assert_not_called()
            traverse.assert_not_called()
            self.assertEqual(rng.mock_calls, [])
            self.assertEqual(decisions.mock_calls, [])

    def test_actor_action_slot_and_history_guards_before_executor(self):
        source = self.make_request()
        turn = source.charge.round_state.active_turn
        wrong_slot = replace(turn.action_slots[-1], declaration=CombatActionDeclaration(CombatActionKind.RECOVER))
        wrong_charge = replace(source.charge, round_state=replace(source.charge.round_state,
            active_turn=replace(turn, action_slots=(*turn.action_slots[:-1], wrong_slot))))
        for changes in (
            {"state": replace(source.state, actor_id="other")},
            {"state": replace(source.state, consumed_aim_follow_up_ids=(source.follow_up.request_id,))},
            {"action_id": "different"}, {"action_id": source.charge.id}, {"charge": wrong_charge},
            {"charge": replace(source.charge, rule_id="foreign")},
            {"follow_up": non_attack_request().follow_up},
        ):
            rng = Mock()
            with self.subTest(changes=changes), patch.object(consumption, "execute_difficult_terrain_charge_action") as execute:
                with self.assertRaises(ValueError):
                    consumption.execute_registered_aim_loss_difficult_terrain_charge(replace(source, **changes), rng)
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])

    def test_unsupported_skill_and_chronology_before_executor(self):
        for kwargs in ({"skill": Skill.SHOOTING}, {"later_round": 1}, {"later_round": 2, "later_second": True}):
            rng = Mock()
            with self.subTest(kwargs=kwargs), patch.object(consumption, "execute_difficult_terrain_charge_action") as execute:
                with self.assertRaises(ValueError):
                    consumption.execute_registered_aim_loss_difficult_terrain_charge(self.make_request(**kwargs), rng)
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])

    def test_runtime_rechecks_shared_preflight(self):
        source, rng = self.make_request(), Mock()
        with (
            patch.object(consumption, "_validate_terrain_charge_loss_preflight", side_effect=ValueError("preflight failed")) as check,
            patch.object(consumption, "execute_difficult_terrain_charge_action") as execute,
            patch.object(consumption, "resolve_difficult_terrain_traversal") as traverse,
        ):
            with self.assertRaisesRegex(ValueError, "preflight failed"):
                consumption.execute_registered_aim_loss_difficult_terrain_charge(source, rng)
        check.assert_called_once_with(source.state, source.follow_up, source.action_id, source.charge, source.terrain)
        execute.assert_not_called()
        traverse.assert_not_called()
        self.assertEqual(rng.mock_calls, [])

    def test_charge_guards_and_rng_failure_preserve_inputs_without_registration(self):
        source = self.make_request()
        for charge in (replace(source.charge, speed=MovementSpeed.SLOW), replace(source.charge, actor_began_turn_in_enemy_close_range=True)):
            rng = Mock()
            with patch.object(consumption, "consume_difficult_terrain_charge_lost_aim") as register:
                with self.assertRaises(ValueError):
                    consumption.execute_registered_aim_loss_difficult_terrain_charge(replace(source, charge=charge), rng)
            register.assert_not_called()
            self.assertEqual(rng.mock_calls, [])
        before = deepcopy(source)
        rng = Mock()
        rng.randint.side_effect = [1, RuntimeError("RNG failed")]
        with patch.object(consumption, "consume_difficult_terrain_charge_lost_aim") as register:
            with self.assertRaisesRegex(RuntimeError, "RNG failed"):
                consumption.execute_registered_aim_loss_difficult_terrain_charge(source, rng)
        register.assert_not_called()
        self.assertEqual(source, before)
        self.assertEqual(rng.randint.call_count, 2)

    def test_pending_pair_mismatches_fail_before_traversal(self):
        source = self.make_request()
        for terrain in (
            replace(source.terrain, state=replace(source.terrain.state, free_move_used_entity_ids=())),
            replace(source.terrain, round_state=replace(source.terrain.round_state, completed_turn_entity_ids=("ally",))),
            replace(source.terrain, actor_conditions=ConditionState(frozenset({Condition.STAGGERED}))),
            replace(source.terrain, destination_zone_id="zone:c"),
            replace(source.terrain, path_entity_ids=("ally",)),
            replace(source.terrain, crosses_obstacle=True),
            replace(source.terrain, rule_id="foreign"),
        ):
            rng = Mock()
            with self.subTest(terrain=terrain), patch.object(consumption, "resolve_difficult_terrain_traversal") as traverse:
                with self.assertRaises(ValueError):
                    consumption.execute_registered_aim_loss_difficult_terrain_charge(replace(source, terrain=terrain), rng)
            traverse.assert_not_called()
            self.assertEqual(rng.mock_calls, [])

    def test_charge_and_geometry_guards_before_first_rng(self):
        source = self.make_request()
        for charge_changes, terrain_changes in (
            ({"reaches_target_close_range": False}, {}),
            ({"melee_bonus_rule_id": "foreign"}, {}),
            ({"actor_conditions": ConditionState(frozenset({Condition.BURDENED}))},
             {"actor_conditions": ConditionState(frozenset({Condition.BURDENED}))}),
            ({"actor_conditions": ConditionState(frozenset({Condition.PRONE}))},
             {"actor_conditions": ConditionState(frozenset({Condition.PRONE}))}),
            ({"crosses_obstacle": True}, {"crosses_obstacle": True}),
            ({"path_entity_ids": ("blocker",)}, {"path_entity_ids": ("blocker",)}),
            ({"kernel_request": replace(source.charge.kernel_request,
                attack=replace(source.charge.kernel_request.attack, is_close_range=False))}, {}),
        ):
            rng = Mock()
            with self.subTest(charge=charge_changes), patch.object(consumption, "execute_difficult_terrain_charge_action") as attack:
                with self.assertRaises(ValueError):
                    changed = replace(source, charge=replace(source.charge, **charge_changes),
                                      terrain=replace(source.terrain, **terrain_changes))
                    consumption.execute_registered_aim_loss_difficult_terrain_charge(changed, rng)
            attack.assert_not_called()
            self.assertEqual(rng.mock_calls, [])

    def test_registration_or_result_failure_preserves_snapshots_without_undoing_rng(self):
        for stage, terrain_roll in product(
            ("consume_difficult_terrain_charge_lost_aim", "RegisteredAimLossDifficultTerrainChargeExecutionResult"), (1, 10),
        ):
            source, rng = self.make_request(), SequenceRandom([terrain_roll, *([10] * self.charge_dice), 7])
            before = deepcopy(source)
            with self.subTest(stage=stage), patch.object(consumption, stage, side_effect=RuntimeError("stage failed")):
                with self.assertRaisesRegex(RuntimeError, "stage failed"):
                    consumption.execute_registered_aim_loss_difficult_terrain_charge(source, rng)
            self.assertEqual(source, before)
            self.assertEqual(rng.randint(1, 10), 7)

    def test_result_binds_charge_source_states_kernel_history_and_exact_trace(self):
        source = self.make_request()
        result = consumption.execute_registered_aim_loss_difficult_terrain_charge(source, SequenceRandom([1, *([10] * self.charge_dice)]))
        other = consumption.execute_registered_aim_loss_difficult_terrain_charge(self.make_request(renamed=True), SequenceRandom([1, *([10] * self.charge_dice)]))
        changed_charges = (
            replace(source.charge, kernel_request=replace(source.charge.kernel_request, id="other")),
            replace(source.charge, speed=MovementSpeed.FAST),
            replace(source.charge, attack_skill=Skill.BRAWN if self.skill is Skill.MELEE else Skill.MELEE),
        )
        for changes in (
            {"request_id": "other"}, {"rule_id": "other"}, {"source_request": None},
            {"registration": None}, {"registration": other.registration},
            {"source_request": replace(source, id="other")},
            {"source_request": replace(source, state=replace(source.state, consumed_aim_source_ids=("other",)))},
            {"source_request": replace(source, terrain=replace(source.terrain,
                athletics_test=replace(source.terrain.athletics_test, id="other")))},
            *({"source_request": replace(source, charge=c)} for c in changed_charges),
            {"applied_rule_ids": ()}, {"applied_rule_ids": (*result.applied_rule_ids, "foreign")},
        ):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(result, **changes)

    def test_types_and_next_preparation_with_returned_history(self):
        source = self.make_request()
        for changes in ({"id": ""}, {"rule_id": "other"}, {"state": None}, {"follow_up": None}, {"charge": None}):
            with self.assertRaises((TypeError, ValueError)):
                replace(source, **changes)
        with self.assertRaises(TypeError):
            consumption.execute_registered_aim_loss_difficult_terrain_charge(None, Mock())
        result = consumption.execute_registered_aim_loss_difficult_terrain_charge(source, SequenceRandom([1, *([10] * self.charge_dice)]))
        candidate = replace(preparation_request(RangedWeaponId.LONGBOW,
            aim=source.follow_up.source_request.aim, attack=replace(attack_execution_request(), id="attack:new")), id="prepare:new")
        with patch("towr.rules.ranged_weapon_attack_preparation.prepare_ranged_weapon_attack") as prepare:
            with self.assertRaisesRegex(ValueError, "source was already consumed"):
                prepare_ranged_weapon_attack_with_aim_history(result.state, candidate)
        prepare.assert_not_called()


class K1RegisteredAimLossDifficultTerrainBrawnChargeTests(K1RegisteredAimLossDifficultTerrainChargeTests):
    skill = Skill.BRAWN


if __name__ == "__main__":
    unittest.main()
