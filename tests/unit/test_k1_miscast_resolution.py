from __future__ import annotations

import unittest

from tests.helpers import SequenceRandom
from towr.domain.magic_models import (
    CastingSpellSelection,
    MiscastPreparationRequest,
    MiscastRollRequest,
    MiscastTableEntryId,
    SpellCastRequest,
    WizardMagicState,
)
from towr.rules.miscast_resolution import (
    prepare_miscast,
    resolve_miscast_roll,
)
from towr.rules.miscast_table import MISCAST_TABLE, lookup_miscast


RULE_ID = "RULE-MAGIC-004:miscast-pool"


def roll_request(*, pool_dice: int = 3) -> MiscastRollRequest:
    return MiscastRollRequest(
        resolution_id="wizard:miscast-pool",
        source_resolution_id="wizard:casting-test",
        target_id="wizard",
        pool_dice_count=pool_dice,
        rule_id=RULE_ID,
    )


def preparation_request(
    *,
    successes: int = 4,
    spell: CastingSpellSelection | None = None,
) -> MiscastPreparationRequest:
    return MiscastPreparationRequest(
        id="wizard:miscast-preparation",
        source=roll_request(),
        state=WizardMagicState(
            miscast_dice=3,
            casting_successes=successes,
            casting_lore_id="lore:beasts",
            latest_casting_roll_successes=min(successes, 2),
        ),
        spell_to_cast=spell,
        rule_id=RULE_ID,
    )


class K1MiscastTableTests(unittest.TestCase):
    def test_table_is_complete_without_overlapping_ranges(self) -> None:
        self.assertEqual(len(MISCAST_TABLE), 21)
        for total in range(1, 80):
            matches = tuple(
                entry for entry in MISCAST_TABLE if entry.includes(total)
            )
            self.assertEqual(len(matches), 1, total)

    def test_corrected_twenty_two_and_twenty_three_ranges(self) -> None:
        self.assertIs(
            lookup_miscast(22).id,
            MiscastTableEntryId.UNNATURAL_WIND,
        )
        self.assertIs(
            lookup_miscast(23).id,
            MiscastTableEntryId.SPELL_RECAST,
        )

    def test_thirty_nine_plus_is_open_ended(self) -> None:
        self.assertIs(
            lookup_miscast(100).id,
            MiscastTableEntryId.CATASTROPHIC_DEATH,
        )


class K1MiscastPreparationTests(unittest.TestCase):
    def test_declining_spell_loses_successes_before_unmodified_roll(self) -> None:
        result = prepare_miscast(preparation_request(successes=4))

        self.assertEqual(result.previous_casting_successes, 4)
        self.assertEqual(result.state.casting_successes, 0)
        self.assertIsNone(result.state.casting_lore_id)
        self.assertEqual(result.state.latest_casting_roll_successes, 0)
        self.assertEqual(len(result.follow_ups), 1)
        roll = result.follow_ups[0]
        self.assertIsInstance(roll, MiscastRollRequest)
        assert isinstance(roll, MiscastRollRequest)
        self.assertEqual(roll.pool_dice_count, 3)
        self.assertEqual(roll.bonus_dice, 0)
        self.assertEqual(roll.dice_count, 3)

    def test_casting_spell_is_ordered_before_roll_and_adds_one_die(self) -> None:
        result = prepare_miscast(
            preparation_request(
                successes=4,
                spell=CastingSpellSelection(
                    spell_rule_id="RULE-SPELL:test",
                    lore_id="lore:beasts",
                    casting_value=4,
                ),
            )
        )

        self.assertEqual(len(result.follow_ups), 2)
        spell, roll = result.follow_ups
        self.assertIsInstance(spell, SpellCastRequest)
        assert isinstance(spell, SpellCastRequest)
        self.assertEqual(spell.lore_id, "lore:beasts")
        self.assertEqual(spell.base_potency, 2)
        self.assertIsInstance(roll, MiscastRollRequest)
        assert isinstance(roll, MiscastRollRequest)
        self.assertEqual(roll.pool_dice_count, 3)
        self.assertEqual(roll.bonus_dice, 1)
        self.assertEqual(roll.dice_count, 4)

    def test_spell_requires_matching_lore_and_enough_successes(self) -> None:
        with self.assertRaises(ValueError):
            preparation_request(
                successes=3,
                spell=CastingSpellSelection(
                    spell_rule_id="RULE-SPELL:test",
                    lore_id="lore:beasts",
                    casting_value=4,
                ),
            )

        with self.assertRaises(ValueError):
            preparation_request(
                spell=CastingSpellSelection(
                    spell_rule_id="RULE-SPELL:test",
                    lore_id="lore:fire",
                    casting_value=4,
                ),
            )

        with self.assertRaises(ValueError):
            MiscastRollRequest(
                resolution_id="invalid",
                source_resolution_id="source",
                target_id="wizard",
                pool_dice_count=3,
                bonus_dice=2,
            )


class K1MiscastRollTests(unittest.TestCase):
    def test_roll_uses_pool_and_bonus_dice_and_requests_table_effect(self) -> None:
        prepared = prepare_miscast(
            preparation_request(
                spell=CastingSpellSelection(
                    spell_rule_id="RULE-SPELL:test",
                    lore_id="lore:beasts",
                    casting_value=4,
                ),
            )
        )
        roll = prepared.follow_ups[-1]
        assert isinstance(roll, MiscastRollRequest)

        result = resolve_miscast_roll(
            roll,
            prepared.state,
            SequenceRandom([5, 6, 6, 6]),
        )

        self.assertEqual(result.roll_values, (5, 6, 6, 6))
        self.assertEqual(result.total, 23)
        self.assertIs(result.entry.id, MiscastTableEntryId.SPELL_RECAST)
        self.assertEqual(result.state.miscast_dice, 3)
        self.assertEqual(result.effect_request.pool_dice_count, 3)
        self.assertEqual(result.effect_request.bonus_dice, 1)
        self.assertIs(
            result.effect_request.entry_id,
            MiscastTableEntryId.SPELL_RECAST,
        )
        self.assertEqual(
            result.effect_request.rule_id,
            "RULE-MISCAST-TABLE:spell_recast",
        )

    def test_roll_rejects_unresolved_successes_or_wrong_pool_snapshot(self) -> None:
        request = roll_request()
        with self.assertRaises(ValueError):
            resolve_miscast_roll(
                request,
                WizardMagicState(
                    miscast_dice=3,
                    casting_successes=1,
                    casting_lore_id="lore:beasts",
                    latest_casting_roll_successes=1,
                ),
                SequenceRandom([1, 1, 1]),
            )
        with self.assertRaises(ValueError):
            resolve_miscast_roll(
                request,
                WizardMagicState(miscast_dice=2),
                SequenceRandom([1, 1, 1]),
            )


if __name__ == "__main__":
    unittest.main()
