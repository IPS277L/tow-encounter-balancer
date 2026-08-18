from __future__ import annotations

import unittest

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import (
    DecisionOwner,
    ProfileInjuryState,
    ProfileNpcType,
)
from towr.domain.resolution_models import (
    MonstrousRegenerationChoice,
    MonstrousRegenerationEndTurnRequest,
    MonstrousRegenerationOutcome,
    SuppressRegenerationNextTurnRequest,
)
from towr.rules.monstrous_regeneration_resolution import (
    InvalidMonstrousRegenerationDecisionError,
    MissingMonstrousRegenerationDecisionError,
    resolve_monstrous_regeneration_end_turn,
)


RULE_ID = "RULE-NPC-014:monstrous-regeneration"


class FixedMonstrousRegenerationDecision:
    def __init__(self, choice: object) -> None:
        self.choice = choice
        self.owner: DecisionOwner | None = None
        self.choices: tuple[MonstrousRegenerationChoice, ...] = ()
        self.calls = 0

    def choose_monstrous_regeneration(
        self,
        *,
        owner: DecisionOwner,
        choices: tuple[MonstrousRegenerationChoice, ...],
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
    pending_suppression: SuppressRegenerationNextTurnRequest | None = None,
) -> MonstrousRegenerationEndTurnRequest:
    conditions = (
        ConditionState(frozenset({Condition.STAGGERED}))
        if staggered
        else ConditionState()
    )
    return MonstrousRegenerationEndTurnRequest(
        id="monstrosity:end-turn:regeneration",
        target_id="monstrosity",
        target_state=ProfileInjuryState(
            wounds=wounds,
            wound_limit=6,
            conditions=conditions,
        ),
        has_non_fire_wound=has_non_fire_wound,
        pending_suppression=pending_suppression,
        rule_id=RULE_ID,
    )


class K1MonstrousRegenerationResolutionTests(unittest.TestCase):
    def test_pending_reaction_suppression_is_consumed_before_decision(self) -> None:
        suppression = SuppressRegenerationNextTurnRequest(
            resolution_id="reaction:attack",
            rule_id=RULE_ID,
        )
        source = request(pending_suppression=suppression)
        decision = FixedMonstrousRegenerationDecision(
            MonstrousRegenerationChoice.REGENERATE
        )

        result = resolve_monstrous_regeneration_end_turn(
            source,
            decisions=decision,
        )

        self.assertIs(
            result.outcome,
            MonstrousRegenerationOutcome.SUPPRESSED_AND_CONSUMED,
        )
        self.assertIs(result.state, source.target_state)
        self.assertIs(result.consumed_suppression, suppression)
        self.assertEqual(result.allowed_choices, ())
        self.assertEqual(result.wounds_healed, 0)
        self.assertEqual(decision.calls, 0)

    def test_suppression_is_consumed_even_without_a_healable_wound(self) -> None:
        suppression = SuppressRegenerationNextTurnRequest(
            resolution_id="reaction:attack",
            rule_id=RULE_ID,
        )

        result = resolve_monstrous_regeneration_end_turn(
            request(
                wounds=0,
                has_non_fire_wound=False,
                pending_suppression=suppression,
            )
        )

        self.assertIs(
            result.outcome,
            MonstrousRegenerationOutcome.SUPPRESSED_AND_CONSUMED,
        )
        self.assertIs(result.consumed_suppression, suppression)

    def test_unavailable_wound_branches_do_not_request_a_decision(self) -> None:
        cases = (
            (
                request(wounds=0, has_non_fire_wound=False),
                MonstrousRegenerationOutcome.UNAVAILABLE_UNWOUNDED,
            ),
            (
                request(has_non_fire_wound=False),
                MonstrousRegenerationOutcome.UNAVAILABLE_FIRE_WOUNDS,
            ),
        )
        decision = FixedMonstrousRegenerationDecision(
            MonstrousRegenerationChoice.REGENERATE
        )

        for source, expected in cases:
            with self.subTest(expected=expected):
                result = resolve_monstrous_regeneration_end_turn(
                    source,
                    decisions=decision,
                )
                self.assertIs(result.outcome, expected)
                self.assertIs(result.state, source.target_state)
                self.assertEqual(result.allowed_choices, ())
                self.assertEqual(result.wounds_healed, 0)
        self.assertEqual(decision.calls, 0)

    def test_available_regeneration_requires_explicit_actor_decision(self) -> None:
        with self.assertRaises(MissingMonstrousRegenerationDecisionError):
            resolve_monstrous_regeneration_end_turn(request())

    def test_actor_can_decline_regeneration(self) -> None:
        source = request()
        decision = FixedMonstrousRegenerationDecision(
            MonstrousRegenerationChoice.SKIP
        )

        result = resolve_monstrous_regeneration_end_turn(
            source,
            decisions=decision,
        )

        self.assertIs(result.outcome, MonstrousRegenerationOutcome.DECLINED)
        self.assertIs(result.state, source.target_state)
        self.assertIs(result.decision_owner, DecisionOwner.ACTOR)
        self.assertIs(result.selected_choice, MonstrousRegenerationChoice.SKIP)
        self.assertIs(decision.owner, DecisionOwner.ACTOR)

    def test_regeneration_heals_and_adds_staggered_when_absent(self) -> None:
        source = request(wounds=2)
        decision = FixedMonstrousRegenerationDecision(
            MonstrousRegenerationChoice.REGENERATE
        )

        result = resolve_monstrous_regeneration_end_turn(
            source,
            decisions=decision,
        )

        self.assertIs(result.outcome, MonstrousRegenerationOutcome.HEALED)
        self.assertEqual(result.state.wounds, 1)
        self.assertTrue(result.state.conditions.has(Condition.STAGGERED))
        self.assertEqual(result.wounds_healed, 1)
        self.assertIsNotNone(result.condition_application)
        self.assertIsNotNone(result.state_change)
        assert result.state_change is not None
        self.assertIs(result.state_change.npc_type, ProfileNpcType.MONSTROSITY)
        self.assertEqual(result.state_change.previous_wounds, 2)
        self.assertEqual(result.state_change.current_wounds, 1)
        self.assertEqual(result.applied_rule_ids, (RULE_ID,))

    def test_already_staggered_monstrosity_still_heals_without_reapplying(self) -> None:
        source = request(wounds=2, staggered=True)

        result = resolve_monstrous_regeneration_end_turn(
            source,
            decisions=FixedMonstrousRegenerationDecision(
                MonstrousRegenerationChoice.REGENERATE
            ),
        )

        self.assertIs(result.outcome, MonstrousRegenerationOutcome.HEALED)
        self.assertEqual(result.state.wounds, 1)
        self.assertTrue(result.state.conditions.has(Condition.STAGGERED))
        self.assertIsNone(result.condition_application)

    def test_invalid_decision_and_mismatched_suppression_are_rejected(self) -> None:
        with self.assertRaises(InvalidMonstrousRegenerationDecisionError):
            resolve_monstrous_regeneration_end_turn(
                request(),
                decisions=FixedMonstrousRegenerationDecision("regenerate"),
            )

        with self.assertRaises(ValueError):
            request(
                pending_suppression=SuppressRegenerationNextTurnRequest(
                    resolution_id="other:reaction",
                    rule_id="RULE-NPC-999:other-regeneration",
                )
            )

    def test_unwounded_request_rejects_non_fire_wound_context(self) -> None:
        with self.assertRaises(ValueError):
            request(wounds=0, has_non_fire_wound=True)


if __name__ == "__main__":
    unittest.main()
