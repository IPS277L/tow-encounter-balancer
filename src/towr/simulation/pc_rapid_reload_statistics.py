"""Observed, source-bound Rapid Reload second actions and ordinary NPC Aim."""
from dataclasses import dataclass, replace

from towr.domain.talent_actor_models import npc_definition_acquired_talents
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import has_talent


@dataclass(frozen=True, slots=True)
class PcRapidReloadCount:
    actor_id: str
    count: int

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('Rapid Reload count requires its exact actor identifier')
        if type(self.count) is not int:
            raise TypeError('Rapid Reload count requires an exact integer')
        if self.count < 0:
            raise ValueError('Rapid Reload count cannot be negative')


def rapid_reload_count_actors(scenario):
    return (tuple(member.actor_id for member in scenario.party
        if has_talent(member.talents, TalentId.RAPID_RELOAD))
        + tuple(enemy.state.actor_id for enemy in scenario.enemies
        if has_talent(npc_definition_acquired_talents(enemy.definition), TalentId.RAPID_RELOAD)))


def rapid_reload_count_by_actor(counts, scenario):
    actors = rapid_reload_count_actors(scenario)
    if not actors:
        if counts is not None:
            raise ValueError('Rapid Reload counts require an acquired Talent source')
        return {}
    if (type(counts) is not tuple or any(type(row) is not PcRapidReloadCount for row in counts)
            or tuple(row.actor_id for row in counts) != actors):
        raise ValueError('Rapid Reload counts require every owner in PC then NPC source order, including zeros')
    for row in counts:
        replace(row)
    return {row.actor_id: row.count for row in counts}


def npc_aim_count_actors(scenario):
    from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_profile
    return tuple(policy.actor_id for policy in scenario.npc_ranged_policies
        if pc_npc_ranged_profile(scenario.enemy(policy.actor_id).definition).awareness_profile is not None)


def validate_npc_aim_counts(counts, scenario, *, trials, actions, started_rounds):
    from towr.simulation.pc_melee_models import PcAimCount
    actors = npc_aim_count_actors(scenario)
    if not actors:
        if counts is not None:
            raise ValueError('NPC Aim counts require actual Awareness sources')
        return
    if (type(counts) is not tuple or any(type(row) is not PcAimCount for row in counts)
            or tuple(row.actor_id for row in counts) != actors):
        raise ValueError('NPC Aim counts require complete source-ordered Awareness actors, including zeros')
    for row in counts:
        replace(row)
        if row.count > min(started_rounds, trials * scenario.max_rounds):
            raise ValueError('NPC Aim exceeds its actual one-Aim-per-own-turn budget')
    if sum(row.count for row in counts) > actions:
        raise ValueError('NPC Aim observations exceed all executed actions')


def validate_rapid_reload_counts(counts, scenario, *, trials, actions, started_rounds,
        pc_ranged_counts, npc_ranged_counts, aim_counts=None, npc_aim_counts=None,
        pc_extra_counts=None, npc_extra_counts=()):
    rapid = rapid_reload_count_by_actor(counts, scenario)
    from towr.simulation.pc_ranged_statistics import PcRangedCount
    from towr.simulation.pc_npc_ranged_statistics import PcNpcRangedCount
    ranged = {}
    for rows, kind in ((pc_ranged_counts, PcRangedCount), (npc_ranged_counts, PcNpcRangedCount)):
        if rows is not None and (type(rows) is not tuple or any(type(row) is not kind for row in rows)):
            raise TypeError('Rapid Reload must retain exact typed ranged observations')
        for row in rows or ():
            replace(row)
            if row.actor_id in ranged:
                raise ValueError('ranged observations cannot alias the same actor')
            ranged[row.actor_id] = row
    aiming = {row.actor_id: row.count for row in aim_counts.action_counts} if aim_counts is not None else {}
    aiming.update({row.actor_id: row.count for row in npc_aim_counts or ()})
    seconds = {row.actor_id: row.count for row in aim_counts.second_action_spend_counts} if aim_counts is not None else {}
    for row in (*(pc_extra_counts or ()), *npc_extra_counts):
        seconds[row.actor_id] = seconds.get(row.actor_id, 0) + row.count
    for actor, count in rapid.items():
        row = ranged.get(actor)
        reloads = 0 if row is None else row.reload_actions
        shots = 0 if row is None else row.shots
        if (count > min(started_rounds, trials * scenario.max_rounds)
                or count > reloads or count > shots + aiming.get(actor, 0)
                or count + seconds.get(actor, 0) > started_rounds):
            raise ValueError('Rapid Reload exceeds its actual Reload, shot/Aim or shared second-action turn budget')
    if 2 * sum(rapid.values()) > actions:
        raise ValueError('each Rapid Reload needs its separate actual Reload and second action')
