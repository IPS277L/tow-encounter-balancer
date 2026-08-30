from __future__ import annotations

import unittest

from tests.helpers import SequenceRandom
from towr.domain.condition_models import (
    Condition,
    ConditionState,
    RepeatedConditionReplacement,
)
from towr.domain.injury_models import CharacterInjuryState, ProfileInjuryState
from towr.domain.infection_models import DailyWoundState
from towr.domain.resolution_models import (
    IdentifiedHazardTarget,
    TargetInjuryPolicy,
    ZoneHazardRequest,
    ZoneHazardResolutionRequest,
)
from towr.domain.test_models import InlineProfile, Skill, TestRequest
from towr.domain.wound_lifecycle_models import (
    CharacterWoundLifecycleCompletionRequest,
)
from towr.rules.hazard_resolution import (
    apply_hazard_character_wound_completion,
)
from towr.rules.soporific_breath import (
    SOPORIFIC_BREATH_RULE_ID,
    soporific_breath_hazard,
)
from towr.rules.zone_hazard_resolution import resolve_zone_hazard
from towr.rules.wound_lifecycle_resolution import (
    complete_character_wound_lifecycle,
)


def target(
    target_id: str,
    *,
    state: ProfileInjuryState | None = None,
    dice: int = 1,
) -> IdentifiedHazardTarget:
    return IdentifiedHazardTarget(
        target_id=target_id,
        avoidance_test=TestRequest(
            id=f"soporific:{target_id}:test",
            profile=InlineProfile(dice, 5),
        ),
        target_policy=TargetInjuryPolicy.BRUTE,
        target_state=state or ProfileInjuryState(wounds=0, wound_limit=6),
    )


class K1SoporificBreathResolutionTests(unittest.TestCase):
    def test_factory_normalizes_the_book_hazard(self) -> None:
        source = soporific_breath_hazard("forest-dragon:breath")

        self.assertEqual(source.rating, 2)
        self.assertIs(source.avoidance_skill, Skill.ENDURANCE)
        self.assertTrue(source.inflicts_wound)
        self.assertEqual(source.failure_conditions, (Condition.DRAINED,))
        self.assertEqual(
            source.repeated_condition_replacements,
            (
                RepeatedConditionReplacement(
                    Condition.DRAINED,
                    Condition.DEFENCELESS,
                    SOPORIFIC_BREATH_RULE_ID,
                ),
            ),
        )

    def test_zone_resolves_fresh_and_repeated_drained_independently(self) -> None:
        result = resolve_zone_hazard(
            ZoneHazardResolutionRequest(
                id="soporific-zone",
                source=soporific_breath_hazard("forest-dragon:breath"),
                targets=(
                    target("fresh"),
                    target(
                        "drained",
                        state=ProfileInjuryState(
                            wounds=0,
                            wound_limit=6,
                            conditions=ConditionState(
                                frozenset({Condition.DRAINED})
                            ),
                        ),
                    ),
                ),
            ),
            SequenceRandom([10, 10]),
        )

        fresh, drained = result.targets
        assert fresh.hazard is not None
        assert drained.hazard is not None
        self.assertEqual(fresh.hazard.state.wounds, 2)
        self.assertEqual(
            fresh.hazard.failure_conditions,
            (Condition.DRAINED,),
        )
        self.assertTrue(fresh.hazard.state.conditions.has(Condition.DRAINED))
        self.assertFalse(
            fresh.hazard.state.conditions.has(Condition.DEFENCELESS)
        )
        self.assertEqual(drained.hazard.state.wounds, 2)
        self.assertEqual(
            drained.hazard.failure_conditions,
            (Condition.DEFENCELESS,),
        )
        self.assertTrue(drained.hazard.state.conditions.has(Condition.DRAINED))
        self.assertTrue(
            drained.hazard.state.conditions.has(Condition.DEFENCELESS)
        )
        self.assertIs(
            drained.hazard.condition_applications[0].condition,
            Condition.DEFENCELESS,
        )

    def test_resisted_hazard_neither_wounds_nor_escalates(self) -> None:
        initial = ProfileInjuryState(
            wounds=1,
            wound_limit=6,
            conditions=ConditionState(frozenset({Condition.DRAINED})),
        )
        result = resolve_zone_hazard(
            ZoneHazardResolutionRequest(
                id="soporific-zone",
                source=soporific_breath_hazard("forest-dragon:breath"),
                targets=(target("resisted", state=initial, dice=2),),
            ),
            SequenceRandom([1, 2]),
        )

        hazard = result.targets[0].hazard
        assert hazard is not None
        self.assertTrue(hazard.avoided)
        self.assertIs(hazard.state, initial)
        self.assertEqual(hazard.failure_conditions, ())
        self.assertEqual(hazard.condition_applications, ())

    def test_wound_condition_is_applied_before_breath_escalation(self) -> None:
        player = IdentifiedHazardTarget(
            target_id="player",
            avoidance_test=TestRequest(
                id="soporific:player:test",
                profile=InlineProfile(1, 5),
            ),
            target_policy=TargetInjuryPolicy.PLAYER,
            target_state=CharacterInjuryState(),
        )
        result = resolve_zone_hazard(
            ZoneHazardResolutionRequest(
                id="soporific-zone",
                source=soporific_breath_hazard("forest-dragon:breath"),
                targets=(player,),
            ),
            SequenceRandom([10, 3, 3]),
        )

        hazard = result.targets[0].hazard
        assert hazard is not None
        assert hazard.character_wound is not None
        assert hazard.pending_character_wound is not None
        completion = complete_character_wound_lifecycle(
            CharacterWoundLifecycleCompletionRequest(
                id="soporific:player:complete-wound",
                roll=hazard.pending_character_wound,
                current_state=hazard.state,
                daily_wounds=DailyWoundState("day:1", "player"),
                daily_registration_id="soporific:player:daily-wound",
            )
        )
        hazard = apply_hazard_character_wound_completion(
            hazard,
            completion,
        )
        self.assertTrue(hazard.state.conditions.has(Condition.DRAINED))
        self.assertTrue(hazard.state.conditions.has(Condition.DEFENCELESS))
        self.assertEqual(
            hazard.failure_conditions,
            (Condition.DEFENCELESS,),
        )

    def test_replacement_must_target_a_failure_condition(self) -> None:
        with self.assertRaises(ValueError):
            ZoneHazardRequest(
                resolution_id="invalid",
                rating=2,
                avoidance_skill=Skill.ENDURANCE,
                rule_id=SOPORIFIC_BREATH_RULE_ID,
                inflicts_wound=True,
                failure_conditions=(Condition.PRONE,),
                repeated_condition_replacements=(
                    RepeatedConditionReplacement(
                        Condition.DRAINED,
                        Condition.DEFENCELESS,
                        SOPORIFIC_BREATH_RULE_ID,
                    ),
                ),
            )


if __name__ == "__main__":
    unittest.main()
