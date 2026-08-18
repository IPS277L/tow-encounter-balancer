from __future__ import annotations

import unittest

from towr.domain.condition_models import (
    Condition,
    ConditionState,
    StaggerChoice,
    StaggerOutcome,
    StaggerRequest,
)
from towr.rules.stagger_resolution import (
    InvalidStaggerDecisionError,
    MissingStaggerDecisionError,
    resolve_stagger,
)


class FixedStaggerDecision:
    def __init__(self, choice: StaggerChoice) -> None:
        self.choice = choice

    def choose_repeated_stagger(self, **_: object) -> StaggerChoice:
        return self.choice


def stagger_request(
    *conditions: Condition,
    can_leave_zone: bool = True,
    has_given_ground: bool = False,
) -> StaggerRequest:
    return StaggerRequest(
        id="impact",
        state=ConditionState(frozenset(conditions)),
        can_leave_zone=can_leave_zone,
        has_given_ground_this_round=has_given_ground,
    )


class K1StaggerResolutionTests(unittest.TestCase):
    def test_first_stagger_adds_condition_without_a_decision(self) -> None:
        result = resolve_stagger(stagger_request())

        self.assertIs(result.outcome, StaggerOutcome.CONDITION_ADDED)
        self.assertTrue(result.state.has(Condition.STAGGERED))
        self.assertEqual(result.allowed_choices, ())

    def test_repeated_stagger_requires_explicit_choice_when_several_are_legal(self) -> None:
        with self.assertRaises(MissingStaggerDecisionError):
            resolve_stagger(stagger_request(Condition.STAGGERED))

    def test_repeated_stagger_can_give_ground_once_when_movement_is_legal(self) -> None:
        result = resolve_stagger(
            stagger_request(Condition.STAGGERED),
            decisions=FixedStaggerDecision(StaggerChoice.GIVE_GROUND),
        )

        self.assertIs(result.outcome, StaggerOutcome.GAVE_GROUND)
        self.assertTrue(result.gave_ground)
        self.assertTrue(result.state.has(Condition.STAGGERED))

    def test_repeated_stagger_can_add_prone(self) -> None:
        result = resolve_stagger(
            stagger_request(Condition.STAGGERED),
            decisions=FixedStaggerDecision(StaggerChoice.FALL_PRONE),
        )

        self.assertIs(result.outcome, StaggerOutcome.FELL_PRONE)
        self.assertTrue(result.state.has(Condition.PRONE))

    def test_prone_staggered_target_must_suffer_wound_without_prompting(self) -> None:
        result = resolve_stagger(
            stagger_request(Condition.STAGGERED, Condition.PRONE)
        )

        self.assertEqual(result.allowed_choices, (StaggerChoice.SUFFER_WOUND,))
        self.assertIs(result.outcome, StaggerOutcome.WOUND_REQUESTED)
        self.assertTrue(result.wound_requested)
        self.assertTrue(result.state.has(Condition.STAGGERED))

    def test_give_ground_is_unavailable_after_use_or_when_zone_cannot_be_left(self) -> None:
        for request in (
            stagger_request(Condition.STAGGERED, has_given_ground=True),
            stagger_request(Condition.STAGGERED, can_leave_zone=False),
        ):
            with self.subTest(request=request):
                with self.assertRaises(InvalidStaggerDecisionError):
                    resolve_stagger(
                        request,
                        decisions=FixedStaggerDecision(StaggerChoice.GIVE_GROUND),
                    )


if __name__ == "__main__":
    unittest.main()
