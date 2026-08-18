from __future__ import annotations

import unittest

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import (
    ProfileInjuryState,
    ProfileNpcType,
    ProfileWoundRequest,
)
from towr.domain.npc_effect_models import (
    TrollStupidityConditionRemovedRequest,
    TrollStupidityLeadershipRequest,
    TrollStupidityOutcome,
    TrollStupidityStartRequest,
    TrollStupidityState,
    TrollStupidityWoundRequest,
)
from towr.domain.test_models import InlineProfile, TestRequest
from towr.rules.injury_resolution import resolve_profile_wound
from towr.rules.test_resolution import resolve_test
from towr.rules.troll_stupidity_resolution import (
    resolve_troll_stupidity_after_condition_removal,
    resolve_troll_stupidity_after_leadership,
    resolve_troll_stupidity_after_wound,
    start_troll_stupidity,
    troll_stupidity_test_modifiers,
)


def troll_state(*, distracted: bool = False) -> ProfileInjuryState:
    conditions = (
        ConditionState(frozenset({Condition.DISTRACTED}))
        if distracted
        else ConditionState()
    )
    return ProfileInjuryState(
        wounds=0,
        wound_limit=3,
        conditions=conditions,
    )


def leadership_test(value: int):
    return resolve_test(
        TestRequest(
            id="ally:wrangle-troll:leadership",
            profile=InlineProfile(1, 5),
        ),
        SequenceRandom([value]),
    )


class K1TrollStupidityResolutionTests(unittest.TestCase):
    def test_battle_start_applies_distracted_and_all_test_penalty(self) -> None:
        ability = TrollStupidityState()
        result = start_troll_stupidity(
            TrollStupidityStartRequest(
                id="battle:start:troll-stupidity",
                target_id="troll",
                target_state=troll_state(),
                ability_state=ability,
            )
        )

        self.assertIs(result.outcome, TrollStupidityOutcome.DISTRACTED_ACTIVE)
        self.assertTrue(result.state.conditions.has(Condition.DISTRACTED))
        self.assertIsNotNone(result.condition_application)
        test = resolve_test(
            TestRequest(
                id="troll:any-test",
                profile=InlineProfile(3, 5),
                dice_modifiers=troll_stupidity_test_modifiers(
                    result.ability_state
                ),
            ),
            SequenceRandom([1, 2]),
        )
        self.assertEqual(test.trace.rolled_dice, 2)
        self.assertEqual(test.trace.regular_dice_delta, -1)
        self.assertEqual(test.trace.applied_rule_ids, (ability.rule_id,))

    def test_inflicted_wound_removes_and_suppresses_stupidity(self) -> None:
        ability = TrollStupidityState()
        wound = resolve_profile_wound(
            ProfileWoundRequest(
                id="troll:wound",
                npc_type=ProfileNpcType.BRUTE,
                state=troll_state(distracted=True),
            )
        )

        result = resolve_troll_stupidity_after_wound(
            TrollStupidityWoundRequest(
                id="troll:stupidity:after-wound",
                target_id="troll",
                wound=wound,
                ability_state=ability,
            )
        )

        self.assertIs(result.outcome, TrollStupidityOutcome.REMOVED_BY_WOUND)
        self.assertFalse(result.state.conditions.has(Condition.DISTRACTED))
        self.assertTrue(result.ability_state.suppressed_until_battle_end)
        self.assertEqual(
            troll_stupidity_test_modifiers(result.ability_state),
            (),
        )

    def test_successful_leadership_removes_and_suppresses_stupidity(self) -> None:
        result = resolve_troll_stupidity_after_leadership(
            TrollStupidityLeadershipRequest(
                id="troll:stupidity:leadership",
                target_id="troll",
                target_state=troll_state(distracted=True),
                leadership_test=leadership_test(1),
                ability_state=TrollStupidityState(),
            )
        )

        self.assertIs(
            result.outcome,
            TrollStupidityOutcome.REMOVED_BY_LEADERSHIP,
        )
        self.assertFalse(result.state.conditions.has(Condition.DISTRACTED))
        self.assertTrue(result.ability_state.suppressed_until_battle_end)

    def test_failed_leadership_leaves_stupidity_active(self) -> None:
        state = troll_state(distracted=True)
        ability = TrollStupidityState()
        result = resolve_troll_stupidity_after_leadership(
            TrollStupidityLeadershipRequest(
                id="troll:stupidity:leadership",
                target_id="troll",
                target_state=state,
                leadership_test=leadership_test(10),
                ability_state=ability,
            )
        )

        self.assertIs(
            result.outcome,
            TrollStupidityOutcome.LEADERSHIP_FAILED,
        )
        self.assertIs(result.state, state)
        self.assertIs(result.ability_state, ability)
        self.assertTrue(result.state.conditions.has(Condition.DISTRACTED))
        self.assertEqual(len(troll_stupidity_test_modifiers(ability)), 1)

    def test_suppression_prevents_reapplication_until_new_battle_state(self) -> None:
        suppressed = TrollStupidityState(suppressed_until_battle_end=True)
        current = start_troll_stupidity(
            TrollStupidityStartRequest(
                id="same-battle:start-check",
                target_id="troll",
                target_state=troll_state(),
                ability_state=suppressed,
            )
        )
        next_battle = start_troll_stupidity(
            TrollStupidityStartRequest(
                id="next-battle:start",
                target_id="troll",
                target_state=current.state,
                ability_state=TrollStupidityState(),
            )
        )

        self.assertIs(
            current.outcome,
            TrollStupidityOutcome.ALREADY_SUPPRESSED,
        )
        self.assertFalse(current.state.conditions.has(Condition.DISTRACTED))
        self.assertTrue(next_battle.state.conditions.has(Condition.DISTRACTED))

    def test_external_condition_removal_suppresses_reapplication(self) -> None:
        ability = TrollStupidityState()
        result = resolve_troll_stupidity_after_condition_removal(
            TrollStupidityConditionRemovedRequest(
                id="troll:stupidity:willpower-removal",
                target_id="troll",
                target_state=troll_state(),
                removal_rule_id="RULE-CONDITION:distracted-willpower-removal",
                ability_state=ability,
            )
        )

        self.assertIs(
            result.outcome,
            TrollStupidityOutcome.REMOVED_EXTERNALLY,
        )
        self.assertTrue(result.ability_state.suppressed_until_battle_end)
        self.assertEqual(
            result.applied_rule_ids,
            (
                "RULE-CONDITION:distracted-willpower-removal",
                ability.rule_id,
            ),
        )


if __name__ == "__main__":
    unittest.main()
