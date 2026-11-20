"""Explicit Acrobatic movement/fall provenance, Player's Guide1.4 III73.

Prerequisites belong to acquisition admission. Encounter owners must match
the retained acquisition to this actor's actual source before execution.
"""
from dataclasses import dataclass, replace

from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import AcquiredTalent

ACROBATIC_RULE_ID = 'RULE-TALENT-002:acrobatic'


def _actor(actor):
    if type(actor) is not str or not actor.strip():
        raise TypeError('Acrobatic requires its exact nonempty actor identifier')


@dataclass(frozen=True, slots=True)
class AcrobaticSource:
    actor_id: str
    talent: AcquiredTalent

    def __post_init__(self):
        _actor(self.actor_id)
        if type(self.talent) is not AcquiredTalent:
            raise TypeError('Acrobatic source requires its exact acquired Talent')
        replace(self.talent)
        if self.talent.id is not TalentId.ACROBATIC:
            raise ValueError('another Talent cannot supply Acrobatic movement or falling')


def validate_acrobatic_source(source: AcrobaticSource | None, actor: str) -> bool:
    _actor(actor)
    if source is None:
        return False
    if type(source) is not AcrobaticSource:
        raise TypeError('Acrobatic permission requires its exact typed source or None')
    replace(source)
    if source.actor_id != actor:
        raise ValueError('Acrobatic permission belongs to another actual actor')
    return True


def acrobatic_rule_ids(source: AcrobaticSource | None, actor: str) -> tuple[str,...]:
    return (ACROBATIC_RULE_ID,) if validate_acrobatic_source(source,actor) else ()


def validate_acrobatic_trace(source: AcrobaticSource | None, actor: str, rule_ids: tuple[str,...]) -> None:
    if tuple(rule_ids).count(ACROBATIC_RULE_ID) != int(validate_acrobatic_source(source,actor)):
        raise ValueError('Acrobatic movement trace lost, invented or duplicated its actual Talent source')


def acrobatic_fall_rating(source: AcrobaticSource, actor: str, base_rating: int) -> int:
    if not validate_acrobatic_source(source, actor):
        raise ValueError('a fall reduction requires its actual Acrobatic source')
    if type(base_rating) is not int:
        raise TypeError('fall Hazard requires its exact integer GM base rating')
    if base_rating < 1:
        raise ValueError('the unmodified GM fall Hazard rating must be positive')
    return base_rating // 2


@dataclass(frozen=True, slots=True)
class AcrobaticFallReduction:
    """Declare a genuine fall, retaining its unreduced GM rating and Talent."""
    source: AcrobaticSource
    base_rating: int

    def __post_init__(self):
        if type(self.source) is not AcrobaticSource:
            raise TypeError('fall reduction requires its exact Acrobatic actor source')
        acrobatic_fall_rating(self.source, self.source.actor_id, self.base_rating)

    @property
    def rating(self) -> int:
        return acrobatic_fall_rating(self.source, self.source.actor_id, self.base_rating)
