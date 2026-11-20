"""Explicit Undead Minion effects, GM1.1 VII168; Skeletal Steed C12.

The native owner must authorize this source from the actual creature's typed
definition. Neither an actor name nor a rider's Talents grant this package.
Psychological immunity does not remove physical or unclassified Conditions.
"""
from dataclasses import dataclass, replace

from towr.domain.condition_models import EffectClassification, EffectImmunity, StaggerChoice
from towr.domain.injury_models import MinionStaggerDefeatOutcome, MinionStaggerDefeatSpec


UNDEAD_MINION_RULE_ID = 'BOOK-GM-GUIDE:1.1:p168:undead-minion'


def _actor(actor_id):
    if type(actor_id) is not str or not actor_id.strip():
        raise TypeError('Undead Minion requires an exact actual actor identifier')


@dataclass(frozen=True, slots=True)
class UndeadMinionSource:
    actor_id: str
    rule_id: str = UNDEAD_MINION_RULE_ID

    def __post_init__(self):
        _actor(self.actor_id)
        if type(self.rule_id) is not str:
            raise TypeError('Undead Minion requires its exact rule source')
        if self.rule_id != UNDEAD_MINION_RULE_ID:
            raise ValueError('Undead Minion requires its actual GM168 rule source')


def validate_undead_minion_source(source: UndeadMinionSource | None, actor_id: str) -> bool:
    _actor(actor_id)
    if source is None:
        return False
    if type(source) is not UndeadMinionSource:
        raise TypeError('Undead Minion permission requires its exact typed source')
    replace(source)
    if source.actor_id != actor_id:
        raise ValueError('Undead Minion source belongs to another actor')
    return True


def undead_minion_effect_immunities(source: UndeadMinionSource | None,
        actor_id: str) -> tuple[EffectImmunity, ...]:
    if not validate_undead_minion_source(source, actor_id):
        return ()
    return (EffectImmunity(EffectClassification.PSYCHOLOGICAL, source.rule_id),)


def undead_minion_stagger_defeat_spec(source: UndeadMinionSource | None,
        actor_id: str) -> MinionStaggerDefeatSpec | None:
    if not validate_undead_minion_source(source, actor_id):
        return None
    return MinionStaggerDefeatSpec(source.rule_id, outcome=MinionStaggerDefeatOutcome.DESTROYED)


def undead_minion_forbidden_stagger_choices(source: UndeadMinionSource | None,
        actor_id: str) -> tuple[StaggerChoice, ...]:
    """Only voluntary reactions; a forced Prone effect remains executable."""
    if not validate_undead_minion_source(source, actor_id):
        return ()
    return (StaggerChoice.GIVE_GROUND, StaggerChoice.FALL_PRONE)
