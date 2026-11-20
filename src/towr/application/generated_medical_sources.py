"""Explicit medical supplies and physical tools permitted by a GM search.

This declares equipment and preparation, not a preset NPC or an automatic
Talent grant. Ratings and injury roles remain independently generated.
"""
from dataclasses import dataclass, replace

from towr.domain.medical_preparation_models import MedicalPreparationFacts
from towr.domain.tool_inventory_models import ToolItemSource


@dataclass(frozen=True, slots=True)
class GeneratedMedicalSource:
    medical: MedicalPreparationFacts
    tools: tuple[ToolItemSource, ...]

    def __post_init__(self):
        if type(self.medical) is not MedicalPreparationFacts:
            raise TypeError('medical generation requires its exact explicit preparation')
        replace(self.medical)
        if type(self.tools) is not tuple or any(type(item) is not ToolItemSource for item in self.tools):
            raise TypeError('medical generation requires its exact physical tool sources')
        for item in self.tools:
            replace(item)
        if len({item.id for item in self.tools}) != len(self.tools):
            raise ValueError('medical tool identities cannot repeat inside a source')


def matches_medical_source(npc, source: GeneratedMedicalSource) -> bool:
    """Physical initial sources stay explicit; no repair from a Talent label."""
    if type(source) is not GeneratedMedicalSource:
        raise TypeError('medical membership requires its exact allowed source')
    replace(source)
    return npc.medical == source.medical and all(item in npc.tools for item in source.tools)
