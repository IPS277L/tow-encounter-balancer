from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import (
    CharacterInjuryState,
    CharacterWoundRequest,
    WoundConditionEffect,
    WoundConditionSourceSnapshot,
    WoundEffectDuration,
    WoundEntryId,
    WoundRecord,
    WoundRestriction,
    WoundRestrictionEffect,
)
from towr.domain.recover_models import (
    EndBattleTreatmentContext,
    EndBattleWoundTreatmentRequest,
)
from towr.domain.wound_healing_models import (
    CatchYourBreathHealingRequest,
)
from towr.rules.injury_resolution import resolve_character_wound
from towr.rules.recover_resolution import apply_end_battle_wound_treatment
from towr.rules.wound_healing_resolution import (
    apply_catch_your_breath_healing,
)


def injury_state(
    *,
    historical_healed: bool = True,
    same_condition_source: bool = False,
) -> CharacterInjuryState:
    effects = [
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
            Condition.BLINDED,
            WoundEffectDuration.UNTIL_HEALED,
        ),
        WoundRestrictionEffect(
            2,
            WoundRestriction.CANNOT_AIM,
            WoundEffectDuration.UNTIL_HEALED,
        ),
    ]
    if same_condition_source:
        effects.append(
            WoundConditionEffect(
                2,
                Condition.DRAINED,
                WoundEffectDuration.UNTIL_HEALED,
            )
        )
    return CharacterInjuryState(
        wounds=(
            WoundRecord(
                1,
                WoundEntryId.GASHED_BROW,
                7,
                (7,),
                effect_resolved=True,
            ),
            WoundRecord(
                2,
                WoundEntryId.SHAKING_GRIP,
                8,
                (8,),
                effect_resolved=True,
            ),
            WoundRecord(
                3,
                WoundEntryId.SUPERFICIAL_INJURY,
                1,
                (1,),
                treated=historical_healed,
                effect_resolved=True,
                healed=historical_healed,
            ),
        ),
        conditions=ConditionState(
            {Condition.DRAINED, Condition.BLINDED, Condition.PRONE}
        ),
        active_wound_effects=tuple(effects),
    )


def treatment_result(state: CharacterInjuryState):
    context = EndBattleTreatmentContext(
        id="battle:1:end-treatment:hero",
        battle_id="battle:1",
        target_id="hero",
        battle_has_ended=True,
        has_chance_to_catch_breath=True,
    )
    request = EndBattleWoundTreatmentRequest(
        id="battle:1:end-treatment:hero:apply",
        context=context,
        target_id="hero",
        injury_state=state,
        has_required_trappings_for_all_wounds=True,
    )
    return apply_end_battle_wound_treatment(request)


def healing_request(
    state: CharacterInjuryState,
    *,
    wound_sequences: tuple[int, ...] = (1,),
    drained_has_other_source: bool = False,
    consumed_source_ids: tuple[str, ...] = (),
    rule_id: str | None = None,
) -> CatchYourBreathHealingRequest:
    treatment = treatment_result(state)
    values = {
        "id": "battle:1:catch-breath:hero",
        "treatment": treatment,
        "target_id": "hero",
        "injury_state": treatment.state,
        "wound_sequences": wound_sequences,
        "condition_source_snapshots": (
            WoundConditionSourceSnapshot(
                Condition.DRAINED,
                drained_has_other_source,
            ),
        ),
        "consumed_source_ids": consumed_source_ids,
    }
    if rule_id is not None:
        values["rule_id"] = rule_id
    return CatchYourBreathHealingRequest(**values)


class K1CatchYourBreathHealingTests(unittest.TestCase):
    def test_heals_exact_category_and_ends_all_nonpermanent_effects(self) -> None:
        state = injury_state()
        source = healing_request(state)

        result = apply_catch_your_breath_healing(source)

        self.assertEqual(result.healed_wound_sequences, (1,))
        self.assertTrue(result.state.wounds[0].healed)
        self.assertTrue(result.state.wounds[0].treated)
        self.assertFalse(result.state.wounds[1].healed)
        self.assertEqual(result.state.wounds[2], state.wounds[2])
        self.assertEqual(
            tuple(wound.sequence for wound in result.state.wounds),
            (1, 2, 3),
        )
        self.assertEqual(result.state.active_wounds, 1)
        self.assertEqual(
            result.removed_effects,
            source.injury_state.active_wound_effects[:2],
        )
        self.assertEqual(
            result.state.active_wound_effects,
            source.injury_state.active_wound_effects[2:],
        )
        self.assertFalse(result.state.conditions.has(Condition.DRAINED))
        self.assertTrue(result.state.conditions.has(Condition.BLINDED))
        self.assertTrue(result.state.conditions.has(Condition.PRONE))
        self.assertEqual(result.removed_conditions, (Condition.DRAINED,))
        self.assertEqual(
            result.consumed_source_ids,
            (source.treatment.request_id,),
        )
        self.assertFalse(hasattr(result, "slot"))
        self.assertFalse(hasattr(result, "test_result"))

    def test_healed_history_does_not_add_wound_table_dice(self) -> None:
        state = CharacterInjuryState(
            wounds=(
                WoundRecord(
                    1,
                    WoundEntryId.SUPERFICIAL_INJURY,
                    1,
                    (1,),
                    treated=True,
                    effect_resolved=True,
                    healed=True,
                ),
                WoundRecord(
                    2,
                    WoundEntryId.SHAKING_GRIP,
                    8,
                    (8,),
                    effect_resolved=True,
                ),
            )
        )

        result = resolve_character_wound(
            CharacterWoundRequest("next-wound", state),
            SequenceRandom([4, 5]),
        )

        self.assertEqual(state.active_wounds, 1)
        self.assertEqual(state.untreated_wounds, 1)
        self.assertEqual(result.table_roll.dice, 2)
        self.assertEqual(result.state.wounds[-1].sequence, 3)

    def test_known_remaining_condition_source_must_be_preserved(self) -> None:
        state = injury_state(same_condition_source=True)

        with self.assertRaises(ValueError):
            healing_request(state)

        result = apply_catch_your_breath_healing(
            healing_request(state, drained_has_other_source=True)
        )
        self.assertTrue(result.state.conditions.has(Condition.DRAINED))
        self.assertEqual(result.removed_conditions, ())

    def test_external_condition_source_can_preserve_condition(self) -> None:
        result = apply_catch_your_breath_healing(
            healing_request(
                injury_state(),
                drained_has_other_source=True,
            )
        )

        self.assertTrue(result.state.conditions.has(Condition.DRAINED))
        self.assertEqual(result.removed_conditions, ())

    def test_request_requires_exact_fresh_post_treatment_state(self) -> None:
        state = injury_state()
        treatment = treatment_result(state)
        valid = healing_request(state)
        invalid_values = (
            {"target_id": "ally"},
            {"injury_state": state},
            {
                "consumed_source_ids": (treatment.request_id,),
            },
        )
        for values in invalid_values:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    replace(valid, **values)

        unresolved = replace(
            treatment.state,
            wounds=(
                replace(treatment.state.wounds[0], effect_resolved=False),
                *treatment.state.wounds[1:],
            ),
        )
        with self.assertRaises(ValueError):
            replace(valid, injury_state=unresolved)

    def test_resolver_requires_every_and_only_catch_your_breath_wound(self) -> None:
        with self.assertRaises(ValueError):
            apply_catch_your_breath_healing(
                healing_request(injury_state(), wound_sequences=(1, 2))
            )

        two_eligible = injury_state(historical_healed=False)
        with self.assertRaises(ValueError):
            apply_catch_your_breath_healing(
                healing_request(two_eligible, wound_sequences=(1,))
            )

        with self.assertRaises(ValueError):
            apply_catch_your_breath_healing(
                healing_request(
                    injury_state(),
                    rule_id="RULE-HOUSE-001",
                )
            )

    def test_healed_wound_state_invariants_are_enforced(self) -> None:
        with self.assertRaises(ValueError):
            WoundRecord(
                1,
                WoundEntryId.SUPERFICIAL_INJURY,
                1,
                (1,),
                effect_resolved=True,
                healed=True,
            )
        with self.assertRaises(ValueError):
            WoundRecord(
                1,
                WoundEntryId.SUPERFICIAL_INJURY,
                1,
                (1,),
                treated=True,
                healed=True,
            )
        healed = WoundRecord(
            1,
            WoundEntryId.SUPERFICIAL_INJURY,
            1,
            (1,),
            treated=True,
            effect_resolved=True,
            healed=True,
        )
        with self.assertRaises(ValueError):
            CharacterInjuryState(
                wounds=(healed,),
                active_wound_effects=(
                    WoundRestrictionEffect(
                        1,
                        WoundRestriction.CANNOT_AIM,
                        WoundEffectDuration.UNTIL_HEALED,
                    ),
                ),
            )

    def test_forged_result_is_rejected(self) -> None:
        result = apply_catch_your_breath_healing(
            healing_request(injury_state())
        )
        for values in (
            {"healed_wound_sequences": (2,)},
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
