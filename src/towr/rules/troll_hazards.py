from __future__ import annotations

from towr.domain.resolution_models import (
    HazardExposureRequest,
    ZoneHazardRequest,
)
from towr.domain.test_models import Skill


TROLL_VOMIT_RULE_ID = "RULE-NPC-019:troll-vomit"
TROLL_HAG_SWAMP_BREATH_RULE_ID = "RULE-NPC-020:swamp-breath"


def troll_vomit_hazard(
    resolution_id: str,
    test_id: str,
) -> HazardExposureRequest:
    """Build Troll Vomit's Hazard for an already selected legal target."""
    return HazardExposureRequest(
        resolution_id=resolution_id,
        test_id=test_id,
        rating=3,
        avoidance_skill=Skill.ENDURANCE,
        rule_id=TROLL_VOMIT_RULE_ID,
        inflicts_wound=True,
        failure_conditions=(),
    )


def troll_hag_swamp_breath_hazard(
    resolution_id: str,
) -> ZoneHazardRequest:
    """Build Troll Hag Swamp Breath's Hazard for an already selected Zone."""
    return ZoneHazardRequest(
        resolution_id=resolution_id,
        rating=3,
        avoidance_skill=Skill.ENDURANCE,
        rule_id=TROLL_HAG_SWAMP_BREATH_RULE_ID,
        inflicts_wound=True,
        failure_conditions=(),
    )
