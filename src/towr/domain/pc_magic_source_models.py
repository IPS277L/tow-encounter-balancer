"""Facts and formal Elementalism spells for the first PC magic encounter.

PG1.4 III81/87, IV98–99, VI135 and VIII155–159/165. These models admit
an already trained Wizard; they do not simulate character creation or downtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from towr.domain.magic_models import (
    FormalSpellDefinition, SpellDuration, SpellRange, SpellTargetKind,
)


ELEMENTALISM_LORE_ID = 'elementalism'


class PcSpellId(str, Enum):
    LIGHTNING_BLAST = 'lightning_blast'
    FIRE_BREATH = 'fire_breath'


def _integer(value: int, name: str, minimum: int, maximum: int | None = None) -> None:
    if type(value) is not int:
        raise TypeError(f'{name} must be an exact integer')
    if value < minimum or maximum is not None and value > maximum:
        raise ValueError(f'{name} is outside its permitted range')


def _spell(value: PcSpellId) -> None:
    if type(value) is not PcSpellId:
        raise TypeError('a PC spell requires its typed supported spell ID')


@dataclass(frozen=True, slots=True)
class PcWizardProfile:
    origin: str
    willpower: int
    wizard_level: int
    lores: tuple[str, ...]
    memorised_spells: tuple[PcSpellId, ...]
    arcane_paraphernalia: bool

    def __post_init__(self) -> None:
        origins = ('human', 'dwarf', 'halfling', 'high_elf', 'wood_elf', 'ogre')
        if type(self.origin) is not str or self.origin not in origins:
            raise ValueError('Wizard profile requires a supported Origin fact')
        # The paid Talent Requirements belong to its acquisition owner.
        # PG73 explicitly permits the free Character Creation waiver.
        _integer(self.willpower, 'Willpower', 1, 10)
        _integer(self.wizard_level, 'Wizard Level', 1, 4)
        if (type(self.lores) is not tuple or not self.lores
                or any(type(lore) is not str or lore != ELEMENTALISM_LORE_ID for lore in self.lores)
                or len(set(self.lores)) != len(self.lores)):
            raise ValueError('the first PC magic profile requires unique Elementalism Lore')
        if type(self.memorised_spells) is not tuple or not self.memorised_spells:
            raise ValueError('Wizard profile requires ordered memorised spells')
        for spell in self.memorised_spells:
            _spell(spell)
            if pc_spell_definition(spell).lore_id not in self.lores:
                raise ValueError('a memorised spell requires its known Magic Lore')
        if len(set(self.memorised_spells)) != len(self.memorised_spells):
            raise ValueError('memorised spells must not repeat')
        if type(self.arcane_paraphernalia) is not bool:
            raise TypeError('Arcane Paraphernalia requires an explicit bool fact')
        if not self.arcane_paraphernalia:
            raise ValueError('this slice requires Arcane Paraphernalia; makeshift tools are outside its scope')


def pc_spell_definition(spell: PcSpellId) -> FormalSpellDefinition:
    """Return fresh immutable canonical metadata, independent of actor identity."""
    _spell(spell)
    if spell is PcSpellId.LIGHTNING_BLAST:
        return FormalSpellDefinition('RULE-SPELL-003:lightning-blast', ELEMENTALISM_LORE_ID,
            2, SpellTargetKind.CREATURE, SpellRange.LONG, SpellDuration.INSTANT)
    return FormalSpellDefinition('RULE-SPELL-003:fire-breath', ELEMENTALISM_LORE_ID,
        2, SpellTargetKind.ZONE, SpellRange.MEDIUM, SpellDuration.INSTANT)


def pc_spell_damage(spell: PcSpellId, potency: int, armoured: bool) -> int:
    """Printed direct Damage for an already admitted positive-Potency effect."""
    _spell(spell)
    _integer(potency, 'spell effect Potency', 1)
    if type(armoured) is not bool:
        raise TypeError('spell target armour must be an exact bool fact')
    if spell is PcSpellId.LIGHTNING_BLAST:
        return 4 + potency + int(armoured)
    return 3 if armoured else 4
