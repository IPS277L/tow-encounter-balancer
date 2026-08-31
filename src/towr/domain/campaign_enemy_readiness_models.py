from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CampaignEnemyReadiness:
    """Enemy preparedness registered by Marked; its effect is external."""

    id: str
    campaign_id: str
    enemy_reference_id: str
    acquired_intelligence_reference_id: str
    next_action_trigger_reference_id: str
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
            (self.id, "campaign enemy readiness id"),
            (self.campaign_id, "campaign enemy readiness campaign_id"),
            (self.enemy_reference_id, "campaign enemy readiness enemy_reference_id"),
            (
                self.acquired_intelligence_reference_id,
                "campaign enemy readiness acquired_intelligence_reference_id",
            ),
            (
                self.next_action_trigger_reference_id,
                "campaign enemy readiness next_action_trigger_reference_id",
            ),
            (
                self.description_reference_id,
                "campaign enemy readiness description_reference_id",
            ),
            (
                self.source_application_id,
                "campaign enemy readiness source_application_id",
            ),
            (
                self.source_consequence_id,
                "campaign enemy readiness source_consequence_id",
            ),
            (
                self.source_specification_id,
                "campaign enemy readiness source_specification_id",
            ),
            (self.battle_id, "campaign enemy readiness battle_id"),
            (self.retreat_id, "campaign enemy readiness retreat_id"),
            (self.rule_id, "campaign enemy readiness rule_id"),
        ):
            _validate_non_empty_string(value, name)
        _validate_unique_values(
            (
                self.enemy_reference_id,
                self.acquired_intelligence_reference_id,
                self.next_action_trigger_reference_id,
            ),
            "campaign enemy readiness role references",
        )
        subjects = _validate_unique_non_empty_ids(
            self.affected_subject_reference_ids,
            "campaign enemy readiness affected subject reference ID",
        )
        object.__setattr__(self, "affected_subject_reference_ids", subjects)


@dataclass(frozen=True, slots=True)
class CampaignEnemyReadinessActivation:
    """Proof that the next matching action against the enemy occurred."""

    id: str
    campaign_id: str
    readiness_id: str
    enemy_reference_id: str
    next_action_trigger_reference_id: str
    action_event_reference_id: str
    rule_id: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.id, "campaign enemy readiness activation id"),
            (self.campaign_id, "campaign enemy readiness activation campaign_id"),
            (self.readiness_id, "campaign enemy readiness activation readiness_id"),
            (
                self.enemy_reference_id,
                "campaign enemy readiness activation enemy_reference_id",
            ),
            (
                self.next_action_trigger_reference_id,
                "campaign enemy readiness activation next_action_trigger_reference_id",
            ),
            (
                self.action_event_reference_id,
                "campaign enemy readiness activation action_event_reference_id",
            ),
            (self.rule_id, "campaign enemy readiness activation rule_id"),
        ):
            _validate_non_empty_string(value, name)
        _validate_unique_values(
            (
                self.next_action_trigger_reference_id,
                self.action_event_reference_id,
            ),
            "campaign enemy readiness activation event references",
        )


@dataclass(frozen=True, slots=True)
class CampaignEnemyReadinessState:
    """Narrow aggregate of Marked readiness records and matched actions."""

    campaign_id: str
    readiness_records: tuple[CampaignEnemyReadiness, ...] = field(
        default_factory=tuple
    )
    activations: tuple[CampaignEnemyReadinessActivation, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.campaign_id,
            "campaign enemy readiness campaign_id",
        )
        readiness_records = tuple(self.readiness_records)
        activations = tuple(self.activations)
        if not all(
            isinstance(item, CampaignEnemyReadiness) for item in readiness_records
        ):
            raise TypeError(
                "readiness_records must contain CampaignEnemyReadiness values"
            )
        if not all(
            isinstance(item, CampaignEnemyReadinessActivation)
            for item in activations
        ):
            raise TypeError(
                "activations must contain CampaignEnemyReadinessActivation values"
            )
        if any(item.campaign_id != self.campaign_id for item in readiness_records):
            raise ValueError("all enemy readiness records must belong to the campaign")
        if any(item.campaign_id != self.campaign_id for item in activations):
            raise ValueError(
                "all enemy readiness activations must belong to the campaign"
            )
        _validate_unique_values(
            tuple(item.id for item in readiness_records),
            "campaign enemy readiness IDs",
        )
        _validate_unique_values(
            tuple(item.source_consequence_id for item in readiness_records),
            "campaign enemy readiness source consequence IDs",
        )
        _validate_unique_values(
            tuple(item.id for item in activations),
            "campaign enemy readiness activation IDs",
        )
        _validate_unique_values(
            tuple(item.readiness_id for item in activations),
            "activated campaign enemy readiness IDs",
        )
        readiness_by_id = {item.id: item for item in readiness_records}
        for activation in activations:
            readiness = readiness_by_id.get(activation.readiness_id)
            if readiness is None:
                raise ValueError(
                    "campaign enemy readiness activation has no registered readiness"
                )
            if activation.enemy_reference_id != readiness.enemy_reference_id:
                raise ValueError(
                    "campaign enemy readiness activation disagrees with enemy"
                )
            if (
                activation.next_action_trigger_reference_id
                != readiness.next_action_trigger_reference_id
            ):
                raise ValueError(
                    "campaign enemy readiness activation disagrees with trigger"
                )
            if activation.rule_id != readiness.rule_id:
                raise ValueError(
                    "campaign enemy readiness activation uses another rule"
                )
        object.__setattr__(self, "readiness_records", readiness_records)
        object.__setattr__(self, "activations", activations)

    def readiness(self, readiness_id: str) -> CampaignEnemyReadiness | None:
        _validate_non_empty_string(readiness_id, "campaign enemy readiness id")
        return next(
            (item for item in self.readiness_records if item.id == readiness_id),
            None,
        )

    def has_source_consequence(self, consequence_id: str) -> bool:
        _validate_non_empty_string(
            consequence_id,
            "campaign enemy readiness source consequence id",
        )
        return any(
            item.source_consequence_id == consequence_id
            for item in self.readiness_records
        )

    def is_activated(self, readiness_id: str) -> bool:
        _validate_non_empty_string(readiness_id, "campaign enemy readiness id")
        return any(item.readiness_id == readiness_id for item in self.activations)


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
