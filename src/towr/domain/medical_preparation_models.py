"""Actual medical knowledge and GM supply facts, PG1.4 74/98–99/121–122.

These facts neither grant a Talent nor create a tool or a Skill rating.
Recovery supports are declared for the actual Wounds they can accommodate.
"""
from dataclasses import dataclass

from towr.domain.injury_models import WoundEntryId


@dataclass(frozen=True, slots=True)
class MedicalPreparationFacts:
    anatomy_lore: bool
    treatment_supplies: bool
    surgery_supplies: bool
    recovery_supports: tuple[WoundEntryId, ...] = ()
    self_treatment_modifier: int = 0
    makeshift_modifier: int | None = None

    def __post_init__(self):
        for value in (self.anatomy_lore,self.treatment_supplies,self.surgery_supplies):
            if type(value) is not bool:
                raise TypeError('medical preparation requires exact knowledge and GM supply booleans')
        if (type(self.recovery_supports) is not tuple
                or any(type(entry) is not WoundEntryId for entry in self.recovery_supports)
                or len(set(self.recovery_supports)) != len(self.recovery_supports)):
            raise TypeError('medical recovery supports retain distinct ordered actual Wound entry IDs')
        if type(self.self_treatment_modifier) is not int or self.self_treatment_modifier > 0:
            raise ValueError('self-treatment difficulty must be an exact nonpositive dice modifier')
        if self.makeshift_modifier is not None and (
                type(self.makeshift_modifier) is not int or self.makeshift_modifier >= 0):
            raise ValueError('explicit makeshift treatment requires a strictly negative difficulty modifier')
