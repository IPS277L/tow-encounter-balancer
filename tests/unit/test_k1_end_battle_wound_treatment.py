from __future__ import annotations

import unittest
from dataclasses import replace

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import (
    CharacterInjuryState,
    WoundConditionEffect,
    WoundEffectDuration,
    WoundEntryId,
    WoundRecord,
    WoundRestriction,
    WoundRestrictionEffect,
)
from towr.domain.recover_models import (
    EndBattleTreatmentContext,
    EndBattleWoundTreatmentRequest,
    RecoverWoundConditionSourceSnapshot,
)
from towr.rules.recover_resolution import (
    apply_end_battle_wound_treatment,
)


def injury_state() -> CharacterInjuryState:
    return CharacterInjuryState(
        wounds=(
            WoundRecord(
                1,
                WoundEntryId.SMASHED_HAND,
                10,
                (10,),
                effect_resolved=True,
            ),
            WoundRecord(
                2,
                WoundEntryId.SUPERFICIAL_INJURY,
                1,
                (1,),
                treated=True,
                effect_resolved=True,
            ),
            WoundRecord(
                3,
                WoundEntryId.BATTERED_LEG,
                5,
                (5,),
                effect_resolved=True,
            ),
        ),
        conditions=ConditionState(
            {Condition.DRAINED, Condition.BLINDED, Condition.PRONE}
        ),
        active_wound_effects=(
            WoundRestrictionEffect(
                1,
                WoundRestriction.USING_INJURED_HAND_CAUSES_CRITICAL,
                WoundEffectDuration.UNTIL_TREATED,
            ),
            WoundConditionEffect(
                1,
                Condition.DRAINED,
                WoundEffectDuration.UNTIL_TREATED,
            ),
            WoundRestrictionEffect(
                1,
                WoundRestriction.ARM_LOST,
                WoundEffectDuration.PERMANENT,
            ),
            WoundConditionEffect(
                2,
                Condition.DRAINED,
                WoundEffectDuration.UNTIL_HEALED,
            ),
            WoundConditionEffect(
                3,
                Condition.BLINDED,
                WoundEffectDuration.UNTIL_TREATED,
            ),
            WoundRestrictionEffect(
                3,
                WoundRestriction.MOVEMENT_IS_DIFFICULT_TERRAIN,
                WoundEffectDuration.UNTIL_TREATED,
            ),
            WoundRestrictionEffect(
                3,
                WoundRestriction.SPEED_IS_SLOW,
                WoundEffectDuration.UNTIL_HEALED,
            ),
        ),
    )


def context(
    *,
    battle_has_ended: bool = True,
    has_chance_to_catch_breath: bool = True,
) -> EndBattleTreatmentContext:
    return EndBattleTreatmentContext(
        id="battle:1:end-treatment:hero",
        battle_id="battle:1",
        target_id="hero",
        battle_has_ended=battle_has_ended,
        has_chance_to_catch_breath=has_chance_to_catch_breath,
    )


def request(
    state: CharacterInjuryState,
    *,
    treatment_context: EndBattleTreatmentContext | None = None,
    has_required_trappings_for_all_wounds: bool = True,
    drained_has_other_source: bool = True,
    blinded_has_other_source: bool = False,
    consumed_context_ids: tuple[str, ...] = (),
) -> EndBattleWoundTreatmentRequest:
    return EndBattleWoundTreatmentRequest(
        id="battle:1:end-treatment:hero:apply",
        context=treatment_context or context(),
        target_id="hero",
        injury_state=state,
        has_required_trappings_for_all_wounds=(
            has_required_trappings_for_all_wounds
        ),
        condition_source_snapshots=(
            RecoverWoundConditionSourceSnapshot(
                Condition.DRAINED,
                drained_has_other_source,
            ),
            RecoverWoundConditionSourceSnapshot(
                Condition.BLINDED,
                blinded_has_other_source,
            ),
        ),
        consumed_context_ids=consumed_context_ids,
    )


class K1EndBattleWoundTreatmentTests(unittest.TestCase):
    def test_treats_every_untreated_wound_without_action_or_test(self) -> None:
        state = injury_state()

        result = apply_end_battle_wound_treatment(request(state))

        self.assertEqual(result.treated_wound_sequences, (1, 3))
        self.assertEqual(result.state.untreated_wounds, 0)
        self.assertEqual(result.state.wounds[1], state.wounds[1])
        self.assertEqual(
            result.removed_effects,
            (
                state.active_wound_effects[0],
                state.active_wound_effects[1],
                state.active_wound_effects[4],
                state.active_wound_effects[5],
            ),
        )
        self.assertEqual(
            result.state.active_wound_effects,
            (
                state.active_wound_effects[2],
                state.active_wound_effects[3],
                state.active_wound_effects[6],
            ),
        )
        self.assertTrue(result.state.conditions.has(Condition.DRAINED))
        self.assertFalse(result.state.conditions.has(Condition.BLINDED))
        self.assertTrue(result.state.conditions.has(Condition.PRONE))
        self.assertEqual(result.removed_conditions, (Condition.BLINDED,))
        self.assertFalse(hasattr(result, "slot"))
        self.assertFalse(hasattr(result, "test_result"))

    def test_consumes_target_scoped_end_battle_context_once(self) -> None:
        treatment_context = context()
        result = apply_end_battle_wound_treatment(
            request(injury_state(), treatment_context=treatment_context)
        )

        self.assertEqual(
            result.consumed_context_ids,
            (treatment_context.id,),
        )
        with self.assertRaises(ValueError):
            request(
                injury_state(),
                treatment_context=treatment_context,
                consumed_context_ids=(treatment_context.id,),
            )

    def test_external_condition_source_preserves_condition(self) -> None:
        result = apply_end_battle_wound_treatment(
            request(injury_state(), blinded_has_other_source=True)
        )

        self.assertTrue(result.state.conditions.has(Condition.BLINDED))
        self.assertEqual(result.removed_conditions, ())

    def test_known_remaining_wound_source_cannot_be_denied(self) -> None:
        with self.assertRaises(ValueError):
            request(injury_state(), drained_has_other_source=False)

    def test_condition_source_snapshot_set_must_be_exact(self) -> None:
        state = injury_state()
        invalid_snapshots = (
            (),
            (
                RecoverWoundConditionSourceSnapshot(
                    Condition.DRAINED,
                    True,
                ),
            ),
            (
                RecoverWoundConditionSourceSnapshot(
                    Condition.DRAINED,
                    True,
                ),
                RecoverWoundConditionSourceSnapshot(
                    Condition.BLINDED,
                    False,
                ),
                RecoverWoundConditionSourceSnapshot(
                    Condition.PRONE,
                    False,
                ),
            ),
        )
        for snapshots in invalid_snapshots:
            with self.subTest(snapshots=snapshots):
                with self.assertRaises(ValueError):
                    EndBattleWoundTreatmentRequest(
                        "battle:1:end-treatment:hero:apply",
                        context(),
                        "hero",
                        state,
                        True,
                        snapshots,
                    )

    def test_completion_breath_tools_and_living_target_are_required(self) -> None:
        state = injury_state()
        invalid_values = (
            {
                "treatment_context": context(battle_has_ended=False),
            },
            {
                "treatment_context": context(
                    has_chance_to_catch_breath=False
                ),
            },
            {"has_required_trappings_for_all_wounds": False},
        )
        for values in invalid_values:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    request(state, **values)

        with self.assertRaises(ValueError):
            request(replace(state, dead=True))
        with self.assertRaises(ValueError):
            EndBattleWoundTreatmentRequest(
                "battle:1:end-treatment:ally:apply",
                context(),
                "ally",
                state,
                True,
            )

    def test_already_treated_state_is_not_a_repeatable_noop(self) -> None:
        state = injury_state()
        treated = replace(
            state,
            wounds=tuple(replace(wound, treated=True) for wound in state.wounds),
        )

        with self.assertRaises(ValueError):
            request(treated)

    def test_unknown_rule_and_forged_result_are_rejected(self) -> None:
        source = request(injury_state())
        with self.assertRaises(ValueError):
            apply_end_battle_wound_treatment(
                replace(source, rule_id="RULE-HOUSE-001")
            )

        result = apply_end_battle_wound_treatment(source)
        for values in (
            {"treated_wound_sequences": (1,)},
            {"state": result.previous_state},
            {"removed_effects": ()},
            {"consumed_context_ids": (*result.consumed_context_ids, "other")},
            {"applied_rule_ids": (result.rule_id,)},
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    replace(result, **values)


if __name__ == "__main__":
    unittest.main()
