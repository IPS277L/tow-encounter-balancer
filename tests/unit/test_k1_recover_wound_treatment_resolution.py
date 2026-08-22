from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from tests.unit.test_k1_recover_resolution import (
    active_round,
    recover_request,
    reserve_action,
    self_target,
)
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
from towr.domain.magic_models import WizardMagicState
from towr.domain.recover_models import (
    RecoverMode,
    RecoverStandardChoice,
    RecoverTreatWoundChoice,
    RecoverWoundConditionSourceSnapshot,
    RecoverWoundTreatmentResolutionRequest,
)
from towr.domain.test_models import TestProfile, TestRequest
from towr.domain.turn_models import CombatActionKind
from towr.rules.recover_resolution import (
    apply_recover_wound_treatment,
    execute_recover_action,
)


def injury_state(
    *,
    include_condition: bool = True,
    include_other_condition_source: bool = False,
) -> CharacterInjuryState:
    conditions = (
        ConditionState({Condition.DRAINED, Condition.PRONE})
        if include_condition
        else ConditionState({Condition.PRONE})
    )
    effects = [
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
        WoundRestrictionEffect(
            2,
            WoundRestriction.MOVEMENT_IS_DIFFICULT_TERRAIN,
            WoundEffectDuration.UNTIL_TREATED,
        ),
    ]
    if include_other_condition_source:
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
                WoundEntryId.SMASHED_HAND,
                10,
                (10,),
                effect_resolved=True,
            ),
            WoundRecord(
                2,
                WoundEntryId.BATTERED_LEG,
                5,
                (5,),
                effect_resolved=True,
            ),
        ),
        conditions=conditions,
        active_wound_effects=tuple(effects),
    )


def successful_recover(
    injury: CharacterInjuryState,
    *,
    automatic: bool = True,
):
    state = reserve_action(active_round(), CombatActionKind.RECOVER)
    choice = RecoverTreatWoundChoice(
        target=self_target(injury.conditions),
        injury_state=injury,
        wound_sequence=1,
        has_required_trappings=True,
        recall_test=(
            None
            if automatic
            else TestRequest("recover:recall", TestProfile(2, 5))
        ),
        automatic_lore_id="lore:anatomy" if automatic else None,
    )
    return execute_recover_action(
        recover_request(
            state,
            actor_conditions=injury.conditions,
            mode=RecoverMode.TREAT_WOUND,
            choice=choice,
        ),
        SequenceRandom([] if automatic else [1, 10]),
    )


def application_request(
    injury: CharacterInjuryState,
    *,
    automatic: bool = True,
    has_other_source: bool = False,
    consumed: tuple[str, ...] = (),
) -> RecoverWoundTreatmentResolutionRequest:
    snapshots = ()
    if injury.conditions.has(Condition.DRAINED):
        snapshots = (
            RecoverWoundConditionSourceSnapshot(
                Condition.DRAINED,
                has_other_source,
            ),
        )
    return RecoverWoundTreatmentResolutionRequest(
        id="recover:treatment:apply",
        recover=successful_recover(injury, automatic=automatic),
        target_id="hero",
        injury_state=injury,
        condition_source_snapshots=snapshots,
        consumed_application_ids=consumed,
    )


class K1RecoverWoundTreatmentResolutionTests(unittest.TestCase):
    def test_treatment_marks_only_selected_wound_and_removes_until_treated(
        self,
    ) -> None:
        injury = injury_state()
        request = application_request(injury, automatic=False)

        result = apply_recover_wound_treatment(request)

        self.assertTrue(result.state.wounds[0].treated)
        self.assertFalse(result.state.wounds[1].treated)
        self.assertEqual(result.state.untreated_wounds, 1)
        self.assertFalse(result.state.conditions.has(Condition.DRAINED))
        self.assertTrue(result.state.conditions.has(Condition.PRONE))
        self.assertEqual(
            result.removed_effects,
            injury.active_wound_effects[:2],
        )
        self.assertEqual(result.removed_conditions, (Condition.DRAINED,))
        self.assertEqual(
            result.state.active_wound_effects,
            injury.active_wound_effects[2:],
        )
        treatment = request.recover.resolution.treatment
        assert treatment is not None
        self.assertEqual(result.consumed_application_ids, (treatment.id,))
        self.assertIs(
            result.source_request.recover.slot.execution,
            request.recover.slot.execution,
        )

    def test_automatic_lore_application_uses_the_same_transition(self) -> None:
        injury = injury_state(include_condition=False)

        result = apply_recover_wound_treatment(application_request(injury))

        self.assertTrue(result.state.wounds[0].treated)
        self.assertEqual(result.removed_conditions, ())
        self.assertEqual(result.state.conditions, injury.conditions)

    def test_explicit_external_source_preserves_condition(self) -> None:
        injury = injury_state()

        result = apply_recover_wound_treatment(
            application_request(injury, has_other_source=True)
        )

        self.assertTrue(result.state.conditions.has(Condition.DRAINED))
        self.assertEqual(result.removed_conditions, ())
        self.assertNotIn(
            injury.active_wound_effects[1],
            result.state.active_wound_effects,
        )

    def test_known_other_wound_source_must_preserve_condition(self) -> None:
        injury = injury_state(include_other_condition_source=True)
        with self.assertRaises(ValueError):
            application_request(injury, has_other_source=False)

        result = apply_recover_wound_treatment(
            application_request(injury, has_other_source=True)
        )
        self.assertTrue(result.state.conditions.has(Condition.DRAINED))
        self.assertIn(
            injury.active_wound_effects[-1],
            result.state.active_wound_effects,
        )

    def test_condition_source_snapshot_set_must_be_exact(self) -> None:
        injury = injury_state()
        recover = successful_recover(injury)
        for snapshots in (
            (),
            (
                RecoverWoundConditionSourceSnapshot(
                    Condition.DRAINED,
                    False,
                ),
                RecoverWoundConditionSourceSnapshot(
                    Condition.PRONE,
                    False,
                ),
            ),
        ):
            with self.subTest(snapshots=snapshots):
                with self.assertRaises(ValueError):
                    RecoverWoundTreatmentResolutionRequest(
                        "recover:treatment:apply",
                        recover,
                        "hero",
                        injury,
                        snapshots,
                    )

    def test_stale_state_and_repeat_consumption_are_rejected(self) -> None:
        injury = injury_state()
        recover = successful_recover(injury)
        treatment = recover.resolution.treatment
        assert treatment is not None
        with self.assertRaises(ValueError):
            RecoverWoundTreatmentResolutionRequest(
                "recover:treatment:apply",
                recover,
                "ally",
                injury,
                (
                    RecoverWoundConditionSourceSnapshot(
                        Condition.DRAINED,
                        False,
                    ),
                ),
            )
        with self.assertRaises(ValueError):
            RecoverWoundTreatmentResolutionRequest(
                "recover:treatment:apply",
                recover,
                "hero",
                replace(injury, dead=True),
                (
                    RecoverWoundConditionSourceSnapshot(
                        Condition.DRAINED,
                        False,
                    ),
                ),
            )
        with self.assertRaises(ValueError):
            application_request(injury, consumed=(treatment.id,))

    def test_non_treatment_and_failed_treatment_cannot_be_applied(self) -> None:
        injury = injury_state()
        state = reserve_action(active_round(), CombatActionKind.RECOVER)
        standard = execute_recover_action(
            recover_request(
                state,
                actor_conditions=injury.conditions,
                mode=RecoverMode.STANDARD,
                choice=RecoverStandardChoice(magic_state=WizardMagicState()),
            ),
            SequenceRandom([]),
        )
        with self.assertRaises(ValueError):
            RecoverWoundTreatmentResolutionRequest(
                "recover:treatment:apply",
                standard,
                "hero",
                injury,
            )

        failed_choice = RecoverTreatWoundChoice(
            target=self_target(injury.conditions),
            injury_state=injury,
            wound_sequence=1,
            has_required_trappings=True,
            recall_test=TestRequest("recover:recall", TestProfile(1, 5)),
        )
        failed = execute_recover_action(
            recover_request(
                state,
                actor_conditions=injury.conditions,
                mode=RecoverMode.TREAT_WOUND,
                choice=failed_choice,
            ),
            SequenceRandom([10]),
        )
        with self.assertRaises(ValueError):
            RecoverWoundTreatmentResolutionRequest(
                "recover:treatment:apply",
                failed,
                "hero",
                injury,
            )

    def test_result_rejects_forged_transition_consumption_and_trace(self) -> None:
        result = apply_recover_wound_treatment(
            application_request(injury_state())
        )
        forged_values = (
            {"state": result.previous_state},
            {"removed_effects": ()},
            {
                "consumed_application_ids": (
                    *result.consumed_application_ids,
                    "other",
                )
            },
            {"applied_rule_ids": (result.rule_id,)},
        )
        for values in forged_values:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    replace(result, **values)


if __name__ == "__main__":
    unittest.main()
