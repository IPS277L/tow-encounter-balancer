from __future__ import annotations

from towr.domain.condition_models import (
    Condition,
    RepeatedConditionReplacement,
)
from towr.domain.resolution_models import ZoneHazardRequest
from towr.domain.test_models import Skill


SOPORIFIC_BREATH_RULE_ID = "RULE-NPC-018:soporific-breath"


def soporific_breath_hazard(
    resolution_id: str,
) -> ZoneHazardRequest:
    """Build the book-defined Hazard for a selected Soporific Breath Zone."""
    return ZoneHazardRequest(
        resolution_id=resolution_id,
        rating=2,
        avoidance_skill=Skill.ENDURANCE,
        rule_id=SOPORIFIC_BREATH_RULE_ID,
        inflicts_wound=True,
        failure_conditions=(Condition.DRAINED,),
        repeated_condition_replacements=(
            RepeatedConditionReplacement(
                condition=Condition.DRAINED,
                replacement=Condition.DEFENCELESS,
                rule_id=SOPORIFIC_BREATH_RULE_ID,
            ),
        ),
    )
