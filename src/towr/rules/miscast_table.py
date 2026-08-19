from __future__ import annotations

from towr.domain.magic_models import MiscastTableEntry, MiscastTableEntryId


MISCAST_TABLE: tuple[MiscastTableEntry, ...] = (
    MiscastTableEntry(MiscastTableEntryId.SENSE_OF_LOSS, 1, 2),
    MiscastTableEntry(MiscastTableEntryId.NAUSEATING_WAVE, 3, 4),
    MiscastTableEntry(MiscastTableEntryId.OBJECTS_TRANSFIGURED, 5, 6),
    MiscastTableEntry(MiscastTableEntryId.SHADOW_CHITTERING, 7, 8),
    MiscastTableEntry(MiscastTableEntryId.FOOD_SPOILED, 9, 10),
    MiscastTableEntry(MiscastTableEntryId.ARCANE_SPILL, 11, 12),
    MiscastTableEntry(MiscastTableEntryId.HIDEOUS_STENCH, 13, 14),
    MiscastTableEntry(MiscastTableEntryId.UNNATURAL_WEATHER, 15, 16),
    MiscastTableEntry(MiscastTableEntryId.RANDOM_TRANSPORT, 17, 18),
    MiscastTableEntry(MiscastTableEntryId.SUNLIGHT_BLINDNESS, 19, 20),
    MiscastTableEntry(MiscastTableEntryId.UNNATURAL_WIND, 21, 22),
    MiscastTableEntry(MiscastTableEntryId.SPELL_RECAST, 23, 24),
    MiscastTableEntry(MiscastTableEntryId.TRUTHBOUND, 25, 26),
    MiscastTableEntry(MiscastTableEntryId.ARCANE_SIGHT, 27, 28),
    MiscastTableEntry(MiscastTableEntryId.FEARED_FOE_ILLUSION, 29, 30),
    MiscastTableEntry(MiscastTableEntryId.INTERNAL_DAMAGE, 31, 32),
    MiscastTableEntry(MiscastTableEntryId.ZONE_HAZARD, 33, 34),
    MiscastTableEntry(MiscastTableEntryId.EAR_DAMAGE, 35, 36),
    MiscastTableEntry(MiscastTableEntryId.DAEMON_RIFT, 37, 37),
    MiscastTableEntry(MiscastTableEntryId.FASCINATING_RIFT, 38, 38),
    MiscastTableEntry(MiscastTableEntryId.CATASTROPHIC_DEATH, 39, None),
)


def lookup_miscast(total: int) -> MiscastTableEntry:
    if not isinstance(total, int) or isinstance(total, bool):
        raise TypeError("Miscast table total must be an integer")
    if total < 1:
        raise ValueError("Miscast table total must be positive")
    for entry in MISCAST_TABLE:
        if entry.includes(total):
            return entry
    raise AssertionError(f"unmapped Miscast table total: {total}")
