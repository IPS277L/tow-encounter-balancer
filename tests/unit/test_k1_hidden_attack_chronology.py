from __future__ import annotations

from dataclasses import replace
import unittest
from unittest.mock import Mock

from tests.helpers import SequenceRandom
from tests.unit.test_k1_aim_resolution import aim_request, attack_execution_request
from tests.unit.test_k1_hidden_attack_resolution import execution_request
from tests.unit.test_k1_hidden_ranged_weapon_attack_resolution import combined_request
from tests.unit.test_k1_move_quietly_resolution import (
    active_round,
    move_quietly_declaration,
    request as quietly_request,
    reserve_action,
    spatial_state,
)
from tests.unit.test_k1_ranged_weapon_attack_preparation import preparation_request
from towr.domain.hiding_position_models import (
    HidingPositionState,
    RegisteredHiddenAttackExecutionRequest,
)
from towr.domain.prepared_hidden_ranged_attack_models import (
    PreparedHiddenRangedAttackExecutionRequest,
)
from towr.domain.prepared_ranged_weapon_attack_models import (
    PreparedRangedWeaponAttackExecutionRequest,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.reload_models import create_initial_ranged_weapon_reload_state
from towr.domain.turn_models import (
    ActionSlotGrant,
    CombatActionDeclaration,
    CombatActionKind,
)
from towr.rules.aim_resolution import execute_aim_action
from towr.rules.hidden_attack_resolution import execute_move_quietly_hidden_attack
from towr.rules.hidden_ranged_weapon_attack_resolution import (
    execute_move_quietly_hidden_ranged_attack,
)
from towr.rules.hiding_position_resolution import execute_registered_hidden_attack
from towr.rules.move_quietly_resolution import execute_move_quietly_action
from towr.rules.prepared_hidden_ranged_attack_resolution import (
    execute_prepared_hidden_ranged_attack,
)
from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack


def round_before_slot(round_number, slot_index):
    state = replace(active_round(), round_number=round_number)
    if slot_index == 2:
        state = reserve_action(state, CombatActionDeclaration(CombatActionKind.AIM))
        state = execute_aim_action(
            aim_request(state, target_id="scout"), SequenceRandom([10, 10, 10]),
        ).round_state
    return state


def completed_quietly(round_number, slot_index):
    state = reserve_action(
        round_before_slot(round_number, slot_index), move_quietly_declaration(),
        grant=ActionSlotGrant.STANDARD if slot_index == 1 else ActionSlotGrant.ABILITY,
    )
    return execute_move_quietly_action(quietly_request(
        round_state=state,
        state=replace(spatial_state(), round_number=round_number),
        slot_index=slot_index,
    ), SequenceRandom([1, 10, 10]))


def attack_at(round_number, slot_index, *, quietly=None):
    state = (quietly.round_state if quietly is not None
             else round_before_slot(round_number, slot_index))
    state = reserve_action(
        state, CombatActionDeclaration(CombatActionKind.ATTACK),
        grant=ActionSlotGrant.STANDARD if slot_index == 1 else ActionSlotGrant.ABILITY,
    )
    return attack_execution_request(state=state, slot_index=slot_index, target_id="scout")


def build_branch(quietly, attack, branch, registered):
    # Every public composition requires this source-bound hidden preflight first.
    hidden = execution_request(
        move_quietly=quietly, attack=attack,
        spatial_state=replace(quietly.spatial_state, round_number=attack.state.round_number),
    )
    if branch == "ordinary":
        request, execute = hidden, execute_move_quietly_hidden_attack
    elif branch == "profile-aware":
        request = combined_request(create_initial_ranged_weapon_reload_state(
            "bow:hero", RangedWeaponId.LONGBOW,
        ), hidden=hidden)
        execute = execute_move_quietly_hidden_ranged_attack
    else:
        prepared = prepare_ranged_weapon_attack(preparation_request(
            RangedWeaponId.LONGBOW, attack=attack,
        ))
        request = PreparedHiddenRangedAttackExecutionRequest(
            "prepared:hidden", replace(hidden, attack=prepared.execution.attack),
            PreparedRangedWeaponAttackExecutionRequest("prepared:execute", prepared),
        )
        execute = execute_prepared_hidden_ranged_attack
    if registered:
        request = RegisteredHiddenAttackExecutionRequest(
            "registered:execute", HidingPositionState("hero"), request,
        )
        execute = execute_registered_hidden_attack
    return request, execute


class K1HiddenAttackChronologyTests(unittest.TestCase):
    def assert_rejected_before_rng(self, source_round, source_slot, attack_round, attack_slot):
        quietly = completed_quietly(source_round, source_slot)
        attack = attack_at(attack_round, attack_slot)
        for branch in ("ordinary", "profile-aware", "prepared"):
            for registered in (False, True):
                with self.subTest(branch=branch, registered=registered):
                    rng, decisions = Mock(), Mock()
                    with self.assertRaisesRegex(ValueError, "hidden Attack must follow Move Quietly"):
                        request, execute = build_branch(quietly, attack, branch, registered)
                        execute(request, rng, decisions=decisions)
                    self.assertEqual(rng.mock_calls, [])
                    self.assertEqual(decisions.mock_calls, [])
        self.assertFalse(attack.state.active_turn.action_slots[attack_slot - 1].executed)

    def test_earlier_round_rejected_even_with_a_later_slot(self):
        self.assert_rejected_before_rng(2, 1, 1, 2)

    def test_same_round_same_slot_rejected(self):
        for slot in (1, 2):
            with self.subTest(slot=slot):
                self.assert_rejected_before_rng(1, slot, 1, slot)

    def test_same_round_earlier_slot_rejected(self):
        self.assert_rejected_before_rng(1, 2, 1, 1)

    def assert_accepted(self, quietly, attack):
        for branch in ("ordinary", "profile-aware", "prepared"):
            for registered in (False, True):
                with self.subTest(branch=branch, registered=registered):
                    request, execute = build_branch(quietly, attack, branch, registered)
                    rng = SequenceRandom([10, 10, 10, 7])
                    result = execute(request, rng)
                    self.assertEqual(rng.randint(1, 10), 7)
                    hidden = result.execution if registered else result
                    actual = hidden.attack if branch == "ordinary" else hidden.ranged_attack.attack
                    self.assertEqual(actual.slot_index, attack.slot_index)
                    self.assertEqual(actual.state.round_number, attack.state.round_number)
                    self.assertTrue(actual.slot.executed)
                    self.assertEqual(hidden.consumed_opportunity_ids,
                                     (quietly.hidden_attack_opportunity.id,))
                    if registered:
                        self.assertEqual(result.state.used_hiding_position_ids, ("hiding:wall",))

    def test_later_slot_of_same_round_is_allowed(self):
        quietly = completed_quietly(1, 1)
        self.assert_accepted(quietly, attack_at(1, 2, quietly=quietly))

    def test_first_slot_of_later_round_is_allowed_after_second_slot_hiding(self):
        quietly = completed_quietly(1, 2)
        self.assert_accepted(quietly, attack_at(2, 1))

    def test_opportunity_has_no_automatic_next_round_expiry(self):
        quietly = completed_quietly(1, 1)
        self.assert_accepted(quietly, attack_at(4, 1))

    def assert_source_slot_rejected(self, quietly, attack):
        for branch in ("ordinary", "profile-aware", "prepared"):
            for registered in (False, True):
                with self.subTest(branch=branch, registered=registered):
                    rng, decisions = Mock(), Mock()
                    with self.assertRaisesRegex(ValueError, "retain the completed Move Quietly slot"):
                        request, execute = build_branch(quietly, attack, branch, registered)
                        execute(request, rng, decisions=decisions)
                    self.assertEqual(rng.mock_calls, [])
                    self.assertEqual(decisions.mock_calls, [])

    def test_same_round_requires_active_turn_and_source_slot(self):
        quietly = completed_quietly(1, 1)
        attack = attack_at(1, 2, quietly=quietly)
        for turn in (None, replace(attack.state.active_turn, action_slots=())):
            with self.subTest(turn=turn):
                self.assert_source_slot_rejected(
                    quietly, replace(attack, state=replace(attack.state, active_turn=turn)),
                )

    def test_same_round_rejects_source_slot_without_receipt(self):
        quietly = completed_quietly(1, 1)
        attack = attack_at(1, 2, quietly=quietly)
        turn = attack.state.active_turn
        changed = replace(turn, action_slots=(
            replace(turn.action_slots[0], execution=None), turn.action_slots[1],
        ))
        self.assert_source_slot_rejected(
            quietly, replace(attack, state=replace(attack.state, active_turn=changed)),
        )
        self.assertTrue(attack.state.active_turn.action_slots[0].executed)

    def test_same_round_rejects_other_completed_action_at_source_slot(self):
        quietly = completed_quietly(1, 1)
        # This branch has a completed Aim in slot 1, not the source Move Quietly.
        self.assert_source_slot_rejected(quietly, attack_at(1, 2))

    def test_same_round_checks_complete_receipt_provenance(self):
        quietly = completed_quietly(1, 1)
        attack = attack_at(1, 2, quietly=quietly)
        turn = attack.state.active_turn
        original = turn.action_slots[0]
        for field in ("id", "source_request_id", "result_request_id", "executor_rule_id"):
            with self.subTest(field=field):
                foreign = replace(original, execution=replace(
                    original.execution, **{field: "foreign:receipt"},
                ))
                changed = replace(turn, action_slots=(foreign, turn.action_slots[1]))
                self.assert_source_slot_rejected(
                    quietly, replace(attack, state=replace(attack.state, active_turn=changed)),
                )
        self.assertEqual(turn.action_slots[0], quietly.slot)

    def test_equal_copy_of_completed_source_slot_is_accepted(self):
        quietly = completed_quietly(1, 1)
        attack = attack_at(1, 2, quietly=quietly)
        copied = replace(quietly.slot, execution=replace(quietly.slot.execution))
        self.assertIsNot(copied, quietly.slot)
        self.assertIsNot(copied.execution, quietly.slot.execution)
        turn = replace(attack.state.active_turn, action_slots=(
            copied, attack.state.active_turn.action_slots[1],
        ))
        self.assert_accepted(quietly, replace(attack, state=replace(attack.state, active_turn=turn)))

    def test_later_round_may_have_a_different_action_at_old_source_slot(self):
        quietly = completed_quietly(1, 1)
        # The new turn's slot 1 contains Aim, while Move Quietly belongs to round 1.
        self.assert_accepted(quietly, attack_at(2, 2))
