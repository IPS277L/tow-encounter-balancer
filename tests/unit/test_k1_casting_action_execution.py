from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.action_execution_models import CastingAttemptExecutionRequest
from towr.domain.magic_models import CastingTestRequest, WizardMagicState
from towr.domain.test_models import TestProfile, TestRequest
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
from towr.rules.casting_action_execution import (
    CASTING_IMPROVISE_EXECUTION_RULE_ID,
    execute_casting_attempt,
)
from towr.rules.turn_resolution import (
    end_combat_turn,
    reserve_combat_action_slot,
    start_combat_turn,
)


def initial_round() -> CombatRoundState:
    return CombatRoundState(
        round_number=1,
        participants=(
            CombatTurnParticipant(
                "wizard",
                CombatSide.PLAYERS_AND_ALLIES,
            ),
            CombatTurnParticipant("enemy", CombatSide.OPPOSITION),
        ),
    )


def started_turn() -> CombatRoundState:
    return start_combat_turn(
        CombatTurnStartRequest("turn:start", initial_round(), "wizard")
    ).state


def reserve_action(
    state: CombatRoundState,
    declaration: CombatActionDeclaration,
    *,
    grant: ActionSlotGrant = ActionSlotGrant.STANDARD,
) -> CombatRoundState:
    return reserve_combat_action_slot(
        CombatActionSlotRequest(
            id=f"slot:{len(state.active_turn.action_slots) + 1}",
            state=state,
            actor_id="wizard",
            declaration=declaration,
            grant=grant,
            grant_rule_id=(
                "RULE-ABILITY:test-extra-action"
                if grant is ActionSlotGrant.ABILITY
                else None
            ),
        )
    ).state


def spell_improvise(
    lore_id: str = "lore:beasts",
) -> CombatActionDeclaration:
    return CombatActionDeclaration(
        CombatActionKind.IMPROVISE,
        improvise_kind=ImproviseKind.SPELL,
        improvise_approach_id=lore_id,
    )


def casting_request(
    *,
    caster_id: str = "wizard",
    lore_id: str = "lore:beasts",
    state: WizardMagicState = WizardMagicState(),
) -> CastingTestRequest:
    return CastingTestRequest(
        id="casting:test",
        caster_id=caster_id,
        lore_id=lore_id,
        test=TestRequest(
            id="casting:willpower",
            profile=TestProfile(3, 5),
        ),
        state=state,
    )


def execution_request(
    state: CombatRoundState,
    *,
    actor_id: str = "wizard",
    slot_index: int = 1,
    casting: CastingTestRequest | None = None,
    request_id: str = "execute:casting",
) -> CastingAttemptExecutionRequest:
    return CastingAttemptExecutionRequest(
        id=request_id,
        state=state,
        actor_id=actor_id,
        slot_index=slot_index,
        casting_request=casting or casting_request(caster_id=actor_id),
    )


class K1CastingActionExecutionTests(unittest.TestCase):
    def test_spell_improvise_executes_one_casting_test_and_marks_slot(self) -> None:
        state = reserve_action(started_turn(), spell_improvise())

        result = execute_casting_attempt(
            execution_request(state),
            SequenceRandom([1, 2, 10]),
        )

        self.assertIs(result.previous_state, state)
        self.assertEqual(result.actor_id, "wizard")
        self.assertEqual(result.slot_index, 1)
        self.assertFalse(state.active_turn.action_slots[0].executed)
        self.assertTrue(result.slot.executed)
        self.assertEqual(result.state.active_turn.action_slots[0], result.slot)
        receipt = result.slot.execution
        assert receipt is not None
        self.assertEqual(receipt.id, "execute:casting")
        self.assertEqual(
            receipt.executor_rule_id,
            CASTING_IMPROVISE_EXECUTION_RULE_ID,
        )
        self.assertEqual(receipt.source_request_id, "casting:test")
        self.assertEqual(receipt.result_request_id, "casting:test")
        self.assertEqual(result.casting.latest_roll_successes, 2)
        self.assertEqual(result.casting.state.casting_successes, 2)
        self.assertEqual(result.casting.state.casting_lore_id, "lore:beasts")
        self.assertEqual(result.casting.follow_ups, ())
        self.assertEqual(
            result.applied_rule_ids,
            (CASTING_IMPROVISE_EXECUTION_RULE_ID,),
        )

    def test_rule_of_nine_follow_up_remains_nested_for_later_phase(self) -> None:
        state = reserve_action(started_turn(), spell_improvise())

        result = execute_casting_attempt(
            execution_request(state),
            SequenceRandom([9, 10, 10]),
        )

        self.assertEqual(result.casting.miscast_dice_added, 1)
        self.assertEqual(len(result.casting.follow_ups), 1)
        self.assertEqual(result.casting.follow_ups[0].target_id, "wizard")
        self.assertEqual(result.casting.state.miscast_dice, 0)

    def test_non_spell_improvise_and_other_actions_are_rejected(self) -> None:
        declarations = (
            CombatActionDeclaration(CombatActionKind.AIM),
            CombatActionDeclaration(
                CombatActionKind.IMPROVISE,
                improvise_kind=ImproviseKind.SKILL,
                improvise_approach_id="brawn:knock-prone",
            ),
            CombatActionDeclaration(
                CombatActionKind.IMPROVISE,
                improvise_kind=ImproviseKind.ABILITY,
                improvise_approach_id="ability:test",
            ),
        )
        for declaration in declarations:
            with self.subTest(declaration=declaration):
                state = reserve_action(started_turn(), declaration)
                with self.assertRaises(ValueError):
                    execute_casting_attempt(
                        execution_request(state),
                        SequenceRandom([]),
                    )

    def test_lore_and_caster_must_match_slot_and_active_actor(self) -> None:
        state = reserve_action(started_turn(), spell_improvise())

        with self.assertRaises(ValueError):
            execute_casting_attempt(
                execution_request(
                    state,
                    casting=casting_request(lore_id="lore:fire"),
                ),
                SequenceRandom([]),
            )
        with self.assertRaises(ValueError):
            execution_request(
                state,
                actor_id="wizard",
                casting=casting_request(caster_id="enemy"),
            )
        with self.assertRaises(ValueError):
            execute_casting_attempt(
                execution_request(
                    state,
                    actor_id="enemy",
                    casting=casting_request(caster_id="enemy"),
                ),
                SequenceRandom([]),
            )

    def test_unreserved_prior_and_executed_slots_are_rejected_before_rng(self) -> None:
        state = reserve_action(
            started_turn(),
            CombatActionDeclaration(CombatActionKind.AIM),
        )
        state = reserve_action(
            state,
            spell_improvise(),
            grant=ActionSlotGrant.ABILITY,
        )
        with self.assertRaises(ValueError):
            execute_casting_attempt(
                execution_request(state, slot_index=2),
                SequenceRandom([]),
            )

        single = reserve_action(started_turn(), spell_improvise())
        executed = execute_casting_attempt(
            execution_request(single),
            SequenceRandom([1, 10, 10]),
        )
        with self.assertRaises(ValueError):
            execute_casting_attempt(
                execution_request(
                    executed.state,
                    request_id="execute:again",
                ),
                SequenceRandom([]),
            )

    def test_spell_improvise_must_execute_before_turn_can_end(self) -> None:
        state = reserve_action(started_turn(), spell_improvise())
        with self.assertRaises(ValueError):
            end_combat_turn(
                CombatTurnEndRequest("turn:end", state, "wizard")
            )

        executed = execute_casting_attempt(
            execution_request(state),
            SequenceRandom([1, 10, 10]),
        )
        ended = end_combat_turn(
            CombatTurnEndRequest("turn:end", executed.state, "wizard")
        )

        self.assertTrue(ended.completed_turn.action_slots[0].executed)
        self.assertEqual(executed.casting.state.casting_successes, 1)

    def test_failed_casting_test_leaves_slot_unexecuted(self) -> None:
        state = reserve_action(started_turn(), spell_improvise())

        with self.assertRaises(RuntimeError):
            execute_casting_attempt(
                execution_request(state),
                SequenceRandom([]),
            )

        self.assertFalse(state.active_turn.action_slots[0].executed)

    def test_result_rejects_forged_actor_or_round_mutation(self) -> None:
        state = reserve_action(started_turn(), spell_improvise())
        result = execute_casting_attempt(
            execution_request(state),
            SequenceRandom([1, 10, 10]),
        )

        with self.assertRaises(ValueError):
            replace(result, actor_id="enemy")
        with self.assertRaises(ValueError):
            replace(result, state=result.previous_state)


class K1ImproviseDeclarationTests(unittest.TestCase):
    def test_improvise_requires_typed_kind_and_non_improvise_rejects_it(
        self,
    ) -> None:
        with self.assertRaises(TypeError):
            CombatActionDeclaration(
                CombatActionKind.IMPROVISE,
                improvise_approach_id="lore:beasts",
            )
        with self.assertRaises(ValueError):
            CombatActionDeclaration(
                CombatActionKind.ATTACK,
                improvise_kind=ImproviseKind.SPELL,
            )


if __name__ == "__main__":
    unittest.main()
