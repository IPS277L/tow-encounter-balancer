"""NPC Resilience rebuilt from immutable equipment and actual mount/Shield facts."""
from dataclasses import replace

from towr.domain.armour_models import armour_is_worn, body_resilience_bonus, helmet_resilience_bonus
from towr.domain.attack_models import ResilienceProfile
from towr.domain.npc_roster_models import NpcDefinition
from towr.domain.pc_mount_models import PcMountedState, mount_source_resilience_bonus


def npc_equipment_resilience(definition, actor_id, *, shield_held, mount_source):
    """Pure physical base, before any encounter-owned Talent reduction."""
    if type(definition) is not NpcDefinition:
        raise TypeError('NPC equipment Resilience requires its exact complete definition')
    replace(definition)
    if type(definition.resilience) is not ResilienceProfile:
        raise TypeError('NPC equipment requires its exact original ResilienceProfile')
    replace(definition.resilience)
    if type(actor_id) is not str or not actor_id.strip() or type(shield_held) is not bool:
        raise TypeError('NPC equipment Resilience needs an exact actor and held Shield fact')
    components = definition.generated_components
    if components is None:
        if mount_source is not None:
            raise ValueError('numeric NPC definitions cannot invent a mount component')
        return definition.resilience
    if shield_held and components.armour.shield is None:
        raise ValueError('NPC cannot acquire a source-less held Shield')
    mounted = False
    if components.mount is None:
        if mount_source is not None:
            raise ValueError('NPC mount witness requires its actual source component')
    else:
        if type(mount_source) is not PcMountedState:
            raise TypeError('mounted NPC source must retain its exact actual mount witness')
        replace(mount_source)
        if mount_source.actor_id != actor_id or mount_source.mount is not components.mount:
            raise ValueError('NPC mount witness differs from the actor or source component')
        mounted = mount_source.mounted
    bonus = (body_resilience_bonus(components.armour) + helmet_resilience_bonus(components.armour)
        + int(shield_held) + (mount_source_resilience_bonus(components.mount)
            + int(components.armour.barding) if mounted else 0))
    return ResilienceProfile(components.toughness, bonus,
        armoured=True if armour_is_worn(components.armour) and bonus == 0 else None,
        mundane_armour_ward=definition.resilience.mundane_armour_ward)


def npc_mount_resilience_source(state, actor_id, *, mounted=None):
    if not any(enemy.state.actor_id == actor_id for enemy in state.source.enemies):
        raise ValueError('NPC Resilience queries require an actual source NPC')
    if mounted is not None and type(mounted) is not bool:
        raise TypeError('mount override must retain an exact mounted boolean')
    definition = state.source.enemy(actor_id).definition
    components = definition.generated_components
    source_mount = None if components is None else components.mount
    if type(state.mounts) is not tuple or any(type(value) is not PcMountedState for value in state.mounts):
        raise TypeError('NPC equipment queries require the exact actual mount bank')
    if len({value.actor_id for value in state.mounts}) != len(state.mounts):
        raise ValueError('actual mount bank cannot duplicate an actor')
    for value in state.mounts:
        replace(value)
    actual = next((value for value in state.mounts if value.actor_id == actor_id), None)
    if source_mount is None:
        if actual is not None or mounted is not None:
            raise ValueError('NPC without a mount component cannot invent mounted state')
        return None
    if type(actual) is not PcMountedState or actual.mount is not source_mount:
        raise ValueError('NPC actual mount differs from its complete initial source')
    return actual if mounted is None else replace(actual, mounted=mounted)


def npc_base_equipment_resilience(state, actor_id, *, shield_held=None, mounted=None):
    if shield_held is not None and type(shield_held) is not bool:
        raise TypeError('Shield override must retain an exact held boolean')
    from towr.domain.pc_actor_models import pc_companion
    if (not any(enemy.state.actor_id == actor_id for enemy in state.source.enemies)
            and pc_companion(state,actor_id) is not None):
        if shield_held is not None or mounted is not None:
            raise ValueError('a mount body cannot acquire its rider\'s Shield or mounted override')
        from towr.domain.pc_companion_effect_models import companion_profile
        return companion_profile(state,actor_id).definition.resilience
    mount = npc_mount_resilience_source(state, actor_id, mounted=mounted)
    initial = state.source.enemy(actor_id)
    enemy = state.enemy(actor_id)
    if initial.state.actor_id != actor_id or enemy.state.actor_id != actor_id:
        raise ValueError('NPC equipment queries cannot alias another actual actor')
    if enemy.definition != initial.definition:
        raise ValueError('NPC equipment cannot replace its immutable initial definition')
    if initial.definition.generated_components is None and shield_held is not None:
        raise ValueError('numeric NPC definitions cannot invent a physical Shield transition')
    return npc_equipment_resilience(initial.definition, actor_id,
        shield_held=enemy.state.holds_shield if shield_held is None else shield_held,
        mount_source=mount)


def npc_current_resilience(state, actor_id, *, shield_held=None, mounted=None):
    from towr.domain.pc_armour_bane_models import armour_bane_resilience
    return armour_bane_resilience(state, actor_id, npc_base_equipment_resilience(state, actor_id,
        shield_held=shield_held, mounted=mounted))
