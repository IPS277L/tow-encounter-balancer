from __future__ import annotations

import unittest
from dataclasses import replace

from towr.domain.magic_models import (
    CastingAbandonmentOutcome,
    CastingAbandonmentRequest,
    CastingSpellSelection,
    MiscastRollRequest,
    SpellCastRequest,
    WizardMagicState,
)
from towr.rules.casting_interruption_resolution import (
    VOLUNTARY_CASTING_ABANDONMENT_RULE_ID,
    abandon_casting,
)


def active_magic(*, miscast_dice: int = 0) -> WizardMagicState:
    return WizardMagicState(
        miscast_dice=miscast_dice,
        casting_successes=4,
        casting_lore_id="lore:beasts",
        latest_casting_roll_successes=2,
    )


def abandonment_request(
    *,
    state: WizardMagicState | None = None,
    wizard_level: int = 2,
    spell: CastingSpellSelection | None = None,
) -> CastingAbandonmentRequest:
    return CastingAbandonmentRequest(
        id="casting:abandon",
        caster_id="wizard",
        state=state if state is not None else active_magic(),
        wizard_level=wizard_level,
        spell_to_cast=spell,
    )


class K1CastingAbandonmentResolutionTests(unittest.TestCase):
    def test_empty_pool_ends_casting_without_miscast(self) -> None:
        result = abandon_casting(abandonment_request())

        self.assertIs(
            result.outcome,
            CastingAbandonmentOutcome.ENDED_WITHOUT_MISCAST,
        )
        self.assertIsNone(result.preparation)
        self.assertEqual(result.previous_state.casting_successes, 4)
        self.assertEqual(result.state, WizardMagicState())
        self.assertEqual(
            result.applied_rule_ids,
            (VOLUNTARY_CASTING_ABANDONMENT_RULE_ID,),
        )

    def test_non_empty_pool_prepares_voluntary_miscast(self) -> None:
        result = abandon_casting(
            abandonment_request(state=active_magic(miscast_dice=2))
        )

        self.assertIs(
            result.outcome,
            CastingAbandonmentOutcome.MISCAST_PREPARED,
        )
        self.assertIsNotNone(result.preparation)
        assert result.preparation is not None
        self.assertEqual(result.preparation.previous_casting_successes, 4)
        self.assertEqual(result.state, WizardMagicState(miscast_dice=2))
        self.assertEqual(len(result.preparation.follow_ups), 1)
        roll = result.preparation.follow_ups[0]
        self.assertIsInstance(roll, MiscastRollRequest)
        assert isinstance(roll, MiscastRollRequest)
        self.assertEqual(roll.source_resolution_id, "casting:abandon")
        self.assertEqual(roll.pool_dice_count, 2)
        self.assertEqual(roll.bonus_dice, 0)

    def test_optional_spell_precedes_roll_and_adds_bonus_die(self) -> None:
        result = abandon_casting(
            abandonment_request(
                state=active_magic(miscast_dice=1),
                spell=CastingSpellSelection(
                    spell_rule_id="RULE-SPELL:test",
                    lore_id="lore:beasts",
                    casting_value=4,
                ),
            )
        )

        assert result.preparation is not None
        spell, roll = result.preparation.follow_ups
        self.assertIsInstance(spell, SpellCastRequest)
        assert isinstance(spell, SpellCastRequest)
        self.assertEqual(spell.base_potency, 2)
        self.assertIsInstance(roll, MiscastRollRequest)
        assert isinstance(roll, MiscastRollRequest)
        self.assertEqual(roll.pool_dice_count, 1)
        self.assertEqual(roll.bonus_dice, 1)

    def test_request_requires_active_untriggered_casting(self) -> None:
        with self.assertRaises(ValueError):
            abandonment_request(state=WizardMagicState())
        with self.assertRaises(ValueError):
            abandonment_request(
                state=active_magic(miscast_dice=3),
                wizard_level=2,
            )

    def test_spell_requires_actual_miscast_and_casting_eligibility(self) -> None:
        spell = CastingSpellSelection(
            spell_rule_id="RULE-SPELL:test",
            lore_id="lore:beasts",
            casting_value=4,
        )
        with self.assertRaises(ValueError):
            abandonment_request(spell=spell)
        with self.assertRaises(ValueError):
            abandonment_request(
                state=active_magic(miscast_dice=1),
                spell=replace(spell, lore_id="lore:fire"),
            )
        with self.assertRaises(ValueError):
            abandonment_request(
                state=active_magic(miscast_dice=1),
                spell=replace(spell, casting_value=5),
            )

    def test_result_rejects_outcome_state_or_preparation_forgery(self) -> None:
        result = abandon_casting(
            abandonment_request(state=active_magic(miscast_dice=2))
        )

        with self.assertRaises(ValueError):
            replace(
                result,
                outcome=CastingAbandonmentOutcome.ENDED_WITHOUT_MISCAST,
            )
        with self.assertRaises(ValueError):
            replace(result, state=WizardMagicState(miscast_dice=1))
        with self.assertRaises(ValueError):
            replace(result, preparation=None)
        with self.assertRaises(ValueError):
            replace(result, wizard_level=1)
        with self.assertRaises(TypeError):
            replace(result, outcome="miscast_prepared")


if __name__ == "__main__":
    unittest.main()
