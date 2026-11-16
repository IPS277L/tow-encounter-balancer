from dataclasses import FrozenInstanceError, replace
import unittest

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.injury_models import (
    CharacterInjuryState, WoundConditionEffect, WoundEffectDuration,
    WoundEntryId, WoundRecord, WoundRestriction, WoundRestrictionEffect,
)
from towr.domain.potion_models import ConsumableItem, ConsumableKind, heal_potion_wound


def damaged_state() -> CharacterInjuryState:
    return CharacterInjuryState(
        wounds=(
            WoundRecord(1, WoundEntryId.SEVERED_ARM, 20, (10, 10), effect_resolved=True),
            WoundRecord(2, WoundEntryId.INTERNAL_INJURY, 14, (10, 4), effect_resolved=True),
        ),
        conditions=ConditionState(frozenset((Condition.DRAINED, Condition.PRONE, Condition.BURDENED))),
        active_wound_effects=(
            WoundRestrictionEffect(1, WoundRestriction.ARM_LOST, WoundEffectDuration.PERMANENT),
            WoundConditionEffect(1, Condition.PRONE, WoundEffectDuration.UNTIL_REMOVED),
            WoundConditionEffect(1, Condition.DRAINED, WoundEffectDuration.UNTIL_HEALED),
            WoundConditionEffect(2, Condition.DRAINED, WoundEffectDuration.UNTIL_HEALED),
        ),
    )


class ConsumableItemTests(unittest.TestCase):
    def test_facts_are_immutable_and_all_eight_characteristics_can_be_described(self):
        item = ConsumableItem('potion:1', ConsumableKind.HEALING, 2, None)
        self.assertEqual(replace(item), item)
        with self.assertRaises(FrozenInstanceError):
            item.quantity = 1
        for characteristic in ('weapon_skill', 'ballistic_skill', 'strength', 'toughness',
                               'initiative', 'agility', 'reason', 'fellowship'):
            with self.subTest(characteristic=characteristic):
                self.assertEqual(ConsumableItem('potion:2', ConsumableKind.ENHANCEMENT,
                    1, characteristic).characteristic, characteristic)

    def test_quantity_kind_and_characteristic_boundaries(self):
        for quantity in (True, False, 0, -1, 1.0, '1'):
            with self.subTest(quantity=quantity), self.assertRaises(ValueError):
                ConsumableItem('potion', ConsumableKind.HEALING, quantity, None)
        for item_id in ('', '  ', None, 1):
            with self.subTest(item_id=item_id), self.assertRaises(ValueError):
                ConsumableItem(item_id, ConsumableKind.HEALING, 1, None)
        with self.assertRaises(TypeError):
            ConsumableItem('potion', 'healing_potion', 1, None)
        with self.assertRaises(ValueError):
            ConsumableItem('potion', ConsumableKind.HEALING, 1, 'strength')
        for characteristic in (None, 'unknown'):
            with self.subTest(characteristic=characteristic), self.assertRaises(ValueError):
                ConsumableItem('potion', ConsumableKind.ENHANCEMENT, 1, characteristic)


class PotionHealingTests(unittest.TestCase):
    def test_heals_one_wound_and_its_permanent_effect_without_rewriting_history(self):
        before = damaged_state()
        after = heal_potion_wound(before, 1)
        self.assertTrue(after.wounds[0].healed)
        self.assertTrue(after.wounds[0].treated)
        self.assertEqual(replace(after.wounds[0], healed=False, treated=False), before.wounds[0])
        self.assertIs(after.wounds[1], before.wounds[1])
        self.assertEqual(after.active_wound_effects, (before.active_wound_effects[-1],))
        self.assertFalse(after.conditions.has(Condition.PRONE))
        self.assertTrue(after.conditions.has(Condition.DRAINED))
        self.assertTrue(after.conditions.has(Condition.BURDENED))
        self.assertEqual((before.untreated_wounds, after.untreated_wounds), (2, 1))
        self.assertEqual((before.active_wounds, after.active_wounds), (2, 1))
        self.assertFalse(before.wounds[0].healed)

    def test_external_cause_survives_even_when_last_wound_cause_is_removed(self):
        before = damaged_state()
        after = heal_potion_wound(before, 1, frozenset((Condition.PRONE,)))
        self.assertTrue(after.conditions.has(Condition.PRONE))
        after = heal_potion_wound(after, 2)
        self.assertFalse(after.conditions.has(Condition.DRAINED))
        self.assertTrue(after.conditions.has(Condition.PRONE))
        self.assertTrue(after.conditions.has(Condition.BURDENED))
        self.assertEqual(after.active_wound_effects, ())

    def test_heals_defenceless_source_without_clearing_a_second_independent_source(self):
        before = CharacterInjuryState(
            (WoundRecord(1, WoundEntryId.RUPTURED_ORGANS, 22, (10, 10, 2), effect_resolved=True),),
            ConditionState(frozenset((Condition.DEFENCELESS, Condition.STAGGERED))),
            (WoundConditionEffect(1, Condition.DEFENCELESS, WoundEffectDuration.UNTIL_HEALED),),
        )
        self.assertFalse(heal_potion_wound(before, 1).conditions.has(Condition.DEFENCELESS))
        after = heal_potion_wound(before, 1, frozenset((Condition.DEFENCELESS,)))
        self.assertTrue(after.conditions.has(Condition.DEFENCELESS))
        self.assertTrue(after.conditions.has(Condition.STAGGERED))

    def test_rejects_dead_unresolved_healed_and_lethal_table_entries(self):
        before = damaged_state()
        sources = (
            replace(before, dead=True),
            replace(before, wounds=(replace(before.wounds[0], effect_resolved=False), before.wounds[1])),
            heal_potion_wound(before, 1),
            CharacterInjuryState((WoundRecord(1, WoundEntryId.APPALLING_STRIKE,
                24, (10, 10, 4), effect_resolved=True),)),
        )
        for injury in sources:
            with self.subTest(injury=injury), self.assertRaises(ValueError):
                heal_potion_wound(injury, 1)

    def test_rejects_noncanonical_sequence_and_external_sources(self):
        for sequence in (True, False, 0, -1, 3, 1.0, '1'):
            with self.subTest(sequence=sequence), self.assertRaises(ValueError):
                heal_potion_wound(damaged_state(), sequence)
        for sources in ({Condition.PRONE}, (Condition.PRONE,), frozenset(('prone',))):
            with self.subTest(sources=sources), self.assertRaises(TypeError):
                heal_potion_wound(damaged_state(), 1, sources)
        with self.assertRaises(TypeError):
            heal_potion_wound(None, 1)


if __name__ == '__main__':
    unittest.main()
