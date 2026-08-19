from __future__ import annotations

import unittest

from towr.domain.magic_models import (
    SpellPotencyModifier,
    SpellPotencyRequest,
)
from towr.rules.spell_potency_resolution import resolve_spell_potency
from towr.rules.stone_troll import (
    MAGIC_RESISTANCE_RULE_ID,
    STONE_TROLL_RESILIENCE,
    STONE_TROLL_RULE_ID,
    magic_resistance_spell_potency_modifier,
    stone_troll_spell_potency_modifier,
)


class K1SpellPotencyResolutionTests(unittest.TestCase):
    def test_stone_troll_profile_and_modifier_match_the_book(self) -> None:
        modifier = stone_troll_spell_potency_modifier()

        self.assertEqual(STONE_TROLL_RESILIENCE, 6)
        self.assertEqual(modifier.rule_id, STONE_TROLL_RULE_ID)
        self.assertEqual(modifier.amount, -1)

    def test_stone_troll_reduces_effective_potency_for_that_target(self) -> None:
        result = resolve_spell_potency(
            SpellPotencyRequest(
                id="spell:stone-troll:potency",
                spell_rule_id="RULE-SPELL:test",
                target_id="stone-troll",
                base_potency=3,
                modifiers=(stone_troll_spell_potency_modifier(),),
            )
        )

        self.assertEqual(result.base_potency, 3)
        self.assertEqual(result.potency_delta, -1)
        self.assertEqual(result.effective_potency, 2)
        self.assertTrue(result.has_effect)
        self.assertEqual(result.applied_rule_ids, (STONE_TROLL_RULE_ID,))

    def test_reduction_to_zero_blocks_the_spell_for_that_target(self) -> None:
        result = resolve_spell_potency(
            SpellPotencyRequest(
                id="spell:stone-troll:potency",
                spell_rule_id="RULE-SPELL:test",
                target_id="stone-troll",
                base_potency=1,
                modifiers=(stone_troll_spell_potency_modifier(),),
            )
        )

        self.assertEqual(result.effective_potency, 0)
        self.assertFalse(result.has_effect)

    def test_zero_base_potency_has_no_effect_without_a_modifier(self) -> None:
        result = resolve_spell_potency(
            SpellPotencyRequest(
                id="spell:zero-potency",
                spell_rule_id="RULE-SPELL:test",
                target_id="target",
                base_potency=0,
            )
        )

        self.assertEqual(result.effective_potency, 0)
        self.assertFalse(result.has_effect)

    def test_other_targets_keep_the_cast_spells_base_potency(self) -> None:
        result = resolve_spell_potency(
            SpellPotencyRequest(
                id="spell:other-target:potency",
                spell_rule_id="RULE-SPELL:test",
                target_id="other-target",
                base_potency=3,
            )
        )

        self.assertEqual(result.effective_potency, 3)
        self.assertTrue(result.has_effect)
        self.assertEqual(result.applied_rule_ids, ())

    def test_magic_resistance_talent_uses_the_same_modifier_policy(self) -> None:
        modifier = magic_resistance_spell_potency_modifier()

        self.assertEqual(modifier.rule_id, MAGIC_RESISTANCE_RULE_ID)
        self.assertEqual(modifier.amount, -1)

    def test_modifier_rule_ids_must_be_unique(self) -> None:
        modifier = SpellPotencyModifier("RULE-MAGIC:test", -1)
        with self.assertRaises(ValueError):
            SpellPotencyRequest(
                id="spell:duplicate-modifiers",
                spell_rule_id="RULE-SPELL:test",
                target_id="stone-troll",
                base_potency=2,
                modifiers=(modifier, modifier),
            )


if __name__ == "__main__":
    unittest.main()
