"""Explicit GM hearing facts for Battlefield Musician (PG73, ADR-0141 C17)."""
from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class BattlefieldMusicAcoustics:
    audible_confirmed: bool
    blocked_zone_pairs: tuple[tuple[str, str], ...] = ()

    def __post_init__(self):
        if type(self.audible_confirmed) is not bool:
            raise TypeError('music audibility requires an explicit GM boolean')
        if type(self.blocked_zone_pairs) is not tuple:
            raise TypeError('acoustic barriers require an ordered tuple of actual Zone pairs')
        seen = set()
        for pair in self.blocked_zone_pairs:
            if (type(pair) is not tuple or len(pair) != 2
                    or any(type(zone) is not str or re.fullmatch(r'(zone|air):-?(0|[1-9][0-9]*)',zone) is None
                        or zone.endswith(':-0') for zone in pair)):
                raise TypeError('each acoustic barrier requires two exact Zone identifiers')
            key = frozenset(pair)
            if len(key) != 2 or key in seen:
                raise ValueError('acoustic barriers require distinct unordered Zone pairs')
            seen.add(key)

    def can_hear(self, first_zone: str, second_zone: str) -> bool:
        return self.audible_confirmed and not any(frozenset(pair) == frozenset((first_zone, second_zone))
            for pair in self.blocked_zone_pairs)
