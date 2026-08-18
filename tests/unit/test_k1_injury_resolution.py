from __future__ import annotations

import unittest

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import (
    AdditionalProfileWound,
    CharacterInjuryState,
    CharacterWoundRequest,
    CharacterWoundType,
    ProfileInjuryState,
    ProfileNpcType,
    ProfileWoundRequest,
    WoundDiceModifier,
    WoundEntryId,
    WoundNegationOption,
    WoundRecord,
)
from towr.rules.injury_resolution import (
    InvalidWoundDecisionError,
    MissingWoundDecisionError,
    resolve_character_wound,
    resolve_profile_wound,
)
from towr.rules.wound_table import lookup_wound


class FixedWoundDecision:
    def __init__(self, rule_id: str | None) -> None:
        self.rule_id = rule_id

    def choose_wound_negation(self, **_: object) -> str | None:
        return self.rule_id


def old_wound(sequence: int, *, treated: bool = False) -> WoundRecord:
    return WoundRecord(
        sequence=sequence,
        entry_id=WoundEntryId.SUPERFICIAL_INJURY,
        table_total=1,
        roll_values=(1,),
        treated=treated,
    )


class K1WoundTableTests(unittest.TestCase):
    def test_table_maps_boundaries_and_keeps_27_plus_open_ended(self) -> None:
        self.assertIs(lookup_wound(1).id, WoundEntryId.SUPERFICIAL_INJURY)
        self.assertIs(lookup_wound(3).id, WoundEntryId.SUPERFICIAL_INJURY)
        self.assertIs(lookup_wound(4).id, WoundEntryId.NICKED_ARM)
        self.assertIs(lookup_wound(23).id, WoundEntryId.RUINED_EYES)
        self.assertIs(lookup_wound(24).id, WoundEntryId.APPALLING_STRIKE)
        self.assertIs(lookup_wound(26).id, WoundEntryId.PIERCED_HEART)
        self.assertIs(lookup_wound(27).id, WoundEntryId.DECAPITATION)
        self.assertIs(lookup_wound(100).id, WoundEntryId.DECAPITATION)


class K1CharacterInjuryTests(unittest.TestCase):
    def test_first_wound_records_result_and_removes_staggered(self) -> None:
        state = CharacterInjuryState(
            conditions=ConditionState(frozenset({Condition.STAGGERED}))
        )

        result = resolve_character_wound(
            CharacterWoundRequest("first-wound", state),
            SequenceRandom([3]),
        )

        self.assertTrue(result.wound_accepted)
        self.assertEqual(result.table_roll.values, (3,))
        self.assertIs(
            result.table_roll.entry.id,
            WoundEntryId.SUPERFICIAL_INJURY,
        )
        self.assertEqual(len(result.state.wounds), 1)
        self.assertFalse(result.state.conditions.has(Condition.STAGGERED))
        self.assertIsNotNone(result.effect_request)

    def test_only_untreated_wounds_add_table_dice(self) -> None:
        state = CharacterInjuryState(
            wounds=(old_wound(1), old_wound(2, treated=True))
        )

        result = resolve_character_wound(
            CharacterWoundRequest("next-wound", state),
            SequenceRandom([4, 5]),
        )

        self.assertEqual(result.table_roll.dice, 2)
        self.assertEqual(result.table_roll.total, 9)
        self.assertIs(result.table_roll.entry.id, WoundEntryId.LEG_SPASM)

    def test_wound_dice_modifiers_apply_with_minimum_one_die(self) -> None:
        increased = resolve_character_wound(
            CharacterWoundRequest(
                "increased",
                CharacterInjuryState(),
                dice_modifiers=(WoundDiceModifier("RULE-WEAPON", 1),),
            ),
            SequenceRandom([5, 5]),
        )
        reduced = resolve_character_wound(
            CharacterWoundRequest(
                "reduced",
                CharacterInjuryState(wounds=(old_wound(1),)),
                dice_modifiers=(WoundDiceModifier("RULE-HARDY", -5),),
            ),
            SequenceRandom([1]),
        )

        self.assertEqual(increased.table_roll.dice, 2)
        self.assertEqual(reduced.table_roll.dice, 1)
        self.assertEqual(reduced.applied_rule_ids, ("RULE-HARDY",))

    def test_lethal_table_result_marks_character_dead(self) -> None:
        state = CharacterInjuryState(
            wounds=(old_wound(1), old_wound(2), old_wound(3))
        )

        result = resolve_character_wound(
            CharacterWoundRequest("lethal", state),
            SequenceRandom([6, 6, 6, 6]),
        )

        self.assertEqual(result.table_roll.total, 24)
        self.assertTrue(result.table_roll.entry.lethal)
        self.assertTrue(result.state.dead)

    def test_near_miss_is_chosen_after_roll_and_preserves_state(self) -> None:
        state = CharacterInjuryState(
            wounds=(old_wound(1), old_wound(2), old_wound(3)),
            conditions=ConditionState(frozenset({Condition.STAGGERED})),
        )
        request = CharacterWoundRequest(
            "near-miss",
            state,
            negation_options=(WoundNegationOption("RULE-FATE:near-miss"),),
        )

        result = resolve_character_wound(
            request,
            SequenceRandom([10, 10, 10, 10]),
            decisions=FixedWoundDecision("RULE-FATE:near-miss"),
        )

        self.assertEqual(result.table_roll.total, 40)
        self.assertFalse(result.wound_accepted)
        self.assertIs(result.state, state)
        self.assertTrue(result.state.conditions.has(Condition.STAGGERED))
        self.assertEqual(result.negated_by_rule_id, "RULE-FATE:near-miss")
        self.assertIsNone(result.effect_request)

    def test_negation_option_requires_explicit_valid_decision(self) -> None:
        request = CharacterWoundRequest(
            "optional",
            CharacterInjuryState(),
            negation_options=(WoundNegationOption("RULE-FATE:near-miss"),),
        )
        with self.assertRaises(MissingWoundDecisionError):
            resolve_character_wound(request, SequenceRandom([1]))
        with self.assertRaises(InvalidWoundDecisionError):
            resolve_character_wound(
                request,
                SequenceRandom([1]),
                decisions=FixedWoundDecision("RULE-NOT-AVAILABLE"),
            )

    def test_character_can_decline_available_negation(self) -> None:
        request = CharacterWoundRequest(
            "accepted",
            CharacterInjuryState(),
            negation_options=(WoundNegationOption("RULE-FATE:near-miss"),),
        )

        result = resolve_character_wound(
            request,
            SequenceRandom([1]),
            decisions=FixedWoundDecision(None),
        )

        self.assertTrue(result.wound_accepted)
        self.assertIsNone(result.negated_by_rule_id)

    def test_champion_uses_the_same_wounds_table_policy(self) -> None:
        result = resolve_character_wound(
            CharacterWoundRequest(
                "champion-wound",
                CharacterInjuryState(),
                subject_type=CharacterWoundType.CHAMPION,
            ),
            SequenceRandom([4]),
        )

        self.assertIs(result.subject_type, CharacterWoundType.CHAMPION)
        self.assertIs(result.table_roll.entry.id, WoundEntryId.NICKED_ARM)


class K1ProfileInjuryTests(unittest.TestCase):
    def test_minion_is_defeated_by_one_wound(self) -> None:
        request = ProfileWoundRequest(
            "minion-wound",
            ProfileNpcType.MINION,
            ProfileInjuryState(wounds=0, wound_limit=1),
        )

        result = resolve_profile_wound(request)

        self.assertTrue(result.state.defeated)
        self.assertEqual(result.wounds_inflicted, 1)

    def test_brute_tracks_wounds_and_requests_profile_state_change(self) -> None:
        request = ProfileWoundRequest(
            "brute-wound",
            ProfileNpcType.BRUTE,
            ProfileInjuryState(
                wounds=0,
                wound_limit=3,
                conditions=ConditionState(frozenset({Condition.STAGGERED})),
            ),
        )

        result = resolve_profile_wound(request)

        self.assertEqual(result.state.wounds, 1)
        self.assertFalse(result.state.defeated)
        self.assertFalse(result.state.conditions.has(Condition.STAGGERED))
        self.assertEqual(result.state_change.previous_wounds, 0)
        self.assertEqual(result.state_change.current_wounds, 1)

    def test_extra_table_die_becomes_additional_profile_wound(self) -> None:
        request = ProfileWoundRequest(
            "heavy-wound",
            ProfileNpcType.MONSTROSITY,
            ProfileInjuryState(wounds=1, wound_limit=3),
            additional_wounds=(
                AdditionalProfileWound("RULE-WEAPON:wound-die", count=1),
            ),
        )

        result = resolve_profile_wound(request)

        self.assertEqual(result.wounds_requested, 2)
        self.assertEqual(result.wounds_inflicted, 2)
        self.assertEqual(result.state.wounds, 3)
        self.assertTrue(result.state.defeated)
        self.assertEqual(result.applied_rule_ids, ("RULE-WEAPON:wound-die",))

    def test_wounds_are_capped_at_profile_limit(self) -> None:
        request = ProfileWoundRequest(
            "overkill",
            ProfileNpcType.BRUTE,
            ProfileInjuryState(wounds=2, wound_limit=3),
            additional_wounds=(AdditionalProfileWound("RULE-OVERKILL", 3),),
        )

        result = resolve_profile_wound(request)

        self.assertEqual(result.wounds_requested, 4)
        self.assertEqual(result.wounds_inflicted, 1)
        self.assertEqual(result.state.wounds, 3)


if __name__ == "__main__":
    unittest.main()
