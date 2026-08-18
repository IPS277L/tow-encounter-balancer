from __future__ import annotations

import unittest

from towr.domain.condition_models import (
    Condition,
    ConditionApplicationRequest,
    ConditionState,
    EffectClassification,
    EffectImmunity,
)
from towr.rules.condition_effect_resolution import (
    resolve_condition_application,
)


def immunity() -> EffectImmunity:
    return EffectImmunity(
        EffectClassification.PSYCHOLOGICAL,
        "RULE-NPC:undead-psychological-immunity",
    )


def request(
    *,
    classification: EffectClassification,
    state: ConditionState | None = None,
    immunities: tuple[EffectImmunity, ...] = (),
) -> ConditionApplicationRequest:
    return ConditionApplicationRequest(
        id="apply-broken",
        state=state or ConditionState(),
        condition=Condition.BROKEN,
        source_rule_id="RULE-SPELL:curse-of-cowardly-flight",
        classification=classification,
        immunities=immunities,
    )


class K1ConditionApplicationTests(unittest.TestCase):
    def test_matching_immunity_blocks_psychological_condition(self) -> None:
        source = request(
            classification=EffectClassification.PSYCHOLOGICAL,
            immunities=(immunity(),),
        )
        result = resolve_condition_application(source)

        self.assertIs(result.state, source.state)
        self.assertFalse(result.state.has(Condition.BROKEN))
        self.assertTrue(result.blocked)
        self.assertEqual(
            result.source_rule_id,
            "RULE-SPELL:curse-of-cowardly-flight",
        )
        self.assertEqual(
            result.blocked_by_rule_id,
            "RULE-NPC:undead-psychological-immunity",
        )
        self.assertEqual(
            result.applied_rule_ids,
            ("RULE-NPC:undead-psychological-immunity",),
        )

    def test_condition_value_does_not_imply_psychological_source(self) -> None:
        result = resolve_condition_application(
            request(
                classification=EffectClassification.UNCLASSIFIED,
                immunities=(immunity(),),
            )
        )

        self.assertFalse(result.blocked)
        self.assertTrue(result.state.has(Condition.BROKEN))
        self.assertIsNone(result.blocked_by_rule_id)
        self.assertEqual(
            result.applied_rule_ids,
            ("RULE-SPELL:curse-of-cowardly-flight",),
        )

    def test_psychological_condition_applies_without_immunity(self) -> None:
        result = resolve_condition_application(
            request(classification=EffectClassification.PSYCHOLOGICAL)
        )

        self.assertFalse(result.blocked)
        self.assertTrue(result.state.has(Condition.BROKEN))

    def test_existing_condition_is_reported_even_when_blocked(self) -> None:
        result = resolve_condition_application(
            request(
                classification=EffectClassification.PSYCHOLOGICAL,
                state=ConditionState(frozenset({Condition.BROKEN})),
                immunities=(immunity(),),
            )
        )

        self.assertTrue(result.was_already_present)
        self.assertTrue(result.blocked)
        self.assertTrue(result.state.has(Condition.BROKEN))

    def test_immunity_requires_unique_explicit_classification(self) -> None:
        with self.assertRaises(ValueError):
            EffectImmunity(
                EffectClassification.UNCLASSIFIED,
                "RULE-NPC:invalid-immunity",
            )
        with self.assertRaises(ValueError):
            request(
                classification=EffectClassification.PSYCHOLOGICAL,
                immunities=(immunity(), immunity()),
            )


if __name__ == "__main__":
    unittest.main()
