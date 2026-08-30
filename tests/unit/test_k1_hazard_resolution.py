from __future__ import annotations

import unittest

from tests.helpers import SequenceRandom
from towr.domain.attack_models import HazardImpactSpec
from towr.domain.condition_models import (
    Condition,
    ConditionState,
    EffectClassification,
    EffectImmunity,
    RepeatedConditionReplacement,
)
from towr.domain.injury_models import (
    CharacterInjuryState,
    ProfileInjuryState,
    WoundEntryId,
    WoundNegationOption,
    WoundRecord,
)
from towr.domain.infection_models import DailyWoundState
from towr.domain.resolution_models import (
    ConsumeWoundNegationRequest,
    HazardExposureRequest,
    HazardResolutionRequest,
    TargetInjuryPolicy,
)
from towr.domain.test_models import InlineProfile, Skill, TestRequest
from towr.domain.wound_lifecycle_models import (
    CharacterWoundLifecycleCompletionRequest,
)
from towr.rules.hazard_resolution import (
    apply_hazard_character_wound_completion,
    resolve_hazard,
    resolve_hazard_exposure_application,
)
from towr.rules.test_resolution import resolve_test
from towr.rules.wound_lifecycle_resolution import (
    complete_character_wound_lifecycle,
)


class FixedWoundDecision:
    def __init__(self, rule_id: str | None) -> None:
        self.rule_id = rule_id

    def choose_wound_negation(self, **_: object) -> str | None:
        return self.rule_id


def exposure(
    *,
    rating: int,
    inflicts_wound: bool = True,
    failure_conditions: tuple[Condition, ...] = (),
    repeated_condition_replacements: tuple[
        RepeatedConditionReplacement, ...
    ] = (),
) -> HazardExposureRequest:
    return HazardExposureRequest.from_spec(
        "hazard-source",
        HazardImpactSpec(
            rating,
            Skill.ENDURANCE,
            "RULE-HAZARD:test",
            inflicts_wound=inflicts_wound,
            failure_conditions=failure_conditions,
            repeated_condition_replacements=(
                repeated_condition_replacements
            ),
        ),
    )


def avoidance_test(
    request: HazardExposureRequest,
    values: list[int],
):
    return resolve_test(
        TestRequest(
            request.test_id,
            InlineProfile(len(values), 5),
        ),
        SequenceRandom(values),
    )


def complete_pending_hazard(result, *, registration: bool = True):
    pending = result.pending_character_wound
    assert pending is not None
    completion = complete_character_wound_lifecycle(
        CharacterWoundLifecycleCompletionRequest(
            id=f"{result.request_id}:complete-wound",
            roll=pending,
            current_state=result.state,
            daily_wounds=DailyWoundState("day:1", "target"),
            daily_registration_id=(
                f"{result.request_id}:daily-wound" if registration else None
            ),
        )
    )
    return apply_hazard_character_wound_completion(result, completion)


def old_wound() -> WoundRecord:
    return WoundRecord(
        sequence=1,
        entry_id=WoundEntryId.SUPERFICIAL_INJURY,
        table_total=1,
        roll_values=(1,),
    )


class K1HazardResolutionTests(unittest.TestCase):
    def test_matching_immunity_blocks_entire_exposure_before_test(self) -> None:
        immunity = EffectImmunity(
            EffectClassification.PSYCHOLOGICAL,
            "RULE-NPC:undead-psychological-immunity",
        )
        hazard = HazardExposureRequest.from_spec(
            "fear-hazard",
            HazardImpactSpec(
                2,
                Skill.WILLPOWER,
                "RULE-HAZARD:supernatural-fear",
                failure_conditions=(Condition.BROKEN,),
                classification=EffectClassification.PSYCHOLOGICAL,
            ),
        )

        result = resolve_hazard_exposure_application(hazard, (immunity,))

        self.assertTrue(result.blocked)
        self.assertEqual(result.source_rule_id, hazard.rule_id)
        self.assertEqual(result.blocked_by_rule_id, immunity.rule_id)
        self.assertEqual(result.applied_rule_ids, (immunity.rule_id,))

    def test_willpower_does_not_imply_psychological_hazard(self) -> None:
        immunity = EffectImmunity(
            EffectClassification.PSYCHOLOGICAL,
            "RULE-NPC:undead-psychological-immunity",
        )
        sunlight = HazardExposureRequest.from_spec(
            "sunlight-hazard",
            HazardImpactSpec(
                2,
                Skill.WILLPOWER,
                "RULE-NPC:vampire-sunlight",
                failure_conditions=(Condition.ABLAZE,),
            ),
        )

        result = resolve_hazard_exposure_application(sunlight, (immunity,))

        self.assertFalse(result.blocked)
        self.assertEqual(result.applied_rule_ids, (sunlight.rule_id,))

    def test_resolution_rejects_an_unrelated_test_result(self) -> None:
        hazard = exposure(rating=1)
        unrelated = resolve_test(
            TestRequest("another-test", InlineProfile(1, 5)),
            SequenceRandom([1]),
        )

        with self.assertRaises(ValueError):
            HazardResolutionRequest(
                "hazard",
                "target",
                hazard,
                unrelated,
                TargetInjuryPolicy.PLAYER,
                CharacterInjuryState(),
            )

    def test_successes_equal_to_rating_avoid_hazard(self) -> None:
        hazard = exposure(rating=2, failure_conditions=(Condition.PRONE,))
        state = CharacterInjuryState()
        request = HazardResolutionRequest(
            "hazard",
            "target",
            hazard,
            avoidance_test(hazard, [1, 2]),
            TargetInjuryPolicy.PLAYER,
            state,
        )

        result = resolve_hazard(request, SequenceRandom([]))

        self.assertTrue(result.avoided)
        self.assertEqual(result.shortfall, 0)
        self.assertIs(result.state, state)
        self.assertEqual(result.failure_conditions, ())

    def test_shortfall_sets_base_wound_dice_before_untreated_wounds(self) -> None:
        hazard = exposure(
            rating=3,
            failure_conditions=(Condition.PRONE,),
        )
        state = CharacterInjuryState(wounds=(old_wound(),))
        request = HazardResolutionRequest(
            "hazard",
            "target",
            hazard,
            avoidance_test(hazard, [1, 10]),
            TargetInjuryPolicy.PLAYER,
            state,
        )

        result = resolve_hazard(request, SequenceRandom([1, 2, 3]))

        self.assertFalse(result.avoided)
        self.assertEqual(result.shortfall, 2)
        self.assertIsNotNone(result.character_wound)
        assert result.character_wound is not None
        self.assertEqual(result.character_wound.table_roll.dice, 3)
        self.assertIsNotNone(result.pending_character_wound)
        self.assertIsNone(result.wound_effect)
        self.assertFalse(result.state.conditions.has(Condition.PRONE))
        self.assertFalse(result.state.conditions.has(Condition.DRAINED))

        completed = complete_pending_hazard(result)
        self.assertTrue(completed.state.conditions.has(Condition.PRONE))
        self.assertTrue(completed.state.conditions.has(Condition.DRAINED))

    def test_condition_only_hazard_does_not_create_wound(self) -> None:
        hazard = exposure(
            rating=1,
            inflicts_wound=False,
            failure_conditions=(Condition.DRAINED,),
        )
        request = HazardResolutionRequest(
            "hazard",
            "target",
            hazard,
            avoidance_test(hazard, [10]),
            TargetInjuryPolicy.PLAYER,
            CharacterInjuryState(),
        )

        result = resolve_hazard(request, SequenceRandom([]))

        self.assertIsNone(result.character_wound)
        self.assertTrue(result.state.conditions.has(Condition.DRAINED))
        self.assertEqual(result.failure_conditions, (Condition.DRAINED,))

    def test_repeated_failure_condition_can_apply_a_replacement(self) -> None:
        replacement = RepeatedConditionReplacement(
            Condition.DRAINED,
            Condition.DEFENCELESS,
            "RULE-NPC:test-repeated-drained",
        )
        hazard = exposure(
            rating=1,
            inflicts_wound=False,
            failure_conditions=(Condition.DRAINED,),
            repeated_condition_replacements=(replacement,),
        )
        request = HazardResolutionRequest(
            "hazard",
            "target",
            hazard,
            avoidance_test(hazard, [10]),
            TargetInjuryPolicy.PLAYER,
            CharacterInjuryState(
                conditions=ConditionState(frozenset({Condition.DRAINED}))
            ),
        )

        result = resolve_hazard(request, SequenceRandom([]))

        self.assertTrue(result.state.conditions.has(Condition.DRAINED))
        self.assertTrue(result.state.conditions.has(Condition.DEFENCELESS))
        self.assertEqual(result.failure_conditions, (Condition.DEFENCELESS,))
        self.assertEqual(
            result.applied_rule_ids,
            (hazard.rule_id, replacement.rule_id),
        )

    def test_profile_npc_suffers_wounds_equal_to_shortfall(self) -> None:
        hazard = exposure(
            rating=3,
            failure_conditions=(Condition.BURDENED,),
        )
        request = HazardResolutionRequest(
            "hazard",
            "target",
            hazard,
            avoidance_test(hazard, [10]),
            TargetInjuryPolicy.BRUTE,
            ProfileInjuryState(wounds=0, wound_limit=5),
        )

        result = resolve_hazard(request, SequenceRandom([]))

        self.assertIsNotNone(result.profile_wound)
        assert result.profile_wound is not None
        self.assertEqual(result.profile_wound.wounds_requested, 3)
        self.assertEqual(result.state.wounds, 3)
        self.assertTrue(result.state.conditions.has(Condition.BURDENED))

    def test_near_miss_does_not_cancel_other_hazard_conditions(self) -> None:
        hazard = exposure(
            rating=1,
            failure_conditions=(Condition.PRONE,),
        )
        near_miss = WoundNegationOption("RULE-FATE:near-miss")
        request = HazardResolutionRequest(
            "hazard",
            "target",
            hazard,
            avoidance_test(hazard, [10]),
            TargetInjuryPolicy.PLAYER,
            CharacterInjuryState(
                conditions=ConditionState(frozenset({Condition.STAGGERED}))
            ),
            wound_negation_options=(near_miss,),
        )

        result = resolve_hazard(
            request,
            SequenceRandom([10]),
            decisions=FixedWoundDecision(near_miss.rule_id),
        )

        self.assertIsNotNone(result.character_wound)
        assert result.character_wound is not None
        self.assertFalse(result.character_wound.wound_accepted)
        self.assertTrue(result.state.conditions.has(Condition.STAGGERED))
        self.assertFalse(result.state.conditions.has(Condition.PRONE))
        result = complete_pending_hazard(result, registration=False)
        self.assertTrue(result.state.conditions.has(Condition.PRONE))
        self.assertIsInstance(
            result.follow_ups[0],
            ConsumeWoundNegationRequest,
        )


if __name__ == "__main__":
    unittest.main()
