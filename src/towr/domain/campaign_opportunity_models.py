from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CampaignGoldenOpportunity:
    """A registered GM-authored opportunity; executing it is a later boundary."""

    id: str
    campaign_id: str
    beneficiary_enemy_id: str
    description_reference_id: str
    source_application_id: str
    battle_id: str
    retreat_id: str
    rule_id: str

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "golden opportunity id")
        _validate_non_empty_string(self.campaign_id, "campaign id")
        _validate_non_empty_string(
            self.beneficiary_enemy_id,
            "golden opportunity beneficiary_enemy_id",
        )
        _validate_non_empty_string(
            self.description_reference_id,
            "golden opportunity description_reference_id",
        )
        _validate_non_empty_string(
            self.source_application_id,
            "golden opportunity source_application_id",
        )
        _validate_non_empty_string(self.battle_id, "golden opportunity battle_id")
        _validate_non_empty_string(self.retreat_id, "golden opportunity retreat_id")
        _validate_non_empty_string(self.rule_id, "golden opportunity rule_id")


@dataclass(frozen=True, slots=True)
class CampaignGoldenOpportunityState:
    """Narrow campaign aggregate for pending and historical opportunities."""

    campaign_id: str
    opportunities: tuple[CampaignGoldenOpportunity, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.campaign_id, "campaign id")
        opportunities = tuple(self.opportunities)
        if not all(
            isinstance(opportunity, CampaignGoldenOpportunity)
            for opportunity in opportunities
        ):
            raise TypeError(
                "opportunities must contain CampaignGoldenOpportunity values"
            )
        if any(
            opportunity.campaign_id != self.campaign_id
            for opportunity in opportunities
        ):
            raise ValueError("all golden opportunities must belong to the campaign")
        _validate_unique_values(
            tuple(opportunity.id for opportunity in opportunities),
            "golden opportunity IDs",
        )
        _validate_unique_values(
            tuple(
                opportunity.source_application_id
                for opportunity in opportunities
            ),
            "golden opportunity source application IDs",
        )
        object.__setattr__(self, "opportunities", opportunities)

    def has_source_application(self, application_id: str) -> bool:
        _validate_non_empty_string(application_id, "source application id")
        return any(
            opportunity.source_application_id == application_id
            for opportunity in self.opportunities
        )


def _validate_unique_values(values: tuple[str, ...], name: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
