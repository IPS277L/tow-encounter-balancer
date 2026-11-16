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


def validate_npc_ranged_counts(counts,scenario,*,started_rounds: int,actions: int):
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
        if row.shots+row.reload_actions>started_rounds:
            raise ValueError('NPC ranged counts exceed its actual turn budget')
        from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_profile
        from towr.domain.ranged_weapon_profiles import ranged_weapon_reload_profile,RangedReloadTrigger
        profile=pc_npc_ranged_profile(scenario.enemy(row.actor_id).definition)
        if (ranged_weapon_reload_profile(profile.weapon_id).trigger is RangedReloadTrigger.AFTER_EVERY_SHOT
                and row.bonus_shots):
            raise ValueError('ordinary Pistol cannot report optional bonus shots')
    if sum(row.shots+row.reload_actions for row in counts)>actions:
        raise ValueError('NPC ranged observations exceed all executed actions')
