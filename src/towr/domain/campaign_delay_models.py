from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CampaignDelayConsequence:
    """Registered Lost delay; travel and time advancement are later boundaries."""

    id: str
    campaign_id: str
    unfamiliar_territory_reference_id: str
    intended_destination_reference_id: str
    return_delay_reference_id: str
    enemy_opportunity_reference_id: str
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
            (self.id, "campaign delay consequence id"),
            (self.campaign_id, "campaign delay campaign_id"),
            (
                self.unfamiliar_territory_reference_id,
                "campaign delay unfamiliar_territory_reference_id",
            ),
            (
                self.intended_destination_reference_id,
                "campaign delay intended_destination_reference_id",
            ),
            (
                self.return_delay_reference_id,
                "campaign delay return_delay_reference_id",
            ),
            (
                self.enemy_opportunity_reference_id,
                "campaign delay enemy_opportunity_reference_id",
            ),
            (self.description_reference_id, "campaign delay description_reference_id"),
            (self.source_application_id, "campaign delay source_application_id"),
            (self.source_consequence_id, "campaign delay source_consequence_id"),
            (
                self.source_specification_id,
                "campaign delay source_specification_id",
            ),
            (self.battle_id, "campaign delay battle_id"),
            (self.retreat_id, "campaign delay retreat_id"),
            (self.rule_id, "campaign delay rule_id"),
        ):
            _validate_non_empty_string(value, name)
        _validate_unique_values(
            (
                self.unfamiliar_territory_reference_id,
                self.intended_destination_reference_id,
                self.return_delay_reference_id,
                self.enemy_opportunity_reference_id,
            ),
            "campaign delay role references",
        )
        subjects = _validate_unique_non_empty_ids(
            self.affected_subject_reference_ids,
            "campaign delay affected subject reference ID",
        )
        object.__setattr__(self, "affected_subject_reference_ids", subjects)


@dataclass(frozen=True, slots=True)
class CampaignDelayState:
    """Narrow aggregate of registered campaign delays."""

    campaign_id: str
    consequences: tuple[CampaignDelayConsequence, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.campaign_id, "campaign delay campaign_id")
        consequences = tuple(self.consequences)
        if not all(
            isinstance(item, CampaignDelayConsequence) for item in consequences
        ):
            raise TypeError(
                "consequences must contain CampaignDelayConsequence values"
            )
        if any(item.campaign_id != self.campaign_id for item in consequences):
            raise ValueError("all delay consequences must belong to the campaign")
        _validate_unique_values(
            tuple(item.id for item in consequences),
            "campaign delay consequence IDs",
        )
        _validate_unique_values(
            tuple(item.source_consequence_id for item in consequences),
            "campaign delay source consequence IDs",
        )
        object.__setattr__(self, "consequences", consequences)

    def has_source_consequence(self, consequence_id: str) -> bool:
        _validate_non_empty_string(
            consequence_id,
            "campaign delay source consequence id",
        )
        return any(
            item.source_consequence_id == consequence_id
            for item in self.consequences
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
