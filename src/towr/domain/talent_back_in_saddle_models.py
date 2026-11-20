"""Back in the Saddle provenance, Player's Guide1.4 III73.

Acquisition prerequisites and the physical rider/mount relationship belong to
the encounter owner. This explicit source only identifies the actual Talent,
actor and mount whose simultaneous standing/remounting is being claimed.
"""
from dataclasses import dataclass, replace

from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import AcquiredTalent


BACK_IN_SADDLE_RULE_ID = 'RULE-TALENT-002:back-in-the-saddle'


def _identifier(value):
    if type(value) is not str or not value.strip():
        raise TypeError('Back in the Saddle requires exact nonempty actor and mount identifiers')


@dataclass(frozen=True, slots=True)
class BackInSaddleSource:
    actor_id: str
    mount_id: str
    talent: AcquiredTalent

    def __post_init__(self):
        _identifier(self.actor_id)
        _identifier(self.mount_id)
        if self.actor_id == self.mount_id:
            raise ValueError('Back in the Saddle requires a distinct actual mount')
        if type(self.talent) is not AcquiredTalent:
            raise TypeError('Back in the Saddle requires its exact acquired Talent source')
        replace(self.talent)
        if self.talent.id is not TalentId.BACK_IN_THE_SADDLE:
            raise ValueError('another Talent cannot authorize Back in the Saddle')


def validate_back_in_saddle_source(source: BackInSaddleSource | None, actor_id: str,
        mount_id: str) -> bool:
    _identifier(actor_id)
    _identifier(mount_id)
    if source is None:
        return False
    if type(source) is not BackInSaddleSource:
        raise TypeError('Back in the Saddle permission requires its exact typed source')
    replace(source)
    if source.actor_id != actor_id or source.mount_id != mount_id:
        raise ValueError('Back in the Saddle source belongs to another actor or mount')
    return True
