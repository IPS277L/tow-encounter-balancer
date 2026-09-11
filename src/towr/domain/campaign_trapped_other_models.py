from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CampaignTrappedOtherCost:
    """Opaque GM-defined Trapped price awaiting a specialised consumer."""

    id: str
    campaign_id: str
    affected_actor_ids: tuple[str, ...]
    consequence_reference_ids: tuple[str, ...]
    description_reference_id: str
    source_application_id: str
    source_proof_id: str
    source_consequence_id: str
    source_specification_id: str
    source_decision_id: str
    battle_id: str
    retreat_id: str
    rule_id: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.id, "campaign Trapped other cost id"),
            (self.campaign_id, "campaign Trapped other campaign_id"),
            (
                self.description_reference_id,
                "campaign Trapped other description_reference_id",
            ),
            (
                self.source_application_id,
                "campaign Trapped other source_application_id",
            ),
            (self.source_proof_id, "campaign Trapped other source_proof_id"),
            (
                self.source_consequence_id,
                "campaign Trapped other source_consequence_id",
            ),
            (
                self.source_specification_id,
                "campaign Trapped other source_specification_id",
            ),
            (self.source_decision_id, "campaign Trapped other source_decision_id"),
            (self.battle_id, "campaign Trapped other battle_id"),
            (self.retreat_id, "campaign Trapped other retreat_id"),
            (self.rule_id, "campaign Trapped other rule_id"),
        ):
            _validate_non_empty_string(value, name)
        actors = _validate_unique_non_empty_ids(
            self.affected_actor_ids,
            "campaign Trapped other affected actor ID",
        )
        references = _validate_unique_non_empty_ids(
            self.consequence_reference_ids,
            "campaign Trapped other consequence reference ID",
        )
        object.__setattr__(self, "affected_actor_ids", actors)
        object.__setattr__(self, "consequence_reference_ids", references)


@dataclass(frozen=True, slots=True)
class CampaignTrappedOtherState:
    """Narrow aggregate of unresolved GM-defined Trapped prices."""

    campaign_id: str
    costs: tuple[CampaignTrappedOtherCost, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.campaign_id,
            "campaign Trapped other campaign_id",
        )
        costs = tuple(self.costs)
        if not all(isinstance(item, CampaignTrappedOtherCost) for item in costs):
            raise TypeError("costs must contain CampaignTrappedOtherCost values")
        if any(item.campaign_id != self.campaign_id for item in costs):
            raise ValueError("all Trapped other costs must belong to the campaign")
        _validate_unique_values(
            tuple(item.id for item in costs),
            "campaign Trapped other cost IDs",
        )
        _validate_unique_values(
            tuple(item.source_application_id for item in costs),
            "campaign Trapped other source application IDs",
        )
        object.__setattr__(self, "costs", costs)

    def has_source_application(self, application_id: str) -> bool:
        _validate_non_empty_string(
            application_id,
            "campaign Trapped other source application id",
        )
        return any(
            item.source_application_id == application_id for item in self.costs
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
