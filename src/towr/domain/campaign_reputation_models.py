from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CampaignReputationConsequence:
    """Registered reputational harm; social mechanics are a later boundary."""

    id: str
    campaign_id: str
    witness_reference_ids: tuple[str, ...]
    gossip_incident_reference_id: str
    reputation_effect_reference_id: str
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
            (self.id, "campaign reputation consequence id"),
            (self.campaign_id, "campaign reputation campaign_id"),
            (
                self.gossip_incident_reference_id,
                "campaign reputation gossip_incident_reference_id",
            ),
            (
                self.reputation_effect_reference_id,
                "campaign reputation reputation_effect_reference_id",
            ),
            (
                self.description_reference_id,
                "campaign reputation description_reference_id",
            ),
            (
                self.source_application_id,
                "campaign reputation source_application_id",
            ),
            (
                self.source_consequence_id,
                "campaign reputation source_consequence_id",
            ),
            (
                self.source_specification_id,
                "campaign reputation source_specification_id",
            ),
            (self.battle_id, "campaign reputation battle_id"),
            (self.retreat_id, "campaign reputation retreat_id"),
            (self.rule_id, "campaign reputation rule_id"),
        ):
            _validate_non_empty_string(value, name)
        witnesses = _validate_unique_non_empty_ids(
            self.witness_reference_ids,
            "campaign reputation witness reference ID",
        )
        _validate_unique_values(
            (
                *witnesses,
                self.gossip_incident_reference_id,
                self.reputation_effect_reference_id,
            ),
            "campaign reputation role references",
        )
        subjects = _validate_unique_non_empty_ids(
            self.affected_subject_reference_ids,
            "campaign reputation affected subject reference ID",
        )
        object.__setattr__(self, "witness_reference_ids", witnesses)
        object.__setattr__(self, "affected_subject_reference_ids", subjects)


@dataclass(frozen=True, slots=True)
class CampaignReputationState:
    """Narrow aggregate of registered reputation consequences."""

    campaign_id: str
    consequences: tuple[CampaignReputationConsequence, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.campaign_id,
            "campaign reputation campaign_id",
        )
        consequences = tuple(self.consequences)
        if not all(
            isinstance(item, CampaignReputationConsequence)
            for item in consequences
        ):
            raise TypeError(
                "consequences must contain CampaignReputationConsequence values"
            )
        if any(item.campaign_id != self.campaign_id for item in consequences):
            raise ValueError(
                "all reputation consequences must belong to the campaign"
            )
        _validate_unique_values(
            tuple(item.id for item in consequences),
            "campaign reputation consequence IDs",
        )
        _validate_unique_values(
            tuple(item.source_consequence_id for item in consequences),
            "campaign reputation source consequence IDs",
        )
        object.__setattr__(self, "consequences", consequences)

    def has_source_consequence(self, consequence_id: str) -> bool:
        _validate_non_empty_string(
            consequence_id,
            "campaign reputation source consequence id",
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
