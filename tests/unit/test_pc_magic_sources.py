from dataclasses import FrozenInstanceError, replace
import unittest

from towr.domain.magic_models import SpellDuration, SpellRange, SpellTargetKind
from towr.domain.pc_magic_source_models import (
    ELEMENTALISM_LORE_ID, PcSpellId, PcWizardProfile,
    pc_spell_damage, pc_spell_definition,
)


def wizard(**changes):
    values = dict(origin='human', reason=3, willpower=5, wizard_level=1,
        lores=(ELEMENTALISM_LORE_ID,),
        memorised_spells=(PcSpellId.LIGHTNING_BLAST, PcSpellId.FIRE_BREATH),
        arcane_paraphernalia=True)
    values.update(changes)
    return PcWizardProfile(**values)


class PcMagicSourceTests(unittest.TestCase):
    def test_level_one_can_know_both_formal_cv_two_spells(self):
        source = wizard()
        self.assertEqual(replace(source), source)
        self.assertEqual(tuple(pc_spell_definition(spell).casting_value
            for spell in source.memorised_spells), (2, 2))
        profile = source.willpower_profile
        self.assertEqual((profile.base_dice, profile.threshold, profile.maximum_dice), (3, 5, 6))
        with self.assertRaises(FrozenInstanceError):
            source.wizard_level = 2

    def test_wizard_prerequisites_are_facts_and_not_npc_identity(self):
        for origin in ('human', 'high_elf', 'wood_elf', 'ogre'):
            with self.subTest(origin=origin):
                self.assertEqual(wizard(origin=origin).origin, origin)
        for origin in ('dwarf', 'halfling', 'unknown', '', None, 1):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                wizard(origin=origin)
        for level in (0, 5, -1):
            with self.subTest(level=level), self.assertRaises(ValueError):
                wizard(wizard_level=level)
        for level in (True, False, 1.0, '1'):
            with self.subTest(level=level), self.assertRaises(TypeError):
                wizard(wizard_level=level)
        for level in range(1, 5):
            self.assertEqual(wizard(wizard_level=level).wizard_level, level)

    def test_reason_skill_and_tool_boundaries_are_not_coerced(self):
        for name, value in (('reason', 0), ('reason', -1), ('willpower', 0), ('willpower', 11)):
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                wizard(**{name: value})
        for name in ('reason', 'willpower'):
            for value in (True, 3.0, '3'):
                with self.subTest(name=name, value=value), self.assertRaises(TypeError):
                    wizard(**{name: value})
        with self.assertRaises(ValueError):
            wizard(arcane_paraphernalia=False)
        for value in (1, 'yes', None):
            with self.subTest(value=value), self.assertRaises(TypeError):
                wizard(arcane_paraphernalia=value)

    def test_worn_armour_fact_includes_helmet_without_inventing_a_resilience_bonus(self):
        from tests.support.pc_tactics_fixtures import automatic_source
        member = replace(automatic_source().party[0],wizard=wizard())
        armoured = replace(member,armour_worn=True)
        self.assertIsNone(member.armour_worn)
        self.assertIs(armoured.armour_worn,True)
        self.assertEqual(member.wizard,armoured.wizard)
        self.assertEqual(member.pc.armour_bonus,armoured.pc.armour_bonus)
        for value in (0, 1, 'yes'):
            with self.subTest(value=value), self.assertRaises(TypeError):
                replace(member,armour_worn=value)

    def test_lore_and_memorisation_must_be_unique_typed_ordered_sources(self):
        for lores in ((), [], ['elementalism'], ('unknown',), ('elementalism', 'elementalism')):
            with self.subTest(lores=lores), self.assertRaises(ValueError):
                wizard(lores=lores)
        for spells in ((), [], [PcSpellId.FIRE_BREATH], (PcSpellId.FIRE_BREATH,)*2):
            with self.subTest(spells=spells), self.assertRaises(ValueError):
                wizard(memorised_spells=spells)
        with self.assertRaises(TypeError):
            wizard(memorised_spells=('fire_breath',))
        self.assertEqual(wizard(memorised_spells=(PcSpellId.FIRE_BREATH,)).memorised_spells,
            (PcSpellId.FIRE_BREATH,))

    def test_cached_mutations_fail_readmission_instead_of_becoming_sources(self):
        for field, value in (('wizard_level', True), ('reason', True), ('willpower', 11),
                ('memorised_spells', ['fire_breath']), ('arcane_paraphernalia', 1),
                ('lores', ('elementalism', 'elementalism'))):
            source = wizard()
            object.__setattr__(source, field, value)
            with self.subTest(field=field), self.assertRaises((TypeError, ValueError)):
                replace(source)

    def test_formal_metadata_has_exact_target_range_duration_and_fresh_values(self):
        lightning = pc_spell_definition(PcSpellId.LIGHTNING_BLAST)
        fire = pc_spell_definition(PcSpellId.FIRE_BREATH)
        self.assertEqual((lightning.rule_id, lightning.lore_id, lightning.target_kind,
            lightning.range, lightning.duration), ('RULE-SPELL-003:lightning-blast',
                'elementalism', SpellTargetKind.CREATURE, SpellRange.LONG, SpellDuration.INSTANT))
        self.assertEqual((fire.rule_id, fire.lore_id, fire.target_kind, fire.range, fire.duration),
            ('RULE-SPELL-003:fire-breath', 'elementalism', SpellTargetKind.ZONE,
                SpellRange.MEDIUM, SpellDuration.INSTANT))
        self.assertIsNot(lightning, pc_spell_definition(PcSpellId.LIGHTNING_BLAST))
        with self.assertRaises(TypeError):
            pc_spell_definition('fire_breath')

    def test_printed_damage_depends_on_target_armour_without_attack_success_bonus(self):
        for potency in (1, 2, 5):
            self.assertEqual(pc_spell_damage(PcSpellId.LIGHTNING_BLAST, potency, False), 4+potency)
            self.assertEqual(pc_spell_damage(PcSpellId.LIGHTNING_BLAST, potency, True), 5+potency)
            self.assertEqual(pc_spell_damage(PcSpellId.FIRE_BREATH, potency, False), 4)
            self.assertEqual(pc_spell_damage(PcSpellId.FIRE_BREATH, potency, True), 3)
        for potency in (0, -1):
            with self.assertRaises(ValueError):
                pc_spell_damage(PcSpellId.LIGHTNING_BLAST, potency, False)
        for potency in (True, 1.0):
            with self.assertRaises(TypeError):
                pc_spell_damage(PcSpellId.LIGHTNING_BLAST, potency, False)
        with self.assertRaises(TypeError):
            pc_spell_damage(PcSpellId.FIRE_BREATH, 1, 1)


if __name__ == '__main__':
    unittest.main()
