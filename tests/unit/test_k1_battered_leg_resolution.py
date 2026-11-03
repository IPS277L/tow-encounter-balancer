from copy import copy
from dataclasses import replace
from unittest import TestCase
from unittest.mock import Mock

from tests.helpers import SequenceRandom
from towr.domain.battered_leg_models import BatteredLegEnduranceTestRequest
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import (
    CharacterInjuryState,
    CharacterWoundRequest,
    WoundConditionEffect,
    WoundEffectDuration,
    WoundEnduranceFailure,
    WoundEntryId,
    WoundRecord,
)
from towr.domain.test_models import (
    Characteristic, DiceModifier, InlineProfile, QualityModifier, RerollLock,
    Skill, SuccessModifier, TestProfile, TestQuality, TestRequest,
)
from towr.rules.battered_leg_resolution import execute_battered_leg_endurance_test
from towr.rules.injury_resolution import resolve_character_wound
from towr.rules.test_resolution import resolve_test
from towr.rules.wound_effect_resolution import resolve_wound_effect


def request(*, dice=(1, 8, 9), characteristic=Characteristic.TOUGHNESS):
    rolled = resolve_character_wound(
        CharacterWoundRequest("wound", CharacterInjuryState()),
        SequenceRandom((5,)),
    )
    effect = resolve_wound_effect(rolled.effect_request, rolled.state)
    follow_up = effect.follow_ups[0]
    return BatteredLegEnduranceTestRequest(
        "wound:endurance:execution",
        "hero",
        effect.state,
        effect,
        follow_up,
        TestRequest(follow_up.test_id, InlineProfile(3, 6)),
        unmounted=True,
        characteristic=characteristic,
    ), tuple(dice)


class BatteredLegResolutionTests(TestCase):
    def test_endurance_success_keeps_the_resolved_wound_state(self):
        source, dice = request()
        result = execute_battered_leg_endurance_test(source, SequenceRandom(dice))

        self.assertTrue(result.wound_result.succeeded)
        self.assertIs(result.request, source)
        self.assertEqual(result.test_result.trace.request_id, source.wound_test.test_id)
        self.assertEqual(result.wound_result.state, source.injury_state)
        self.assertFalse(result.wound_result.state.conditions.has(Condition.PRONE))

    def test_endurance_failure_applies_only_source_scoped_prone(self):
        source, dice = request(dice=(10, 10, 10, 7))
        rng = SequenceRandom(dice)

        result = execute_battered_leg_endurance_test(source, rng)

        self.assertFalse(result.wound_result.succeeded)
        self.assertTrue(result.wound_result.state.conditions.has(Condition.PRONE))
        self.assertIn(
            WoundConditionEffect(
                1,
                Condition.PRONE,
                WoundEffectDuration.UNTIL_REMOVED,
            ),
            result.wound_result.state.active_wound_effects,
        )
        self.assertEqual(result.wound_result.state.wounds, source.injury_state.wounds)
        self.assertEqual(rng.randint(1, 10), 7)

    def test_authored_characteristic_is_explicit_and_preserved(self):
        source, dice = request(characteristic=Characteristic.AGILITY)
        result = execute_battered_leg_endurance_test(source, SequenceRandom(dice))

        self.assertIs(result.request.characteristic, Characteristic.AGILITY)
        self.assertIs(result.request.skill, Skill.ENDURANCE)

    def test_invalid_wound_test_actor_skill_and_test_source_reject_before_rng(self):
        source, _ = request()
        invalid_requests = (
            lambda: replace(source, wound_test=replace(source.wound_test, entry_id=WoundEntryId.NICKED_ARM)),
            lambda: replace(source, wound_test=replace(source.wound_test, failure=WoundEnduranceFailure.DROP_RANDOM_HAND_ITEM)),
            lambda: replace(source, endurance_test=TestRequest("foreign:test", InlineProfile(3, 6))),
            lambda: replace(source, skill=Skill.MELEE),
            lambda: replace(source, actor_id=" "),
        )
        for build in invalid_requests:
            with self.subTest(build=build), self.assertRaises((TypeError, ValueError)):
                build()

        rng = Mock()
        with self.assertRaises((TypeError, ValueError)):
            execute_battered_leg_endurance_test(None, rng)
        rng.randint.assert_not_called()

    def test_unresolved_or_foreign_injury_snapshot_rejects(self):
        source, _ = request()
        unresolved = CharacterInjuryState(
            wounds=(WoundRecord(1, WoundEntryId.BATTERED_LEG, 5, (5,)),)
        )
        with self.assertRaises(ValueError):
            replace(source, injury_state=unresolved)

        foreign = CharacterInjuryState(
            wounds=(
                WoundRecord(
                    1,
                    WoundEntryId.STOMACH_BLOW,
                    6,
                    (6,),
                    effect_resolved=True,
                ),
            )
        )
        with self.assertRaises(ValueError):
            replace(source, injury_state=foreign)

    def test_result_rejects_a_detached_test_outcome(self):
        source, dice = request(dice=(10, 10, 10))
        result = execute_battered_leg_endurance_test(source, SequenceRandom(dice))

        with self.assertRaises(ValueError):
            replace(result, wound_result=replace(result.wound_result, succeeded=True))

    def test_all_existing_conditions_reject_before_rng(self):
        source, _ = request()
        rng = Mock()
        for condition in Condition:
            state = replace(
                source.injury_state,
                conditions=ConditionState(frozenset((condition,))),
            )
            with self.subTest(condition=condition), self.assertRaises(ValueError):
                replace(source, injury_state=state)

        # A detached typed snapshot is readmitted by execution as well.
        detached = copy(source)
        object.__setattr__(detached, "injury_state", state)
        with self.assertRaises(ValueError):
            execute_battered_leg_endurance_test(detached, rng)
        rng.randint.assert_not_called()

    def test_treated_and_healed_wounds_reject_before_rng(self):
        source, _ = request()
        rng = Mock()
        for treated, healed in ((True, False), (True, True)):
            state = replace(source.injury_state, wounds=(replace(
                source.injury_state.wounds[0], treated=treated, healed=healed,
            ),))
            with self.subTest(treated=treated, healed=healed), self.assertRaises(ValueError):
                replace(source, injury_state=state)
            detached = copy(source)
            object.__setattr__(detached, "injury_state", state)
            with self.assertRaises(ValueError):
                execute_battered_leg_endurance_test(detached, rng)
        rng.randint.assert_not_called()

    def test_mounted_or_untyped_mount_assertion_rejects(self):
        source, _ = request()
        with self.assertRaises(ValueError):
            replace(source, unmounted=False)
        with self.assertRaises(TypeError):
            replace(source, unmounted=1)

    def test_modifiers_and_reroll_sources_are_explicitly_outside_this_slice(self):
        source, _ = request()
        fields = (
            ("dice_modifiers", (DiceModifier("bonus", 2),)),
            ("quality_modifiers", (QualityModifier("glorious", TestQuality.GLORIOUS),)),
            ("success_modifiers", (SuccessModifier("success", 1),)),
            ("reroll_locks", (RerollLock("locked", 9),)),
        )
        for name, value in fields:
            test = replace(source.endurance_test, **{name: value})
            with self.subTest(name=name), self.assertRaises(ValueError):
                replace(source, endurance_test=test)

    def test_effect_witness_must_own_the_exact_follow_up(self):
        source, _ = request()
        foreign = replace(source.wound_effect, request=replace(
            source.wound_effect.request, id="another:effect",
        ))
        with self.assertRaises(ValueError):
            replace(source, wound_effect=foreign)

    def test_same_id_foreign_test_profile_cannot_replace_the_actual_trace(self):
        source, dice = request()
        result = execute_battered_leg_endurance_test(source, SequenceRandom(dice))
        foreign = resolve_test(
            TestRequest(source.endurance_test.id, InlineProfile(1, 10)),
            SequenceRandom((1,)),
        )
        with self.assertRaises(ValueError):
            replace(result, test_result=foreign)

    def test_forged_success_arithmetic_cannot_replace_the_actual_trace(self):
        source, dice = request()
        result = execute_battered_leg_endurance_test(source, SequenceRandom(dice))
        for changes in ({"successes": 99}, {"success_delta": 1}, {"successes": True}):
            foreign = replace(result.test_result, trace=replace(
                result.test_result.trace, **changes,
            ))
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(result, test_result=foreign)

    def test_both_authored_profiles_and_a_natural_one_die_use_their_skill_threshold(self):
        source, _ = request()
        for profile, dice in ((TestProfile(2, 6), (6, 10)), (InlineProfile(1, 6), (6,))):
            candidate = replace(source, endurance_test=replace(
                source.endurance_test, profile=profile,
            ))
            with self.subTest(profile=profile):
                result = execute_battered_leg_endurance_test(candidate, SequenceRandom(dice))
                self.assertTrue(result.wound_result.succeeded)

    def test_detached_equal_string_cannot_replace_a_typed_follow_up(self):
        source, _ = request()
        detached = copy(source.wound_test)
        object.__setattr__(detached, "entry_id", WoundEntryId.BATTERED_LEG.value)
        effect = replace(source.wound_effect, follow_ups=(detached,))
        with self.assertRaises(TypeError):
            replace(source, wound_effect=effect)

    def test_failed_result_requires_a_typed_prone_condition(self):
        source, dice = request(dice=(10, 10, 10))
        result = execute_battered_leg_endurance_test(source, SequenceRandom(dice))
        conditions = copy(result.wound_result.state.conditions)
        object.__setattr__(conditions, "conditions", frozenset(("prone",)))
        state = replace(result.wound_result.state, conditions=conditions)
        with self.assertRaises(TypeError):
            replace(result, wound_result=replace(result.wound_result, state=state))

