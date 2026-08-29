from __future__ import annotations

import unittest
from dataclasses import replace

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import (
    CharacterInjuryState,
    WoundConditionEffect,
    WoundConditionSourceSnapshot,
    WoundEffectDuration,
    WoundEntryId,
    WoundRecord,
    WoundRestriction,
    WoundRestrictionEffect,
)
from towr.domain.wound_healing_models import (
    NightsRespiteHealingOpportunity,
    NightsRespiteHealingRequest,
)
from towr.rules.wound_healing_resolution import (
    apply_nights_respite_healing,
)


def injury_state() -> CharacterInjuryState:
    return CharacterInjuryState(
        wounds=(
            WoundRecord(
                1,
                WoundEntryId.INTERNAL_INJURY,
                14,
                (10, 4),
                treated=True,
                effect_resolved=True,
            ),
            WoundRecord(
                2,
                WoundEntryId.SCARRING_STRIKE,
                15,
                (10, 5),
                treated=True,
                effect_resolved=True,
            ),
            WoundRecord(
                3,
                WoundEntryId.SLASHED_FOREARMS,
                16,
                (10, 6),
                treated=True,
                effect_resolved=True,
            ),
            WoundRecord(
                4,
                WoundEntryId.SHAKING_GRIP,
                8,
                (8,),
                effect_resolved=True,
            ),
            WoundRecord(
                5,
                WoundEntryId.GASHED_BROW,
                7,
                (7,),
                treated=True,
                effect_resolved=True,
                healed=True,
            ),
        ),
        conditions=ConditionState(
            {Condition.DRAINED, Condition.STAGGERED, Condition.PRONE}
        ),
        active_wound_effects=(
            WoundConditionEffect(
                1,
                Condition.DRAINED,
                WoundEffectDuration.UNTIL_HEALED,
            ),
            WoundRestrictionEffect(
                1,
                WoundRestriction.NEXT_TEST_IS_GRIM,
                WoundEffectDuration.NEXT_TEST,
            ),
            WoundRestrictionEffect(
                1,
                WoundRestriction.ARM_LOST,
                WoundEffectDuration.PERMANENT,
            ),
            WoundConditionEffect(
                2,
                Condition.STAGGERED,
                WoundEffectDuration.UNTIL_HEALED,
            ),
            WoundConditionEffect(
                3,
                Condition.DRAINED,
                WoundEffectDuration.UNTIL_HEALED,
            ),
            WoundRestrictionEffect(
                4,
                WoundRestriction.CANNOT_AIM,
                WoundEffectDuration.UNTIL_TREATED,
            ),
        ),
    )


def opportunity(
    state: CharacterInjuryState,
    *,
    took_it_easy: bool = True,
    early_night_completed: bool = True,
    morning_has_arrived: bool = True,
) -> NightsRespiteHealingOpportunity:
    return NightsRespiteHealingOpportunity(
        id="rest:1:nights-respite:hero",
        rest_id="rest:1",
        target_id="hero",
        injury_state=state,
        took_it_easy=took_it_easy,
        early_night_completed=early_night_completed,
        morning_has_arrived=morning_has_arrived,
    )


def request(
    state: CharacterInjuryState,
    *,
    wound_sequences: tuple[int, ...] = (1, 2),
    drained_has_other_source: bool = True,
    consumed_source_ids: tuple[str, ...] = ("prior-opportunity",),
    rule_id: str | None = None,
) -> NightsRespiteHealingRequest:
    source = opportunity(state)
    values = {
        "id": "rest:1:nights-respite:hero:apply",
        "opportunity": source,
        "target_id": "hero",
        "injury_state": state,
        "wound_sequences": wound_sequences,
        "condition_source_snapshots": (
            WoundConditionSourceSnapshot(
                Condition.DRAINED,
                drained_has_other_source,
            ),
            WoundConditionSourceSnapshot(Condition.STAGGERED, False),
        ),
        "consumed_source_ids": consumed_source_ids,
    }
    if rule_id is not None:
        values["rule_id"] = rule_id
    return NightsRespiteHealingRequest(**values)


class K1NightsRespiteHealingTests(unittest.TestCase):
    def test_heals_ready_night_wounds_and_reuses_common_transition(self) -> None:
        state = injury_state()
        source = request(state)

        result = apply_nights_respite_healing(source)

        self.assertEqual(result.healed_wound_sequences, (1, 2))
        self.assertTrue(result.state.wounds[0].healed)
        self.assertTrue(result.state.wounds[1].healed)
        self.assertFalse(result.state.wounds[2].healed)
        self.assertFalse(result.state.wounds[3].healed)
        self.assertEqual(result.state.wounds[4], state.wounds[4])
        self.assertEqual(
            result.removed_effects,
            (
                state.active_wound_effects[0],
                state.active_wound_effects[1],
                state.active_wound_effects[3],
            ),
        )
        self.assertEqual(
            result.state.active_wound_effects,
            (
                state.active_wound_effects[2],
                state.active_wound_effects[4],
                state.active_wound_effects[5],
            ),
        )
        self.assertTrue(result.state.conditions.has(Condition.DRAINED))
        self.assertFalse(result.state.conditions.has(Condition.STAGGERED))
        self.assertTrue(result.state.conditions.has(Condition.PRONE))
        self.assertEqual(result.removed_conditions, (Condition.STAGGERED,))
        self.assertEqual(
            result.consumed_source_ids,
            ("prior-opportunity", source.opportunity.id),
        )
        self.assertFalse(hasattr(result, "slot"))
        self.assertFalse(hasattr(result, "test_result"))
        self.assertFalse(
            hasattr(result.source_request.opportunity, "hours_slept")
        )

    def test_every_table_entry_from_eight_through_fifteen_is_eligible(
        self,
    ) -> None:
        entries = (
            WoundEntryId.SHAKING_GRIP,
            WoundEntryId.LEG_SPASM,
            WoundEntryId.CRUSHED_RIB,
            WoundEntryId.EARS_RINGING,
            WoundEntryId.SMASHED_HAND,
            WoundEntryId.TORN_LEG,
            WoundEntryId.INTERNAL_INJURY,
            WoundEntryId.SCARRING_STRIKE,
        )
        state = CharacterInjuryState(
            wounds=tuple(
                WoundRecord(
                    sequence=index,
                    entry_id=entry_id,
                    table_total=total,
                    roll_values=(total,)
                    if total <= 10
                    else (10, total - 10),
                    treated=True,
                    effect_resolved=True,
                )
                for index, (entry_id, total) in enumerate(
                    zip(entries, range(8, 16), strict=True),
                    start=1,
                )
            )
        )
        source = opportunity(state)
        healing = NightsRespiteHealingRequest(
            "rest:1:all-night-wounds",
            source,
            "hero",
            state,
            tuple(range(1, 9)),
        )

        result = apply_nights_respite_healing(healing)

        self.assertTrue(all(wound.healed for wound in result.state.wounds))

    def test_unready_night_wound_does_not_block_ready_wounds(self) -> None:
        result = apply_nights_respite_healing(request(injury_state()))

        self.assertFalse(result.state.wounds[3].treated)
        self.assertFalse(result.state.wounds[3].healed)

    def test_completed_calm_night_facts_are_required(self) -> None:
        state = injury_state()
        invalid_values = (
            {"took_it_easy": False},
            {"early_night_completed": False},
            {"morning_has_arrived": False},
        )
        for values in invalid_values:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    opportunity(state, **values)

        with self.assertRaises(ValueError):
            opportunity(replace(state, dead=True))

    def test_request_rejects_stale_target_state_and_repeat(self) -> None:
        valid = request(injury_state())
        invalid_values = (
            {"target_id": "ally"},
            {"injury_state": CharacterInjuryState()},
            {
                "consumed_source_ids": (
                    *valid.consumed_source_ids,
                    valid.opportunity.id,
                )
            },
            {"wound_sequences": (4,)},
        )
        for values in invalid_values:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    replace(valid, **values)

    def test_condition_removal_respects_known_and_external_sources(self) -> None:
        with self.assertRaises(ValueError):
            request(injury_state(), drained_has_other_source=False)

        single = CharacterInjuryState(
            wounds=(
                WoundRecord(
                    1,
                    WoundEntryId.INTERNAL_INJURY,
                    14,
                    (10, 4),
                    treated=True,
                    effect_resolved=True,
                ),
            ),
            conditions=ConditionState({Condition.DRAINED}),
            active_wound_effects=(
                WoundConditionEffect(
                    1,
                    Condition.DRAINED,
                    WoundEffectDuration.UNTIL_HEALED,
                ),
            ),
        )
        source = opportunity(single)
        remove = NightsRespiteHealingRequest(
            "rest:1:remove-drained",
            source,
            "hero",
            single,
            (1,),
            (WoundConditionSourceSnapshot(Condition.DRAINED, False),),
        )
        preserve = replace(
            remove,
            id="rest:1:preserve-drained",
            condition_source_snapshots=(
                WoundConditionSourceSnapshot(Condition.DRAINED, True),
            ),
        )

        removed = apply_nights_respite_healing(remove)
        preserved = apply_nights_respite_healing(preserve)

        self.assertFalse(removed.state.conditions.has(Condition.DRAINED))
        self.assertTrue(preserved.state.conditions.has(Condition.DRAINED))

    def test_resolver_rejects_incomplete_extra_and_unknown_rule(self) -> None:
        state = CharacterInjuryState(
            wounds=(
                WoundRecord(
                    1,
                    WoundEntryId.SHAKING_GRIP,
                    8,
                    (8,),
                    treated=True,
                    effect_resolved=True,
                ),
                WoundRecord(
                    2,
                    WoundEntryId.LEG_SPASM,
                    9,
                    (9,),
                    treated=True,
                    effect_resolved=True,
                ),
                WoundRecord(
                    3,
                    WoundEntryId.SLASHED_FOREARMS,
                    16,
                    (10, 6),
                    treated=True,
                    effect_resolved=True,
                ),
            )
        )
        source = opportunity(state)
        for sequences in ((1,), (1, 2, 3)):
            with self.subTest(sequences=sequences):
                with self.assertRaises(ValueError):
                    apply_nights_respite_healing(
                        NightsRespiteHealingRequest(
                            "rest:1:invalid-selection",
                            source,
                            "hero",
                            state,
                            sequences,
                        )
                    )

        valid = NightsRespiteHealingRequest(
            "rest:1:unknown-rule",
            source,
            "hero",
            state,
            (1, 2),
            rule_id="RULE-HOUSE-001",
        )
        with self.assertRaises(ValueError):
            apply_nights_respite_healing(valid)

    def test_forged_result_is_rejected(self) -> None:
        result = apply_nights_respite_healing(request(injury_state()))
        for values in (
            {"healed_wound_sequences": (1,)},
            {"state": result.previous_state},
            {"removed_effects": ()},
            {"removed_conditions": ()},
            {"consumed_source_ids": (*result.consumed_source_ids, "other")},
            {"applied_rule_ids": (result.rule_id,)},
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    replace(result, **values)


if __name__ == "__main__":
    unittest.main()
