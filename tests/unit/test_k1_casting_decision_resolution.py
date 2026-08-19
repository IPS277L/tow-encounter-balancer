from __future__ import annotations

import unittest

from towr.domain.magic_models import (
    CastingChoice,
    CastingDecisionRequest,
    CastingSpellSelection,
    SpellCastRequest,
    SpellPotencyRequest,
    WizardMagicState,
)
from towr.rules.casting_decision_resolution import (
    CAST_OR_WAIT_RULE_ID,
    resolve_casting_decision,
)
from towr.rules.spell_potency_resolution import resolve_spell_potency


def active_state(
    *,
    accumulated: int = 4,
    latest: int = 2,
    miscast_dice: int = 1,
) -> WizardMagicState:
    return WizardMagicState(
        miscast_dice=miscast_dice,
        casting_successes=accumulated,
        casting_lore_id="lore:beasts",
        latest_casting_roll_successes=latest,
    )


def selected_spell(
    *,
    lore_id: str = "lore:beasts",
    casting_value: int = 4,
) -> CastingSpellSelection:
    return CastingSpellSelection(
        spell_rule_id="RULE-SPELL:beast-form",
        lore_id=lore_id,
        casting_value=casting_value,
    )


def decision_request(
    *,
    choice: CastingChoice,
    state: WizardMagicState | None = None,
    spell: CastingSpellSelection | None = None,
    wizard_level: int = 2,
) -> CastingDecisionRequest:
    return CastingDecisionRequest(
        id="wizard:post-casting",
        caster_id="wizard",
        state=state if state is not None else active_state(),
        wizard_level=wizard_level,
        choice=choice,
        selected_spell=spell,
    )


class K1CastingDecisionResolutionTests(unittest.TestCase):
    def test_wait_preserves_the_entire_casting_snapshot(self) -> None:
        state = active_state()

        result = resolve_casting_decision(
            decision_request(choice=CastingChoice.WAIT, state=state)
        )

        self.assertIs(result.choice, CastingChoice.WAIT)
        self.assertIs(result.state, state)
        self.assertEqual(result.previous_casting_successes, 4)
        self.assertIsNone(result.base_potency)
        self.assertEqual(result.follow_ups, ())
        self.assertEqual(result.applied_rule_ids, (CAST_OR_WAIT_RULE_ID,))

    def test_cast_creates_follow_up_and_clears_only_casting_snapshot(self) -> None:
        result = resolve_casting_decision(
            decision_request(
                choice=CastingChoice.CAST,
                spell=selected_spell(),
            )
        )

        self.assertIs(result.choice, CastingChoice.CAST)
        self.assertEqual(result.previous_casting_successes, 4)
        self.assertEqual(result.base_potency, 2)
        self.assertEqual(result.state.miscast_dice, 1)
        self.assertEqual(result.state.casting_successes, 0)
        self.assertIsNone(result.state.casting_lore_id)
        self.assertEqual(result.state.latest_casting_roll_successes, 0)
        self.assertEqual(len(result.follow_ups), 1)
        cast = result.follow_ups[0]
        self.assertIsInstance(cast, SpellCastRequest)
        self.assertEqual(cast.caster_id, "wizard")
        self.assertEqual(cast.spell_rule_id, "RULE-SPELL:beast-form")
        self.assertEqual(cast.lore_id, "lore:beasts")
        self.assertEqual(cast.casting_value, 4)
        self.assertEqual(cast.base_potency, 2)

    def test_accumulated_successes_can_cast_with_zero_base_potency(self) -> None:
        result = resolve_casting_decision(
            decision_request(
                choice=CastingChoice.CAST,
                state=active_state(latest=0),
                spell=selected_spell(),
            )
        )

        cast = result.follow_ups[0]
        potency = resolve_spell_potency(
            SpellPotencyRequest(
                id="wizard:target-potency",
                spell_rule_id=cast.spell_rule_id,
                target_id="target",
                base_potency=cast.base_potency,
            )
        )

        self.assertEqual(cast.base_potency, 0)
        self.assertFalse(potency.has_effect)

    def test_cast_requires_matching_lore_and_enough_successes(self) -> None:
        with self.assertRaises(ValueError):
            decision_request(
                choice=CastingChoice.CAST,
                spell=selected_spell(lore_id="lore:fire"),
            )
        with self.assertRaises(ValueError):
            decision_request(
                choice=CastingChoice.CAST,
                spell=selected_spell(casting_value=5),
            )

    def test_choice_and_selected_spell_must_agree(self) -> None:
        with self.assertRaises(ValueError):
            decision_request(choice=CastingChoice.CAST)
        with self.assertRaises(ValueError):
            decision_request(
                choice=CastingChoice.WAIT,
                spell=selected_spell(),
            )

    def test_decision_requires_active_casting_and_no_pending_miscast(self) -> None:
        with self.assertRaises(ValueError):
            decision_request(
                choice=CastingChoice.WAIT,
                state=WizardMagicState(),
            )
        with self.assertRaises(ValueError):
            decision_request(
                choice=CastingChoice.WAIT,
                state=active_state(miscast_dice=3),
                wizard_level=2,
            )

    def test_pool_equal_to_wizard_level_still_allows_decision(self) -> None:
        result = resolve_casting_decision(
            decision_request(
                choice=CastingChoice.WAIT,
                state=active_state(miscast_dice=2),
                wizard_level=2,
            )
        )

        self.assertIs(result.choice, CastingChoice.WAIT)


if __name__ == "__main__":
    unittest.main()
