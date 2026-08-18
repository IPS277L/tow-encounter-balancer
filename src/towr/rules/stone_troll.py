from __future__ import annotations

from towr.domain.magic_models import SpellPotencyModifier


STONE_TROLL_RULE_ID = "RULE-NPC-022:stone-troll"
MAGIC_RESISTANCE_RULE_ID = "RULE-MAGIC-002:magic-resistance"
STONE_TROLL_RESILIENCE = 6


def stone_troll_spell_potency_modifier() -> SpellPotencyModifier:
    return SpellPotencyModifier(STONE_TROLL_RULE_ID, -1)


def magic_resistance_spell_potency_modifier() -> SpellPotencyModifier:
    return SpellPotencyModifier(MAGIC_RESISTANCE_RULE_ID, -1)
