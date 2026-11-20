"""Explicit single acquisition sources for fixtures without Talent choices.

Choice-bearing or repeated acquisitions must be declared by the caller. These
helpers never fill missing prerequisites, waive paid Requirements, or convert
malformed identifiers.
"""
from towr.domain.talent_models import (
    AcquiredTalent, TalentAcquisition, TalentAcquisitionPhase, TalentFunding,
)
from towr.domain.talent_catalog import TalentId


def paid_talent(id: TalentId) -> AcquiredTalent:
    return AcquiredTalent(id, (TalentAcquisition(
        TalentAcquisitionPhase.ADVANCEMENT, TalentFunding.XP),))


def free_talent(id: TalentId) -> AcquiredTalent:
    return AcquiredTalent(id, (TalentAcquisition(
        TalentAcquisitionPhase.CREATION, TalentFunding.FREE),))


def paid_talent_document(id: TalentId) -> dict:
    """An explicit single paid source for JSON inputs, not expected results."""
    if type(id) is not TalentId:
        raise TypeError('fixture Talent document requires its typed identifier')
    return dict(id=id.value,acquisitions=[dict(phase='advancement',funding='xp',
        choice=None,devotion_confirmed=None)])
