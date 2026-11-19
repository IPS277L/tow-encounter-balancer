"""Healthy component-built sources for PG69 actual shove/drag battles."""
from dataclasses import replace

from tests.support.magic_weapon_battles import magic_battle
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_mount_models import CombatMount, RiderKind
from towr.domain.pc_battlefield_models import PcAirspaceSpec


def pc_shove_scene(*, weapon='sling', count=1, loaded=True):
    result = magic_battle(weapon, players=2, npc_toughness=1, count=count)
    actor = result.party[0]
    actor = replace(actor, pc=replace(actor.pc, weapon=PcMeleeWeapon.UNARMED, brawn=6, ranged=None),
        initial_weapon_hand=None, combat_equipment=())
    ally = result.party[1]
    if not loaded:
        ally = replace(ally, combat_equipment=(replace(ally.combat_equipment[0], initially_loaded=False),))
    return replace(result, party=(actor, ally))


def npc_shove_scene():
    result = magic_battle('sling', npc_magic=True, count=2,
        pc_ws=1, pc_toughness=1, npc_toughness=20)
    actor = result.enemies[0]
    generated = replace(actor.definition.generated_components, weapons=(), brawn=6, ranged=None)
    return replace(result, enemies=(generated.participant(actor.state.actor_id), result.enemies[1]),
        npc_ranged_policies=tuple(policy for policy in result.npc_ranged_policies
            if policy.actor_id != actor.state.actor_id))


def pc_drag_scene():
    result = magic_battle('staff', pc_ws=1, pc_toughness=20, npc_toughness=1)
    actor = result.party[0]
    actor = replace(actor, pc=replace(actor.pc, weapon=PcMeleeWeapon.UNARMED, brawn=6),
        initial_weapon_hand=None, combat_equipment=())
    enemy = result.enemies[0]
    generated = replace(enemy.definition.generated_components, mount=CombatMount.HORSE)
    return replace(result, party=(actor,), enemies=(generated.participant(enemy.state.actor_id),),
        facts=replace(result.facts, unmounted=False))


def npc_drag_scene():
    result = magic_battle('staff', pc_ws=1, pc_toughness=1, npc_toughness=20)
    actor = result.enemies[0]
    generated = replace(actor.definition.generated_components, weapons=(), brawn=6)
    return replace(result, party=(replace(result.party[0], mount=CombatMount.HORSE),),
        enemies=(generated.participant(actor.state.actor_id),), facts=replace(result.facts, unmounted=False))


def npc_air_drag_scene(*, weapon='sling'):
    """The PC takes off to shoot; the opposing flying rider genuinely follows."""
    result = magic_battle(weapon, distance='short', pc_ws=1,
        pc_toughness=20, npc_toughness=20)
    member = replace(result.party[0], mount=CombatMount.PEGASUS, rider_kind=RiderKind.HUMAN,
        pc=replace(result.party[0].pc, endurance=1))
    enemy = result.enemies[0]
    generated = replace(enemy.definition.generated_components, weapons=(), brawn=6, strength=10,
        mount=CombatMount.PEGASUS, rider_kind=RiderKind.HUMAN)
    return replace(result, party=(member,), enemies=(generated.participant(enemy.state.actor_id),),
        facts=replace(result.facts, unmounted=False),
        battlefield=replace(result.battlefield, airspace=PcAirspaceSpec(2, True)))
