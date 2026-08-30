from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from tests.unit.test_k1_combat_surgeon_treatment import (
    combat_surgeon_request,
    completed_treatment,
    untreated_state,
)
from towr.domain.combat_surgeon_suppression_models import (
    COMBAT_SURGEON_EFFECTIVE_EFFECTS_RULE_ID,
    COMBAT_SURGEON_SUPPRESSION_REGISTRATION_RULE_ID,
    CombatSurgeonEffectiveEffectsRequest,
    CombatSurgeonSuppressionAggregate,
    CombatSurgeonSuppressionRegistrationRequest,
)
from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundConditionSourceSnapshot, WoundEntryId
from towr.rules.combat_surgeon_resolution import (
    resolve_combat_surgeon_treatment,
)
from towr.rules.combat_surgeon_suppression_resolution import (
    register_combat_surgeon_suppression,
    resolve_combat_surgeon_effective_effects,
)


def successful_source():
    treatment = completed_treatment(untreated_state())
    return resolve_combat_surgeon_treatment(
        combat_surgeon_request(treatment),
        SequenceRandom([1, 10]),
    )


def registered_source():
    source = successful_source()
    registration = register_combat_surgeon_suppression(
        CombatSurgeonSuppressionRegistrationRequest(
            id="battle:1:suppression:register",
            aggregate=CombatSurgeonSuppressionAggregate("battle:1"),
            source=source,
        )
    )
    return source, registration


def condition_snapshots(
    *,
    drained_has_other_source: bool = False,
) -> tuple[WoundConditionSourceSnapshot, ...]:
    return (
        WoundConditionSourceSnapshot(Condition.BURDENED, True),
        WoundConditionSourceSnapshot(
            Condition.DRAINED,
            drained_has_other_source,
        ),
    )


class K1CombatSurgeonSuppressionTests(unittest.TestCase):
    def test_successful_suppression_registers_once_for_its_battle(self) -> None:
        source = successful_source()
        previous = CombatSurgeonSuppressionAggregate("battle:1")

        result = register_combat_surgeon_suppression(
            CombatSurgeonSuppressionRegistrationRequest(
                id="battle:1:suppression:register",
                aggregate=previous,
                source=source,
            )
        )

        self.assertEqual(result.previous_aggregate, previous)
        self.assertEqual(result.aggregate.suppressions, (source.suppression,))
        self.assertIn(
            COMBAT_SURGEON_SUPPRESSION_REGISTRATION_RULE_ID,
            result.applied_rule_ids,
        )
        with self.assertRaisesRegex(ValueError, "already registered"):
            CombatSurgeonSuppressionRegistrationRequest(
                id="battle:1:suppression:repeat",
                aggregate=result.aggregate,
                source=source,
            )

    def test_registration_rejects_failure_and_another_battle(self) -> None:
        treatment = completed_treatment(untreated_state())
        failed = resolve_combat_surgeon_treatment(
            combat_surgeon_request(treatment),
            SequenceRandom([8, 10]),
        )
        with self.assertRaisesRegex(ValueError, "successful suppression"):
            CombatSurgeonSuppressionRegistrationRequest(
                id="failed:register",
                aggregate=CombatSurgeonSuppressionAggregate("battle:1"),
                source=failed,
            )

        source = successful_source()
        with self.assertRaisesRegex(ValueError, "another battle"):
            CombatSurgeonSuppressionRegistrationRequest(
                id="wrong-battle:register",
                aggregate=CombatSurgeonSuppressionAggregate("battle:2"),
                source=source,
            )

    def test_effective_view_ignores_effects_without_mutating_injury(self) -> None:
        source, registration = registered_source()
        state = source.state

        result = resolve_combat_surgeon_effective_effects(
            CombatSurgeonEffectiveEffectsRequest(
                id="battle:1:hero:effective-effects",
                battle_id="battle:1",
                aggregate=registration.aggregate,
                target_id="hero",
                injury_state=state,
                condition_source_snapshots=condition_snapshots(),
            )
        )

        suppression = source.suppression
        assert suppression is not None
        self.assertEqual(result.active_suppressions, (suppression,))
        self.assertEqual(
            result.suppressed_effects,
            suppression.suppressed_effects,
        )
        self.assertEqual(
            result.effective_wound_effects,
            state.active_wound_effects[2:],
        )
        self.assertEqual(result.ignored_conditions, (Condition.DRAINED,))
        self.assertTrue(result.effective_conditions.has(Condition.BURDENED))
        self.assertFalse(result.effective_conditions.has(Condition.DRAINED))
        self.assertEqual(source.state, state)
        self.assertEqual(
            source.state.active_wound_effects,
            state.active_wound_effects,
        )
        self.assertIn(
            COMBAT_SURGEON_EFFECTIVE_EFFECTS_RULE_ID,
            result.applied_rule_ids,
        )

    def test_independent_condition_source_is_preserved(self) -> None:
        source, registration = registered_source()

        result = resolve_combat_surgeon_effective_effects(
            CombatSurgeonEffectiveEffectsRequest(
                id="battle:1:hero:external-source",
                battle_id="battle:1",
                aggregate=registration.aggregate,
                target_id="hero",
                injury_state=source.state,
                condition_source_snapshots=condition_snapshots(
                    drained_has_other_source=True,
                ),
            )
        )

        self.assertEqual(result.ignored_conditions, ())
        self.assertTrue(result.effective_conditions.has(Condition.BURDENED))
        self.assertTrue(result.effective_conditions.has(Condition.DRAINED))

    def test_known_remaining_wound_source_cannot_be_denied(self) -> None:
        source, registration = registered_source()
        invalid = (
            (),
            (
                WoundConditionSourceSnapshot(Condition.BURDENED, False),
                WoundConditionSourceSnapshot(Condition.DRAINED, False),
            ),
        )
        for snapshots in invalid:
            with self.subTest(snapshots=snapshots):
                with self.assertRaises(ValueError):
                    CombatSurgeonEffectiveEffectsRequest(
                        id="battle:1:hero:invalid-sources",
                        battle_id="battle:1",
                        aggregate=registration.aggregate,
                        target_id="hero",
                        injury_state=source.state,
                        condition_source_snapshots=snapshots,
                    )

    def test_view_rejects_wrong_context_and_changed_wound_identity(self) -> None:
        source, registration = registered_source()
        changed_identity = replace(
            source.state,
            wounds=(
                replace(
                    source.state.wounds[0],
                    entry_id=WoundEntryId.BLACKING_OUT,
                ),
                source.state.wounds[1],
            ),
        )
        invalid = (
            {
                "battle_id": "battle:2",
                "target_id": "hero",
                "injury_state": source.state,
            },
            {
                "battle_id": "battle:1",
                "target_id": "other",
                "injury_state": source.state,
            },
            {
                "battle_id": "battle:1",
                "target_id": "hero",
                "injury_state": changed_identity,
            },
        )
        for changes in invalid:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    CombatSurgeonEffectiveEffectsRequest(
                        id="invalid:effective-effects",
                        aggregate=registration.aggregate,
                        condition_source_snapshots=condition_snapshots(),
                        **changes,
                    )

    def test_view_allows_unrelated_state_change_but_not_stale_effect_set(
        self,
    ) -> None:
        source, registration = registered_source()
        evolved = replace(
            source.state,
            conditions=source.state.conditions.with_condition(
                Condition.STAGGERED
            ),
        )
        result = resolve_combat_surgeon_effective_effects(
            CombatSurgeonEffectiveEffectsRequest(
                id="battle:1:hero:evolved",
                battle_id="battle:1",
                aggregate=registration.aggregate,
                target_id="hero",
                injury_state=evolved,
                condition_source_snapshots=condition_snapshots(),
            )
        )
        self.assertTrue(result.effective_conditions.has(Condition.STAGGERED))

        stale = replace(
            source.state,
            active_wound_effects=source.state.active_wound_effects[1:],
        )
        with self.assertRaisesRegex(ValueError, "stale Wound effect set"):
            CombatSurgeonEffectiveEffectsRequest(
                id="battle:1:hero:stale",
                battle_id="battle:1",
                aggregate=registration.aggregate,
                target_id="hero",
                injury_state=stale,
                condition_source_snapshots=condition_snapshots(),
            )

    def test_healed_wound_makes_registered_suppression_inactive(self) -> None:
        source, registration = registered_source()
        healed = replace(
            source.state,
            wounds=(
                replace(source.state.wounds[0], healed=True),
                source.state.wounds[1],
            ),
            conditions=(
                source.state.conditions.without_condition(Condition.DRAINED)
            ),
            active_wound_effects=source.state.active_wound_effects[2:],
        )

        result = resolve_combat_surgeon_effective_effects(
            CombatSurgeonEffectiveEffectsRequest(
                id="battle:1:hero:healed",
                battle_id="battle:1",
                aggregate=registration.aggregate,
                target_id="hero",
                injury_state=healed,
            )
        )

        self.assertEqual(result.active_suppressions, ())
        self.assertEqual(result.suppressed_effects, ())
        self.assertEqual(
            result.effective_wound_effects,
            healed.active_wound_effects,
        )
        self.assertEqual(result.effective_conditions, healed.conditions)

    def test_unknown_application_rules_are_rejected(self) -> None:
        source = successful_source()
        registration_request = CombatSurgeonSuppressionRegistrationRequest(
            id="unknown:registration",
            aggregate=CombatSurgeonSuppressionAggregate("battle:1"),
            source=source,
            rule_id="HOUSE:registration",
        )
        with self.assertRaisesRegex(ValueError, "unknown rule"):
            register_combat_surgeon_suppression(registration_request)

        _, registration = registered_source()
        view_request = CombatSurgeonEffectiveEffectsRequest(
            id="unknown:view",
            battle_id="battle:1",
            aggregate=registration.aggregate,
            target_id="hero",
            injury_state=source.state,
            condition_source_snapshots=condition_snapshots(),
            rule_id="HOUSE:effective-effects",
        )
        with self.assertRaisesRegex(ValueError, "unknown rule"):
            resolve_combat_surgeon_effective_effects(view_request)

    def test_forged_registration_and_view_results_are_rejected(self) -> None:
        source, registration = registered_source()
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(
                registration,
                aggregate=registration.previous_aggregate,
            )

        view = resolve_combat_surgeon_effective_effects(
            CombatSurgeonEffectiveEffectsRequest(
                id="battle:1:hero:view",
                battle_id="battle:1",
                aggregate=registration.aggregate,
                target_id="hero",
                injury_state=source.state,
                condition_source_snapshots=condition_snapshots(),
            )
        )
        with self.assertRaisesRegex(ValueError, "stale provenance"):
            replace(view, ignored_conditions=())


if __name__ == "__main__":
    unittest.main()
