from __future__ import annotations

import unittest

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import DecisionOwner, ProfileInjuryState
from towr.domain.npc_effect_models import (
    TrollRegenerationChoice,
    TrollRegenerationOutcome,
    TrollRegenerationRequest,
)
from towr.rules.troll_regeneration_resolution import (
    InvalidTrollRegenerationDecisionError,
    MissingTrollRegenerationDecisionError,
    resolve_troll_regeneration,
)


class FixedRegenerationDecision:
    def __init__(self, choice: object) -> None:
        self.choice = choice
        self.owner: DecisionOwner | None = None
        self.choices: tuple[TrollRegenerationChoice, ...] = ()
        self.calls = 0

    def choose_troll_regeneration(
        self,
        *,
        owner: DecisionOwner,
        choices: tuple[TrollRegenerationChoice, ...],
        **_: object,
    ):
        self.calls += 1
        self.owner = owner
        self.choices = choices
        return self.choice


def request(
    *,
    wounds: int = 2,
    staggered: bool = False,
    has_non_fire_wound: bool = True,
) -> TrollRegenerationRequest:
    conditions = (
        ConditionState(frozenset({Condition.STAGGERED}))
        if staggered
        else ConditionState()
    )
    return TrollRegenerationRequest(
        id="troll:end-turn:regeneration",
        target_id="troll",
        target_state=ProfileInjuryState(
            wounds=wounds,
            wound_limit=3,
            conditions=conditions,
        ),
        has_non_fire_wound=has_non_fire_wound,
    )


class K1TrollRegenerationResolutionTests(unittest.TestCase):
    def test_unavailable_branches_do_not_request_a_decision(self) -> None:
        cases = (
            (
                request(staggered=True),
                TrollRegenerationOutcome.UNAVAILABLE_STAGGERED,
            ),
            (
                request(wounds=0, has_non_fire_wound=False),
                TrollRegenerationOutcome.UNAVAILABLE_UNWOUNDED,
            ),
            (
                request(has_non_fire_wound=False),
                TrollRegenerationOutcome.UNAVAILABLE_FIRE_WOUNDS,
            ),
        )
        decision = FixedRegenerationDecision(
            TrollRegenerationChoice.REGENERATE
        )

        for source, expected in cases:
            with self.subTest(expected=expected):
                result = resolve_troll_regeneration(
                    source,
                    decisions=decision,
                )
                self.assertIs(result.outcome, expected)
                self.assertIs(result.state, source.target_state)
                self.assertEqual(result.allowed_choices, ())
                self.assertEqual(result.wounds_healed, 0)
        self.assertEqual(decision.calls, 0)

    def test_available_regeneration_requires_explicit_actor_decision(self) -> None:
        with self.assertRaises(MissingTrollRegenerationDecisionError):
            resolve_troll_regeneration(request())

    def test_actor_can_decline_regeneration(self) -> None:
        source = request()
        decision = FixedRegenerationDecision(TrollRegenerationChoice.SKIP)

        result = resolve_troll_regeneration(source, decisions=decision)

        self.assertIs(result.outcome, TrollRegenerationOutcome.DECLINED)
        self.assertIs(result.state, source.target_state)
        self.assertIs(result.decision_owner, DecisionOwner.ACTOR)
        self.assertIs(
            result.selected_choice,
            TrollRegenerationChoice.SKIP,
        )
        self.assertIs(decision.owner, DecisionOwner.ACTOR)

    def test_actor_can_gain_staggered_and_heal_one_wound(self) -> None:
        source = request(wounds=2)
        decision = FixedRegenerationDecision(
            TrollRegenerationChoice.REGENERATE
        )

        result = resolve_troll_regeneration(source, decisions=decision)

        self.assertIs(result.outcome, TrollRegenerationOutcome.HEALED)
        self.assertEqual(result.state.wounds, 1)
        self.assertTrue(result.state.conditions.has(Condition.STAGGERED))
        self.assertEqual(result.wounds_healed, 1)
        self.assertIsNotNone(result.condition_application)
        self.assertIsNotNone(result.state_change)
        assert result.state_change is not None
        self.assertEqual(result.state_change.previous_wounds, 2)
        self.assertEqual(result.state_change.current_wounds, 1)
        self.assertEqual(result.applied_rule_ids, (source.rule_id,))

    def test_invalid_decision_is_rejected(self) -> None:
        with self.assertRaises(InvalidTrollRegenerationDecisionError):
            resolve_troll_regeneration(
                request(),
                decisions=FixedRegenerationDecision("regenerate"),
            )

    def test_unwounded_request_rejects_non_fire_wound_context(self) -> None:
        with self.assertRaises(ValueError):
            request(wounds=0, has_non_fire_wound=True)


if __name__ == "__main__":
    unittest.main()
