from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CampaignHuntThreat:
    """One registered Hunted threat; activation is recorded separately."""

    id: str
    campaign_id: str
    pursuer_reference_id: str
    activation_trigger_reference_id: str
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
            (self.id, "campaign hunt threat id"),
            (self.campaign_id, "campaign hunt campaign_id"),
            (self.pursuer_reference_id, "campaign hunt pursuer_reference_id"),
            (
                self.activation_trigger_reference_id,
                "campaign hunt activation_trigger_reference_id",
            ),
            (
                self.description_reference_id,
                "campaign hunt description_reference_id",
            ),
            (
                self.source_application_id,
                "campaign hunt source_application_id",
            ),
            (
                self.source_consequence_id,
                "campaign hunt source_consequence_id",
            ),
            (
                self.source_specification_id,
                "campaign hunt source_specification_id",
            ),
            (self.battle_id, "campaign hunt battle_id"),
            (self.retreat_id, "campaign hunt retreat_id"),
            (self.rule_id, "campaign hunt rule_id"),
        ):
            _validate_non_empty_string(value, name)
        if self.pursuer_reference_id == self.activation_trigger_reference_id:
            raise ValueError(
                "campaign hunt pursuer and activation trigger references "
                "must be distinct"
            )
        subjects = _validate_unique_non_empty_ids(
            self.affected_subject_reference_ids,
            "campaign hunt affected subject reference ID",
        )
        object.__setattr__(self, "affected_subject_reference_ids", subjects)


@dataclass(frozen=True, slots=True)
class CampaignHuntActivation:
    """Proof that one registered threat was activated by an external movement fact."""

    id: str
    campaign_id: str
    threat_id: str
    activation_trigger_reference_id: str
    movement_event_reference_id: str
    rule_id: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.id, "campaign hunt activation id"),
            (self.campaign_id, "campaign hunt activation campaign_id"),
            (self.threat_id, "campaign hunt activation threat_id"),
            (
                self.activation_trigger_reference_id,
                "campaign hunt activation trigger reference id",
            ),
            (
                self.movement_event_reference_id,
                "campaign hunt movement event reference id",
            ),
            (self.rule_id, "campaign hunt activation rule_id"),
        ):
            _validate_non_empty_string(value, name)
        if (
            self.activation_trigger_reference_id
            == self.movement_event_reference_id
        ):
            raise ValueError(
                "campaign hunt trigger and movement event references must be distinct"
            )


@dataclass(frozen=True, slots=True)
class CampaignHuntState:
    """Narrow aggregate of registered Hunted threats and their activations."""

    campaign_id: str
    threats: tuple[CampaignHuntThreat, ...] = field(default_factory=tuple)
    activations: tuple[CampaignHuntActivation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.campaign_id, "campaign hunt campaign_id")
        threats = tuple(self.threats)
        activations = tuple(self.activations)
        if not all(isinstance(item, CampaignHuntThreat) for item in threats):
            raise TypeError("threats must contain CampaignHuntThreat values")
        if not all(
            isinstance(item, CampaignHuntActivation) for item in activations
        ):
            raise TypeError(
                "activations must contain CampaignHuntActivation values"
            )
        if any(item.campaign_id != self.campaign_id for item in threats):
            raise ValueError("all hunt threats must belong to the campaign")
        if any(item.campaign_id != self.campaign_id for item in activations):
            raise ValueError("all hunt activations must belong to the campaign")
        _validate_unique_values(
            tuple(item.id for item in threats),
            "campaign hunt threat IDs",
        )
        _validate_unique_values(
            tuple(item.source_consequence_id for item in threats),
            "campaign hunt source consequence IDs",
        )
        _validate_unique_values(
            tuple(item.id for item in activations),
            "campaign hunt activation IDs",
        )
        _validate_unique_values(
            tuple(item.threat_id for item in activations),
            "activated campaign hunt threat IDs",
        )
        threat_by_id = {item.id: item for item in threats}
        for activation in activations:
            threat = threat_by_id.get(activation.threat_id)
            if threat is None:
                raise ValueError("campaign hunt activation has no registered threat")
            if (
                activation.activation_trigger_reference_id
                != threat.activation_trigger_reference_id
            ):
                raise ValueError(
                    "campaign hunt activation disagrees with threat trigger"
                )
            if activation.rule_id != threat.rule_id:
                raise ValueError("campaign hunt activation uses another rule")
        object.__setattr__(self, "threats", threats)
        object.__setattr__(self, "activations", activations)

    def threat(self, threat_id: str) -> CampaignHuntThreat | None:
        _validate_non_empty_string(threat_id, "campaign hunt threat id")
        return next((item for item in self.threats if item.id == threat_id), None)

    def has_source_consequence(self, consequence_id: str) -> bool:
        _validate_non_empty_string(
            consequence_id,
            "campaign hunt source consequence id",
        )
        return any(
            item.source_consequence_id == consequence_id for item in self.threats
        )

    def is_active(self, threat_id: str) -> bool:
        _validate_non_empty_string(threat_id, "campaign hunt threat id")
        return any(item.threat_id == threat_id for item in self.activations)


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
