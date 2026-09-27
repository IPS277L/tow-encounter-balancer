from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_registered_hidden_aim_attack import request as applied_hidden_request
from tests.unit.test_k1_aim_resolution import follow_up_request
from tests.unit.test_k1_move_quietly_resolution import reserve_action
from tests.unit.test_k1_aim_prepared_attack_loss_consumption import request as prepared_loss_request
from tests.unit.test_k1_aim_consumption_resolution import request as non_attack_request
from towr.domain.aim_models import AimFollowUpOutcome
from towr.domain.test_models import Skill
from towr.domain.turn_models import ActionSlotGrant, CombatActionDeclaration, CombatActionKind
from towr.rules import aim_consumption_resolution as consumption
from towr.rules.aim_resolution import execute_aim_action, resolve_aim_follow_up
from tests.unit.test_k1_registered_hidden_attack_resolution import branches
from towr.domain.aim_consumption_models import AimConsumptionState
from towr.domain.attack_models import AttackOutcome
from towr.domain.hiding_position_models import HidingPositionState, RegisteredHiddenAttackExecutionRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.registered_hidden_aim_models import RegisteredHiddenAimLossAttackExecutionRequest
from towr.rules import hiding_position_resolution as hiding
from towr.rules import registered_hidden_aim_resolution as resolution
from towr.rules.kernel import resolve_kernel_attack
from towr.rules.move_quietly_resolution import execute_move_quietly_action
from towr.rules.ranged_weapon_attack_preparation import (
    prepare_ranged_weapon_attack,
    prepare_ranged_weapon_attack_with_aim_history,
)


def request(*, weapon=RangedWeaponId.CROSSBOW, values=(1, 2, 10), renamed=False):
    base = applied_hidden_request(weapon=weapon, values=values, renamed=renamed)
    combined = base.attack.attack
    raw = combined.prepared_attack.preparation.source_request
    aim = execute_aim_action(replace(raw.aim.source_request, target_id="guard"), SequenceRandom(values))
    attack = replace(raw.attack, state=reserve_action(aim.round_state,
        CombatActionDeclaration(CombatActionKind.ATTACK), grant=ActionSlotGrant.ABILITY))
    if renamed:
        attack = replace(attack, kernel_request=replace(attack.kernel_request, id="kernel:new",
            attack=replace(attack.kernel_request.attack, id="test:new")))
    preparation = prepare_ranged_weapon_attack(replace(raw, aim=None, attack=attack,
        next_reload_cycle_id="reload:new" if renamed and weapon is RangedWeaponId.CROSSBOW else raw.next_reload_cycle_id))
    prepared = replace(combined.prepared_attack, preparation=preparation)
    hidden = replace(combined.hidden_attack, attack=preparation.execution.attack)
    combined = replace(combined, hidden_attack=hidden, prepared_attack=prepared)
    follow = resolve_aim_follow_up(replace(follow_up_request(aim, attack=preparation.execution.attack, skill=Skill.SHOOTING),
        id="follow:lost:new" if renamed else "follow:lost"))
    return RegisteredHiddenAimLossAttackExecutionRequest(
        base.id, base.aim_state, follow, replace(base.attack, attack=combined))


class K1RegisteredHiddenAimLossAttackTests(unittest.TestCase):
    def test_one_kernel_receipt_and_each_registration_preserve_all_histories_and_traces(self):
        for weapon in (RangedWeaponId.LONGBOW, RangedWeaponId.CROSSBOW):
            for values in ((1, 2, 10), (10, 10, 10)):
                for hit in (False, True):
                    with self.subTest(weapon=weapon, values=values, hit=hit):
                        source = request(weapon=weapon, values=values)
                        before = deepcopy(source)
                        dice = 2
                        rng = SequenceRandom([1 if hit else 10, *([10] * (dice - 1)), 7])
                        decisions = Mock()
                        with (
                            patch.object(resolution, "execute_registered_hidden_attack", wraps=resolution.execute_registered_hidden_attack) as execute,
                            patch.object(hiding, "register_revealed_hiding_position", wraps=hiding.register_revealed_hiding_position) as hide_register,
                            patch.object(resolution, "consume_prepared_attack_lost_aim", wraps=resolution.consume_prepared_attack_lost_aim) as aim_register,
                            patch("towr.rules.attack_action_execution.resolve_kernel_attack", wraps=resolve_kernel_attack) as kernel,
                        ):
                            result = resolution.execute_registered_hidden_aim_loss_attack(source, rng, decisions=decisions)
                        execute.assert_called_once_with(source.attack, rng, decisions=decisions)
                        kernel.assert_called_once()
                        hide_register.assert_called_once_with(result.hidden_attack.registration.source_request)
                        aim_register.assert_called_once_with(result.aim_registration.source_request)
                        self.assertIs(result.execution, result.hidden_attack.execution)
                        self.assertIs(result.execution.prepared_attack, result.aim_registration.source_request.execution)
                        self.assertIs(result.aim_state, result.aim_registration.state)
                        self.assertIs(result.hiding_position_state, result.hidden_attack.state)
                        self.assertEqual(result.hiding_position_state.used_hiding_position_ids, ("hiding:older", "hiding:wall"))
                        self.assertEqual(result.hiding_position_state.consumed_attack_execution_ids,
                                         ("attack:older", source.attack.hidden_request.attack.id))
                        self.assertEqual(result.execution.consumed_opportunity_ids,
                                         ("hidden:older", source.attack.hidden_request.opportunity.id))
                        self.assertEqual(result.aim_state.consumed_aim_source_ids, ("source:older", "aim:execute"))
                        self.assertEqual(result.aim_state.consumed_aim_follow_up_ids,
                                         ("aim:older", "follow:prior", source.follow_up.request_id))
                        self.assertIs(source.follow_up.outcome, AimFollowUpOutcome.LOST)
                        self.assertIsNone(source.follow_up.modifier)
                        self.assertEqual(source.follow_up.source_request.aim.bonus.target_id, "guard")
                        self.assertEqual(source.attack.hidden_request.target_id, "scout")
                        self.assertEqual(result.execution.consumed_aim_follow_up_ids, source.aim_state.consumed_aim_follow_up_ids)
                        self.assertNotEqual(result.execution.consumed_aim_follow_up_ids, result.aim_state.consumed_aim_follow_up_ids)
                        shot = result.execution.ranged_attack
                        self.assertIsNone(shot.attack.resolution.attack.defender_test)
                        self.assertEqual(shot.attack.resolution.attack.outcome, AttackOutcome.HIT if hit else AttackOutcome.MISS)
                        self.assertEqual(shot.attack.resolution.attack.attacker_test.trace.rolled_dice, dice)
                        self.assertEqual(shot.attack.resolution.attack.attacker_test.trace.regular_dice_delta, 0)
                        old_slots = source.attack.hidden_request.attack.state.active_turn.action_slots
                        new_slots = shot.attack.state.active_turn.action_slots
                        self.assertEqual(new_slots[:-1], old_slots[:-1])
                        self.assertEqual(sum(s.executed for s in new_slots), sum(s.executed for s in old_slots) + 1)
                        self.assertEqual(shot.attack.slot.execution.id, source.attack.hidden_request.attack.id)
                        preparation = source.attack.attack.prepared_attack.preparation
                        self.assertTrue(set(preparation.applied_rule_ids) <= set(result.applied_rule_ids))
                        self.assertTrue(set(result.hidden_attack.applied_rule_ids) <= set(result.applied_rule_ids))
                        self.assertTrue(set(result.aim_registration.applied_rule_ids) <= set(result.applied_rule_ids))
                        if weapon is RangedWeaponId.CROSSBOW:
                            self.assertFalse(shot.weapon_state.loaded)
                            self.assertEqual(shot.weapon_state.reload_cycle_id, preparation.source_request.next_reload_cycle_id)
                            self.assertEqual(shot.weapon_state.reload_cycle_ids, (preparation.source_request.next_reload_cycle_id,))
                        else:
                            self.assertIs(shot.weapon_state, preparation.execution.weapon_state)
                        self.assertEqual(rng.randint(1, 10), 7)
                        self.assertEqual(source, before)

    def test_aim_replay_with_all_new_wrapper_attack_preparation_and_follow_up_ids(self):
        source = request()
        done = resolution.execute_registered_hidden_aim_loss_attack(source, SequenceRandom([10] * 2))
        for candidate in (source, request(renamed=True)):
            rng, decisions = Mock(), Mock()
            with self.subTest(id=candidate.id), patch.object(resolution, "execute_registered_hidden_attack") as execute:
                with self.assertRaisesRegex(ValueError, "Aim source was already consumed"):
                    resolution.execute_registered_hidden_aim_loss_attack(replace(candidate, aim_state=done.aim_state), rng, decisions=decisions)
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])
            self.assertEqual(decisions.mock_calls, [])

    def test_hiding_history_replay_with_renamed_attack_is_rejected_before_rng(self):
        source = request()
        done = resolution.execute_registered_hidden_aim_loss_attack(source, SequenceRandom([10] * 2))
        for candidate in (source, request(renamed=True)):
            rng = Mock()
            with self.subTest(id=candidate.id), patch.object(resolution, "execute_registered_hidden_attack") as execute:
                with self.assertRaisesRegex(ValueError, "already registered|already used"):
                    attack = replace(candidate.attack, state=done.hiding_position_state)
                    resolution.execute_registered_hidden_aim_loss_attack(replace(candidate, attack=attack), rng)
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])

    def test_actor_and_prefix_guards_for_both_histories(self):
        source = request()
        for state in (
            replace(source.aim_state, actor_id="other"),
            replace(source.aim_state, consumed_aim_follow_up_ids=()),
            replace(source.aim_state, consumed_aim_follow_up_ids=tuple(reversed(source.aim_state.consumed_aim_follow_up_ids))),
        ):
            with self.subTest(aim=state), self.assertRaises(ValueError):
                replace(source, aim_state=state)
        for state in (
            replace(source.attack.state, actor_id="other"),
            replace(source.attack.state, used_hiding_position_ids=()),
            replace(source.attack.state, used_hiding_position_ids=("different",)),
        ):
            with self.subTest(hiding=state), self.assertRaises(ValueError):
                replace(source, attack=replace(source.attack, state=state))

    def test_consumed_hidden_opportunity_and_aware_target_are_rejected(self):
        source = request()
        hidden = source.attack.hidden_request
        for changes in (
            {"consumed_opportunity_ids": (*hidden.consumed_opportunity_ids, hidden.opportunity.id)},
            {"target_is_unaware": False},
        ):
            rng = Mock()
            with self.subTest(changes=changes), patch.object(resolution, "execute_registered_hidden_attack") as execute:
                with self.assertRaises(ValueError):
                    combined = replace(source.attack.attack, hidden_attack=replace(hidden, **changes))
                    resolution.execute_registered_hidden_aim_loss_attack(replace(source, attack=replace(source.attack, attack=combined)), rng)
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])

    def test_applied_other_hidden_branches_and_bad_types_are_rejected(self):
        source = request()
        with self.assertRaisesRegex(ValueError, "direct no-Aim branch"):
            replace(source, attack=applied_hidden_request().attack)
        for attack, _ in branches():
            with self.subTest(type=type(attack)), self.assertRaises((ValueError, TypeError)):
                replace(source, attack=RegisteredHiddenAttackExecutionRequest("other", HidingPositionState("hero"), attack))
        for changes in ({"aim_state": None}, {"follow_up": None}, {"attack": None}, {"id": ""}, {"rule_id": "foreign"}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(source, **changes)
        with self.assertRaises(TypeError):
            resolution.execute_registered_hidden_aim_loss_attack(None, Mock())

    def test_runtime_preflight_runs_both_shared_guards_before_executor(self):
        source = request()
        module = "towr.domain.registered_hidden_aim_models"
        for stage in ("_validate_hiding_position_preflight", "_validate_prepared_attack_loss_preflight"):
            rng = Mock()
            with (
                self.subTest(stage=stage),
                patch(f"{module}.{stage}", side_effect=ValueError("preflight failed")) as guard,
                patch.object(resolution, "execute_registered_hidden_attack") as execute,
            ):
                with self.assertRaisesRegex(ValueError, "preflight failed"):
                    resolution.execute_registered_hidden_aim_loss_attack(source, rng)
            guard.assert_called_once()
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])

    def test_errors_preserve_inputs_without_rolling_back_rng(self):
        source = request()
        before = deepcopy(source)
        rng = Mock()
        rng.randint.side_effect = [1, RuntimeError("RNG failed")]
        with patch.object(resolution, "consume_prepared_attack_lost_aim") as register:
            with self.assertRaisesRegex(RuntimeError, "RNG failed"):
                resolution.execute_registered_hidden_aim_loss_attack(source, rng)
        register.assert_not_called()
        self.assertEqual(rng.randint.call_count, 2)
        self.assertEqual(source, before)
        for module, stage in (
            (hiding, "register_revealed_hiding_position"),
            (resolution, "consume_prepared_attack_lost_aim"),
            (resolution, "RegisteredHiddenAimLossAttackExecutionResult"),
        ):
            rng = SequenceRandom([10] * 2 + [7])
            with self.subTest(stage=stage), patch.object(module, stage, side_effect=RuntimeError("stage failed")):
                with self.assertRaisesRegex(RuntimeError, "stage failed"):
                    resolution.execute_registered_hidden_aim_loss_attack(source, rng)
            self.assertEqual(rng.randint(1, 10), 7)
            self.assertEqual(source, before)

    def test_result_provenance_links_both_registrations_and_exact_trace(self):
        source = request()
        result = resolution.execute_registered_hidden_aim_loss_attack(source, SequenceRandom([10] * 2))
        other = resolution.execute_registered_hidden_aim_loss_attack(request(renamed=True), SequenceRandom([10] * 2))
        for changes in (
            {"request_id": "other"}, {"rule_id": "other"}, {"source_request": None},
            {"hidden_attack": None}, {"aim_registration": None}, {"hidden_attack": other.hidden_attack},
            {"aim_registration": other.aim_registration}, {"applied_rule_ids": ()},
            {"applied_rule_ids": (*result.applied_rule_ids, "extra")},
            {"source_request": replace(source, aim_state=replace(source.aim_state, consumed_aim_source_ids=("different",)))},
        ):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(result, **changes)

    def test_returned_histories_drive_both_next_preparations(self):
        source = request()
        done = resolution.execute_registered_hidden_aim_loss_attack(source, SequenceRandom([10] * 2))
        raw = request(renamed=True).attack.attack.prepared_attack.preparation.source_request
        aim = source.follow_up.source_request.aim
        attack = replace(raw.attack, target_id=aim.bonus.target_id,
            kernel_request=replace(raw.attack.kernel_request, target_id=aim.bonus.target_id))
        with self.assertRaisesRegex(ValueError, "Aim source was already consumed"):
            prepare_ranged_weapon_attack_with_aim_history(done.aim_state, replace(raw, attack=attack, aim=aim))
        quietly = source.attack.hidden_request.move_quietly.source_request
        with self.assertRaises(ValueError):
            hiding.prepare_move_quietly_with_hiding_positions(done.hiding_position_state, quietly)
        fresh = hiding.prepare_move_quietly_with_hiding_positions(done.hiding_position_state,
            replace(quietly, id="quietly:new", hiding_position_id="hiding:new"))
        self.assertEqual(fresh.used_hiding_position_ids, ("hiding:older", "hiding:wall"))


    def test_shared_aim_history_blocks_cross_branch_reuse(self):
        source = request()
        done = resolution.execute_registered_hidden_aim_loss_attack(source, SequenceRandom([10, 10]))
        applied = applied_hidden_request()
        applied_done = resolution.execute_registered_hidden_aim_attack(applied, SequenceRandom([10] * 4))
        prepared = prepared_loss_request()
        non_attack = non_attack_request()
        histories = (applied_done.aim_state, consumption.consume_prepared_attack_lost_aim(prepared).state,
                     consumption.consume_lost_aim(non_attack).state)
        for history in histories:
            rng = Mock()
            with self.subTest(history=history), patch.object(resolution, "execute_registered_hidden_attack") as execute:
                with self.assertRaisesRegex(ValueError, "Aim source was already consumed"):
                    resolution.execute_registered_hidden_aim_loss_attack(replace(source, aim_state=history), rng)
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])
        with self.assertRaisesRegex(ValueError, "Aim source was already consumed"):
            replace(applied, aim_state=done.aim_state)
        with self.assertRaisesRegex(ValueError, "Aim source was already consumed"):
            replace(prepared, state=done.aim_state)

    def test_follow_up_exact_attack_and_chronology_fail_before_rng(self):
        source = request()
        follow_source = source.follow_up.source_request
        changed_attack = replace(follow_source.attack,
            kernel_request=replace(follow_source.attack.kernel_request, id="kernel:other"))
        pending = follow_source.aim.source_request
        future = execute_aim_action(replace(pending, round_state=replace(pending.round_state, round_number=3)),
                                    SequenceRandom([1, 2, 10]))
        for follow in (
            resolve_aim_follow_up(replace(follow_source, attack=changed_attack)),
            resolve_aim_follow_up(replace(follow_source, aim=future)),
            non_attack_request().follow_up,
        ):
            rng = Mock()
            with self.subTest(follow=follow), patch.object(resolution, "execute_registered_hidden_attack") as execute:
                with self.assertRaises(ValueError):
                    resolution.execute_registered_hidden_aim_loss_attack(replace(source, follow_up=follow), rng)
            execute.assert_not_called()
            self.assertEqual(rng.mock_calls, [])
        done = resolution.execute_registered_hidden_aim_loss_attack(source, SequenceRandom([10, 10]))
        renamed = replace(source, follow_up=resolve_aim_follow_up(replace(follow_source, id="follow:other")))
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(done, source_request=renamed)
