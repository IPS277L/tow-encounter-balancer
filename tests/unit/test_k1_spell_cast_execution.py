from __future__ import annotations

import unittest

from towr.domain.magic_models import (
    IdentifiedSpellTarget,
    SpellCastExecutionRequest,
    SpellCastRequest,
    SpellPotencyModifier,
)
from towr.rules.spell_cast_execution import (
    TARGET_SCOPED_POTENCY_RULE_ID,
    resolve_spell_cast_targets,
)
from towr.rules.stone_troll import STONE_TROLL_RULE_ID


def cast_request(*, base_potency: int = 2) -> SpellCastRequest:
    return SpellCastRequest(
        resolution_id="wizard:cast",
        caster_id="wizard",
        spell_rule_id="RULE-SPELL:beast-form",
        lore_id="lore:beasts",
        casting_value=4,
        base_potency=base_potency,
        rule_id="RULE-MAGIC-004:cast-or-wait",
    )


def execution_request(
    targets: tuple[IdentifiedSpellTarget, ...],
    *,
    base_potency: int = 2,
) -> SpellCastExecutionRequest:
    return SpellCastExecutionRequest(
        id="wizard:cast:targets",
        source=cast_request(base_potency=base_potency),
        selected_target_id="subject",
        targets=targets,
    )


class K1SpellCastExecutionTests(unittest.TestCase):
    def test_targets_keep_stable_order_and_resolve_potency_independently(self) -> None:
        result = resolve_spell_cast_targets(
            execution_request(
                (
                    IdentifiedSpellTarget("ally"),
                    IdentifiedSpellTarget(
                        "stone-troll",
                        potency_modifiers=(
                            SpellPotencyModifier(STONE_TROLL_RULE_ID, -1),
                        ),
                    ),
                    IdentifiedSpellTarget(
                        "warded-target",
                        potency_modifiers=(
                            SpellPotencyModifier("RULE-MAGIC:strong-ward", -2),
                        ),
                    ),
                )
            )
        )

        self.assertEqual(
            tuple(item.target_id for item in result.targets),
            ("ally", "stone-troll", "warded-target"),
        )
        self.assertEqual(
            tuple(item.potency.effective_potency for item in result.targets),
            (2, 1, 0),
        )
        self.assertEqual(
            tuple(item.target_id for item in result.follow_ups),
            ("ally", "stone-troll"),
        )
        self.assertIsNone(result.targets[2].effect_request)

    def test_effect_follow_up_preserves_cast_and_target_context(self) -> None:
        result = resolve_spell_cast_targets(
            execution_request((IdentifiedSpellTarget("target"),))
        )

        effect = result.follow_ups[0]
        self.assertEqual(result.caster_id, "wizard")
        self.assertEqual(result.spell_rule_id, "RULE-SPELL:beast-form")
        self.assertEqual(result.lore_id, "lore:beasts")
        self.assertEqual(result.selected_target_id, "subject")
        self.assertEqual(effect.source_cast_id, "wizard:cast")
        self.assertEqual(effect.caster_id, "wizard")
        self.assertEqual(effect.spell_rule_id, "RULE-SPELL:beast-form")
        self.assertEqual(effect.lore_id, "lore:beasts")
        self.assertEqual(effect.target_id, "target")
        self.assertEqual(effect.potency, 2)
        self.assertEqual(effect.rule_id, "RULE-SPELL:beast-form")

    def test_zero_potency_records_targets_without_effect_follow_ups(self) -> None:
        result = resolve_spell_cast_targets(
            execution_request(
                (
                    IdentifiedSpellTarget("first"),
                    IdentifiedSpellTarget("second"),
                ),
                base_potency=0,
            )
        )

        self.assertEqual(len(result.targets), 2)
        self.assertTrue(
            all(not item.potency.has_effect for item in result.targets)
        )
        self.assertEqual(result.follow_ups, ())

    def test_result_traces_boundary_and_unique_modifier_rules(self) -> None:
        result = resolve_spell_cast_targets(
            execution_request(
                (
                    IdentifiedSpellTarget(
                        "first",
                        potency_modifiers=(
                            SpellPotencyModifier("RULE-MAGIC:ward", -1),
                        ),
                    ),
                    IdentifiedSpellTarget(
                        "second",
                        potency_modifiers=(
                            SpellPotencyModifier("RULE-MAGIC:ward", -1),
                        ),
                    ),
                )
            )
        )

        self.assertEqual(
            result.applied_rule_ids,
            (TARGET_SCOPED_POTENCY_RULE_ID, "RULE-MAGIC:ward"),
        )

    def test_targets_can_be_empty_but_must_be_unique(self) -> None:
        empty = resolve_spell_cast_targets(execution_request(()))
        self.assertEqual(empty.targets, ())
        self.assertEqual(empty.follow_ups, ())

        with self.assertRaises(ValueError):
            execution_request(
                (
                    IdentifiedSpellTarget("same"),
                    IdentifiedSpellTarget("same"),
                )
            )

    def test_each_target_requires_unique_modifier_rule_ids(self) -> None:
        modifier = SpellPotencyModifier("RULE-MAGIC:ward", -1)
        with self.assertRaises(ValueError):
            IdentifiedSpellTarget(
                "target",
                potency_modifiers=(modifier, modifier),
            )


if __name__ == "__main__":
    unittest.main()
