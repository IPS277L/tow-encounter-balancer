"""PG1.4 III73–81 inventory; registry presence is not combat admission."""
from tests.support.talent_sources import paid_talent
from collections import Counter
from dataclasses import FrozenInstanceError, replace
import pickle
import unittest

from towr.domain.talent_catalog import (
    FamiliarEffect, TALENT_DEFINITIONS, TalentEquipmentRequirement,
    TalentId, TalentLoreRequirement, TalentOrigin, TalentProgression,
    TalentRequirements, TalentSelection, TalentStatusTier, talent_definition,
)


class TalentCatalogTests(unittest.TestCase):
    def test_complete_book_inventory_and_printed_page_counts(self):
        # Independently counted Cost headings on the nine source pages.
        self.assertEqual(len(TalentId), 59)
        self.assertEqual(len(TALENT_DEFINITIONS), 59)
        self.assertEqual(Counter(entry.page for entry in TALENT_DEFINITIONS),
            {73: 7, 74: 7, 75: 3, 76: 8, 77: 4, 78: 5, 79: 10, 80: 7, 81: 8})
        self.assertEqual({entry.id for entry in TALENT_DEFINITIONS}, set(TalentId))
        self.assertEqual(talent_definition(TalentId.GRAIL_VOW).name, 'The Grail Vow')
        self.assertEqual(talent_definition(TalentId.QUESTING_VOW).name, 'The Questing Vow')

    def test_multiple_purchases_are_only_the_three_printed_exceptions(self):
        repeatable={entry.id for entry in TALENT_DEFINITIONS if entry.maximum_purchases != 1}
        self.assertEqual(repeatable, {TalentId.FAITH, TalentId.FAMILIAR, TalentId.WIZARD})
        self.assertEqual(talent_definition(TalentId.WIZARD).maximum_purchases, 4)
        self.assertIsNone(talent_definition(TalentId.FAITH).maximum_purchases)
        familiar=talent_definition(TalentId.FAMILIAR)
        self.assertIs(familiar.progression, TalentProgression.FAMILIAR_EFFECTS)
        self.assertIs(familiar.selection, TalentSelection.FAMILIAR_EFFECT)
        self.assertEqual({effect.value for effect in FamiliarEffect}, {
            'armoured', 'babbler', 'bookrest', 'chaos_sink', 'combatant',
            'flight', 'linked', 'poison_tongue', 'skulker'})

    def test_creation_phase_and_operative_restrictions_are_not_stat_prerequisites(self):
        self.assertEqual({entry.id for entry in TALENT_DEFINITIONS if entry.creation_only},
            {TalentId.LONGBEARD, TalentId.SECRET_BLOODLINE, TalentId.SHORT_SIZE})
        self.assertEqual(talent_definition(TalentId.LONGBEARD).requirements.origins,
            (TalentOrigin.DWARF,))
        self.assertEqual(talent_definition(TalentId.GRAIL_VOW).requirements.talents,
            (TalentId.QUESTING_VOW,))
        self.assertIn(76, talent_definition(TalentId.GRAIL_VOW).operative_source_pages)
        self.assertIn(138, talent_definition(TalentId.FAITH).operative_source_pages)

    def test_combined_prerequisites_are_retained_without_implicit_waivers(self):
        blessing=talent_definition(TalentId.BLESSINGS_OF_THE_LADY).requirements
        self.assertEqual(blessing.origins, (TalentOrigin.BRETONNIAN_HUMAN,))
        self.assertEqual(blessing.lores, (TalentLoreRequirement.HIGH_SOCIETY,))
        self.assertEqual(blessing.talents, (TalentId.HONOUR_BOUND,))
        quick=talent_definition(TalentId.QUICK_THROW).requirements
        self.assertEqual((quick.weapon_skill, quick.ballistic_skill), (4, 4))
        self.assertEqual(talent_definition(TalentId.VOUCH_FOR_THEM).requirements.minimum_status,
            TalentStatusTier.SILVER)
        self.assertEqual({tier.value for tier in TalentStatusTier}, {'brass', 'silver', 'gold'})
        self.assertEqual(talent_definition(TalentId.BATTLEFIELD_MUSICIAN).requirements.equipment,
            (TalentEquipmentRequirement.MUSICIANS_GEAR,))
        self.assertEqual(talent_definition(TalentId.WIZARD).requirements.lores,
            (TalentLoreRequirement.ANY_MAGIC,))

    def test_untyped_aliased_and_impossible_metadata_are_rejected(self):
        for changes in (dict(weapon_skill=True), dict(strength=-1), dict(reason=1.5),
                dict(origins=('dwarf',)), dict(talents=(paid_talent(TalentId.WIZARD), paid_talent(TalentId.WIZARD))),
                dict(minimum_status='silver')):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                TalentRequirements(**changes)
        with self.assertRaises(ValueError):
            TalentRequirements(origins=(TalentOrigin.DWARF,), excluded_origins=(TalentOrigin.DWARF,))
        with self.assertRaises(TypeError):
            talent_definition('hardy')
        for changes in (dict(page=True), dict(page=82), dict(xp_cost=True), dict(creation_only=1)):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(talent_definition(TalentId.HARDY), **changes)

    def test_entries_are_immutable_and_retain_their_typed_source_across_pickle(self):
        for entry in TALENT_DEFINITIONS:
            self.assertIs(talent_definition(entry.id), entry)
            self.assertEqual(pickle.loads(pickle.dumps(entry)), entry)
        with self.assertRaises(FrozenInstanceError):
            talent_definition(TalentId.HARDY).xp_cost=0


if __name__ == '__main__':
    unittest.main()
