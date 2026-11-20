"""Source-ordered observations of actual NPC shots and Reload actions."""
from dataclasses import dataclass,replace


@dataclass(frozen=True,slots=True)
class PcNpcRangedCount:
    actor_id: str
    shots: int
    bonus_shots: int
    reload_actions: int

    def __post_init__(self):
        if type(self.actor_id) is not str or not self.actor_id.strip():
            raise TypeError('NPC ranged count requires its exact actor identifier')
        for name in ('shots','bonus_shots','reload_actions'):
            if type(getattr(self,name)) is not int or getattr(self,name)<0:
                raise ValueError('NPC ranged counters must be nonnegative exact integers')
        if self.bonus_shots>self.shots:
            raise ValueError('Repeater bonus count cannot exceed actual shots')


def validate_npc_ranged_counts(counts,scenario,*,started_rounds: int,actions: int,rapid_reload_counts=None):
    from towr.simulation.pc_rapid_reload_statistics import rapid_reload_count_by_actor
    rapid=rapid_reload_count_by_actor(rapid_reload_counts,scenario)
    from towr.domain.pc_npc_ranged_source_models import (
        pc_npc_ranged_profile,validate_pc_npc_ranged_policies,
    )
    from towr.domain.weapon_capability_models import weapon_ranged_requirements
    from towr.domain.weapon_catalog import WeaponKind
    validate_pc_npc_ranged_policies(scenario)
    actors=tuple(policy.actor_id for policy in scenario.npc_ranged_policies)
    if not actors:
        if counts is not None:
            raise ValueError('NPC ranged counters require a ranged source')
        return
    if (type(counts) is not tuple or any(type(row) is not PcNpcRangedCount for row in counts)
            or tuple(row.actor_id for row in counts)!=actors):
        raise ValueError('NPC ranged counts must preserve the complete source order, including zeros')
    for row in counts:
        replace(row)
        definition=scenario.enemy(row.actor_id).definition
        # Rapid Reload can pair one Reload with a second-action shot. Merely
        # owning it cannot authorize two shots or two Reloads in one turn.
        paired=min(rapid.get(row.actor_id,0),row.shots,row.reload_actions)
        if row.shots+row.reload_actions>started_rounds+paired:
            raise ValueError('NPC ranged counts exceed its actual turn budget')
        components=definition.generated_components
        # Rows aggregate every selected unit in the battle, not just the first
        # Shooting profile. A carried Repeater remains a concrete capability.
        kinds=(tuple(item.kind for item in components.weapons) if components is not None
            else (WeaponKind(pc_npc_ranged_profile(definition).weapon_id.value),))
        requirements=weapon_ranged_requirements(kinds)
        if row.bonus_shots and (requirements is None or not requirements.repeater):
            raise ValueError('NPC inventory has no optional bonus-shot weapon')
    if sum(row.shots+row.reload_actions for row in counts)>actions:
        raise ValueError('NPC ranged observations exceed all executed actions')
