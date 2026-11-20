"""Prepare an explicit opposed-Test tie-break from source-bound preferences.

PG1.4 V109/III80; the opposing-preferences interpretation is ADR-0141 C2.
This helper neither establishes Talent ownership nor authorises its use. The
caller must derive each preference from the actual participants and Test.
The ordinary resolver still owns non-ties and the special double-zero case.
"""
from dataclasses import replace

from towr.domain.test_models import OpposedSide, TieBreak


def _validate_source(value: TieBreak) -> None:
    if type(value) is not TieBreak:
        raise TypeError('a tie source requires an exact typed TieBreak')
    if type(value.rule_id) is not str:
        raise TypeError('a tie source requires an exact string rule ID')
    if value.rule_id != value.rule_id.strip():
        raise ValueError('a tie source rule ID cannot contain surrounding whitespace')
    if type(value.winner) is not OpposedSide:
        raise TypeError('a tie source requires its exact typed opposed side')
    # Cached frozen values may have been changed outside their constructor.
    replace(value)


def _part(value: str) -> str:
    """Length-prefix identifiers so punctuation cannot alias another source."""
    return f'{len(value)}:{value}'


def compose_talent_tie_break(ordinary: TieBreak,
        preferences: tuple[TieBreak, ...]) -> TieBreak:
    """Opposing special preferences cancel; agreeing ones preserve all sources.

    A cancellation is not a majority vote, nor a preference for the last item.
    It returns the actual ordinary source unchanged. A one-sided result uses
    a canonical provenance ID containing the ordinary rule/side and every
    distinct contributing rule, independent of the caller's tuple order.
    """
    _validate_source(ordinary)
    if type(preferences) is not tuple:
        raise TypeError('tie preferences require an exact ordered tuple')
    seen = {ordinary.rule_id}
    for preference in preferences:
        _validate_source(preference)
        if preference.rule_id in seen:
            raise ValueError('tie preferences cannot duplicate or alias a source rule')
        seen.add(preference.rule_id)

    sides = {preference.winner for preference in preferences}
    if len(sides) != 1:
        return ordinary

    winner = next(iter(sides))
    ordered = sorted(preference.rule_id for preference in preferences)
    provenance = (_part(ordinary.rule_id) + _part(ordinary.winner.value)
        + f'{len(ordered)}:' + ''.join(_part(rule_id) for rule_id in ordered))
    return TieBreak('RULE-TALENT-002:tie-preferences:' + provenance, winner)
