from __future__ import annotations

from towr.domain.injury_models import (
    HealingRequirement,
    WoundEntryId,
    WoundTableEntry,
)


WOUND_TABLE: tuple[WoundTableEntry, ...] = (
    WoundTableEntry(
        WoundEntryId.SUPERFICIAL_INJURY,
        1,
        3,
        HealingRequirement.CATCH_YOUR_BREATH,
        False,
    ),
    WoundTableEntry(WoundEntryId.NICKED_ARM, 4, 4, HealingRequirement.CATCH_YOUR_BREATH, False),
    WoundTableEntry(WoundEntryId.BATTERED_LEG, 5, 5, HealingRequirement.CATCH_YOUR_BREATH, False),
    WoundTableEntry(WoundEntryId.STOMACH_BLOW, 6, 6, HealingRequirement.CATCH_YOUR_BREATH, False),
    WoundTableEntry(WoundEntryId.GASHED_BROW, 7, 7, HealingRequirement.CATCH_YOUR_BREATH, False),
    WoundTableEntry(WoundEntryId.SHAKING_GRIP, 8, 8, HealingRequirement.NIGHTS_REST, False),
    WoundTableEntry(WoundEntryId.LEG_SPASM, 9, 9, HealingRequirement.NIGHTS_REST, False),
    WoundTableEntry(WoundEntryId.CRUSHED_RIB, 10, 10, HealingRequirement.NIGHTS_REST, False),
    WoundTableEntry(WoundEntryId.EARS_RINGING, 11, 11, HealingRequirement.NIGHTS_REST, False),
    WoundTableEntry(WoundEntryId.SMASHED_HAND, 12, 12, HealingRequirement.NIGHTS_REST, False),
    WoundTableEntry(WoundEntryId.TORN_LEG, 13, 13, HealingRequirement.NIGHTS_REST, False),
    WoundTableEntry(WoundEntryId.INTERNAL_INJURY, 14, 14, HealingRequirement.NIGHTS_REST, False),
    WoundTableEntry(WoundEntryId.SCARRING_STRIKE, 15, 15, HealingRequirement.NIGHTS_REST, False),
    WoundTableEntry(
        WoundEntryId.SLASHED_FOREARMS,
        16,
        16,
        HealingRequirement.REST_AND_RECOVERY,
        False,
    ),
    WoundTableEntry(
        WoundEntryId.SHATTERED_KNEE,
        17,
        17,
        HealingRequirement.REST_AND_RECOVERY,
        False,
    ),
    WoundTableEntry(
        WoundEntryId.SPILLING_GUTS,
        18,
        18,
        HealingRequirement.REST_AND_RECOVERY,
        False,
    ),
    WoundTableEntry(WoundEntryId.BLACKING_OUT, 19, 19, HealingRequirement.REST_AND_RECOVERY, False),
    WoundTableEntry(
        WoundEntryId.SEVERED_ARM,
        20,
        20,
        HealingRequirement.SURGERY_AND_RECOVERY,
        False,
    ),
    WoundTableEntry(
        WoundEntryId.SEVERED_LEG,
        21,
        21,
        HealingRequirement.SURGERY_AND_RECOVERY,
        False,
    ),
    WoundTableEntry(
        WoundEntryId.RUPTURED_ORGANS,
        22,
        22,
        HealingRequirement.SURGERY_AND_RECOVERY,
        False,
    ),
    WoundTableEntry(
        WoundEntryId.RUINED_EYES,
        23,
        23,
        HealingRequirement.SURGERY_AND_RECOVERY,
        False,
    ),
    WoundTableEntry(WoundEntryId.APPALLING_STRIKE, 24, 24, HealingRequirement.NOT_APPLICABLE, True),
    WoundTableEntry(WoundEntryId.BISECTION, 25, 25, HealingRequirement.NOT_APPLICABLE, True),
    WoundTableEntry(WoundEntryId.PIERCED_HEART, 26, 26, HealingRequirement.NOT_APPLICABLE, True),
    WoundTableEntry(WoundEntryId.DECAPITATION, 27, None, HealingRequirement.NOT_APPLICABLE, True),
)


def lookup_wound(total: int) -> WoundTableEntry:
    if not isinstance(total, int) or isinstance(total, bool):
        raise TypeError("wound table total must be an integer")
    if total < 1:
        raise ValueError("wound table total must be positive")
    for entry in WOUND_TABLE:
        if entry.includes(total):
            return entry
    raise AssertionError(f"unmapped wound table total: {total}")
