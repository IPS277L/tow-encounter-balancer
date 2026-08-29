from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.downtime_models import (
    FESTERING_WOUNDS_RECOVERY_RULE_ID,
    REST_AND_RECOVERY_ENDEAVOUR_RULE_ID,
    RestAndRecoveryEndeavourRequest,
)
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
from towr.domain.test_models import Skill, TestProfile, TestRequest
from towr.domain.wound_healing_models import (
    REST_AND_RECOVERY_HEALING_RULE_ID,
    RestAndRecoveryHealingRequest,
    RestAndRecoveryHealingResult,
)
from towr.rules.downtime_resolution import (
    execute_rest_and_recovery_endeavour,
)
from towr.rules.wound_healing_resolution import (
    apply_rest_and_recovery_healing,
)


def injury_state() -> CharacterInjuryState:
    return CharacterInjuryState(
        wounds=(
            WoundRecord(
                1,
                WoundEntryId.SLASHED_FOREARMS,
                16,
                (10, 6),
                treated=True,
                effect_resolved=True,
            ),
            WoundRecord(
                2,
                WoundEntryId.SHATTERED_KNEE,
                17,
                (10, 7),
                treated=True,
                effect_resolved=True,
            ),
            WoundRecord(
                3,
                WoundEntryId.SEVERED_ARM,
                20,
                (10, 10),
                treated=True,
                effect_resolved=True,
            ),
            WoundRecord(
                4,
                WoundEntryId.INTERNAL_INJURY,
                14,
                (10, 4),
                treated=True,
                effect_resolved=True,
            ),
            WoundRecord(
                5,
                WoundEntryId.BLACKING_OUT,
                19,
                (10, 9),
                effect_resolved=True,
            ),
        ),
        conditions=ConditionState(
            {Condition.DRAINED, Condition.BURDENED, Condition.DEFENCELESS}
        ),
        active_wound_effects=(
            WoundConditionEffect(
                1,
                Condition.DRAINED,
                WoundEffectDuration.UNTIL_HEALED,
            ),
            WoundRestrictionEffect(
                1,
                WoundRestriction.INJURED_ARM_UNUSABLE,
                WoundEffectDuration.UNTIL_HEALED,
            ),
            WoundConditionEffect(
                2,
                Condition.BURDENED,
                WoundEffectDuration.UNTIL_HEALED,
            ),
            WoundRestrictionEffect(
                3,
                WoundRestriction.ARM_LOST,
                WoundEffectDuration.PERMANENT,
            ),
            WoundConditionEffect(
                3,
                Condition.DEFENCELESS,
                WoundEffectDuration.UNTIL_HEALED,
            ),
            WoundConditionEffect(
                4,
                Condition.DRAINED,
                WoundEffectDuration.UNTIL_HEALED,
            ),
        ),
    )


def endeavour_request(
    state: CharacterInjuryState,
    *,
    rule_id: str = REST_AND_RECOVERY_ENDEAVOUR_RULE_ID,
    skill: Skill = Skill.ENDURANCE,
) -> RestAndRecoveryEndeavourRequest:
    return RestAndRecoveryEndeavourRequest(
        id="downtime:1:rest-and-recovery:hero",
        downtime_id="downtime:1",
        target_id="hero",
        injury_state=state,
        endurance_test=TestRequest(
            id="downtime:1:rest-and-recovery:hero:endurance",
            profile=TestProfile(2, 6),
        ),
        skill=skill,
        rule_id=rule_id,
    )


def successful_endeavour(state: CharacterInjuryState):
    return execute_rest_and_recovery_endeavour(
        endeavour_request(state),
        SequenceRandom([3, 9]),
    )


def healing_request(
    state: CharacterInjuryState,
    *,
    wound_sequence: int = 1,
    snapshots: tuple[WoundConditionSourceSnapshot, ...] = (
        WoundConditionSourceSnapshot(Condition.DRAINED, True),
    ),
    consumed_source_ids: tuple[str, ...] = ("prior-source",),
    rule_id: str = REST_AND_RECOVERY_HEALING_RULE_ID,
) -> RestAndRecoveryHealingRequest:
    return RestAndRecoveryHealingRequest(
        id="downtime:1:rest-and-recovery:hero:heal",
        endeavour=successful_endeavour(state),
        target_id="hero",
        injury_state=state,
        wound_sequence=wound_sequence,
        condition_source_snapshots=snapshots,
        consumed_source_ids=consumed_source_ids,
        rule_id=rule_id,
    )


class K1RestAndRecoveryHealingTests(unittest.TestCase):
    def test_success_heals_exactly_one_selected_wound(self) -> None:
        state = injury_state()
        request = healing_request(state)

        result = apply_rest_and_recovery_healing(request)

        self.assertEqual(result.healed_wound_sequence, 1)
        self.assertTrue(result.state.wounds[0].healed)
        self.assertFalse(result.state.wounds[1].healed)
        self.assertFalse(result.state.wounds[2].healed)
        self.assertEqual(
            result.removed_effects,
            state.active_wound_effects[:2],
        )
        self.assertEqual(
            result.state.active_wound_effects,
            state.active_wound_effects[2:],
        )
        self.assertTrue(result.state.conditions.has(Condition.DRAINED))
        self.assertTrue(result.state.conditions.has(Condition.BURDENED))
        self.assertTrue(result.state.conditions.has(Condition.DEFENCELESS))
        self.assertEqual(
            result.consumed_source_ids,
            ("prior-source", request.endeavour.request_id),
        )
        self.assertIn(request.rule_id, result.applied_rule_ids)
        self.assertIn(
            REST_AND_RECOVERY_ENDEAVOUR_RULE_ID,
            result.applied_rule_ids,
        )

    def test_success_also_requests_all_festering_wounds_recovery(self) -> None:
        state = injury_state()

        result = successful_endeavour(state)

        self.assertTrue(result.succeeded)
        self.assertEqual(result.test_result.successes, 1)
        follow_up = result.festering_wounds_recovery
        self.assertIsNotNone(follow_up)
        assert follow_up is not None
        self.assertEqual(follow_up.target_id, "hero")
        self.assertEqual(follow_up.source_endeavour_id, result.request_id)
        self.assertEqual(
            follow_up.source_test_id,
            result.source_request.endurance_test.id,
        )
        self.assertEqual(follow_up.rule_id, FESTERING_WOUNDS_RECOVERY_RULE_ID)

    def test_failed_endeavour_creates_no_healing_source(self) -> None:
        state = injury_state()
        result = execute_rest_and_recovery_endeavour(
            endeavour_request(state),
            SequenceRandom([8, 9]),
        )

        self.assertFalse(result.succeeded)
        self.assertIsNone(result.festering_wounds_recovery)
        with self.assertRaisesRegex(ValueError, "successful Endeavour"):
            RestAndRecoveryHealingRequest(
                id="failed:heal",
                endeavour=result,
                target_id="hero",
                injury_state=state,
                wound_sequence=1,
                condition_source_snapshots=(
                    WoundConditionSourceSnapshot(Condition.DRAINED, True),
                ),
            )

    def test_all_and_only_table_rows_16_to_19_are_eligible(self) -> None:
        entries = (
            WoundEntryId.SLASHED_FOREARMS,
            WoundEntryId.SHATTERED_KNEE,
            WoundEntryId.SPILLING_GUTS,
            WoundEntryId.BLACKING_OUT,
        )
        for index, (entry_id, total) in enumerate(
            zip(entries, range(16, 20), strict=True),
            start=1,
        ):
            with self.subTest(total=total):
                state = CharacterInjuryState(
                    wounds=(
                        WoundRecord(
                            1,
                            entry_id,
                            total,
                            (10, total - 10),
                            treated=True,
                            effect_resolved=True,
                        ),
                    )
                )
                request = RestAndRecoveryHealingRequest(
                    id=f"heal:{index}",
                    endeavour=successful_endeavour(state),
                    target_id="hero",
                    injury_state=state,
                    wound_sequence=1,
                )
                self.assertTrue(
                    apply_rest_and_recovery_healing(request).state.wounds[0].healed
                )

        for entry_id, total in (
            (WoundEntryId.INTERNAL_INJURY, 14),
            (WoundEntryId.SEVERED_ARM, 20),
        ):
            with self.subTest(rejected_total=total):
                state = CharacterInjuryState(
                    wounds=(
                        WoundRecord(
                            1,
                            entry_id,
                            total,
                            (10, total - 10),
                            treated=True,
                            effect_resolved=True,
                        ),
                    )
                )
                request = RestAndRecoveryHealingRequest(
                    id=f"reject:{total}",
                    endeavour=successful_endeavour(state),
                    target_id="hero",
                    injury_state=state,
                    wound_sequence=1,
                )
                message = (
                    "surgery proof" if total == 20 else "eligible Wound"
                )
                with self.assertRaisesRegex(ValueError, message):
                    apply_rest_and_recovery_healing(request)

    def test_selected_wound_must_be_ready_and_source_must_be_current(self) -> None:
        state = injury_state()
        source = successful_endeavour(state)

        with self.assertRaisesRegex(ValueError, "treated Wound"):
            RestAndRecoveryHealingRequest(
                id="untreated",
                endeavour=source,
                target_id="hero",
                injury_state=state,
                wound_sequence=5,
            )
        with self.assertRaisesRegex(ValueError, "stale Endeavour"):
            RestAndRecoveryHealingRequest(
                id="stale",
                endeavour=source,
                target_id="hero",
                injury_state=replace(state, conditions=ConditionState()),
                wound_sequence=1,
            )
        with self.assertRaisesRegex(ValueError, "another healing target"):
            RestAndRecoveryHealingRequest(
                id="wrong-target",
                endeavour=source,
                target_id="ally",
                injury_state=state,
                wound_sequence=1,
            )
        with self.assertRaisesRegex(ValueError, "already consumed"):
            RestAndRecoveryHealingRequest(
                id="repeat",
                endeavour=source,
                target_id="hero",
                injury_state=state,
                wound_sequence=1,
                condition_source_snapshots=(
                    WoundConditionSourceSnapshot(Condition.DRAINED, True),
                ),
                consumed_source_ids=(source.request_id,),
            )

    def test_condition_is_removed_only_without_another_source(self) -> None:
        state = CharacterInjuryState(
            wounds=(
                WoundRecord(
                    1,
                    WoundEntryId.SHATTERED_KNEE,
                    17,
                    (10, 7),
                    treated=True,
                    effect_resolved=True,
                ),
            ),
            conditions=ConditionState({Condition.BURDENED}),
            active_wound_effects=(
                WoundConditionEffect(
                    1,
                    Condition.BURDENED,
                    WoundEffectDuration.UNTIL_HEALED,
                ),
            ),
        )
        request = RestAndRecoveryHealingRequest(
            id="heal:knee",
            endeavour=successful_endeavour(state),
            target_id="hero",
            injury_state=state,
            wound_sequence=1,
            condition_source_snapshots=(
                WoundConditionSourceSnapshot(Condition.BURDENED, False),
            ),
        )

        result = apply_rest_and_recovery_healing(request)

        self.assertEqual(result.removed_conditions, (Condition.BURDENED,))
        self.assertFalse(result.state.conditions.has(Condition.BURDENED))

    def test_unknown_rules_and_non_endurance_skill_are_rejected(self) -> None:
        state = injury_state()
        with self.assertRaisesRegex(ValueError, "Endurance Test"):
            endeavour_request(state, skill=Skill.RECALL)

        request = endeavour_request(state, rule_id="HOUSE:rest")
        with self.assertRaisesRegex(ValueError, "unknown source rule"):
            execute_rest_and_recovery_endeavour(
                request,
                SequenceRandom([3, 9]),
            )

        healing = healing_request(state, rule_id="HOUSE:healing")
        with self.assertRaisesRegex(ValueError, "unknown healing rule"):
            apply_rest_and_recovery_healing(healing)

    def test_forged_healing_result_is_rejected(self) -> None:
        state = injury_state()
        result = apply_rest_and_recovery_healing(healing_request(state))

        with self.assertRaisesRegex(ValueError, "unrelated injury state"):
            replace(result, state=state)
        with self.assertRaisesRegex(ValueError, "trace is incomplete"):
            RestAndRecoveryHealingResult(
                request_id=result.request_id,
                rule_id=result.rule_id,
                source_request=result.source_request,
                target_id=result.target_id,
                healed_wound_sequence=result.healed_wound_sequence,
                previous_state=result.previous_state,
                state=result.state,
                removed_effects=result.removed_effects,
                removed_conditions=result.removed_conditions,
                previous_consumed_source_ids=("prior-source",),
                consumed_source_ids=result.consumed_source_ids,
                applied_rule_ids=(result.rule_id,),
            )


if __name__ == "__main__":
    unittest.main()
