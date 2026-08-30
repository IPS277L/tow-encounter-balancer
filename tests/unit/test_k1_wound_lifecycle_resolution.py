from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.fate_models import (
    FATE_NEAR_MISS_RULE_ID,
    FateNearMissBurnRequest,
    FateSessionState,
)
from towr.domain.infection_models import DailyWoundState
from towr.domain.injury_models import (
    CharacterInjuryState,
    CharacterWoundRequest,
    CharacterWoundType,
    WoundNegationOption,
)
from towr.domain.resolution_models import ConsumeWoundNegationRequest
from towr.domain.wound_lifecycle_models import (
    CHARACTER_WOUND_LIFECYCLE_RULE_ID,
    CharacterWoundLifecycleCompletionRequest,
    CharacterWoundLifecycleOutcome,
    CharacterWoundLifecycleRollRequest,
)
from towr.rules.wound_lifecycle_resolution import (
    complete_character_wound_lifecycle,
    roll_character_wound_lifecycle,
)


class SelectNegation:
    def choose_wound_negation(self, **_: object) -> str:
        return "RULE-ABILITY:negate-wound"


def roll_request(
    *,
    state: CharacterInjuryState = CharacterInjuryState(),
    subject_type: CharacterWoundType = CharacterWoundType.PLAYER,
    wound_request: CharacterWoundRequest | None = None,
) -> CharacterWoundLifecycleRollRequest:
    wound = wound_request or CharacterWoundRequest(
        id="wound:hero:1",
        state=state,
        subject_type=subject_type,
    )
    return CharacterWoundLifecycleRollRequest(
        id="wound-lifecycle:hero:1",
        target_id="hero",
        wound=wound,
    )


def near_miss_request(
    wound_id: str,
    *,
    actor_id: str = "hero",
) -> FateNearMissBurnRequest:
    return FateNearMissBurnRequest(
        id=f"burn:{wound_id}",
        state=FateSessionState(
            session_id="session:1",
            actor_id=actor_id,
            rating=1,
            session_spend_limit=1,
        ),
        wound_negation=ConsumeWoundNegationRequest(
            resolution_id=wound_id,
            rule_id=FATE_NEAR_MISS_RULE_ID,
        ),
    )


def completion_request(
    roll,
    *,
    near_miss: FateNearMissBurnRequest | None = None,
    daily_registration_id: str | None = "register:day:1:wound:1",
    consumed_roll_ids: tuple[str, ...] = (),
    current_state: CharacterInjuryState | None = None,
) -> CharacterWoundLifecycleCompletionRequest:
    if near_miss is not None or not roll.wound_result.wound_accepted:
        daily_registration_id = None
    return CharacterWoundLifecycleCompletionRequest(
        id="complete:wound-lifecycle:hero:1",
        roll=roll,
        current_state=current_state or roll.wound_result.state,
        daily_wounds=DailyWoundState("day:1", "hero"),
        daily_registration_id=daily_registration_id,
        near_miss=near_miss,
        consumed_roll_ids=consumed_roll_ids,
    )


class K1CharacterWoundLifecycleTests(unittest.TestCase):
    def test_roll_stops_before_effect_and_opens_player_near_miss_window(
        self,
    ) -> None:
        source = CharacterInjuryState(
            conditions=ConditionState(frozenset({Condition.STAGGERED}))
        )

        result = roll_character_wound_lifecycle(
            roll_request(state=source),
            SequenceRandom([6]),
        )

        self.assertTrue(result.wound_result.wound_accepted)
        self.assertTrue(result.near_miss_eligible)
        self.assertFalse(result.wound_result.state.wounds[-1].effect_resolved)
        self.assertFalse(
            result.wound_result.state.conditions.has(Condition.STAGGERED)
        )
        self.assertEqual(
            result.applied_rule_ids,
            (CHARACTER_WOUND_LIFECYCLE_RULE_ID,),
        )

    def test_acceptance_registers_before_resolving_the_wound_effect(self) -> None:
        roll = roll_character_wound_lifecycle(
            roll_request(),
            SequenceRandom([6]),
        )

        result = complete_character_wound_lifecycle(
            completion_request(roll)
        )

        self.assertIs(result.outcome, CharacterWoundLifecycleOutcome.ACCEPTED)
        self.assertIsNone(result.fate_burn)
        self.assertIsNone(result.near_miss_application)
        self.assertIsNotNone(result.daily_registration)
        self.assertIsNotNone(result.wound_effect)
        assert result.daily_registration is not None
        assert result.wound_effect is not None
        self.assertFalse(result.daily_registration.receipt.wound.effect_resolved)
        self.assertTrue(result.state.wounds[-1].effect_resolved)
        self.assertTrue(result.state.conditions.has(Condition.DRAINED))
        self.assertEqual(result.daily_wounds.wound_count, 1)
        self.assertEqual(
            result.consumed_roll_ids,
            (roll.request_id,),
        )
        self.assertLess(
            result.applied_rule_ids.index(
                result.daily_registration.rule_id
            ),
            result.applied_rule_ids.index(result.wound_effect.request.rule_id),
        )

    def test_near_miss_burn_is_applied_without_effect_or_registration(
        self,
    ) -> None:
        source = CharacterInjuryState(
            conditions=ConditionState(frozenset({Condition.STAGGERED}))
        )
        roll = roll_character_wound_lifecycle(
            roll_request(state=source),
            SequenceRandom([6]),
        )

        result = complete_character_wound_lifecycle(
            completion_request(
                roll,
                near_miss=near_miss_request(roll.source_request.wound.id),
            )
        )

        self.assertIs(result.outcome, CharacterWoundLifecycleOutcome.NEAR_MISS)
        self.assertIsNotNone(result.fate_burn)
        self.assertIsNotNone(result.near_miss_application)
        self.assertIsNone(result.daily_registration)
        self.assertIsNone(result.wound_effect)
        assert result.fate_burn is not None
        self.assertEqual(result.fate_burn.state.rating, 0)
        self.assertEqual(result.state, source)
        self.assertTrue(result.state.conditions.has(Condition.STAGGERED))
        self.assertEqual(result.daily_wounds.wound_count, 0)
        self.assertEqual(len(result.consumed_near_miss_effect_ids), 1)

    def test_near_miss_can_cancel_a_lethal_pending_wound(self) -> None:
        request = roll_request(
            wound_request=CharacterWoundRequest(
                id="wound:hero:lethal",
                state=CharacterInjuryState(),
                base_dice=3,
            )
        )
        roll = roll_character_wound_lifecycle(
            request,
            SequenceRandom([10, 10, 10]),
        )
        self.assertTrue(roll.wound_result.state.dead)

        result = complete_character_wound_lifecycle(
            completion_request(
                roll,
                near_miss=near_miss_request(request.wound.id),
            )
        )

        self.assertFalse(result.state.dead)
        self.assertEqual(result.state.wounds, ())
        self.assertEqual(result.daily_wounds.wound_count, 0)

    def test_completion_preserves_condition_changes_after_pending_roll(
        self,
    ) -> None:
        source = CharacterInjuryState(
            conditions=ConditionState(frozenset({Condition.STAGGERED}))
        )
        roll = roll_character_wound_lifecycle(
            roll_request(state=source),
            SequenceRandom([6]),
        )
        current = replace(
            roll.wound_result.state,
            conditions=roll.wound_result.state.conditions.with_condition(
                Condition.PRONE
            ),
        )

        accepted = complete_character_wound_lifecycle(
            completion_request(roll, current_state=current)
        )
        self.assertTrue(accepted.state.conditions.has(Condition.PRONE))

        near_miss = complete_character_wound_lifecycle(
            replace(
                completion_request(
                    roll,
                    near_miss=near_miss_request(
                        roll.source_request.wound.id
                    ),
                    current_state=current,
                ),
                id="complete:wound-lifecycle:hero:near-miss",
            )
        )
        self.assertTrue(near_miss.state.conditions.has(Condition.STAGGERED))
        self.assertTrue(near_miss.state.conditions.has(Condition.PRONE))

    def test_preexisting_non_fate_negation_closes_without_side_effects(
        self,
    ) -> None:
        wound = CharacterWoundRequest(
            id="wound:hero:ability-negation",
            state=CharacterInjuryState(),
            negation_options=(
                WoundNegationOption("RULE-ABILITY:negate-wound"),
            ),
        )
        roll = roll_character_wound_lifecycle(
            roll_request(wound_request=wound),
            SequenceRandom([10]),
            decisions=SelectNegation(),
        )

        result = complete_character_wound_lifecycle(
            completion_request(roll)
        )

        self.assertFalse(roll.near_miss_eligible)
        self.assertIs(result.outcome, CharacterWoundLifecycleOutcome.NEGATED)
        self.assertEqual(result.state, wound.state)
        self.assertEqual(result.daily_wounds.wound_count, 0)
        self.assertIsNone(result.wound_effect)

    def test_completion_rejects_wrong_near_miss_and_stale_or_reused_roll(
        self,
    ) -> None:
        roll = roll_character_wound_lifecycle(
            roll_request(),
            SequenceRandom([4]),
        )

        with self.assertRaisesRegex(ValueError, "another actor"):
            completion_request(
                roll,
                near_miss=near_miss_request(
                    roll.source_request.wound.id,
                    actor_id="other",
                ),
            )
        with self.assertRaisesRegex(ValueError, "another Wound resolution"):
            completion_request(
                roll,
                near_miss=near_miss_request("wound:other"),
            )
        with self.assertRaisesRegex(ValueError, "current injury state is stale"):
            completion_request(
                roll,
                current_state=CharacterInjuryState(),
            )
        with self.assertRaisesRegex(ValueError, "already consumed"):
            completion_request(
                roll,
                consumed_roll_ids=(roll.request_id,),
            )

        champion_roll = roll_character_wound_lifecycle(
            roll_request(subject_type=CharacterWoundType.CHAMPION),
            SequenceRandom([4]),
        )
        with self.assertRaisesRegex(ValueError, "player character"):
            completion_request(
                champion_roll,
                near_miss=near_miss_request(
                    champion_roll.source_request.wound.id
                ),
            )

    def test_unknown_rules_and_forged_completion_are_rejected(self) -> None:
        unknown_roll = replace(
            roll_request(),
            rule_id="RULE-UNKNOWN",
        )
        with self.assertRaisesRegex(ValueError, "unknown rule"):
            roll_character_wound_lifecycle(
                unknown_roll,
                SequenceRandom([4]),
            )

        roll = roll_character_wound_lifecycle(
            roll_request(),
            SequenceRandom([4]),
        )
        unknown_completion = replace(
            completion_request(roll),
            rule_id="RULE-UNKNOWN",
        )
        with self.assertRaisesRegex(ValueError, "unknown rule"):
            complete_character_wound_lifecycle(unknown_completion)

        result = complete_character_wound_lifecycle(completion_request(roll))
        with self.assertRaisesRegex(ValueError, "accepted branch is stale"):
            replace(result, wound_effect=None)
        with self.assertRaisesRegex(ValueError, "accepted branch is stale"):
            replace(result, state=result.previous_state)


if __name__ == "__main__":
    unittest.main()
