from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CampaignDebtObligation:
    """Outstanding debt created by a rescue; repayment is a later boundary."""

    id: str
    campaign_id: str
    creditor_reference_id: str
    debt_reference_id: str
    repayment_reference_id: str
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
            (self.id, "campaign debt obligation id"),
            (self.campaign_id, "campaign debt campaign_id"),
            (self.creditor_reference_id, "campaign debt creditor_reference_id"),
            (self.debt_reference_id, "campaign debt debt_reference_id"),
            (self.repayment_reference_id, "campaign debt repayment_reference_id"),
            (
                self.description_reference_id,
                "campaign debt description_reference_id",
            ),
            (self.source_application_id, "campaign debt source_application_id"),
            (self.source_consequence_id, "campaign debt source_consequence_id"),
            (
                self.source_specification_id,
                "campaign debt source_specification_id",
            ),
            (self.battle_id, "campaign debt battle_id"),
            (self.retreat_id, "campaign debt retreat_id"),
            (self.rule_id, "campaign debt rule_id"),
        ):
            _validate_non_empty_string(value, name)
        _validate_unique_values(
            (
                self.creditor_reference_id,
                self.debt_reference_id,
                self.repayment_reference_id,
            ),
            "campaign debt role references",
        )
        subjects = _validate_unique_non_empty_ids(
            self.affected_subject_reference_ids,
            "campaign debt affected subject reference ID",
        )
        object.__setattr__(self, "affected_subject_reference_ids", subjects)


@dataclass(frozen=True, slots=True)
class CampaignDebtState:
    """Narrow campaign aggregate of outstanding rescue debts."""

    campaign_id: str
    obligations: tuple[CampaignDebtObligation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.campaign_id, "campaign debt campaign_id")
        obligations = tuple(self.obligations)
        if not all(isinstance(item, CampaignDebtObligation) for item in obligations):
            raise TypeError(
                "obligations must contain CampaignDebtObligation values"
            )
        if any(item.campaign_id != self.campaign_id for item in obligations):
            raise ValueError("all debt obligations must belong to the campaign")
        _validate_unique_values(
            tuple(item.id for item in obligations),
            "campaign debt obligation IDs",
        )
        _validate_unique_values(
            tuple(item.source_consequence_id for item in obligations),
            "campaign debt source consequence IDs",
        )
        object.__setattr__(self, "obligations", obligations)

    def has_source_consequence(self, consequence_id: str) -> bool:
        _validate_non_empty_string(
            consequence_id,
            "campaign debt source consequence id",
        )
        return any(
            item.source_consequence_id == consequence_id for item in self.obligations
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
