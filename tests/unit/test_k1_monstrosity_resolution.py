from __future__ import annotations

import unittest

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import (
    DecisionOwner,
    MonstrosityImpactChoice,
    MonstrosityImpactRequest,
    ProfileInjuryState,
)
from towr.rules.monstrosity_resolution import (
    MissingMonstrosityDecisionError,
    resolve_monstrosity_impact,
)


class FixedMonstrosityDecision:
    def __init__(self, choice: MonstrosityImpactChoice) -> None:
        self.choice = choice

    def choose_monstrosity_impact(self, **_: object) -> MonstrosityImpactChoice:
        return self.choice


def impact_request(
    *,
    damage: int,
    resilience: int = 5,
    staggered: bool = False,
) -> MonstrosityImpactRequest:
    conditions = (
        ConditionState(frozenset({Condition.STAGGERED}))
        if staggered
        else ConditionState()
    )
    return MonstrosityImpactRequest(
        id="monster-impact",
        state=ProfileInjuryState(
            wounds=0,
            wound_limit=3,
            conditions=conditions,
        ),
        damage=damage,
        resilience=resilience,
    )


class K1MonstrosityResolutionTests(unittest.TestCase):
    def test_non_wounding_damage_first_applies_staggered_without_decision(self) -> None:
        result = resolve_monstrosity_impact(impact_request(damage=5))

        self.assertTrue(result.staggered_applied)
        self.assertTrue(result.state.conditions.has(Condition.STAGGERED))
        self.assertIsNone(result.decision_owner)

    def test_repeated_low_damage_gives_choice_to_monstrosity(self) -> None:
        result = resolve_monstrosity_impact(
            impact_request(damage=5, staggered=True),
            decisions=FixedMonstrosityDecision(
                MonstrosityImpactChoice.TRIGGER_REACTION
            ),
        )

        self.assertIs(result.decision_owner, DecisionOwner.MONSTROSITY)
        self.assertTrue(result.reaction_requested)
        self.assertFalse(result.wound_requested)
        self.assertTrue(result.state.conditions.has(Condition.STAGGERED))

    def test_wounding_damage_gives_choice_to_attacker(self) -> None:
        result = resolve_monstrosity_impact(
            impact_request(damage=6),
            decisions=FixedMonstrosityDecision(
                MonstrosityImpactChoice.SUFFER_WOUND
            ),
        )

        self.assertIs(result.decision_owner, DecisionOwner.ATTACKER)
        self.assertTrue(result.wound_requested)
        self.assertFalse(result.reaction_requested)

    def test_wound_reaction_branch_never_uses_hidden_default(self) -> None:
        with self.assertRaises(MissingMonstrosityDecisionError):
            resolve_monstrosity_impact(impact_request(damage=6))


if __name__ == "__main__":
    unittest.main()
