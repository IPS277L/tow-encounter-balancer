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
from towr.domain.combat_surgeon_models import (
    COMBAT_SURGEON_RULE_ID,
    CombatSurgeonSuppressionDuration,
    CombatSurgeonTreatmentRequest,
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
from towr.domain.recover_models import (
    RecoverMode,
    RecoverTreatWoundChoice,
    RecoverWoundConditionSourceSnapshot,
    RecoverWoundTreatmentResolutionRequest,
)
from towr.domain.test_models import Skill, TestProfile, TestRequest
from towr.domain.turn_models import CombatActionKind
from towr.rules.combat_surgeon_resolution import (
    resolve_combat_surgeon_treatment,
)
from towr.rules.recover_resolution import (
    apply_recover_wound_treatment,
    execute_recover_action,
)


def untreated_state(*, with_until_healed: bool = True) -> CharacterInjuryState:
    effects = [
        WoundConditionEffect(
            1,
            Condition.CRITICALLY_INJURED,
            WoundEffectDuration.UNTIL_TREATED,
        ),
    ]
    conditions = {Condition.CRITICALLY_INJURED}
    if with_until_healed:
        effects.extend(
            (
                WoundConditionEffect(
                    1,
                    Condition.BURDENED,
                    WoundEffectDuration.UNTIL_HEALED,
                ),
                WoundConditionEffect(
                    1,
                    Condition.DRAINED,
                    WoundEffectDuration.UNTIL_HEALED,
                ),
                WoundRestrictionEffect(
                    1,
                    WoundRestriction.MOVEMENT_IS_DIFFICULT_TERRAIN,
                    WoundEffectDuration.PERMANENT,
                ),
                WoundConditionEffect(
                    2,
                    Condition.BURDENED,
                    WoundEffectDuration.UNTIL_HEALED,
                ),
            )
        )
        conditions.update((Condition.BURDENED, Condition.DRAINED))
    return CharacterInjuryState(
        wounds=(
            WoundRecord(
                1,
                WoundEntryId.SPILLING_GUTS,
                18,
                (10, 8),
                effect_resolved=True,
            ),
            WoundRecord(
                2,
                WoundEntryId.INTERNAL_INJURY,
                9,
                (9,),
                treated=True,
                effect_resolved=True,
            ),
        ),
        conditions=ConditionState(conditions),
        active_wound_effects=tuple(effects),
    )


def completed_treatment(
    initial: CharacterInjuryState,
):
    round_state = reserve_action(active_round(), CombatActionKind.RECOVER)
    choice = RecoverTreatWoundChoice(
        target=self_target(initial.conditions),
        injury_state=initial,
        wound_sequence=1,
        has_required_trappings=True,
        automatic_lore_id="lore:anatomy",
    )
    recover = execute_recover_action(
        recover_request(
            round_state,
            actor_conditions=initial.conditions,
            mode=RecoverMode.TREAT_WOUND,
            choice=choice,
        ),
        SequenceRandom([]),
    )
    application = RecoverWoundTreatmentResolutionRequest(
        id="recover:treatment:apply",
        recover=recover,
        target_id="hero",
        injury_state=initial,
        condition_source_snapshots=(
            RecoverWoundConditionSourceSnapshot(
                Condition.CRITICALLY_INJURED,
                False,
            ),
        ),
    )
    return apply_recover_wound_treatment(application)


def combat_surgeon_request(
    treatment,
    **changes,
) -> CombatSurgeonTreatmentRequest:
    values = {
        "id": "battle:1:combat-surgeon:hero:1",
        "battle_id": "battle:1",
        "treatment": treatment,
        "surgeon_id": "hero",
        "target_id": "hero",
        "injury_state": treatment.state,
        "recall_test": TestRequest(
            "battle:1:combat-surgeon:hero:1:recall",
            TestProfile(2, 5),
        ),
        "surgeon_has_combat_surgeon": True,
    }
    values.update(changes)
    return CombatSurgeonTreatmentRequest(**values)


class K1CombatSurgeonTreatmentTests(unittest.TestCase):
    def test_success_suppresses_all_until_healed_effects_of_selected_wound(
        self,
    ) -> None:
        treatment = completed_treatment(untreated_state())
        request = combat_surgeon_request(
            treatment,
            consumed_treatment_result_ids=("earlier:treatment",),
        )

        result = resolve_combat_surgeon_treatment(
            request,
            SequenceRandom([1, 10]),
        )

        self.assertTrue(result.succeeded)
        suppression = result.suppression
        assert suppression is not None
        self.assertEqual(
            suppression.suppressed_effects,
            treatment.state.active_wound_effects[:2],
        )
        self.assertEqual(suppression.battle_id, "battle:1")
        self.assertEqual(suppression.wound_sequence, 1)
        self.assertEqual(suppression.wound, treatment.state.wounds[0])
        self.assertIs(
            suppression.duration,
            CombatSurgeonSuppressionDuration.REST_OF_BATTLE,
        )
        self.assertEqual(
            result.consumed_treatment_result_ids,
            ("earlier:treatment", treatment.request_id),
        )
        self.assertIn(COMBAT_SURGEON_RULE_ID, result.applied_rule_ids)

    def test_suppression_does_not_heal_or_remove_effect_provenance(self) -> None:
        treatment = completed_treatment(untreated_state())

        result = resolve_combat_surgeon_treatment(
            combat_surgeon_request(treatment),
            SequenceRandom([1, 10]),
        )

        self.assertIs(result.previous_state, treatment.state)
        self.assertIs(result.state, treatment.state)
        self.assertFalse(result.state.wounds[0].healed)
        self.assertEqual(
            result.state.active_wound_effects,
            treatment.state.active_wound_effects,
        )
        self.assertTrue(result.state.conditions.has(Condition.BURDENED))
        self.assertTrue(result.state.conditions.has(Condition.DRAINED))

    def test_failure_creates_no_suppression_but_consumes_trigger(self) -> None:
        treatment = completed_treatment(untreated_state())

        result = resolve_combat_surgeon_treatment(
            combat_surgeon_request(treatment),
            SequenceRandom([8, 10]),
        )

        self.assertFalse(result.succeeded)
        self.assertIsNone(result.suppression)
        self.assertIs(result.state, treatment.state)
        self.assertEqual(
            result.consumed_treatment_result_ids,
            (treatment.request_id,),
        )

    def test_only_selected_wound_until_healed_effects_are_suppressed(self) -> None:
        treatment = completed_treatment(untreated_state())
        result = resolve_combat_surgeon_treatment(
            combat_surgeon_request(treatment),
            SequenceRandom([1, 10]),
        )
        suppression = result.suppression
        assert suppression is not None

        self.assertNotIn(
            treatment.state.active_wound_effects[2],
            suppression.suppressed_effects,
        )
        self.assertNotIn(
            treatment.state.active_wound_effects[3],
            suppression.suppressed_effects,
        )

    def test_talent_ownership_recall_skill_and_distinct_test_are_required(
        self,
    ) -> None:
        treatment = completed_treatment(untreated_state())
        application = treatment.source_request.recover.resolution.treatment
        assert application is not None
        invalid = (
            {"surgeon_has_combat_surgeon": False},
            {"recall_skill": Skill.AWARENESS},
            {
                "recall_test": TestRequest(
                    application.source_test_id or "recover:recall",
                    TestProfile(2, 5),
                )
            },
        )
        for changes in invalid:
            with self.subTest(changes=changes):
                if application.source_test_id is None and "recall_test" in changes:
                    continue
                with self.assertRaises(ValueError):
                    combat_surgeon_request(treatment, **changes)

        nonautomatic_initial = untreated_state()
        round_state = reserve_action(active_round(), CombatActionKind.RECOVER)
        recover = execute_recover_action(
            recover_request(
                round_state,
                actor_conditions=nonautomatic_initial.conditions,
                mode=RecoverMode.TREAT_WOUND,
                choice=RecoverTreatWoundChoice(
                    target=self_target(nonautomatic_initial.conditions),
                    injury_state=nonautomatic_initial,
                    wound_sequence=1,
                    has_required_trappings=True,
                    recall_test=TestRequest(
                        "recover:recall",
                        TestProfile(2, 5),
                    ),
                ),
            ),
            SequenceRandom([1, 10]),
        )
        nonautomatic_treatment = apply_recover_wound_treatment(
            RecoverWoundTreatmentResolutionRequest(
                "recover:nonautomatic:apply",
                recover,
                "hero",
                nonautomatic_initial,
                (
                    RecoverWoundConditionSourceSnapshot(
                        Condition.CRITICALLY_INJURED,
                        False,
                    ),
                ),
            )
        )
        with self.assertRaises(ValueError):
            combat_surgeon_request(
                nonautomatic_treatment,
                recall_test=TestRequest("recover:recall", TestProfile(2, 5)),
            )

    def test_exact_surgeon_target_state_and_single_use_are_required(self) -> None:
        treatment = completed_treatment(untreated_state())
        stale = replace(treatment.state, dead=True)
        invalid = (
            {"surgeon_id": "other"},
            {"target_id": "ally"},
            {"injury_state": stale},
            {"consumed_treatment_result_ids": (treatment.request_id,)},
        )
        for changes in invalid:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    combat_surgeon_request(treatment, **changes)

    def test_wound_requires_an_active_until_healed_effect(self) -> None:
        treatment = completed_treatment(untreated_state(with_until_healed=False))

        with self.assertRaises(ValueError):
            combat_surgeon_request(treatment)

    def test_unknown_rule_is_rejected_before_rng(self) -> None:
        treatment = completed_treatment(untreated_state())
        request = combat_surgeon_request(treatment, rule_id="RULE:wrong")

        with self.assertRaises(ValueError):
            resolve_combat_surgeon_treatment(request, SequenceRandom([]))

    def test_forged_suppression_and_state_are_rejected(self) -> None:
        treatment = completed_treatment(untreated_state())
        result = resolve_combat_surgeon_treatment(
            combat_surgeon_request(treatment),
            SequenceRandom([1, 10]),
        )
        assert result.suppression is not None

        with self.assertRaises(ValueError):
            replace(
                result,
                suppression=replace(result.suppression, battle_id="battle:2"),
            )
        with self.assertRaises(ValueError):
            replace(result, state=replace(result.state, dead=True))


if __name__ == "__main__":
    unittest.main()
