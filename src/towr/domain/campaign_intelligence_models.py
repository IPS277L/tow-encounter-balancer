from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CampaignIntelligenceExposure:
    """Registered knowledge gained by an enemy; exploiting it is a later boundary."""

    id: str
    campaign_id: str
    enemy_reference_id: str
    home_reference_id: str
    shelter_reference_ids: tuple[str, ...]
    weakness_reference_id: str
    description_reference_id: str
    affected_subject_reference_ids: tuple[str, ...]
    source_application_id: str
    source_consequence_id: str
    source_specification_id: str
    battle_id: str
    retreat_id: str
    rule_id: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.id, "campaign intelligence exposure id"),
            (self.campaign_id, "campaign intelligence campaign_id"),
            (
                self.enemy_reference_id,
                "campaign intelligence enemy_reference_id",
            ),
            (
                self.home_reference_id,
                "campaign intelligence home_reference_id",
            ),
            (
                self.weakness_reference_id,
                "campaign intelligence weakness_reference_id",
            ),
            (
                self.description_reference_id,
                "campaign intelligence description_reference_id",
            ),
            (
                self.source_application_id,
                "campaign intelligence source_application_id",
            ),
            (
                self.source_consequence_id,
                "campaign intelligence source_consequence_id",
            ),
            (
                self.source_specification_id,
                "campaign intelligence source_specification_id",
            ),
            (self.battle_id, "campaign intelligence battle_id"),
            (self.retreat_id, "campaign intelligence retreat_id"),
            (self.rule_id, "campaign intelligence rule_id"),
        ):
            _validate_non_empty_string(value, name)
        shelters = _validate_unique_non_empty_ids(
            self.shelter_reference_ids,
            "campaign intelligence shelter reference ID",
        )
        subjects = _validate_unique_non_empty_ids(
            self.affected_subject_reference_ids,
            "campaign intelligence affected subject reference ID",
        )
        role_references = (
            self.enemy_reference_id,
            self.home_reference_id,
            *shelters,
            self.weakness_reference_id,
        )
        _validate_unique_values(
            role_references,
            "campaign intelligence role references",
        )
        object.__setattr__(self, "shelter_reference_ids", shelters)
        object.__setattr__(self, "affected_subject_reference_ids", subjects)


@dataclass(frozen=True, slots=True)
class CampaignIntelligenceState:
    """Narrow aggregate of registered enemy intelligence disclosures."""

    campaign_id: str
    exposures: tuple[CampaignIntelligenceExposure, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.campaign_id,
            "campaign intelligence campaign_id",
        )
        exposures = tuple(self.exposures)
        if not all(
            isinstance(item, CampaignIntelligenceExposure) for item in exposures
        ):
            raise TypeError(
                "exposures must contain CampaignIntelligenceExposure values"
            )
        if any(item.campaign_id != self.campaign_id for item in exposures):
            raise ValueError(
                "all intelligence exposures must belong to the campaign"
            )
        _validate_unique_values(
            tuple(item.id for item in exposures),
            "campaign intelligence exposure IDs",
        )
        _validate_unique_values(
            tuple(item.source_consequence_id for item in exposures),
            "campaign intelligence source consequence IDs",
        )
        object.__setattr__(self, "exposures", exposures)

    def has_source_consequence(self, consequence_id: str) -> bool:
        _validate_non_empty_string(
            consequence_id,
            "campaign intelligence source consequence id",
        )
        return any(
            item.source_consequence_id == consequence_id for item in self.exposures
        )


def _validate_unique_non_empty_ids(
    values: tuple[str, ...],
    name: str,
) -> tuple[str, ...]:
    ids = tuple(values)
    if not ids:
        raise ValueError(f"{name}s must not be empty")
    for value in ids:
        _validate_non_empty_string(value, name)
    _validate_unique_values(ids, f"{name}s")
    return ids


def _validate_unique_values(values: tuple[str, ...], name: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
