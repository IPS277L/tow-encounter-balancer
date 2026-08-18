from __future__ import annotations

import unittest

from towr.domain.condition_models import Condition
from towr.domain.injury_models import CharacterInjuryState, DecisionOwner
from towr.domain.npc_effect_models import (
    DropHeldHandItemRequest,
    FoulStenchChoice,
    FoulStenchOutcome,
    FoulStenchRequest,
)
from towr.rules.foul_stench_resolution import (
    InvalidFoulStenchDecisionError,
    MissingFoulStenchDecisionError,
    resolve_foul_stench,
)


class FixedFoulStenchDecision:
    def __init__(self, choice: object) -> None:
        self.choice = choice
        self.owner: DecisionOwner | None = None
        self.choices: tuple[FoulStenchChoice, ...] = ()

    def choose_foul_stench_response(
        self,
        *,
        owner: DecisionOwner,
        choices: tuple[FoulStenchChoice, ...],
        **_: object,
    ):
        self.owner = owner
        self.choices = choices
        return self.choice


def request(
    *,
    has_free_hand: bool,
    has_droppable_hand_item: bool,
    state: CharacterInjuryState | None = None,
) -> FoulStenchRequest:
    return FoulStenchRequest(
        id="wyvern-enters-zone",
        target_id="target",
        target_state=state or CharacterInjuryState(),
        has_free_hand=has_free_hand,
        has_droppable_hand_item=has_droppable_hand_item,
    )


class K1FoulStenchResolutionTests(unittest.TestCase):
    def test_free_hand_covers_nose_without_decision_or_inventory_change(self) -> None:
        source = request(
            has_free_hand=True,
            has_droppable_hand_item=True,
        )

        result = resolve_foul_stench(source)

        self.assertIs(
            result.outcome,
            FoulStenchOutcome.COVERED_NOSE_WITH_FREE_HAND,
        )
        self.assertIs(result.state, source.target_state)
        self.assertEqual(result.allowed_choices, ())
        self.assertIsNone(result.selected_choice)
        self.assertEqual(result.follow_ups, ())

    def test_occupied_hands_require_explicit_target_decision(self) -> None:
        with self.assertRaises(MissingFoulStenchDecisionError):
            resolve_foul_stench(
                request(
                    has_free_hand=False,
                    has_droppable_hand_item=True,
                )
            )

    def test_target_can_request_drop_of_one_held_hand_item(self) -> None:
        source = request(
            has_free_hand=False,
            has_droppable_hand_item=True,
        )
        decision = FixedFoulStenchDecision(
            FoulStenchChoice.DROP_HELD_HAND_ITEM
        )

        result = resolve_foul_stench(source, decisions=decision)

        self.assertIs(
            result.outcome,
            FoulStenchOutcome.DROP_HELD_HAND_ITEM_REQUESTED,
        )
        self.assertIs(result.decision_owner, DecisionOwner.TARGET)
        self.assertIs(decision.owner, DecisionOwner.TARGET)
        self.assertEqual(
            decision.choices,
            (
                FoulStenchChoice.DROP_HELD_HAND_ITEM,
                FoulStenchChoice.SUFFER_DISTRACTED,
            ),
        )
        self.assertEqual(len(result.follow_ups), 1)
        self.assertIsInstance(result.follow_ups[0], DropHeldHandItemRequest)
        self.assertEqual(result.follow_ups[0].target_id, source.target_id)
        self.assertIs(result.state, source.target_state)

    def test_target_can_accept_distracted_instead_of_dropping_item(self) -> None:
        decision = FixedFoulStenchDecision(
            FoulStenchChoice.SUFFER_DISTRACTED
        )

        result = resolve_foul_stench(
            request(
                has_free_hand=False,
                has_droppable_hand_item=True,
            ),
            decisions=decision,
        )

        self.assertIs(result.outcome, FoulStenchOutcome.SUFFERED_DISTRACTED)
        self.assertTrue(result.state.conditions.has(Condition.DISTRACTED))
        self.assertIsNotNone(result.condition_application)
        self.assertEqual(result.follow_ups, ())

    def test_distracted_is_automatic_when_a_hand_cannot_be_freed(self) -> None:
        result = resolve_foul_stench(
            request(
                has_free_hand=False,
                has_droppable_hand_item=False,
            )
        )

        self.assertIs(result.outcome, FoulStenchOutcome.SUFFERED_DISTRACTED)
        self.assertIsNone(result.decision_owner)
        self.assertEqual(
            result.allowed_choices,
            (FoulStenchChoice.SUFFER_DISTRACTED,),
        )
        self.assertIs(
            result.selected_choice,
            FoulStenchChoice.SUFFER_DISTRACTED,
        )
        self.assertTrue(result.state.conditions.has(Condition.DISTRACTED))

    def test_invalid_target_decision_is_rejected(self) -> None:
        with self.assertRaises(InvalidFoulStenchDecisionError):
            resolve_foul_stench(
                request(
                    has_free_hand=False,
                    has_droppable_hand_item=True,
                ),
                decisions=FixedFoulStenchDecision("drop"),
            )


if __name__ == "__main__":
    unittest.main()
