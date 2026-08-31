from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CampaignCaptivityRecord:
    """One active capture fact; escape and release are separate future changes."""

    id: str
    campaign_id: str
    captive_actor_id: str
    captor_reference_id: str
    consequence_reference_id: str
    source_application_id: str
    source_proof_id: str
    source_consequence_id: str
    battle_id: str
    retreat_id: str
    rule_id: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.id, "campaign captivity record id"),
            (self.campaign_id, "campaign captivity campaign_id"),
            (self.captive_actor_id, "campaign captivity captive_actor_id"),
            (self.captor_reference_id, "campaign captivity captor_reference_id"),
            (
                self.consequence_reference_id,
                "campaign captivity consequence_reference_id",
            ),
            (
                self.source_application_id,
                "campaign captivity source_application_id",
            ),
            (self.source_proof_id, "campaign captivity source_proof_id"),
            (
                self.source_consequence_id,
                "campaign captivity source_consequence_id",
            ),
            (self.battle_id, "campaign captivity battle_id"),
            (self.retreat_id, "campaign captivity retreat_id"),
            (self.rule_id, "campaign captivity rule_id"),
        ):
            _validate_non_empty_string(value, name)


@dataclass(frozen=True, slots=True)
class CampaignCaptivityState:
    """Narrow aggregate of currently active captivity records."""

    campaign_id: str
    captures: tuple[CampaignCaptivityRecord, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.campaign_id, "campaign captivity campaign_id")
        captures = tuple(self.captures)
        if not all(isinstance(item, CampaignCaptivityRecord) for item in captures):
            raise TypeError(
                "captures must contain CampaignCaptivityRecord values"
            )
        if any(item.campaign_id != self.campaign_id for item in captures):
            raise ValueError("all captivity records must belong to the campaign")
        _validate_unique_values(
            tuple(item.id for item in captures),
            "campaign captivity record IDs",
        )
        _validate_unique_values(
            tuple(item.captive_actor_id for item in captures),
            "active captive actor IDs",
        )
        object.__setattr__(self, "captures", captures)

    def has_source_application(self, application_id: str) -> bool:
        _validate_non_empty_string(application_id, "capture source application id")
        return any(
            item.source_application_id == application_id for item in self.captures
        )

    def is_captive(self, actor_id: str) -> bool:
        _validate_non_empty_string(actor_id, "captive actor id")
        return any(item.captive_actor_id == actor_id for item in self.captures)


def _validate_unique_values(values: tuple[str, ...], name: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
