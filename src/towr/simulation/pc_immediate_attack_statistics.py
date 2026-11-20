"""Source-bound free strikes, separate from ordinary action observations.

The current producer is Bash Attack (PG1.4 III73). Each such strike requires
its own ordinary Brawn action, and at most one is currently available per
actor and started round. These aggregate bounds are Bash-specific; they do
not define a budget for future reactive Talents such as Stand and Shoot.
The native replay owner, not these totals, proves and deduplicates each grant.
"""
from dataclasses import dataclass, replace

from towr.domain.talent_actor_models import npc_definition_acquired_talents
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import has_talent


@dataclass(frozen=True, slots=True)
class PcImmediateAttackCount:
    actor_id: str
    count: int

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('immediate Attack count requires its exact actor identifier')
        if type(self.count) is not int:
            raise TypeError('immediate Attack count requires an exact integer')
        if self.count < 0:
            raise ValueError('immediate Attack count cannot be negative')


def immediate_attack_count_actors(scenario) -> tuple[str, ...]:
    """Actual Bash owners in complete PC then NPC source order, without Fate."""
    return (tuple(member.actor_id for member in scenario.party
        if has_talent(member.talents, TalentId.BASH_ATTACK))
        + tuple(enemy.state.actor_id for enemy in scenario.enemies
        if has_talent(npc_definition_acquired_talents(enemy.definition), TalentId.BASH_ATTACK)))


def validate_immediate_attack_counts(counts, scenario, *, started_rounds: int, actions: int) -> None:
    """Validate observations without reserving or incrementing an action.

    Zero observations remain mandatory for every actual owner. The action
    bound refers to each Bash's distinct ordinary Brawn source, not payment
    for its free Melee strike. Full timeline/source ownership stays in replay.
    """
    for name, value in (('started rounds', started_rounds), ('actions', actions)):
        if type(value) is not int:
            raise TypeError('immediate Attack ' + name + ' requires an exact integer')
        if value < 0:
            raise ValueError('immediate Attack ' + name + ' cannot be negative')
    actors = immediate_attack_count_actors(scenario)
    if not actors:
        if counts is not None:
            raise ValueError('immediate Attack counts require an actual Bash Attack owner')
        return
    if type(counts) is not tuple or any(type(row) is not PcImmediateAttackCount for row in counts):
        raise TypeError('immediate Attack counts require exact immutable typed rows')
    for row in counts:
        replace(row)
    if tuple(row.actor_id for row in counts) != actors:
        raise ValueError('immediate Attack counts require every owner in PC then NPC source order, including zeros')
    if any(row.count > started_rounds for row in counts):
        raise ValueError('Bash Attack count exceeds the current one-source-action-per-own-round bound')
    if sum(row.count for row in counts) > actions:
        raise ValueError('each Bash Attack requires a distinct actual ordinary Brawn action')
