from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CampaignConflictOpportunity:
    """One registered conflict hook; resolving or starting it is a later boundary."""

    id: str
    campaign_id: str
    opposition_reference_id: str
    encounter_setup_reference_id: str
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
            (self.id, "campaign conflict opportunity id"),
            (self.campaign_id, "campaign conflict campaign_id"),
            (
                self.opposition_reference_id,
                "campaign conflict opposition_reference_id",
            ),
            (
                self.encounter_setup_reference_id,
                "campaign conflict encounter_setup_reference_id",
            ),
            (
                self.description_reference_id,
                "campaign conflict description_reference_id",
            ),
            (
                self.source_application_id,
                "campaign conflict source_application_id",
            ),
            (
                self.source_consequence_id,
                "campaign conflict source_consequence_id",
            ),
            (
                self.source_specification_id,
                "campaign conflict source_specification_id",
            ),
            (self.battle_id, "campaign conflict battle_id"),
            (self.retreat_id, "campaign conflict retreat_id"),
            (self.rule_id, "campaign conflict rule_id"),
        ):
            _validate_non_empty_string(value, name)
        if self.opposition_reference_id == self.encounter_setup_reference_id:
            raise ValueError(
                "campaign conflict opposition and encounter setup references "
                "must be distinct"
            )
        subjects = _validate_unique_non_empty_ids(
            self.affected_subject_reference_ids,
            "campaign conflict affected subject reference ID",
        )
        object.__setattr__(self, "affected_subject_reference_ids", subjects)


@dataclass(frozen=True, slots=True)
class CampaignConflictOpportunityState:
    """Narrow campaign aggregate of registered conflict opportunities."""

    campaign_id: str
    opportunities: tuple[CampaignConflictOpportunity, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.campaign_id, "campaign conflict campaign_id")
        opportunities = tuple(self.opportunities)
        if not all(
            isinstance(item, CampaignConflictOpportunity) for item in opportunities
        ):
            raise TypeError(
                "opportunities must contain CampaignConflictOpportunity values"
            )
        if any(item.campaign_id != self.campaign_id for item in opportunities):
            raise ValueError("all conflict opportunities must belong to the campaign")
        _validate_unique_values(
            tuple(item.id for item in opportunities),
            "campaign conflict opportunity IDs",
        )
        _validate_unique_values(
            tuple(item.source_consequence_id for item in opportunities),
            "campaign conflict source consequence IDs",
        )
        object.__setattr__(self, "opportunities", opportunities)

    def has_source_consequence(self, consequence_id: str) -> bool:
        _validate_non_empty_string(
            consequence_id,
            "campaign conflict source consequence id",
        )
        return any(
            item.source_consequence_id == consequence_id
            for item in self.opportunities
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
