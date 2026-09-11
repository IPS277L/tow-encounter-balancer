from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.exacting_test_models import ExactingTestProgress
from towr.domain.reload_models import (
    RELOAD_RULE_ID,
    ReloadableWeaponState,
    ReloadActionExecutionRequest,
    reload_approach_id,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.test_models import Skill, TestProfile, TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant,
    CombatActionDeclaration,
    CombatActionKind,
    CombatActionSlotRequest,
    CombatRoundState,
    CombatSide,
    CombatTurnEndRequest,
    CombatTurnParticipant,
    CombatTurnStartRequest,
    ImproviseKind,
)
from towr.rules.reload_resolution import execute_reload_action
from towr.rules.turn_resolution import (
    end_combat_turn,
    reserve_combat_action_slot,
    start_combat_turn,
)


def weapon_state(
    required_successes: int = 3,
    *,
    weapon_instance_id: str = "crossbow:hero:1",
    reload_cycle_id: str = "battle:1:crossbow:hero:1:reload:1",
) -> ReloadableWeaponState:
    weapon_id = {
        2: RangedWeaponId.CROSSBOW,
        3: RangedWeaponId.PISTOL,
        4: RangedWeaponId.HOCHLAND_LONG_RIFLE,
    }.get(required_successes, RangedWeaponId.CROSSBOW)
    return ReloadableWeaponState(
        weapon_instance_id=weapon_instance_id,
        weapon_id=weapon_id,
        reload_cycle_id=reload_cycle_id,
        required_successes=required_successes,
        loaded=False,
        exacting=ExactingTestProgress(
            id=f"{reload_cycle_id}:exacting",
            required_successes=required_successes,
        ),
        reload_cycle_ids=(reload_cycle_id,),
    )


def active_round(
    state: ReloadableWeaponState,
    *,
    round_number: int = 1,
    actor_id: str = "hero",
    declaration: CombatActionDeclaration | None = None,
) -> CombatRoundState:
    round_state = CombatRoundState(
        round_number=round_number,
        participants=(
            CombatTurnParticipant(actor_id, CombatSide.PLAYERS_AND_ALLIES),
            CombatTurnParticipant("enemy", CombatSide.OPPOSITION),
        ),
    )
    round_state = start_combat_turn(
        CombatTurnStartRequest(
            f"turn:{round_number}:{actor_id}",
            round_state,
            actor_id,
        )
    ).state
    action = declaration or CombatActionDeclaration(
        CombatActionKind.IMPROVISE,
        improvise_kind=ImproviseKind.SKILL,
        improvise_approach_id=reload_approach_id(state.weapon_instance_id),
    )
    return reserve_combat_action_slot(
        CombatActionSlotRequest(
            id=f"slot:{round_number}:{actor_id}",
            state=round_state,
            actor_id=actor_id,
            declaration=action,
            grant=ActionSlotGrant.STANDARD,
        )
    ).state


def reload_request(
    state: ReloadableWeaponState,
    *,
    action_number: int = 1,
    round_state: CombatRoundState | None = None,
    actor_id: str = "hero",
    rolls: int = 3,
    **changes,
) -> ReloadActionExecutionRequest:
    values = {
        "id": f"battle:1:reload-action:{action_number}",
        "round_state": (
            round_state
            if round_state is not None
            else active_round(
                state,
                round_number=action_number,
                actor_id=actor_id,
            )
        ),
        "actor_id": actor_id,
        "actor_conditions": ConditionState(),
        "slot_index": 1,
        "weapon_state": state,
        "dexterity_test": TestRequest(
            f"battle:1:reload-dexterity:{action_number}",
            TestProfile(rolls, 5),
        ),
    }
    values.update(changes)
    return ReloadActionExecutionRequest(**values)


class K1ReloadResolutionTests(unittest.TestCase):
    def test_each_action_adds_one_test_and_only_completion_loads_weapon(self) -> None:
        initial = weapon_state()
        first = execute_reload_action(
            reload_request(initial, action_number=1),
            SequenceRandom([1, 2, 10]),
        )

        self.assertEqual(first.exacting.contribution.successes, 2)
        self.assertEqual(first.state.exacting.accumulated_successes, 2)
        self.assertFalse(first.completed)
        self.assertFalse(first.state.loaded)
        self.assertTrue(first.slot.executed)
        self.assertEqual(
            first.slot.execution.result_request_id,
            first.exacting.request_id,
        )
        end_combat_turn(
            CombatTurnEndRequest("end:1", first.round_state, "hero")
        )

        second = execute_reload_action(
            reload_request(
                first.state,
                action_number=2,
                rolls=2,
            ),
            SequenceRandom([1, 2]),
        )

        self.assertEqual(second.state.exacting.accumulated_successes, 4)
        self.assertEqual(len(second.state.exacting.contributions), 2)
        self.assertTrue(second.completed)
        self.assertTrue(second.state.loaded)
        self.assertEqual(
            tuple(
                item.contributor_id
                for item in second.state.exacting.contributions
            ),
            ("hero", "hero"),
        )

    def test_failed_test_spends_action_without_loading_or_losing_progress(self) -> None:
        result = execute_reload_action(
            reload_request(weapon_state(2), rolls=2),
            SequenceRandom([9, 10]),
        )

        self.assertEqual(result.exacting.contribution.successes, 0)
        self.assertEqual(result.state.exacting.accumulated_successes, 0)
        self.assertEqual(len(result.state.exacting.contributions), 1)
        self.assertFalse(result.state.loaded)
        self.assertTrue(result.slot.executed)

    def test_progress_is_bound_to_weapon_instance_and_reload_cycle(self) -> None:
        state = weapon_state()
        with self.assertRaisesRegex(ValueError, "another cycle"):
            replace(
                state,
                reload_cycle_id="battle:1:crossbow:hero:1:reload:2",
            )
        with self.assertRaisesRegex(ValueError, "weapon profile"):
            replace(state, required_successes=4)
        with self.assertRaisesRegex(ValueError, "only on Exacting completion"):
            replace(state, loaded=True)

    def test_weapon_can_start_loaded_without_fabricated_reload_history(self) -> None:
        state = ReloadableWeaponState(
            weapon_instance_id="crossbow:hero:1",
            weapon_id=RangedWeaponId.CROSSBOW,
            reload_cycle_id=None,
            required_successes=2,
            loaded=True,
            exacting=None,
            reload_cycle_ids=(),
        )

        self.assertTrue(state.loaded)
        self.assertIsNone(state.exacting)
        with self.assertRaisesRegex(ValueError, "does not need reloading"):
            reload_request(state)
        with self.assertRaisesRegex(ValueError, "requires a reload cycle"):
            replace(state, loaded=False)

    def test_only_matching_non_attack_skill_improvise_can_reload(self) -> None:
        state = weapon_state()
        wrong_kind = active_round(
            state,
            declaration=CombatActionDeclaration(CombatActionKind.RECOVER),
        )
        with self.assertRaisesRegex(ValueError, "Skill Improvise"):
            reload_request(state, round_state=wrong_kind)

        wrong_weapon = active_round(
            state,
            declaration=CombatActionDeclaration(
                CombatActionKind.IMPROVISE,
                improvise_kind=ImproviseKind.SKILL,
                improvise_approach_id=reload_approach_id("pistol:hero:1"),
            ),
        )
        with self.assertRaisesRegex(ValueError, "weapon must match"):
            reload_request(state, round_state=wrong_weapon)

        attacking = active_round(
            state,
            declaration=CombatActionDeclaration(
                CombatActionKind.IMPROVISE,
                improvise_kind=ImproviseKind.SKILL,
                improvise_approach_id=reload_approach_id(
                    state.weapon_instance_id
                ),
                improvise_produces_attack=True,
            ),
        )
        with self.assertRaisesRegex(ValueError, "not an Attack"):
            reload_request(state, round_state=attacking)

    def test_requires_dexterity_and_an_actor_who_can_act(self) -> None:
        state = weapon_state()
        with self.assertRaisesRegex(ValueError, "Dexterity"):
            reload_request(state, skill=Skill.ATHLETICS)
        with self.assertRaisesRegex(ValueError, "Defenceless"):
            reload_request(
                state,
                actor_conditions=ConditionState({Condition.DEFENCELESS}),
            )

    def test_loaded_weapon_and_free_reload_profile_need_no_action(self) -> None:
        completed = execute_reload_action(
            reload_request(weapon_state(2), rolls=2),
            SequenceRandom([1, 2]),
        ).state
        with self.assertRaisesRegex(ValueError, "does not need reloading"):
            reload_request(completed, action_number=2)
        with self.assertRaisesRegex(ValueError, "positive"):
            weapon_state(0)

    def test_replay_and_duplicate_test_are_rejected_before_rng(self) -> None:
        initial = weapon_state(3)
        request = reload_request(initial, rolls=1)
        first = execute_reload_action(request, SequenceRandom([1]))

        with self.assertRaisesRegex(ValueError, "already been executed"):
            reload_request(
                first.state,
                action_number=2,
                round_state=first.round_state,
            )
        with self.assertRaisesRegex(ValueError, "already consumed"):
            reload_request(
                first.state,
                action_number=2,
                dexterity_test=request.dexterity_test,
            )

    def test_result_is_closed_and_rule_trace_is_complete(self) -> None:
        result = execute_reload_action(
            reload_request(weapon_state(2), rolls=2),
            SequenceRandom([1, 2]),
        )

        self.assertIn(RELOAD_RULE_ID, result.applied_rule_ids)
        self.assertIn(result.exacting.rule_id, result.applied_rule_ids)
        with self.assertRaisesRegex(ValueError, "unrelated weapon state"):
            replace(result, state=result.previous_state)
        with self.assertRaisesRegex(ValueError, "trace is incomplete"):
            replace(result, applied_rule_ids=(RELOAD_RULE_ID,))

    def test_reload_contract_does_not_invent_ammunition_inventory(self) -> None:
        request_fields = ReloadActionExecutionRequest.__dataclass_fields__
        state_fields = ReloadableWeaponState.__dataclass_fields__

        self.assertNotIn("ammunition", request_fields)
        self.assertNotIn("ammunition", state_fields)
        self.assertNotIn("inventory", request_fields)


if __name__ == "__main__":
    unittest.main()
