"""Explicit allowed Oath acquisition/GM bundles; never fabricated by sampling."""
from dataclasses import dataclass, fields, replace

from towr.domain.oath_context_models import OathBattleContext, validate_oath_context
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import AcquiredTalent, TalentOwnerFacts, validate_acquired_talents


OATH_TALENT_IDS = frozenset((TalentId.HONOUR_BOUND, TalentId.BLESSINGS_OF_THE_LADY))


@dataclass(frozen=True, slots=True)
class GeneratedOathSource:
    talents: tuple[AcquiredTalent, ...]
    context: OathBattleContext
    talent_facts: TalentOwnerFacts

    def __post_init__(self):
        if (type(self.talents) is not tuple or not self.talents
                or any(type(talent) is not AcquiredTalent or talent.id not in OATH_TALENT_IDS
                    for talent in self.talents)):
            raise TypeError('an allowed Oath source requires complete Honour Bound/Lady acquisitions')
        if type(self.talent_facts) is not TalentOwnerFacts:
            raise TypeError('an allowed Oath source requires its explicit initial prerequisite facts')
        replace(self.talent_facts)
        validate_acquired_talents(self.talents, self.talent_facts)
        validate_oath_context(self.talents, self.context)


def merge_oath_facts(existing: TalentOwnerFacts | None, supplied: TalentOwnerFacts) -> TalentOwnerFacts:
    """Combine compatible declared sources without repairing a conflicting fact."""
    existing = TalentOwnerFacts() if existing is None else existing
    for value in (existing, supplied):
        if type(value) is not TalentOwnerFacts:
            raise TypeError('Oath generation retains exact TalentOwnerFacts')
        replace(value)
    updates = {}
    for field in fields(TalentOwnerFacts):
        first, second = getattr(existing, field.name), getattr(supplied, field.name)
        if field.name == 'lores':
            by_id = {lore.id: lore for lore in first}
            for lore in second:
                if lore.id in by_id and by_id[lore.id] != lore:
                    raise ValueError('Oath source conflicts with another actual Lore classification')
                by_id.setdefault(lore.id, lore)
            updates[field.name] = tuple(by_id.values())
        elif field.name == 'equipment':
            updates[field.name] = tuple(dict.fromkeys((*first, *second)))
        elif type(first) is bool:
            updates[field.name] = first or second
        elif first is not None and second is not None and first != second:
            raise ValueError('Oath source conflicts with another actual prerequisite fact: '+field.name)
        else:
            updates[field.name] = first if second is None else second
    return TalentOwnerFacts(**updates)


def matches_oath_source(npc, source: GeneratedOathSource) -> bool:
    if npc.oath_context != source.context:
        return False
    if tuple(talent for talent in npc.talents if talent.id in OATH_TALENT_IDS) != source.talents:
        return False
    actual = npc.talent_facts or TalentOwnerFacts()
    for field in fields(TalentOwnerFacts):
        wanted, got = getattr(source.talent_facts, field.name), getattr(actual, field.name)
        if field.name in ('lores', 'equipment'):
            if not all(value in got for value in wanted):
                return False
        elif type(wanted) is bool:
            if wanted and not got:
                return False
        elif wanted is not None and wanted != got:
            return False
    return True
