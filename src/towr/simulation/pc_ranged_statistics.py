"""Observed PC ranged actions and item changes in automatic encounters."""
from dataclasses import dataclass,replace


@dataclass(frozen=True,slots=True)
class PcRangedCount:
    actor_id: str
    shots: int
    bonus_shots: int
    shooting_help_tests: int
    bonus_help_tests: int
    reload_actions: int
    weapon_swaps: int

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('PC ranged count requires its exact actor')
        for name in ('shots','bonus_shots','shooting_help_tests','bonus_help_tests','reload_actions','weapon_swaps'):
            if type(getattr(self,name)) is not int or getattr(self,name)<0:
                raise ValueError('PC ranged counters must be nonnegative exact integers')
        if self.bonus_shots>self.shots or self.bonus_help_tests>self.shooting_help_tests:
            raise ValueError('optional bonus counts exceed their actual Test uses')


def pc_ranged_count_actors(scenario):
    from towr.domain.pc_melee_models import PcMeleePolicy
    return tuple(p.actor_id for p in scenario.party
        if p.policy is PcMeleePolicy.AUTOMATIC_COMBAT and p.pc.ranged is not None)


def validate_pc_ranged_counts(counts,scenario,*,started_rounds,actions,help_counts):
    actors=pc_ranged_count_actors(scenario)
    if not actors:
        if counts is not None:raise ValueError('PC ranged counters require an automatic ranged source')
        return
    if (type(counts) is not tuple or any(type(row) is not PcRangedCount for row in counts)
            or tuple(row.actor_id for row in counts)!=actors):
        raise ValueError('PC ranged counts must retain all source actors in order, including zero rows')
    help_by_actor={row.actor_id:row.count for row in help_counts}
    for row in counts:
        replace(row)
        if (row.shots+row.shooting_help_tests+row.reload_actions>started_rounds
                or row.weapon_swaps>started_rounds
                or row.shooting_help_tests>help_by_actor.get(row.actor_id,0)):
            raise ValueError('PC ranged observations exceed their actual action/turn/Help budget')
        from towr.domain.pc_melee_models import PcMeleeWeapon
        if scenario.participant(row.actor_id).pc.weapon is PcMeleeWeapon.PISTOL and (row.bonus_shots or row.bonus_help_tests):
            raise ValueError('ordinary Pistol has no optional Test bonus')
    if sum(row.shots+row.shooting_help_tests+row.reload_actions for row in counts)>actions:
        raise ValueError('PC ranged observations exceed all executed actions')
