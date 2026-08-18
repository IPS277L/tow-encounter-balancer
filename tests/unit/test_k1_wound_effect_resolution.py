from __future__ import annotations

import unittest

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition
from towr.domain.injury_models import (
    CharacterInjuryState,
    WoundChoice,
    WoundChoiceRequest,
    WoundConditionEffect,
    WoundConsequence,
    WoundConsequenceRequest,
    WoundEffectDuration,
    WoundEffectRequest,
    WoundEnduranceFailure,
    WoundEnduranceTestRequest,
    WoundEntryId,
    WoundRecord,
    WoundRestriction,
    WoundRestrictionEffect,
)
from towr.domain.test_models import InlineProfile, TestRequest
from towr.rules.test_resolution import resolve_test
from towr.rules.wound_effect_resolution import (
    WOUND_EFFECT_SPECS,
    resolve_wound_choice,
    resolve_wound_effect,
    resolve_wound_endurance_test,
)


def injury_state(entry_id: WoundEntryId) -> CharacterInjuryState:
    return CharacterInjuryState(
        wounds=(
            WoundRecord(
                sequence=1,
                entry_id=entry_id,
                table_total=1,
                roll_values=(1,),
            ),
        )
    )


def effect_request(entry_id: WoundEntryId) -> WoundEffectRequest:
    return WoundEffectRequest(
        "wound-effect",
        1,
        entry_id,
        f"RULE-WOUND:{entry_id.value}",
    )


def endurance_result(test_id: str, die: int):
    return resolve_test(
        TestRequest(test_id, InlineProfile(1, 5)),
        SequenceRandom([die]),
    )


class K1WoundEffectTests(unittest.TestCase):
    def test_every_wound_table_entry_has_an_explicit_effect_spec(self) -> None:
        self.assertEqual(set(WOUND_EFFECT_SPECS), set(WoundEntryId))

    def test_unconditional_condition_is_sourced_and_effect_is_closed(self) -> None:
        request = effect_request(WoundEntryId.STOMACH_BLOW)

        result = resolve_wound_effect(
            request,
            injury_state(WoundEntryId.STOMACH_BLOW),
        )

        self.assertTrue(result.state.conditions.has(Condition.DRAINED))
        self.assertEqual(
            result.state.active_wound_effects,
            (
                WoundConditionEffect(
                    1,
                    Condition.DRAINED,
                    WoundEffectDuration.END_OF_NEXT_TURN,
                ),
            ),
        )
        self.assertTrue(result.state.wounds[0].effect_resolved)
        self.assertEqual(result.follow_ups, ())

    def test_drop_then_endurance_order_is_preserved_for_smashed_hand(self) -> None:
        result = resolve_wound_effect(
            effect_request(WoundEntryId.SMASHED_HAND),
            injury_state(WoundEntryId.SMASHED_HAND),
        )

        self.assertIsInstance(result.follow_ups[0], WoundConsequenceRequest)
        self.assertEqual(
            result.follow_ups[0].consequence,
            WoundConsequence.DROP_RANDOM_HAND_ITEM,
        )
        self.assertIsInstance(result.follow_ups[1], WoundEnduranceTestRequest)
        self.assertEqual(
            result.follow_ups[1].failure,
            WoundEnduranceFailure.LOSE_RANDOM_FINGER,
        )
        self.assertIn(
            WoundRestrictionEffect(
                1,
                WoundRestriction.USING_INJURED_HAND_CAUSES_CRITICAL,
                WoundEffectDuration.UNTIL_TREATED,
            ),
            result.state.active_wound_effects,
        )

    def test_scarring_strike_reapplies_sourced_staggered(self) -> None:
        result = resolve_wound_effect(
            effect_request(WoundEntryId.SCARRING_STRIKE),
            injury_state(WoundEntryId.SCARRING_STRIKE),
        )

        self.assertTrue(result.state.conditions.has(Condition.STAGGERED))
        self.assertIn(
            WoundRestrictionEffect(
                1,
                WoundRestriction.NON_FACE_PROTECTION_ACTION_CAUSES_CRITICAL,
                WoundEffectDuration.UNTIL_TREATED,
            ),
            result.state.active_wound_effects,
        )

    def test_severed_leg_keeps_permanent_loss_and_slow_speed(self) -> None:
        result = resolve_wound_effect(
            effect_request(WoundEntryId.SEVERED_LEG),
            injury_state(WoundEntryId.SEVERED_LEG),
        )

        self.assertTrue(result.state.conditions.has(Condition.DEFENCELESS))
        self.assertIn(
            WoundRestrictionEffect(
                1,
                WoundRestriction.LEG_LOST,
                WoundEffectDuration.PERMANENT,
            ),
            result.state.active_wound_effects,
        )
        self.assertIn(
            WoundRestrictionEffect(
                1,
                WoundRestriction.SPEED_IS_SLOW,
                WoundEffectDuration.PERMANENT,
            ),
            result.state.active_wound_effects,
        )
        self.assertEqual(
            result.follow_ups[0].consequence,
            WoundConsequence.RANDOMISE_SEVERED_LEG,
        )

    def test_effect_cannot_be_applied_twice(self) -> None:
        request = effect_request(WoundEntryId.STOMACH_BLOW)
        first = resolve_wound_effect(
            request,
            injury_state(WoundEntryId.STOMACH_BLOW),
        )

        with self.assertRaises(ValueError):
            resolve_wound_effect(request, first.state)


class K1WoundEnduranceTests(unittest.TestCase):
    def test_success_avoids_the_failure_effect(self) -> None:
        state = injury_state(WoundEntryId.BATTERED_LEG)
        request = WoundEnduranceTestRequest(
            "endurance",
            1,
            WoundEntryId.BATTERED_LEG,
            WoundEnduranceFailure.FALL_PRONE,
            "RULE-WOUND:battered-leg",
        )

        result = resolve_wound_endurance_test(
            request,
            state,
            endurance_result("endurance", 1),
        )

        self.assertTrue(result.succeeded)
        self.assertIs(result.state, state)

    def test_failed_test_applies_temporary_condition(self) -> None:
        state = injury_state(WoundEntryId.GASHED_BROW)
        request = WoundEnduranceTestRequest(
            "endurance",
            1,
            WoundEntryId.GASHED_BROW,
            WoundEnduranceFailure.BLINDED_UNTIL_END_OF_NEXT_TURN,
            "RULE-WOUND:gashed-brow",
        )

        result = resolve_wound_endurance_test(
            request,
            state,
            endurance_result("endurance", 10),
        )

        self.assertFalse(result.succeeded)
        self.assertTrue(result.state.conditions.has(Condition.BLINDED))
        self.assertIn(
            WoundConditionEffect(
                1,
                Condition.BLINDED,
                WoundEffectDuration.END_OF_NEXT_TURN,
            ),
            result.state.active_wound_effects,
        )

    def test_failed_test_can_emit_an_inventory_consequence(self) -> None:
        state = injury_state(WoundEntryId.NICKED_ARM)
        request = WoundEnduranceTestRequest(
            "endurance",
            1,
            WoundEntryId.NICKED_ARM,
            WoundEnduranceFailure.DROP_RANDOM_HAND_ITEM,
            "RULE-WOUND:nicked-arm",
        )

        result = resolve_wound_endurance_test(
            request,
            state,
            endurance_result("endurance", 10),
        )

        self.assertEqual(
            result.follow_ups[0].consequence,
            WoundConsequence.DROP_RANDOM_HAND_ITEM,
        )


class K1WoundChoiceTests(unittest.TestCase):
    def test_spilling_guts_choice_is_explicit(self) -> None:
        state = injury_state(WoundEntryId.SPILLING_GUTS)
        request = WoundChoiceRequest(
            1,
            (
                WoundChoice.DROP_AND_CLUTCH_STOMACH,
                WoundChoice.BECOME_DEFENCELESS,
            ),
            "RULE-WOUND:spilling-guts",
        )

        comply = resolve_wound_choice(
            request,
            state,
            WoundChoice.DROP_AND_CLUTCH_STOMACH,
        )
        refuse = resolve_wound_choice(
            request,
            state,
            WoundChoice.BECOME_DEFENCELESS,
        )

        self.assertEqual(
            comply.follow_ups[0].consequence,
            WoundConsequence.DROP_ONE_HAND_ITEM_AND_CLUTCH_STOMACH,
        )
        self.assertTrue(refuse.state.conditions.has(Condition.DEFENCELESS))


if __name__ == "__main__":
    unittest.main()
