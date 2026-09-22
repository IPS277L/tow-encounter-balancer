from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError, replace

from tests.helpers import SequenceRandom
from tests.unit.test_k1_hidden_attack_resolution import execution_request
from tests.unit.test_k1_hidden_ranged_weapon_attack_resolution import combined_request
from tests.unit.test_k1_prepared_hidden_ranged_attack_resolution import request as prepared_request
from tests.unit.test_k1_move_quietly_resolution import (
    request as quietly_request,
    reserve_action,
    move_quietly_declaration,
)
from towr.domain.hiding_position_models import (
    HIDING_POSITION_REGISTRATION_RULE_ID,
    HidingPositionRegistrationRequest,
    HidingPositionState,
)
from towr.domain.move_quietly_models import MoveQuietlyHidingChoice
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.reload_models import create_initial_ranged_weapon_reload_state
from towr.domain.turn_models import CombatRoundState, CombatTurnStartRequest
from towr.rules.hidden_attack_resolution import execute_move_quietly_hidden_attack
from towr.rules.hidden_ranged_weapon_attack_resolution import execute_move_quietly_hidden_ranged_attack
from towr.rules.prepared_hidden_ranged_attack_resolution import execute_prepared_hidden_ranged_attack
from towr.rules.hiding_position_resolution import (
    prepare_move_quietly_with_hiding_positions,
    register_revealed_hiding_position,
)
from towr.rules.move_quietly_resolution import execute_move_quietly_action
from towr.rules.turn_resolution import start_combat_turn


def completed_attack():
    return execute_move_quietly_hidden_attack(execution_request(), SequenceRandom([1, 10]))


def registration(execution=None, state=None):
    return HidingPositionRegistrationRequest(
        "register:hidden", state or HidingPositionState("hero"),
        execution or completed_attack(),
    )


class K1HidingPositionResolutionTests(unittest.TestCase):
    def test_all_three_execution_paths_register_hit_and_miss_without_reexecution(self):
        for hit in (True, False):
            weapon = create_initial_ranged_weapon_reload_state("bow:hero", RangedWeaponId.LONGBOW)
            for source, execute in (
                (execution_request(), execute_move_quietly_hidden_attack),
                (combined_request(weapon), execute_move_quietly_hidden_ranged_attack),
                (prepared_request(), execute_prepared_hidden_ranged_attack),
            ):
                with self.subTest(hit=hit, executor=execute.__name__):
                    rng = SequenceRandom(([1, 10] if hit else [10, 10]) + [7])
                    execution = execute(source, rng)
                    request = registration(execution)
                    result = register_revealed_hiding_position(request)
                    self.assertEqual(rng.randint(1, 10), 7)
                    self.assertIs(result.source_request.execution, execution)
                    self.assertEqual(result.state.used_hiding_position_ids, ("hiding:wall",))
                    self.assertEqual(result.state.consumed_attack_execution_ids,
                                     (request.hidden_request.attack.id,))
                    self.assertEqual(result.previous_state, HidingPositionState("hero"))
                    self.assertEqual(result.applied_rule_ids, tuple(dict.fromkeys((
                        HIDING_POSITION_REGISTRATION_RULE_ID, *execution.applied_rule_ids,
                    ))))

    def test_replay_rejected_even_with_a_new_registration_id(self):
        request = registration()
        result = register_revealed_hiding_position(request)
        with self.assertRaisesRegex(ValueError, "already registered"):
            replace(request, id="registration:retry", state=result.state)

    def test_actor_scope_and_preparation_owner_are_checked(self):
        with self.assertRaisesRegex(ValueError, "another actor"):
            registration(state=HidingPositionState("ally"))
        with self.assertRaisesRegex(ValueError, "another actor"):
            prepare_move_quietly_with_hiding_positions(HidingPositionState("ally"), quietly_request())
        # Another actor's history does not globally reserve this position.
        ally = HidingPositionState("ally", ("hiding:wall",))
        self.assertEqual(register_revealed_hiding_position(registration()).state.used_hiding_position_ids,
                         ally.used_hiding_position_ids)

    def test_old_position_rejected_for_same_zone_and_route_before_rng(self):
        state = register_revealed_hiding_position(registration()).state
        for choice in (MoveQuietlyHidingChoice.HIDE_IN_CURRENT_ZONE,
                       MoveQuietlyHidingChoice.HIDE_ALONG_ROUTE):
            with self.subTest(choice=choice), self.assertRaisesRegex(ValueError, "new hiding position"):
                prepare_move_quietly_with_hiding_positions(state, quietly_request(
                    include_movement=choice is MoveQuietlyHidingChoice.HIDE_ALONG_ROUTE,
                    hiding_choice=choice,
                ))

    def test_next_round_new_hiding_and_attack_extend_both_histories(self):
        first = registration()
        state = register_revealed_hiding_position(first).state
        hidden = first.hidden_request
        round_state = start_combat_turn(CombatTurnStartRequest(
            "turn:hero:2", CombatRoundState(
                round_number=2, participants=hidden.attack.state.participants,
            ), "hero",
        )).state
        round_state = reserve_action(round_state, move_quietly_declaration())
        spatial = replace(hidden.spatial_state, round_number=2, free_move_used_entity_ids=())
        candidate = replace(quietly_request(
            round_state=round_state, state=spatial, include_movement=False,
            hiding_choice=MoveQuietlyHidingChoice.HIDE_IN_CURRENT_ZONE,
            hiding_position_id="hiding:tree",
        ), id="quietly:2")
        prepared = prepare_move_quietly_with_hiding_positions(state, candidate)
        self.assertEqual(candidate.used_hiding_position_ids, ())
        self.assertEqual(prepared.used_hiding_position_ids, ("hiding:wall",))
        quietly = execute_move_quietly_action(prepared, SequenceRandom([1, 10, 10]))
        next_hidden = execution_request(
            move_quietly=quietly, hiding_position_id="hiding:tree",
            consumed=first.execution.consumed_opportunity_ids,
        )
        next_hidden = replace(next_hidden, id="hidden:2",
                              attack=replace(next_hidden.attack, id="attack:2"))
        execution = execute_move_quietly_hidden_attack(next_hidden, SequenceRandom([10, 10]))
        second = register_revealed_hiding_position(registration(execution, state))
        self.assertEqual(second.state.used_hiding_position_ids, ("hiding:wall", "hiding:tree"))
        self.assertEqual(second.state.consumed_attack_execution_ids,
                         (hidden.attack.id, "attack:2"))
        self.assertEqual(state.used_hiding_position_ids, ("hiding:wall",))

    def test_stale_history_and_reused_position_are_rejected(self):
        for positions, message in ((("hiding:older",), "stale"), (("hiding:wall",), "already used")):
            with self.subTest(positions=positions), self.assertRaisesRegex(ValueError, message):
                registration(state=HidingPositionState("hero", positions))

    def test_only_completed_hidden_attack_is_accepted(self):
        for invalid in (execution_request(), completed_attack().attack, None):
            with self.subTest(type=type(invalid)), self.assertRaises(TypeError):
                HidingPositionRegistrationRequest("invalid", HidingPositionState("hero"), invalid)

    def test_state_validates_ids_and_is_immutable(self):
        for field in ("used_hiding_position_ids", "consumed_attack_execution_ids"):
            for invalid in (("",), ("same", "same"), (1,), "identifier"):
                with self.subTest(field=field, invalid=invalid), self.assertRaises((ValueError, TypeError)):
                    HidingPositionState("hero", **{field: invalid})
        state = HidingPositionState("hero", ["older"])
        self.assertEqual(state.used_hiding_position_ids, ("older",))
        with self.assertRaises(FrozenInstanceError):
            state.actor_id = "ally"

    def test_registration_result_rejects_tampered_state_source_and_trace(self):
        result = register_revealed_hiding_position(registration())
        for changes in (
            {"state": HidingPositionState("hero")},
            {"previous_state": HidingPositionState("ally")},
            {"request_id": "foreign"},
            {"applied_rule_ids": (HIDING_POSITION_REGISTRATION_RULE_ID,)},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(result, **changes)

    def test_prepared_aim_reload_consumption_chains_remain_intact(self):
        source = prepared_request(RangedWeaponId.CROSSBOW, aim_values=(1, 10, 10))
        execution = execute_prepared_hidden_ranged_attack(source, SequenceRandom([10, 10, 10]))
        result = register_revealed_hiding_position(registration(execution))
        self.assertIs(result.source_request.execution, execution)
        self.assertFalse(execution.ranged_attack.weapon_state.loaded)
        self.assertEqual(len(execution.consumed_aim_follow_up_ids), 2)
        self.assertEqual(len(execution.consumed_opportunity_ids), 2)

    def test_declined_hiding_still_receives_current_history(self):
        state = HidingPositionState("hero", ("hiding:wall",))
        request = prepare_move_quietly_with_hiding_positions(
            state, quietly_request(include_movement=False),
        )
        self.assertEqual(request.used_hiding_position_ids, state.used_hiding_position_ids)
